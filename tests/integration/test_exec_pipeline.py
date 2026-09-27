"""G22-16/17/18/27/28b/30b/33/37..G22-45: execução pelo contrato de sandbox integrada ao Job Manager 2.1.

Somente o FakeSandbox (código confiável de teste) é usado; nenhum código não confiável é executado."""
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

from appfactory.jobs import states as S
from appfactory.jobs.errors import FactoryStopped
from appfactory.jobs.executor import Executor
from appfactory.jobs.handlers import StepContext, StepInterrupted
from appfactory.jobs.store import connect
from appfactory.logs import audit
from appfactory.security.command_policy import CommandPolicyConfig, CommandRequest
from appfactory.security.paths import make_scope
from appfactory.security.sandbox import STOP_KILL_S, STOP_TERMINATE_S
from appfactory.toolbox.shell import StopMonitor, exec_untrusted
from tests.fakes import exec_handler
from tests.fakes.gitrepo import GIT, commit_all, git, init_repo, write
from tests.fakes.sandbox import FakeSandbox
from tests.helpers import FakeClock, FactoryTestCase

REPO = Path(__file__).resolve().parents[2]


class PipelineBase(FactoryTestCase):
    def setUp(self):
        super().setUp()
        exec_handler.register()
        self.wt = self.tmp / "workspaces" / "_worktrees" / "demo" / "TASK-1"
        self.wt.mkdir(parents=True)

    def tearDown(self):
        exec_handler.unregister()
        super().tearDown()

    def sandboxes(self, s1h=None, s2=None):
        exec_handler.SANDBOXES.update({"S1h": s1h or FakeSandbox("S1h"), "S2": s2 or FakeSandbox("S2", available=False)})
        return exec_handler.SANDBOXES

    def job(self, m, **payload):
        payload.setdefault("worktree", str(self.wt))
        return m.create_job("demo", "teste de execução", job_type="test.exec", payload=payload)

    def start(self, m, job_id):
        box = {}
        t = threading.Thread(target=lambda: box.setdefault("res", Executor(m).run(job_id)), daemon=True)
        t.start()
        return t, box

    def journal(self, job_id):
        conn = connect(self.paths.db)
        try:
            return [dict(r) for r in conn.execute("SELECT * FROM step_journal WHERE job_id = ? ORDER BY intent_at",
                                                  (job_id,))]
        finally:
            conn.close()

    def audit_types(self):
        path = audit.audit_path(self.paths)
        if not path.exists():
            return []
        return [json.loads(x)["type"] for x in path.read_text(encoding="utf-8").splitlines()]


class ExecSuccessAndFailureTests(PipelineBase):
    def test_g22_37_success_and_g22_20_redaction(self):
        box = FakeSandbox("S1h", stdout="ok token=ghp_abcdefghijklmnopqrstuvwxyz0123\n", stderr="password=hunter2")
        self.sandboxes(box)
        m = self.manager()
        job = self.job(m, argv=["pytest", "-q"], kind="tests")
        res = Executor(m).run(job["id"])
        self.assertEqual(res.final_state, S.COMPLETED, res)
        self.assertEqual(len(box.calls), 1)
        self.assertLessEqual(set(box.calls[0]["env"]), {"PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG"})
        rows = self.journal(job["id"])
        self.assertEqual(len(rows), 1)
        rec = json.loads(rows[0]["result_json"])
        self.assertEqual(rec["run"]["outcome"], "ok")
        self.assertEqual(rec["sandbox"], "S1h")
        out = Path(rec["run"]["stdout_ref"]).read_text(encoding="utf-8")
        err = Path(rec["run"]["stderr_ref"]).read_text(encoding="utf-8")
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz0123", out)
        self.assertNotIn("hunter2", err)
        self.assertTrue(Path(rec["run"]["stdout_ref"]).is_relative_to(self.paths.jobs_dir))
        log = self.paths.job_log(job["id"]).read_text(encoding="utf-8")
        self.assertIn("exec.result", log)
        self.assertEqual([c["kind"] for c in m.list_checkpoints(job["id"])], ["step"])

    def test_g22_41_failure_error_timeout(self):
        box = FakeSandbox("S1h", behavior="fail", exit_code=3)
        self.sandboxes(box)
        m = self.manager()
        job = self.job(m, argv=["pytest"], kind="tests")
        for i in range(3):
            Executor(m).run(job["id"])
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)
        self.assertIn("needs_human", j["state_reason"])
        outcomes = [json.loads(r["result_json"])["run"]["outcome"] for r in self.journal(job["id"])]
        self.assertEqual(outcomes, ["failed"] * 3)
        for behavior in ("error", "timeout"):
            box.behavior = behavior
            job2 = self.job(m, argv=["pytest"], kind="tests")
            Executor(m).run(job2["id"])
            self.assertEqual(m.get_job(job2["id"])["state_reason"], "retry_pending")
            rec = json.loads(self.journal(job2["id"])[0]["result_json"])["run"]
            self.assertEqual(rec["outcome"], behavior)
            if behavior == "timeout":
                self.assertIsNotNone(rec["terminated_at_ms"])
            m.cancel(job2["id"])

    def test_g22_42_limits(self):
        for behavior in ("limit_memory", "limit_processes"):
            self.sandboxes(FakeSandbox("S1h", behavior=behavior))
            m = self.manager()
            job = self.job(m, argv=["pytest"], kind="tests")
            Executor(m).run(job["id"])
            self.assertEqual(m.get_job(job["id"])["state_reason"], "retry_pending")
            self.assertEqual(json.loads(self.journal(job["id"])[0]["result_json"])["run"]["outcome"], behavior)
            m.cancel(job["id"])
        self.assertIn("sandbox.run", self.audit_types())

    def test_g22_33_production_sandboxes_block(self):
        m = self.manager()                     # SANDBOXES vazio => sandboxes de produção (falham fechados)
        job = self.job(m, argv=["pytest"], kind="tests")
        Executor(m).run(job["id"])
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)
        self.assertIn("sandbox_unavailable:S1h", j["state_reason"])
        self.assertEqual(self.journal(job["id"]), [])          # nada foi lançado nem pretendido
        self.assertEqual(m.attempts(job["id"])[-1]["outcome"], "held")
        self.assertIn("sandbox.unavailable", self.audit_types())
        job2 = self.job(m, argv=["pytest"], kind="tests", flags=["network_isolation_required"])
        m.cancel(job["id"])
        Executor(m).run(job2["id"])
        self.assertIn("sandbox_unavailable:S2", m.get_job(job2["id"])["state_reason"])

    def test_g22_30b_r2_without_approval_blocks(self):
        self.sandboxes()
        m = self.manager()
        job = self.job(m, argv=["npm", "install"], kind="install", timeout_s=600)
        Executor(m).run(job["id"])
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)
        self.assertIn("approval", j["state_reason"])
        self.assertIn("command.denied", self.audit_types())

    def test_g22_28b_forbidden_command_violation_then_block(self):
        box = FakeSandbox("S1h")
        self.sandboxes(box)
        m = self.manager()
        job = self.job(m, argv=["curl", "http://exemplo.invalid"], kind="shell", timeout_s=60)
        Executor(m).run(job["id"])
        self.assertEqual(m.get_job(job["id"])["state_reason"], "retry_pending")   # 1ª: negada e registrada
        Executor(m).run(job["id"])
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)                                     # reincidência
        self.assertIn("policy_violation", j["state_reason"])
        self.assertEqual(box.calls, [])
        self.assertEqual(sum(1 for e in m.history(job["id"]) if e["type"] == "security.violation"), 2)


class ViolationAndDiffTests(PipelineBase):
    def test_g22_45_path_violation_reincidence(self):
        self.sandboxes()
        m = self.manager()
        job = self.job(m, action="write_outside", writes=["src/**"], target="fora/x.txt", times=2)
        Executor(m).run(job["id"])
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)
        self.assertIn("policy_violation", j["state_reason"])
        self.assertFalse((self.wt / "fora" / "x.txt").exists())
        self.assertEqual(self.audit_types().count("security.violation"), 2)
        self.assertTrue(audit.verify_chain(audit.audit_path(self.paths))[0])

    @unittest.skipIf(GIT is None, "git não disponível")
    def test_g22_27_rejected_diff_blocks_job(self):
        init_repo(self.tmp)
        write(self.tmp, "config/policies/x.yaml", "{}")
        write(self.tmp, "src/app/a.py", "a")
        commit_all(self.tmp, "base")
        git(self.tmp, "checkout", "-q", "-b", "task")
        write(self.tmp, "config/policies/x.yaml", '{"relaxado": true}')
        commit_all(self.tmp, "task")
        git(self.tmp, "checkout", "-q", "main")
        self.sandboxes()
        m = self.manager()
        job = self.job(m, action="diff", repo=str(self.tmp), base="main", head="task")
        Executor(m).run(job["id"])
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)
        self.assertIn("policy_violation", j["state_reason"])
        self.assertIn("security.violation", [e["type"] for e in m.history(job["id"])])
        self.assertIn("diff.rejected", self.audit_types())


class StopDuringExecutionTests(PipelineBase):
    def test_g22_38_job_stop_during_execution(self):
        box = FakeSandbox("S1h", behavior="block", poll_s=0.05)
        self.sandboxes(box)
        m = self.manager()
        job = self.job(m, argv=["pytest"], kind="tests")
        t, out = self.start(m, job["id"])
        self.assertTrue(box.started.wait(20))
        t0 = time.monotonic()
        m.request_stop(job["id"])
        t.join(45)
        elapsed = time.monotonic() - t0
        self.assertFalse(t.is_alive())
        self.assertLessEqual(elapsed, STOP_KILL_S)
        j = m.get_job(job["id"])
        self.assertEqual(j["state"], S.STOPPED)
        self.assertEqual(box.signal.reason, "job_stop")
        self.assertEqual(box.signal.t0_iso, j["stop_requested_at"])
        self.assertLessEqual(box.signal.terminate_at_ms - box.signal.detected_active_ms, STOP_TERMINATE_S * 1000)
        self.assertLessEqual(box.signal.kill_at_ms - box.signal.detected_active_ms, STOP_KILL_S * 1000)
        self.assertTrue(all(g <= 1000 for g in box.poll_gaps_ms), box.poll_gaps_ms)
        rec = json.loads(self.journal(job["id"])[0]["result_json"])
        self.assertEqual(rec["run"]["outcome"], "killed_stop")
        self.assertNotIn("step", [c["kind"] for c in m.list_checkpoints(job["id"])])
        self.assertFalse(self.paths.job_tmp(job["id"], out["res"].attempt_id).exists())
        # retomada explícita: o passo interrompido é reexecutado numa nova tentativa
        m.resume(job["id"])
        box.behavior = "ok"
        self.assertEqual(Executor(m).run(job["id"]).final_state, S.COMPLETED)

    def test_g22_38b_non_cooperative_deadlines_simulated(self):
        clock = FakeClock()
        box = FakeSandbox("S1h", behavior="block", poll_s=1.0, clock=clock, simulate=True, cooperative=False,
                          obey_terminate=False)
        self.sandboxes(box)
        m = self.manager(clock=clock)
        job = self.job(m, argv=["pytest"], kind="tests")
        t, _ = self.start(m, job["id"])
        self.assertTrue(box.started.wait(20))
        m.request_stop(job["id"])
        t.join(60)
        self.assertFalse(t.is_alive())
        sig = box.signal
        t0_active = sig.detected_active_ms  # detecção imediata: nenhum tempo simulado passou antes do sinal
        self.assertLessEqual(box.terminated_at_ms, t0_active + STOP_TERMINATE_S * 1000)
        self.assertLessEqual(box.killed_at_ms, t0_active + STOP_KILL_S * 1000)
        self.assertGreaterEqual(box.killed_at_ms, t0_active + STOP_TERMINATE_S * 1000)
        self.assertEqual(m.get_job(job["id"])["state"], S.STOPPED)

    def test_g22_38c_detection_latency_never_extends_deadline(self):
        clock = FakeClock()
        m = self.manager(clock=clock)
        job = self.job(m, argv=["pytest"], kind="tests")
        claim = m.claim("exec-teste", job_id=job["id"])
        ctx = StepContext(attempt_n=1, tmp_dir=str(self.tmp), job_id=job["id"], attempt_id=claim["attempt_id"],
                          manager=m, step_index=0)
        m.request_stop(job["id"])
        clock.advance(12)                          # STOP detectado 12 s depois do T0 persistido
        sig = StopMonitor(ctx)()
        self.assertEqual(sig.reason, "job_stop")
        # o T0 persistido tem precisão de ms: o prazo restante pode ser até 1 ms MENOR, nunca maior
        self.assertAlmostEqual(sig.terminate_at_ms - sig.detected_active_ms, (STOP_TERMINATE_S - 12) * 1000, delta=2)
        self.assertLessEqual(sig.terminate_at_ms - sig.detected_active_ms, (STOP_TERMINATE_S - 12) * 1000)
        self.assertAlmostEqual(sig.kill_at_ms - sig.detected_active_ms, (STOP_KILL_S - 12) * 1000, delta=2)
        self.assertLessEqual(sig.kill_at_ms - sig.detected_active_ms, (STOP_KILL_S - 12) * 1000)
        clock.advance(100)                         # detecção muito atrasada: prazo imediato, nunca maior
        sig2 = StopMonitor(ctx)()
        self.assertEqual((sig2.terminate_at_ms, sig2.kill_at_ms), (sig2.detected_active_ms, sig2.detected_active_ms))

    def test_g22_39_factory_stop_during_execution(self):
        for trigger in ("api", "file"):
            box = FakeSandbox("S1h", behavior="block", poll_s=0.05)
            exec_handler.SANDBOXES.clear()
            self.sandboxes(box)
            m = self.manager()
            job = self.job(m, argv=["pytest"], kind="tests")
            t, _ = self.start(m, job["id"])
            self.assertTrue(box.started.wait(20))
            t0 = time.monotonic()
            if trigger == "api":
                m.stop_factory(reason="user")
            else:
                self.paths.stop_file.write_text("parar\n", encoding="utf-8")
            t.join(45)
            self.assertFalse(t.is_alive())
            self.assertLessEqual(time.monotonic() - t0, STOP_KILL_S)
            j = m.get_job(job["id"])
            self.assertEqual((j["state"], j["state_reason"]), (S.PAUSED, "factory_stop"), trigger)
            self.assertEqual(box.signal.reason, "factory_stop")
            self.assertEqual(json.loads(self.journal(job["id"])[0]["result_json"])["run"]["outcome"],
                             "killed_factory_stop")
            if self.paths.stop_file.exists():
                os.remove(self.paths.stop_file)     # apagar o arquivo NÃO libera
            m2 = self.manager()
            self.assertTrue(m2.factory_stop_state()["active"])
            with self.assertRaises(FactoryStopped):
                m2.claim("outro", job_id=job["id"])
            with self.assertRaises(PermissionError):
                m2.resume_factory(confirmed=False)
            self.assertTrue(m2.resume_factory(actor="user", confirmed=True))
            self.assertEqual(m2.get_job(job["id"])["state"], S.QUEUED)
            m2.cancel(job["id"])
        types = self.audit_types()
        self.assertEqual(types.count("stop.set"), 2)
        self.assertEqual(types.count("stop.released"), 2)
        self.assertTrue(audit.verify_chain(audit.audit_path(self.paths))[0])

    def test_g22_40_stop_active_before_execution(self):
        box = FakeSandbox("S1h")
        self.sandboxes(box)
        m = self.manager()
        job = self.job(m, argv=["pytest"], kind="tests")
        claim = m.claim("exec-teste", job_id=job["id"])
        m.stop_factory()
        ctx = StepContext(attempt_n=1, tmp_dir=str(self.tmp), job_id=job["id"], attempt_id=claim["attempt_id"],
                          manager=m, step_index=0)
        scope = make_scope(self.tmp, job["id"], claim["attempt_id"], self.wt)
        req = CommandRequest(("pytest",), self.wt, 60, kind="tests")
        with self.assertRaises(StepInterrupted):
            exec_untrusted(ctx, req, scope=scope, sandboxes=exec_handler.SANDBOXES,
                           policy=CommandPolicyConfig.load(REPO))
        self.assertEqual(box.calls, [])
        job2 = self.job(m, argv=["pytest"], kind="tests")
        with self.assertRaises(FactoryStopped):
            m.claim("exec-teste", job_id=job2["id"])

    def test_g22_43_cancel_lease_loss_during_execution(self):
        box = FakeSandbox("S1h", behavior="block", poll_s=0.05)
        self.sandboxes(box)
        m = self.manager()
        job = self.job(m, argv=["pytest"], kind="tests")
        t, out = self.start(m, job["id"])
        self.assertTrue(box.started.wait(20))
        m.cancel(job["id"])
        t.join(45)
        self.assertFalse(t.is_alive())
        self.assertEqual(box.signal.reason, "cancel")
        self.assertIn("posse perdida", out["res"].detail)
        self.assertEqual(m.get_job(job["id"])["state"], S.CANCELLED)
        rows = self.journal(job["id"])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["result_at"])          # a tentativa antiga não grava nada depois de perder a posse


class RecoveryTests(PipelineBase):
    faults = True

    def test_g22_44_crash_during_execution_then_recover(self):
        m = self.manager()
        job = self.job(m, argv=["pytest"], kind="tests")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env.pop("AF_ROOT", None)
        proc = subprocess.run([sys.executable, str(REPO / "tests" / "fakes" / "exec_job_runner.py"), str(self.tmp),
                               job["id"], "crash"], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 88, proc.stderr)
        rows = self.journal(job["id"])
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["result_at"])
        m2 = self.manager()
        m2.recover()
        j = m2.get_job(job["id"])
        self.assertEqual(j["state"], S.BLOCKED)
        self.assertIn("efeito colateral", j["state_reason"])     # D-0046: nada é repetido às cegas
        self.assertIsNone(m2.latest_valid_checkpoint(job["id"]))


class ImmutabilityTests(PipelineBase):
    def test_g22_16b_17c_sql_tampering_aborts(self):
        self.sandboxes()
        m = self.manager()
        job = self.job(m, argv=["pytest"], kind="tests")
        Executor(m).run(job["id"])
        conn = connect(self.paths.db)
        try:
            for sql in ("UPDATE checkpoints SET state_json = '{}'", "DELETE FROM checkpoints",
                        "DELETE FROM events", "UPDATE events SET type = 'x'"):
                with self.assertRaises(sqlite3.DatabaseError, msg=sql):
                    conn.execute(sql)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
