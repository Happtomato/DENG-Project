"""Bounded collection and DB-backed membership, without live network requests."""
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from backend.retailers.mediamarkt import collector as c
from backend import flow
from backend.database import active_products
from backend.transform import transform_directory
from backend.ingestion import ingest_directory
import psycopg
from test_mediamarkt import html, url, RAM, SSD, CONFIG, report
import test_ingestion as ingestion_tests
from test_ingestion import fixture


class CatalogueModesTests(unittest.TestCase):
    def test_catalog_initial_uses_unimported_candidates_and_raw_waiting_for_load(self):
        cat={'version':1,'source':'mediamarkt','products':{},'discovery':{}}
        for sku,status in [('2230728','candidate'),('101374309','accepted'),('9999999','excluded')]:
            row=c.register(cat,{'sku':sku,'url':url('_candidate-'+sku+'.html')},'ram','test')
            row['status']=status
        selected, imported=c.select_catalog(cat,{'2230728'},['ram'])
        self.assertEqual(selected,{'101374309'})
        self.assertEqual(imported,1)

    def test_links_only_discovery_uses_listing_without_product_requests(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            category_url=CONFIG['gpu']['category_url']
            with patch.object(c.Client,'get_html',autospec=True,
                              side_effect=lambda client,address,**kw: (html('grafikkarten-751073.html'),address)
                              if address==category_url and not kw.get('product') else self.fail('Product request')) as get:
                result=c.main(['discover','--links-only','--categories','gpu','--max-pages','1',
                               '--catalog',str(root/'catalog.json'),'--debug-dir',str(root/'debug'),
                               '--output-dir',str(root/'raw')],return_report=True)
            self.assertEqual(result['exit_code'],0)
            self.assertEqual((result['pages'],result['new_urls'],result['known_urls']),(1,12,0))
            self.assertEqual(get.call_count,1)
            self.assertFalse((root/'raw').exists())
            self.assertEqual(len(c.load_catalog(root/'catalog.json')['products']),12)
            catalog_data=c.load_catalog(root/'catalog.json')
            catalog_data['discovery'].clear()  # Revisit the same saved page in this isolated fixture.
            c.atomic_json(root/'catalog.json',catalog_data)
            with patch.object(c.Client,'get_html',autospec=True,
                              side_effect=lambda client,address,**kw: (html('grafikkarten-751073.html'),address)
                              if address==category_url and not kw.get('product') else self.fail('Product request')):
                again=c.main(['discover','--links-only','--categories','gpu','--max-pages','1',
                              '--catalog',str(root/'catalog.json'),'--debug-dir',str(root/'debug'),
                              '--output-dir',str(root/'raw')],return_report=True)
            self.assertEqual((again['new_urls'],again['known_urls']),(0,12))

    def test_initial_limits_collection_to_selected_urls(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);selection=root/'selected.json'
            selection.write_text(json.dumps({'ram':[url(RAM)]}))
            cat={'version':1,'source':'mediamarkt','products':{},'discovery':{}}
            c.register(cat,{'sku':'9999999','url':url('_unselected-9999999.html')},'ram','test')
            selected=c.select_initial(cat,selection)
            args=c.arguments(['initial','--catalog',str(root/'catalog.json'),'--output-dir',str(root/'raw'),'--debug-dir',str(root/'debug')])
            args.selected_skus=selected;client=Mock();client.get_html.return_value=(html(RAM),url(RAM))
            c.collect(cat,client,args,CONFIG,report())
            client.get_html.assert_called_once_with(url(RAM),product=True)

    def test_daily_uses_db_membership_instead_of_candidate_queue(self):
        cat={'version':1,'source':'mediamarkt','products':{},'discovery':{}}
        c.register(cat,{'sku':'9999999','url':url('_unselected-9999999.html')},'ram','discovery')
        when=datetime(2026,10,15,tzinfo=timezone.utc)
        selected=c.select_daily(cat,[{'retailer_sku':'2230728','product_url':url(RAM),'category':'ram',
                                    'brand':'CORSAIR','title':'CORSAIR VENGEANCE DDR5',
                                    'first_seen_at':when,'last_success_at':when,'last_record':None}])
        self.assertEqual(selected,{'2230728'})
        self.assertEqual(cat['products']['mediamarkt:2230728']['status'],'accepted')
        self.assertEqual(cat['products']['mediamarkt:2230728']['last_success_at'],when.isoformat())
        with self.assertRaisesRegex(ValueError,'No imported'):c.select_daily(cat,[])

    def test_daily_next_day_fetches_same_product_then_skips_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            cat={'version':1,'source':'mediamarkt','products':{},'discovery':{}}
            c.register(cat,{'sku':'2230728','url':url(RAM)},'ram','selected')
            args=c.arguments(['initial','--categories','ram','--catalog',str(root/'c.json'),
                              '--output-dir',str(root/'raw'),'--debug-dir',str(root/'debug')])
            args.selected_skus={'2230728'}
            client=Mock();client.get_html.return_value=(html(RAM),url(RAM))
            day1=datetime(2026,10,15,8,tzinfo=timezone.utc)
            with patch.object(c.mm,'utc_now',return_value=day1):c.collect(cat,client,args,CONFIG,report())
            args.command='daily'
            c.select_daily(cat,[{'retailer_sku':'2230728','product_url':url(RAM),'category':'ram',
                'brand':'CORSAIR','title':'CORSAIR VENGEANCE DDR5',
                'first_seen_at':day1,'last_success_at':day1,'last_record':str(root/'raw/2230728_2026-10-15.json')}])
            day2=datetime(2026,10,16,8,tzinfo=timezone.utc)
            with patch.object(c.mm,'utc_now',return_value=day2):
                c.collect(cat,client,args,CONFIG,report())
                c.collect(cat,client,args,CONFIG,report())
            self.assertEqual(client.get_html.call_count,2)
            records=[json.loads(p.read_text()) for p in (root/'raw').glob('*.json')]
            self.assertEqual(len(records),2)
            self.assertEqual(len({r['metadata']['collected_at'] for r in records}),2)
            self.assertEqual(len({r['price_history']['price_chf'] for r in records}),1)

    def test_initial_rejects_duplicate_or_external_urls(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'selection.json'
            for urls in ([url(RAM),url(RAM)],['https://example.com/item.html']):
                path.write_text(json.dumps({'ram':urls}))
                with self.assertRaises(ValueError):c.select_initial({'products':{}},path)

    def test_daily_collect_requests_products_from_database(self):
        with patch.object(flow,'connect') as connection, patch.object(flow,'active_products',return_value=[{'retailer_sku':'TEST'}]) as products, patch.object(flow.collector,'main',return_value=0) as collect:
            result=flow.collect.fn('daily','raw','catalog',2,8)
            products.assert_called_once_with(connection.return_value.__enter__.return_value)
            self.assertEqual(collect.call_args.kwargs['products'],[{'retailer_sku':'TEST'}])
            self.assertEqual(result['database_products'],1)

    def test_daily_excludes_legacy_out_of_scope_without_deleting_it(self):
        rows=[{'category':'gpu','brand':'ASUS','title':'ASUS PRIME GeForce RTX 5070'},
              {'category':'gpu','brand':'ASUS','title':'ASUS ROG Strix GeForce RTX 5070'},
              {'category':'ram','brand':'ADATA','title':'ADATA DDR5'},
              {'category':'ssd','brand':'SAMSUNG','title':'SAMSUNG 990 PRO'}]
        self.assertEqual(c.in_scope_active_products(rows),[rows[1],rows[3]])

    def test_initial_does_not_require_database_for_acquisition(self):
        with patch.object(flow,'connect') as conn,patch.object(flow.collector,'main',return_value=0) as collect:
            flow.collect.fn('initial','raw','catalog',2,8)
            conn.assert_not_called();self.assertEqual(collect.call_args.args[0][0],'initial')

    def test_catalog_initial_gets_imported_skus_from_database(self):
        with patch.object(flow,'connect') as connection, \
             patch.object(flow,'active_products',return_value=[{'retailer_sku':'2230728'}]), \
             patch.object(flow.collector,'main',return_value={'exit_code':0}) as collector:
            result=flow.collect.fn('initial','raw','catalog',2,8,from_catalog=True)
        self.assertEqual(result['exit_code'],0)
        self.assertEqual(collector.call_args.kwargs['imported_skus'],{'2230728'})
        self.assertIn('--from-catalog',collector.call_args.args[0])
        connection.assert_called_once()


class DatabaseCatalogueTest(unittest.TestCase):
    setUp=ingestion_tests.DatabaseTests.setUp
    tearDown=ingestion_tests.DatabaseTests.tearDown
    put=ingestion_tests.DatabaseTests.put

    def test_database_list_tracks_imported_offers_and_latest_observation(self):
        first=fixture();self.put(first)
        rows=active_products(self.conn)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['retailer_sku'],'2230728')
        self.assertEqual(rows[0]['last_success_at'],first['observation']['observed'])
        self.assertEqual(rows[0]['last_record'],first['path'])
        self.assertEqual(rows[0]['brand'],'CORSAIR')

    def test_raw_is_loaded_after_first_database_import_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            raw=root/'raw';raw.mkdir()
            original=next((c.ROOT/'data/raw/mediamarkt').glob('2230728_2026-10-16.json'))
            saved=raw/original.name
            shutil.copyfile(original,saved)
            record=json.loads(saved.read_text())
            observed=datetime.fromisoformat(record['metadata']['collected_at'])
            cat=c.load_catalog(root/'catalog.json')
            row=c.register(cat,{'sku':'2230728','url':url(RAM)},'ram','test')
            row.update(status='accepted',last_success_at=observed.isoformat(),last_record=str(saved))
            c.atomic_json(root/'catalog.json',cat)
            with patch('backend.ingestion.load_observation',side_effect=psycopg.OperationalError('simulated')):
                failed=ingest_directory(self.conn,raw)
            self.assertEqual(failed['error'],1)
            self.assertEqual(active_products(self.conn),[])
            with patch.object(c.mm,'utc_now',return_value=observed), \
                 patch.object(c.Client,'get_html',side_effect=AssertionError('Unexpected HTTP')):
                collection=c.main(['initial','--from-catalog','--categories','ram',
                                   '--catalog',str(root/'catalog.json'),'--output-dir',str(raw),
                                   '--debug-dir',str(root/'debug')],
                                  imported_skus=set(),return_report=True)
            self.assertEqual(collection['exit_code'],0)
            self.assertEqual(collection['selected_products'],1)
            self.assertEqual(collection['skipped_today'],1)
            self.assertEqual(collection['raw_paths'],[str(saved)])
            recovered=ingest_directory(self.conn,raw,transformed=transform_directory(raw))
            self.assertEqual(recovered['loaded'],1)
            self.assertEqual(len(active_products(self.conn)),1)
