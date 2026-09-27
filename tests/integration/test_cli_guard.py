"""AC-04 (af guard check-diff), AC-11 (af audit verify), af guard check-path e af guardrails status."""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import appfactory
from tests.fakes.gitrepo import GIT, commit_all, git, init_repo, write
from tests.helpers import FactoryTestCase

REPO = Path(__file__).resolve().parents[2]
SRC = str(Path(appfactory.__file__).resolve().parents[1])


def af(root, *args):
    env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
    env.pop("AF_ROOT", None)
    proc = subprocess.run([sys.executable, "-m", "appfactory", "--root", str(root), *args], env=env,
                          capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
    except ValueError:
        data = None
    return proc.returncode, data, proc


class CliGuardTests(FactoryTestCase):
    def setUp(self):
        super().setUp()
        shutil.copytree(REPO / "config", self.tmp / "config")

    @unittest.skipIf(GIT is None, "git não disponível")
    def test_ac04_check_diff(self):
        init_repo(self.tmp)
        write(self.tmp, "src/app/a.py", "a")
        commit_all(self.tmp, "base")
        git(self.tmp, "checkout", "-q", "-b", "ruim")
        write(self.tmp, "config/policies/commands.yaml", "{}")
        commit_all(self.tmp, "ruim")
        git(self.tmp, "checkout", "-q", "-b", "bom", "main")
        write(self.tmp, "src/app/a.py", "b")
        commit_all(self.tmp, "bom")
        rc, data, proc = af(self.tmp, "guard", "check-diff", "--base", "main", "--head", "ruim")
        self.assertEqual(rc, 3, proc.stderr)
        self.assertFalse(data["ok"])
        self.assertEqual(data["violations"][0]["path"], "config/policies/commands.yaml")
        rc, data, proc = af(self.tmp, "guard", "check-diff", "--base", "main", "--head", "bom")
        self.assertEqual(rc, 0, proc.stderr)
        self.assertTrue(data["ok"])
        rc, data, _ = af(self.tmp, "guard", "check-diff", "--base", "main", "--head", "nao-existe")
        self.assertEqual(rc, 3)
        self.assertTrue(data["error"])

    def test_check_path(self):
        wt = self.tmp / "workspaces" / "_worktrees" / "demo" / "T1"
        wt.mkdir(parents=True)
        rc, data, _ = af(self.tmp, "guard", "check-path", "--op", "write", "--path", "src/x.py", "--worktree", str(wt),
                         "--writes", "src/**")
        self.assertEqual((rc, data["allowed"]), (0, True))
        rc, data, _ = af(self.tmp, "guard", "check-path", "--op", "write", "--path", "../../../../AGENTS.md",
                         "--worktree", str(wt), "--writes", "src/**")
        self.assertEqual((rc, data["allowed"]), (3, False))

    def test_ac11_audit_verify(self):
        m = self.manager()
        m.stop_factory()
        m.resume_factory(confirmed=True)
        rc, data, _ = af(self.tmp, "audit", "verify")
        self.assertEqual((rc, data["ok"]), (0, True))
        path = self.tmp / ".appfactory" / "logs" / "audit.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text(lines[1] + "\n", encoding="utf-8")
        rc, data, _ = af(self.tmp, "audit", "verify")
        self.assertEqual((rc, data["ok"], data["first_invalid_line"]), (3, False, 0))

    def test_guardrails_status_pending_is_not_approval(self):
        rc, data, proc = af(REPO, "guardrails", "status")
        self.assertEqual(rc, 0, proc.stderr)
        self.assertFalse(data["evolution_allowed"])
        self.assertTrue(data["pending"])
        self.assertIn("pending nunca significa aprovação", data["note"])


if __name__ == "__main__":
    unittest.main()
