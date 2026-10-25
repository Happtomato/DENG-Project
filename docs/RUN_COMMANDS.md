# Run, inspect, and verify

Run all commands from the repository root. Docker Desktop must use Linux containers. Mac/ARM64 has been tested; Windows/amd64 still needs an independent check. Create a local `.env` from `.env.example` and keep credentials out of Git. Agree on MediaMarkt usage and volume limits before new live requests. The DISCOVER, INITIAL, and DAILY commands below document supported operation; they do not authorize additional requests.

## First setup and services

```sh
test -f .env || cp .env.example .env
# On a fresh setup, set a local POSTGRES_PASSWORD in .env.
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose run --rm --no-deps pipeline python -m backend.flow verify
```

`db_init` applies the schema and migrations, then imports the newest `data/seed/*/manifest.json` bundle only if every business table is empty. It reports the selected bundle or `skipped_nonempty`. Without a bundle, the schema stays empty and `verify` exits with code 1 until data is loaded; a manual Raw-file REPLAY is then an option. Existing data is never replaced by a newer seed. Never use `down -v` when retaining data. The frontend is at [localhost:3000](http://localhost:3000) and Prefect at [localhost:4200](http://localhost:4200). Check `PIPELINE_SCHEDULE_ENABLED` in the copied `.env` before starting the deployment.

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

## SwissHardware: provisional master data and daily prices

The retailer confirmed one collection per day after the team described roughly 100 selected product pages, a 03:00 run, at least three seconds between requests, and an end date of **9 December 2026**. The shop's server can still enforce a stricter technical limit; HTTP 429 occurred on 24 and 25 October. Do not interpret it as a withdrawal of consent, and do not repeatedly rerun DAILY to probe it. The exact server limit is unknown; ask the retailer before another live trial.

SwissHardware Sàrl allowed automated access once per day. On 22 October 2026, the team captured all linked GPU, RAM, and SSD category pages: **6 + 4 + 4 pages**. The HTML is under `data/raw/swisshardware/listings/2026-10-22/`. The catalog contains **171 GPU, 111 RAM, and 113 SSD listing candidates**. Listing prices are not database observations. All **395 product pages** have now been captured once with at least three seconds between requests; 130 were already saved and only the 265 missing URLs were requested in the second pass. The detail-page manufacturer and technical checks found **184 currently in-scope offers**: 112 active with verified MPN (41 GPU, 38 RAM, 33 SSD), and 72 inactive without MPN (28 GPU, 32 RAM, 12 SSD). Another 11 offers imported under an earlier, looser RAM rule remain in PostgreSQL but are inactive with an explicit scope reason. All 395 captures are recorded in `raw_import`: 195 as loaded and 200 as rejected. The 200 rejected pages remain in Raw and the catalog with review reasons, without creating unverified product rows. Every imported offer retains its first real price observation and URL.

```sh
# Rebuild the pipeline image once after pulling the new adapter; no volume deletion.
docker compose build pipeline
# Reparse saved category HTML without any HTTP requests.
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.collector discover
# Review candidates and their direct product links, optionally by category.
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.collector list gpu
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.collector list ram
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.collector list ssd
# Manual overrides for a catalog candidate; active DAILY membership is held in PostgreSQL.
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.collector select PRODUCT-SLUG
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.collector deselect PRODUCT-SLUG
```

To refresh the category catalog on a **later** Zurich calendar day, run `discover --live --max-pages 10 --max-requests 20 --delay 3`. Existing listing HTML for that day is reused. Category discovery is manual and does not run at 03:00. It follows only numbered pages in the three approved categories, checks robots.txt and stops on denied or failed responses. INITIAL requests only product URLs that have never been captured on any date. It can be rerun without another product request after the current catalog is captured:

```sh
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.product initial --max-products 20 --delay 3
```

The product collector stores HTML, URL, listing-derived category, and actual capture timestamp in `data/raw/swisshardware/products/YYYY-MM-DD/`. The importer checks canonical URL, seller, CHF price, manufacturer and technical scope, and explicitly labelled manufacturer MPN; the shop's JSON-LD `brand` names the shop and its JSON-LD `mpn` is a variant ID, so neither is used as manufacturer evidence. An explicit `Fabricant` on the page takes precedence; ASUS TUF and Kingston FURY Beast are recognized from their titles when that field is absent. Repeated imports are idempotent. Exact EAN and MPN can link an existing MediaMarkt master without overwriting conflicting technical descriptions. An offer without verified MPN is retained with `is_active=false` and a reason; it receives no later DAILY fetch. The 22 October Raw files can be replayed without HTTP:

```sh
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.product initial --raw-dir data/raw/swisshardware/products/2026-10-22 --max-products 1
# On a new Zurich calendar day, fetch active PostgreSQL offer URLs and import their observations:
docker compose run --rm --no-deps pipeline python -m backend.retailers.swisshardware.product daily --max-products 200 --delay 3
```

DAILY reads active SwissHardware offers from PostgreSQL; the catalog's `selected` flag records INITIAL review. The current cap of 200 covers all 112 active offers, with a three-second minimum delay, and reports any deferred offers if the active set later exceeds the cap. A stopped or sleeping host misses the 03:00 run. The 23 October next-day run saved 112 SwissHardware captures; 24–25 October runs hit 429 and saved none. Digitec enrichment after permission will require extending its current eight-product importer and exact MPN/EAN matching; unknown identities must not be merged by similar names.

For SwissHardware, `data/raw/swisshardware/products/YYYY-MM-DD/_request_attempts.json` records every attempted product URL before HTTP, including failures. A same-day rerun skips those URLs; 403, 429, server errors, or an interrupted request stop the remaining batch for that Zurich day. The journal's `blocked` and `in_flight` fields explain why a run makes zero new requests. Keep this file with its dated Raw directory; deleting it would remove the once-per-day protection. Successful saved Raw files are still imported even when a later request fails. This journal was introduced after the 24–25 October failures, so it does not retroactively record those attempts.

## DAILY and Prefect

```sh
# Database-based MediaMarkt update plus the selected SwissHardware URLs.
docker compose run --rm pipeline python -m backend.flow daily
# Optional one-SKU manual check, after agreeing on live access.
docker compose run --rm pipeline python -m backend.flow daily --categories ssd --sku 2199070 --max-products 1 --max-requests 3 --delay 3
# Read-only database and deployment checks.
docker compose run --rm pipeline python -m backend.flow verify
docker compose exec -T prefect_server env PREFECT_API_URL=http://localhost:4200/api prefect deployment inspect 'DENG Product Price Pipeline/fetch-product-prices-daily' --output json
```

The schedule is `0 3 * * *` in `Europe/Zurich`. Compose and `.env.example` default to `PIPELINE_SCHEDULE_ENABLED=false` for a fresh setup, so merely starting the project does not trigger retailer requests. The team's existing local `.env` may still enable the deployment. On 25 October, Prefect showed the single deployment **READY**, with the correct cron/timezone and `paused=true` during an offline verification started with `PIPELINE_SCHEDULE_ENABLED=false`. DAILY runs MediaMarkt collection, the local authorised Digitec inbox import, and active SwissHardware product URLs from PostgreSQL. SwissHardware category discovery remains manual and is never scheduled. Only after agreeing practical request limits, set `PIPELINE_SCHEDULE_ENABLED=true` in `.env`, run `docker compose up -d --no-deps --force-recreate pipeline`, then inspect the deployment. The host must be awake and Docker running at execution time.

Prefect's run form now shows typed default values and a description for every parameter. The deployment uses these current values unless overridden:

| Parameter | Default | Meaning |
| --- | --- | --- |
| `mode` | `daily` | Run the daily workflow. Other modes are manual CLI operations. |
| `input_dir` | `/workspace/data/raw/mediamarkt` | MediaMarkt Raw JSON directory. |
| `catalog` | `/workspace/data/catalog/mediamarkt.json` | MediaMarkt candidate catalog. |
| `max_products` | `3` | MediaMarkt attempts **per category**; SwissHardware separately caps at 200 active offers. |
| `max_requests` | `20` | Maximum MediaMarkt HTTP requests in this run. |
| `selection` | `/workspace/data/catalog/mediamarkt_initial.json` | Manual MediaMarkt INITIAL URL selection; unused by DAILY. |
| `delay` | `3.0` seconds | Minimum delay between requests for both retailers. |
| `categories` | `gpu`, `ram`, `ssd` | MediaMarkt categories; SwissHardware DAILY uses all active DB offers. |
| `max_pages` | `1` | MediaMarkt listing pages for manual DISCOVER; unused by DAILY. |
| `from_catalog` | `false` | MediaMarkt INITIAL catalog selection; unused by DAILY. |
| `product_sku` | `null` | No MediaMarkt SKU restriction; a targeted manual SKU run skips SwissHardware. |

The scheduled 21 October run started at 03:50 rather than 03:00 because the Mac slept. It stored five new MediaMarkt observations, reported three disconnected product attempts, and ended `Failed/partial`. The Mac slept again from 03:50:10 to a brief wake at 04:49:38, which accounts for almost all of one apparent hour-long request. The 20-second socket-inactivity timeout does not wake a sleeping computer. See the [run report](../data/catalog/runs/20261021T015016086824Z.json).

Starting the Prefect deployment manually without overriding parameters uses **DAILY**. REPLAY must be selected explicitly. The small per-category limit leaves other offers for a later run; it does not check the whole catalog every day. `--sku` is only for a manual DAILY run and refers to an already imported MediaMarkt SKU. In the Prefect UI, set `product_sku` with `mode=daily` and matching `categories` for a manual single-offer run. The scheduled run has no SKU filter. A changed current price appears only after a successful new product fetch and load; replaying an old file cannot discover it.

Inspect the overall Prefect state **and every task**. `Collect Completed` only means that the collection task returned a report. On per-product failures, Transform/Load still process successful Raw files. The result's `outcome` distinguishes new observations, failed attempts, and offers deferred by limits. A technically partial result is marked **Failed** in Prefect so the missing fetch is visible; successful DB rows remain. `RemoteDisconnected` is a network failure, not HTTP 403/429. HTTP 403/429 stops further requests. There are no automatic HTTP retries or backoff loops.

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

GitHub Actions runs the frontend checks, the full Python and frontend test suites, and both Qodana configurations on pushes and pull requests. The test job starts its own Docker Compose stack with the DAILY schedule disabled; `db_init` restores the newest committed seed into its fresh CI database. It never collects live retailer pages. Commit at least one complete seed bundle with the workflow, or the integration job will stop with a clear error. Python Qodana Community needs no secret. Frontend Qodana runs only after `QODANA_TOKEN_FRONTEND` is added as a GitHub repository secret for a Qodana Ultimate project; without it, the job explains the skip while the normal frontend checks still run. The workflow does not push fixes or change the local database.

## Parquet seed for a new database

`make seed-export` creates a new timestamped `data/seed/.../` directory; `backend.flow seed-export --seed-dir <new-path>` is the direct form. It exports eleven business tables to Parquet and writes a row-count/SHA-256 manifest with a UTC creation time. The next **fresh, empty** database chooses the newest manifest automatically, regardless of directory name. Older bundles without a creation time use the date in their directory name. A malformed newest bundle fails startup rather than silently falling back to an older one. This is a snapshot of existing data, not a new scrape or synthetic history.

The newest included bundle is `data/seed/2026-10-25-081750-415685/`: 215 products, 229 offers, 424 own price observations, and 3,752 separate Digitec chart changes. It was restored into an isolated empty schema and verified. The older `data/seed/midterm-2026-10-25/` bundle remains available with 26 products, 34 offers, and 79 observations; its directory name does not reflect the observation dates. **Do not import either bundle into the project's populated database.** Import requires an initialized schema with empty business tables and checks all hashes and rows before a transactional restore.

```sh
# Import is automatic during the first docker compose up on an empty database.
docker compose run --rm --no-deps pipeline python -m backend.flow verify
# Export the current database to a NEW bundle directory:
make seed-export
# Or choose the new destination explicitly:
docker compose run --rm --no-deps pipeline python -m backend.flow seed-export --seed-dir data/seed/my-new-snapshot
```

`backend.flow seed-import` remains available for an initialized **empty** database or isolated test schema; `--seed-dir` selects a particular bundle. It refuses populated tables. Exporting a newer bundle never modifies the current database and takes effect only on a future fresh database.

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
