"""One transaction per raw file; exact identifiers and the original timestamp."""
from pathlib import Path
import psycopg
from psycopg import sql

from .transform import InvalidRecord
from .transform import transform_file, transform_directory


def entity(conn, table, name, **extra):
    if table == 'brand':
        old = conn.execute('SELECT brand_id FROM brand WHERE lower(btrim(name))=lower(btrim(%s))', (name,)).fetchone()
        if old:
            return old['brand_id']
    columns = ['name', *extra]
    query = sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT(name) DO UPDATE SET name=EXCLUDED.name RETURNING {}').format(
        sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, columns)),
        sql.SQL(',').join(sql.Placeholder() for _ in columns), sql.Identifier(table + '_id'))
    return conn.execute(query, [name, *extra.values()]).fetchone()[table + '_id']


def resolve_product(conn, v, brand_id, category_id, retailer_id):
    matches = set()
    if v['ean']:
        matches.update(r['product_id'] for r in conn.execute(
            "SELECT product_id FROM product WHERE lpad(ean,14,'0')=%s", (v['ean'],)))
    if v['mpn']:
        matches.update(r['product_id'] for r in conn.execute(
            'SELECT product_id FROM product WHERE brand_id=%s AND upper(btrim(mpn))=%s', (brand_id,v['mpn'])))
    matches.update(r['product_id'] for r in conn.execute(
        'SELECT product_id FROM retailer_product WHERE retailer_id=%s AND retailer_sku=%s', (retailer_id,v['sku'])))
    if len(matches)>1:
        raise InvalidRecord('GTIN, manufacturer/MPN and listing point to different products')
    if matches:
        product = conn.execute('SELECT * FROM product WHERE product_id=%s', (matches.pop(),)).fetchone()
        if product['brand_id'] != brand_id or product['category_id'] != category_id:
            raise InvalidRecord('Matched product has conflicting manufacturer/category')
        for key in ('ean','mpn'):
            old = product[key]
            if key == 'ean' and old:
                old = old.zfill(14)
            if key == 'mpn' and old:
                old = old.strip().upper()
            if old and v[key] and old != v[key]:
                raise InvalidRecord('Matched product has conflicting ' + key)
        pid = product['product_id']
        conn.execute('UPDATE product SET ean=COALESCE(ean,%s),mpn=COALESCE(mpn,%s) WHERE product_id=%s', (v['ean'],v['mpn'],pid))
    else:
        # Without global identifiers, create a separate product for this SKU.
        # Never infer identity from a similar name; the listing resolves reruns.
        pid = conn.execute('''INSERT INTO product(brand_id,category_id,product_name,ean,mpn)
            VALUES (%s,%s,%s,%s,%s) RETURNING product_id''',
            (brand_id,category_id,v['name'],v['ean'],v['mpn'])).fetchone()['product_id']
    table = sql.Identifier(v['category'] + '_details')
    old = conn.execute(sql.SQL('SELECT * FROM {} WHERE product_id=%s').format(table), (pid,)).fetchone()
    if old:
        for key,value in v['details'].items():
            same = old[key].casefold() == value.casefold() if isinstance(old[key],str) and isinstance(value,str) else old[key] == value
            if value is not None and old[key] is not None and not same:
                raise InvalidRecord('Conflicting technical attribute: ' + key)
    conn.execute(sql.SQL('INSERT INTO {}(product_id) VALUES (%s) ON CONFLICT(product_id) DO NOTHING').format(table), (pid,))
    for key,value in v['details'].items():
        if value is not None:
            conn.execute(sql.SQL('UPDATE {} SET {}=COALESCE({},%s) WHERE product_id=%s').format(table,sql.Identifier(key),sql.Identifier(key)), (value,pid))
    return pid


def load_observation(conn, v, raw_sha):
    bid = entity(conn,'brand',v['brand'])
    cid = entity(conn,'category',v['category'].upper())
    rid = entity(conn,'retailer','MediaMarkt',website='https://www.mediamarkt.ch')
    pid = resolve_product(conn,v,bid,cid,rid)
    listing = conn.execute('''INSERT INTO retailer_product
        (product_id,retailer_id,retailer_sku,retailer_product_name,product_url,first_seen_at,last_seen_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(retailer_id,retailer_sku) DO UPDATE SET
          first_seen_at=LEAST(retailer_product.first_seen_at,EXCLUDED.first_seen_at),
          last_seen_at=GREATEST(retailer_product.last_seen_at,EXCLUDED.last_seen_at)
        RETURNING retailer_product_id''',
        (pid,rid,v['sku'],v['name'],v['source_url'],v['observed'],v['observed'])).fetchone()['retailer_product_id']
    previous = conn.execute('SELECT * FROM price_history WHERE retailer_product_id=%s AND collected_at=%s', (listing,v['observed'])).fetchone()
    if previous:
        for field,key in [('price_chf','price'),('original_price_chf','original'),('seller_name','seller_name'),('availability','availability')]:
            if previous[field] != v[key]:
                raise InvalidRecord('Same observation timestamp has conflicting ' + field)
        return 'duplicate'
    conn.execute('''INSERT INTO price_history
        (retailer_product_id,price_chf,original_price_chf,availability,collected_at,raw_sha256,source_url,seller_name)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
        (listing,v['price'],v['original'],v['availability'],v['observed'],raw_sha,v['source_url'],v['seller_name']))
    return 'loaded'


def ingest_file(conn, path, source='mediamarkt', *, transformed=None):
    if source != 'mediamarkt':
        raise ValueError('Only MediaMarkt is active in the Midterm')
    item = transformed if transformed is not None else transform_file(path)
    status, reason = 'rejected', item.get('rejection')
    with conn.transaction():
        # Small batches: serialize identity decisions, including concurrent reruns.
        conn.execute('SELECT pg_advisory_xact_lock(91342002)')
        previous = conn.execute('SELECT status FROM raw_import WHERE sha256=%s', (item['sha256'],)).fetchone()
        if previous and previous['status'] in ('loaded','duplicate'):
            return {'path':item['path'],'status':'duplicate','reason':'Identical raw file already accepted'}
        conn.execute('''INSERT INTO raw_import(sha256,path,evidence_path,status,reason)
            VALUES (%s,%s,%s,'rejected',%s) ON CONFLICT(sha256) DO UPDATE SET
            path=EXCLUDED.path,evidence_path=EXCLUDED.evidence_path''',
            (item['sha256'],item['path'],item.get('evidence'),reason))
        if 'observation' in item:
            try:
                with conn.transaction():
                    status = load_observation(conn,item['observation'],item['sha256'])
            except InvalidRecord as error:
                status,reason = 'rejected',str(error)
            except psycopg.Error as error:
                status,reason = 'error',str(error).splitlines()[0]
        conn.execute('UPDATE raw_import SET status=%s,reason=%s,processed_at=CURRENT_TIMESTAMP WHERE sha256=%s', (status,reason,item['sha256']))
    return {'path':item['path'],'status':status,'reason':reason}


def ingest_directory(conn, directory, source='mediamarkt', *, transformed=None):
    items = transformed if transformed is not None else transform_directory(directory)
    report = {'files':len(items),'loaded':0,'duplicate':0,'rejected':0,'error':0,'results':[]}
    for item in items:
        result = ingest_file(conn,Path(item['path']),source,transformed=item)
        report[result['status']] += 1
        report['results'].append(result)
    report['accepted'] = report['loaded'] + report['duplicate']
    return report
