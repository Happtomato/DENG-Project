# Run, inspect, and verify

Run all commands from the repository root. Docker Desktop must use Linux containers. Mac/ARM64 has been tested; Windows/amd64 still needs an independent check. Create a local `.env` from `.env.example` and keep credentials out of Git. Agree on MediaMarkt usage and volume limits before new live requests. The DISCOVER, INITIAL, and DAILY commands below document supported operation; they do not authorize additional requests.

## First setup and services

```sh
test -f .env || cp .env.example .env
# On a fresh setup, set a local POSTGRES_PASSWORD in .env.
docker compose config --quiet
docker compose up -d --build
docker compose ps
# On an empty database, choose this Raw-file REPLAY OR the Parquet seed import below.
docker compose run --rm --no-deps pipeline python -m backend.flow replay
docker compose run --rm --no-deps pipeline python -m backend.flow verify
```

`db_init` applies `data/initialization.sql` and active migrations idempotently. On an empty database, `verify` correctly exits with code 1 until data is loaded. Do not run both a full REPLAY and a seed import into the same populated database. Never use `down -v` when retaining data. The frontend is at [localhost:3000](http://localhost:3000) and Prefect at [localhost:4200](http://localhost:4200). A fresh checkout registers the DAILY deployment paused by default.

```sh
docker compose logs --tail 80 pipeline
docker compose logs --tail 80 frontend
```

## Catalog, selection, and Raw files

`data/catalog/mediamarkt.json` stores persistent discovery candidates and fetch states. `data/catalog/mediamarkt_initial.json` is an optional manual URL selection. **Only PostgreSQL confirms an imported product or offer**; a successful parse in the catalog is not proof of a DB load. `data/catalog/runs/` stores individual run reports. `data/raw/` and `data/debug/` hold replay and saved HTML evidence and must remain available at their recorded paths.

The seven manually supplied Digitec chart files are organized under `data/import/digitec/manual-charts/{GPU,RAM,SSD}/` and mapped by `data/catalog/digitec_manual_charts.json`. The old Digitec mock is a test fixture under `backend/tests/fixtures/digitec/`. The one-off phase-2 live-test catalog is under `docs/evidence/phase2/`. No JSON was deleted during this cleanup.

After agreeing on access and a small request budget:

```sh
# Listing links from at most one RAM category page; no product details or DB load.
docker compose run --rm pipeline python -m backend.flow discover --categories ram --max-pages 1 --max-requests 3 --delay 3
# Show candidates and active PostgreSQL offers.
docker compose run --rm pipeline python -m backend.flow catalog
# Try one not-yet-imported RAM candidate from the persistent catalog.
docker compose run --rm pipeline python -m backend.flow initial --from-catalog --categories ram --max-products 1 --max-requests 3 --delay 3
# Or use the optional manual selection.
docker compose run --rm pipeline python -m backend.flow initial --selection /workspace/data/catalog/mediamarkt_initial.json --max-products 3 --max-requests 10 --delay 3
```

`--max-pages` and `--max-products` apply per category; `--max-requests` applies across categories, robots.txt, and redirects. Defaults are **three product attempts per category**, **20 total HTTP requests**, and at least **three seconds between requests**. Raising `--max-products` alone does not bypass the total request budget.

## DAILY and Prefect

```sh
# Database-based update of known, in-scope offers only.
docker compose run --rm pipeline python -m backend.flow daily
# Optional one-SKU manual check, after agreeing on live access.
docker compose run --rm pipeline python -m backend.flow daily --categories ssd --sku 2199070 --max-products 1 --max-requests 3 --delay 3
# Read-only database and deployment checks.
docker compose run --rm pipeline python -m backend.flow verify
docker compose exec -T prefect_server env PREFECT_API_URL=http://localhost:4200/api prefect deployment inspect 'DENG MediaMarkt Batch/mediamarkt-daily' --output json
```

The schedule is `0 3 * * *` in `Europe/Zurich`. A fresh checkout starts with `PIPELINE_SCHEDULE_ENABLED=false`. The team explicitly enabled its **local** deployment on 20 October (`.env`: `PIPELINE_SCHEDULE_ENABLED=true`); inspection on 21 October confirmed `paused=false` and `active=true`. To enable it on another machine, set that variable in its `.env`, run `docker compose up -d --no-deps --force-recreate pipeline`, then inspect the deployment. The host must be awake and Docker running at execution time.

The scheduled 21 October run started at 03:50 rather than 03:00 because the Mac slept. It stored five new MediaMarkt observations, reported three disconnected product attempts, and ended `Failed/partial`. The Mac slept again from 03:50:10 to a brief wake at 04:49:38, which accounts for almost all of one apparent hour-long request. The 20-second socket-inactivity timeout does not wake a sleeping computer. See the [run report](../data/catalog/runs/20261021T015016086824Z.json).

Starting the Prefect deployment manually without overriding parameters uses **DAILY**. REPLAY must be selected explicitly. The small per-category limit leaves other offers for a later run; it does not check the whole catalog every day. `--sku` is only for a manual DAILY run and refers to an already imported MediaMarkt SKU. In the Prefect UI, set `product_sku` with `mode=daily` and matching `categories` for a manual single-offer run. The scheduled run has no SKU filter. A changed current price appears only after a successful new product fetch and load; replaying an old file cannot discover it.

Inspect the overall Prefect state **and all three tasks**. `Collect Completed` only means that the collection task returned a report. On per-product failures, Transform/Load still process successful Raw files. The result's `outcome` distinguishes new observations, failed attempts, and offers deferred by limits. A technically partial result is marked **Failed** in Prefect so the missing fetch is visible; successful DB rows remain. `RemoteDisconnected` is a network failure, not HTTP 403/429. HTTP 403/429 stops further requests. There are no automatic HTTP retries or backoff loops.

## REPLAY, backfill, and SQL

REPLAY makes **no HTTP requests**. It adds only observations not already imported and preserves the Raw file's original `collected_at` time.

```sh
docker compose run --rm pipeline python -m backend.flow replay
# A small backfill from saved, real Raw files.
docker compose run --rm pipeline python -m backend.flow replay --input /workspace/data/raw/mediamarkt/live-check
docker compose run --rm pipeline python -m backend.flow verify
```

For read-only SQL checks:

```sh
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < data/queries/verification.sql
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < data/queries/catalog_stats.sql
```

The duplicate offer/timestamp query must return no rows. `backend.flow verify` also checks invalid CHF prices and Raw import states.

## Digitec: offline eight-product proof of concept

There is no approval for automated Digitec access. The old mock is a test fixture, not an import source. The Digitec importer sends **no HTTP requests** and accepts locally saved HTML/JSON or a later explicitly authorized export. The proof of concept is limited to the eight products in `data/catalog/mediamarkt_initial.json`: GPU 2277758/2277995, RAM 2230728/101374309/107353786, SSD 2155505/2199070/2155504.

For WD_BLACK, manually saved HTML and the full chart are under the locally ignored `data/import/digitec/manual/`. The page and price response agree on Digitec SKU 36108805, EAN 619659198053, and a Digitec retail price of CHF 269.00; that EAN matches MediaMarkt SKU 2199070. A cheaper marketplace offer is not treated as Digitec's own retail price. The 292 `validFrom` chart points are **historical retailer price changes**, not daily observations made by this project. They are stored separately in `retailer_price_change`; a point without price remains a gap. Only the evidenced current capture is in `price_history`.

```sh
# Preview: no database write.
docker compose run --rm pipeline python -m backend.flow digitec-import \
  --digitec-html /workspace/data/import/digitec/manual/wd_black_sn850p_2026-10-20.html \
  --digitec-chart /workspace/data/import/digitec/manual/wd_black_sn850p_full_chart_2026-10-20.json \
  --captured-at 2026-10-20T10:28:53+02:00 --digitec-category ssd
# Apply the same checked evidence; rerunning it is idempotent.
docker compose run --rm pipeline python -m backend.flow digitec-import \
  --digitec-html /workspace/data/import/digitec/manual/wd_black_sn850p_2026-10-20.html \
  --digitec-chart /workspace/data/import/digitec/manual/wd_black_sn850p_full_chart_2026-10-20.json \
  --captured-at 2026-10-20T10:28:53+02:00 --digitec-category ssd --apply
```

For another product, first save its **own** matching page and response under `data/import/digitec/manual/`; supply its real capture time and category. The importer checks URL/SKU, EAN, retail seller, current CHF price, product ID, and unambiguous MediaMarkt match. It rejects price/time conflicts and invented capture times.

Seven additional manually saved chart JSONs have **no matching product-page HTML**. They are mapped to the initial products in `data/catalog/digitec_manual_charts.json`; the team confirmed G.Skill and Kingston mappings, while the other five filenames contain matching MPNs. They add only historical chart changes. They do not prove an EAN, seller, or present-day price, so these seven products have no current Digitec observation. The Explorer labels them “Digitec history.”

```sh
# Preview chart-only imports; this does not write or fetch anything.
docker compose run --rm --no-deps pipeline python -m backend.flow digitec-import \
  --digitec-chart-manifest data/catalog/digitec_manual_charts.json
# Explicit, idempotent import of the saved charts.
docker compose run --rm --no-deps pipeline python -m backend.flow digitec-import \
  --digitec-chart-manifest data/catalog/digitec_manual_charts.json --apply
# Check retailer observations and chart changes separately.
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off' < data/queries/digitec_poc.sql
```

A later authorized normalized export may be placed in the Digitec inbox with a genuine `permission_reference`, HTTPS product URL, SKU, EAN, brand, category, product name, seller, CHF price, and timezone-aware observation time. Unknown values must not be guessed. DAILY checks this **local inbox** but does not scrape Digitec. The frontend shows current offers from PostgreSQL and separately marked historical retailer changes; product history defaults to 90 days.

## Tests and frontend

```sh
docker compose run --rm pipeline python -m unittest discover -s backend/tests -v
npm --prefix frontend ci
npm --prefix frontend run check
npm --prefix frontend run lint
npm --prefix frontend run build
DASHBOARD_TEST_URL=http://127.0.0.1:3000 npm --prefix frontend run test:integration
```

Python DB tests use isolated temporary schemas, not a reset of the production schema. HTTP tests use saved fixtures and mocks. Frontend integration tests expect populated local PostgreSQL and Prefect.

For optional Qodana inspections, install the Qodana CLI and run these from the repository root:

```sh
qodana scan --config qodana-backend.yaml
qodana scan --config qodana-frontend.yaml
```

The two configurations inspect `backend/` and `frontend/` separately and install their locked dependencies before analysis. The Python Community linter can run without a Cloud token; the JavaScript linter requires a Qodana Ultimate project token supplied through `QODANA_TOKEN` in the environment. Do not put tokens in YAML or `.env.example`. Qodana complements the existing `make check` (including Svelte-specific checks); it does not replace the offline tests above.

GitHub Actions runs the frontend checks, the full Python and frontend test suites, and both Qodana configurations on pushes and pull requests. The test job starts its own Docker Compose stack with the DAILY schedule disabled and restores `data/seed/midterm-2026-10-20/` into a fresh CI database; it never collects live retailer pages. Commit that complete seed bundle with the workflow, or the integration job will stop with a clear error. Python Qodana Community needs no secret. Frontend Qodana runs only after `QODANA_TOKEN_FRONTEND` is added as a GitHub repository secret for a Qodana Ultimate project; without it, the job explains the skip while the normal frontend checks still run. The workflow does not push fixes or change the local database.

## Parquet seed for a new database

`backend/seed.py` is called **manually via the pipeline container CLI**, not HTTP and not GitHub Actions. `make seed-export` creates a new timestamped `data/seed/.../` directory; `backend.flow seed-export --seed-dir <new-path>` is the direct form. It exports eleven business tables to Parquet and writes a row-count/SHA-256 manifest. It will not overwrite an existing bundle. This is a snapshot of existing data, not a new scrape or synthetic history.

The included `data/seed/midterm-2026-10-20/` bundle contains 26 products, 34 offers, 63 own price observations, and 3,752 separate Digitec chart changes as of export. **Do not import it into the project's populated database.** Import requires an initialized schema with empty business tables and checks all hashes and rows before a transactional restore.

```sh
# Only after docker compose up -d --build on a fresh, empty database:
docker compose run --rm --no-deps pipeline python -m backend.flow seed-import
docker compose run --rm --no-deps pipeline python -m backend.flow verify
# Export the current database to a NEW bundle directory:
make seed-export
# Or choose the new destination explicitly:
docker compose run --rm --no-deps pipeline python -m backend.flow seed-export --seed-dir data/seed/my-new-snapshot
```

The existing bundle was also restored into an isolated empty test schema; a second import was rejected. Raw JSON remains the source evidence.

## Troubleshooting and safe shutdown

```sh
docker compose ps
docker compose logs --since 1h pipeline
docker compose logs --since 1h prefect_server
docker compose run --rm pipeline python -m backend.flow verify
docker compose stop
```

After a failed DAILY run, compare its `data/catalog/runs/<run_id>.json`, the overall Prefect state, all three tasks, and `verify`. The load's total `accepted` count may include old Raw duplicates; use `outcome.new_observations_from_selected_raw` for new observations from that run. `remaining_due` counts offers deferred by product limits; failed attempts are in `errors`.

Docker images can be rebuilt from Dockerfiles. PostgreSQL and Prefect state is in the named `postgres_data` and `prefect_data` volumes; `./data` is a host-mounted directory. `docker compose stop` or `docker compose down` **without `-v`** retains them. Do not run `docker compose down -v` or `docker volume prune` while those data are needed.
