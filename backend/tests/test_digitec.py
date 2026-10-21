"""Digitec contract and SQL writes are tested only in temporary schemas."""
import hashlib
import base64
import json
import tempfile
import unittest
import uuid
from datetime import timedelta
from pathlib import Path

from psycopg import sql

from backend.database import ROOT, connect, migrate
from backend.ingestion import ingest_file
from backend.retailers.digitec import importer
from backend.transform import InvalidRecord, transform_file


def media_fixture(sku='2230728'):
    return transform_file(next((ROOT / 'data/raw/mediamarkt').glob(sku + '_*.json')))


def authorised_test_record(observation):
    return {
        'source': 'digitec', 'access_method': 'authorized_export',
        'permission_reference': 'isolated-test-only',
        'sku': '12345678', 'product_url': 'https://www.digitec.ch/de/s1/product/test-12345678',
        'ean': observation['ean'], 'brand': observation['brand'],
        'category': observation['category'], 'product_name': observation['name'],
        'currency': 'CHF', 'price_chf': str(observation['price']),
        'seller_name': 'Test Seller', 'observed_at': observation['observed'].isoformat(),
        'availability': 'InStock',
    }


def manual_test_files(directory, observation):
    product_id = base64.b64encode(b'Product\nd12345678:1:42').decode()
    product = {'@type':'Product','sku':'12345678','gtin':observation['ean'],
               'brand':{'name':observation['brand']},'name':observation['name'],
               'offers':{'price':'269.00','priceCurrency':'CHF','availability':'InStock'}}
    next_data = {'props':{'pageProps':{'preloadedQuery':{'rawResponse':{'data':{'product':{
        'id':product_id,'offer':{'shopOfferType':'RETAIL'},
        'defaultCustomerPrice':{'currency':'CHF','amountInclusive':269}}}}}}}}
    html = ('<html><head><link rel="canonical" href="https://www.digitec.ch/de/s1/product/test-12345678">'
            f'<meta property="gtin" content="{observation["ean"]}">'
            '<meta property="product:price:amount" content="269.00">'
            '<meta property="product:price:currency" content="CHF">'
            f'<script type="application/ld+json">{json.dumps(product)}</script>'
            f'<script id="__NEXT_DATA__">{json.dumps(next_data)}</script></head></html>')
    chart = {'data':{'productById':{'id':product_id,
        'price':{'currency':'CHF','amountInclusive':{'source':'269.00','parsedValue':269}},
        'offers':{'newOffers':{'cheapestOffer':{'product':{'id':'marketplace'}}}},
        'priceHistory':{'points':[{'validFrom':observation['observed'].isoformat(),
                                   'price':{'currency':'CHF','amountInclusive':269}}],
                        'hasHistoryOlderThan3Months':True}}}}
    html_path,chart_path = directory / 'page.html',directory / 'chart.json'
    html_path.write_text(html)
    chart_path.write_text(json.dumps(chart))
    return html_path,chart_path


class ContractTests(unittest.TestCase):
    def test_old_mockup_cannot_be_loaded(self):
        old = next((ROOT / 'backend/tests/fixtures/digitec').glob('54237902_*.json'))
        with self.assertRaises(InvalidRecord):
            importer.validated(json.loads(old.read_text()))

    def test_rejects_missing_authorization_seller_price_and_insecure_url(self):
        record = authorised_test_record(media_fixture()['observation'])
        for change in ({'permission_reference': ''}, {'seller_name': None},
                       {'price_chf': None}, {'product_url': 'http://www.digitec.ch/test-12345678'},
                       {'currency': 'EUR'}):
            with self.subTest(change=change), self.assertRaises(InvalidRecord):
                importer.validated({**record, **change})


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect()
        self.schema = 'digitec_test_' + uuid.uuid4().hex
        self.conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
        migrate(self.conn)
        self.media = media_fixture()
        assert ingest_file(self.conn, Path(self.media['path']), transformed=self.media)['status'] == 'loaded'
        self.tmp = tempfile.TemporaryDirectory()
        self.inbox = Path(self.tmp.name) / 'inbox'
        self.inbox.mkdir()
        self.raw = Path(self.tmp.name) / 'raw'

    def tearDown(self):
        self.tmp.cleanup()
        self.conn.execute('SET search_path TO public')
        self.conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.conn.close()

    def write(self, row, name='offer.json'):
        path = self.inbox / name
        path.write_text(json.dumps(row), encoding='utf-8')
        return path

    def count(self, table):
        return self.conn.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(table))).fetchone()['n']

    def test_preview_apply_rerun_and_provenance(self):
        record = authorised_test_record(self.media['observation'])
        source = self.write(record)
        preview = importer.run(self.inbox, conn=self.conn, raw_dir=self.raw)
        self.assertEqual((preview['ready'], self.count('retailer_product')),(1,1))
        self.assertFalse(self.raw.exists())
        applied = importer.run(self.inbox, conn=self.conn, raw_dir=self.raw, apply=True)
        self.assertEqual(applied['loaded'],1)
        self.assertEqual((self.count('product'),self.count('retailer_product'),self.count('price_history')),(1,2,2))
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertEqual((self.raw / (digest + '.json')).read_bytes(),source.read_bytes())
        row = self.conn.execute('''SELECT r.name,rp.product_id,ph.seller_name,ph.source_url,ph.raw_sha256
            FROM price_history ph JOIN retailer_product rp USING(retailer_product_id)
            JOIN retailer r USING(retailer_id) WHERE r.name='Digitec' ''').fetchone()
        self.assertEqual((row['seller_name'],row['raw_sha256']),('Test Seller',digest))
        self.assertEqual(row['source_url'],record['product_url'])
        comparison = self.conn.execute('''SELECT platform,price_chf FROM hardware_prices
            WHERE product_id=%s ORDER BY platform''', (row['product_id'],)).fetchall()
        self.assertEqual([offer['platform'] for offer in comparison],['Digitec','MediaMarkt'])
        self.assertEqual(importer.run(self.inbox, conn=self.conn, raw_dir=self.raw, apply=True)['duplicate'],1)
        self.assertEqual(self.count('price_history'),2)

    def test_next_day_same_price_is_new_and_conflicting_timestamp_rejected(self):
        record = authorised_test_record(self.media['observation'])
        self.write(record, 'first.json')
        self.assertEqual(importer.run(self.inbox, conn=self.conn, raw_dir=self.raw, apply=True)['loaded'],1)
        later = {**record, 'observed_at': (self.media['observation']['observed'] + timedelta(days=1)).isoformat()}
        self.write(later, 'later.json')
        self.assertEqual(importer.run(self.inbox, conn=self.conn, raw_dir=self.raw, apply=True)['loaded'],1)
        self.assertEqual(self.count('price_history'),3)
        self.write({**record, 'price_chf': '1.00'}, 'conflict.json')
        report = importer.run(self.inbox, conn=self.conn, raw_dir=self.raw, apply=True)
        self.assertEqual(report['rejected'],1)
        self.assertIn('conflicting values',next(x['reason'] for x in report['results'] if x['status']=='rejected'))
        self.assertEqual(self.count('price_history'),3)

    def test_unmatched_identifier_never_creates_product(self):
        record = authorised_test_record(self.media['observation'])
        record['ean'] = media_fixture('2155505')['observation']['ean']
        self.write(record)
        preview = importer.run(self.inbox, conn=self.conn, raw_dir=self.raw)
        self.assertEqual(preview['rejected'],1)
        applied = importer.run(self.inbox, conn=self.conn, raw_dir=self.raw, apply=True)
        self.assertEqual(applied['rejected'],1)
        self.assertEqual((self.count('product'),self.count('retailer_product'),self.count('price_history')),(1,1,1))

    def test_empty_inbox_has_no_database_or_network_effect(self):
        report = importer.run(self.inbox, conn=self.conn, raw_dir=self.raw, apply=True)
        self.assertEqual(report['status'],'awaiting_authorized_source_data')
        self.assertFalse(self.raw.exists())

    def test_manual_html_and_chart_load_only_current_retail_price(self):
        ssd = media_fixture('2155505')
        self.assertEqual(ingest_file(self.conn,Path(ssd['path']),transformed=ssd)['status'],'loaded')
        html,chart = manual_test_files(Path(self.tmp.name),ssd['observation'])
        captured_at = (ssd['observation']['observed'] + timedelta(days=1)).isoformat()
        preview = importer.import_manual_snapshot(html,chart,captured_at,'ssd',conn=self.conn,
                                                  input_dir=self.inbox,raw_dir=self.raw)
        self.assertEqual((preview['status'],preview['historical_change_points_in_source']),('ready',1))
        self.assertFalse(self.raw.exists())
        applied = importer.import_manual_snapshot(html,chart,captured_at,'ssd',apply=True,conn=self.conn,
                                                  input_dir=self.inbox,raw_dir=self.raw)
        self.assertEqual(applied['status'],'loaded')
        self.assertTrue(applied['marketplace_offer_excluded'])
        self.assertEqual((applied['historical_change_points_imported'],self.count('retailer_price_change')),(1,1))
        self.assertEqual(self.count('price_history'),3)
        repeated = importer.import_manual_snapshot(html,chart,captured_at,'ssd',apply=True,
            conn=self.conn,input_dir=self.inbox,raw_dir=self.raw)
        self.assertEqual((repeated['status'],repeated['historical_change_points_duplicate']),('duplicate',1))
        self.assertEqual(self.count('price_history'),3)

    def test_manual_chart_must_match_product_and_retail_price(self):
        html,chart = manual_test_files(Path(self.tmp.name),self.media['observation'])
        captured_at = (self.media['observation']['observed'] + timedelta(days=1)).isoformat()
        data = json.loads(chart.read_text())
        data['data']['productById']['price']['amountInclusive'] = 258
        chart.write_text(json.dumps(data))
        with self.assertRaisesRegex(InvalidRecord,'prices disagree'):
            importer.import_manual_snapshot(html,chart,captured_at,'ssd',conn=self.conn,
                                            input_dir=self.inbox,raw_dir=self.raw)
        self.assertEqual(self.count('price_history'),1)

    def test_older_chart_adds_only_new_change_points_and_keeps_null_gap(self):
        ssd = media_fixture('2155505')
        self.assertEqual(ingest_file(self.conn,Path(ssd['path']),transformed=ssd)['status'],'loaded')
        html,chart = manual_test_files(Path(self.tmp.name),ssd['observation'])
        captured_at = (ssd['observation']['observed'] + timedelta(days=3)).isoformat()
        importer.import_manual_snapshot(html,chart,captured_at,'ssd',apply=True,
                                        conn=self.conn,input_dir=self.inbox,raw_dir=self.raw)
        data = json.loads(chart.read_text())
        data['data']['productById']['priceHistory']['points'].append({
            'validFrom':(ssd['observation']['observed'] + timedelta(days=1)).isoformat(),
            'price':None})
        chart.write_text(json.dumps(data))
        result = importer.import_manual_snapshot(html,chart,captured_at,'ssd',apply=True,
                                                 conn=self.conn,input_dir=self.inbox,raw_dir=self.raw)
        self.assertEqual((result['historical_change_points_imported'],
                          result['historical_change_points_duplicate']),(1,1))
        self.assertEqual(self.count('retailer_price_change'),2)
        self.assertEqual(self.count('price_history'),3)
        gap = self.conn.execute("SELECT price_chf,point_type FROM retailer_price_change WHERE point_type='no_price'").fetchone()
        self.assertIsNone(gap['price_chf'])

    def test_chart_only_manifest_imports_history_without_inventing_observation(self):
        source_root = Path(self.tmp.name) / 'source'
        source = source_root / 'RAM' / 'CMK64GX5M2B6000Z30.json'
        source.parent.mkdir(parents=True)
        chart = {'data':{'productById':{
            'id':base64.b64encode(b'Product\nd12345678:1:42').decode(),
            'name':'Vengeance',
            'price':{'currency':'CHF','amountInclusive':269},
            'priceHistory':{'points':[
                {'validFrom':'2026-10-15T12:00:00Z','price':{'currency':'CHF','amountInclusive':199}},
                {'validFrom':'2026-10-16T12:00:00Z','price':None}]}}}}
        source.write_text(json.dumps(chart))
        manifest = Path(self.tmp.name) / 'manifest.json'
        entry = {'file':str(source),'mediamarkt_sku':'2230728',
                 'mpn':'CMK64GX5M2B6000Z30','source_name':'Vengeance'}
        manifest.write_text(json.dumps([entry]))
        preview = importer.import_chart_manifest(manifest,conn=self.conn,source_root=source_root,
                                                  raw_dir=self.raw)
        self.assertEqual((preview['ready'],preview['rejected']), (1,0), preview)
        self.assertEqual(self.count('retailer_price_change'),0)
        applied = importer.import_chart_manifest(manifest,apply=True,conn=self.conn,
                                                  source_root=source_root,raw_dir=self.raw)
        self.assertEqual((applied['loaded'],self.count('retailer_price_change')),(1,2))
        self.assertEqual((self.count('retailer_product'),self.count('price_history')),(2,1))
        self.assertIsNone(self.conn.execute("SELECT product_url FROM retailer_product WHERE retailer_sku='12345678'").fetchone()['product_url'])
        repeated = importer.import_chart_manifest(manifest,apply=True,conn=self.conn,
                                                   source_root=source_root,raw_dir=self.raw)
        self.assertEqual((repeated['duplicate'],self.count('retailer_price_change')),(1,2))
        manifest.write_text(json.dumps([{**entry,'mpn':'WRONG'}]))
        rejected = importer.import_chart_manifest(manifest,conn=self.conn,source_root=source_root)
        self.assertEqual(rejected['rejected'],1)


if __name__ == '__main__':
    unittest.main()
