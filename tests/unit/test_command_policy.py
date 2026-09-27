"""G22-19 (ambiente limpo), G22-28..G22-31: CommandPolicy (08 §3, §4.3, §7)."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from appfactory.security.command_policy import CommandPolicyConfig, CommandRequest, clean_env, evaluate
from appfactory.security.paths import PathScope

REPO = Path(__file__).resolve().parents[2]
POLICY = CommandPolicyConfig.load(REPO)


class CommandPolicyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="af-cmd-")).resolve()
        self.wt = self.root / "workspaces" / "_worktrees" / "demo" / "T1"
        self.wt.mkdir(parents=True)
        self.scope = PathScope(self.root, "J", "J-A01", self.wt, None, ("**",), ("src/**",), "project")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def ev(self, argv, kind="script", timeout=60, flags=(), cwd=None, trust="untrusted"):
        return evaluate(CommandRequest(tuple(argv) if not isinstance(argv, str) else argv, cwd or self.wt, timeout,
                                       trust, kind, frozenset(flags)), self.scope, POLICY)

    def test_g22_28_forbidden_commands(self):
        r3 = [["format", "C:"], ["diskpart"], ["reg", "add", "HKLM\\x"], ["bcdedit", "/set"],
              ["Set-ExecutionPolicy", "Bypass"], ["netsh", "advfirewall"], ["icacls", "D:\\", "/grant", "x:F"],
              ["schtasks", "/create"], ["sc", "create", "svc"], ["net", "user", "x", "/add"], ["git", "push"],
              ["git", "push", "--force"], ["git", "reset", "--hard"], ["git", "clean", "-fdx"], ["rm", "-rf", "/"],
              ["Remove-Item", "-Recurse", "C:\\"], ["git", "-c", "core.hooksPath=x", "commit"]]
        for argv in r3:
            d = self.ev(argv)
            self.assertFalse(d.allowed, argv)
            self.assertEqual(d.risk, "R3", argv)
            self.assertTrue(d.needs_human, argv)
        for argv, rule in ((["cmd", "/c", "dir"], "shell_interpreter"), (["powershell", "-c", "x"], "shell_interpreter"),
                           (["bash", "-c", "x"], "shell_interpreter"), (["pwsh.exe", "-c", "x"], "shell_interpreter"),
                           (["curl", "http://x"], "not_allowlisted"), (["certutil", "-urlcache"], "not_allowlisted"),
                           (["C:\\evil\\python.exe", "x.py"], "executable_path_not_allowed"),
                           (["./python", "x.py"], "executable_path_not_allowed")):
            d = self.ev(argv)
            self.assertFalse(d.allowed, argv)
            self.assertEqual(d.rule, rule, argv)

    def test_g22_29_command_shape(self):
        self.assertEqual(self.ev("python x.py").rule, "string_command")
        self.assertEqual(self.ev([]).rule, "malformed")
        self.assertEqual(self.ev(["python", "x.py"], timeout=None).rule, "timeout_required")
        self.assertEqual(self.ev(["python", "x.py"], kind="shell", timeout=301).rule, "timeout_exceeds")
        self.assertEqual(self.ev(["pytest"], kind="tests", timeout=901).rule, "timeout_exceeds")
        self.assertEqual(self.ev(["python", "x.py"], cwd=self.root).rule, "cwd_outside_scope")
        self.assertTrue(self.ev(["pytest"], kind="tests", timeout=900).allowed)

    def test_g22_30_npm_pip_policy(self):
        cases = [
            (["npm", "ci", "--ignore-scripts"], "S1h", "R2", True),
            (["npm", "ci"], "S2", "R2", True),
            (["npm", "install"], "S2", "R2", True),
            (["npm", "i", "-g", "x"], None, "R3", False),
            (["python", "-m", "pip", "install", "--only-binary=:all:", "--require-hashes", "-r", "req.lock"], "S1h", "R2", True),
            (["python", "-m", "pip", "install", "--only-binary", ":all:", "--require-hashes", "-r", "req.lock"], "S1h", "R2", True),
            (["python", "-m", "pip", "install", "x"], "S2", "R2", True),
            (["python", "-m", "pip", "install", "--only-binary=:all:", "--require-hashes", "-r", "r.lock", "extra"], "S2", "R2", True),
            (["python", "-m", "pip", "install", "-e", "."], "S2", "R2", True),
            (["python", "setup.py", "install"], "S2", "R2", True),
            (["python", "-m", "pip", "install", "--user", "x"], None, "R3", False),
            (["uv", "pip", "install", "x"], "S2", "R2", True),
            (["uv", "sync"], "S2", "R2", True),
            (["yarn"], "S2", "R2", True),
            (["pnpm", "install"], "S2", "R2", True),
            (["npx", "cowsay"], "S2", "R2", True),
        ]
        for argv, sandbox, risk, classified in cases:
            d = self.ev(argv, kind="install", timeout=600)
            self.assertFalse(d.allowed, argv)          # R2 sem pré-autorização e R3: negados na 2.2
            self.assertEqual(d.risk, risk, argv)
            if classified:
                self.assertEqual(d.sandbox, sandbox, argv)
                self.assertEqual(d.rule, "approval_required", argv)
            else:
                self.assertTrue(d.needs_human, argv)

    def test_g22_31_script_execution(self):
        for argv, kind in ((["python", "scripts/x.py"], "script"), (["node", "x.js"], "script"),
                           (["pytest"], "tests"), (["npm", "test"], "tests"), (["ruff", "check", "."], "tests")):
            d = self.ev(argv, kind=kind)
            self.assertTrue(d.allowed, argv)
            self.assertEqual(d.sandbox, "S1h", argv)
            self.assertEqual(d.risk, "R1", argv)
        d = self.ev(["git", "status"])
        self.assertEqual((d.allowed, d.sandbox), (True, "S0"))
        self.assertFalse(self.ev(["git", "commit", "--no-verify", "-m", "x"]).allowed)

    def test_g22_19_clean_env(self):
        secrets_env = {"OPENAI_API_KEY": "sk-abcdefghijklmnopqrstuvwxyz", "GITHUB_TOKEN": "ghp_x",
                       "AF_TOKEN": "t", "USERPROFILE": "C:\\Users\\x", "APPDATA": "C:\\x"}
        with mock.patch.dict(os.environ, secrets_env):
            env = clean_env("S1h", self.wt / "tmp", ["C:\\py"])
        self.assertLessEqual(set(env), {"PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG"})
        for k in secrets_env:
            self.assertNotIn(k, env)
        self.assertNotIn("sk-", " ".join(env.values()))

    def test_policy_file_is_consistent(self):
        self.assertTrue({"python", "uv", "pytest", "ruff", "node", "npm", "npx", "git"} <= POLICY.allow)
        self.assertFalse(POLICY.allow & POLICY.shell_interpreters)
        self.assertEqual(POLICY.preauthorized_r2, frozenset())


if __name__ == "__main__":
    unittest.main()
