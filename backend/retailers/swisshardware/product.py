"""Selected SwissHardware products: archived HTML -> checked master data -> PostgreSQL.

The shop's JSON-LD ``mpn`` is a Shopify variant ID. Only an explicitly labelled
manufacturer article number in the product specifications is an MPN here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from backend.database import connect, migrate
from backend.ingestion import ingest_file
from backend.retailers.swisshardware.collector import (
    CATALOG, ORIGIN, ROOT, USER_AGENT, atomic_json, catalog_lock,
    canonical_product_url, load_catalog, today,
)
from backend.transform import DETAIL_FIELDS, InvalidRecord, gtin, money, mpn_key, timestamp

RAW = ROOT / 'data/raw/swisshardware/products'


def plain(value: str) -> str:
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKD', value)
                  .encode('ascii', 'ignore').decode()).strip()


BRAND_PATTERNS = {
    'gpu': [('ASUS', r'\basus\b|\brog\s+(?:strix|astral)\b'),
            ('MSI', r'\bmsi\b'), ('AMD', r'\bamd\b')],
    'ram': [('G.SKILL', r'\bg[. ]?skill\b'),
            ('KINGSTON', r'\bkingston\b|\bfury\s+(?:beast|renegade)\b'),
            ('CORSAIR', r'\bcorsair\b')],
    'ssd': [('SAMSUNG', r'\bsamsung\b'),
            ('WESTERN DIGITAL', r'\bwestern\s+digital\b|\bwd(?:[_ ]?(?:black|blue|red|green))?\b|\bsandisk\b'),
            ('KINGSTON', r'\bkingston\b|\bfury\s+renegade\b')],
}


def scope_brand(name: str, category: str, manufacturer: str | None = None) -> str:
    """Prefer the page's labelled manufacturer; titles only identify aliases/fallbacks."""
    title = name.casefold()
    source = plain(manufacturer).casefold() if manufacturer else title
    brand = next((value for value, pattern in BRAND_PATTERNS[category]
                  if re.search(pattern, source)), None)
    if brand is None:
        raise InvalidRecord('Manufacturer is not clearly inside the configured scope')
    if brand == 'ASUS' and re.search(r'\brog\b', title):
        return 'ASUS ROG'  # Keep identity compatible with existing MediaMarkt ROG products.
    return brand


def in_scope(name: str, category: str, manufacturer: str | None = None) -> str:
    brand = scope_brand(name, category, manufacturer)
    upper = name.upper()
    if category == 'gpu':
        nvidia = re.search(r'\bRTX\s*(\d{4})\b', upper)
        amd = re.search(r'\bRX\s*(\d{4})\b', upper)
        if not ((nvidia and int(nvidia[1]) >= 3000) or (amd and int(amd[1]) >= 6000)):
            raise InvalidRecord('GPU family/model is outside the configured scope')
    elif category == 'ram':
        if re.search(r'\bSO[- ]?(?:DIMM|DDR[45])\b|\b(?:LAPTOP|NOTEBOOK)\b', upper):
            raise InvalidRecord('Outside project scope: desktop RAM only (SO-DIMM excluded)')
        capacity = re.search(r'\b(\d{1,3})\s*(?:GB|GO)\b', upper)
        if not re.search(r'\bDDR[45]\b', upper) or not capacity or not 8 <= int(capacity[1]) <= 64:
            raise InvalidRecord('RAM type/capacity is outside the configured scope')
    else:
        capacity = re.search(r'\b(\d+(?:[.,]\d+)?)\s*(TB|GB|GO)\b', upper)
        size = float(capacity[1].replace(',', '.')) * (1000 if capacity[2] == 'TB' else 1) if capacity else 0
        if (not 256 <= size <= 4000 or not re.search(r'\b(?:NVME|M[.]?2)\b', upper)
                or re.search(r'\b(?:EXTERN\w*|PORTABLE|USB|SATA)\b', upper)):
            raise InvalidRecord('SSD type/capacity is outside the configured scope')
    return brand


def specifications(soup: BeautifulSoup) -> dict[str, str]:
    values = {}
    for row in soup.select('tr'):
        cells = row.find_all(['th', 'td'], recursive=False)
        if len(cells) >= 2:
            values[plain(cells[0].get_text(' ', strip=True)).casefold()] = plain(cells[1].get_text(' ', strip=True))
    for row in soup.select('#specs-techniques .shw-product__spec-row'):
        key, value = row.find('dt'), row.find('dd')
        if key and value:
            values[plain(key.get_text(' ', strip=True)).casefold()] = plain(value.get_text(' ', strip=True))
    return values


def detail_number(specs: dict, key: str, unit: str = '') -> int | None:
    value = specs.get(key, '')
    found = re.search(r'(\d[\d ]*)\s*' + unit, value, re.I)
    return int(found[1].replace(' ', '')) if found else None


def parse_product(html: str, url: str, category: str, captured_at: str) -> dict:
    canonical = canonical_product_url(url)
    if category not in ('gpu', 'ram', 'ssd'):
        raise InvalidRecord('Unsupported category')
    observed = timestamp(captured_at)
    soup = BeautifulSoup(html, 'html.parser')
    link = soup.select_one('link[rel="canonical"]')
    if not link or canonical_product_url(link.get('href', '')) != canonical:
        raise InvalidRecord('Captured page canonical URL differs from the selected URL')
    products = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            node = json.loads(tag.string or tag.get_text())
        except (ValueError, TypeError):
            continue
        if isinstance(node, dict) and node.get('@type') == 'Product':
            products.append(node)
    matches = []
    for product in products:
        offer = product.get('offers')
        if isinstance(offer, dict) and offer.get('priceCurrency') == 'CHF':
            try:
                if canonical_product_url(offer.get('url', '')) == canonical:
                    matches.append((product, offer))
            except ValueError:
                pass
    if not matches:
        raise InvalidRecord('No matching CHF product offer in saved HTML')
    product, offer = matches[0]
    name = product.get('name')
    if not isinstance(name, str) or not name.strip():
        raise InvalidRecord('Product name is missing')
    seller = offer.get('seller')
    seller_name = seller.get('name', '') if isinstance(seller, dict) else ''
    if 'SwissHardware' not in seller_name:
        raise InvalidRecord('Offer is not sold by SwissHardware')
    price = money(offer.get('price'))
    specs = specifications(soup)
    explicit_brand = specs.get('fabricant')
    brand = in_scope(name, category, explicit_brand)
    # A matching title alias may be absent (e.g. FURY Beast); a conflicting
    # *known* title brand is still suspicious and must not be silently merged.
    if explicit_brand:
        try:
            title_brand = scope_brand(name, category)
        except InvalidRecord:
            title_brand = None
        if title_brand and title_brand != brand:
            raise InvalidRecord('Manufacturer specification conflicts with product name')
    mpn = specs.get('ref. du fabricant') or specs.get("n d'article fabricant")
    if mpn and mpn_key(mpn) in {'N/A', 'NONE', 'UNKNOWN', 'NON SPECIFIE', '-'}:
        mpn = None
    ean = specs.get('ean')
    details = {key: None for key in DETAIL_FIELDS[category]}
    if category == 'gpu':
        model = re.search(r'\b(?:RTX|RX)\s*\d{4}(?:\s*TI|\s*SUPER|\s*XT)?\b', name, re.I)
        details.update(gpu_model=model[0].upper() if model else None,
                       vram_gb=detail_number(specs, 'espace de stockage', r'(?:GB|Go)'),
                       vram_type=specs.get('type de memoire video'),
                       clock_mhz=detail_number(specs, "frequence d'horloge", 'MHz'),
                       boost_clock_mhz=detail_number(specs, 'frequence boost', 'MHz'),
                       tdp_watts=detail_number(specs, "consommation d'energie", 'W'))
    elif category == 'ram':
        kind = re.search(r'\bDDR[45]\b', name, re.I)
        capacity = re.search(r'\b(\d{1,3})\s*(?:GB|GO)\b', name, re.I)
        modules = re.search(r'\b(\d+)\s*[xX]\s*(\d+)\s*(?:GB|GO)\b', name, re.I)
        speed = re.search(r'\b(\d{4,5})\s*(?:MT/S|MHZ)\b', name, re.I)
        latency = re.search(r'\bCL\s*(\d+)\b', name, re.I)
        details.update(ram_type=kind[0].upper() if kind else None,
                       total_capacity_gb=int(capacity[1]) if capacity else None,
                       module_count=int(modules[1]) if modules else None,
                       capacity_per_module_gb=int(modules[2]) if modules else None,
                       speed_mts=int(speed[1]) if speed else None,
                       cas_latency='CL' + latency[1] if latency else None)
    else:
        details.update(capacity_gb=detail_number(specs, 'capacite de memoire totale', r'(?:GB|Go)'),
                       interface=specs.get('interface du disque dur'),
                       form_factor=specs.get('facteur de forme du ssd'),
                       nand_type=specs.get('memoire flash nand'),
                       read_speed_mbps=detail_number(specs, 'vitesse de lecture', 'MB/s'),
                       write_speed_mbps=detail_number(specs, "vitesse d ecriture", 'MB/s'))
    return {'brand': brand, 'sku': canonical.rsplit('/', 1)[-1], 'name': name,
            'category': category, 'ean': gtin(ean) if ean else None,
            'mpn': mpn_key(mpn), 'details': details, 'observed': observed,
            'price': price, 'original': None, 'availability': offer.get('availability'),
            'seller_name': seller_name, 'source_url': canonical}


def transform_raw(path: Path) -> dict:
    content = path.read_bytes()
    result = {'path': str(path), 'sha256': hashlib.sha256(content).hexdigest()}
    try:
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raise InvalidRecord('Raw capture must be a JSON object')
        if raw.get('source') != 'swisshardware' or raw.get('access_method') != 'public_html':
            raise InvalidRecord('Saved raw must be a SwissHardware public HTML capture')
        if not isinstance(raw.get('html'), str):
            raise InvalidRecord('Saved HTML is missing')
        result['observation'] = parse_product(raw['html'], raw['url'], raw['category'], raw['captured_at'])
    except (ValueError, KeyError, TypeError) as error:
        result['rejection'] = str(error)
    return result


def selected_rows(catalog_path: Path) -> list[dict]:
    return sorted((row for row in load_catalog(catalog_path)['products'].values() if row['selected']),
                  key=lambda row: (row['category'], row['slug']))


def active_rows(conn) -> list[dict]:
    """Daily tracking is controlled by the persisted offer flag and URL."""
    return conn.execute('''SELECT rp.retailer_sku AS slug,rp.product_url AS url,
        lower(c.name) AS category FROM retailer_product rp
        JOIN retailer r USING(retailer_id) JOIN product p USING(product_id)
        JOIN category c USING(category_id)
        WHERE r.name='SwissHardware' AND rp.is_active=TRUE
          AND rp.product_url IS NOT NULL AND lower(c.name) IN ('gpu','ram','ssd')
        ORDER BY rp.retailer_sku''').fetchall()


def scope_candidates(catalog_path: Path) -> list[dict]:
    """Review every category link; only the detail page can confirm manufacturer."""
    return sorted(load_catalog(catalog_path)['products'].values(),
                  key=lambda row: (row['category'], row['slug']))


def uncaptured_candidates(catalog_path: Path) -> tuple[list[dict], int]:
    """INITIAL never refetches a product page already archived on any date."""
    rows = scope_candidates(catalog_path)
    captured = {path.stem for path in RAW.glob('*/*.json')}
    return [row for row in rows if row['slug'] not in captured], len(captured.intersection(
        row['slug'] for row in rows))


def collect_rows(rows: list[dict], raw_dir: Path, max_products: int,
                 delay: float) -> dict:
    """Capture each product at most once per Zurich day, including failed requests.

    The dated request journal is written before HTTP. A crash during a request
    leaves ``in_flight`` set and conservatively stops the rest of that day.
    """
    if raw_dir.name != today() or max_products < 1 or delay < 3:
        raise ValueError('Live collection needs today, a positive limit and >=3 seconds delay')
    # When a conservative daily request cap is smaller than the selected set,
    # visit never-captured or oldest-captured products first on later runs.
    def last_capture(row):
        return max((path.parent.name for path in RAW.glob('*/' + row['slug'] + '.json')),
                   default='0000-00-00')
    raw_dir.mkdir(parents=True, exist_ok=True)
    journal_path = raw_dir / '_request_attempts.json'
    # The lock also prevents two concurrent DAILY runs from exceeding the
    # once-per-day agreement. It is held for this small bounded batch.
    with catalog_lock(journal_path):
        journal = (json.loads(journal_path.read_text(encoding='utf-8'))
                   if journal_path.exists() else {'date': raw_dir.name, 'attempted': [],
                                                 'in_flight': None, 'blocked': None})
        if journal.get('date') != raw_dir.name or not isinstance(journal.get('attempted'), list):
            raise ValueError('Invalid SwissHardware request journal; refusing live requests')
        attempted_today = set(journal['attempted'])
        pending = [row for row in rows if not (raw_dir / (row['slug'] + '.json')).exists()
                   and row['slug'] not in attempted_today]
        reused = sum((raw_dir / (row['slug'] + '.json')).exists() for row in rows)
        previously_attempted = len(rows) - reused - len(pending)
        pending.sort(key=lambda row: (last_capture(row), row['category'], row['slug']))
        blocked = journal.get('blocked') or (
            'Previous request was interrupted' if journal.get('in_flight') else None)
        if blocked or not pending:
            return {'selected': len(rows), 'product_requests': 0, 'saved': 0,
                    'reused_today': reused, 'already_attempted_today': previously_attempted,
                    'deferred': len(pending), 'blocked_today': blocked,
                    'errors': [{'error': f'SwissHardware requests paused today: {blocked}'}] if blocked else []}
        session = requests.Session()
        session.headers.update({'User-Agent': USER_AGENT, 'Accept-Language': 'de-CH,de;q=0.9'})
        fetched, attempts, failures = 0, 0, []
        try:
            try:
                robots_response = session.get(ORIGIN + '/robots.txt', timeout=20,
                                              allow_redirects=False)
                robots_response.raise_for_status()
            except requests.RequestException as error:
                journal['blocked'] = f'robots.txt failed: {error}'
                atomic_json(journal_path, journal)
                return {'selected': len(rows), 'product_requests': 0, 'saved': 0,
                        'reused_today': reused, 'already_attempted_today': previously_attempted,
                        'deferred': len(pending), 'blocked_today': journal['blocked'],
                        'errors': [{'error': journal['blocked']}]}
            robots = RobotFileParser()
            robots.parse(robots_response.text.splitlines())
            for row in pending:
                path = raw_dir / (row['slug'] + '.json')
                if attempts >= max_products:
                    break
                if not robots.can_fetch(USER_AGENT, row['url']):
                    failures.append({'slug': row['slug'], 'error': 'robots.txt disallows URL'})
                    continue
                time.sleep(delay)
                attempts += 1
                journal['attempted'].append(row['slug'])
                journal['in_flight'] = row['slug']
                atomic_json(journal_path, journal)
                try:
                    response = session.get(row['url'], timeout=25, allow_redirects=False)
                    if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
                        raise ValueError(f'HTTP {response.status_code} or non-HTML response')
                    captured_at = datetime.now(timezone.utc).isoformat()
                    # Preserve the original response; validation and DB import happen separately.
                    snapshot = {'source': 'swisshardware', 'access_method': 'public_html',
                                'url': row['url'], 'category': row['category'],
                                'captured_at': captured_at, 'html': response.text}
                    with path.open('x', encoding='utf-8') as saved:
                        json.dump(snapshot, saved, ensure_ascii=False)
                    fetched += 1
                    print(f"SwissHardware {fetched}/{max_products}: saved {row['category']} {row['slug']}", flush=True)
                except (requests.RequestException, ValueError) as error:
                    failures.append({'slug': row['slug'], 'error': str(error)})
                    if (isinstance(error, ValueError) and
                            (response.status_code in (403, 429) or response.status_code >= 500)):
                        journal['blocked'] = f'HTTP {response.status_code}'
                # Leave in_flight set on an unexpected interruption. The next
                # run then makes no more requests until the next Zurich day.
                journal['in_flight'] = None
                atomic_json(journal_path, journal)
                if journal['blocked']:
                    break
            return {'selected': len(rows), 'product_requests': attempts, 'saved': fetched,
                    'reused_today': reused, 'already_attempted_today': previously_attempted,
                    'deferred': max(0, len(pending) - attempts -
                                    sum(1 for failure in failures if failure['error'].startswith('robots.txt'))),
                    'blocked_today': journal['blocked'], 'errors': failures}
        finally:
            session.close()


def collect_selected(catalog_path: Path, raw_dir: Path, max_products: int = 3,
                     delay: float = 3.0) -> dict:
    return collect_rows(selected_rows(catalog_path), raw_dir, max_products, delay)


def import_saved(raw_dir: Path, catalog_path: Path, rows=None) -> dict:
    selected = {row['slug']: row for row in (rows if rows is not None else selected_rows(catalog_path))}
    result = {'files': 0, 'loaded': 0, 'duplicate': 0, 'rejected': 0, 'error': 0, 'results': []}
    with connect() as conn:
        migrate(conn)
        for path in sorted(raw_dir.glob('*.json')):
            if path.stem not in selected:
                continue
            item = transform_raw(path)
            if 'observation' in item:
                row = selected[path.stem]
                observed = item['observation']
                if observed['source_url'] != row['url'] or observed['category'] != row['category']:
                    item.pop('observation')
                    item['rejection'] = 'Raw URL/category differs from the selected catalog row'
            outcome = ingest_file(conn, path, 'swisshardware', transformed=item)
            result['files'] += 1
            result[outcome['status']] += 1
            result['results'].append(outcome)
    return result


MISSING_MPN_REASON = (
    'No verified manufacturer MPN on product page; excluded from daily tracking '
    'because cross-retailer identity cannot be verified'
)


def import_scope(raw_dir: Path, catalog_path: Path) -> dict:
    """Store checked in-scope captures; only verified MPNs enter DAILY."""
    report = {'candidate_files': 0, 'with_mpn': 0, 'loaded': 0,
              'duplicate': 0, 'missing_mpn': 0, 'inactive_imported': 0,
              'rejected': 0, 'error': 0, 'selected_for_daily': 0,
              'by_category': {'gpu': 0, 'ram': 0, 'ssd': 0},
              'results': []}
    with catalog_lock(catalog_path):
        catalog = load_catalog(catalog_path)
        candidates = {row['slug']: row for row in scope_candidates(catalog_path)}
        with connect() as conn:
            migrate(conn)
            for path in sorted(raw_dir.glob('*.json')):
                row = candidates.get(path.stem)
                if row is None:
                    continue
                report['candidate_files'] += 1
                item = transform_raw(path)
                observation = item.get('observation')
                if observation and (observation['source_url'] != row['url'] or
                                    observation['category'] != row['category']):
                    item.pop('observation')
                    item['rejection'] = 'Raw URL/category differs from the catalog listing'
                    observation = None
                if not observation:
                    status, reason = 'rejected', item.get('rejection', 'Invalid observation')
                    # Record the captured source and rejection in PostgreSQL
                    # without inventing a product/brand for an out-of-scope page.
                    ingest_file(conn, path, 'swisshardware', transformed=item)
                    report['rejected'] += 1
                    catalog['products'][row['slug']]['selected'] = False
                    # Preserve offers loaded under an older, looser scope but
                    # prevent the daily job from requesting them again.
                    conn.execute('''UPDATE retailer_product rp SET
                        is_active=FALSE,tracking_reason=%s FROM retailer r
                        WHERE rp.retailer_id=r.retailer_id AND r.name='SwissHardware'
                          AND rp.retailer_sku=%s''', (reason, row['slug']))
                else:
                    has_mpn = bool(observation['mpn'])
                    item['active'] = has_mpn
                    item['tracking_reason'] = None if has_mpn else MISSING_MPN_REASON
                    report['with_mpn' if has_mpn else 'missing_mpn'] += 1
                    outcome = ingest_file(conn, path, 'swisshardware', transformed=item)
                    status, reason = outcome['status'], outcome['reason']
                    report[status] += 1
                    if status in ('loaded', 'duplicate'):
                        catalog['products'][row['slug']]['selected'] = has_mpn
                        if has_mpn:
                            report['by_category'][row['category']] += 1
                        else:
                            # Older proof-of-concept offers were already loaded before
                            # the tracking flag existed. Preserve them but stop DAILY.
                            conn.execute('''UPDATE retailer_product rp SET
                                is_active=FALSE,tracking_reason=%s FROM retailer r
                                WHERE rp.retailer_id=r.retailer_id AND r.name='SwissHardware'
                                  AND rp.retailer_sku=%s''',
                                (item['tracking_reason'], row['slug']))
                            report['inactive_imported'] += 1
                catalog['products'][row['slug']]['validation_status'] = (
                    'active' if observation and status in ('loaded', 'duplicate') and observation['mpn'] else
                    'inactive_missing_mpn' if observation and status in ('loaded', 'duplicate') else status)
                catalog['products'][row['slug']]['validation_reason'] = (
                    MISSING_MPN_REASON
                    if catalog['products'][row['slug']]['validation_status'] == 'inactive_missing_mpn'
                    else reason)
                report['results'].append({'slug': row['slug'], 'category': row['category'],
                                          'status': catalog['products'][row['slug']]['validation_status'],
                                          'reason': catalog['products'][row['slug']]['validation_reason']})
        report['selected_for_daily'] = sum(bool(row.get('selected')) for row in catalog['products'].values())
        atomic_json(catalog_path, catalog)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['collect', 'import', 'daily', 'initial'])
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--raw-dir', type=Path, default=RAW / today())
    parser.add_argument('--max-products', type=int, default=3,
                        help='Maximum new product pages; INITIAL can use a larger explicit budget')
    parser.add_argument('--delay', type=float, default=3.0)
    args = parser.parse_args(argv)
    result = {}
    if args.command in ('collect', 'daily'):
        if args.command == 'daily':
            with connect() as conn:
                migrate(conn)
                rows = active_rows(conn)
            result['collection'] = collect_rows(rows, args.raw_dir, args.max_products, args.delay)
        else:
            result['collection'] = collect_selected(args.catalog, args.raw_dir, args.max_products, args.delay)
    if args.command == 'initial':
        if args.raw_dir.name == today():
            rows, previously_captured = uncaptured_candidates(args.catalog)
            result['collection'] = collect_rows(rows, args.raw_dir,
                                                args.max_products, args.delay)
            result['collection']['previously_captured'] = previously_captured
            result['collection']['catalog_candidates'] = len(rows) + previously_captured
        else:
            result['collection'] = {'product_requests': 0, 'offline_replay': True}
        result['import'] = import_scope(args.raw_dir, args.catalog)
    if args.command in ('import', 'daily'):
        result['import'] = import_saved(args.raw_dir, args.catalog,
                                        rows=rows if args.command == 'daily' else None)
    print(json.dumps(result, indent=2, default=str))
    return 1 if result.get('collection', {}).get('errors') or result.get('import', {}).get('error') else 0


if __name__ == '__main__':
    raise SystemExit(main())
