from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "mediamarkt"
DEBUG_HTML = PROJECT_ROOT / "data" / "debug" / "mediamarkt_product.html"

USER_AGENT = "HSLU-DataEngineering-Project/1.0"
TIMEOUT_SECONDS = 20
PRODUCT_URL = (
    "https://www.mediamarkt.ch/de/product/"
    "_asus-prime-geforce-rtx-5070-12gb-gddr7-"
    "nvidia-grafikkarte-2277751.html"
)


class ScraperError(RuntimeError):
    """Expected scraper failure that can be shown without a traceback."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-CH,de;q=0.9,en;q=0.7",
        }
    )
    return session








def load_jsonld_documents(soup: BeautifulSoup) -> Iterator[Any]:
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.string or script.get_text()
        if not text or not text.strip():
            continue
        try:
            yield json.loads(text)
        except (json.JSONDecodeError, TypeError) as error:
            print(f"Warning: skipped invalid JSON-LD block: {error}", file=sys.stderr)


def walk_json(value: Any) -> Iterator[Any]:
    """Depth-first traversal through every JSON object and array."""
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def has_schema_type(value: dict[str, Any], expected: str) -> bool:
    schema_type = value.get("@type")
    if isinstance(schema_type, str):
        return schema_type == expected
    if isinstance(schema_type, list):
        return expected in schema_type
    return False


def find_product_jsonld(soup: BeautifulSoup, product_id: str | None = None) -> dict[str, Any] | None:
    """Find Product anywhere, including BuyAction.object and @graph nodes."""
    for document in load_jsonld_documents(soup):
        for candidate in walk_json(document):
            if isinstance(candidate, dict) and has_schema_type(candidate, "Product"):
                if product_id is None or str(candidate.get("sku")) == product_id:
                    return candidate
    return None


def load_preloaded_apollo_state(soup: BeautifulSoup) -> dict[str, Any]:
    """Load MediaMarkt's embedded Apollo cache without executing JavaScript."""
    prefix = "window.__PRELOADED_STATE__"
    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        if not text or prefix not in text:
            continue

        _, separator, payload = text.partition("=")
        if not separator:
            continue

        # MediaMarkt emits JavaScript `undefined` values. They occur as object
        # values and are the only non-JSON tokens in the currently observed
        # state. Replacing only value positions avoids changing quoted text.
        payload = payload.strip().rstrip(";")
        # Match quoted strings first so literal ':undefined,' in descriptions
        # stays intact. Never evaluate the embedded JavaScript.
        payload = re.sub(r'"(?:\\.|[^"\\])*"|\bundefined\b',
                         lambda match: "null" if match[0] == "undefined" else match[0], payload)
        try:
            state = json.loads(payload)
        except json.JSONDecodeError as error:
            print(f"Warning: could not parse __PRELOADED_STATE__: {error}", file=sys.stderr)
            return {}

        apollo_state = state.get("apolloState") if isinstance(state, dict) else None
        return apollo_state if isinstance(apollo_state, dict) else {}
    return {}


def find_apollo_product(
    apollo_state: dict[str, Any], product_id: str | None
) -> dict[str, Any] | None:
    """Select exactly the requested product, never a recommendation."""
    if product_id is None:
        return None
    matches = [
        value
        for value in apollo_state.values()
        if isinstance(value, dict)
        and value.get("__typename") == "GraphqlProduct"
        and str(value.get("id")) == product_id
    ]
    detailed_matches = [
        value
        for value in matches
        if isinstance(value.get("featureGroupsWithProductId"), dict)
    ]
    if len(detailed_matches) > 1:
        print(
            f"Warning: multiple detailed Apollo products matched ID {product_id}; using the richest.",
            file=sys.stderr,
        )
    candidates = detailed_matches or matches
    return max(candidates, key=len) if candidates else None


def resolve_product_features(
    apollo_state: dict[str, Any], product: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Resolve only feature references owned by the selected product."""
    if not product:
        return []
    feature_group_ref = product.get("featureGroupsWithProductId")
    if not isinstance(feature_group_ref, dict):
        return []
    group_key = feature_group_ref.get("__ref")
    groups = apollo_state.get(group_key) if isinstance(group_key, str) else None
    if not isinstance(groups, dict):
        return []
    if str(groups.get("productId")) != str(product.get("id")):
        return []

    resolved: list[dict[str, Any]] = []
    for group in groups.get("featureGroups", []):
        if not isinstance(group, dict):
            continue
        for reference in group.get("features", []):
            if not isinstance(reference, dict):
                continue
            key = reference.get("__ref")
            feature = apollo_state.get(key) if isinstance(key, str) else None
            if isinstance(feature, dict) and feature.get("__typename") == "GraphqlProductFeature":
                resolved.append(feature)
    return resolved


def normalize_label(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def feature_value(
    features: list[dict[str, Any]],
    *,
    feature_ids: tuple[str, ...] = (),
    names: tuple[str, ...] = (),
) -> Any:
    """Prefer stable feature IDs and use normalized names as a fallback."""
    normalized_names = {normalize_label(name) for name in names}
    for feature in features:
        if feature.get("featureId") in feature_ids:
            return feature.get("value")
    for feature in features:
        if normalize_label(feature.get("name")) in normalized_names:
            return feature.get("value")
    return None


def positive_int(value: Any) -> int | None:
    number = normalize_decimal(value)
    if number is None or number <= 0 or number != number.to_integral_value():
        return None
    return int(number)


def nullable_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    normalized = normalize_label(value)
    if normalized in {"ja", "yes", "true", "vorhanden", "unterstutzt"}:
        return True
    if normalized in {"nein", "no", "false", "nichtvorhanden", "nichtunterstutzt"}:
        return False
    return None


def last_breadcrumb_name(product: dict[str, Any] | None) -> str | None:
    if not product:
        return None
    breadcrumbs = product.get("breadcrumbs")
    if not isinstance(breadcrumbs, list):
        return None
    for breadcrumb in reversed(breadcrumbs):
        if isinstance(breadcrumb, dict) and isinstance(breadcrumb.get("name"), str):
            name = breadcrumb["name"].strip()
            if name:
                return name
    return None


def extract_architecture(
    product: dict[str, Any] | None, features: list[dict[str, Any]]
) -> str | None:
    texts = [str(feature.get("value") or "") for feature in features]
    if product:
        texts.append(str(product.get("description") or ""))
    joined = " ".join(texts)
    if re.search(r"\bNVIDIA\s+Blackwell\b|\bBlackwell\s+Architektur\b", joined, re.IGNORECASE):
        return "NVIDIA Blackwell"
    return None


def is_gpu_product(product: dict[str, Any] | None, category: str | None) -> bool:
    kind = normalize_label(product.get("kindOfProduct")) if product else ""
    label = normalize_label(category)
    return kind == "graphicscard" or "grafikkart" in label or "graphicscard" in label


def is_ram_product(product: dict[str, Any] | None, category: str | None) -> bool:
    kind = normalize_label(product.get("kindOfProduct")) if product else ""
    label = normalize_label(category)
    return kind in {"memory", "ram"} or "arbeitsspeicher" in label or label == "ram"


def is_ssd_product(product: dict[str, Any] | None, category: str | None) -> bool:
    kind = normalize_label(product.get("kindOfProduct")) if product else ""
    label = normalize_label(category)
    return kind in {"ssd", "solidstatedrive"} or "ssd" in label or "solidstate" in label


def normalize_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = re.sub(r"(?i)CHF", "", text).replace("'", "").replace("’", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return result if result.is_finite() and result >= 0 else None


def json_number(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    return int(value) if value == value.to_integral_value() else float(value)


def first_offer(product: dict[str, Any]) -> dict[str, Any]:
    offers = product.get("offers")
    if isinstance(offers, dict):
        return offers
    if isinstance(offers, list):
        return next((item for item in offers if isinstance(item, dict)), {})
    return {}


def is_chf(value: Any) -> bool:
    return isinstance(value, str) and value.strip().upper() == "CHF"


def extract_original_price(offer: dict[str, Any]) -> Decimal | None:
    specifications = offer.get("priceSpecification")
    if isinstance(specifications, dict):
        specifications = [specifications]
    if not isinstance(specifications, list):
        return None

    for specification in specifications:
        if not isinstance(specification, dict):
            continue
        price_type = specification.get("priceType")
        if isinstance(price_type, str) and price_type.rstrip("/").rsplit("/", 1)[-1] == "StrikethroughPrice":
            if not is_chf(specification.get("priceCurrency")):
                return None
            return normalize_decimal(specification.get("price"))
    return None


def extract_brand(product: dict[str, Any]) -> str | None:
    brand = product.get("brand")
    if isinstance(brand, dict):
        name = brand.get("name")
        return str(name).strip() if name is not None and str(name).strip() else None
    return brand.strip() if isinstance(brand, str) and brand.strip() else None


def extract_availability(offer: dict[str, Any]) -> str | None:
    value = offer.get("availability")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.rstrip("/").rsplit("/", 1)[-1]


def extract_product_id(url: str) -> str | None:
    match = re.search(r"-(\d+)\.html(?:[?#].*)?$", url)
    return match.group(1) if match else None


def discount_percent(price: Decimal | None, original: Decimal | None) -> Decimal | None:
    if price is None or original is None or original <= 0 or price > original:
        return None
    return ((original - price) / original * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def create_record(
    product: dict[str, Any],
    url: str,
    access_method: str,
    technical_product: dict[str, Any] | None = None,
    features: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    features = features or []
    collected_at = utc_now().isoformat()
    offer = first_offer(product)
    currency = offer.get("priceCurrency")
    price = normalize_decimal(offer.get("price")) if is_chf(currency) else None
    original = extract_original_price(offer)
    discount = discount_percent(price, original)
    sku_value = product.get("sku") or extract_product_id(url)
    sku = str(sku_value).strip() if sku_value is not None and str(sku_value).strip() else None
    name_value = product.get("name")
    name = str(name_value).strip() if name_value is not None and str(name_value).strip() else None
    ean_value = product.get("gtin13") or product.get("gtin")
    ean = str(ean_value).strip() if ean_value is not None and str(ean_value).strip() else None

    category_name = last_breadcrumb_name(technical_product)
    mpn = feature_value(
        features,
        feature_ids=("PROD_FEAT_00002",),
        names=("Manufacturer Part Number (MPN)", "Hersteller Artikelnummer", "MPN"),
    )
    series = feature_value(
        features,
        feature_ids=("PROD_FEAT_16042",),
        names=("Serie", "Produktserie"),
    )
    architecture = extract_architecture(technical_product, features)
    model = technical_product.get("rawTitle") if technical_product else None
    # Retailer publication time is not the hardware's release date.
    release_date = feature_value(features, names=("Produkt Einführungsdatum", "Release Date"))
    try:
        release_date = datetime.strptime(str(release_date), "%Y-%m-%d").date().isoformat()
    except ValueError:
        release_date = None
    manufacturer_url = None
    if technical_product:
        legal_contact = technical_product.get("manufacturerLegalContact")
        if isinstance(legal_contact, dict):
            manufacturer_url = legal_contact.get("websiteUrl")

    gpu_values = {
        "gpu_model": None,
        "gpu_architecture": None,
        "vram_gb": None,
        "vram_type": None,
        "clock_mhz": None,
        "boost_clock_mhz": None,
        "pcie_interface": None,
        "tdp_watts": None,
        "cooling_variant": None,
    }
    if is_gpu_product(technical_product, category_name):
        gpu_values.update(
            {
                "gpu_model": feature_value(
                    features,
                    feature_ids=("PROD_FEAT_16856",),
                    names=("Graphics Chipset", "Grafikchipsatz", "GPU-Modell"),
                ),
                "gpu_architecture": architecture,
                "vram_gb": positive_int(
                    feature_value(
                        features,
                        feature_ids=("PROD_FEAT_13488",),
                        names=("Grafikspeicher", "Videospeicher", "VRAM"),
                    )
                ),
                "vram_type": feature_value(
                    features,
                    feature_ids=("PROD_FEAT_16165",),
                    names=("Grafikspeicher-Typ", "Videospeichertyp", "VRAM-Typ"),
                ),
                # MediaMarkt's GPU clock feature is the advertised maximum/OC
                # clock for this card. A base clock is not provided.
                "boost_clock_mhz": positive_int(
                    feature_value(
                        features,
                        feature_ids=("PROD_FEAT_15000",),
                        names=("Grafik-Taktfrequenz", "Boost-Takt", "Boost Clock"),
                    )
                ),
                "pcie_interface": feature_value(
                    features,
                    feature_ids=("PROD_FEAT_12111",),
                    names=("Steckplatz", "PCIe-Schnittstelle", "PCI Express"),
                ),
                # Deliberately excludes "Empfohlene Spannungsversorgung":
                # recommended PSU wattage is not GPU TDP.
                "tdp_watts": positive_int(
                    feature_value(features, names=("TDP", "Leistungsaufnahme GPU"))
                ),
                "cooling_variant": feature_value(
                    features,
                    feature_ids=("PROD_FEAT_15551",),
                    names=("Kühlung", "Kühlungsart", "Cooling"),
                ),
            }
        )

    ram_values = {
        "ram_type": None,
        "total_capacity_gb": None,
        "module_count": None,
        "capacity_per_module_gb": None,
        "speed_mts": None,
        "cas_latency": None,
        "voltage": None,
        "ecc": None,
        "rgb": None,
    }
    if is_ram_product(technical_product, category_name):
        ram_values.update(
            {
                "ram_type": feature_value(
                    features,
                    names=("Arbeitsspeichertyp", "RAM-Typ", "Speichertyp"),
                ),
                "total_capacity_gb": positive_int(
                    feature_value(
                        features,
                        names=("Gesamtspeicherkapazität", "Speicherkapazität", "Arbeitsspeicher"),
                    )
                ),
                "module_count": positive_int(
                    feature_value(features, names=("Anzahl Speichermodule", "Anzahl Module"))
                ),
                "capacity_per_module_gb": positive_int(
                    feature_value(features, names=("Kapazität pro Modul", "Speicher pro Modul"))
                ),
                "speed_mts": positive_int(
                    feature_value(
                        features,
                        names=("Speichergeschwindigkeit", "Datenübertragungsrate", "RAM-Geschwindigkeit"),
                    )
                ),
                "cas_latency": feature_value(
                    features, names=("CAS Latency", "CAS-Latenz", "Latenzzeit")
                ),
                "voltage": json_number(
                    normalize_decimal(feature_value(features, names=("Spannung", "Betriebsspannung")))
                ),
                "ecc": nullable_bool(feature_value(features, names=("ECC", "ECC-Unterstützung"))),
                "rgb": nullable_bool(feature_value(features, names=("RGB", "RGB-Beleuchtung"))),
            }
        )

    ssd_values = {
        "capacity_gb": None,
        "interface": None,
        "pcie_generation": None,
        "form_factor": None,
        "nand_type": None,
        "controller": None,
        "read_speed_mbps": None,
        "write_speed_mbps": None,
        "tbw": None,
        "dram_cache": None,
    }
    if is_ssd_product(technical_product, category_name):
        ssd_values.update(
            {
                "capacity_gb": positive_int(
                    feature_value(features, names=("Speicherkapazität", "Kapazität", "SSD-Kapazität"))
                ),
                "interface": feature_value(
                    features, names=("Schnittstelle", "SSD-Schnittstelle", "Anschluss")
                ),
                "pcie_generation": feature_value(
                    features, names=("PCIe Generation", "PCI-Express-Version", "PCIe-Version")
                ),
                "form_factor": feature_value(
                    features, names=("Formfaktor", "Bauform", "SSD-Formfaktor")
                ),
                "nand_type": feature_value(
                    features, names=("NAND-Typ", "Flash-Speichertyp", "Speichertechnologie")
                ),
                "controller": feature_value(features, names=("Controller", "SSD-Controller")),
                "read_speed_mbps": positive_int(
                    feature_value(
                        features,
                        names=("Lesegeschwindigkeit", "Maximale Lesegeschwindigkeit"),
                    )
                ),
                "write_speed_mbps": positive_int(
                    feature_value(
                        features,
                        names=("Schreibgeschwindigkeit", "Maximale Schreibgeschwindigkeit"),
                    )
                ),
                "tbw": positive_int(
                    feature_value(features, names=("TBW", "Total Bytes Written"))
                ),
                "dram_cache": nullable_bool(
                    feature_value(features, names=("DRAM-Cache", "DRAM Cache"))
                ),
            }
        )

    return {
        "metadata": {
            "source": "mediamarkt",
            "source_type": "retailer",
            "source_product_id": sku,
            "source_url": url,
            "access_method": access_method,
            "collected_at": collected_at,
        },
        "brand": {"brand_id": None, "name": extract_brand(product)},
        "category": {"category_id": None, "name": category_name},
        "retailer": {"retailer_id": None, "name": "MediaMarkt", "website": "https://www.mediamarkt.ch"},
        "product": {
            "product_id": None, "brand_id": None, "category_id": None,
            "product_name": name, "ean": ean, "mpn": mpn or product.get("mpn"),
            "release_date": release_date, "model": model or product.get("model"), "series": series,
            "generation": architecture, "msrp_chf": None, "manufacturer_url": manufacturer_url,
            "created_at": None, "updated_at": None,
        },
        "retailer_product": {
            "retailer_product_id": None, "product_id": None, "retailer_id": None,
            "retailer_sku": sku, "retailer_product_name": name,
            "product_url": product.get("url") or url, "first_seen_at": None, "last_seen_at": None,
        },
        "price_history": {
            "price_id": None, "retailer_product_id": None,
            "price_chf": json_number(price), "original_price_chf": json_number(original),
            "discount_percent": json_number(discount), "availability": extract_availability(offer),
            "collected_at": collected_at,
        },
        "gpu_details": {
            "gpu_details_id": None, "product_id": None, **gpu_values,
        },
        "ram_details": {
            "ram_details_id": None, "product_id": None, **ram_values,
        },
        "ssd_details": {
            "ssd_details_id": None, "product_id": None, **ssd_values,
        },
        # Exact parsed Product object: no normalization or additions inside the payload.
        "raw_payload": product,
    }


def measured_feature(features, names, units, *, integer=True):
    """Convert only explicitly labelled units; never read 1 TB as 1 GB."""
    labels = {normalize_label(name) for name in names}
    for feature in features:
        if normalize_label(feature.get("name")) not in labels:
            continue
        text = str(feature.get("value") or "").strip()
        match = re.fullmatch(r"([\d.,'’\s]+)\s*([A-Za-z/]+)?", text)
        if not match:
            continue
        unit = (match[2] or feature.get("unit") or "").strip().casefold()
        numeric_text = match[1].strip()
        if unit in {"mb/s", "mhz", "mt/s"} and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", numeric_text):
            numeric_text = numeric_text.replace('.', '')
        number = normalize_decimal(numeric_text)
        if number is None or number <= 0 or unit not in units:
            continue
        value = number * Decimal(str(units[unit]))
        if integer and value != value.to_integral_value():
            continue
        return int(value) if integer else json_number(value)
    return None


def enrich_verified_features(record, technical, features):
    """Mappings verified against saved GPU, RAM and SSD product pages."""
    technical = technical or {}
    get = lambda *names: feature_value(features, names=names)
    capacity_units = {"gb": 1, "tb": 1000, "mb": .001}
    identity = " ".join(str(technical.get(key) or "") for key in ("title", "rawTitle", "kindOfProduct"))
    product_type = str(get("Produkttyp", "Festplattentyp") or "")
    category = record["category"]["name"]
    gpu = is_gpu_product(technical, category)
    ram = is_ram_product(technical, category)
    ssd = is_ssd_product(technical, category) or (
        technical.get("kindOfProduct") == "HARD_DISK_INTERNAL"
        and re.search(r"\bSSD\b|Solid State", product_type, re.I) is not None
    )
    code = "gpu" if gpu else "ram" if ram else "ssd" if ssd else None
    metadata = record["metadata"]
    metadata["category_code"] = code
    metadata["quality_warnings"] = []
    if not record['brand']['name']:
        record['brand']['name'] = technical.get('manufacturer')
    if not record['product']['ean']:
        record['product']['ean'] = technical.get('ean')
    ean = record['product']['ean']
    if ean and (not re.fullmatch(r'\d{13}', str(ean)) or
                (sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(str(ean)[:12])) + int(str(ean)[12])) % 10):
        metadata['quality_warnings'].append('invalid_gtin13')
    # Separate from the untouched Product JSON-LD; retain source evidence.
    record["technical_payload"] = {
        "product_id": technical.get("id"), "kind_of_product": technical.get("kindOfProduct"),
        "raw_title": technical.get("rawTitle"), "features": features,
        "breadcrumbs": technical.get("breadcrumbs"),
    }
    if ram:
        details = record["ram_details"]
        details["ram_type"] = get("Arbeitsspeicher-Typ", "Arbeitsspeichertyp", "RAM-Typ")
        details["total_capacity_gb"] = measured_feature(features,
            ("Arbeitsspeicher-Größe", "Gesamtspeicherkapazität", "Speicherkapazität"), capacity_units)
        details["capacity_per_module_gb"] = measured_feature(features,
            ("Kapazität pro Modul", "Speicher pro Modul"), capacity_units)
        details["speed_mts"] = measured_feature(features,
            ("Speichergeschwindigkeit", "Datenübertragungsrate", "RAM-Geschwindigkeit"), {"mt/s": 1})
        # Vendors label effective DDR rates as MHz. Accept only when the same
        # rate is explicitly present in a DDR product's model designation.
        clock = measured_feature(features, ("Taktfrequenz",), {"mhz": 1})
        if details["speed_mts"] is None and clock and details["ram_type"] in {"DDR4", "DDR5"}:
            if re.search(rf"(?<!\d){clock}(?!\d)", identity):
                details["speed_mts"] = clock
                metadata["ram_speed_normalization"] = "Vendor effective DDR rate labelled MHz; confirmed in model name"
        details["voltage"] = measured_feature(features, ("Spannung", "Betriebsspannung"), {"v": 1}, integer=False)
        details["cas_latency"] = get("CAS Latency (CL)", "CAS Latency", "CAS-Latenz")
        modules = str(get("Modulanzahl", "Anzahl Speichermodule", "Anzahl Module") or "")
        match = re.fullmatch(r"\s*(\d+)\s*[x×]\s*(\d+)\s*GB\s*", modules, re.I)
        if match:
            count, size = map(int, match.groups())
            if count > 0 and size > 0 and details["total_capacity_gb"] in (None, count * size):
                details.update(module_count=count, capacity_per_module_gb=size, total_capacity_gb=count * size)
            else:
                metadata["quality_warnings"].append("ram_capacity_conflict")
        elif modules.isdigit() and int(modules) > 0:
            details["module_count"] = int(modules)
        record["product"]["generation"] = details["ram_type"]
    if ssd:
        details = record["ssd_details"]
        details["capacity_gb"] = measured_feature(features, ("Speicherkapazität", "Kapazität", "SSD-Kapazität"), capacity_units)
        details["interface"] = get("Festplattenschnittstelle", "Schnittstelle", "SSD-Schnittstelle")
        details["form_factor"] = get("Passende Festplattengrösse", "Passende Festplattengröße", "Formfaktor", "SSD-Formfaktor")
        details["read_speed_mbps"] = measured_feature(features, ("Transferrate (lesen)", "Lesegeschwindigkeit", "Maximale Lesegeschwindigkeit"), {"mb/s": 1, "gb/s": 1000})
        details["write_speed_mbps"] = measured_feature(features, ("Transferrate (schreiben)", "Schreibgeschwindigkeit", "Maximale Schreibgeschwindigkeit"), {"mb/s": 1, "gb/s": 1000})
        details["tbw"] = measured_feature(features, ("TBW-Bewertung", "TBW", "Total Bytes Written"), {"tb": 1})
        interface_evidence = " ".join([identity, str(get("Übertragungsrate") or ""), str(get("Anschlüsse") or "")]).replace('®', '').replace('™', '')
        if re.search(r"\bSATA\b", str(details["interface"]), re.I) and re.search(r"NVMe", interface_evidence, re.I):
            metadata["quality_warnings"].append("ssd_interface_conflict")
            details["interface"] = None
        elif details["interface"] is None and re.search(r"NVMe", interface_evidence, re.I):
            details["interface"] = "NVMe"
        generation = re.search(r"PCI(?:e|\s*Express)\s*(?:Gen\s*)?([345])(?:[.,]0)?\b", interface_evidence, re.I)
        if not generation and re.search(r"PCI(?:e|\s*Express)", interface_evidence, re.I):
            generation = re.search(r"\bGen\s*([345])\b", interface_evidence, re.I)
        details["pcie_generation"] = generation[1] + ".0" if generation else None
        record["product"]["generation"] = "PCIe " + details["pcie_generation"] if generation else None
        special = str(get("Besondere Merkmale") or "")
        factor = re.search(r"Formfaktor:\s*(M\.2\s*\(\d{4}\))", special, re.I)
        if details['form_factor'] is None and factor:
            details['form_factor'] = factor[1]
        nand = re.search(r"([^,;]*NAND[^,;]*)\s*\(Speicher\)", special, re.I)
        if details['nand_type'] is None and nand:
            details['nand_type'] = nand[1].strip()
        controller = re.search(r"([^,;]*eigener Controller)", special, re.I)
        if details['controller'] is None and controller:
            details['controller'] = controller[1].strip()
        if details['dram_cache'] is None and re.search(r"\b(?:SDRAM|DRAM)\b[^,;]*\(Cache-Arbeitsspeicher\)", special, re.I):
            details['dram_cache'] = True
    if gpu:
        # The generic 'Grafik-Taktfrequenz' is ambiguous. Use explicit labels
        # or a clearly stated Boost clock, preserving OC information in features.
        details = record["gpu_details"]
        details["clock_mhz"] = measured_feature(features, ("Basistakt", "Base Clock"), {"mhz": 1, "ghz": 1000})
        details["boost_clock_mhz"] = measured_feature(features, ("Boost-Takt", "Boost Clock"), {"mhz": 1, "ghz": 1000})
        special = str(get("Besondere Merkmale") or "")
        boost = re.search(r"(\d+)\s*MHz\s*\(Boost-Takt\)", special, re.I)
        if boost and details["boost_clock_mhz"] is None:
            details["boost_clock_mhz"] = int(boost[1])
        details["tdp_watts"] = measured_feature(features, ("TDP", "Leistungsaufnahme GPU"), {"w": 1})
        details["vram_gb"] = measured_feature(features, ("Grafikspeicher", "Videospeicher", "VRAM"), capacity_units)
        gpu_name = str(details["gpu_model"] or identity).replace("™", "")
        family = re.search(r"\b(RTX|RX)\s*(\d{4})\b", gpu_name, re.I)
        if family:
            model = int(family[2])
            record["product"]["generation"] = (f"RTX {model // 100} Series" if family[1].upper() == "RTX" else f"RX {model // 1000}000 Series")
    metadata["item_condition"] = first_offer(record["raw_payload"]).get("itemCondition")




def parse_html(html: str, url: str, access_method: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    product = find_product_jsonld(soup, extract_product_id(url))
    if product is None:
        raise ScraperError("No Product JSON-LD found in the HTML.")

    product_id_value = product.get("sku") or extract_product_id(url)
    product_id = str(product_id_value).strip() if product_id_value is not None else None
    apollo_state = load_preloaded_apollo_state(soup)
    technical_product = find_apollo_product(apollo_state, product_id)
    features = resolve_product_features(apollo_state, technical_product)
    if technical_product:
        print(f"Technical product data found for SKU {product_id} ({len(features)} features).")
    else:
        print(
            f"Warning: no matching technical product data found for SKU {product_id}.",
            file=sys.stderr,
        )
    record = create_record(
        product,
        url,
        access_method,
        technical_product=technical_product,
        features=features,
    )
    enrich_verified_features(record, technical_product, features)
    record['metadata'].update(schema_version=1, parser_version='mediamarkt-1.0',
                              observation_type='daily_scrape')
    record['source_document'] = {'sha256': hashlib.sha256(html.encode('utf-8')).hexdigest(),
                                 'content_utf8': html}
    record['provenance'] = {'parser_version': 'mediamarkt-1.0', 'format': 'public_product_html'}
    return record








