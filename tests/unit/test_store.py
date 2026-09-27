import sqlite3
import unittest

from appfactory.jobs.store import SCHEMA_VERSION, SchemaError, check_database, connect, migrate, write_tx
from tests.helpers import FactoryTestCase


class StoreTest(FactoryTestCase):
    def test_migrate_idempotent_and_check(self):
        conn = connect(self.paths.db)
        try:
            self.assertEqual(migrate(conn), SCHEMA_VERSION)
            self.assertEqual(migrate(conn), SCHEMA_VERSION)
            report = check_database(conn)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["journal_mode"], "wal")
            self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 2)  # FULL
        finally:
            conn.close()

    def test_newer_schema_refused(self):
        conn = connect(self.paths.db)
        try:
            migrate(conn)
            conn.execute("UPDATE schema_meta SET value = '999' WHERE key = 'schema_version'")
            with self.assertRaises(SchemaError):
                migrate(conn)
        finally:
            conn.close()

    def test_events_are_append_only(self):
        m = self.manager()
        job = m.create_job("p1", "x", payload={"numbers": [1]})
        conn = connect(self.paths.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE events SET type = 'x' WHERE job_id = ?", (job["id"],))
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM events WHERE job_id = ?", (job["id"],))
        finally:
            conn.close()
        self.assertEqual(self.events(m, job["id"])[:2], ["job.created", "job.queued"])

    def test_checkpoints_immutable(self):
        m = self.manager()
        job = m.create_job("p1", "x", payload={"numbers": [1, 2]})
        claim = m.claim("e1", job["id"])
        m.save_checkpoint(claim["attempt_id"], 0, "s0", {"total": 1, "processed": 1})
        conn = connect(self.paths.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM checkpoints")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE checkpoints SET state_json = '{}'")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE checkpoints SET status = 'valid' WHERE status = 'valid'")
            conn.execute("UPDATE checkpoints SET status = 'invalid'")  # única alteração permitida
        finally:
            conn.close()

    def test_database_enforces_one_active_job_per_project(self):
        m = self.manager()
        a = m.create_job("proj", "a", payload={"numbers": [1]})
        b = m.create_job("proj", "b", payload={"numbers": [1]})
        conn = connect(self.paths.db)
        try:
            conn.execute("UPDATE jobs SET state = 'RUNNING' WHERE id = ?", (a["id"],))
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE jobs SET state = 'RUNNING' WHERE id = ?", (b["id"],))
        finally:
            conn.close()

    def test_write_tx_rolls_back(self):
        conn = connect(self.paths.db)
        try:
            migrate(conn)
            with self.assertRaises(RuntimeError):
                with write_tx(conn):
                    conn.execute("INSERT INTO id_counters (scope, value) VALUES ('t', 1)")
                    raise RuntimeError("boom")
            self.assertIsNone(conn.execute("SELECT 1 FROM id_counters WHERE scope = 't'").fetchone())
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
