# Phase 5.2 — DAILY diagnosis and data audit

Historical record from 17 October 2026, Europe/Zurich. It documents the state at that time, **not current database totals**. This audit deleted no Raw, HTML, SQL, or catalog files, reset no volume, and made no additional MediaMarkt request.

## Scheduled DAILY run on 17 October

Prefect flow `DENG MediaMarkt Batch`, run `brainy-coucal` (`01a14697-231c-7111-bc10-14ce486f5b8a`), collector run `20261017T011041653545Z`: due **03:00 CEST**, started **03:10:41**, ended **03:41:35**, overall state **Failed**. Collect, Transform, and Load each completed as tasks. The flow then marked the batch incomplete because the collector reported two product failures. A completed Collect task means only that a report was returned.

The unchanged [collector report](../../../data/catalog/runs/20261017T011041653545Z.json) shows 22 selected DB products, six accepted pages, two errors, 14 deferred by product limits, zero already collected that day, nine HTTP requests, and six new Raw files. The DB rose from 33 to **39 observations**. Verification showed 26 products, 26 offers, 39 observations, zero invalid CHF prices, zero duplicate offer/timestamp pairs, and `ok=true`. Eighteen out-of-scope or low-quality Raw files were rejected rather than loaded as prices.

The deployment used `mode=daily`, `max_products=3`, `max_requests=20`, `delay=3.0`, and GPU/RAM/SSD categories. `max_products` is **per category**. Of 26 DB offers, 22 passed the active scope: two GPU and three each for RAM and SSD were attempted, making eight product attempts plus robots.txt = nine requests. Six succeeded and two failed; the other 14 were deferred. Four older DB offers remained outside the current scope but were not deleted. The HTTP budget was not exhausted. Limits were not raised because allowed collection volume was still unresolved.

| SKU | Saved product URL | Failure and handling |
| --- | --- | --- |
| 101374309 | `https://www.mediamarkt.ch/de/product/_kingston-ddr4-ram-fury-beast-3200-mhz-arbeitsspeicher-16-gb-ddr4-101374309.html` | `RemoteDisconnected` at 03:11:09; last successful DB observation from 16 October remained. |
| 2155504 | `https://www.mediamarkt.ch/de/product/_samsung-990-pro-nvme-m-2-ssd-2155504.html` | Same disconnect type at 03:41:33; remains eligible for a later permitted run. |

`Client.request()` uses `requests.Session.get(..., timeout=20, allow_redirects=False)` without a retry adapter. It waits at least three seconds or the stricter robots.txt interval, but has **no automatic HTTP retry or backoff**. A transport exception becomes a per-SKU `FetchError`; the next product is attempted. HTTP 401/403/429/503 instead raises `StopRun` and halts collection. The precise external reason for `RemoteDisconnected` is unknown: the error alone proves neither blocking nor a specific server/proxy fault. No HTTP 403/429 response was observed.

The roughly 30-minute gap has a separate explanation. Catalog state recorded the start of SKU 107353786 at **03:11:09.909** and its successful observation at **03:41:22.679**. macOS `pmset -g log` showed sleep at **03:10:50**, brief DarkWake windows at 03:16:22 and 03:24:02, another sleep at **03:24:08**, and DarkWake at **03:41:21**. The next pipeline log line followed at 03:41:22. Host sleep therefore explains the long wall-clock pause; the exact TCP state during sleep cannot be reconstructed. A shorter socket timeout would not wake the Mac. Reliable scheduling needs an awake host or a later always-on environment.

Transform/Load retained the six valid Raw files and prices. They also encountered old Raw files and correctly treated them as duplicates, so the load's total accepted count is not the number of new live observations. The relevant count is `outcome.new_observations_from_selected_raw=6`. Phase 5.2 added `outcome.run_result`: `completed` without a technical error, `partial` for valid new observations plus an error, and `failed` for an error with no new valid observation or invalid SQL verification. Prefect deliberately marks a technically partial run **Failed** to keep missing retailer fetches visible. Failed attempts do not overwrite the last DB price or successful observation time.

After the pipeline runner was rebuilt, the historical deployment remained active with the same DAILY parameters, cron, timezone, and request limits. Re-registering the schedule changed an internal Prefect schedule ID but did not alter the schedule or trigger a manual DAILY run. Later deployment state is documented in the [current audit](../../MIDTERM_AUDIT.md).

## Historical phase-5.2 checks

The pipeline container passed **60/60 Python tests** using saved HTML fixtures, mock HTTP, and isolated test schemas. Frontend integration passed **8/8 tests**; TypeScript, lint, SvelteKit build, Compose config, diff whitespace, and relative Markdown links passed. Verification reported 26 products, 26 offers, 39 observations, no invalid prices, and no duplicates. These counts are the 17 October snapshot. The only new real data that day came from the already scheduled DAILY run, not from a test fetch.

## File inventory and preservation decision

At audit time, `data/` had 15 catalog run reports, 58 Raw files, and 67 saved HTML/debug files. Six new Raw files, six HTML files, the new report, and catalog state changes came from scheduled DAILY. They were retained. The then-empty `data/import/` and zero-byte `data/seed/data.parquet` were historical state; the latter was subsequently replaced by a checked Parquet bundle. These old counts are **not cleanup criteria**.

| Path | Role | Decision |
| --- | --- | --- |
| `data/catalog/mediamarkt.json` | Active discovery and fetch-state catalog | Keep |
| `data/catalog/mediamarkt_initial.json` | Curated optional INITIAL selection | Keep |
| `docs/evidence/phase2/midterm-live-check.json` | One-off phase-2 live-test catalog, later moved here unchanged | Keep as evidence |
| `data/catalog/runs/*.json` | Unique run IDs, times, scopes, and idempotence/error evidence | Keep |
| `data/raw/mediamarkt/` and `live-check/` | Original observations for transform, replay, backfill, and provenance | Keep at recorded paths |
| `data/raw/digitec/` | Earlier source/provenance evidence | Keep |
| `data/debug/mediamarkt/` and `mediamarkt_product.html` | Saved HTML; transform also uses these for verification and legacy fallback | Keep |
| `data/debug/legacy/` | Historical blocked retailer pages | Keep as evidence |
| `data/initialization.sql` and active migrations | Fresh database creation; migration checksums | Keep unchanged |
| `data/migrations/archive/` | Old, inactive phase-1 migration | Keep as historical evidence |
| `data/queries/` | Read-only verification and catalog SQL | Keep |
| `data/queries/archive/` | Old verification SQL | Keep as historical evidence |

Every catalog run report has its own run ID and historical outcome, including zero-result runs that show idempotence or budget limits. None was deleted. Later cleanup moved only a mock, a one-off catalog, and seven manually supplied chart JSONs; it did not move database-referenced Raw paths. The active [runbook](../../RUN_COMMANDS.md) describes their current locations.

## Repository hygiene

`.env`, Python caches, SvelteKit output, `node_modules`, catalog locks, and temporary files are ignored. Dependency lockfiles remain tracked. A broad root `lib/` ignore pattern was narrowed to `/lib/` so required `frontend/src/lib/` source files are visible to Git. The 17 October audit noted tracked `.idea` files as a cleanup candidate. They were later removed from Git tracking **without deleting the local PyCharm files**. No untracked user data was removed.
