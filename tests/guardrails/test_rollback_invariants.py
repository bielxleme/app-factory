"""I3 — rollback funciona (revert de merge, restauração de marco) (09 §1). Pendente até a fatia 2.7."""
import importlib
import unittest

from tests.guardrails._support import guard


class RollbackInvariants(unittest.TestCase):
    @guard("I3.rollback")
    def test_rollback_revert_and_milestone_restore(self):
        importlib.import_module("appfactory.checkpoints.rollback")   # fatia 2.7


if __name__ == "__main__":
    unittest.main()
