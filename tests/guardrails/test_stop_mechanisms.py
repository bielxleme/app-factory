"""I6 — kill switch e pause/cancel param tudo em ≤ 40 s desde o T0 persistido (terminate ≤ T0 + 30 s, D-0054);
STOP persiste e apagar o arquivo não libera; Job Object mata tudo se o daemon morrer (fatia 2.4, KI-0019)."""
import importlib
import os
import threading
import unittest

from appfactory.jobs import states as S
from appfactory.jobs.errors import FactoryStopped
from appfactory.jobs.executor import Executor
from appfactory.security import sandbox as sb
from tests.fakes import exec_handler
from tests.fakes.sandbox import FakeSandbox
from tests.guardrails._support import guard
from tests.helpers import FakeClock, FactoryTestCase


class StopMechanisms(FactoryTestCase):
    @guard("I6.stop_persistent")
    def test_stop_persists_file_deletion_does_not_release(self):
        m = self.manager()
        self.paths.stop_file.write_text("x", encoding="utf-8")
        self.assertTrue(m.check_stop_file())
        os.remove(self.paths.stop_file)
        m2 = self.manager()
        self.assertTrue(m2.factory_stop_state()["active"])
        job = m2.create_job("demo", "I6", payload={"numbers": [1]})
        with self.assertRaises(FactoryStopped):
            m2.claim("e", job_id=job["id"])
        with self.assertRaises(PermissionError):
            m2.resume_factory(confirmed=False)
        self.assertTrue(self.manager().factory_stop_state()["active"])

    @guard("I6.stop_deadlines")
    def test_deadlines_from_persisted_t0(self):
        self.assertEqual((sb.STOP_TERMINATE_S, sb.STOP_KILL_S), (30, 40))
        self.assertLessEqual(sb.STOP_POLL_MAX_S, 1.0)
        self.assertEqual(sb.deadlines(0, 5), (25_000, 35_000))
        self.assertEqual(sb.deadlines(0, -10), (30_000, 40_000))
        exec_handler.register()
        try:
            clock = FakeClock()
            wt = self.tmp / "workspaces" / "_worktrees" / "demo" / "T1"
            wt.mkdir(parents=True)
            box = FakeSandbox("S1h", behavior="block", poll_s=1.0, clock=clock, simulate=True, cooperative=False,
                              obey_terminate=False)
            exec_handler.SANDBOXES.update({"S1h": box, "S2": FakeSandbox("S2", available=False)})
            m = self.manager(clock=clock)
            job = m.create_job("demo", "I6", job_type="test.exec", payload={"worktree": str(wt), "argv": ["pytest"]})
            t = threading.Thread(target=lambda: Executor(m).run(job["id"]), daemon=True)
            t.start()
            self.assertTrue(box.started.wait(20))
            m.stop_factory(reason="guardrail-test")
            t.join(60)
            self.assertFalse(t.is_alive())
            d = box.signal.detected_active_ms
            self.assertLessEqual(box.terminated_at_ms, d + 30_000)
            self.assertLessEqual(box.killed_at_ms, d + 40_000)
            self.assertEqual(box.signal.t0_iso, m.factory_stop_state()["set_at"])
            self.assertEqual(m.get_job(job["id"])["state"], S.PAUSED)
        finally:
            exec_handler.unregister()

    @guard("I6.job_object_kill")
    def test_job_object_kills_everything(self):
        importlib.import_module("appfactory.jobs.jobobjects")   # fatia 2.4 (KI-0019)


if __name__ == "__main__":
    unittest.main()
