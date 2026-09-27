"""G22-32..G22-36: seleção S1h × S2 (nunca rebaixa), falha fechada e especificações de lançamento."""
import unittest
from unittest import mock

from appfactory.security.command_policy import CommandDecision
from appfactory.security.sandbox import (CEILINGS, GIB, STOP_KILL_S, STOP_TERMINATE_S, Limits, SandboxUnavailable,
                                         deadlines, limits_for, production_sandboxes, select_sandbox,
                                         validate_limits)
from appfactory.security.sandbox import docker as dk
from appfactory.security.sandbox import s1h_runner_user as s1h
from tests.fakes.sandbox import FakeSandbox

OK_S1H = CommandDecision(True, "R1", "S1h", "python_script", "ok")
OK_S2 = CommandDecision(True, "R2", "S2", "install", "ok")


class SelectionTests(unittest.TestCase):
    def test_g22_32_never_downgrade(self):
        s1h_ok, s2_off = FakeSandbox("S1h"), FakeSandbox("S2", available=False)
        c = select_sandbox(OK_S2, frozenset(), s1h_ok, s2_off, True)
        self.assertEqual((c.kind, c.hold), (None, "BLOCKED"))
        for flag in ("network_isolation_required", "needs_network", "unknown_origin", "server", "release_build",
                     "untrusted_high"):
            c = select_sandbox(OK_S1H, frozenset({flag}), s1h_ok, s2_off, True)
            self.assertIsNone(c.kind, flag)
            self.assertIn(c.hold, ("BLOCKED", "WAITING"), flag)
        c = select_sandbox(OK_S1H, frozenset({"server"}), s1h_ok, FakeSandbox("S2"), False)
        self.assertEqual((c.kind, c.hold), (None, "WAITING"))
        c = select_sandbox(OK_S1H, frozenset({"server"}), s1h_ok, FakeSandbox("S2"), True)
        self.assertEqual(c.kind, "S2")
        self.assertEqual(select_sandbox(OK_S1H, frozenset(), s1h_ok, s2_off, False).kind, "S1h")
        c = select_sandbox(OK_S1H, frozenset(), FakeSandbox("S1h", available=False), FakeSandbox("S2"), True)
        self.assertEqual((c.kind, c.hold), (None, "BLOCKED"))   # P-09: sem escalonamento automático
        self.assertEqual(select_sandbox(CommandDecision(True, "R0", "S0", "git_status", "x"), frozenset(),
                                        s1h_ok, s2_off, True).hold, "BLOCKED")

    def test_g22_33_production_sandboxes_fail_closed(self):
        sb = production_sandboxes()
        self.assertEqual(set(sb), {"S1h", "S2"})
        for kind, box in sb.items():
            ok, why = box.available()
            self.assertFalse(ok, kind)
            self.assertTrue(why)
            with mock.patch("subprocess.Popen", side_effect=AssertionError("processo criado!")):
                with self.assertRaises(SandboxUnavailable):
                    box.run(["python", "-c", "1"], ".", {}, limits_for("FOREGROUND", 10), lambda: None)
        c = select_sandbox(OK_S1H, frozenset(), sb["S1h"], sb["S2"], True)
        self.assertEqual((c.kind, c.hold), (None, "BLOCKED"))

    def test_g22_34_s1h_launch_spec(self):
        fg = s1h.s1h_launch_spec("FOREGROUND", False, "/t/tmp", "/t/wt")
        bg = s1h.s1h_launch_spec("BACKGROUND", False, "/t/tmp", "/t/wt")
        bat = s1h.s1h_launch_spec("BATTERY", True, "/t/tmp", "/t/wt")
        self.assertEqual((fg.job_memory_bytes, fg.cpu_rate, fg.active_processes), (int(1.5 * GIB), 5000, 32))
        self.assertEqual((bg.job_memory_bytes, bg.cpu_rate, bg.active_processes), (3 * GIB, 8000, 32))
        self.assertEqual(fg.process_memory_bytes, fg.job_memory_bytes)
        self.assertEqual(fg.priority_class, s1h.BELOW_NORMAL_PRIORITY_CLASS)
        self.assertEqual(bat.priority_class, s1h.IDLE_PRIORITY_CLASS)
        for spec in (fg, bg, bat):
            self.assertTrue(spec.limit_flags & s1h.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
            self.assertFalse(spec.limit_flags & (s1h.JOB_OBJECT_LIMIT_BREAKAWAY_OK | s1h.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK))
            self.assertTrue(spec.ui_restrictions & s1h.JOB_OBJECT_UILIMIT_READCLIPBOARD)
            self.assertTrue(spec.ui_restrictions & s1h.JOB_OBJECT_UILIMIT_WRITECLIPBOARD)
            self.assertTrue(spec.ui_restrictions & s1h.JOB_OBJECT_UILIMIT_DESKTOP)
            self.assertFalse(spec.logon_flags & s1h.LOGON_NETCREDENTIALS_ONLY)
            self.assertTrue(spec.creation_flags & s1h.CREATE_SUSPENDED)
            self.assertLessEqual(set(spec.env), {"PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG"})
            self.assertFalse(spec.network_isolated)       # KI-0015 declarado
            self.assertEqual(spec.parent_job, "AppFactory-afd")
        with self.assertRaises(ValueError):
            s1h.S1hLaunchSpec(**{**fg.__dict__, "logon_flags": s1h.LOGON_NETCREDENTIALS_ONLY}).validate()
        with self.assertRaises(ValueError):
            s1h.S1hLaunchSpec(**{**fg.__dict__, "limit_flags": fg.limit_flags | s1h.JOB_OBJECT_LIMIT_BREAKAWAY_OK}).validate()
        with self.assertRaises(ValueError):
            s1h.S1hLaunchSpec(**{**fg.__dict__, "env": {**fg.env, "AF_TOKEN": "x"}}).validate()

    def test_g22_35_docker_spec(self):
        spec = dk.docker_spec("TASK-1", "/t/wt", "FOREGROUND", False, "img:1", ("pytest",), cpu_count=12)
        a = spec.args
        self.assertIn("--rm", a)
        self.assertEqual(a[a.index("--network") + 1], "none")
        self.assertEqual(a[a.index("--user") + 1], "1000:1000")
        self.assertIn("--memory", a)
        self.assertEqual(a[a.index("--cpus") + 1], "6.0")
        self.assertIn("appfactory.task=TASK-1", a)
        self.assertEqual(a.count("--mount"), 1)
        self.assertNotIn("docker.sock", " ".join(a))
        inst = dk.docker_spec("TASK-1", "/t/wt", "FOREGROUND", True, "img:1", cpu_count=12)
        self.assertEqual(inst.network, "bridge")
        with self.assertRaises(ValueError):
            dk.DockerSpec(a + ("--mount", "type=bind,source=/var/run/docker.sock,target=/s"), "none", 1, 1).validate()
        with self.assertRaises(ValueError):
            dk.DockerSpec(tuple(x if x != "1000:1000" else "0:0" for x in a), "none", 1, 1).validate()

    def test_g22_36_ceilings(self):
        for mode, ceil in CEILINGS.items():
            lim = limits_for(mode, 60)
            self.assertLessEqual(lim.memory_bytes, ceil["memory_bytes"])
        with self.assertRaises(ValueError):
            validate_limits(Limits(2 * GIB, 50, 32, "BELOW_NORMAL", 60), "FOREGROUND")
        with self.assertRaises(ValueError):
            validate_limits(Limits(GIB, 90, 32, "BELOW_NORMAL", 60), "BACKGROUND")
        with self.assertRaises(ValueError):
            validate_limits(Limits(GIB, 50, 64, "BELOW_NORMAL", 60), "FOREGROUND")
        with self.assertRaises(ValueError):
            validate_limits(Limits(GIB, 50, 32, "NORMAL", 60), "FOREGROUND")

    def test_stop_deadlines_formula(self):
        # D-0054: prazo efetivo = menor entre T0 + prazo e detecção + prazo
        self.assertEqual(deadlines(1000, 0), (1000 + STOP_TERMINATE_S * 1000, 1000 + STOP_KILL_S * 1000))
        self.assertEqual(deadlines(1000, 12.0), (1000 + 18_000, 1000 + 28_000))
        self.assertEqual(deadlines(1000, 100.0), (1000, 1000))
        self.assertEqual(deadlines(1000, -50.0), (1000 + 30_000, 1000 + 40_000))   # relógio voltou: nunca maior
        self.assertEqual(deadlines(1000, None), (31_000, 41_000))


if __name__ == "__main__":
    unittest.main()
