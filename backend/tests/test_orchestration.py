import unittest
from unittest.mock import patch
from backend import flow as module


class OrchestrationTests(unittest.TestCase):
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
        with patch.object(module.mediamarkt_pipeline,'serve') as serve:
            module.main(['serve','--mode','live'])
            self.assertEqual(serve.call_args.kwargs['parameters']['mode'],'daily')
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

    def test_failed_live_collection_loads_existing_then_fails(self):
        with patch.object(module,'collect',return_value={'exit_code':1}), \
             patch.object(module,'transform',return_value=[]) as transform, \
             patch.object(module,'load',return_value={'error':0,'accepted':1,'verification':{'ok':True}}) as load:
            with self.assertRaises(RuntimeError):module.mediamarkt_pipeline.fn('live',input_dir='/tmp')
            transform.assert_called_once();load.assert_called_once()

    def test_zero_accepted_files_fails_even_when_db_has_data(self):
        with patch.object(module,'collect',return_value={'exit_code':0}), \
             patch.object(module,'transform',return_value=[]), \
             patch.object(module,'load',return_value={'error':0,'accepted':0,'verification':{'ok':True}}):
            with self.assertRaises(RuntimeError):module.mediamarkt_pipeline.fn('replay')
