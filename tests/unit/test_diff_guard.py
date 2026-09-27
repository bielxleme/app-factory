"""G22-15/16c/17b/18a (diff), G22-21..G22-26 (verificador de diff) e G22-53 (fábrica × projeto, D-0053)."""
import shutil
import tempfile
import unittest
from pathlib import Path

from appfactory.security.diff_guard import check_diff, parse_raw_z
from appfactory.security.paths import ProtectedPaths, classify_repo, make_scope
from tests.fakes.gitrepo import (GIT, add_gitlink_entry, add_symlink_entry, commit_all, commit_index, git,
                                 init_repo, write)

REPO = Path(__file__).resolve().parents[2]
PROTECTED = ProtectedPaths.load(REPO)
BASE_FILES = ["README.md", "config/policies/protected-paths.yaml", "config/resources.yaml", "src/app/x.py",
              "src/appfactory/core/stop.py", "pyproject.toml", "docs/architecture/a.md",
              ".appfactory/checkpoints/CP-1.json", "src/appfactory/logs/audit.py",
              "src/appfactory/checkpoints/service.py"]


@unittest.skipIf(GIT is None, "git não disponível")
class DiffGuardFactoryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="af-diff-")).resolve()
        init_repo(self.root)
        for f in BASE_FILES:
            write(self.root, f, f"conteudo de {f}\n" * 3)
        commit_all(self.root, "base")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def branch(self, name, change, use_index=False):
        git(self.root, "checkout", "-q", "-b", name, "main")
        change(self.root)
        commit_index(self.root, name) if use_index else commit_all(self.root, name)
        git(self.root, "checkout", "-q", "-f", "main")
        return check_diff(self.root, "main", name, PROTECTED, self.root)

    def rules(self, verdict):
        return {(v.status, v.path, v.rule.split(":")[0]) for v in verdict.violations}

    def test_g22_21_all_statuses_rejected(self):
        v = self.branch("a", lambda r: write(r, "config/novo.yaml", "{}"))
        self.assertFalse(v.ok)
        self.assertIn(("A", "config/novo.yaml", "protected"), self.rules(v))
        v = self.branch("m", lambda r: write(r, "src/appfactory/core/stop.py", "enfraquecido\n"))
        self.assertIn(("M", "src/appfactory/core/stop.py", "protected"), self.rules(v))
        v = self.branch("d", lambda r: git(r, "rm", "-q", "src/appfactory/logs/audit.py"))
        self.assertIn(("D", "src/appfactory/logs/audit.py", "protected"), self.rules(v))
        v = self.branch("r1", lambda r: git(r, "mv", "docs/architecture/a.md", "notes/a.md") if
                        (r / "notes").mkdir() or True else None)
        self.assertTrue(any(s == "R" and rule == "protected" for s, _p, rule in self.rules(v)), v)
        v = self.branch("r2", lambda r: (r / "config" / "sub").mkdir() or git(r, "mv", "src/app/x.py", "config/sub/x.py"))
        self.assertTrue(any(s == "R" and p == "config/sub/x.py" for s, p, _ in self.rules(v)), v)

        def copy(r):
            write(r, "src/appfactory/checkpoints/service.py", "conteudo alterado\n" + "conteudo de x\n" * 3)
            shutil.copy(r / "src/appfactory/checkpoints/service.py", r / "src/app/copia.py")
        v = self.branch("c", copy)
        self.assertFalse(v.ok)
        statuses = {e.status for e in v.entries}
        if "C" in statuses:
            self.assertTrue(any(s == "C" for s, _p, _r in self.rules(v)), v)

        def typechange(r):
            add_symlink_entry(r, "src/appfactory/core/stop.py", "outro")
        v = self.branch("t", typechange, use_index=True)
        self.assertFalse(v.ok)
        self.assertIn("symlink", {x.rule for x in v.violations})
        self.assertTrue(any(e.status == "T" for e in v.entries), v.entries)

    def test_g22_15b_16c_17b_18a_specific_attempts(self):
        for name, change, path in (
                ("cfg", lambda r: write(r, "config/resources.yaml", "{\"x\": 99}"), "config/resources.yaml"),
                ("ckpt", lambda r: write(r, "src/appfactory/checkpoints/service.py", "x"), "src/appfactory/checkpoints/service.py"),
                ("cp", lambda r: write(r, ".appfactory/checkpoints/CP-1.json", "{}"), ".appfactory/checkpoints/CP-1.json"),
                ("log", lambda r: git(r, "rm", "-q", "src/appfactory/logs/audit.py"), "src/appfactory/logs/audit.py"),
                ("stop", lambda r: write(r, "src/appfactory/core/stop.py", "pass\n"), "src/appfactory/core/stop.py")):
            v = self.branch(name, change)
            self.assertFalse(v.ok, name)
            self.assertIn(path, {x.path for x in v.violations}, name)

    def test_g22_22_clean_diff_ok(self):
        v = self.branch("limpo", lambda r: write(r, "src/app/x.py", "novo\n"))
        self.assertTrue(v.ok, v)
        self.assertEqual(v.repo_kind, "factory")
        self.assertEqual([e.path for e in v.entries], ["src/app/x.py"])

    def test_g22_23_symlink_and_gitlink_rejected(self):
        v = self.branch("sl", lambda r: add_symlink_entry(r, "src/app/link", "../../config"), use_index=True)
        self.assertEqual({x.rule for x in v.violations}, {"symlink"})
        v = self.branch("gl", lambda r: add_gitlink_entry(r, "src/app/sub"), use_index=True)
        self.assertEqual({x.rule for x in v.violations}, {"gitlink"})

    def test_g22_24_pytest_config_in_pyproject(self):
        for i, text in enumerate(("[tool.pytest.ini_options]\naddopts='-p x'\n", "[ tool . pytest ]\nx=1\n")):
            v = self.branch(f"pp{i}", lambda r, t=text: write(r, "pyproject.toml", "[project]\nname='x'\n" + t))
            self.assertIn("pytest_config", {x.rule for x in v.violations})
        v = self.branch("pp-ok", lambda r: write(r, "pyproject.toml", "[project]\nname='y'\n"))
        self.assertTrue(v.ok, v)

    def test_g22_25_git_failure_fails_closed(self):
        v = check_diff(self.root, "main", "nao-existe", PROTECTED, self.root)
        self.assertFalse(v.ok)
        self.assertTrue(v.error)
        v = check_diff(self.root, "--output=/tmp/x", "main", PROTECTED, self.root)
        self.assertFalse(v.ok)
        self.assertIn("revisão inválida", v.error)
        v = check_diff(self.root / "nao-existe", "main", "main", PROTECTED, self.root)
        self.assertFalse(v.ok)

    def test_g22_26_case_variants_rejected(self):
        v = self.branch("case1", lambda r: write(r, "Pytest.INI", "[pytest]\n"))
        self.assertFalse(v.ok)
        v = self.branch("case2", lambda r: write(r, "tests/Guardrails/t.py", "x"))
        self.assertFalse(v.ok)

    def test_parse_raw_z(self):
        out = ":100644 100644 aaa bbb M\0a.py\0:100644 100644 ccc ddd R090\0old.py\0new.py\0"
        e = parse_raw_z(out)
        self.assertEqual([(x.status, x.path, x.old_path) for x in e], [("M", "a.py", None), ("R", "new.py", "old.py")])


@unittest.skipIf(GIT is None, "git não disponível")
class FactoryVsProjectTests(unittest.TestCase):
    """G22-53 (D-0053)."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="af-kind-")).resolve()
        init_repo(self.root)
        write(self.root, "README.md")
        commit_all(self.root, "base")
        self.proj = init_repo(self.root / "workspaces" / "demo")
        write(self.proj, "src/app.py")
        commit_all(self.proj, "base")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def proj_branch(self, name, change, use_index=False):
        git(self.proj, "checkout", "-q", "-b", name, "main")
        change(self.proj)
        commit_index(self.proj, name) if use_index else commit_all(self.proj, name)
        git(self.proj, "checkout", "-q", "-f", "main")
        return check_diff(self.proj, "main", name, PROTECTED, self.root)

    def test_project_rules(self):
        self.assertEqual(classify_repo(self.proj, self.root), "project")

        def normal(r):
            write(r, "pytest.ini", "[pytest]\n")
            write(r, "conftest.py", "x = 1\n")
            write(r, "tests/conftest.py", "x = 1\n")
            write(r, ".gitignore", "*.pyc\n")
            write(r, "docs/architecture/x.md", "doc\n")
        v = self.proj_branch("normal", normal)
        self.assertTrue(v.ok, v)
        self.assertEqual(v.repo_kind, "project")
        v = self.proj_branch("handoff", lambda r: write(r, ".appfactory/handoff.md", "x"))
        self.assertFalse(v.ok)
        self.assertTrue(v.violations[0].rule.startswith("project_protected:"))
        v = self.proj_branch("sl", lambda r: add_symlink_entry(r, "link", "../../.."), use_index=True)
        self.assertEqual({x.rule for x in v.violations}, {"symlink"})
        v = self.proj_branch("gl", lambda r: add_gitlink_entry(r, "sub"), use_index=True)
        self.assertEqual({x.rule for x in v.violations}, {"gitlink"})

    def test_classification_is_trusted_and_fails_closed(self):
        self.assertEqual(classify_repo(self.root, self.root), "factory")
        plain = self.root / "workspaces" / "sem-git"
        plain.mkdir(parents=True)
        self.assertEqual(classify_repo(plain, self.root), "factory")          # dúvida => fábrica
        outside = init_repo(Path(tempfile.mkdtemp(prefix="af-out-")))
        try:
            self.assertEqual(classify_repo(outside, self.root), "factory")    # fora de workspaces/ => fábrica
        finally:
            shutil.rmtree(outside, ignore_errors=True)
        evo = self.root / "workspaces" / "_worktrees" / "fabrica" / "evo-EP-0001"
        evo.parent.mkdir(parents=True)
        git(self.root, "worktree", "add", "-q", "-b", "evo/EP-0001", str(evo), "main")
        self.assertEqual(classify_repo(evo, self.root), "factory")            # evo/* é sempre fábrica
        scope = make_scope(self.root, "J", "J-A01", evo, writes=("src/**",), declared_repo_kind="project")
        self.assertEqual(scope.repo_kind, "factory")                          # declaração ignorada
        scope = make_scope(self.root, "J", "J-A01", self.proj, declared_repo_kind="factory")
        self.assertEqual(scope.repo_kind, "project")


if __name__ == "__main__":
    unittest.main()
