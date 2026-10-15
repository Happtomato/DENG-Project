"""Bounded catalogue discovery and repeatable daily MediaMarkt observations.

Run `python backend/scrapeMediamarkt/pipeline.py --help` from any directory.
The catalogue is an extraction queue, not a replacement for PostgreSQL.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
# Keep the existing inspect.py helper from shadowing the standard library.
if sys.path and Path(sys.path[0]).resolve() == HERE:
    sys.path.pop(0)
spec = importlib.util.spec_from_file_location("mediamarkt_product", HERE / "app.py")
mm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mm)

ROOT = HERE.parents[1]
CATALOG = ROOT / "data/catalog/mediamarkt.json"
ORIGIN = "https://www.mediamarkt.ch"


class StopRun(mm.ScraperError):
    """Stop all network activity on throttling, blocked access or budget limits."""


class FetchError(mm.ScraperError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def canonical_url(url, *, product=False):
    parsed = urlsplit(urljoin(ORIGIN, url))
    if parsed.scheme != "https" or parsed.netloc != "www.mediamarkt.ch":
        raise ValueError("Only HTTPS URLs on www.mediamarkt.ch are accepted")
    prefix = "/de/product/" if product else "/de/"
    if not parsed.path.startswith(prefix) or not parsed.path.endswith(".html"):
        raise ValueError("Expected a German MediaMarkt HTML page")
    if product and not mm.extract_product_id(parsed.path):
        raise ValueError("Product URL has no retailer SKU")
    # Strip tracking, store selection, fragments and offer-selection parameters.
    return urlunsplit(("https", parsed.netloc, parsed.path, "", ""))


def day(timestamp):
    return datetime.fromisoformat(timestamp).astimezone(ZoneInfo("Europe/Zurich")).date().isoformat()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


@contextmanager
def catalog_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise mm.ScraperError(f"Another run owns {lock}; after a crash, verify no process runs before removing this lock.") from error
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def load_catalog(path):
    if not path.exists():
        return {"version": 1, "source": "mediamarkt", "products": {}, "discovery": {}}
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("version") != 1 or not isinstance(result.get("products"), dict):
        raise mm.ScraperError("Unsupported or corrupt catalogue; will not overwrite")
    return result


class Client:
    def __init__(self, delay=3, max_requests=100):
        self.session = mm.build_session()
        self.delay = max(3.0, delay)
        self.max_requests = max_requests
        self.requests = 0
        self.last_request = None
        self.robots = None
        self.wildcard_rules = []

    def close(self):
        self.session.close()

    def request(self, url):
        if self.requests >= self.max_requests:
            raise StopRun(f"Request budget reached ({self.max_requests}); resume on the next run")
        if self.last_request is not None:
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        self.requests += 1
        try:
            response = self.session.get(url, timeout=mm.TIMEOUT_SECONDS, allow_redirects=False)
        except mm.requests.RequestException as error:
            raise FetchError(f"Request failed: {error}") from error
        if response.status_code in {401, 403, 429, 503}:
            raise StopRun(f"HTTP {response.status_code}: stopping; Retry-After={response.headers.get('Retry-After', 'unspecified')}")
        return response

    def check_robots(self, url):
        if self.robots is None:
            response = self.request(ORIGIN + "/robots.txt")
            if response.status_code != 200 or "<html" in response.text.lower():
                raise StopRun("robots.txt unavailable; no pages fetched")
            lines = response.text.splitlines()
            self.robots = RobotFileParser()
            self.robots.parse(lines)
            crawl_delay = self.robots.crawl_delay(mm.USER_AGENT)
            rate = self.robots.request_rate(mm.USER_AGENT)
            self.delay = max(self.delay, float(crawl_delay or 0), rate.seconds / rate.requests if rate and rate.requests else 0)
            # urllib.robotparser does not implement wildcard path matching.
            # Also enforce wildcard rules in the applicable default group.
            default_group = False
            for line in lines:
                key, sep, value = line.split('#', 1)[0].partition(':')
                key, value = key.strip().lower(), value.strip()
                if key == "user-agent":
                    default_group = value == "*"
                elif default_group and key in {"allow", "disallow"} and value:
                    self.wildcard_rules.append((key == "allow", value))
        if not self.robots.can_fetch(mm.USER_AGENT, url):
            raise FetchError("robots.txt disallows URL")
        path = unquote(urlsplit(url).path + ("?" + urlsplit(url).query if urlsplit(url).query else ""))
        matches = []
        for allowed, rule in self.wildcard_rules:
            pattern = "^" + re.escape(rule.rstrip('$')).replace(r"\*", ".*") + ("$" if rule.endswith('$') else "")
            if re.search(pattern, path):
                matches.append((len(rule.replace('*', '')), allowed))
        if matches and not max(matches)[1]:
            raise FetchError("robots.txt wildcard rule disallows URL")

    def get_html(self, url, *, product=False):
        original_id = mm.extract_product_id(url) if product else None
        for _ in range(4):
            canonical_url(url, product=product)
            if original_id and mm.extract_product_id(url) != original_id:
                raise FetchError("Redirect changed product SKU")
            self.check_robots(url)
            response = self.request(url)
            if response.status_code in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.headers.get("Location", ""))
                continue
            if response.status_code != 200:
                raise FetchError(f"HTTP {response.status_code} for {url}", response.status_code)
            if "html" not in response.headers.get("Content-Type", "").lower():
                raise FetchError("Expected HTML")
            response.encoding = "utf-8"
            return response.text, url
        raise FetchError("Too many redirects")


def listing(html, url):
    soup = mm.BeautifulSoup(html, "html.parser")
    state = mm.load_preloaded_apollo_state(soup)
    cat_id = "CAT_CH_MM_" + re.search(r"-(\d+)\.html", url)[1]
    ids = set()
    max_page = None
    for key, value in state.items():
        if cat_id not in key or not isinstance(value, dict):
            continue
        if value.get("__typename") == "ProductListPage":
            ids.update(str(p["productId"]) for p in value.get("products", []) if p.get("productId"))
        if value.get("__typename") == "ProductList":
            max_page = value.get("maxPage")
    if not ids or not isinstance(max_page, int) or max_page < 1:
        raise mm.ScraperError("No verified listing/pagination data: page layout may have changed")
    found = {}
    for anchor in soup.select('a[href]'):
        try:
            link = canonical_url(anchor['href'], product=True)
        except ValueError:
            continue
        sku = mm.extract_product_id(link)
        if sku in ids:
            title = anchor.get_text(" ", strip=True)
            if sku not in found or title:
                found[sku] = {"sku": sku, "url": link, "title": title}
    if set(found) != ids:
        raise mm.ScraperError("Listing contains product IDs without links; refusing an incomplete page")
    return list(found.values()), max_page


def scope_decision(record, category, config):
    """accepted/excluded/review: unknown evidence never silently passes."""
    metadata = record['metadata']
    if metadata.get('category_code') != category:
        return "review", "category_not_confirmed"
    technical = record.get('technical_payload', {})
    features = technical.get('features', [])
    get = lambda *names: mm.feature_value(features, names=names)
    identity = " ".join(str(x or "") for x in [record['product']['product_name'], technical.get('raw_title'), get('Produkttyp'), get('Speichertechnologie'), get('Speicher Architektur')])
    if re.search(r"\b(?:refurbished|gebraucht|renewed|enterprise|server|workstation|quadro|NAS|RDIMM|LRDIMM)\b|RTX\s*PRO|SO[ -]?DIMM|Notebook", identity, re.I):
        return "excluded", "excluded_hardware_or_condition"
    if mm.nullable_bool(get('Wiederaufbereitet')) is True:
        return "excluded", "refurbished"
    condition = str(metadata.get('item_condition') or '').rsplit('/', 1)[-1]
    if condition and condition != 'NewCondition':
        return "excluded", "not_new"
    if not condition:
        return "review", "condition_unknown"
    if metadata.get('quality_warnings'):
        return "review", ",".join(metadata['quality_warnings'])
    allowed_brands = config.get('brands', [])
    brand = record['brand']['name']
    if allowed_brands and not brand:
        return "review", "brand_unknown"
    if allowed_brands and str(brand).casefold() not in {b.casefold() for b in allowed_brands}:
        return "excluded", "brand_filter"
    if category == 'gpu':
        model_text = str(record['gpu_details']['gpu_model'] or identity).replace('™', '')
        model = re.search(r"\b(GeForce\s+RTX|Radeon\s+RX)\s*(\d{4})\b", model_text, re.I)
        if not model:
            return "review", "consumer_gpu_family_unknown"
        minimum = config['nvidia_min_model'] if 'rtx' in model[1].lower() else config['amd_min_model']
        family = 'rtx' if 'rtx' in model[1].lower() else 'rx'
        if family not in config.get('families', ['rtx', 'rx']):
            return 'excluded', 'gpu_family_filter'
        return ("accepted", "in_scope") if int(model[2]) >= minimum else ("excluded", "older_gpu_generation")
    if category == 'ram':
        detail = record['ram_details']
        if detail['ram_type'] not in config['types']:
            return ("review", "ram_type_unknown") if detail['ram_type'] is None else ("excluded", "ram_type")
        if not re.search(r"\b(?:U-?DIMM|DIMM|Desktop)\b", identity, re.I):
            return "review", "desktop_ram_not_confirmed"
        if detail['ecc'] is True:
            return "excluded", "ecc_server_memory"
        capacity = detail['total_capacity_gb']
    else:
        detail = record['ssd_details']
        capacity = detail['capacity_gb']
        construction = str(get('Bauart') or '')
        if re.search(r"\bextern", construction, re.I):
            return "excluded", "external_ssd"
        if construction != 'intern' and 'interne' not in str(record['category']['name']).lower():
            return "review", "internal_ssd_not_confirmed"
        if re.search(r"SATA|SAS", str(detail['interface']), re.I):
            return "excluded", "non_nvme_ssd"
        if not re.search(r"NVMe", str(detail['interface']) + ' ' + identity, re.I):
            return "review", "nvme_not_confirmed"
        if detail['pcie_generation'] not in config['pcie_generations']:
            return "review", "pcie_generation_not_confirmed"
    if capacity is None:
        return "review", "capacity_unknown"
    return ("accepted", "in_scope") if config['min_gb'] <= capacity <= config['max_gb'] else ("excluded", "capacity_out_of_range")


def register(catalog, item, category, source):
    key = 'mediamarkt:' + item['sku']
    now = mm.utc_now().isoformat()
    row = catalog['products'].get(key)
    if row is None:
        row = {"retailer": "mediamarkt", "retailer_sku": item['sku'],
               "product_url": item['url'], "title": item.get('title'),
               "category": category, "status": "candidate", "first_seen_at": now,
               "last_success_at": None, "last_attempt_at": None, "consecutive_errors": 0}
        catalog['products'][key] = row
    row['last_discovered_at'] = now
    row['discovered_from'] = source
    # Do not overwrite a validated canonical URL with stale listing data.
    if row['status'] == 'candidate':
        row['product_url'] = item['url']
    return row


def discover(catalog, client, args, config, report):
    for category in args.categories:
        seed = canonical_url(config[category]['category_url'])
        cursor = catalog['discovery'].setdefault(category, {'next_page': 1})
        for _ in range(args.max_pages):
            page = cursor['next_page']
            url = seed + (f'?page={page}' if page > 1 else '')
            html, final_url = client.get_html(url)
            save_html(args.debug_dir, f'listing_{category}_{page}', html)
            products, last_page = listing(html, final_url)
            signature = hashlib.sha256(','.join(sorted(p['sku'] for p in products)).encode()).hexdigest()
            if page > 1 and signature == cursor.get('last_signature'):
                raise mm.ScraperError('Pagination repeated the previous page; cursor retained for inspection')
            for item in products:
                register(catalog, item, category, url)
            cursor.update(next_page=page + 1 if page < last_page else 1,
                          last_signature=signature, last_page=last_page,
                          last_completed_at=mm.utc_now().isoformat(), cycle_complete=page >= last_page)
            atomic_json(args.catalog, catalog)
            report['pages'] += 1
            print(f'{category}: page {page}/{last_page}, {len(products)} product links')
            if page >= last_page:
                break


def save_html(directory, label, html):
    directory.mkdir(parents=True, exist_ok=True)
    stamp = mm.utc_now().strftime('%Y%m%dT%H%M%S%fZ')
    (directory / f'{label}_{stamp}.html').write_text(html, encoding='utf-8')


def collect(catalog, client, args, config, report):
    today = day(mm.utc_now().isoformat())
    states = {'candidate'} if args.command in {'discover', 'collect'} else {'accepted'}
    if args.recheck:
        states.update({'review', 'excluded'})
    for category in args.categories:
        rows = [r for r in catalog['products'].values() if r['category'] == category and r['status'] in states]
        # Oldest attempt first prevents unavailable products starving the queue.
        rows.sort(key=lambda r: r.get('last_attempt_at') or '')
        attempted = 0
        for row in rows:
            if not args.recheck and row.get('last_success_at') and day(row['last_success_at']) == today:
                report['skipped_today'] += 1
                continue
            if attempted >= args.max_products:
                report['remaining_due'] += 1
                continue
            attempted += 1
            row['last_attempt_at'] = mm.utc_now().isoformat()
            try:
                record_path = args.output_dir / f"{row['retailer_sku']}_{today}.json"
                existing_path = record_path
                if row.get('last_success_at') and day(row['last_success_at']) == today and row.get('last_record'):
                    existing_path = Path(row['last_record'])
                reused = existing_path.is_file()
                if reused:
                    # Recover a crash after writing the observation but before
                    # committing the catalogue, without a second HTTP request.
                    record = json.loads(existing_path.read_text(encoding='utf-8'))
                    if (record['metadata'].get('source') != 'mediamarkt'
                            or record['metadata'].get('access_method') != 'public_html'
                            or day(record['metadata']['collected_at']) != today):
                        raise mm.ScraperError('Existing daily observation has unexpected identity/date')
                    record_path = existing_path
                    final_url = record['metadata']['source_url']
                else:
                    html, final_url = client.get_html(row['product_url'], product=True)
                    save_html(args.debug_dir, row['retailer_sku'], html)
                    record = mm.parse_html(html, final_url, 'public_html')
                if record['retailer_product']['retailer_sku'] != row['retailer_sku']:
                    raise mm.ScraperError('Product identity differs from catalogue SKU')
                status, reason = scope_decision(record, category, config[category])
                record['metadata'].update(scope_status=status, scope_reason=reason,
                                          run_id=report['run_id'], observation_day=today)
                record['retailer_product'].update(first_seen_at=row['first_seen_at'], last_seen_at=record['metadata']['collected_at'])
                # Keep rejected raw records for audit, but do not ingest their prices.
                if not reused:
                    atomic_json(record_path, record)
                row.update(status=status, reason=reason, title=record['product']['product_name'],
                           product_url=canonical_url(final_url, product=True),
                           brand=record['brand']['name'], ean=record['product']['ean'], mpn=record['product']['mpn'],
                           last_success_at=record['metadata']['collected_at'], last_record=str(record_path),
                           consecutive_errors=0, last_error=None)
                price = record['price_history']['price_chf']
                price_valid = price is not None and price > 0
                row['last_price_valid'] = price_valid
                report[status] += 1
                if status == 'accepted' and not price_valid:
                    report['missing_price'] += 1
                print(f"{category} {row['retailer_sku']}: {status} ({reason})")
            except StopRun:
                raise
            except (FetchError, mm.ScraperError, ValueError) as error:
                row['last_error'] = str(error)
                row['consecutive_errors'] += 1
                # Keep vanished/temporarily unavailable URLs for subsequent runs.
                report['errors'].append({'sku': row['retailer_sku'], 'error': str(error)})
                print(f"Failed {row['retailer_sku']}: {error}", file=sys.stderr)
            finally:
                atomic_json(args.catalog, catalog)


def positive(value):
    value = int(value)
    if value <= 0:
        raise argparse.ArgumentTypeError('Must be a positive integer')
    return value


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['discover', 'collect', 'daily', 'add', 'status'])
    parser.add_argument('--categories', nargs='+', choices=['gpu', 'ram', 'ssd'], default=['gpu', 'ram', 'ssd'])
    parser.add_argument('--config', type=Path, default=HERE / 'scope.json')
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--output-dir', type=Path, default=mm.RAW_DIR)
    parser.add_argument('--debug-dir', type=Path, default=ROOT / 'data/debug/mediamarkt')
    parser.add_argument('--max-pages', type=positive, default=2, help='Category pages per category per discover run; cursor persists')
    parser.add_argument('--max-products', type=positive, default=10, help='Product attempts per category per run')
    parser.add_argument('--max-requests', type=positive, default=100, help='Total HTTP request budget including robots and redirects')
    parser.add_argument('--delay', type=float, default=3, help='Minimum seconds between requests; never below 3')
    parser.add_argument('--links-only', action='store_true', help='Discover links without product fetches')
    parser.add_argument('--recheck', action='store_true', help='Re-evaluate excluded/review products against current config')
    parser.add_argument('--brand', help='Override brand filter for the selected categories, e.g. ASUS')
    parser.add_argument('--gpu-family', choices=['rtx', 'rx'], help='Optional GPU family filter, e.g. rtx for ASUS RTX 30 and newer')
    parser.add_argument('--url', action='append', default=[], help='Known product URL for add; repeatable')
    args = parser.parse_args(argv)
    if args.command == 'add' and (len(args.categories) != 1 or not args.url):
        parser.error('add requires exactly one --categories value and at least one --url')
    if args.links_only and args.command != 'discover':
        parser.error('--links-only is only valid with discover')
    if args.delay < 3 or not __import__('math').isfinite(args.delay):
        parser.error('--delay must be a finite value of at least 3 seconds')
    return args


def main(argv=None):
    args = arguments(argv)
    client = None
    try:
        # Fail early if Windows lacks tzdata, before any network access.
        ZoneInfo('Europe/Zurich')
        config = json.loads(args.config.read_text(encoding='utf-8'))
        for category in args.categories:
            canonical_url(config[category]['category_url'])
            if args.brand:
                config[category]['brands'] = [args.brand]
            if category == 'gpu' and args.gpu_family:
                config[category]['families'] = [args.gpu_family]
        with catalog_lock(args.catalog):
            catalog = load_catalog(args.catalog)
            if args.command == 'status':
                counts = {}
                for row in catalog['products'].values():
                    key = row['category'] + ':' + row['status']
                    counts[key] = counts.get(key, 0) + 1
                print(json.dumps({'counts': counts, 'discovery': catalog['discovery']}, indent=2))
                return 0
            if args.command == 'add':
                for url in args.url:
                    url = canonical_url(url, product=True)
                    register(catalog, {'sku': mm.extract_product_id(url), 'url': url}, args.categories[0], 'manual_seed')
                atomic_json(args.catalog, catalog)
                return 0
            client = Client(args.delay, args.max_requests)
            report = {'run_id': mm.utc_now().strftime('%Y%m%dT%H%M%S%fZ'), 'command': args.command,
                      'pages': 0, 'accepted': 0, 'review': 0, 'excluded': 0, 'skipped_today': 0,
                      'missing_price': 0, 'remaining_due': 0, 'errors': [], 'scope': config}
            try:
                if args.command == 'discover':
                    discover(catalog, client, args, config, report)
                if not args.links_only:
                    collect(catalog, client, args, config, report)
            except (StopRun, FetchError, mm.ScraperError) as error:
                report['stopped_reason'] = str(error)
            finally:
                report.update(requests=client.requests, finished_at=mm.utc_now().isoformat())
                atomic_json(args.catalog, catalog)
                report_path = args.catalog.parent / 'runs' / (report['run_id'] + '.json')
                atomic_json(report_path, report)
                print(json.dumps(report, ensure_ascii=True, indent=2))
            return 1 if report.get('stopped_reason') or report['errors'] else 0
    except (OSError, ValueError, KeyError, mm.ScraperError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()


if __name__ == '__main__':
    raise SystemExit(main())
