"""Explicit versioned migrations and short transactions."""
import hashlib
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]


def connect():
    if os.environ.get("DATABASE_URL"):
        return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row)
    return psycopg.connect(host=os.getenv("POSTGRES_HOST", "localhost"),
                          port=os.getenv("POSTGRES_PORT", "5432"),
                          dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
                          password=os.environ["POSTGRES_PASSWORD"],
                          connect_timeout=10, autocommit=True, row_factory=dict_row)


def migrate(conn):
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(91342001)")
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migration (
            name TEXT PRIMARY KEY, sha256 TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        if conn.execute("SELECT 1 FROM schema_migration WHERE name='002_pipeline.sql'").fetchone():
            raise ValueError('Phase-1 schema already applied: stop and plan an additive migration; no data was changed')
        paths = [ROOT / "data/initialization.sql", *sorted((ROOT / "data/migrations").glob("*.sql"))]
        for path in paths:
            source = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(source.encode()).hexdigest()
            previous = conn.execute("SELECT sha256 FROM schema_migration WHERE name=%s", (path.name,)).fetchone()
            if previous:
                if previous["sha256"] != checksum:
                    raise ValueError(f"Applied migration changed: {path.name}. Add a new migration instead.")
                continue
            # The original initializer wraps itself in BEGIN/COMMIT. The migration
            # runner owns the transaction so its ledger commits atomically too.
            source = "\n".join(line for line in source.splitlines() if line.strip() not in {"BEGIN;", "COMMIT;"})
            conn.execute(source)
            conn.execute("INSERT INTO schema_migration(name,sha256) VALUES (%s,%s)", (path.name, checksum))


def verification(conn):
    counts = {name:conn.execute(f'SELECT count(*) AS n FROM {name}').fetchone()['n']
              for name in ('product','retailer_product','price_history')}
    counts['invalid_prices'] = conn.execute("SELECT count(*) AS n FROM price_history WHERE price_chf<=0 OR currency<>'CHF'").fetchone()['n']
    counts['duplicate_observations'] = conn.execute('''SELECT count(*) AS n FROM (
        SELECT retailer_product_id,collected_at FROM price_history
        GROUP BY 1,2 HAVING count(*)>1) d''').fetchone()['n']
    raw = conn.execute('SELECT status,reason,count(*) AS files FROM raw_import GROUP BY 1,2 ORDER BY 1,2').fetchall()
    counts['accepted_raw_files'] = sum(r['files'] for r in raw if r['status'] in ('loaded','duplicate'))
    counts['rejected_raw_files'] = sum(r['files'] for r in raw if r['status']=='rejected')
    counts['error_raw_files'] = sum(r['files'] for r in raw if r['status']=='error')
    categories = conn.execute('SELECT category,count(*) AS observations FROM hardware_prices GROUP BY 1 ORDER BY 1').fetchall()
    data_loaded = all(counts[name]>0 for name in ('product','retailer_product','price_history'))
    technically_valid = counts['invalid_prices']==0 and counts['duplicate_observations']==0
    return {'counts':counts,'raw_files':raw,'categories':categories,
            'technically_valid':technically_valid,'data_loaded':data_loaded,
            'ok':technically_valid and data_loaded}


def active_products(conn):
    """Existing imported MediaMarkt offers; failures never delete or deactivate them."""
    return conn.execute('''SELECT rp.retailer_sku, rp.product_url, lower(c.name) AS category,
        b.name AS brand, p.product_name AS title,
        rp.first_seen_at, latest.collected_at AS last_success_at, latest.path AS last_record
        FROM retailer_product rp JOIN retailer r USING(retailer_id)
        JOIN product p USING(product_id) JOIN category c USING(category_id)
        JOIN brand b USING(brand_id)
        JOIN LATERAL (
            SELECT ph.collected_at, ri.path FROM price_history ph
            LEFT JOIN raw_import ri ON ri.sha256=ph.raw_sha256
            WHERE ph.retailer_product_id=rp.retailer_product_id
            ORDER BY ph.collected_at DESC LIMIT 1
        ) latest ON true
        WHERE r.name='MediaMarkt' AND rp.product_url IS NOT NULL
          AND lower(c.name) IN ('gpu','ram','ssd')
        ORDER BY rp.retailer_sku''').fetchall()
