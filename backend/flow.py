"""One entry point and one Prefect flow: DISCOVER / INITIAL / DAILY / REPLAY."""
import argparse
import json
import math
import os
from pathlib import Path

from prefect import flow, task
from prefect.schedules import Cron

from backend.database import ROOT, connect, migrate, verification, active_products
from backend.retailers.mediamarkt import collector
from backend.retailers.digitec import importer as digitec
from backend.transform import transform_directory
from backend.ingestion import ingest_directory
from backend.seed import export_tables, import_tables

RAW = str(ROOT / 'data/raw/mediamarkt')
CATALOG = str(ROOT / 'data/catalog/mediamarkt.json')
SELECTION = str(ROOT / 'data/catalog/mediamarkt_initial.json')


@task(name='Collect', retries=0, persist_result=False)
def collect(mode, input_dir, catalog, max_products, max_requests, selection=SELECTION, delay=3.0,
            categories=('gpu', 'ram', 'ssd'), max_pages=1, from_catalog=False, product_sku=None):
    if mode=='replay':
        return {'mode':'replay','exit_code':0, 'requests':0}
    products = None
    imported_skus = None
    if mode=='daily':
        with connect() as conn:
            products = active_products(conn)
        if product_sku is not None:
            products = [row for row in products if str(row['retailer_sku']) == product_sku]
            if not products:
                raise ValueError(f'MediaMarkt SKU {product_sku} is not an active imported product')
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


@task(name='Import authorised Digitec files', retries=0, persist_result=False)
def import_digitec_files():
    # The inbox is empty until the team receives an authorised export. No HTTP.
    return digitec.run(apply=True)


@flow(name='DENG MediaMarkt Batch', log_prints=True, persist_result=False)
def mediamarkt_pipeline(mode='daily', input_dir=RAW, catalog=CATALOG, max_products=3,
                        max_requests=20, selection=SELECTION, delay=3.0,
                        categories=('gpu', 'ram', 'ssd'), max_pages=1, from_catalog=False,
                        product_sku: str | None = None):
    # Keep the previous deployment parameters usable while upgrading.
    mode = 'daily' if mode=='live' else mode
    if mode not in ('discover','initial','daily','replay'):
        raise ValueError('Mode must be discover, initial, daily or replay')
    if from_catalog and mode != 'initial':
        raise ValueError('Catalog selection is only valid for INITIAL')
    if product_sku is not None and mode != 'daily':
        raise ValueError('Product SKU selection is only valid for DAILY')
    if not categories or set(categories) - {'gpu','ram','ssd'}:
        raise ValueError('Categories must be gpu, ram and/or ssd')
    if max_products<1 or max_requests<1 or max_pages<1:
        raise ValueError('Request/product limits must be positive')
    if not math.isfinite(delay) or delay < 3:
        raise ValueError('Delay must be at least three seconds')
    if mode in ('initial','daily'):
        Path(input_dir).mkdir(parents=True,exist_ok=True)
    collection = collect(mode,input_dir,catalog,max_products,max_requests,selection,delay,
                         categories,max_pages,from_catalog,product_sku)
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

    digitec_report = import_digitec_files() if mode == 'daily' else None

    if digitec_report and digitec_report.get('loaded'):
        with connect() as conn:
            report['verification'] = verification(conn)
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
                             'errors':collection.get('errors',[]),
                             'digitec_import':digitec_report}
    else:
        report['outcome'] = {'raw_files':report.get('files',0), 'new_imports':report.get('loaded',0),
                             'duplicates':report.get('duplicate',0), 'rejected':report.get('rejected',0),
                             'errors':report['error']}
    incomplete = bool(collection['exit_code'] or report['error'] or not report['accepted']
                      or (digitec_report and (digitec_report.get('rejected') or digitec_report.get('error')))
                      or not report['verification']['ok'])
    fresh_loaded = (current_loaded + (digitec_report.get('loaded', 0) if digitec_report else 0)
                    if mode in ('initial', 'daily') else report.get('loaded', 0))
    run_result = 'partial' if incomplete and fresh_loaded else 'failed' if incomplete else 'completed'
    report['outcome']['run_result'] = run_result
    failed_attempts = len(collection.get('errors', [])) + bool(collection.get('stopped_sku'))
    report['outcome']['failed_product_attempts'] = failed_attempts
    print(f"{mode.upper()} result={run_result}: {fresh_loaded} new observations from this run, "
          f"{failed_attempts} product errors, "
          f"{collection.get('remaining_due', 0)} deferred by product limits")
    print(json.dumps(report,indent=2,default=str))
    if incomplete:
        raise RuntimeError(f'{mode.upper()} {run_result}: {fresh_loaded} new observations, '
                           f"{failed_attempts} product errors; inspect the collection report")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',nargs='?',choices=['init','verify','catalog','discover','initial','daily','replay','serve','digitec-import','seed-export','seed-import'])
    parser.add_argument('--mode',choices=['discover','initial','daily','live','replay'],help='Compatibility with Phase-2 parameters')
    parser.add_argument('--input',default=RAW)
    parser.add_argument('--digitec-input',default=str(digitec.INBOX),help='Directory of authorised Digitec JSON files')
    parser.add_argument('--seed-dir',default=str(ROOT / 'data/seed/midterm-2026-10-20'),
                        help='Offline Parquet snapshot directory')
    parser.add_argument('--digitec-html',help='DIGITEC-IMPORT: locally saved manual product HTML')
    parser.add_argument('--digitec-chart',help='DIGITEC-IMPORT: locally saved price-chart JSON')
    parser.add_argument('--digitec-chart-manifest',help='DIGITEC-IMPORT: manually mapped chart-only JSON files')
    parser.add_argument('--captured-at',help='DIGITEC-IMPORT: actual manual capture time with timezone')
    parser.add_argument('--digitec-category',choices=['gpu','ram','ssd'],
                        help='DIGITEC-IMPORT: category checked against the matching MediaMarkt product')
    parser.add_argument('--apply',action='store_true',help='DIGITEC-IMPORT only: archive and load matched offers')
    parser.add_argument('--catalog',default=CATALOG)
    parser.add_argument('--selection',default=SELECTION)
    parser.add_argument('--from-catalog',action='store_true',help='INITIAL: use candidates not yet imported into PostgreSQL')
    parser.add_argument('--sku',help='Manual DAILY: only this already imported MediaMarkt SKU')
    parser.add_argument('--categories',nargs='+',choices=['gpu','ram','ssd'],default=['gpu','ram','ssd'])
    parser.add_argument('--max-pages',type=int,default=1,help='Listing pages per category for manual discovery')
    parser.add_argument('--max-products',type=int,default=int(os.getenv('PIPELINE_MAX_PRODUCTS','3')),help='Product attempts per category')
    parser.add_argument('--max-requests',type=int,default=int(os.getenv('PIPELINE_MAX_REQUESTS','20')))
    parser.add_argument('--delay',type=float,default=float(os.getenv('PIPELINE_DELAY_SECONDS','3')),help='Minimum seconds between HTTP requests')
    parser.add_argument('--serve',action='store_true',help='Compatibility alias for serve')
    parser.add_argument('--cron',default=os.getenv('PIPELINE_CRON','0 3 * * *'))
    args = parser.parse_args(argv)
    if args.command in ('seed-export','seed-import'):
        with connect() as conn:
            migrate(conn)
            result = (export_tables(conn,args.seed_dir) if args.command == 'seed-export'
                      else import_tables(conn,args.seed_dir))
            if args.command == 'seed-import':
                result = {'tables':result,'verification':verification(conn)}
        print(json.dumps(result,indent=2,default=str))
        return 0
    if args.command == 'digitec-import':
        manual = (args.digitec_html, args.digitec_chart, args.captured_at, args.digitec_category)
        if args.digitec_chart_manifest and any(manual):
            parser.error('Choose either a full manual snapshot or a chart-only manifest')
        if any(manual) and not all(manual):
            parser.error('Manual Digitec import requires --digitec-html, --digitec-chart, --captured-at and --digitec-category together')
        if args.digitec_chart_manifest:
            report = digitec.import_chart_manifest(args.digitec_chart_manifest,apply=args.apply)
        elif all(manual):
            report = digitec.import_manual_snapshot(*manual,apply=args.apply,input_dir=args.digitec_input)
        else:
            report = digitec.run(args.digitec_input, apply=args.apply)
        print(json.dumps(report,indent=2,default=str))
        return 1 if report.get('rejected') or report.get('error') or report.get('status') == 'rejected' else 0
    if args.apply:
        parser.error('--apply is only valid with digitec-import')
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
    if args.sku and (mode != 'daily' or serving):
        parser.error('--sku is only valid with a manual DAILY run')
    parameters = dict(mode=mode,input_dir=args.input,catalog=args.catalog,
                      max_products=args.max_products,max_requests=args.max_requests,
                      selection=args.selection,delay=args.delay,categories=args.categories,
                      max_pages=args.max_pages,from_catalog=args.from_catalog,product_sku=args.sku)
    if serving:
        # Registration must not silently resume retailer requests after a Docker restart.
        schedule_enabled = os.getenv('PIPELINE_SCHEDULE_ENABLED','false').lower() == 'true'
        mediamarkt_pipeline.serve(name='mediamarkt-daily',parameters=parameters,
            schedule=Cron(args.cron,timezone='Europe/Zurich',active=schedule_enabled),
            paused=not schedule_enabled,pause_on_shutdown=True,limit=1)
    else:
        mediamarkt_pipeline(**parameters)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
