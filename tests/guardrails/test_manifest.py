"""G22-50 — controle do manifesto (D-0048): nenhuma invariante pode ser escondida como `pending`,
`pending` nunca é aprovação e o Evolution só é habilitado com I1–I7 `active`."""
import importlib
import importlib.util
import inspect
import unittest
from pathlib import Path

from appfactory.security import guardrail_manifest as gm
from tests.guardrails._support import MANIFEST, REPO

HERE = Path(__file__).resolve().parent


def _guardrail_tests():
    out = []
    for f in sorted(HERE.glob("test_*.py")):
        if f.name == "test_manifest.py":
            continue
        mod = importlib.import_module(f"tests.guardrails.{f.stem}")
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if not issubclass(cls, unittest.TestCase) or cls.__module__ != mod.__name__:
                continue
            for name, fn in inspect.getmembers(cls):
                if name.startswith("test"):
                    out.append((f.name, cls, name, fn))
    return out


class ManifestControl(unittest.TestCase):
    def test_all_invariants_present_and_valid(self):
        gm.validate(MANIFEST)
        self.assertEqual(sorted(MANIFEST["invariants"]), list(gm.INVARIANTS))
        for name, spec in MANIFEST["invariants"].items():
            self.assertTrue((HERE / spec["file"]).is_file(), spec["file"])

    def test_pending_module_must_not_exist(self):
        for cid, c in gm.pending(MANIFEST).items():
            try:
                found = importlib.util.find_spec(c["module"]) is not None
            except ModuleNotFoundError:
                found = False
            self.assertFalse(found, f"{cid}: o módulo {c['module']} já existe — o guardrail deve virar 'active'")

    def test_every_test_is_tagged_and_active_tests_never_skipped(self):
        checks = gm.checks(MANIFEST)
        tests = _guardrail_tests()
        self.assertTrue(tests)
        covered = set()
        for fname, cls, name, fn in tests:
            cid = getattr(fn, "__guard_check__", None)
            self.assertIsNotNone(cid, f"{fname}::{name} sem marcação @guard")
            self.assertIn(cid, checks, f"{fname}::{name} marca verificação inexistente {cid}")
            expected_file = MANIFEST["invariants"][cid.split(".")[0]]["file"]
            self.assertEqual(fname, expected_file, f"{cid} deve estar em {expected_file}")
            skipped = getattr(fn, "__unittest_skip__", False) or getattr(cls, "__unittest_skip__", False)
            if checks[cid]["status"] == "active":
                self.assertFalse(skipped, f"{fname}::{name}: verificação ativa {cid} não pode ser pulada")
            else:
                self.assertTrue(skipped, f"{fname}::{name}: verificação pendente {cid} deve ser pulada")
            covered.add(cid)
        self.assertEqual(set(checks) - covered, set(), "toda verificação do manifesto precisa de teste")

    def test_pending_is_never_approval_and_evolution_gate(self):
        pend = gm.pending(MANIFEST)
        self.assertEqual(gm.evolution_allowed(MANIFEST), not pend)
        result = gm.approval(MANIFEST, 0)
        self.assertEqual(result["approved"], not pend)
        self.assertFalse(gm.approval(MANIFEST, 1)["approved"])
        all_active = {"invariants": {k: {"file": v["file"], "checks": {c: {"status": "active"} for c in v["checks"]}}
                                     for k, v in MANIFEST["invariants"].items()}}
        self.assertTrue(gm.evolution_allowed(all_active))
        self.assertTrue(gm.approval(all_active, 0)["approved"])

    def test_manifest_is_protected(self):
        from appfactory.security.paths import ProtectedPaths
        self.assertIsNotNone(ProtectedPaths.load(REPO).match(gm.MANIFEST_FILE))


if __name__ == "__main__":
    unittest.main()
