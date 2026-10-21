# MediaMarkt retailer adapter

The active files are `backend/retailers/mediamarkt/collector.py`, `parser.py`, and `scope.json`. Use the central [backend flow](../backend/flow.py) CLI; runnable commands are in the [runbook](RUN_COMMANDS.md).

## Product pages and parsing

The adapter reads public German-language product pages at `https://www.mediamarkt.ch/de/product/...-<SKU>.html`. `Client.get_html()` checks the domain, SKU, robots.txt, redirects, and HTML content type. `Client.request()` uses a 20-second timeout for socket inactivity, no automatic retry, and at least a three-second delay or the longer robots.txt interval. HTTP 401/403/429/503 stops the batch. Host sleep can interrupt a request for much longer; the [daily audit](evidence/phase5_2/audit.md) documents an earlier case, and the [midterm audit](MIDTERM_AUDIT.md) covers 21 October.

`parser.parse_html()` selects the Product JSON-LD that matches the URL SKU, including nested Product objects. Recommendations with a different SKU are ignored. Price, CHF currency, and seller come from the selected JSON-LD offer. Specifications come from the embedded Apollo state for that same product, without executing JavaScript or calling private APIs. Category and details require source evidence; a title alone cannot justify an uncertain variant match.

`scope_decision()` additionally requires:

- **GPU:** AMD or MSI board brands, or ASUS with a confirmed ROG line; confirmed GeForce RTX 3000+ or Radeon RX 6000+. An AMD chip in another board brand is insufficient; ASUS Prime/Dual/TUF is outside the chosen ROG scope.
- **RAM:** G.Skill, Kingston, or Corsair; confirmed DDR4/DDR5 desktop DIMM, 8–64 GB. SO-DIMM and server/ECC memory are excluded.
- **SSD:** Samsung, Western Digital, or Kingston; internal NVMe, confirmed PCIe 3.0/4.0/5.0, 256–4000 GB.
- **Condition:** New. Missing or conflicting evidence is reviewed; clearly unsupported hardware is excluded.

Transformation checks identity, prices, timestamps, and technical fields again. A collector-level acceptance does not prove a successful PostgreSQL import. Retailer platform and actual seller remain separate; an unknown seller stays unknown.

## URLs, discovery, and pagination

The parser is not limited to one URL; its fixed GPU example is a test fixture. Normal INITIAL uses the manual selection or candidates in `data/catalog/mediamarkt.json`; DAILY uses URLs from PostgreSQL. `discover()` reads product links and IDs from category pages. `listing()` checks completeness and the last page. Pagination uses `?page=N`, a saved cursor, and page signatures to detect repeated pages.

Six retained listing captures from 15 October cover two pages per category and yielded 24 distinct URLs in each category. Their advertised page counts (GPU 20, RAM 25, SSD 4) are historical source values, not a guarantee of current catalog size or successfully importable products. There has been no large category crawl for this project.

## INITIAL and DAILY

`select_initial()` registers only selected URLs; it does not fetch every discovered candidate. The manual selection contains two GPUs, three RAM products, and three SSDs. Listing titles are a conservative prefilter; the actual product page determines scope. The two GPU URLs were validated and imported during a small run on 16 October.

`select_daily()` uses offer membership, URLs, and the latest successful observation from PostgreSQL. It skips older offers now outside the active scope. The JSON catalog retains discovery candidates and fetch errors but does not define DAILY's product set. HTTP errors never delete offers or prices. A same-day rerun uses the same Raw file; a new day's successful fetch receives its real observation timestamp. REPLAY interprets saved Raw files under the scope recorded with them, preserving historical observations.

Historical counts for known, fetched, validated, and imported products are in [the phase 3.5 report](archive/PHASE3_5.md). For current counts, run `backend.flow catalog` and `backend.flow verify`. Raw files, saved HTML, and fixtures remain available. The former single-product CLI and `inspect.py` were removed when their duplicate fetch/write paths became unnecessary.
