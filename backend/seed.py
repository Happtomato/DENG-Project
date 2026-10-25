"""Optional, offline PostgreSQL snapshot for a fresh Midterm database.

The files are a reproducibility aid. Raw JSON and the normal REPLAY pipeline
remain the source evidence; importing a snapshot never creates observations.
"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from psycopg import sql


# Foreign-key order. Keep this list explicit so a bundle cannot choose SQL tables.
TABLES = (
    'brand', 'category', 'retailer', 'raw_import', 'product',
    'gpu_details', 'ram_details', 'ssd_details', 'retailer_product',
    'price_history', 'retailer_price_change',
)
FORMAT_VERSION = 1
SEED_ROOT = Path(__file__).resolve().parents[1] / 'data/seed'


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _columns(conn, table):
    rows = conn.execute(
        """SELECT column_name,is_identity FROM information_schema.columns
           WHERE table_schema=current_schema() AND table_name=%s
           ORDER BY ordinal_position""", (table,)
    ).fetchall()
    if not rows:
        raise ValueError(f'Missing schema table: {table}')
    return [row['column_name'] for row in rows], [
        row['column_name'] for row in rows if row['is_identity'] == 'YES'
    ]


def export_tables(conn, directory):
    """Write one Parquet file per populated table; refuse to replace a bundle."""
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError(f'Snapshot already exists: {directory}')
    directory.mkdir(parents=True)
    manifest = {'format_version': FORMAT_VERSION,
                'created_at': datetime.now(timezone.utc).isoformat(), 'tables': []}
    try:
        for name in TABLES:
            columns, _ = _columns(conn, name)
            rows = conn.execute(
                sql.SQL('SELECT {} FROM {}').format(
                    sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(name)
                )
            ).fetchall()
            entry = {'name': name, 'rows': len(rows), 'sha256': None}
            if rows:
                path = directory / f'{name}.parquet'
                pq.write_table(pa.Table.from_pylist([dict(row) for row in rows]), path,
                               compression='zstd')
                entry['sha256'] = _digest(path)
            manifest['tables'].append(entry)
        (directory / 'manifest.json').write_text(
            json.dumps(manifest, indent=2) + '\n', encoding='utf-8'
        )
    except Exception:
        # Keep partial output for diagnosis; never replace a complete older bundle.
        raise
    return manifest


def _bundle_date(directory):
    """Use manifest time; older bundles have a date in their directory name."""
    manifest_path = directory / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    created_at = manifest.get('created_at')
    if created_at is not None:
        value = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        if value.tzinfo is None:
            raise ValueError(f'Seed timestamp has no timezone: {directory}')
        return value.astimezone(timezone.utc).timestamp()
    match = re.search(r'20\d{2}-\d{2}-\d{2}(?:-\d{6})?', directory.name)
    if match:
        value = match.group()
        pattern = '%Y-%m-%d-%H%M%S' if len(value) > 10 else '%Y-%m-%d'
        return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc).timestamp()
    return manifest_path.stat().st_mtime


def latest_seed_dir(root=SEED_ROOT):
    """Choose the newest complete bundle, independently of directory ordering."""
    root = Path(root)
    if not root.is_dir():
        return None
    bundles = [path for path in root.iterdir()
               if path.is_dir() and (path / 'manifest.json').is_file()]
    return max(bundles, key=lambda path: (_bundle_date(path), path.name)) if bundles else None


def import_latest_if_empty(conn, root=SEED_ROOT):
    """Initialize only an entirely empty business schema; preserve existing rows."""
    for name in TABLES:
        _columns(conn, name)
        if conn.execute(sql.SQL('SELECT 1 FROM {} LIMIT 1').format(sql.Identifier(name))).fetchone():
            return {'status': 'skipped_nonempty'}
    directory = latest_seed_dir(root)
    if directory is None:
        return {'status': 'no_bundle'}
    return {'status': 'imported', 'bundle': str(directory),
            'tables': import_tables(conn, directory)}


def _validated_bundle(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format_version') != FORMAT_VERSION:
        raise ValueError('Unsupported Parquet snapshot version')
    entries = manifest.get('tables')
    if not isinstance(entries, list) or [row.get('name') for row in entries] != list(TABLES):
        raise ValueError('Snapshot has an unexpected table list or order')
    tables = []
    for entry in entries:
        name, count, digest = entry['name'], entry['rows'], entry['sha256']
        if not isinstance(count, int) or count < 0:
            raise ValueError(f'Invalid row count for {name}')
        if count == 0:
            if digest is not None or (directory / f'{name}.parquet').exists():
                raise ValueError(f'Unexpected data for empty table {name}')
            tables.append((name, []))
            continue
        path = directory / f'{name}.parquet'
        if _digest(path) != digest:
            raise ValueError(f'Parquet checksum mismatch: {name}')
        rows = pq.read_table(path).to_pylist()
        if len(rows) != count:
            raise ValueError(f'Parquet row count mismatch: {name}')
        tables.append((name, rows))
    return tables


def import_tables(conn, directory):
    """Restore a checked snapshot into an initialized *empty* schema atomically."""
    tables = _validated_bundle(directory)
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(91342004)')
        for name, _ in tables:
            _columns(conn, name)
            if conn.execute(sql.SQL('SELECT 1 FROM {} LIMIT 1').format(sql.Identifier(name))).fetchone():
                raise ValueError(f'Target table is not empty: {name}')
        for name, rows in tables:
            if not rows:
                continue
            schema_columns, identities = _columns(conn, name)
            columns = list(rows[0])
            missing = set(schema_columns) - set(columns)
            optional_old_bundle = name == 'retailer_product' and missing <= {'is_active', 'tracking_reason'}
            if (set(columns) - set(schema_columns) or
                    (missing and not optional_old_bundle) or
                    any(set(row) != set(columns) for row in rows)):
                raise ValueError(f'Parquet columns do not match schema: {name}')
            statement = sql.SQL('INSERT INTO {} ({}) {} VALUES ({})').format(
                sql.Identifier(name),
                sql.SQL(',').join(map(sql.Identifier, columns)),
                sql.SQL('OVERRIDING SYSTEM VALUE') if identities else sql.SQL(''),
                sql.SQL(',').join(sql.Placeholder() for _ in columns),
            )
            with conn.cursor() as cursor:
                cursor.executemany(statement, [[row[column] for column in columns] for row in rows])
            for column in identities:
                sequence = conn.execute('SELECT pg_get_serial_sequence(%s,%s) AS seq',
                                        (name, column)).fetchone()['seq']
                if sequence:
                    highest = conn.execute(
                        sql.SQL('SELECT max({}) AS n FROM {}').format(
                            sql.Identifier(column), sql.Identifier(name)
                        )
                    ).fetchone()['n']
                    conn.execute('SELECT setval(%s::regclass,%s,true)', (sequence, highest))
    return {name: len(rows) for name, rows in tables}
