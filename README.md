# PC Price Lab — Swiss PC hardware prices

**HSLU Data Engineering, autumn 2026 · Midterm deadline: 22 October 2026, 15:30 Europe/Zurich**

This small batch pipeline collects evidenced Swiss prices for GPUs, desktop RAM, and internal NVMe SSDs. PostgreSQL is the data product; a read-only SvelteKit frontend lets us inspect products, retailer offers, and price histories. Cloud infrastructure is reserved for the final project.

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
| `backend/retailers/digitec/importer.py` | Offline import of manually captured or explicitly authorized Digitec files; no Digitec scraper |
| `backend/transform.py` | Validate and normalize Raw observations |
| `backend/ingestion.py` | Transactional, idempotent PostgreSQL loading |
| `backend/database.py` | Connection, schema migrations, and verification queries |
| `backend/seed.py` | Parquet snapshot export and guarded automatic import for an empty database; outside daily collection |
| `backend/tests/` | Offline regression tests and saved fixtures |

`data/raw/` contains source evidence and must keep its paths for replay and database provenance. `data/debug/` contains saved HTML used for diagnosis and Raw verification. `data/catalog/` holds selected URLs, discovery state, and run reports. `data/import/` holds manually supplied Digitec material. `data/migrations/` and `data/initialization.sql` define the schema; `data/queries/` contains reviewer SQL; `data/seed/` contains a checked Parquet snapshot. The `archive/` and `evidence/` subdirectories preserve earlier project decisions and test results. See the [architecture](docs/ARCHITECTURE.md) for the dependency map.

## Collection modes and data meaning

DISCOVER stores product links in the candidate catalog; it does not import prices. INITIAL validates selected new products and creates products, retailer offers, and first observations. DAILY reads active MediaMarkt and SwissHardware offer URLs from PostgreSQL and records new observations. REPLAY reprocesses retained Raw files without HTTP. A repeated Raw file does not create another observation; a genuine new daily fetch with an unchanged price does. The scheduled Prefect deployment runs only DAILY at **03:00 Europe/Zurich**. Check `PIPELINE_SCHEDULE_ENABLED` in `.env` before starting; this project's local deployment was enabled at the team's request.

The transformation checks identity, source timestamps, and positive CHF prices, and normalizes SSD terabytes and RAM kit capacity to GB. Missing technical values remain unknown. This makes price-per-capacity comparisons meaningful without inventing product facts.

MediaMarkt Switzerland remains an active HTML/JSON-LD source. SwissHardware Sàrl has permitted once-daily collection and is the provisional product-master source: GPU, RAM, and SSD product pages supply identifiers, specifications, and own price observations. Its category discovery is manual. All 395 listing links were captured as product pages on 22 October. Manufacturer and technical checks found 184 offers in the current scope: 112 with verified manufacturer MPNs are active for DAILY; 72 without MPNs are inactive. Eleven offers imported under the earlier, looser RAM rule remain in the database but are inactive, with a reason. All 395 captures are recorded in `raw_import`; 200 rejected pages remain in Raw and the catalog but are not invented as valid product rows. The MediaMarkt batch attempts at most three products per category and 20 HTTP requests in total, with at least three seconds between requests and robots.txt checks. Digitec is a future preferred product-master source, but automated access has **not been authorized**. The current proof of concept uses manually saved evidence. Digitec `validFrom` points are historical **retailer price changes** in `retailer_price_change`, not our daily measurements in `price_history`; seven of eight example products therefore have no current Digitec price.

## Verification, limitations, and submission

The local read-only check on 24 October showed **215 products, 229 retailer offers, and 408 actual price observations**, with zero invalid CHF prices or duplicate offer/timestamp pairs. The included older seed contains 26 products, 34 offers, and 79 observations. Counts change after new runs; use [verification SQL](data/queries/verification.sql) and the [midterm audit](docs/MIDTERM_AUDIT.md) for checks.

A sleeping laptop cannot reliably run a local schedule. The small request budget does not cover the entire catalog each day. BRACK declined the team's data-access request without giving a specific reason; it is excluded as a project data source, and no BRACK collection will be implemented. Automatic Digitec scraping, Interdiscount, Terraform, GCS, and BigQuery are outside this midterm scope. The Parquet bundle is a reproducibility snapshot, not a substitute for Raw evidence or a new fetch. The team still needs to test a fresh checkout on another computer, agree on retailer usage limits, prepare a commit/tag, and submit through ILIAS.

- [Runbook](docs/RUN_COMMANDS.md): setup, collection, Prefect, seeds, SQL, and shutdown.
- [Architecture v0.2](docs/ARCHITECTURE.md): components, schema, and failure behavior.
- [MediaMarkt adapter](docs/MEDIAMARKT.md): parsing, scope, and collection limits.
- [Frontend](frontend/README.md): views, API, and local development.
- [Midterm audit](docs/MIDTERM_AUDIT.md): every checklist item and its evidence.
