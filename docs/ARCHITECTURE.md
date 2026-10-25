# Architecture v0.2 — local midterm system

The active system consists of MediaMarkt and SwissHardware adapters, a small manual Digitec proof of concept, retained Raw files, PostgreSQL, one Prefect flow, and a read-only SvelteKit frontend. Cloud, Terraform, GCS, and BigQuery belong to the final phase.

BRACK declined the team's data-access request without stating a reason. It is excluded from future retailer integration; this is a source-selection decision, not a claim about BRACK's technical systems or policies. Other retailers are only candidates until their product coverage, data access, and permitted request volume have been checked.

```mermaid
flowchart LR
  MM[MediaMarkt public HTML] --> C[MediaMarkt collector]
  SH[SwissHardware public HTML] --> SC[Bounded SwissHardware collector]
  SC --> SR[(SwissHardware Raw HTML)]
  SR --> SI[Validate scope, MPN, seller and CHF]
  SI --> DB
  DB -->|DAILY active SwissHardware URLs| SC
  DISC[DISCOVER category pages] --> CAT[(JSON candidate catalog)]
  CAT -->|INITIAL candidates| C
  SEL[Optional manual selection] --> C
  DB[(PostgreSQL)] -->|DAILY known offers and URLs| C
  C --> RAW[(Raw JSON and saved HTML)]
  RAW --> T[Transform: scope, identity, CHF, specifications]
  T --> L[Transactional load]
  L --> DB
  DG[Manually saved Digitec evidence] --> DI[Offline identity and price checks]
  DI --> DB
  DI --> CH[(Historical retailer price changes)]
  RAW -->|REPLAY without HTTP| T
  DB --> UI[SvelteKit read-only views]
  CH --> UI
  DB -->|explicit export| PQ[(Parquet snapshot)]
  PQ -->|db_init: newest bundle, empty DB only| DB
  PF[One Prefect flow: Collect → Transform → Load] -. orchestrates .-> C
  PF -. orchestrates .-> T
  PF -. orchestrates .-> L
  DB --> V[VERIFY: SQL quality checks]
```

## Code and modes

`backend/flow.py` is the only pipeline CLI and Prefect entry point. `backend/retailers/mediamarkt/collector.py` handles bounded HTTP collection, robots.txt, listing discovery, and URL selection; `parser.py` extracts JSON-LD and embedded technical specifications. `backend/transform.py` validates Raw records, `backend/ingestion.py` loads them transactionally, and `backend/database.py` owns connections, migrations, and verification queries. `backend/seed.py` exports offline snapshots and restores the latest one during empty-database initialization; it is not a daily task. Tests and fixtures are in `backend/tests/`. There is no second pipeline or retailer microservice.

`backend/retailers/digitec/importer.py` accepts locally supplied files **without network access**. The midterm proof of concept is tied to the eight MediaMarkt products in the initial selection. A current Digitec offer requires a matching product page, product ID, retail seller and price, and an unambiguous EAN match. Seven chart-only JSON files are mapped in `data/catalog/digitec_manual_charts.json`; they add historical `validFrom` changes to `retailer_price_change`, but no current observation. A point without a price remains a gap. `price_history` contains only independently evidenced observations. Automated Digitec access is not configured.

`backend/retailers/swisshardware/collector.py` collects the three approved category listings and records product URLs in `data/catalog/swisshardware.json`. `product.py` captures bounded product pages, validates seller, category, scope, CHF price and manufacturer MPN, and imports saved observations through the shared ingestion code. INITIAL skips product URLs already archived on any date. When the detail page has a labelled manufacturer (`Fabricant`), it takes precedence over the title; ASUS TUF and Kingston FURY Beast are recognized title aliases. The shop's JSON-LD brand names the shop and is not product-manufacturer evidence. On 22 October all 395 listing links were captured. Of these, 184 satisfy the current technical and manufacturer scope: 112 with verified MPN are active for DAILY and 72 without MPN are inactive. Eleven offers imported under the earlier RAM rule remain in PostgreSQL but are now inactive with a scope reason. All 395 captures have `raw_import` provenance; 200 rejected pages remain in Raw and the catalog without creating unverified product rows. Original prices remain available; DAILY selects active URLs from PostgreSQL, never from listing pages.

- **DISCOVER:** Manual, links only. Parses category pages and pagination, saves normalized candidate URLs in `data/catalog/mediamarkt.json`; no product detail fetch or database import.
- **INITIAL:** Uses either `mediamarkt_initial.json` or unimported catalog candidates. Valid products create products, retailer offers, and first price observations.
- **DAILY:** Reads active MediaMarkt and SwissHardware offer URLs from PostgreSQL. It does not discover new URLs or fetch category pages. It also checks locally supplied normalized Digitec inbox files, without Digitec HTTP access.
- **REPLAY:** Loads retained Raw files without HTTP and preserves their original observation times.
- **VERIFY:** Reads product, offer, observation, price-quality, and duplicate counts.
- **Seed export/import:** Export is an explicit CLI operation. On a fresh database, `db_init` imports the newest checked Parquet bundle automatically; manual import into an empty schema remains available. No HTTP endpoint or scheduled Prefect task is involved.

Prefect schedules **DAILY only** at 03:00 Europe/Zurich. Schedule activation follows `PIPELINE_SCHEDULE_ENABLED` in `.env`; the team's local deployment is enabled. A sleeping host cannot guarantee a punctual run.

## Infrastructure and data model

`docker-compose.yaml` has four long-running services: `postgres`, `prefect_server`, `pipeline`, and `frontend`; `db_init` is a one-off schema job. They share `deng-project-network`. `postgres_data` and `prefect_data` are named persistent volumes. The pipeline bind-mounts `./data`; the frontend reads the catalog read-only. Local ports are 5432, 4200, and 3000. Database credentials stay on the SvelteKit server, not in the browser.

`backend.database.migrate()` applies `data/initialization.sql` and active `data/migrations/*.sql`, recording checksums. SQL under `data/migrations/archive/` is not applied. The core tables are `brand`, `category`, `retailer`, `product`, `retailer_product`, `price_history`, and GPU/RAM/SSD detail tables. `raw_import` records file provenance and import results. `retailer_product` retains the retailer SKU, URL, active tracking flag and optional reason; `price_history.collected_at` retains the real observation time. Raw hashes and the unique offer/timestamp constraint prevent duplicate imports. A genuine new day's fetch may produce a new observation even when the price is unchanged. Product identity requires evidence such as EAN, brand/MPN, or the existing retailer SKU; uncertain variants are not matched by name alone.

`backend/seed.py` exports eleven business tables as Parquet with SHA-256 hashes, row counts, and a creation time in a manifest. `db_init` mounts `data/seed/` read-only, chooses the newest bundle and imports it only when all business tables are empty. Import checks every file in one database transaction; a damaged newest bundle fails rather than loading older data silently. A restart cannot replace existing rows. Raw JSON and REPLAY remain the evidence of ingestion. The transformation normalizes RAM kit capacity and SSD TB to GB, checks positive CHF prices, and leaves unknown details empty. The `hardware_prices` view exposes prices, retailer, actual seller, category, time, and Raw provenance.

## Failure behavior and limits

The collector checks robots.txt, domain, SKU and redirects, HTML content type, a total request budget, and at least three seconds between requests. HTTP 401/403/429/503 stops further collection. Per-product network or validation failures are reported while other selected products continue. There are no automatic HTTP retries. The 20-second Requests timeout limits socket inactivity, not total wall time or host sleep. The scheduled run on 21 October began 50 minutes late while the Mac slept; another sleep interrupted one request for almost an hour. It still stored five successful observations and marked the overall flow Failed because three product attempts disconnected. See the [midterm audit](MIDTERM_AUDIT.md) and [run report](../data/catalog/runs/20261021T015016086824Z.json).

Successful Raw files survive partial failures and proceed through Transform/Load. Repeated Raw files are identified as duplicates. Reports separate newly collected observations from old Raw reprocessing. A technical partial result is deliberately marked **Failed** in Prefect so missing products remain visible. Failed offers keep their last successful observation and are eligible on a later permitted run. Three product attempts per category and 20 total HTTP requests do not cover the complete catalog in one day; the limits are not raised without agreed usage boundaries.

Compared with v0.1, the midterm scope was reduced to a verifiable local data pipeline. Compared with phase 3, the SvelteKit frontend is an optional fourth long-running service and catalog-based DISCOVER/INITIAL are connected. Historical designs and phase reports remain in [archive/](archive/); saved SQL, Prefect, and test evidence remains in [evidence/](evidence/). Exact commands are in the [runbook](RUN_COMMANDS.md).
