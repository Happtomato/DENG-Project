# Midterm acceptance audit — 21 October 2026

Basis: the official HSLU project description, its midterm deliverables, and the team's Notion checklist. Notion statuses were checked independently. **DONE** here means locally executed and backed by a test, command, or SQL result; it does not claim that a fresh checkout or future live run has been tested. The repository has not yet been submitted. Terraform, GCS, BigQuery, and additional retailer scrapers belong to the final phase.

| Requirement | Status | Evidence | Remaining work | Priority |
| --- | --- | --- | --- | --- |
| PostgreSQL | DONE | `docker compose ps`: `postgres` healthy; `backend.flow verify` connects | Check on a second computer | P0 |
| Local Schema | DONE | `data/initialization.sql`, active migrations `002_midterm.sql` and `003_digitec_chart.sql`; `backend.database.migrate()` runs in Compose and tests | None | P0 |
| Data loaded | DONE | `verify` on 21 Oct: 26 products, 34 offers, 75 actual observations; 3,752 separate Digitec chart points | Recheck before submission | P0 |
| Queryable Data | DONE | PostgreSQL SQL and `verify`: 75 observations, zero invalid CHF prices, zero duplicate offer/timestamp pairs | None | P0 |
| Docker | DONE | Linux containers for database, Prefect, pipeline, and frontend | Independently test Windows/amd64 | P0 |
| Docker Compose | DONE | `docker compose config --quiet` and `docker compose ps`; four running services plus one-off `db_init` | None | P0 |
| Common Network | DONE | Services share `deng-project-network`; pipeline and frontend reach DB/Prefect | None | P0 |
| Modular Batch Ingestion | DONE | One flow with Collect/Transform/Load in `backend/flow.py`; retailer adapter, transform, ingestion; 75 Python tests pass | None | P0 |
| Source → Storage | DONE | 75 real MediaMarkt/manual Digitec observations in `price_history`, source paths in `raw_import`; SQL and replay tests | Additional live volume needs agreed usage limits | P0 |
| Transformation | DONE | `backend/transform.py` normalizes RAM kits, SSD capacity, CHF price and identity; ingestion tests and `hardware_prices` view | None | P0 |
| Justification | DONE | [README](../README.md) and [architecture](ARCHITECTURE.md): capacity normalization supports CHF/GB comparison | Explain in oral defense | P0 |
| Orchestrator | DONE | `prefect_server` healthy; deployment inspect for `DENG MediaMarkt Batch/mediamarkt-daily` | None | P0 |
| Pipeline Workflow | DONE | Prefect Collect/Transform/Load tasks, actual run reports in `data/catalog/runs/`, orchestration tests | None | P0 |
| Scheduling | DONE, active locally | Inspect: `0 3 * * *`, `Europe/Zurich`, `paused=false`, `active=true`; scheduled 21 Oct run actually started | Host must stay awake; agree on retailer usage limits | P0 |
| Reruns | DONE | Re-importing identical Raw evidence creates no second observation; SQL finds zero duplicates | None | P0 |
| Backfills | DONE | REPLAY uses saved Raw files without HTTP and preserves source timestamps; regression tests | Do not invent Digitec daily observations | P0 |
| Architecture v0.2 | DONE | [Architecture](ARCHITECTURE.md) diagram covers Docker, Prefect, Raw, PostgreSQL, offline Digitec, and Parquet | Explain in oral defense | P0 |
| Architecture Changes | DONE | “Compared with v0.1” in [architecture](ARCHITECTURE.md); original plans in `docs/archive/` | None | P0 |
| Setup Instructions | DONE | [README](../README.md), [runbook](RUN_COMMANDS.md), `.env.example`, `Makefile` | Test fresh checkout on second machine | P0 |
| Execution Instructions | DONE | [Runbook](RUN_COMMANDS.md): setup, discovery, initial, daily, replay, verify, offline Digitec, seeds, stop | Live commands need agreed usage limits | P0 |
| Verification Instructions | DONE | `make verify`, `data/queries/verification.sql`, `make check`, `make test`, frontend `/api/verify` | Reviewer executes them independently | P0 |
| Both understand architecture | **MANUAL ACTION / NOT TESTED** | Diagram and code map exist; personal understanding cannot be proven by code | Both students explain data flow, timestamps, Digitec distinction, and failure modes | P0 |
| Explain reliability | **MANUAL ACTION / IN PROGRESS** | [Architecture](ARCHITECTURE.md) and [daily audit](evidence/phase5_2/audit.md) cover partial failures, idempotence, sleep, and limits | Both students rehearse | P0 |
| Explain limitations | **MANUAL ACTION / IN PROGRESS** | README, architecture, and limits below | Both students rehearse | P0 |
| Commit hash / release tag | **MANUAL ACTION / NOT STARTED** | No commit or tag created by Codex | Team fixes a reviewed submission revision | P0 |
| Submit repository link | **MANUAL ACTION / NOT STARTED** | No ILIAS submission performed | Team submits GitHub link plus revision via ILIAS | P0 |
| Meet deadline | **MANUAL ACTION / NOT STARTED** | Deadline: Thursday, 22 Oct 2026, 15:30 Europe/Zurich | Submit on time | P0 |

## Checks and practical limits

On 20 October, `make check` passed (Python syntax, Svelte/TypeScript with zero errors and warnings, Prettier/ESLint); `make test` passed **75/75 Python** and **14/14 frontend integration** tests; the frontend build and `git diff --check` passed. The bundled Parquet snapshot was imported into an isolated empty test schema: 26 products, 34 offers, 63 observations, and 3,752 chart points were preserved; a second import was rejected. The original DB and volumes were not reset. Test-container HTTP checks use fixtures/mocks and triggered no extra live requests.

On 21 October, the automatically scheduled DAILY run `20261021T015016086824Z` selected 22 database offers and made nine HTTP requests. Five successful product fetches added five MediaMarkt observations; three attempts disconnected. Prefect correctly marked the technical partial outcome **Failed**, while retaining the five successful DB rows. It was due at 03:00 but began at 03:50 because the Mac slept; macOS logs show another sleep from 03:50:10 to a brief wake at 04:49:38. A Requests socket timeout cannot keep a host awake. A later DAILY run, already present when this audit was updated, added seven further observations. A fresh read-only `verify` then reported **26 products, 34 offers, 75 observations, 83 loaded Raw files, 18 rejected Raw files, zero import errors, zero invalid CHF prices, and zero duplicate offer/timestamp pairs**. The seed bundle still represents the earlier 63-observation snapshot.

The Raw JSON files referenced by `raw_import.path` are kept at their original paths to preserve provenance and REPLAY. Seven manually supplied Digitec chart JSONs were moved unchanged from `data/raw/digitec/manual import/` to `data/import/digitec/manual-charts/`; their manifest paths were updated. An old Digitec mock now lives with test fixtures, and a one-off live-test catalog is archived under `docs/evidence/phase2/`. No JSON was deleted. `data/catalog/runs/` contains run evidence, not disposable cache. Saved HTML is retained because transformation can use it to verify original product details.

The old zero-byte `data/seed/data.parquet` placeholder was replaced by the genuine `data/seed/midterm-2026-10-20/` bundle. It and newly collected Raw/HTML evidence are still untracked in the local worktree; the team must deliberately review what to include in its submission commit. `.env` and credentials must stay out. Digitec automated access is not approved; its historical retailer chart points are not our own daily observations. New larger retailer request volumes and a reliable always-on scheduler host remain open decisions. None of the final-phase cloud work is needed for the local midterm data flow.
