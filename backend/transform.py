"""Small MediaMarkt contract: explicit identifiers, CHF amounts and source timestamps."""
import hashlib
import json
from pathlib import Path
from .retailers.mediamarkt import collector as media

ROOT = Path(__file__).resolve().parents[1]

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata

DETAIL_FIELDS = {
    'gpu': ('gpu_model', 'gpu_architecture', 'vram_gb', 'vram_type', 'clock_mhz',
            'boost_clock_mhz', 'pcie_interface', 'tdp_watts', 'cooling_variant'),
    'ram': ('ram_type', 'total_capacity_gb', 'module_count', 'capacity_per_module_gb',
            'speed_mts', 'cas_latency', 'voltage', 'ecc', 'rgb'),
    'ssd': ('capacity_gb', 'interface', 'pcie_generation', 'form_factor', 'nand_type',
            'controller', 'read_speed_mbps', 'write_speed_mbps', 'tbw', 'dram_cache'),
}


class InvalidRecord(ValueError):
    """Keep the original file and report why it cannot be loaded."""


def text(value):
    return str(value).strip() if value is not None and str(value).strip() else None


def mpn_key(value):
    # Retain punctuation and variant suffixes.
    return unicodedata.normalize('NFKC', text(value) or '').upper() or None


def gtin(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{8}|[0-9]{12,14}', value):
        raise InvalidRecord('GTIN must be an 8/12/13/14 digit string')
    total = sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(reversed(value[:-1])))
    if (total + int(value[-1])) % 10 or set(value) == {'0'}:
        raise InvalidRecord('Invalid GTIN check digit')
    return value.zfill(14)


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.utcoffset() is None:
            raise ValueError()
        return result
    except (AttributeError, TypeError, ValueError) as error:
        raise InvalidRecord('Observation timestamp requires an explicit timezone') from error


def money(value):
    try:
        amount = Decimal(str(value))
        if isinstance(value, bool) or not amount.is_finite() or amount <= 0:
            raise ValueError()
        if amount != amount.quantize(Decimal('.01')) or amount >= Decimal('10000000000'):
            raise ValueError()
        return amount
    except (ValueError, InvalidOperation) as error:
        raise InvalidRecord('Price must be positive finite CHF with at most two decimal places') from error


def validate(record, expected_source='mediamarkt'):
    if expected_source != 'mediamarkt' or not isinstance(record, dict):
        raise InvalidRecord('Midterm supports MediaMarkt JSON objects only')
    for key in ('metadata', 'brand', 'product', 'retailer_product', 'price_history', 'raw_payload'):
        if not isinstance(record.get(key), dict):
            raise InvalidRecord(f'{key} must be an object')
    meta, product, prices = record['metadata'], record['product'], record['price_history']
    if meta.get('source') != 'mediamarkt' or meta.get('access_method') != 'public_html':
        raise InvalidRecord('Source must be a documented MediaMarkt public HTML observation')
    if meta.get('is_example') or meta.get('is_test'):
        raise InvalidRecord('Example/test data is not a production observation')
    if meta.get('scope_status') != 'accepted' or meta.get('quality_warnings'):
        raise InvalidRecord('Scope/quality rejected: ' + str(meta.get('scope_reason') or meta.get('quality_warnings') or 'unconfirmed'))
    category = meta.get('category_code')
    if category not in DETAIL_FIELDS:
        raise InvalidRecord('Unsupported category')
    brand, sku, name = text(record['brand'].get('name')), text(meta.get('source_product_id')), text(product.get('product_name'))
    if not all((brand, sku, name, text(meta.get('source_url')))):
        raise InvalidRecord('Manufacturer, SKU, name and source URL are required')
    if text(record['retailer_product'].get('retailer_sku')) != sku:
        raise InvalidRecord('Source SKU and listing SKU disagree')
    observed = timestamp(meta.get('collected_at'))
    if prices.get('collected_at') and timestamp(prices['collected_at']) != observed:
        raise InvalidRecord('Conflicting observation timestamps')
    offer = record['raw_payload'].get('offers')
    if isinstance(offer, list):
        offer = offer[0] if offer else None
    if not isinstance(offer, dict) or offer.get('priceCurrency') != 'CHF':
        raise InvalidRecord('Original offer must explicitly contain CHF')
    price = money(prices.get('price_chf'))
    if money(offer.get('price')) != price:
        raise InvalidRecord('Transformed price differs from original offer')
    if prices.get('currency', 'CHF') != 'CHF':
        raise InvalidRecord('Only CHF is supported')
    original = money(prices['original_price_chf']) if prices.get('original_price_chf') is not None else None
    if original is not None and original < price:
        raise InvalidRecord('Reference price is below observed price')
    details = record.get(category + '_details') or {}
    if not isinstance(details, dict):
        raise InvalidRecord('Category details must be an object')
    details = {k: details.get(k) for k in DETAIL_FIELDS[category]}
    booleans = {'ecc', 'rgb', 'dram_cache'}
    integers = {'vram_gb', 'clock_mhz', 'boost_clock_mhz', 'tdp_watts', 'total_capacity_gb',
                'module_count', 'capacity_per_module_gb', 'speed_mts', 'capacity_gb',
                'read_speed_mbps', 'write_speed_mbps', 'tbw'}
    for key, value in details.items():
        if value is None:
            continue
        if key in booleans and type(value) is not bool:
            raise InvalidRecord(f'{key}: expected boolean')
        if key in integers and (type(value) is not int or value < (0 if key == 'tbw' else 1)):
            raise InvalidRecord(f'{key}: invalid integer')
        if key == 'voltage':
            details[key] = money(value)
        elif key not in booleans | integers and not isinstance(value, str):
            raise InvalidRecord(f'{key}: expected text')
    if category == 'ram':
        total, count, per = (details[k] for k in ('total_capacity_gb', 'module_count', 'capacity_per_module_gb'))
        if all(v is not None for v in (total, count, per)) and total != count * per:
            raise InvalidRecord('RAM kit capacity conflict')
    seller = offer.get('seller')
    seller_name = text(seller.get('name')) if isinstance(seller, dict) else None
    return dict(brand=brand, sku=sku, name=name, category=category, ean=gtin(product.get('ean')),
                mpn=mpn_key(product.get('mpn')), details=details, observed=observed, price=price,
                original=original, availability=text(prices.get('availability')), seller_name=seller_name,
                source_url=meta['source_url'])


def restore_legacy(record):
    """Reparse an identical Product payload; never fetch replacement evidence."""
    meta = record['metadata']
    if meta.get('parser_version'):
        return record, None
    if meta.get('source') != 'mediamarkt' or meta.get('access_method') != 'public_html':
        raise InvalidRecord('Legacy source is not documented public HTML')
    if meta.get('scope_status') == 'excluded':
        raise InvalidRecord('Scope excluded: ' + str(meta.get('scope_reason')))
    sku = str(meta['source_product_id'])
    candidates = sorted((ROOT / 'data/debug/mediamarkt').glob(sku + '_*.html'))
    candidates.append(ROOT / 'data/debug/mediamarkt_product.html')
    mm = media
    for path in candidates:
        if not path.is_file():
            continue
        # Timestamped captures must belong to the same original collection event.
        if path.parent.name == 'mediamarkt':
            from datetime import datetime, timezone
            captured = datetime.strptime(path.stem.split('_', 1)[1], '%Y%m%dT%H%M%S%fZ').replace(tzinfo=timezone.utc)
            if abs((timestamp(meta['collected_at']) - captured).total_seconds()) > 2:
                continue
        try:
            parsed = mm.mm.parse_html(path.read_text(encoding='utf-8'), meta['source_url'], 'public_html')
        except mm.mm.ScraperError:
            continue
        if parsed['raw_payload'] != record.get('raw_payload'):
            continue
        config = json.loads((ROOT / 'backend/retailers/mediamarkt/scope.json').read_text())
        category = parsed['metadata'].get('category_code')
        if category not in config:
            raise InvalidRecord('Category could not be confirmed from saved HTML')
        # Preserve the interpretation under which historical raw was captured.
        # The new brand scope governs new collection and DAILY membership only.
        config[category]['brands'] = []
        status, reason = mm.scope_decision(parsed, category, config[category])
        parsed['metadata'].update(collected_at=meta['collected_at'], scope_status=status, scope_reason=reason)
        parsed['price_history']['collected_at'] = meta['collected_at']
        return parsed, str(path.relative_to(ROOT))
    raise InvalidRecord('No matching saved HTML for legacy raw record')


def transform_file(path):
    path = Path(path)
    content = path.read_bytes()
    item = {'path': str(path), 'sha256': hashlib.sha256(content).hexdigest()}
    try:
        record = json.loads(content)
        if not isinstance(record, dict) or not isinstance(record.get('metadata'), dict):
            raise InvalidRecord('Raw record and metadata must be objects')
        if record['metadata'].get('is_test') or record['metadata'].get('is_example'):
            raise InvalidRecord('Example/test data is not a production observation')
        record, evidence = restore_legacy(record)
        item.update(observation=validate(record), evidence=evidence)
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        item['rejection'] = str(error)
    return item


def transform_directory(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f'Raw directory does not exist: {directory}')
    return [transform_file(path) for path in sorted(directory.rglob('*.json'))]
