"""I7 — ações R3 exigem aprovação humana; orçamento pago padrão = 0 (09 §1)."""
import importlib
import shutil
import tempfile
import unittest
from pathlib import Path

from appfactory.security.command_policy import CommandPolicyConfig, CommandRequest, evaluate
from appfactory.security.paths import PathScope
from tests.guardrails._support import REPO, guard
from tests.helpers import FactoryTestCase


class HumanApproval(FactoryTestCase):
    @guard("I7.r2_r3_denied_without_approval")
    def test_r2_r3_denied(self):
        policy = CommandPolicyConfig.load(REPO)
        self.assertEqual(policy.preauthorized_r2, frozenset())
        wt = Path(tempfile.mkdtemp(prefix="af-i7-")).resolve()
        try:
            scope = PathScope(wt.parent, "J", "J-A01", wt)
            d = evaluate(CommandRequest(("npm", "install"), wt, 600, kind="install"), scope, policy)
            self.assertEqual((d.allowed, d.risk, d.rule), (False, "R2", "approval_required"))
            for argv in (("git", "push"), ("schtasks", "/create"), ("net", "user", "x", "/add")):
                d = evaluate(CommandRequest(argv, wt, 60), scope, policy)
                self.assertEqual((d.allowed, d.risk, d.needs_human), (False, "R3", True), argv)
        finally:
            shutil.rmtree(wt, ignore_errors=True)

    @guard("I7.release_requires_confirmation")
    def test_release_requires_confirmation(self):
        m = self.manager()
        m.stop_factory()
        for value in (False, None, "yes", 1):
            with self.assertRaises(PermissionError):
                m.resume_factory(confirmed=value)
        self.assertTrue(m.factory_stop_state()["active"])

    @guard("I7.interactive_approvals")
    def test_interactive_approvals(self):
        importlib.import_module("appfactory.security.approvals")   # fatia 2.6

    @guard("I7.paid_budget_zero")
    def test_paid_budget_zero(self):
        importlib.import_module("appfactory.routing.budget")       # fatia 2.5


if __name__ == "__main__":
    unittest.main()
