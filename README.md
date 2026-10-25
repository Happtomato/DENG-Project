# PC Price Lab — Swiss PC hardware prices

**HSLU Data Engineering, autumn 2026 · Midterm deadline: 22 October 2026, 15:30 Europe/Zurich**

This small batch pipeline collects evidenced Swiss prices for GPUs, desktop RAM, and internal NVMe SSDs. PostgreSQL is the data product; a read-only SvelteKit frontend lets us inspect products, retailer offers, and price histories. Cloud infrastructure is reserved for the final project.

The intended users are students comparing the prices and specifications of the same hardware across Swiss shops. One `product` row represents an identified hardware model, one `retailer_product` row a shop's offer/URL, and one `price_history` row a price actually observed at a specific time. We use incremental daily collection after an initial product review: a new observation is useful even when the price is unchanged, while replaying the same Raw file must not duplicate it. Missing specifications and unavailable prices remain unknown rather than being filled in. This is a small project sample, not a complete Swiss market index.

| Source | Access and format | Frequency and quality risk |
| --- | --- | --- |
| SwissHardware | Approved public category/product HTML, saved with URL and capture time | One selected-product pass per Zurich day; 112 active offers at the last review. Pages can omit a manufacturer MPN, change layout, or return 429. |
| MediaMarkt | Public product HTML with JSON-LD, saved as Raw JSON and HTML evidence | Bounded daily requests for already imported offers; pages can disconnect, change schema, or lack a valid price. Larger volumes need an agreed limit. |
| Digitec | Manually captured page/chart files supplied by the team; offline import only | Historical `validFrom` changes are not daily observations. Automated access is awaiting permission. |

## Start locally

Docker Desktop with Linux containers and Docker Compose are required. Node.js 24 and npm are needed only for local frontend checks; Compose builds the frontend in a container.

```sh
test -f .env || cp .env.example .env
# On a fresh setup, choose a local POSTGRES_PASSWORD in .env.
docker compose up -d --build
docker compose ps
docker compose run --rm --no-deps pipeline python -m backend.flow verify
```

On a fresh database, `db_init` creates the schema and automatically imports the newest Parquet bundle in `data/seed/`. It validates checksums and row counts; a restart leaves populated tables untouched. If no bundle is present, the schema stays empty until data is loaded. `replay` can rebuild MediaMarkt records from retained Raw JSON and demonstrates the ingestion path itself. The [runbook](docs/RUN_COMMANDS.md) gives the exact commands and SQL checks. The frontend runs at [localhost:3000](http://localhost:3000), Prefect at [localhost:4200](http://localhost:4200). `make up`, `make verify`, `make check`, and `make test` are shortcuts; `make stop` preserves volumes.

## Data flow and code map

```text
MediaMarkt HTML/JSON-LD → Raw JSON → validation and transformation → PostgreSQL
                               Prefect: Collect → Transform → Load
Manually captured Digitec files ────────────────→ checked offline import
PostgreSQL → read-only SvelteKit views / explicit Parquet snapshot export
```

The active Python backend has a small set of distinct responsibilities:

| Path | Responsibility |
| --- | --- |
| `backend/flow.py` | One CLI entry point and Prefect flow; DISCOVER, INITIAL, DAILY, REPLAY, verification, and explicit seed commands |
| `backend/retailers/mediamarkt/` | HTTP collection, listing discovery, JSON-LD parsing, and product scope |
| `backend/retailers/swisshardware/` | Approved category discovery, checked product captures, and daily prices for active PostgreSQL offers |
| `backend/retailers/digitec/importer.py` | Offline import of manually captured or explicitly authorized Digitec files; no Digitec scraper |
| `backend/transform.py` | Validate and normalize Raw observations |
| `backend/ingestion.py` | Transactional, idempotent PostgreSQL loading |
| `backend/database.py` | Connection, schema migrations, and verification queries |
| `backend/seed.py` | Parquet snapshot export and guarded automatic import for an empty database; outside daily collection |
| `backend/tests/` | Offline regression tests and saved fixtures |

`data/raw/` contains source evidence and keeps its paths for replay and database provenance. `data/debug/` contains saved HTML used for diagnosis and Raw verification. `data/catalog/` holds selected URLs, discovery state, and run reports. `data/import/` holds manually supplied Digitec material. `data/migrations/` and `data/initialization.sql` define the active schema; `data/queries/` contains reviewer SQL; `data/seed/` contains a checked Parquet snapshot. Historical SQL is under `docs/archive/sql/`; previous reports and test evidence remain in `docs/archive/` and `docs/evidence/`. See the [architecture](docs/ARCHITECTURE.md) for the dependency map.

## Collection modes and data meaning

DISCOVER stores product links in the candidate catalog; it does not import prices. INITIAL validates selected new products and creates products, retailer offers, and first observations. DAILY reads active MediaMarkt and SwissHardware offer URLs from PostgreSQL and records new observations. REPLAY reprocesses retained Raw files without HTTP. A repeated Raw file does not create another observation; a genuine new daily fetch with an unchanged price does. The Prefect deployment is configured for DAILY at **03:00 Europe/Zurich**. Fresh setups leave its schedule paused (`PIPELINE_SCHEDULE_ENABLED=false`) to avoid unplanned retailer requests. The existing local `.env` may differ; on 25 October the runner was verified as READY with the schedule intentionally paused. Check both `.env` and Prefect before relying on scheduled runs.

The transformation checks identity, source timestamps, and positive CHF prices, and normalizes SSD terabytes and RAM kit capacity to GB. Missing technical values remain unknown. This makes price-per-capacity comparisons meaningful without inventing product facts.

MediaMarkt Switzerland remains an active HTML/JSON-LD source. SwissHardware Sàrl has permitted once-daily collection and is the provisional product-master source: GPU, RAM, and SSD product pages supply identifiers, specifications, and own price observations. Its category discovery is manual. All 395 listing links were captured as product pages on 22 October. Manufacturer and technical checks found 184 offers in the current scope: 112 with verified manufacturer MPNs are active for DAILY; 72 without MPNs are inactive. Eleven offers imported under the earlier, looser RAM rule remain in the database but are inactive, with a reason. All 395 captures are recorded in `raw_import`; 200 rejected pages remain in Raw and the catalog but are not invented as valid product rows. The MediaMarkt batch attempts at most three products per category and 20 HTTP requests in total, with at least three seconds between requests and robots.txt checks. Digitec is a future preferred product-master source, but automated access has **not been authorized**. The current proof of concept uses manually saved evidence. Digitec `validFrom` points are historical **retailer price changes** in `retailer_price_change`, not our daily measurements in `price_history`; seven of eight example products therefore have no current Digitec price.

SwissHardware consent covers the selected product pages once per day at approximately 03:00, with at least three seconds between requests, until **9 December 2026**. The retailer's written reply was “Ja, du chasch es 1x pro Tag abhole.” The collection code records attempted URLs before each request, so failed requests are not retried on the same Zurich day. HTTP 403, 429, or server errors stop the remaining SwissHardware batch for that day. A 429 is a technical rate-limit response, not evidence that consent was withdrawn; its exact cause is unknown. Runs on 24–25 October encountered 429 and added no new SwissHardware captures. Do not repeatedly launch manual DAILY runs to probe the limit; ask the retailer to confirm the server's practical request budget. The [runbook](docs/RUN_COMMANDS.md) explains the daily request journal and safe verification without new shop requests.

## Verification, limitations, and submission

The local read-only check on **25 October** showed **215 products, 229 retailer offers, and 424 actual price observations**, with zero invalid CHF prices or duplicate offer/timestamp pairs. A matching Parquet bundle under `data/seed/2026-10-25-081750-415685/` was restored and verified in an isolated schema; fresh installations choose this latest bundle automatically. The older `midterm-2026-10-25/` bundle contains 26 products, 34 offers, and 79 observations despite its directory name. Counts change after new runs; use [verification SQL](data/queries/verification.sql) and the [midterm audit](docs/MIDTERM_AUDIT.md) for checks.

A sleeping laptop cannot reliably run a local schedule. The MediaMarkt request budget does not cover its entire catalog each day; SwissHardware's practical server limit is unresolved despite the agreement. BRACK declined the team's data-access request without giving a specific reason; it is excluded as a project data source. Automatic Digitec scraping, Interdiscount, Terraform, GCS, and BigQuery are outside the midterm scope. The Parquet bundle is a reproducibility snapshot, not a substitute for Raw evidence or a new fetch. The **midterm repository deadline was 22 October 2026**; code changed after that date cannot alter the assessed commit. Both students must independently explain the pipeline in the oral defence, and the team must check its actual ILIAS submission and assigned peer-review work.

- [Runbook](docs/RUN_COMMANDS.md): setup, collection, Prefect, seeds, SQL, and shutdown.
- [Architecture v0.2](docs/ARCHITECTURE.md): components, schema, and failure behavior.
- [MediaMarkt adapter](docs/MEDIAMARKT.md): parsing, scope, and collection limits.
- [Frontend](frontend/README.md): views, API, and local development.
- [Midterm audit](docs/MIDTERM_AUDIT.md): every checklist item and its evidence.
- [Documentation guide](docs/README.md) and [data-folder guide](data/README.md): maintained files versus historical evidence.
