"""Critérios de aceite da Fase 2.1 com processos reais (o executor roda num subprocesso separado)."""
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

import appfactory
from appfactory.jobs import states as S
from appfactory.jobs.executor import Executor
from tests.helpers import FactoryTestCase

SRC = str(Path(appfactory.__file__).resolve().parents[1])


class ProcessTestCase(FactoryTestCase):
    faults = True

    def spawn_executor(self, job_id: str) -> subprocess.Popen:
        env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1", AF_ALLOW_FAULT_INJECTION="1")
        env.pop("AF_ROOT", None)
        return subprocess.Popen([sys.executable, "-m", "appfactory", "--root", str(self.tmp), "job", "run", job_id],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_for(self, cond, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return True
            time.sleep(0.05)
        return False


class AcceptanceCrashResumeTest(ProcessTestCase):
    def test_create_run_checkpoint_crash_restart_recover_resume_validate_complete(self):
        m = self.manager()
        numbers = [5, 10, 15, 20, 25, 30]
        # CRIAR JOB -> QUEUED
        job = m.create_job("demo", "aceite: crash e retomada",
                           payload={"numbers": numbers, "_faults": {"crash_at_step": 3}})
        self.assertEqual(job["state"], S.QUEUED)
        # RUNNING -> checkpoints -> ENCERRAMENTO INESPERADO do processo (os._exit no passo 3)
        proc = self.spawn_executor(job["id"])
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 86, err)
        crashed = m.get_job(job["id"])
        self.assertEqual(crashed["state"], S.RUNNING)
        self.assertIsNotNone(crashed["current_attempt_id"])            # ficou "órfão"
        del m
        # REINICIAR JOB MANAGER -> RECUPERAR
        m2 = self.manager()
        report = m2.recover()
        self.assertIn(job["id"], report["interrupted"])
        recovered = m2.get_job(job["id"])
        self.assertEqual((recovered["state"], recovered["state_reason"]), (S.RUNNING, "recovered"))
        # IDENTIFICAR ÚLTIMO CHECKPOINT VÁLIDO
        last = m2.latest_valid_checkpoint(job["id"])
        self.assertEqual(last["step_index"], 2)
        self.assertEqual(last["state"], {"total": 30, "processed": 3})
        self.assertEqual(recovered["resume_from"], last["id"])
        # RETOMAR -> VALIDAR -> COMPLETED
        res = Executor(m2).run(job["id"])
        self.assertEqual(res.final_state, S.COMPLETED)
        final = m2.get_job(job["id"])
        self.assertTrue(final["completed_at"])
        self.assertEqual(m2.latest_valid_checkpoint(job["id"])["state"], {"total": sum(numbers), "processed": 6})
        # passos 0..2 não foram refeitos na segunda tentativa
        cks = m2.list_checkpoints(job["id"])
        second = [c["step_index"] for c in cks if c["attempt_id"] == res.attempt_id]
        self.assertEqual(second, [3, 4, 5])
        ev = self.events(m2, job["id"])
        for expected in ("job.created", "job.queued", "attempt.started", "checkpoint.saved", "attempt.interrupted",
                         "job.recovered", "job.resumed", "validation.recorded", "job.completed"):
            self.assertIn(expected, ev)
        attempts = m2.attempts(job["id"])
        self.assertEqual([a["outcome"] for a in attempts], ["interrupted", "completed"])

    def test_crash_in_the_middle_of_a_checkpoint_write(self):
        m = self.manager()
        job = m.create_job("demo", "queda durante checkpoint",
                           payload={"numbers": [1, 2, 3, 4], "_faults": {"crash_in_checkpoint_at": 2}})
        proc = self.spawn_executor(job["id"])
        proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 87)
        m2 = self.manager()
        m2.recover()
        last = m2.latest_valid_checkpoint(job["id"])
        self.assertEqual(last["step_index"], 1)                          # gravação interrompida não valeu
        self.assertEqual(len(m2.list_checkpoints(job["id"])), 2)
        self.assertEqual(Executor(m2).run(job["id"]).final_state, S.COMPLETED)
        self.assertEqual(m2.latest_valid_checkpoint(job["id"])["state"]["total"], 10)

    def test_crash_on_side_effect_step_blocks_for_human(self):
        m = self.manager()
        job = m.create_job("demo", "efeito colateral",
                           payload={"numbers": [1, 2, 3], "side_effect_steps": [1], "_faults": {"crash_at_step": 1}})
        proc = self.spawn_executor(job["id"])
        proc.communicate(timeout=60)
        m2 = self.manager()
        report = m2.recover()
        self.assertIn(job["id"], report["blocked"])
        j = m2.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)
        self.assertIn("efeito colateral", j["state_reason"])

    def test_recovery_is_isolated_per_job_and_idempotent(self):
        m = self.manager()
        jobs = [m.create_job(p, "x", payload={"numbers": [1, 2, 3], "_faults": {"crash_at_step": 1}})
                for p in ("p1", "p2")]
        for j in jobs:
            proc = self.spawn_executor(j["id"])
            proc.communicate(timeout=60)
        m2 = self.manager()
        original = m2._interrupt_attempt
        calls = {"n": 0}

        def flaky(conn, job, att, status):
            if job["id"] == jobs[0]["id"] and calls["n"] == 0:
                calls["n"] += 1
                raise RuntimeError("falha simulada durante a recuperação")
            return original(conn, job, att, status)

        m2._interrupt_attempt = flaky
        r1 = m2.recover()
        self.assertEqual([e["job_id"] for e in r1["errors"]], [jobs[0]["id"]])
        self.assertIn(jobs[1]["id"], r1["interrupted"])                 # o outro job não foi afetado
        self.assertIn("recovery.error", self.events(m2, jobs[0]["id"]))
        r2 = m2.recover()                                               # rodar de novo resolve
        self.assertIn(jobs[0]["id"], r2["interrupted"])
        self.assertEqual(r2["errors"], [])
        for j in jobs:
            self.assertEqual(Executor(m2).run(j["id"]).final_state, S.COMPLETED)


class AcceptanceStopTest(ProcessTestCase):
    def test_running_stop_stopping_checkpoint_stopped(self):
        m = self.manager()
        job = m.create_job("demo", "aceite: stop gracioso",
                           payload={"numbers": list(range(1, 31)), "step_delay_ms": 100})
        proc = self.spawn_executor(job["id"])
        self.assertTrue(self.wait_for(
            lambda: (m.latest_valid_checkpoint(job["id"]) or {}).get("step_index", -1) >= 2))
        self.assertEqual(m.get_job(job["id"])["state"], S.RUNNING)
        # STOP -> STOPPING
        self.assertEqual(m.request_stop(job["id"], reason="aceite")["state"], S.STOPPING)
        out, err = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0, err)
        # SALVAR ESTADO/CHECKPOINT -> STOPPED
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.STOPPED)
        last = m.latest_valid_checkpoint(job["id"])
        self.assertEqual(last["kind"], "stop")
        self.assertEqual(last["state"]["processed"], last["step_index"] + 1)
        self.assertEqual(self.transitions(m, job["id"])[-2:], [(S.RUNNING, S.STOPPING), (S.STOPPING, S.STOPPED)])
        self.assertFalse(any((self.paths.jobs_dir / job["id"] / "tmp").iterdir()))
        # STOP persiste após reinício; retomada só por comando explícito
        m2 = self.manager()
        self.assertEqual(m2.recover()["interrupted"], [])
        self.assertEqual(m2.get_job(job["id"])["state"], S.STOPPED)
        m2.resume(job["id"])
        self.assertEqual(Executor(m2).run(job["id"]).final_state, S.COMPLETED)
        self.assertEqual(m2.latest_valid_checkpoint(job["id"])["state"]["total"], sum(range(1, 31)))


if __name__ == "__main__":
    unittest.main()
