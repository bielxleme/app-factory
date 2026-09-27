"""G22-01..G22-15 (arquivo), G22-19 (credenciais), G22-54 (formato D-0049): política de caminhos."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from appfactory.security.paths import (Op, PathRejected, PathScope, PolicyFileError, ProtectedPaths,
                                       check_access, load_policy_file, match_pattern, normalize_rel)

REPO = Path(__file__).resolve().parents[2]
PROTECTED = ProtectedPaths.load(REPO)


class PolicyBase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="af-pol-")).resolve()
        self.wt = self.root / "workspaces" / "_worktrees" / "demo" / "TASK-1"
        (self.wt / "src" / "api").mkdir(parents=True)
        (self.wt / "src" / "db").mkdir(parents=True)
        (self.wt / "src" / "a.py").write_text("a")
        self.integ = self.root / "workspaces" / "_worktrees" / "demo" / "_integration-J"
        self.integ.mkdir(parents=True)
        self.job = self.root / ".appfactory" / "jobs" / "JOB-1"
        for d in ("tmp/JOB-1-A01", "tmp/JOB-1-A02", "artifacts", "quarantine"):
            (self.job / d).mkdir(parents=True)
        (self.root / ".appfactory" / "state").mkdir(parents=True)
        self.scope = PathScope(self.root, "JOB-1", "JOB-1-A01", self.wt, self.integ, ("**",),
                               ("src/api/**", "tests/test_x.py"), "factory")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def ok(self, op, path, **kw):
        d = check_access(op, path, self.scope, PROTECTED, **kw)
        self.assertTrue(d.allowed, d)
        return d

    def no(self, op, path, rule=None, **kw):
        d = check_access(op, path, self.scope, PROTECTED, **kw)
        self.assertFalse(d.allowed, d)
        if rule:
            self.assertTrue(d.rule.startswith(rule) or rule in d.rule, d)
        return d


class FileAccessTests(PolicyBase):
    def test_g22_01_read_allowed(self):
        self.assertEqual(self.ok(Op.READ, "src/a.py").rule, "reads")

    def test_g22_02_write_inside_writes(self):
        self.assertEqual(self.ok(Op.CREATE, "src/api/h.py").rule, "writes")
        self.ok(Op.CREATE, "tests/test_x.py")

    def test_g22_03_write_outside_writes(self):
        self.no(Op.WRITE, "src/db/x.py", "writes")
        self.no(Op.CREATE, "tests/other.py", "writes")

    def test_g22_04_dotdot_rejected(self):
        for p in ("../../AGENTS.md", "src/../../x", "..\\..\\AGENTS.md"):
            self.no(Op.WRITE, p, "malformed")
            with self.assertRaises(PathRejected):
                normalize_rel(p, self.wt)

    def test_g22_05_absolute_unc_other_drive(self):
        for p in ("C:\\Windows\\x", "/etc/passwd", "\\\\?\\D:\\x", "\\\\srv\\share\\x", "//srv/share/x", "C:x"):
            d = check_access(Op.WRITE, p, self.scope, PROTECTED)
            self.assertFalse(d.allowed, p)
            self.assertIn(d.rule, ("outside_root", "malformed"), (p, d))
        self.no(Op.READ, str(self.root.parent / "fora.txt"), "outside_root")

    def test_g22_06_symlink_or_junction_escape(self):
        target = self.root / "config"
        (target / "policies").mkdir(parents=True)
        link = self.wt / "src" / "api" / "link"
        try:
            if sys.platform == "win32":
                import _winapi
                _winapi.CreateJunction(str(target), str(link))
            else:
                os.symlink(target, link, target_is_directory=True)
        except (OSError, AttributeError, NotImplementedError) as exc:
            self.skipTest(f"SO não permite criar link: {exc}")
        d = self.no(Op.WRITE, "src/api/link/policies/x.yaml")
        self.assertTrue(d.rule.startswith("link_target:"), d)

    def test_g22_07_windows_name_tricks(self):
        for p in ("src/api/a.txt:evil", "src/api/AGENTS.md.", "src/api/x ", "src/api/NUL", "src/api/con.txt",
                  "src/api/COM1.log", "src/api/a|b"):
            self.no(Op.WRITE, p, "malformed")
        # maiúsculas: caminho protegido continua protegido
        scope = PathScope(self.root, "JOB-1", "JOB-1-A01", self.wt, None, ("**",), ("config/**",), "factory")
        d = check_access(Op.WRITE, "CONFIG/POLICIES/x.yaml", scope, PROTECTED)
        self.assertFalse(d.allowed)
        self.assertTrue(d.rule.startswith("protected:"), d)

    @unittest.skipUnless(sys.platform == "win32", "nomes curtos 8.3 só existem no Windows")
    def test_g22_07b_short_names_resolved(self):
        import ctypes
        long_dir = self.wt / "src" / "api" / "diretoriomuitolongo"
        long_dir.mkdir()
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(long_dir), buf, 1024)
        if not n or buf.value.lower() == str(long_dir).lower():
            self.skipTest("nomes 8.3 desativados neste volume")
        self.ok(Op.CREATE, os.path.join(buf.value, "x.py"))

    def test_g22_08_hardlink_denied(self):
        src = self.root / "segredo.txt"
        src.write_text("s")
        dst = self.wt / "src" / "api" / "hl.txt"
        try:
            os.link(src, dst)
        except OSError as exc:
            self.skipTest(f"hardlink indisponível: {exc}")
        self.no(Op.WRITE, "src/api/hl.txt", "hardlink")

    def test_g22_09_delete_by_area(self):
        (self.job / "tmp" / "JOB-1-A01" / "f").write_text("x")
        (self.job / "tmp" / "JOB-1-A02" / "f").write_text("x")
        self.ok(Op.DELETE, str(self.job / "tmp" / "JOB-1-A01" / "f"))
        self.no(Op.DELETE, str(self.job / "tmp" / "JOB-1-A02" / "f"))
        self.no(Op.DELETE, str(self.job / "tmp" / "JOB-1-A01"))
        self.no(Op.DELETE, str(self.job / "artifacts"))
        self.ok(Op.DELETE, "src/api/qualquer.py")
        self.no(Op.DELETE, "src/a.py", "writes")
        self.ok(Op.CREATE, str(self.job / "artifacts" / "r.txt"))
        self.no(Op.CREATE, str(self.job / "quarantine" / "x"), "quarantine")
        self.no(Op.READ, str(self.root / ".appfactory" / "jobs" / "JOB-2" / "x"), "operational_state")
        self.ok(Op.READ, str(self.integ / "x.py"))
        self.no(Op.WRITE, str(self.integ / "x.py"), "integration_readonly")

    def test_g22_10_rename_rules(self):
        self.ok(Op.RENAME, "src/api/a.py", dest="src/api/b.py")
        self.no(Op.RENAME, "src/api/a.py", "rename_dest", dest="src/db/b.py")
        self.no(Op.RENAME, "src/api/a.py", "rename_dest", dest="../../AGENTS.md")
        self.no(Op.RENAME, "src/db/a.py", "writes", dest="src/api/b.py")

    def test_g22_11_operational_state_inaccessible(self):
        for p in (".appfactory/state/factory.db", ".appfactory/logs/audit.jsonl", ".appfactory/runtime/job.json",
                  ".appfactory/STOP", ".appfactory/jobs/JOB-9/tmp/x"):
            for op in (Op.READ, Op.WRITE, Op.DELETE):
                d = check_access(op, str(self.root / p), self.scope, PROTECTED)
                self.assertFalse(d.allowed, (p, op))
                self.assertEqual(d.rule, "operational_state", (p, d))


class ProtectedListTests(unittest.TestCase):
    def test_g22_12_matcher_samples(self):
        protected = ["x/y/z.pth", "a.pth", "a/conftest.py", "conftest.py", "src/appfactory/core/stop.py",
                     "Config/Resources.yaml", "config/factory.yaml", "config/novo/x.json",
                     "src/appfactory/jobs/manager.py", "src/appfactory/jobs/store.py", "src/appfactory/cli/main.py",
                     "src/appfactory/core/paths.py", "src/appfactory/core/clock.py", "src/appfactory/core/procinfo.py",
                     "src/appfactory/jobs/executor.py", "src/appfactory/jobs/states.py", "src/appfactory/jobs/handlers.py",
                     "src/appfactory/jobs/jobobjects.py", "src/appfactory/core/api.py", ".git/HEAD", ".git",
                     "evals/t.json", "tests/guardrails/MANIFEST.json", "pytest.ini", "a/b/sitecustomize.py",
                     "AGENTS.md", "docs/architecture/08-seguranca.md", ".appfactory/checkpoints/CP-0001-fase0.json",
                     "src/appfactory/toolbox/fs.py", "src/appfactory/security/paths.py", "src/appfactory/logs/audit.py",
                     "tools/diagnostics/measure-hardware.ps1", ".appfactory/job.json"]
        free = ["README.md", "src/appfactory/jobs/errors.py", "src/appfactory/core/ids.py", "docs/specs/x.md",
                "tests/unit/test_x.py", "src/app/conftest_helper.py", "scripts/x.py"]
        for p in protected:
            self.assertIsNotNone(PROTECTED.match(p), p)
        for p in free:
            self.assertIsNone(PROTECTED.match(p), p)

    def test_g22_12b_pattern_semantics(self):
        self.assertTrue(match_pattern("**/*.pth", "a.pth"))
        self.assertTrue(match_pattern("dir/**", "dir"))
        self.assertTrue(match_pattern("dir/**", "DIR/a/b"))
        self.assertFalse(match_pattern("dir/**", "dirx/a"))
        self.assertFalse(match_pattern("pytest.ini", "sub/pytest.ini"))

    def test_g22_14_missing_or_invalid_list_fails_closed(self):
        tmp = Path(tempfile.mkdtemp(prefix="af-pp-"))
        try:
            with self.assertRaises(PolicyFileError):
                ProtectedPaths.load(tmp)
            f = tmp / "config" / "policies" / "protected-paths.yaml"
            f.parent.mkdir(parents=True)
            f.write_text("factory:\n  - config/**\n", encoding="utf-8")
            with self.assertRaises(PolicyFileError):
                ProtectedPaths.load(tmp)
            f.write_text('{"factory": ["src/**"], "project": [".git/**"]}', encoding="utf-8")
            with self.assertRaises(PolicyFileError):   # não protege a si mesma
                ProtectedPaths.load(tmp)
            f.write_text('{"factory": [], "project": [".git/**"]}', encoding="utf-8")
            with self.assertRaises(PolicyFileError):
                ProtectedPaths.load(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CredentialAndConfigTests(PolicyBase):
    def test_g22_15_config_modification_denied(self):
        scope = PathScope(self.root, "JOB-1", "JOB-1-A01", self.wt, None, ("**",), ("config/**",), "factory")
        d = check_access(Op.WRITE, "config/policies/commands.yaml", scope, PROTECTED)
        self.assertFalse(d.allowed)
        self.assertTrue(d.rule.startswith("protected:config/**"), d)
        self.assertTrue(check_access(Op.READ, "config/policies/commands.yaml", scope, PROTECTED).allowed)

    def test_g22_16a_checkpoint_file_denied(self):
        cp = self.root / ".appfactory" / "checkpoints" / "CP-0004-fase2-1.json"
        self.no(Op.WRITE, str(cp), "operational_state")
        scope = PathScope(self.root, "JOB-1", "JOB-1-A01", self.wt, None, ("**",), (".appfactory/**",), "factory")
        self.assertFalse(check_access(Op.WRITE, ".appfactory/checkpoints/CP-1.json", scope, PROTECTED).allowed)

    def test_g22_17a_log_delete_denied(self):
        self.no(Op.DELETE, str(self.root / ".appfactory" / "logs" / "jobs" / "JOB-1.jsonl"), "operational_state")

    def test_g22_18d_stop_file_denied(self):
        self.no(Op.WRITE, str(self.root / ".appfactory" / "STOP"), "operational_state")
        self.no(Op.CREATE, str(self.root / ".appfactory" / "STOP"), "operational_state")

    def test_g22_19_credentials_never_readable(self):
        scope = PathScope(self.root, "JOB-1", "JOB-1-A01", self.wt, None, ("**",), ("src/**",), "factory")
        for p in (".env", "src/.env.local", "secrets/k.txt", "credentials.json", "src/credentials-prod.json",
                  "id.key"):
            d = check_access(Op.READ, p, scope, PROTECTED)
            self.assertFalse(d.allowed, p)
            self.assertEqual(d.rule, "credential", (p, d))
        self.assertTrue(check_access(Op.READ, ".env.example", scope, PROTECTED).allowed)
        tok = self.root / ".appfactory" / "runtime" / "tokens" / "user.token"
        self.assertFalse(check_access(Op.READ, str(tok), scope, PROTECTED).allowed)
        self.assertFalse(check_access(Op.READ, str(Path.home() / "x.txt"), scope, PROTECTED).allowed)


class PolicyFormatTests(unittest.TestCase):
    def test_g22_54_yaml_syntax_rejected(self):
        tmp = Path(tempfile.mkdtemp(prefix="af-fmt-"))
        try:
            f = tmp / "x.yaml"
            for bad in ("# comentario\n{\"a\": 1}", "a: 1\n", "{a: 1}", '{"a": NaN}', '{"a": 1, "a": 2}',
                        "[1, 2]", "\ufeff{\"a\": 1}", ""):
                f.write_text(bad, encoding="utf-8")
                with self.assertRaises(PolicyFileError, msg=repr(bad)):
                    load_policy_file(f)
            f.write_text('{"a": [1, "b"]}', encoding="utf-8")
            self.assertEqual(load_policy_file(f), {"a": [1, "b"]})
            # arquivos reais da fábrica são JSON válido
            for name in ("protected-paths.yaml", "commands.yaml"):
                self.assertIsInstance(load_policy_file(REPO / "config" / "policies" / name), dict)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
