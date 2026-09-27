"""I1 — todo evento de ciclo de vida é logado; audit.jsonl com cadeia de hashes íntegra (09 §1)."""
import json
import sqlite3
import unittest

from appfactory.jobs import states as S
from appfactory.jobs.executor import Executor
from appfactory.jobs.store import connect
from appfactory.logs import audit
from tests.guardrails._support import guard
from tests.helpers import FactoryTestCase


class LoggingInvariants(FactoryTestCase):
    @guard("I1.events_append_only")
    def test_lifecycle_events_recorded_and_immutable(self):
        m = self.manager()
        job = m.create_job("demo", "I1", payload={"numbers": [1, 2, 3]})
        self.assertEqual(Executor(m).run(job["id"]).final_state, S.COMPLETED)
        self.assertEqual(self.transitions(m, job["id"]), [(S.QUEUED, S.RUNNING), (S.RUNNING, S.COMPLETED)])
        types = self.events(m, job["id"])
        for t in ("job.created", "attempt.started", "checkpoint.saved", "validation.recorded", "job.completed"):
            self.assertIn(t, types)
        conn = connect(self.paths.db)
        try:
            for sql in ("DELETE FROM events", "UPDATE events SET reason = 'x'"):
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(sql)
        finally:
            conn.close()

    @guard("I1.audit_chain")
    def test_audit_chain_detects_tampering(self):
        path = audit.audit_path(self.paths)
        for i in range(4):
            audit.append(path, {"type": "t", "i": i})
        self.assertTrue(audit.verify_chain(path)[0])
        lines = path.read_text(encoding="utf-8").splitlines()
        e = json.loads(lines[1])
        e["i"] = -1
        path.write_text("\n".join([lines[0], json.dumps(e)] + lines[2:]) + "\n", encoding="utf-8")
        self.assertEqual(audit.verify_chain(path)[:2], (False, 1))
        path.write_text("\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8")
        self.assertFalse(audit.verify_chain(path)[0])

    @guard("I1.stop_audited")
    def test_stop_set_and_release_audited(self):
        m = self.manager()
        m.stop_factory(reason="guardrail-test")
        m.resume_factory(actor="user", confirmed=True)
        path = audit.audit_path(self.paths)
        types = [json.loads(x)["type"] for x in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(types, ["stop.set", "stop.released"])
        self.assertTrue(audit.verify_chain(path)[0])


if __name__ == "__main__":
    unittest.main()
