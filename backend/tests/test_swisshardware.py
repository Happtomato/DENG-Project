"""Offline checks for the bounded SwissHardware candidate catalog."""

import tempfile
import unittest
import uuid
import json
from pathlib import Path
from unittest.mock import Mock, patch

from psycopg import sql

from backend.retailers.swisshardware.collector import (
    CATALOG, CATEGORIES, canonical_product_url, listing_pages, load_catalog, parse_listing,
    register_listings,
)
from backend.retailers.swisshardware.product import (
    RAW, active_rows, collect_rows, collect_selected, in_scope, parse_product,
    scope_candidates, transform_raw, uncaptured_candidates,
)
from backend.database import ROOT, connect, migrate
from backend.transform import InvalidRecord

EXAMPLES = (
    'msi-geforce-rtx-5080-gaming-trio-oc',
    'kingston-32gb-ddr5-6000mt-s-cl30-dimm-2-x-16gb-6000-mhz-ram-ddr5-dimm',
    'ssd-samsung-990-evo-plus-2tb-m-2-2280',
)


def page(*cards):
    return '<div class="coll__grid">' + ''.join(
        f'<a class="pcard" href="/de/products/{slug}">'
        f'<h3 class="pcard__name">{name}</h3>'
        f'<span class="pcard__price">CHF {price}</span></a>'
        for slug, name, price in cards
    ) + '</div>'


class SwissHardwareCatalogTests(unittest.TestCase):
    def test_listing_contains_only_unique_positive_price_product_links(self):
        html = page(('ssd-a', 'SSD A', '129.90'), ('ssd-a', 'SSD A', '129.90'),
                    ('no-product', 'Placeholder', '0.00'))
        rows = parse_listing(html)
        self.assertEqual([row['slug'] for row in rows], ['ssd-a'])
        self.assertEqual(rows[0]['url'], 'https://swisshw.ch/de/products/ssd-a')
        self.assertEqual(rows[0]['listing_price'], 'CHF 129.90')
        with self.assertRaises(ValueError):
            canonical_product_url('https://other.example/de/products/ssd-a')

    def test_rerun_preserves_manual_selection_and_never_needs_http(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / '2026-10-22'
            raw.mkdir()
            for category in CATEGORIES:
                (raw / f'{category}.html').write_text(
                    page((f'{category}-a', f'{category.upper()} A', '129.90'))
                )
            catalog = load_catalog(Path(directory) / 'new.json')
            self.assertEqual(register_listings(catalog, raw)['new'], 3)
            catalog['products']['gpu-a']['selected'] = True
            (raw / 'gpu.html').write_text(page(('gpu-a', 'GPU A', '119.90')))
            self.assertEqual(register_listings(catalog, raw)['known'], 3)
            self.assertTrue(catalog['products']['gpu-a']['selected'])
            self.assertEqual(catalog['products']['gpu-a']['listing_price'], 'CHF 119.90')

    def test_pagination_merges_pages_and_deduplicates_products(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / '2026-10-22'
            raw.mkdir()
            for category in CATEGORIES:
                first = page((f'{category}-a', 'Product A', '129.90'))
                if category == 'gpu':
                    first += '<a href="/de/collections/carte-graphique?page=2">2</a>'
                    first += '<a href="/de/collections/ram?page=99">wrong category</a>'
                    (raw / 'gpu_p2.html').write_text(page(('gpu-a', 'Product A', '129.90'),
                                                         ('gpu-b', 'Product B', '139.90')))
                (raw / f'{category}.html').write_text(first)
            self.assertEqual(listing_pages((raw / 'gpu.html').read_text(), 'gpu'), 2)
            catalog = load_catalog(Path(directory) / 'new.json')
            report = register_listings(catalog, raw)
            self.assertEqual(report['by_category']['gpu'], 2)
            self.assertEqual(report['new'], 4)

    def test_saved_pages_use_real_identifiers_and_seller(self):
        items = {slug: transform_raw(RAW / '2026-10-22' / (slug + '.json'))
                 for slug in EXAMPLES}
        self.assertEqual(len(items), 3)
        gpu = items['msi-geforce-rtx-5080-gaming-trio-oc']['observation']
        ram = items['kingston-32gb-ddr5-6000mt-s-cl30-dimm-2-x-16gb-6000-mhz-ram-ddr5-dimm']['observation']
        ssd = items['ssd-samsung-990-evo-plus-2tb-m-2-2280']['observation']
        self.assertEqual(gpu['mpn'], 'V531-005R')
        self.assertEqual(gpu['ean'], '04711377292160')
        self.assertIsNone(ram['mpn'])  # JSON-LD variant ID is not a manufacturer MPN.
        self.assertIsNone(ssd['mpn'])
        self.assertEqual(ssd['details']['write_speed_mbps'], 6300)
        self.assertTrue(all('SwissHardware' in item['observation']['seller_name'] for item in items.values()))
        wd = transform_raw(RAW / '2026-10-22/wd-black-sn7100-powered-by-sandisk.json')['observation']
        self.assertEqual(wd['brand'], 'WESTERN DIGITAL')
        self.assertEqual(wd['mpn'], 'WDS100T4X0E-00CJA0')

    def test_scope_rejects_other_brands_and_categories(self):
        self.assertEqual(in_scope('MSI GeForce RTX 5080', 'gpu'), 'MSI')
        self.assertEqual(in_scope('ASUS TUF GeForce RTX 5070', 'gpu'), 'ASUS')
        self.assertEqual(in_scope('FURY Beast DDR5 32GB', 'ram'), 'KINGSTON')
        with self.assertRaises(InvalidRecord):
            in_scope('Palit GeForce RTX 5080', 'gpu', 'Palit')
        with self.assertRaises(InvalidRecord):
            in_scope('Kingston 4GB DDR3', 'ram')
        with self.assertRaisesRegex(InvalidRecord, 'SO-DIMM excluded'):
            in_scope('Kingston FURY Impact 32GB DDR5 SO-DIMM', 'ram')

    def test_product_page_manufacturer_confirms_or_rejects_title_alias(self):
        def html(name, manufacturer, slug):
            url = 'https://swisshw.ch/de/products/' + slug
            product = {'@type': 'Product', 'name': name,
                       'brand': {'@type': 'Brand', 'name': 'SwissHardware'},
                       'offers': {'url': url, 'priceCurrency': 'CHF', 'price': '199.90',
                                  'seller': {'name': 'SwissHardware'}}}
            return (f'<link rel="canonical" href="{url}">'
                    f'<script type="application/ld+json">{json.dumps(product)}</script>'
                    f'<table><tr><td>Fabricant</td><td>{manufacturer}</td></tr></table>')

        when = '2026-10-22T08:00:00+00:00'
        asus = parse_product(html('ASUS TUF GeForce RTX 5070', 'ASUS', 'asus-tuf'),
                             'https://swisshw.ch/de/products/asus-tuf', 'gpu', when)
        fury = parse_product(html('FURY Beast DDR5 32GB', 'Kingston', 'fury-beast'),
                             'https://swisshw.ch/de/products/fury-beast', 'ram', when)
        self.assertEqual(asus['brand'], 'ASUS')
        self.assertEqual(fury['brand'], 'KINGSTON')
        with self.assertRaises(InvalidRecord):
            parse_product(html('MSI GeForce RTX 5070', 'ASUS', 'conflict'),
                          'https://swisshw.ch/de/products/conflict', 'gpu', when)
        with self.assertRaises(InvalidRecord):
            parse_product(html('Palit GeForce RTX 5070', 'Palit', 'foreign'),
                          'https://swisshw.ch/de/products/foreign', 'gpu', when)

    def test_all_listing_links_remain_candidates_until_detail_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'catalog.json'
            path.write_text(json.dumps({'version': 1, 'source': 'swisshardware', 'listings': {},
                                        'products': {
                                            'known': {'slug': 'known', 'category': 'ram',
                                                      'name': 'FURY Beast DDR5 32GB'},
                                            'unclear': {'slug': 'unclear', 'category': 'gpu',
                                                        'name': 'Gaming graphics card'},
                                        }}))
            self.assertEqual([r['slug'] for r in scope_candidates(path)], ['unclear', 'known'])
            archived = root / 'raw' / '2026-10-21'
            archived.mkdir(parents=True)
            (archived / 'known.json').write_text('{}')
            with patch('backend.retailers.swisshardware.product.RAW', root / 'raw'):
                uncaptured, reused = uncaptured_candidates(path)
            self.assertEqual([row['slug'] for row in uncaptured], ['unclear'])
            self.assertEqual(reused, 1)

    def test_same_day_selected_captures_make_no_http_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            source = load_catalog(CATALOG)
            source['products'] = {key: row for key, row in source['products'].items()
                                  if (RAW / '2026-10-22' / (key + '.json')).exists() and row['selected']}
            path = Path(directory) / 'catalog.json'
            path.write_text(json.dumps(source))
            with patch('backend.retailers.swisshardware.product.today', return_value='2026-10-22'), \
                 patch('backend.retailers.swisshardware.product.requests.Session') as session:
                report = collect_selected(path, RAW / '2026-10-22', max_products=3)
        self.assertEqual(report['product_requests'], 0)
        self.assertEqual(report['reused_today'], len(source['products']))
        session.assert_not_called()

    def test_failed_product_request_still_consumes_the_daily_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / '2026-10-22'
            rows = [
                {'slug': 'test-swiss-a', 'category': 'gpu',
                 'url': 'https://swisshw.ch/de/products/test-swiss-a'},
                {'slug': 'test-swiss-b', 'category': 'gpu',
                 'url': 'https://swisshw.ch/de/products/test-swiss-b'},
            ]
            robots = Mock(text='User-agent: *\nAllow: /')
            failed = Mock(status_code=404, headers={'Content-Type': 'text/html'})
            session = Mock()
            session.get.side_effect = [robots, failed]
            with patch('backend.retailers.swisshardware.product.today', return_value='2026-10-22'), \
                 patch('backend.retailers.swisshardware.product.requests.Session', return_value=session), \
                 patch('backend.retailers.swisshardware.product.time.sleep'):
                report = collect_rows(rows, raw, max_products=1, delay=3)
        self.assertEqual(report['product_requests'], 1)
        self.assertEqual(report['saved'], 0)
        self.assertEqual(report['deferred'], 1)
        self.assertEqual(len(report['errors']), 1)
        self.assertEqual(session.get.call_count, 2)  # robots.txt plus one product page

    def test_daily_cap_counts_only_uncaptured_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / '2026-10-22'
            raw.mkdir()
            (raw / 'known.json').write_text('{}')
            rows = [{'slug': slug, 'category': 'gpu',
                     'url': 'https://swisshw.ch/de/products/' + slug}
                    for slug in ('known', 'new-a', 'new-b')]
            robots = Mock(text='User-agent: *\nAllow: /')
            good = Mock(status_code=200, headers={'Content-Type': 'text/html'}, text='<html/>')
            session = Mock()
            session.get.side_effect = [robots, good]
            with patch('backend.retailers.swisshardware.product.today', return_value='2026-10-22'), \
                 patch('backend.retailers.swisshardware.product.requests.Session', return_value=session), \
                 patch('backend.retailers.swisshardware.product.time.sleep'):
                report = collect_rows(rows, raw, max_products=1, delay=3)
        self.assertEqual(report['product_requests'], 1)
        self.assertEqual(report['reused_today'], 1)
        self.assertEqual(report['deferred'], 1)
        self.assertEqual(session.get.call_count, 2)

    def test_selected_saved_import_is_idempotent_in_isolated_schema(self):
        with tempfile.TemporaryDirectory() as temp, connect() as conn:
            schema = 'swiss_test_' + uuid.uuid4().hex
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            try:
                conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
                migrate(conn)
                # import_saved opens its own connection, so run the same ingestion
                # primitive here under an isolated schema instead.
                from backend.ingestion import ingest_file
                paths = [RAW / '2026-10-22' / (slug + '.json') for slug in EXAMPLES]
                first = [ingest_file(conn, p, 'swisshardware', transformed=transform_raw(p)) for p in paths]
                again = [ingest_file(conn, p, 'swisshardware', transformed=transform_raw(p)) for p in paths]
                self.assertEqual([r['status'] for r in first], ['loaded'] * 3)
                self.assertEqual([r['status'] for r in again], ['duplicate'] * 3)
                self.assertEqual(conn.execute('SELECT count(*) n FROM price_history').fetchone()['n'], 3)
            finally:
                conn.execute('SET search_path TO public')
                conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

    def test_missing_mpn_offer_is_stored_but_not_tracked_daily(self):
        with connect() as conn:
            schema = 'swiss_test_' + uuid.uuid4().hex
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            try:
                conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
                migrate(conn)
                from backend.ingestion import ingest_file
                path = RAW / '2026-10-22' / 'kingston-32gb-ddr5-6000mt-s-cl30-dimm-2-x-16gb-6000-mhz-ram-ddr5-dimm.json'
                item = transform_raw(path)
                self.assertIsNone(item['observation']['mpn'])
                item.update(active=False, tracking_reason='No verified manufacturer MPN on product page')
                self.assertEqual(ingest_file(conn, path, 'swisshardware', transformed=item)['status'], 'loaded')
                row = conn.execute('SELECT is_active,tracking_reason,product_url FROM retailer_product').fetchone()
                self.assertFalse(row['is_active'])
                self.assertIn('No verified manufacturer MPN', row['tracking_reason'])
                self.assertTrue(row['product_url'].startswith('https://swisshw.ch/de/products/'))
                self.assertEqual(len(active_rows(conn)), 0)
                self.assertEqual(conn.execute('SELECT count(*) n FROM price_history').fetchone()['n'], 1)
            finally:
                conn.execute('SET search_path TO public')
                conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

    def test_exact_ean_and_mpn_link_existing_product_without_overwriting_specs(self):
        with connect() as conn:
            schema = 'swiss_test_' + uuid.uuid4().hex
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
            try:
                conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
                migrate(conn)
                from backend.ingestion import ingest_file
                from backend.transform import transform_file
                media_path = next((ROOT / 'data/raw/mediamarkt').glob('2155505_*.json'))
                swiss_path = RAW / '2026-10-22/samsung-ssd-990-pro-m-2-2280-nvme-1024-gb.json'
                self.assertEqual(ingest_file(conn, media_path, transformed=transform_file(media_path))['status'], 'loaded')
                before = conn.execute('SELECT capacity_gb,interface FROM ssd_details').fetchone()
                self.assertEqual(ingest_file(conn, swiss_path, 'swisshardware',
                                             transformed=transform_raw(swiss_path))['status'], 'loaded')
                self.assertEqual(conn.execute('SELECT count(*) n FROM product').fetchone()['n'], 1)
                self.assertEqual(conn.execute('SELECT count(*) n FROM retailer_product').fetchone()['n'], 2)
                self.assertEqual(conn.execute('SELECT capacity_gb,interface FROM ssd_details').fetchone(), before)
            finally:
                conn.execute('SET search_path TO public')
                conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


if __name__ == '__main__':
    unittest.main()
