"""Offline import of documented Digitec offers for existing MediaMarkt products.

No HTTP client is used. Each JSON file is one source observation; its bytes are
archived unchanged before an explicit --apply writes to PostgreSQL.
"""
import argparse
import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
from bs4 import BeautifulSoup

from backend.database import ROOT, connect, migrate
from backend.ingestion import entity
from backend.transform import InvalidRecord, gtin, money, mpn_key, timestamp, text

INBOX = ROOT / 'data/import/digitec'
RAW = ROOT / 'data/raw/digitec'
SELECTION = ROOT / 'data/catalog/mediamarkt_initial.json'
CHART_MANIFEST = ROOT / 'data/catalog/digitec_manual_charts.json'


def validated(record):
    if not isinstance(record, dict):
        raise InvalidRecord('Digitec observation must be a JSON object')
    method = record.get('access_method')
    if record.get('source') != 'digitec' or method not in {'authorized_export', 'manual_capture'}:
        raise InvalidRecord('Digitec source must be a documented export or manual capture')
    if method == 'authorized_export' and not text(record.get('permission_reference')):
        raise InvalidRecord('A real permission_reference is required for an export')
    if method == 'manual_capture' and not text(record.get('source_reference')):
        raise InvalidRecord('Manual captures require a source_reference to the original files')
    sku = text(record.get('sku'))
    if not sku or not re.fullmatch(r'[0-9]+', sku):
        raise InvalidRecord('Digitec SKU must be a numeric string')
    url = urlsplit(text(record.get('product_url')) or '')
    if (url.scheme != 'https' or url.hostname not in {'www.digitec.ch', 'digitec.ch'}
            or url.username or url.password or url.port or not url.path.endswith('-' + sku)):
        raise InvalidRecord('Product URL must be an HTTPS Digitec product URL ending in the SKU')
    if record.get('currency') != 'CHF':
        raise InvalidRecord('Only explicit CHF prices are accepted')
    category = text(record.get('category'))
    if category not in {'gpu', 'ram', 'ssd'}:
        raise InvalidRecord('Category must be gpu, ram or ssd')
    brand, name, seller = (text(record.get(key)) for key in ('brand', 'product_name', 'seller_name'))
    if not all((brand, name, seller)):
        raise InvalidRecord('Brand, product_name and actual seller_name are required')
    return {
        'access_method': method,
        'sku': sku, 'url': urlunsplit((url.scheme, url.netloc, url.path, '', '')),
        'ean': gtin(record.get('ean')), 'mpn': mpn_key(record.get('mpn')),
        'category': category, 'brand': brand, 'name': name, 'seller': seller,
        'price': money(record.get('price_chf')),
        'observed': timestamp(record.get('observed_at')),
        'availability': text(record.get('availability')),
    }


def match_media_product(conn, row):
    if not row['ean']:
        raise InvalidRecord('Exact EAN is required for a cross-retailer match')
    matches = conn.execute('''SELECT p.product_id,p.mpn,b.name AS brand,lower(c.name) AS category
        FROM product p JOIN brand b USING(brand_id) JOIN category c USING(category_id)
        WHERE lpad(p.ean,14,'0')=%s AND EXISTS (
          SELECT 1 FROM retailer_product rp JOIN retailer r USING(retailer_id)
          WHERE rp.product_id=p.product_id AND lower(r.name)='mediamarkt')''', (row['ean'],)).fetchall()
    if len(matches) != 1:
        raise InvalidRecord('EAN has no unique existing MediaMarkt product')
    product = matches[0]
    source_brand = {'wd':'western digital'}.get(row['brand'].casefold(),row['brand'].casefold())
    if product['category'] != row['category'] or product['brand'].casefold() != source_brand:
        raise InvalidRecord('EAN match conflicts with brand or category')
    if row['mpn'] and product['mpn'] and row['mpn'] != mpn_key(product['mpn']):
        raise InvalidRecord('EAN match conflicts with manufacturer part number')
    return product['product_id']


def selected_for_manual_poc(conn, product_id, selection=SELECTION):
    chosen = json.loads(Path(selection).read_text(encoding='utf-8'))
    skus = {match.group(1) for urls in chosen.values() for url in urls
            if (match := re.search(r'-(\d+)\.html(?:\?.*)?$', url))}
    found = conn.execute('''SELECT 1 FROM retailer_product rp JOIN retailer r USING(retailer_id)
        WHERE rp.product_id=%s AND r.name='MediaMarkt' AND rp.retailer_sku=ANY(%s)''',
        (product_id,list(skus))).fetchone()
    if not found:
        raise InvalidRecord('Manual Digitec POC is limited to mediamarkt_initial.json products')


def existing_offer(conn, row, product_id):
    offer = conn.execute('''SELECT rp.retailer_product_id,rp.product_id FROM retailer_product rp
        JOIN retailer r USING(retailer_id)
        WHERE r.name='Digitec' AND rp.retailer_sku=%s''', (row['sku'],)).fetchone()
    if offer and offer['product_id'] != product_id:
        raise InvalidRecord('Digitec SKU is already linked to a different product')
    return offer


def existing_observation(conn, row, offer_id):
    if offer_id is None:
        return None
    previous = conn.execute('''SELECT price_chf,seller_name,availability FROM price_history
        WHERE retailer_product_id=%s AND collected_at=%s''', (offer_id,row['observed'])).fetchone()
    if previous and (previous['price_chf'] != row['price'] or previous['seller_name'] != row['seller']
                     or previous['availability'] != row['availability']):
        raise InvalidRecord('Same Digitec observation timestamp has conflicting values')
    return previous


def write_observation(conn, row, sha):
    product_id = match_media_product(conn, row)
    if row['access_method'] == 'manual_capture':
        selected_for_manual_poc(conn,product_id)
    old = existing_offer(conn, row, product_id)
    if existing_observation(conn, row, old['retailer_product_id'] if old else None):
        return 'duplicate'
    retailer_id = entity(conn, 'retailer', 'Digitec', website='https://www.digitec.ch')
    offer_id = conn.execute('''INSERT INTO retailer_product
        (product_id,retailer_id,retailer_sku,retailer_product_name,product_url,first_seen_at,last_seen_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(retailer_id,retailer_sku) DO UPDATE SET
          retailer_product_name=EXCLUDED.retailer_product_name,product_url=EXCLUDED.product_url,
          first_seen_at=LEAST(retailer_product.first_seen_at,EXCLUDED.first_seen_at),
          last_seen_at=GREATEST(retailer_product.last_seen_at,EXCLUDED.last_seen_at)
        RETURNING retailer_product_id''',
        (product_id,retailer_id,row['sku'],row['name'],row['url'],row['observed'],row['observed'])).fetchone()['retailer_product_id']
    conn.execute('''INSERT INTO price_history
        (retailer_product_id,price_chf,availability,collected_at,raw_sha256,source_url,seller_name)
        VALUES (%s,%s,%s,%s,%s,%s,%s)''',
        (offer_id,row['price'],row['availability'],row['observed'],sha,row['url'],row['seller']))
    return 'loaded'


def archive(path, content, sha, raw_dir, suffix='.json'):
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / (sha + suffix)
    try:
        with destination.open('xb') as handle:
            handle.write(content)
    except FileExistsError:
        if destination.read_bytes() != content:
            raise ValueError('Raw archive hash collision; refusing to overwrite')
    return destination


def inclusive_price(value):
    if not isinstance(value, dict) or value.get('currency') != 'CHF':
        raise InvalidRecord('Digitec price needs explicit CHF currency')
    amount = value.get('amountInclusive')
    if isinstance(amount, dict):
        amount = amount.get('source') or amount.get('parsedValue')
    return money(amount)


def manual_snapshot(html_content, chart_content, captured_at, category):
    """Convert two manually supplied files into one current retail observation.

    The chart points have source validFrom times, not collection times. No
    request is sent to its GraphQL endpoint.
    """
    observed = timestamp(captured_at)
    page = BeautifulSoup(html_content, 'html.parser')
    products = []
    for script in page.select('script[type="application/ld+json"]'):
        try:
            item = json.loads(script.string or script.get_text())
        except (TypeError, ValueError) as error:
            raise InvalidRecord('Invalid Digitec JSON-LD') from error
        if isinstance(item, dict) and item.get('@type') == 'Product':
            products.append(item)
    if len(products) != 1:
        raise InvalidRecord('Exactly one Digitec JSON-LD Product is required')
    product = products[0]
    canonical = page.select_one('link[rel="canonical"]')
    url = canonical.get('href') if canonical else None
    sku = text(product.get('sku'))
    if not sku or not url or not urlsplit(url).path.endswith('-' + sku):
        raise InvalidRecord('Canonical URL and JSON-LD SKU disagree')
    meta_gtin = page.select_one('meta[property="gtin"]')
    ean = product.get('gtin')
    if not meta_gtin or meta_gtin.get('content') != ean:
        raise InvalidRecord('HTML GTIN and JSON-LD GTIN disagree')
    html_price = page.select_one('meta[property="product:price:amount"]')
    html_currency = page.select_one('meta[property="product:price:currency"]')
    if not html_price or not html_currency or html_currency.get('content') != 'CHF':
        raise InvalidRecord('HTML needs a current CHF product price')
    price = money(html_price.get('content'))
    offers = product.get('offers') or {}
    if money(offers.get('price')) != price or offers.get('priceCurrency') != 'CHF':
        raise InvalidRecord('HTML current price and JSON-LD offer disagree')
    next_script = page.select_one('script#__NEXT_DATA__')
    if not next_script:
        raise InvalidRecord('Digitec retail offer metadata is missing')
    try:
        next_product = json.loads(next_script.string or next_script.get_text())['props']['pageProps']['preloadedQuery']['rawResponse']['data']['product']
        chart = json.loads(chart_content)['data']['productById']
    except (TypeError, KeyError, ValueError) as error:
        raise InvalidRecord('Invalid Digitec page or price-chart JSON') from error
    if next_product.get('offer', {}).get('shopOfferType') != 'RETAIL':
        raise InvalidRecord('Main product offer is not Digitec retail')
    if chart.get('id') != next_product.get('id'):
        raise InvalidRecord('Page and price chart product IDs disagree')
    if inclusive_price(next_product.get('defaultCustomerPrice')) != price or inclusive_price(chart.get('price')) != price:
        raise InvalidRecord('Page and price-chart current prices disagree')
    try:
        chart_id = base64.b64decode(chart['id']).decode('utf-8')
    except (KeyError, ValueError, UnicodeError) as error:
        raise InvalidRecord('Price chart has no readable product identity') from error
    if not chart_id.startswith('Product\nd' + sku + ':'):
        raise InvalidRecord('Price chart belongs to a different Digitec product')
    points = chart_points(chart, observed)
    record = {
        'source': 'digitec', 'access_method': 'manual_capture',
        'source_reference': 'sha256:' + hashlib.sha256(html_content).hexdigest() +
                            ',sha256:' + hashlib.sha256(chart_content).hexdigest(),
        'sku': sku, 'product_url': url, 'ean': ean,
        'brand': (product.get('brand') or {}).get('name'),
        'category': category, 'product_name': product.get('name'),
        'seller_name': 'Digitec', 'currency': 'CHF', 'price_chf': str(price),
        'observed_at': observed.isoformat(), 'availability': offers.get('availability'),
    }
    validated(record)
    return record, points, {'historical_change_points_in_source': len(points),
                    'history_older_than_three_months': bool(chart.get('priceHistory', {}).get('hasHistoryOlderThan3Months')),
                    'marketplace_offer_excluded': chart.get('offers', {}).get('newOffers', {}).get('cheapestOffer') is not None}


def chart_points(chart, observed):
    points = chart.get('priceHistory', {}).get('points')
    if not isinstance(points, list):
        raise InvalidRecord('Price chart points are missing')
    unique = {}
    for point in points:
        if not isinstance(point, dict):
            raise InvalidRecord('Invalid historical Digitec price point')
        valid_from = timestamp(point.get('validFrom'))
        if valid_from > observed:
            raise InvalidRecord('Historical price point is after manual capture')
        price = inclusive_price(point['price']) if point.get('price') is not None else None
        if valid_from in unique and unique[valid_from] != price:
            raise InvalidRecord('Conflicting chart prices at the same validFrom')
        unique[valid_from] = price
    return sorted(unique.items())


def load_chart_points(conn, offer_id, points, sha, chart_path):
    loaded = duplicate = 0
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(91342003)')
        conn.execute('''INSERT INTO raw_import(sha256,path,status)
            VALUES (%s,%s,'loaded') ON CONFLICT(sha256) DO NOTHING''', (sha,str(chart_path)))
        for valid_from, price in points:
            previous = conn.execute('''SELECT price_chf FROM retailer_price_change
                WHERE retailer_product_id=%s AND valid_from=%s''', (offer_id,valid_from)).fetchone()
            if previous:
                if previous['price_chf'] != price:
                    raise InvalidRecord('Historical chart conflicts with an imported validFrom')
                duplicate += 1
                continue
            conn.execute('''INSERT INTO retailer_price_change
                (retailer_product_id,valid_from,price_chf,point_type,raw_sha256)
                VALUES (%s,%s,%s,%s,%s)''',
                (offer_id,valid_from,price,'price' if price is not None else 'no_price',sha))
            loaded += 1
    return {'historical_change_points_imported':loaded,
            'historical_change_points_duplicate':duplicate}


def existing_chart_points(conn, offer_id, points):
    if not offer_id or not conn.execute("SELECT to_regclass('retailer_price_change') AS name").fetchone()['name']:
        return 0
    stored = conn.execute('''SELECT valid_from,price_chf FROM retailer_price_change
        WHERE retailer_product_id=%s AND valid_from=ANY(%s)''',
        (offer_id,[p[0] for p in points])).fetchall()
    source = dict(points)
    if any(source[row['valid_from']] != row['price_chf'] for row in stored):
        raise InvalidRecord('Historical chart conflicts with an imported validFrom')
    return len(stored)


def import_chart_manifest(manifest=CHART_MANIFEST, *, apply=False, conn=None, raw_dir=RAW,
                          source_root=ROOT / 'data/import/digitec/manual-charts'):
    """Import manually mapped Digitec change points, never a current observation.

    A GraphQL price-chart response lacks EAN, canonical URL and seller evidence.
    The manifest therefore records the team's explicit product mapping, while
    price_history remains untouched until a full product-page capture exists.
    """
    entries = json.loads(Path(manifest).read_text(encoding='utf-8'))
    if not isinstance(entries, list) or not entries:
        raise InvalidRecord('Chart manifest must contain product mappings')
    if len({entry.get('file') for entry in entries}) != len(entries):
        raise InvalidRecord('Chart manifest contains a duplicate source file')
    if len({entry.get('mediamarkt_sku') for entry in entries}) != len(entries):
        raise InvalidRecord('Chart manifest contains a duplicate MediaMarkt SKU')
    own_connection = conn is None
    if own_connection:
        conn = connect()
    try:
        if apply:
            migrate(conn)
        results = []
        for entry in entries:
            try:
                source = (ROOT / entry['file']).resolve()
                if not source.is_relative_to(Path(source_root).resolve()):
                    raise InvalidRecord('Chart source must be a local manual Digitec chart file')
                content = source.read_bytes()
                chart = json.loads(content)['data']['productById']
                source_name = text(chart.get('name'))
                if source_name != entry.get('source_name'):
                    raise InvalidRecord('Chart product name differs from manual mapping')
                try:
                    identity = base64.b64decode(chart['id'], validate=True).decode('utf-8')
                except (ValueError, UnicodeError, KeyError) as error:
                    raise InvalidRecord('Chart product ID is invalid') from error
                match = re.fullmatch(r'Product\nd(\d+):\d+:\d+', identity)
                if not match:
                    raise InvalidRecord('Chart product ID has no Digitec SKU')
                sku = match.group(1)
                points = chart_points(chart, datetime.now(timezone.utc))
                if not points:
                    raise InvalidRecord('Chart has no historical points')
                inclusive_price(chart.get('price'))  # Validate, but do not invent a current observation.
                target = conn.execute('''SELECT p.product_id,p.mpn,b.name AS brand,lower(c.name) AS category
                    FROM retailer_product rp JOIN retailer r USING(retailer_id)
                    JOIN product p USING(product_id) JOIN brand b USING(brand_id)
                    JOIN category c USING(category_id)
                    WHERE r.name='MediaMarkt' AND rp.retailer_sku=%s''',
                    (entry['mediamarkt_sku'],)).fetchall()
                if len(target) != 1:
                    raise InvalidRecord('MediaMarkt SKU has no unique product')
                product = target[0]
                selected_for_manual_poc(conn, product['product_id'])
                if source.parent.name.casefold() != product['category']:
                    raise InvalidRecord('Chart folder conflicts with product category')
                expected_mpn = entry.get('mpn')
                if expected_mpn:
                    if mpn_key(expected_mpn) != mpn_key(product['mpn']) or source.stem != expected_mpn:
                        raise InvalidRecord('Manual MPN and MediaMarkt product disagree')
                elif entry.get('confirmed_by_team') is not True or source.stem.casefold().replace('.', '') not in product['brand'].casefold().replace('.', ''):
                    raise InvalidRecord('Unnumbered product needs explicit team confirmation and brand match')
                offer = existing_offer(conn, {'sku':sku}, product['product_id'])
                other = conn.execute('''SELECT 1 FROM retailer_product rp JOIN retailer r USING(retailer_id)
                    WHERE r.name='Digitec' AND rp.product_id=%s AND rp.retailer_sku<>%s''',
                    (product['product_id'],sku)).fetchone()
                if other:
                    raise InvalidRecord('This product already has a different Digitec SKU')
                previous = existing_chart_points(conn, offer['retailer_product_id'] if offer else None, points)
                result = {'file':str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
                          'mediamarkt_sku':entry['mediamarkt_sku'],
                          'digitec_sku':sku,'matched_product_id':product['product_id'],
                          'points':len(points),'already_present':previous,
                          'status':'duplicate' if previous == len(points) else 'ready',
                          'current_observation_imported':False}
                if apply:
                    sha = hashlib.sha256(content).hexdigest()
                    archived = archive(source, content, sha, Path(raw_dir) / 'evidence')
                    with conn.transaction():
                        retailer_id = entity(conn, 'retailer', 'Digitec', website='https://www.digitec.ch')
                        if not offer:
                            offer_id = conn.execute('''INSERT INTO retailer_product
                                (product_id,retailer_id,retailer_sku,retailer_product_name)
                                VALUES (%s,%s,%s,%s) RETURNING retailer_product_id''',
                                (product['product_id'],retailer_id,sku,source_name)).fetchone()['retailer_product_id']
                        else:
                            offer_id = offer['retailer_product_id']
                        loaded = load_chart_points(conn,offer_id,points,sha,archived)
                    result.update(loaded)
                    result['status'] = 'loaded' if loaded['historical_change_points_imported'] else 'duplicate'
                results.append(result)
            except (KeyError, ValueError, TypeError, OSError, psycopg.Error) as error:
                results.append({'file':entry.get('file'), 'status':'rejected', 'reason':str(error).splitlines()[0]})
        return {'files':len(entries),'loaded':sum(x['status']=='loaded' for x in results),
                'duplicate':sum(x['status']=='duplicate' for x in results),
                'ready':sum(x['status']=='ready' for x in results),
                'rejected':sum(x['status']=='rejected' for x in results),
                'results':results}
    finally:
        if own_connection:
            conn.close()


def import_manual_snapshot(html_path, chart_path, captured_at, category, *, apply=False,
                           input_dir=INBOX, raw_dir=RAW, selection=SELECTION, conn=None):
    html_path, chart_path = Path(html_path), Path(chart_path)
    html_content, chart_content = html_path.read_bytes(), chart_path.read_bytes()
    record, points, details = manual_snapshot(html_content, chart_content, captured_at, category)
    name = 'manual_' + hashlib.sha256(html_content + chart_content).hexdigest() + '.json'
    destination = Path(input_dir) / name
    content = (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if destination.exists() and destination.read_bytes() != content:
        raise InvalidRecord('This manual evidence already has a different capture time or record')
    own_connection = conn is None
    if own_connection:
        conn = connect()
    try:
        if apply:
            migrate(conn)
        row = validated(record)
        product_id = match_media_product(conn, row)
        selected_for_manual_poc(conn, product_id, selection)
        offer = existing_offer(conn, row, product_id)
        previous = existing_observation(conn, row, offer['retailer_product_id'] if offer else None)
        current = existing_chart_points(conn,offer['retailer_product_id'] if offer else None,points)
        if not apply:
            return {'status': 'duplicate' if previous else 'ready', 'matched_product_id': product_id,
                    'sku': record['sku'], 'price_chf': record['price_chf'],
                    'observed_at': record['observed_at'],
                    'historical_change_points_already_present':current, **details}
        archive(html_path, html_content, hashlib.sha256(html_content).hexdigest(), Path(raw_dir) / 'evidence', '.html')
        chart_sha = hashlib.sha256(chart_content).hexdigest()
        chart_archive = archive(chart_path, chart_content, chart_sha, Path(raw_dir) / 'evidence')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            with destination.open('xb') as handle:
                handle.write(content)
        with conn.transaction():
            result = import_file(conn, destination, apply=True, raw_dir=raw_dir)
            if result['status'] not in {'loaded','duplicate'}:
                return {**result, **details}
            offer = existing_offer(conn,row,product_id)
            history = load_chart_points(conn,offer['retailer_product_id'],points,chart_sha,chart_archive)
            return {**result, **details, **history}
    finally:
        if own_connection:
            conn.close()


def import_file(conn, path, *, apply=False, raw_dir=RAW):
    path = Path(path)
    content = path.read_bytes()
    sha = hashlib.sha256(content).hexdigest()
    result = {'path': str(path), 'sha256': sha, 'status': 'rejected', 'reason': None}
    try:
        row = validated(json.loads(content))
        product_id = match_media_product(conn, row)
        if row['access_method'] == 'manual_capture':
            selected_for_manual_poc(conn,product_id)
        offer = existing_offer(conn, row, product_id)
        previous = existing_observation(conn, row, offer['retailer_product_id'] if offer else None)
        if not apply:
            result['status'] = 'duplicate' if previous else 'ready'
            result['matched_product_id'] = product_id
            return result
    except (ValueError, TypeError, UnicodeError) as error:
        row = None
        result['reason'] = str(error)
        if not apply:
            return result
    destination = archive(path, content, sha, Path(raw_dir))
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(91342002)')
        prior = conn.execute('SELECT status FROM raw_import WHERE sha256=%s', (sha,)).fetchone()
        if prior and prior['status'] in {'loaded', 'duplicate'}:
            result.update(status='duplicate', reason='Identical raw file already accepted')
            return result
        conn.execute('''INSERT INTO raw_import(sha256,path,status,reason)
            VALUES (%s,%s,'rejected',%s)
            ON CONFLICT(sha256) DO UPDATE SET path=EXCLUDED.path,reason=EXCLUDED.reason''',
            (sha,str(destination),result['reason']))
        if row is not None:
            try:
                with conn.transaction():
                    result['status'] = write_observation(conn,row,sha)
            except InvalidRecord as error:
                result.update(status='rejected', reason=str(error))
            except psycopg.Error as error:
                result.update(status='error', reason=str(error).splitlines()[0])
        conn.execute('UPDATE raw_import SET status=%s,reason=%s,processed_at=CURRENT_TIMESTAMP WHERE sha256=%s',
                     (result['status'],result['reason'],sha))
    return result


def run(input_dir=INBOX, *, apply=False, raw_dir=RAW, conn=None):
    input_dir = Path(input_dir)
    files = sorted(input_dir.glob('*.json')) if input_dir.is_dir() else []
    if not files:
        return {'status': 'awaiting_authorized_source_data', 'files': 0, 'results': []}
    own_connection = conn is None
    if own_connection:
        conn = connect()
    try:
        results = [import_file(conn,path,apply=apply,raw_dir=raw_dir) for path in files]
    finally:
        if own_connection:
            conn.close()
    counts = {status: sum(item['status'] == status for item in results)
              for status in ('ready','loaded','duplicate','rejected','error')}
    return {'status': 'applied' if apply else 'preview', 'files': len(files), **counts, 'results': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=INBOX, help='Directory of authorised one-offer JSON files')
    parser.add_argument('--apply', action='store_true', help='Archive originals and write matched offers to PostgreSQL')
    args = parser.parse_args(argv)
    report = run(args.input, apply=args.apply)
    print(json.dumps(report,indent=2,default=str))
    return 1 if report.get('error') or report.get('rejected') else 0


if __name__ == '__main__':
    raise SystemExit(main())
