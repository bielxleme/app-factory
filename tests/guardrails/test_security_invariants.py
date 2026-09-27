"""I5 — controles de segurança: caminhos protegidos, diff, CommandPolicy, redação, ambiente limpo, sandbox
fail-closed, separação de tokens (09 §1; 08). A parte de isolamento do SO (afrunner/ACL) é da fatia 2.6."""
import importlib
import shutil
import tempfile
import unittest
from pathlib import Path

from appfactory.core.auth import Principal, Role, authorize
from appfactory.logs.redaction import redact
from appfactory.security.command_policy import CommandDecision, CommandPolicyConfig, CommandRequest, clean_env, evaluate
from appfactory.security.diff_guard import check_diff
from appfactory.security.paths import PathScope, ProtectedPaths
from appfactory.security.sandbox import production_sandboxes, select_sandbox
from appfactory.security.sandbox.s1h_runner_user import s1h_launch_spec
from appfactory.toolbox import AccessDenied
from appfactory.toolbox.fs import fs_write
from tests.fakes.gitrepo import GIT, commit_all, git, init_repo, write
from tests.fakes.sandbox import FakeSandbox
from tests.guardrails._support import PROTECTED_LITERAL, REPO, guard

PROTECTED = ProtectedPaths.load(REPO)


class SecurityInvariants(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="af-i5-")).resolve()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    @guard("I5.protected_paths")
    def test_protected_list_complete_and_enforced(self):
        missing = [p for p in PROTECTED_LITERAL if p not in PROTECTED.factory]
        self.assertEqual(missing, [], "a lista protegida não pode encolher (08 §5.1)")
        self.assertIsNotNone(PROTECTED.match("config/policies/protected-paths.yaml"))
        wt = self.root / "wt"
        wt.mkdir()
        scope = PathScope(self.root, "J", "J-A01", wt, None, ("**",), ("config/**", "src/**"), "factory")
        for target in ("config/policies/commands.yaml", "src/appfactory/core/stop.py", "src/appfactory/jobs/manager.py"):
            with self.assertRaises(AccessDenied):
                fs_write(scope, PROTECTED, target, b"relaxado")
            self.assertFalse((wt / target).exists())

    @guard("I5.diff_guard")
    @unittest.skipIf(GIT is None, "git não disponível")
    def test_protected_diff_rejected_factory_vs_project(self):
        init_repo(self.root)
        write(self.root, "README.md")
        commit_all(self.root)
        git(self.root, "checkout", "-q", "-b", "cand")
        write(self.root, "pytest.ini", "[pytest]\naddopts = -p evil\n")
        commit_all(self.root)
        v = check_diff(self.root, "main", "cand", PROTECTED, self.root)
        self.assertFalse(v.ok)
        self.assertEqual(v.repo_kind, "factory")
        proj = init_repo(self.root / "workspaces" / "demo")
        write(proj, "a.py")
        commit_all(proj)
        git(proj, "checkout", "-q", "-b", "cand")
        write(proj, "pytest.ini", "[pytest]\n")
        write(proj, "conftest.py", "")
        commit_all(proj)
        v = check_diff(proj, "main", "cand", PROTECTED, self.root)
        self.assertTrue(v.ok, v)
        self.assertEqual(v.repo_kind, "project")

    @guard("I5.command_policy")
    def test_command_policy(self):
        policy = CommandPolicyConfig.load(REPO)
        wt = self.root / "wt"
        wt.mkdir()
        scope = PathScope(self.root, "J", "J-A01", wt)
        deny = (["cmd", "/c", "x"], ["powershell", "-c", "x"], ["format", "C:"], ["icacls", "x"], ["git", "push"],
                ["curl", "x"], ["python", "-m", "pip", "install", "--user", "x"], ["npm", "i", "-g", "x"])
        for argv in deny:
            self.assertFalse(evaluate(CommandRequest(tuple(argv), wt, 60), scope, policy).allowed, argv)
        self.assertFalse(evaluate(CommandRequest("python x.py", wt, 60), scope, policy).allowed)
        self.assertFalse(evaluate(CommandRequest(("pytest",), wt, None), scope, policy).allowed)
        d = evaluate(CommandRequest(("npm", "ci"), wt, 600, kind="install"), scope, policy)
        self.assertEqual(d.sandbox, "S2")

    @guard("I5.redaction_clean_env")
    def test_redaction_and_clean_env(self):
        for secret in ("ghp_" + "abcdefghijklmnopqrstuvwxyz0123", "sk-" + "abcdefghijklmnopqrstuvwxyz",
                       "AKIA" + "ABCDEFGHIJKLMNOP"):   # valores fictícios montados em tempo de execução
            self.assertNotIn(secret, redact(f"valor {secret} fim"))
        env = clean_env("S1h", self.root, [])
        self.assertLessEqual(set(env), {"PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG"})

    @guard("I5.sandbox_fail_closed")
    def test_sandboxes_fail_closed_never_downgrade(self):
        sb = production_sandboxes()
        self.assertEqual(set(sb), {"S1h", "S2"})
        self.assertFalse(any(box.available()[0] for box in sb.values()))
        ok_s2 = CommandDecision(True, "R2", "S2", "x", "x")
        c = select_sandbox(ok_s2, frozenset(), FakeSandbox("S1h"), FakeSandbox("S2", available=False), True)
        self.assertIsNone(c.kind)
        ok_s1h = CommandDecision(True, "R1", "S1h", "x", "x")
        c = select_sandbox(ok_s1h, frozenset({"untrusted_high"}), FakeSandbox("S1h"), sb["S2"], True)
        self.assertIsNone(c.kind)

    @guard("I5.token_separation")
    def test_token_separation(self):
        runner = Principal(Role.RUNNER, "J-A01", "J", 10)
        self.assertFalse(authorize(runner, "POST", "/stop/release", confirmation_ok=True))
        self.assertFalse(authorize(runner, "POST", "/approvals/APR-1", confirmation_ok=True))
        self.assertFalse(authorize(Principal(Role.UI), "POST", "/stop/release", confirmation_ok=True))
        self.assertTrue(authorize(runner, "POST", "/stop"))
        spec = s1h_launch_spec("FOREGROUND", False, "/t/tmp", "/t/wt")
        self.assertFalse(any("TOKEN" in k.upper() for k in spec.env))

    @guard("I5.s1h_os_isolation")
    def test_s1h_os_isolation(self):
        importlib.import_module("appfactory.security.acl")   # fatia 2.6 (PoC KI-0014/KI-0016)


if __name__ == "__main__":
    unittest.main()
