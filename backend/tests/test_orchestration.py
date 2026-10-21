import unittest
import inspect
from unittest.mock import patch
from backend import flow as module


class OrchestrationTests(unittest.TestCase):
    def test_parameterless_prefect_run_defaults_to_daily(self):
        self.assertEqual(inspect.signature(module.mediamarkt_pipeline.fn).parameters['mode'].default,'daily')

    def test_manual_commands_route_to_the_same_flow(self):
        with patch.object(module,'mediamarkt_pipeline') as pipeline:
            self.assertEqual(module.main(['discover','--categories','gpu','--max-pages','1',
                                          '--max-requests','3']),0)
            self.assertEqual(pipeline.call_args.kwargs['mode'],'discover')
            self.assertEqual(pipeline.call_args.kwargs['categories'],['gpu'])
            self.assertEqual(pipeline.call_args.kwargs['max_pages'],1)
            self.assertFalse(pipeline.call_args.kwargs['from_catalog'])
            self.assertEqual(module.main(['initial','--from-catalog']),0)
            self.assertEqual(pipeline.call_args.kwargs['mode'],'initial')
            self.assertTrue(pipeline.call_args.kwargs['from_catalog'])

    def test_discovery_uses_existing_collector_links_only(self):
        with patch.object(module.collector,'main',return_value={'exit_code':0,'new_urls':2}) as collector:
            result=module.collect.fn('discover','raw','catalog',3,8,categories=('gpu',),max_pages=1)
        options=collector.call_args.args[0]
        self.assertIn('--links-only',options)
        self.assertEqual(options[options.index('--max-pages')+1],'1')
        self.assertEqual(options[options.index('--categories')+1],'gpu')
        self.assertEqual(result['new_urls'],2)

    def test_discovery_flow_never_transforms_or_loads(self):
        collection={'exit_code':0,'new_urls':2,'known_urls':3,'pages':1,'requests':2,'errors':[]}
        with patch.object(module,'collect',return_value=collection), \
             patch.object(module,'transform') as transform, patch.object(module,'load') as load, \
             patch.object(module,'connect') as connect:
            result=module.mediamarkt_pipeline.fn('discover')
        self.assertEqual(result['outcome']['new_urls'],2)
        transform.assert_not_called();load.assert_not_called();connect.assert_not_called()

    def test_serve_rejects_discovery_and_initial(self):
        for mode in ('discover','initial','replay'):
            with self.subTest(mode=mode), patch.object(module.mediamarkt_pipeline,'serve') as serve:
                with self.assertRaises(SystemExit) as error:
                    module.main(['serve','--mode',mode])
                self.assertEqual(error.exception.code,2)
                serve.assert_not_called()
        with patch.dict('os.environ',{'PIPELINE_SCHEDULE_ENABLED':'false'}), \
             patch.object(module.mediamarkt_pipeline,'serve') as serve:
            module.main(['serve','--mode','live'])
            self.assertEqual(serve.call_args.kwargs['parameters']['mode'],'daily')
            self.assertTrue(serve.call_args.kwargs['paused'])
        with patch.dict('os.environ',{'PIPELINE_SCHEDULE_ENABLED':'true'}), \
             patch.object(module.mediamarkt_pipeline,'serve') as serve:
            module.main(['serve'])
            self.assertFalse(serve.call_args.kwargs['paused'])
        with patch.object(module.mediamarkt_pipeline,'serve') as serve:
            with self.assertRaises(SystemExit):
                module.main(['discover','--serve'])
            serve.assert_not_called()

    def test_no_new_live_products_are_reported_as_zero(self):
        collection={'exit_code':0,'selected_products':1,'selected_skus':['123'],
                    'requests':0,'validated_products':0,'errors':[]}
        loaded={'error':0,'accepted':1,'loaded':0,'duplicate':1,'rejected':0,
                'previous_offer_skus':['123'],'new_offer_skus':[],'results':[], 'verification':{'ok':True}}
        with patch.object(module,'collect',return_value=collection), \
             patch.object(module,'transform',return_value=[]), \
             patch.object(module,'load',return_value=loaded):
            result=module.mediamarkt_pipeline.fn('initial')
        self.assertEqual(result['outcome']['new_offers_from_selection'],0)
        self.assertEqual(result['outcome']['already_imported'],1)
        self.assertEqual(result['outcome']['http_requests'],0)
        self.assertEqual(result['outcome']['validated_products'],0)

    def test_replay_does_not_call_collector(self):
        with patch.object(module,'collector') as collector:
            self.assertEqual(module.collect.fn('replay','unused','unused',1,2)['exit_code'],0)
            collector.main.assert_not_called()

    def test_daily_imports_authorised_digitec_files_but_replay_does_not(self):
        collection={'exit_code':0,'selected_products':0,'selected_skus':[],
                    'raw_paths':[],'requests':0,'errors':[]}
        loaded={'error':0,'accepted':1,'loaded':0,'duplicate':1,'rejected':0,
                'results':[],'verification':{'ok':True}}
        with patch.object(module,'collect',return_value=collection), \
             patch.object(module,'transform',return_value=[]), \
             patch.object(module,'load',return_value=loaded), \
             patch.object(module,'import_digitec_files',return_value={'loaded':1,'rejected':0,'error':0}) as digitec, \
             patch.object(module,'connect') as connect, \
             patch.object(module,'verification',return_value={'ok':True}), \
             patch.object(module,'print'):
            result=module.mediamarkt_pipeline.fn('daily')
            self.assertEqual(result['outcome']['digitec_import']['loaded'],1)
            digitec.assert_called_once()
            connect.assert_called_once()
            digitec.reset_mock()
            module.mediamarkt_pipeline.fn('replay')
            digitec.assert_not_called()

    def test_manual_daily_sku_filters_database_products_before_collection(self):
        products=[{'retailer_sku':'2199070'},{'retailer_sku':'2155505'}]
        with patch.object(module,'connect') as connect, \
             patch.object(module,'active_products',return_value=products), \
             patch.object(module.collector,'main',return_value={'exit_code':0}) as collector:
            result=module.collect.fn('daily','raw','catalog',1,3,
                                     categories=('ssd',),product_sku='2199070')
        self.assertEqual(result['database_products'],1)
        self.assertEqual(collector.call_args.kwargs['products'],[products[0]])
        connect.assert_called_once()

    def test_manual_sku_cannot_be_used_for_scheduled_or_replay_runs(self):
        for command in (['serve','--sku','2199070'],['replay','--sku','2199070']):
            with self.subTest(command=command), patch.object(module.mediamarkt_pipeline,'serve') as serve:
                with self.assertRaises(SystemExit):
                    module.main(command)
                serve.assert_not_called()

    def test_failed_live_collection_loads_existing_then_fails(self):
        with patch.object(module,'collect',return_value={'exit_code':1}), \
             patch.object(module,'transform',return_value=[]) as transform, \
             patch.object(module,'load',return_value={'error':0,'accepted':1,'verification':{'ok':True}}) as load:
            with self.assertRaises(RuntimeError):module.mediamarkt_pipeline.fn('live',input_dir='/tmp')
            transform.assert_called_once();load.assert_called_once()

    def test_partial_daily_reports_fresh_imports_before_failed_state(self):
        collection={'exit_code':1,'selected_products':2,'selected_skus':['1','2'],
                    'raw_paths':['new.json'],'requests':3,'remaining_due':0,
                    'errors':[{'sku':'2','kind':'network','error':'disconnected'}]}
        loaded={'error':0,'accepted':4,'loaded':1,'duplicate':3,'rejected':0,
                'results':[{'path':'new.json','status':'loaded'}],
                'verification':{'ok':True}}
        with patch.object(module,'collect',return_value=collection), \
             patch.object(module,'transform',return_value=[]), \
             patch.object(module,'load',return_value=loaded), \
             patch.object(module,'print') as output:
            with self.assertRaisesRegex(RuntimeError,'DAILY partial: 1 new observations'):
                module.mediamarkt_pipeline.fn('daily')
        report=next(call.args[0] for call in output.call_args_list if '"run_result"' in call.args[0])
        self.assertIn('"run_result": "partial"',report)
        self.assertIn('"failed_product_attempts": 1',report)

    def test_zero_accepted_files_fails_even_when_db_has_data(self):
        with patch.object(module,'collect',return_value={'exit_code':0}), \
             patch.object(module,'transform',return_value=[]), \
             patch.object(module,'load',return_value={'error':0,'accepted':0,'verification':{'ok':True}}):
            with self.assertRaises(RuntimeError):module.mediamarkt_pipeline.fn('replay')
