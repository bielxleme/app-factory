import os
import threading
import time
import unittest

from appfactory.jobs import states as S
from appfactory.jobs.errors import FactoryStopped, InvalidTransition, LeaseLost
from appfactory.jobs.executor import Executor
from tests.helpers import FactoryTestCase, FakeClock, FakeLiveness


class JobStopTest(FactoryTestCase):
    faults = True

    def _wait(self, cond, timeout=10):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.02)
        return False

    def test_stop_running_job_gracefully(self):
        m = self.manager()
        job = m.create_job("demo", "parar", payload={"numbers": list(range(1, 21)), "step_delay_ms": 50})
        result = {}
        t = threading.Thread(target=lambda: result.setdefault("r", Executor(m).run(job["id"])))
        t.start()
        self.assertTrue(self._wait(lambda: (m.latest_valid_checkpoint(job["id"]) or {}).get("step_index", -1) >= 1))
        tmp_root = self.paths.jobs_dir / job["id"] / "tmp"
        self.assertTrue(any(tmp_root.iterdir()))                       # recurso temporário existe
        stopping = m.request_stop(job["id"], reason="teste")
        self.assertEqual(stopping["state"], S.STOPPING)
        self.assertTrue(stopping["stop_requested_at"])
        t.join(timeout=15)
        self.assertEqual(result["r"].final_state, S.STOPPED)
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.STOPPED)
        self.assertTrue(j["stopped_at"])
        self.assertIsNone(j["current_attempt_id"])
        self.assertIn((S.RUNNING, S.STOPPING), self.transitions(m, job["id"]))
        self.assertIn((S.STOPPING, S.STOPPED), self.transitions(m, job["id"]))
        last = m.latest_valid_checkpoint(job["id"])
        self.assertEqual(last["kind"], "stop")                          # estado salvo na parada
        self.assertLess(last["step_index"], 19)
        self.assertEqual(list(tmp_root.iterdir()), [])                  # temporários finalizados
        self.assertEqual(m.attempts(job["id"])[-1]["outcome"], "stopped")
        # retomada explícita continua do checkpoint da parada e completa
        m.resume(job["id"])
        self.assertEqual(Executor(m).run(job["id"]).final_state, S.COMPLETED)
        self.assertEqual(m.latest_valid_checkpoint(job["id"])["state"]["total"], sum(range(1, 21)))

    def test_stop_persists_across_restart_while_executor_dead(self):
        clock, live = FakeClock(), FakeLiveness()
        live.alive.add(4242)
        m = self.manager(clock=clock, liveness=live)
        job = m.create_job("demo", "parar", payload={"numbers": [1, 2, 3]})
        claim = m.claim("e1", job["id"], pid=4242)
        m.save_checkpoint(claim["attempt_id"], 0, "s0", {"total": 1, "processed": 1})
        m.request_stop(job["id"])
        del m
        m2 = self.manager(clock=clock, liveness=live)                  # reinício: STOP continua registrado
        self.assertEqual(m2.get_job(job["id"])["state"], S.STOPPING)
        self.assertTrue(m2.heartbeat(claim["attempt_id"])["stop"])
        live.alive.clear()                                              # executor morreu antes de concluir
        report = m2.recover()
        self.assertIn(job["id"], report["stopped"])
        self.assertEqual(m2.get_job(job["id"])["state"], S.STOPPED)     # parada honrada, não retomada
        self.assertEqual(m2.get_job(job["id"])["resume_from"], job["id"] + "-CK0001")

    def test_stop_non_running_and_terminal(self):
        m = self.manager()
        q = m.create_job("demo", "fila", payload={"numbers": [1]})
        self.assertEqual(m.request_stop(q["id"])["state"], S.STOPPED)
        self.assertEqual(m.request_stop(q["id"])["state"], S.STOPPED)   # idempotente
        done = m.create_job("demo2", "ok", payload={"numbers": [1]})
        Executor(m).run(done["id"])
        with self.assertRaises(InvalidTransition):
            m.request_stop(done["id"])

    def test_failure_during_stop_is_degraded_but_safe(self):
        m = self.manager()
        job = m.create_job("demo", "parar", payload={"numbers": list(range(20)), "step_delay_ms": 50,
                                                     "_faults": {"fail_stop_checkpoint": True}})
        result = {}
        t = threading.Thread(target=lambda: result.setdefault("r", Executor(m).run(job["id"])))
        t.start()
        self.assertTrue(self._wait(lambda: m.latest_valid_checkpoint(job["id"]) is not None))
        m.request_stop(job["id"])
        t.join(timeout=15)
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.STOPPED)
        self.assertIn("job.stop_degraded", self.events(m, job["id"]))
        last = m.latest_valid_checkpoint(job["id"])
        self.assertEqual(last["kind"], "step")                          # o último válido anterior segue lá
        self.assertEqual(j["resume_from"], last["id"])

    def test_stopped_executor_cannot_write(self):
        m = self.manager()
        job = m.create_job("demo", "x", payload={"numbers": [1, 2]})
        aid = m.claim("e1", job["id"])["attempt_id"]
        m.request_stop(job["id"])
        m.save_checkpoint(aid, 0, "s0", {"total": 1, "processed": 1})  # STOPPING ainda aceita o checkpoint
        m.finish_stop(aid)
        with self.assertRaises(LeaseLost):
            m.save_checkpoint(aid, 1, "s1", {"total": 3, "processed": 2})


class FactoryStopTest(FactoryTestCase):
    def test_factory_stop_blocks_dispatch_and_needs_confirmation(self):
        m = self.manager()
        job = m.create_job("demo", "x", payload={"numbers": [1]})
        self.assertTrue(m.stop_factory(reason="teste"))
        self.assertTrue(m.factory_stop_flag.is_set())                   # espelho em memória
        with self.assertRaises(FactoryStopped):
            Executor(m).run(job["id"])
        m2 = self.manager()                                             # persistido
        self.assertTrue(m2.factory_stop_flag.is_set())
        with self.assertRaises(PermissionError):
            m2.resume_factory()
        self.assertTrue(m2.resume_factory(confirmed=True))
        self.assertFalse(m2.factory_stop_flag.is_set())
        self.assertEqual(Executor(m2).run(job["id"]).final_state, S.COMPLETED)

    def test_stop_file_triggers_and_deleting_does_not_release(self):
        m = self.manager()
        self.paths.stop_file.write_text("", encoding="utf-8")
        m2 = self.manager()
        self.assertTrue(m2.factory_stop_state()["active"])
        self.assertEqual(m2.factory_stop_state()["reason"], "file_trigger")
        os.remove(self.paths.stop_file)
        m3 = self.manager()
        self.assertTrue(m3.factory_stop_state()["active"])              # apagar o arquivo NÃO libera
        self.assertTrue(m3.factory_stop_flag.is_set())

    def test_running_job_pauses_on_factory_stop_and_requeues_on_release(self):
        m = self.manager()
        job = m.create_job("demo", "x", payload={"numbers": list(range(20)), "step_delay_ms": 50})
        result = {}
        t = threading.Thread(target=lambda: result.setdefault("r", Executor(m).run(job["id"])))
        t.start()
        end = time.time() + 10
        while m.latest_valid_checkpoint(job["id"]) is None and time.time() < end:
            time.sleep(0.02)
        m.stop_factory(reason="teste")
        t.join(timeout=15)
        j = m.get_job(job["id"])
        self.assertEqual((j["state"], j["state_reason"]), (S.PAUSED, "factory_stop"))
        with self.assertRaises(FactoryStopped):
            m.resume(job["id"])
        m.resume_factory(confirmed=True)
        self.assertEqual(m.get_job(job["id"])["state"], S.QUEUED)
        self.assertEqual(Executor(m).run(job["id"]).final_state, S.COMPLETED)


if __name__ == "__main__":
    unittest.main()
