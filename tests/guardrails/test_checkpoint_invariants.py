"""I2 — checkpoints de passo/task/marco são criados e restauráveis (09 §1)."""
import importlib
import sqlite3
import unittest

from appfactory.jobs import states as S
from appfactory.jobs.executor import Executor
from appfactory.jobs.store import connect
from tests.guardrails._support import guard
from tests.helpers import FactoryTestCase


class CheckpointInvariants(FactoryTestCase):
    faults = True

    @guard("I2.step_checkpoints")
    def test_step_checkpoints_created_immutable_restorable(self):
        m = self.manager()
        job = m.create_job("demo", "I2", payload={"numbers": [1, 2, 3, 4], "_faults": {"fail_at_step": 2}})
        Executor(m).run(job["id"])                           # falha no passo 2: checkpoints 0 e 1 ficam
        m2 = self.manager()                                  # reinício
        point = m2.latest_valid_checkpoint(job["id"])
        self.assertEqual(point["step_index"], 1)
        self.assertEqual(point["state"], {"total": 3, "processed": 2})
        conn = connect(self.paths.db)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE checkpoints SET state_json = '{}'")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM checkpoints")
        finally:
            conn.close()
        self.assertEqual(Executor(m2).run(job["id"]).final_state, S.COMPLETED)

    @guard("I2.task_milestone_checkpoints")
    def test_task_and_milestone_checkpoints(self):
        importlib.import_module("appfactory.checkpoints.snapshot")   # fatia 2.7


if __name__ == "__main__":
    unittest.main()
