import json
import unittest

from appfactory.checkpoints.service import canonical, compute_checksum
from appfactory.jobs.store import connect
from tests.helpers import FactoryTestCase


class CheckpointTest(FactoryTestCase):
    def setUp(self):
        super().setUp()
        self.m = self.manager()
        self.job = self.m.create_job("demo", "ck", payload={"numbers": [1, 2, 3]})
        self.aid = self.m.claim("e1", self.job["id"])["attempt_id"]

    def test_create_read_latest_and_append_only(self):
        c1 = self.m.save_checkpoint(self.aid, 0, "s0", {"total": 1, "processed": 1})
        c2 = self.m.save_checkpoint(self.aid, 1, "s1", {"total": 3, "processed": 2})
        self.assertEqual((c1["seq"], c2["seq"]), (1, 2))
        latest = self.m.latest_valid_checkpoint(self.job["id"])
        self.assertEqual(latest["id"], c2["id"])
        self.assertEqual(latest["state"], {"total": 3, "processed": 2})
        self.assertEqual(len(self.m.list_checkpoints(self.job["id"])), 2)   # nada sobrescrito
        job = self.m.get_job(self.job["id"])
        self.assertEqual((job["current_checkpoint_id"], job["current_step"], job["step_index"]), (c2["id"], "s1", 1))

    def test_failure_during_checkpoint_keeps_previous(self):
        good = self.m.save_checkpoint(self.aid, 0, "s0", {"total": 1, "processed": 1})

        def boom():
            raise OSError("disco cheio simulado no meio da gravação")

        with self.assertRaises(OSError):
            self.m.save_checkpoint(self.aid, 1, "s1", {"total": 3, "processed": 2}, before_commit=boom)
        self.assertEqual(self.m.latest_valid_checkpoint(self.job["id"])["id"], good["id"])
        self.assertEqual(len(self.m.list_checkpoints(self.job["id"])), 1)
        self.assertEqual(self.m.get_job(self.job["id"])["current_checkpoint_id"], good["id"])
        self.assertEqual(self.events(self.m, self.job["id"]).count("checkpoint.saved"), 1)

    def test_corrupted_checkpoint_is_skipped_and_marked_invalid(self):
        good = self.m.save_checkpoint(self.aid, 0, "s0", {"total": 1, "processed": 1})
        state_json = canonical({"total": 3, "processed": 2})
        conn = connect(self.paths.db)
        try:  # simula registro parcialmente gravado/corrompido (checksum não confere)
            conn.execute("INSERT INTO checkpoints (id, job_id, seq, attempt_id, kind, step_index, step_name, "
                         "state_json, checksum, status, created_at) VALUES (?, ?, 2, ?, 'step', 1, 's1', ?, ?, "
                         "'valid', 'x')", (self.job["id"] + "-CK0002", self.job["id"], self.aid, state_json[:-3],
                                           compute_checksum(self.job["id"], 2, 1, "step", state_json)))
        finally:
            conn.close()
        self.assertEqual(self.m.latest_valid_checkpoint(self.job["id"])["id"], good["id"])
        m2 = self.manager()          # reinício
        m2.recover()
        cks = {c["id"]: c for c in m2.list_checkpoints(self.job["id"])}
        self.assertEqual(cks[self.job["id"] + "-CK0002"]["status"], "invalid")
        self.assertIn("checkpoint.invalid", self.events(m2, self.job["id"]))
        self.assertEqual(m2.latest_valid_checkpoint(self.job["id"])["id"], good["id"])

    def test_latest_checkpoint_after_restart(self):
        self.m.save_checkpoint(self.aid, 0, "s0", {"total": 1, "processed": 1})
        c2 = self.m.save_checkpoint(self.aid, 1, "s1", {"total": 3, "processed": 2})
        m2 = self.manager()
        self.assertEqual(m2.latest_valid_checkpoint(self.job["id"])["id"], c2["id"])

    def test_state_must_be_json_dict(self):
        with self.assertRaises(TypeError):
            self.m.save_checkpoint(self.aid, 0, "s0", ["não", "dict"])
        with self.assertRaises(TypeError):
            self.m.save_checkpoint(self.aid, 0, "s0", {"x": object()})
        json.dumps({})  # sanidade


if __name__ == "__main__":
    unittest.main()
