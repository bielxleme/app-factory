import re
import threading
import unittest

from appfactory.jobs import states as S
from appfactory.jobs.errors import InvalidTransition, JobNotFound, ValidationRequired
from appfactory.jobs.executor import Executor
from tests.helpers import FactoryTestCase, FakeClock


class IdentityTest(FactoryTestCase):
    def test_create_job_fields(self):
        m = self.manager()
        job = m.create_job("demo", "somar números", payload={"numbers": [1, 2]}, priority=2)
        self.assertRegex(job["id"], r"^JOB-\d{8}-\d{4}$")
        self.assertEqual(job["state"], S.QUEUED)
        self.assertEqual(job["project"], "demo")
        self.assertEqual(job["intent"], "somar números")
        for k in ("created_at", "queued_at", "updated_at"):
            self.assertTrue(job[k])
        self.assertIsNone(job["started_at"])
        self.assertIsNone(job["current_checkpoint_id"])

    def test_ids_unique_sequential_and_concurrent(self):
        managers = [self.manager() for _ in range(4)]
        ids, errors = [], []

        def worker(mgr):
            try:
                for _ in range(15):
                    ids.append(mgr.create_job("p", "x", payload={"numbers": [1]})["id"])
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(mg,)) for mg in managers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(ids), 60)
        self.assertEqual(len(set(ids)), 60)

    def test_input_validation(self):
        m = self.manager()
        for bad in ("", "com espaço", "../x", "a" * 65):
            with self.assertRaises(ValueError):
                m.create_job(bad, "x", payload={"numbers": [1]})
        with self.assertRaises(ValueError):
            m.create_job("p", "   ", payload={"numbers": [1]})
        with self.assertRaises(ValueError):
            m.create_job("p", "x", payload={"numbers": [1], "codigo": "import os"})
        with self.assertRaises(ValueError):
            m.create_job("p", "x", payload={"numbers": [1], "_faults": {"crash_at_step": 0}})  # sem permissão
        with self.assertRaises(Exception):
            m.create_job("p", "x", job_type="shell.exec", payload={})
        with self.assertRaises(JobNotFound):
            m.get_job("JOB-00000000-0000")


class PersistenceTest(FactoryTestCase):
    def test_job_state_events_timestamps_survive_restart(self):
        m1 = self.manager()
        job = m1.create_job("demo", "persistir", payload={"numbers": [1, 2, 3]})
        Executor(m1).run(job["id"])
        before = m1.get_job(job["id"])
        hist_before = m1.history(job["id"])
        del m1
        m2 = self.manager()  # "reinício" do processo: nova instância, mesmo SQLite
        after = m2.get_job(job["id"])
        self.assertEqual(after, before)
        self.assertEqual(after["state"], S.COMPLETED)
        self.assertTrue(after["completed_at"] and after["started_at"])
        self.assertEqual(m2.history(job["id"]), hist_before)

    def test_queue_survives_restart_and_order(self):
        clock = FakeClock()
        m1 = self.manager(clock=clock)
        low = m1.create_job("a", "baixa", payload={"numbers": [1]}, priority=2)
        clock.advance(1)
        high = m1.create_job("b", "alta", payload={"numbers": [1]}, priority=1)
        clock.advance(1)
        urgent = m1.create_job("c", "P0", payload={"numbers": [1]}, priority=0)
        del m1
        m2 = self.manager(clock=clock)
        self.assertEqual([j["id"] for j in m2.queue()], [urgent["id"], high["id"], low["id"]])
        self.assertTrue(all(j["state"] == S.QUEUED for j in m2.queue()))
        clock.advance(61 * 60)  # envelhecimento: P2 sobe até P1 (limite)
        self.assertEqual(m2.queue()[0]["id"], urgent["id"])
        self.assertEqual(m2.queue()[1]["id"], low["id"])

    def test_runtime_mirror_is_not_source_of_truth(self):
        m = self.manager()
        job = m.create_job("demo", "espelho", payload={"numbers": [1]})
        self.assertTrue(self.paths.runtime_job_json.exists())
        self.assertTrue(self.paths.job_log(job["id"]).exists())
        self.paths.runtime_job_json.unlink()
        self.paths.job_log(job["id"]).unlink()
        m2 = self.manager()
        self.assertEqual(m2.get_job(job["id"])["state"], S.QUEUED)
        self.assertEqual(self.events(m2, job["id"])[:2], ["job.created", "job.queued"])


class CompletionTest(FactoryTestCase):
    def _run_all_steps(self, m, job):
        claim = m.claim("e1", job["id"])
        aid = claim["attempt_id"]
        state = {"total": 0, "processed": 0}
        for i, n in enumerate([1, 2, 3]):
            state = {"total": state["total"] + n, "processed": i + 1}
            m.save_checkpoint(aid, i, f"s{i}", state)
        return aid

    def test_completed_only_after_validation(self):
        m = self.manager()
        job = m.create_job("demo", "v", payload={"numbers": [1, 2, 3]})
        aid = self._run_all_steps(m, job)
        with self.assertRaises(ValidationRequired):
            m.complete(aid)                          # processo terminou, mas sem validação
        m.record_validation(aid, False, {"motivo": "teste"})
        with self.assertRaises(ValidationRequired):
            m.complete(aid)                          # validação reprovada não basta
        with m._tx() as conn:                       # nem uma transição direta consegue
            with self.assertRaises(ValidationRequired):
                m._transition(conn, m._get_job(conn, job["id"]), S.COMPLETED, reason="x", actor="t")
        m.record_validation(aid, True, {"ok": True})
        self.assertEqual(m.complete(aid)["state"], S.COMPLETED)

    def test_validation_must_cover_latest_checkpoint(self):
        m = self.manager()
        job = m.create_job("demo", "v", payload={"numbers": [1, 2, 3]})
        aid = self._run_all_steps(m, job)
        m.record_validation(aid, True, {"ok": True})
        m.save_checkpoint(aid, 2, "s2-bis", {"total": 99, "processed": 3})  # estado mudou depois
        with self.assertRaises(ValidationRequired):
            m.complete(aid)

    def test_validation_failure_goes_to_failed(self):
        m = self.manager()
        job = m.create_job("demo", "v", payload={"numbers": [1, 2], "expected_sum": 999})
        res = Executor(m).run(job["id"])
        self.assertEqual(res.final_state, S.FAILED)
        self.assertIn("validation_failed", m.get_job(job["id"])["fail_reason"])
        self.assertTrue(m.get_job(job["id"])["failed_at"])


class FailureTest(FactoryTestCase):
    faults = True

    def test_step_failure_retries_then_completes(self):
        m = self.manager()
        job = m.create_job("demo", "f", payload={"numbers": [1, 2, 3], "_faults": {"fail_at_step": 1,
                                                                                  "fail_attempts": 1}})
        r1 = Executor(m).run(job["id"])
        self.assertEqual(r1.final_state, S.RUNNING)
        self.assertEqual(m.get_job(job["id"])["state_reason"], "retry_pending")
        self.assertEqual(m.latest_valid_checkpoint(job["id"])["step_index"], 0)
        r2 = Executor(m).run(job["id"])               # retoma do passo 1
        self.assertEqual(r2.final_state, S.COMPLETED)
        self.assertEqual(m.latest_valid_checkpoint(job["id"])["state"]["total"], 6)

    def test_repeated_failures_block_for_human(self):
        m = self.manager()
        job = m.create_job("demo", "f", payload={"numbers": [1, 2], "_faults": {"fail_at_step": 0,
                                                                              "fail_attempts": 99}})
        for _ in range(3):
            Executor(m).run(job["id"])
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)
        self.assertIn("needs_human", j["state_reason"])
        with self.assertRaises(InvalidTransition):
            Executor(m).run(job["id"])
        self.assertEqual(m.resume(job["id"])["state"], S.QUEUED)

    def test_fatal_failure(self):
        m = self.manager()
        job = m.create_job("demo", "f", payload={"numbers": [1, 2], "_faults": {"fatal_at_step": 1}})
        self.assertEqual(Executor(m).run(job["id"]).final_state, S.FAILED)
        self.assertEqual(m.resume(job["id"])["state"], S.QUEUED)   # requeue manual (03 §2)

    def test_cancel(self):
        m = self.manager()
        job = m.create_job("demo", "c", payload={"numbers": [1]})
        self.assertEqual(m.cancel(job["id"])["state"], S.CANCELLED)
        with self.assertRaises(InvalidTransition):
            m.cancel(job["id"])


if __name__ == "__main__":
    unittest.main()
