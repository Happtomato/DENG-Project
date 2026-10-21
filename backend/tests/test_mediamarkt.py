"""Offline regression checks: real reduced HTML plus isolated mocked HTTP."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from backend.retailers.mediamarkt import collector as p
HERE = Path(p.__file__).resolve().parent
FIXTURES = Path(__file__).parent / 'fixtures/mediamarkt'
CONFIG = json.loads((HERE / 'scope.json').read_text(encoding='utf-8'))
RAM = '_corsair-vengeance-ddr5-2230728.html'
SSD = '_samsung-990-pro-nvme-m-2-ssd-2155505.html'
CONFLICT = '_kingston-m2-1tb-nv3-nvme-pcie-40-x-4-1-tb-ssd-0-intern-145381326.html'


def html(name):
    return (FIXTURES / name).read_text(encoding='utf-8')


def url(name):
    return p.ORIGIN + '/de/product/' + name


def record(name):
    return p.mm.parse_html(html(name), p.mm.PRODUCT_URL if name == 'gpu.html' else url(name), 'saved_html')


def report():
    return dict(run_id='offline-test', accepted=0, excluded=0, review=0, skipped_today=0,
                remaining_due=0, missing_price=0, errors=[], pages=0)


class ParsingTests(unittest.TestCase):
    def test_gpu_payload_and_clock_semantics(self):
        r = record('gpu.html')
        self.assertEqual(r['gpu_details']['boost_clock_mhz'], 2512)
        self.assertIsNone(r['gpu_details']['tdp_watts'])
        self.assertEqual(r['product']['generation'], 'RTX 50 Series')
        self.assertEqual(r['raw_payload'], p.mm.find_product_jsonld(p.mm.BeautifulSoup(html('gpu.html'),'html.parser'),'2277751'))
        self.assertEqual(p.scope_decision(r,'gpu',CONFIG['gpu']), ('excluded', 'gpu_boardpartner_filter'))

    def test_strict_gpu_board_partner_and_brand_scope(self):
        r = record('gpu.html')
        r['brand']['name'] = 'MSI'
        self.assertEqual(p.scope_decision(r,'gpu',CONFIG['gpu'])[0], 'accepted')
        r['brand']['name'] = 'ASUS'
        r['product']['product_name'] = 'ASUS ROG Strix GeForce RTX 5070'
        self.assertEqual(p.scope_decision(r,'gpu',CONFIG['gpu'])[0], 'accepted')
        r['product']['product_name'] = 'ASUS TUF Gaming GeForce RTX 5070'
        self.assertEqual(p.scope_decision(r,'gpu',CONFIG['gpu'])[0], 'excluded')
        r['brand']['name'] = 'GIGABYTE'
        self.assertEqual(p.scope_decision(r,'gpu',CONFIG['gpu'])[0], 'excluded')

    def test_strict_ram_and_ssd_brands(self):
        self.assertEqual(p.brand_decision('ram','G.Skill','G.SKILL kit',CONFIG['ram'])[0], 'accepted')
        self.assertEqual(p.brand_decision('ram','ADATA','ADATA DIMM',CONFIG['ram'])[0], 'excluded')
        self.assertEqual(p.brand_decision('ssd','WESTERN DIGITAL','WD_BLACK',CONFIG['ssd'])[0], 'accepted')
        self.assertEqual(p.brand_decision('ssd','CRUCIAL','NVMe',CONFIG['ssd'])[0], 'excluded')
        self.assertEqual(p.brand_decision('ssd',None,'unknown',CONFIG['ssd'])[0], 'review')

    def test_listing_prefilter_avoids_obvious_off_scope_requests(self):
        self.assertFalse(p.candidate_brand_allowed({'category':'gpu','title':'SAPPHIRE Radeon RX 9070'},CONFIG))
        self.assertFalse(p.candidate_brand_allowed({'category':'gpu','title':'ASUS PRIME RTX 5070'},CONFIG))
        self.assertTrue(p.candidate_brand_allowed({'category':'gpu','title':'ASUS ROG Strix RTX 5070'},CONFIG))
        self.assertTrue(p.candidate_brand_allowed({'category':'gpu','title':'MSI GeForce RTX 5070'},CONFIG))
        self.assertFalse(p.candidate_brand_allowed({'category':'ssd','title':'CRUCIAL P310 NVMe'},CONFIG))
        self.assertTrue(p.candidate_brand_allowed({'category':'gpu','title':'Grafikkarte MSI GeForce RTX 5070'},CONFIG))
        self.assertTrue(p.candidate_brand_allowed({'category':'gpu','title':'Neue Grafikkarte RTX 5070'},CONFIG))
        self.assertFalse(p.candidate_brand_allowed({'category':'gpu','title':'Grafikkarte SAPPHIRE Radeon RX 9070'},CONFIG))

    def test_ram_kit_capacity_and_units(self):
        r = record(RAM)
        self.assertEqual(r['ram_details']['total_capacity_gb'], 64)
        self.assertEqual(r['ram_details']['module_count'], 2)
        self.assertEqual(r['ram_details']['capacity_per_module_gb'], 32)
        self.assertEqual(r['ram_details']['speed_mts'], 6000)
        self.assertEqual(r['ram_details']['cas_latency'], '30')
        self.assertEqual(p.scope_decision(r,'ram',CONFIG['ram'])[0], 'accepted')
        self.assertTrue(all(x is None for x in r['ssd_details'].values()))

    def test_ssd_selects_correct_variant_and_converts_tb(self):
        r = record(SSD)
        self.assertEqual(r['product']['ean'], '8806094215021')
        self.assertEqual(r['ssd_details']['capacity_gb'], 1000)
        self.assertEqual(r['ssd_details']['read_speed_mbps'], 7450)
        self.assertEqual(r['ssd_details']['write_speed_mbps'], 6900)
        self.assertEqual(r['ssd_details']['pcie_generation'], '4.0')
        self.assertEqual(p.scope_decision(r,'ssd',CONFIG['ssd'])[0], 'accepted')

    def test_contradictory_source_is_reviewed(self):
        r = record(CONFLICT)
        self.assertEqual(r['ssd_details']['capacity_gb'], 1000)
        self.assertEqual(p.scope_decision(r,'ssd',CONFIG['ssd']), ('review','ssd_interface_conflict'))

    def test_unsupported_product_and_unproven_condition(self):
        r = record(RAM)
        r['technical_payload']['raw_title'] += ' SO-DIMM'
        self.assertEqual(p.scope_decision(r,'ram',CONFIG['ram'])[0], 'excluded')
        r = record(RAM)
        r['metadata']['item_condition'] = None
        self.assertEqual(p.scope_decision(r,'ram',CONFIG['ram'])[0], 'review')

    def test_missing_product_cannot_use_recommendation(self):
        with self.assertRaises(p.mm.ScraperError):
            p.mm.parse_html(html(SSD), url('_missing-9999999.html'), 'saved_html')

    def test_nonfinite_numbers_and_undefined_in_strings(self):
        for value in ['NaN', 'Infinity', '-Infinity', True]:
            self.assertIsNone(p.mm.normalize_decimal(value))
        soup = p.mm.BeautifulSoup('<script>window.__PRELOADED_STATE__ = {"apolloState":{"text":":undefined,","empty":undefined}};</script>', 'html.parser')
        self.assertEqual(p.mm.load_preloaded_apollo_state(soup), {'text':':undefined,', 'empty':None})

    def test_schema_keys_match_postgres(self):
        import re
        sql = (p.ROOT/'data/initialization.sql').read_text(encoding='utf-8')
        r = record(RAM)
        for table, body in re.findall(r'CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);', sql, re.S):
            columns = re.findall(r'^    (\w+) (?:BIGINT|VARCHAR|TEXT|DATE|NUMERIC|TIMESTAMPTZ|INTEGER|BOOLEAN)\b',body,re.M)
            self.assertEqual(set(r[table]), set(columns), table)


class CatalogueTests(unittest.TestCase):
    def test_listing_deduplicates_and_reports_pages(self):
        for category, name in [('gpu','grafikkarten-751073.html'),('ram','arbeitsspeicher-ram-751074.html'),('ssd','interne-ssd-751115.html')]:
            items, last = p.listing(html(name), CONFIG[category]['category_url'])
            self.assertEqual(len(items),12)
            self.assertEqual(len({item['sku'] for item in items}),12)
            self.assertGreater(last,1)
        with self.assertRaises(p.mm.ScraperError):
            p.listing('<html>blocked</html>',CONFIG['gpu']['category_url'])

    def test_daily_rerun_makes_no_product_requests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = p.arguments(['collect','--categories','ram','--catalog',str(root/'catalog.json'),
                '--debug-dir',str(root/'debug'),'--output-dir',str(root/'raw')])
            catalog = p.load_catalog(args.catalog)
            p.register(catalog,dict(sku='2230728',url=url(RAM)), 'ram','test')
            client = Mock()
            client.get_html.return_value = (html(RAM),url(RAM))
            p.collect(catalog,client,args,CONFIG,report())
            self.assertEqual(client.get_html.call_count,1)
            args.command='daily'
            result=report()
            p.collect(catalog,client,args,CONFIG,result)
            self.assertEqual(client.get_html.call_count,1)
            self.assertEqual(result['skipped_today'],1)
            self.assertEqual(len(list((root/'raw').glob('*.json'))),1)
            self.assertEqual(p.load_catalog(args.catalog)['products']['mediamarkt:2230728']['status'],'accepted')

    def test_error_keeps_url_and_next_product_continues(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            args=p.arguments(['collect','--categories','ssd','--catalog',str(root/'c.json'), '--debug-dir',str(root/'debug'),'--output-dir',str(root/'raw')])
            catalog=p.load_catalog(args.catalog)
            p.register(catalog,dict(sku='145381326',url=url(CONFLICT)),'ssd','test')
            p.register(catalog,dict(sku='2155505',url=url(SSD)),'ssd','test')
            client=Mock()
            client.get_html.side_effect=[p.FetchError('HTTP 404',404),(html(SSD),url(SSD))]
            result=report()
            p.collect(catalog,client,args,CONFIG,result)
            self.assertEqual(len(result['errors']),1)
            self.assertEqual(result['errors'][0]['kind'],'http')
            self.assertIn('started_at',result['errors'][0])
            self.assertIn('finished_at',result['errors'][0])
            self.assertEqual(result['accepted'],1)
            self.assertEqual(catalog['products']['mediamarkt:145381326']['status'],'candidate')

    def test_lock_and_atomic_catalogue(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'c.json'
            with p.catalog_lock(path):
                with self.assertRaises(p.mm.ScraperError):
                    with p.catalog_lock(path):
                        pass
                p.atomic_json(path,p.load_catalog(path))
            self.assertFalse(path.with_name('c.json.lock').exists())
            self.assertEqual(p.load_catalog(path)['version'],1)

    def test_recovers_observation_written_before_catalogue_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = p.arguments(['collect','--categories','ram','--catalog',str(root/'c.json'),
                '--debug-dir',str(root/'debug'),'--output-dir',str(root/'raw')])
            catalog = p.load_catalog(args.catalog)
            p.register(catalog,dict(sku='2230728',url=url(RAM)),'ram','test')
            r = record(RAM)
            r['metadata']['access_method'] = 'public_html'
            path = args.output_dir / ('2230728_' + p.day(r['metadata']['collected_at']) + '.json')
            p.atomic_json(path,r)
            client = Mock()
            result = report()
            p.collect(catalog,client,args,CONFIG,result)
            client.get_html.assert_not_called()
            self.assertEqual(result['accepted'],1)
            self.assertEqual(len(list(args.output_dir.glob('*.json'))),1)

    def test_pagination_cursor_is_saved_and_repeats_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            args=p.arguments(['discover','--categories','gpu','--max-pages','1',
                '--catalog',str(root/'c.json'),'--debug-dir',str(root/'debug')])
            catalog=p.load_catalog(args.catalog)
            client=Mock()
            client.get_html.return_value=(html('grafikkarten-751073.html'),CONFIG['gpu']['category_url'])
            p.discover(catalog,client,args,CONFIG,report())
            self.assertEqual(catalog['discovery']['gpu']['next_page'],2)
            with self.assertRaises(p.mm.ScraperError):
                p.discover(catalog,client,args,CONFIG,report())
            self.assertEqual(catalog['discovery']['gpu']['next_page'],2)

    def test_url_identity_and_domain(self):
        self.assertEqual(p.canonical_url(url(RAM)+'?tracking=x#reviews',product=True),url(RAM))
        with self.assertRaises(ValueError):
            p.canonical_url('https://evil.example/de/product/_foo-123.html',product=True)


class HttpTests(unittest.TestCase):
    def test_disconnection_is_network_error_without_automatic_retry(self):
        c=p.Client()
        c.session.get=Mock(side_effect=p.mm.requests.ConnectionError('remote closed'))
        with self.assertRaises(p.FetchError) as caught:
            c.request(url(RAM))
        self.assertEqual(caught.exception.kind,'network')
        self.assertEqual(c.session.get.call_count,1)
        c.close()

    def test_blocked_requests_abort_without_retry(self):
        for status in (403,429,503):
            c=p.Client()
            c.session.get=Mock(return_value=Mock(status_code=status, headers={}))
            with self.assertRaises(p.StopRun):
                c.request(url(RAM))
            self.assertEqual(c.session.get.call_count,1)
            c.close()

    def test_redirect_checks_robots_at_each_hop(self):
        c=p.Client()
        c.check_robots=Mock()
        first=Mock(status_code=302,headers={'Location':url(RAM)+'?page=1'})
        second=Mock(status_code=200,headers={'Content-Type':'text/html'},text=html(RAM))
        c.request=Mock(side_effect=[first,second])
        c.get_html(url(RAM),product=True)
        self.assertEqual(c.check_robots.call_count,2)
        c.close()

    def test_budget_stops_before_request(self):
        c=p.Client(max_requests=1)
        c.requests=1
        c.session.get=Mock()
        with self.assertRaises(p.StopRun):
            c.request(url(RAM))
        c.session.get.assert_not_called()
        c.close()


if __name__=='__main__':
    unittest.main()
