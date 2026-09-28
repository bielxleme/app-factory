"""G23-15 — contabilidade de VRAM no WDDM (05 §1.1; D-0032, D-0059)."""
import unittest

from appfactory.resources.gpu_accounting import account


class GpuAccounting(unittest.TestCase):
    def test_g23_15_all_ollama_models_are_foreign_until_2_5(self):
        a = account(6141, 4000, [{"name": "qwen", "size_vram_mib": 2500}], base_mib=105, margin_mib=512,
                    reserve_mib=768)
        self.assertEqual(a.factory_mib, 0)                         # sem registro de posse (D-0059)
        self.assertEqual(a.ollama_foreign_mib, 2500)
        self.assertEqual(a.other_mib, 1395)
        self.assertEqual(a.foreign_mib, 3895)
        self.assertEqual(a.available_for_factory_mib, 6141 - 4000 - 768 - 512)

    def test_ownership_only_counts_when_given(self):
        a = account(6141, 4000, [{"name": "qwen", "size_vram_mib": 2500}], base_mib=105, margin_mib=512,
                    reserve_mib=768, factory_models=("qwen",))
        self.assertEqual((a.factory_mib, a.ollama_foreign_mib, a.foreign_mib), (2500, 0, 1395))

    def test_unknown_totals_are_worst_case(self):
        a = account(None, None, None, base_mib=105, margin_mib=512, reserve_mib=768)
        self.assertEqual(a.available_for_factory_mib, 0.0)
        self.assertIsNone(a.foreign_mib)
        a = account(6141, 6000, None, base_mib=105, margin_mib=512, reserve_mib=768)
        self.assertEqual(a.available_for_factory_mib, 0.0)        # nunca negativo
        self.assertEqual(a.foreign_mib, 6000 - 105)                # /api/ps falhou: tudo em "outros"


if __name__ == "__main__":
    unittest.main()
