"""G22-51 e critérios AC-06..AC-09 verificados automaticamente sobre o código-fonte."""
import ast
import os
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "appfactory"
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "workspaces", ".appfactory", "__pycache__", ".pytest_cache"}
SUBPROCESS_ALLOWED = {"security/diff_guard.py", "cli/main.py"}
FORBIDDEN_CALLS = {"CreateProcessWithLogonW", "CreateProcessAsUserW", "CreateProcessWithTokenW", "LogonUserW",
                   "CreateJobObjectW", "AssignProcessToJobObject", "SetInformationJobObject", "TerminateJobObject",
                   "NetUserAdd", "SetNamedSecurityInfoW", "SetFileSecurityW", "SetSecurityInfo"}
FORBIDDEN_EXES = {"icacls", "docker", "net", "schtasks", "sc", "reg", "netsh", "bcdedit", "ollama", "runas"}


def _sources():
    for p in sorted(SRC.rglob("*.py")):
        yield p.relative_to(SRC).as_posix(), ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def _call_name(node):
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)


class RepoHygiene(unittest.TestCase):
    def test_g22_51_pytest_config_locked(self):
        found = []
        for dirpath, dirnames, filenames in os.walk(REPO):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for f in filenames:
                if f in ("conftest.py", "sitecustomize.py", "usercustomize.py") or f.endswith(".pth"):
                    found.append(os.path.join(dirpath, f))
        self.assertEqual(found, [])
        self.assertNotRegex((REPO / "pyproject.toml").read_text(encoding="utf-8"), r"(?m)^\s*\[\[?\s*tool\s*\.\s*pytest")
        self.assertTrue((REPO / "pytest.ini").is_file())
        self.assertTrue((REPO / "tests" / "guardrails" / "pytest.ini").is_file())

    def test_ac06_no_shell_true_and_subprocess_confined(self):
        for rel, tree in _sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg == "shell":
                            self.assertFalse(isinstance(kw.value, ast.Constant) and kw.value.value is True,
                                             f"shell=True em {rel}")
                            self.assertIsInstance(kw.value, ast.Constant, f"shell= dinâmico em {rel}")
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
                    if any(n and (n == "subprocess" or n.startswith("subprocess.")) for n in names):
                        self.assertIn(rel, SUBPROCESS_ALLOWED, f"subprocess fora dos módulos aprovados: {rel}")
                    if any(n in ("os.system", "pty") for n in names):
                        self.fail(f"import proibido em {rel}")
                if isinstance(node, ast.Call) and _call_name(node) in ("system", "popen", "startfile") and \
                        isinstance(node.func, ast.Attribute) and getattr(node.func.value, "id", "") == "os":
                    self.fail(f"os.{_call_name(node)} em {rel}")

    def test_ac07_no_new_dependencies(self):
        text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^dependencies = \[\]\s*$")
        self.assertNotIn("yaml", text.lower().replace("pytest.ini", ""))

    def test_ac08_only_fail_closed_sandboxes_in_src(self):
        sandbox_classes = set()
        for rel, tree in _sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and not any(getattr(b, "id", "") == "Protocol" for b in node.bases):
                    methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                    if {"available", "run"} <= methods:
                        sandbox_classes.add(node.name)
            self.assertNotIn("FakeSandbox", (SRC / rel).read_text(encoding="utf-8"), rel)
        self.assertEqual(sandbox_classes, {"S1hSandbox", "DockerSandbox"})

    def test_ac09_no_os_changes_in_src(self):
        for rel, tree in _sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    self.assertNotIn(_call_name(node), FORBIDDEN_CALLS, f"chamada proibida na 2.2 em {rel}")
                    if node.args and isinstance(node.args[0], (ast.List, ast.Tuple)) and node.args[0].elts:
                        first = node.args[0].elts[0]
                        if isinstance(first, ast.Constant) and isinstance(first.value, str):
                            self.assertNotIn(first.value.lower(), FORBIDDEN_EXES, f"comando proibido em {rel}")

    def test_config_files_are_json_subset(self):
        from appfactory.security.paths import load_policy_file
        for f in sorted((REPO / "config").rglob("*.yaml")):
            self.assertIsInstance(load_policy_file(f), dict, f)
        self.assertFalse(re.search(r"#", (REPO / "config/policies/protected-paths.yaml").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
