"""Small, bounded SwissHardware catalogue discovery from three category pages.

Discovery records candidates only. It never fetches product pages or writes prices to
PostgreSQL. Select candidates explicitly before adding them to a daily price pipeline.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from backend.retailers.mediamarkt.collector import atomic_json, catalog_lock

ROOT = Path(__file__).resolve().parents[3]
ORIGIN = 'https://swisshw.ch'
CATALOG = ROOT / 'data/catalog/swisshardware.json'
RAW = ROOT / 'data/raw/swisshardware/listings'
CATEGORIES = {
    'gpu': ORIGIN + '/de/collections/carte-graphique',
    'ram': ORIGIN + '/de/collections/ram',
    'ssd': ORIGIN + '/de/collections/ssd',
}
USER_AGENT = 'HSLU-DataEngineering-Project/1.0 (student research)'


def today() -> str:
    return datetime.now(ZoneInfo('Europe/Zurich')).date().isoformat()


def canonical_product_url(href: str) -> str:
    url = urlsplit(urljoin(ORIGIN, href))
    if url.scheme != 'https' or url.netloc != 'swisshw.ch':
        raise ValueError('Product URL must be on swisshw.ch')
    if not re.fullmatch(r'/de/products/[a-z0-9][a-z0-9-]*', url.path):
        raise ValueError('Not a German SwissHardware product URL')
    return urlunsplit(('https', url.netloc, url.path, '', ''))


def parse_listing(html: str) -> list[dict]:
    """Read only real product cards; ignore menus, installment prices and duplicates."""
    soup = BeautifulSoup(html, 'html.parser')
    products = {}
    for card in soup.select('a.pcard[href]'):
        try:
            url = canonical_product_url(card['href'])
        except ValueError:
            continue
        name = card.select_one('.pcard__name')
        price = card.select_one('.pcard__price')
        stock = card.select_one('.pcard__stock-indicator')
        if not name or not name.get_text(strip=True) or not price:
            continue
        listing_price = price.get_text(' ', strip=True)
        try:
            amount = Decimal(listing_price.removeprefix('CHF').strip().replace(',', ''))
        except InvalidOperation:
            continue
        if amount <= 0:
            continue
        products[url] = {
            'url': url,
            'slug': url.rsplit('/', 1)[-1],
            'name': name.get_text(' ', strip=True),
            'listing_price': listing_price,
            'listing_availability': stock.get_text(' ', strip=True) if stock else None,
        }
    return list(products.values())


def listing_pages(html: str, category: str) -> int:
    """Read the last page advertised by this category's own pagination."""
    base = urlsplit(CATEGORIES[category])
    pages = {1}
    for anchor in BeautifulSoup(html, 'html.parser').select('a[href]'):
        link = urlsplit(urljoin(ORIGIN, anchor['href']))
        if (link.scheme, link.netloc, link.path) != (base.scheme, base.netloc, base.path):
            continue
        query = parse_qs(link.query)
        if set(query) != {'page'}:
            continue
        try:
            page = int(query['page'][0])
        except (ValueError, IndexError):
            continue
        if page > 0:
            pages.add(page)
    return max(pages)


def raw_page(raw_dir: Path, category: str, page: int) -> Path:
    return raw_dir / (f'{category}.html' if page == 1 else f'{category}_p{page}.html')


def load_catalog(path: Path) -> dict:
    if not path.exists():
        return {'version': 1, 'source': 'swisshardware', 'products': {}, 'listings': {}}
    catalog = json.loads(path.read_text(encoding='utf-8'))
    if catalog.get('version') != 1 or catalog.get('source') != 'swisshardware' or not isinstance(catalog.get('products'), dict):
        raise ValueError('Unsupported SwissHardware catalog; refusing to overwrite it')
    return catalog


def register_listings(catalog: dict, raw_dir: Path) -> dict:
    """Merge captured listings without changing previous manual selections."""
    report = {'new': 0, 'known': 0, 'by_category': {}}
    for category in CATEGORIES:
        first = raw_page(raw_dir, category, 1)
        if not first.is_file():
            raise FileNotFoundError(f'Missing captured listing: {first}')
        total_pages = listing_pages(first.read_text(encoding='utf-8'), category)
        all_items = {}
        paths = []
        for page in range(1, total_pages + 1):
            path = raw_page(raw_dir, category, page)
            if not path.is_file():
                raise FileNotFoundError(f'Missing page {page} of {total_pages}: {path}')
            paths.append(str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path))
            for item in parse_listing(path.read_text(encoding='utf-8')):
                all_items[item['slug']] = item
        report['by_category'][category] = len(all_items)
        for item in all_items.values():
            key = item['slug']
            previous = catalog['products'].get(key)
            if previous and previous['url'] != item['url']:
                raise ValueError(f'Conflicting URLs for product slug {key}')
            report['known' if previous else 'new'] += 1
            catalog['products'][key] = {
                **(previous or {}), **item, 'category': category,
                'selected': previous.get('selected', False) if previous else False,
                'last_seen_on_listing': raw_dir.name,
            }
        catalog['listings'][category] = {'url': CATEGORIES[category], 'raw_paths': paths,
                                         'captured_on': raw_dir.name, 'visible_products': len(all_items)}
    return report


def capture_listings(raw_dir: Path, delay: float = 3.0, max_pages: int = 10,
                     max_requests: int = 20) -> dict:
    """Fetch each advertised category page at most once per Zurich day."""
    if delay < 3:
        raise ValueError('Delay must be at least 3 seconds')
    if raw_dir.name != today():
        raise ValueError('Live captures must use the current Europe/Zurich date')
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT, 'Accept-Language': 'de-CH,de;q=0.9'})
    try:
        robots_response = session.get(ORIGIN + '/robots.txt', timeout=20, allow_redirects=False)
        robots_response.raise_for_status()
        robots = RobotFileParser()
        robots.parse(robots_response.text.splitlines())
        raw_dir.mkdir(parents=True, exist_ok=True)
        fetched = 0
        for category, url in CATEGORIES.items():
            first = raw_page(raw_dir, category, 1)
            for page in range(1, max_pages + 1):
                path = raw_page(raw_dir, category, page)
                page_url = url if page == 1 else f'{url}?page={page}'
                if not path.exists():
                    if fetched + 1 >= max_requests:
                        raise RuntimeError(f'Request budget of {max_requests} reached')
                    if not robots.can_fetch(USER_AGENT, page_url):
                        raise RuntimeError(f'robots.txt disallows {page_url}')
                    time.sleep(delay)
                    response = session.get(page_url, timeout=25, allow_redirects=False)
                    if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
                        raise RuntimeError(f'Stopped after HTTP {response.status_code} from {page_url}')
                    if not parse_listing(response.text):
                        raise RuntimeError(f'No product cards in {page_url}; saved no data')
                    path.write_bytes(response.content)
                    fetched += 1
                if page == 1:
                    total_pages = listing_pages(first.read_text(encoding='utf-8'), category)
                    if total_pages > max_pages:
                        raise RuntimeError(f'{category} has {total_pages} pages, above the --max-pages limit {max_pages}')
                if page >= total_pages:
                    break
        return {'http_requests': fetched + 1, 'listing_pages': fetched}
    finally:
        session.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['discover', 'list', 'select', 'deselect'])
    parser.add_argument('slugs', nargs='*', help='Product slugs shown by list')
    parser.add_argument('--live', action='store_true', help='Fetch the three category pages once today')
    parser.add_argument('--date', default=today(), help='Use already captured raw listings from this date')
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--delay', type=float, default=3.0)
    parser.add_argument('--max-pages', type=int, default=10, help='Safety limit per category')
    parser.add_argument('--max-requests', type=int, default=20, help='Total HTTP budget, including robots.txt')
    args = parser.parse_args(argv)
    if args.live and args.command != 'discover':
        parser.error('--live is only valid with discover')
    with catalog_lock(args.catalog):
        catalog = load_catalog(args.catalog)
        if args.command == 'discover':
            if args.slugs:
                parser.error('discover does not accept product slugs')
            raw_dir = RAW / args.date
            network = capture_listings(raw_dir, args.delay, args.max_pages, args.max_requests) if args.live else {'http_requests': 0, 'listing_pages': 0}
            report = register_listings(catalog, raw_dir)
            atomic_json(args.catalog, catalog)
            print(json.dumps({**network, **report, 'catalog': str(args.catalog)}, indent=2))
        elif args.command == 'list':
            rows = sorted(catalog['products'].values(), key=lambda x: (x['category'], x['name']))
            for row in rows:
                if not args.slugs or row['category'] in args.slugs or row['slug'] in args.slugs:
                    print(f"{row['category'].upper():3} {'[x]' if row['selected'] else '[ ]'} {row['slug']} | {row['name']} | {row['listing_price'] or '—'} | {row['url']}")
            print(f"{len(rows)} known products; {sum(row['selected'] for row in rows)} selected")
        else:
            if not args.slugs:
                parser.error(f'{args.command} requires one or more product slugs')
            unknown = set(args.slugs) - catalog['products'].keys()
            if unknown:
                parser.error('Unknown product slugs: ' + ', '.join(sorted(unknown)))
            for slug in args.slugs:
                catalog['products'][slug]['selected'] = args.command == 'select'
            atomic_json(args.catalog, catalog)
            print(f"{len(args.slugs)} product(s) {'selected' if args.command == 'select' else 'deselected'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
