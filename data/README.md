# Data directory

This folder holds both the database definition and source evidence. Keep the dated Raw paths: `raw_import.path` and REPLAY use them for provenance and idempotent backfills.

| Folder | Purpose | Retention |
| --- | --- | --- |
| `catalog/` | MediaMarkt and SwissHardware candidate URLs, selections, and JSON run reports | Keep; a parsed candidate is not proof of a database import. |
| `raw/` | Timestamped source captures and SwissHardware daily request journals | Keep at their recorded paths. These are source evidence, not cache. |
| `debug/` | Saved MediaMarkt HTML used by transformation checks, plus historical blocked-page evidence | Keep while those checks and provenance remain in use. |
| `import/` | Team-supplied Digitec page/chart files for offline import | Keep original files; private incoming material stays ignored by Git. |
| `migrations/` | Active additive PostgreSQL migrations | Keep; applied checksums are recorded in `schema_migration`. Historical SQL lives in `docs/archive/sql/`. |
| `queries/` | Read-only SQL for reviewer verification and catalog statistics | Keep. |
| `seed/` | Checked Parquet snapshot for an empty database | Keep at least one complete bundle with its manifest. It is not a live source or a replacement for Raw evidence. |

`initialization.sql` defines the initial schema. The latest `seed/2026-10-25-081750-415685/` bundle contains 215 products, 229 offers, and 424 own price observations and was tested by restoring it into an isolated schema. The older `seed/midterm-2026-10-25/` directory contains a 26-product snapshot with 79 observations; its name is newer than the data inside. `db_init` chooses the newest bundle by manifest time but only imports into an empty schema. Never delete the Docker PostgreSQL volume to tidy this directory.
