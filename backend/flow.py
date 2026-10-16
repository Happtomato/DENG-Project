"""One entry point and one Prefect flow: DISCOVER / INITIAL / DAILY / REPLAY."""
import argparse
import json
import math
import os
from pathlib import Path

from prefect import flow, task
from prefect.client.schemas.schedules import CronSchedule

from backend.database import ROOT, connect, migrate, verification, active_products
from backend.retailers.mediamarkt import collector
from backend.transform import transform_directory
from backend.ingestion import ingest_directory

RAW = str(ROOT / 'data/raw/mediamarkt')
CATALOG = str(ROOT / 'data/catalog/mediamarkt.json')
SELECTION = str(ROOT / 'data/catalog/mediamarkt_initial.json')


@task(name='Collect', retries=0, persist_result=False)
def collect(mode, input_dir, catalog, max_products, max_requests, selection=SELECTION, delay=3.0,
            categories=('gpu', 'ram', 'ssd'), max_pages=1, from_catalog=False):
    if mode=='replay':
        return {'mode':'replay','exit_code':0, 'requests':0}
    products = None
    imported_skus = None
    if mode=='daily':
        with connect() as conn:
            products = active_products(conn)
    elif mode=='initial' and from_catalog:
        with connect() as conn:
            imported_skus = {str(row['retailer_sku']) for row in active_products(conn)}
    options = [mode,'--catalog',catalog,'--output-dir',input_dir,
               '--selection',selection,'--max-products',str(max_products),
               '--max-requests',str(max_requests),'--delay',str(delay),
               '--categories',*categories]
    if mode=='discover':
        options += ['--links-only','--max-pages',str(max_pages)]
    if from_catalog:
        options.append('--from-catalog')
    result = collector.main(options, products=products, imported_skus=imported_skus, return_report=True)
    # Keep small mocks and older direct callers compatible with the integer exit code.
    report = result if isinstance(result, dict) else {'exit_code':result}
    report['mode'] = mode
    report['database_products'] = len(products) if products is not None else None
    return report


@task(name='Transform', retries=0, persist_result=False)
def transform(input_dir):
    return transform_directory(input_dir)


@task(name='Load', retries=0, persist_result=False)
def load(input_dir, records):
    with connect() as conn:
        migrate(conn)
        before = {str(row['retailer_sku']) for row in active_products(conn)}
        report = ingest_directory(conn,input_dir,transformed=records)
        after = {str(row['retailer_sku']) for row in active_products(conn)}
        report['previous_offer_skus'] = sorted(before)
        report['new_offer_skus'] = sorted(after - before)
        report['verification'] = verification(conn)
    return report


@flow(name='DENG MediaMarkt Batch', log_prints=True, persist_result=False)
def mediamarkt_pipeline(mode='replay', input_dir=RAW, catalog=CATALOG, max_products=3,
                        max_requests=20, selection=SELECTION, delay=3.0,
                        categories=('gpu', 'ram', 'ssd'), max_pages=1, from_catalog=False):
    # Keep the previous deployment parameters usable while upgrading.
    mode = 'daily' if mode=='live' else mode
    if mode not in ('discover','initial','daily','replay'):
        raise ValueError('Mode must be discover, initial, daily or replay')
    if from_catalog and mode != 'initial':
        raise ValueError('Catalog selection is only valid for INITIAL')
    if not categories or set(categories) - {'gpu','ram','ssd'}:
        raise ValueError('Categories must be gpu, ram and/or ssd')
    if max_products<1 or max_requests<1 or max_pages<1:
        raise ValueError('Request/product limits must be positive')
    if not math.isfinite(delay) or delay < 3:
        raise ValueError('Delay must be at least three seconds')
    if mode in ('initial','daily'):
        Path(input_dir).mkdir(parents=True,exist_ok=True)
    collection = collect(mode,input_dir,catalog,max_products,max_requests,selection,delay,
                         categories,max_pages,from_catalog)
    if mode=='discover':
        result = {'collection':collection,
                  'outcome':{'new_urls':collection.get('new_urls',0),
                             'known_urls':collection.get('known_urls',0),
                             'duplicate_links':collection.get('duplicate_links',0),
                             'pages':collection.get('pages',0),
                             'http_requests':collection.get('requests',0),
                             'errors':collection.get('errors',[])}}
        print(json.dumps(result,indent=2,default=str))
        if collection['exit_code']:
            raise RuntimeError('Discovery incomplete; inspect the collection report above')
        return result
    records = transform(input_dir)
    report = load(input_dir,records)
    report['collection'] = collection
    selected = set(collection.get('selected_skus',[]))
    new_offers = set(report.get('new_offer_skus',[]))
    current_paths = set(collection.get('raw_paths',[]))
    current_loaded = sum(item['status']=='loaded' and item['path'] in current_paths
                         for item in report.get('results',[]))
    if mode=='initial':
        report['outcome'] = {'selected_candidates':collection.get('selected_products'),
                             'already_imported':collection.get('already_imported') if from_catalog else
                                                len(selected & set(report.get('previous_offer_skus',[]))),
                             'skipped_today':collection.get('skipped_today',0),
                             'skipped_scope':collection.get('skipped_scope',0),
                             'remaining_due':collection.get('remaining_due',0),
                             'http_requests':collection.get('requests',0),
                             'validated_products':collection.get('validated_products',0),
                             'new_offers_from_selection':len(new_offers & selected),
                             'new_offers_from_all_raw':len(new_offers),
                             'loaded_observations_from_selected_raw':current_loaded,
                             'rejected_raw_files':report.get('rejected',0),
                             'errors':collection.get('errors',[])}
    elif mode=='daily':
        report['outcome'] = {'selected_database_products':collection.get('selected_products'),
                             'skipped_today':collection.get('skipped_today',0),
                             'remaining_due':collection.get('remaining_due',0),
                             'http_requests':collection.get('requests',0),
                             'new_observations_from_selected_raw':current_loaded,
                             'missing_prices':collection.get('missing_price',0),
                             'errors':collection.get('errors',[])}
    else:
        report['outcome'] = {'raw_files':report.get('files',0), 'new_imports':report.get('loaded',0),
                             'duplicates':report.get('duplicate',0), 'rejected':report.get('rejected',0),
                             'errors':report['error']}
    print(json.dumps(report,indent=2,default=str))
    if collection['exit_code'] or report['error'] or not report['accepted'] or not report['verification']['ok']:
        raise RuntimeError('Pipeline incomplete; inspect collection, rejected files and SQL verification above')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',choices=['init','verify','catalog','discover','initial','daily','replay','serve'])
    parser.add_argument('--mode',choices=['discover','initial','daily','live','replay'],help='Compatibility with Phase-2 parameters')
    parser.add_argument('--input',default=RAW)
    parser.add_argument('--catalog',default=CATALOG)
    parser.add_argument('--selection',default=SELECTION)
    parser.add_argument('--from-catalog',action='store_true',help='INITIAL: use candidates not yet imported into PostgreSQL')
    parser.add_argument('--categories',nargs='+',choices=['gpu','ram','ssd'],default=['gpu','ram','ssd'])
    parser.add_argument('--max-pages',type=int,default=1,help='Listing pages per category for manual discovery')
    parser.add_argument('--max-products',type=int,default=int(os.getenv('PIPELINE_MAX_PRODUCTS','3')),help='Product attempts per category')
    parser.add_argument('--max-requests',type=int,default=int(os.getenv('PIPELINE_MAX_REQUESTS','20')))
    parser.add_argument('--delay',type=float,default=float(os.getenv('PIPELINE_DELAY_SECONDS','3')),help='Minimum seconds between HTTP requests')
    parser.add_argument('--serve',action='store_true',help='Compatibility alias for serve')
    parser.add_argument('--cron',default=os.getenv('PIPELINE_CRON','0 3 * * *'))
    args = parser.parse_args(argv)
    if args.command in ('init','verify','catalog'):
        with connect() as conn:
            if args.command=='init':
                migrate(conn);result={'schema':'ready'}
            elif args.command=='verify':
                result=verification(conn)
            else:
                products=active_products(conn)
                active=collector.in_scope_active_products(products)
                result={'database_products':products,'in_scope_products':active,
                        'legacy_out_of_scope_count':len(products)-len(active),
                        'catalogue_funnel':collector.catalog_summary(args.catalog)}
        print(json.dumps(result,indent=2,default=str))
        return 0 if result.get('ok',True) else 1
    serving = args.serve or args.command=='serve'
    if serving and args.command not in (None,'serve'):
        parser.error('Use serve without another command')
    if args.mode and args.command in ('discover','initial','daily','replay'):
        parser.error('Use the positional command OR --mode, not both')
    mode = args.mode or ('daily' if serving else args.command or 'replay')
    mode = 'daily' if mode == 'live' else mode
    if serving and mode != 'daily':
        parser.error('The scheduled deployment only supports DAILY')
    if args.from_catalog and mode != 'initial':
        parser.error('--from-catalog is only valid with INITIAL')
    parameters = dict(mode=mode,input_dir=args.input,catalog=args.catalog,
                      max_products=args.max_products,max_requests=args.max_requests,
                      selection=args.selection,delay=args.delay,categories=args.categories,
                      max_pages=args.max_pages,from_catalog=args.from_catalog)
    if serving:
        mediamarkt_pipeline.serve(name='mediamarkt-daily',parameters=parameters,
            schedule=CronSchedule(cron=args.cron,timezone='Europe/Zurich'),pause_on_shutdown=True,limit=1)
    else:
        mediamarkt_pipeline(**parameters)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
