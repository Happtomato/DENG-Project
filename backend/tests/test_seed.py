"""Parquet roundtrip uses two disposable schemas and one saved real observation."""
import tempfile
import unittest
import uuid
from pathlib import Path

from psycopg import sql

from backend.database import ROOT, connect, migrate, verification
from backend.ingestion import ingest_file
from backend.seed import export_tables, import_tables
from backend.transform import transform_file


class SeedTests(unittest.TestCase):
    def test_export_import_preserves_observation_and_refuses_overwrite(self):
        source = 'seed_source_' + uuid.uuid4().hex
        target = 'seed_target_' + uuid.uuid4().hex
        with connect() as conn, tempfile.TemporaryDirectory() as directory:
            for name in (source, target):
                conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
            try:
                conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(source)))
                migrate(conn)
                raw = next((ROOT / 'data/raw/mediamarkt').glob('2230728_*.json'))
                item = transform_file(raw)
                self.assertEqual(ingest_file(conn, Path(item['path']), transformed=item)['status'],
                                 'loaded')
                manifest = export_tables(conn, Path(directory) / 'snapshot')
                self.assertEqual(next(row['rows'] for row in manifest['tables']
                                      if row['name'] == 'price_history'), 1)

                conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(target)))
                migrate(conn)
                restored = import_tables(conn, Path(directory) / 'snapshot')
                self.assertEqual(restored['price_history'], 1)
                self.assertEqual(restored['retailer_price_change'], 0)
                self.assertTrue(verification(conn)['ok'])
                actual = conn.execute('SELECT collected_at,price_chf FROM price_history').fetchone()
                self.assertEqual(actual['collected_at'], item['observation']['observed'])
                self.assertEqual(actual['price_chf'], item['observation']['price'])
                with self.assertRaisesRegex(ValueError, 'not empty'):
                    import_tables(conn, Path(directory) / 'snapshot')
            finally:
                conn.execute('SET search_path TO public')
                for name in (target, source):
                    conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))
