"""G23-01..G23-03 — política `config/resources.yaml` (D-0049, D-0064, D-0070, D-0072)."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from appfactory.resources.policy import (CANONICAL, PolicyError, check_ceilings, load_policy, parse_policy,
                                         validate_schema)

REPO = Path(__file__).resolve().parents[2]


def real_raw() -> dict:
    return json.loads((REPO / "config" / "resources.yaml").read_text(encoding="utf-8"))


class ResourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="af-pol-"))
        (self.tmp / "config").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, text: str) -> None:
        (self.tmp / "config" / "resources.yaml").write_text(text, encoding="utf-8")

    def test_g23_01_real_policy_valid(self):
        pol = load_policy(REPO)
        self.assertEqual(check_ceilings(pol), [])
        self.assertEqual(pol.interval_s, 1.0)                          # D-0070
        self.assertEqual(pol.ram_reserve("CONTENTION"), 3.0)          # D-0072
        self.assertNotIn("mode_confirmations", pol["sampling"])       # D-0070
        self.assertEqual(len(pol.sha256), 64)

    def test_g23_02_json_subset_only(self):
        self._write("# comentário\nsampling: {interval_s: 1}\n")
        with self.assertRaises(PolicyError):
            load_policy(self.tmp)
        self._write(json.dumps(real_raw())[:-1])                    # JSON truncado
        with self.assertRaises(PolicyError):
            load_policy(self.tmp)
        with self.assertRaises(PolicyError):                         # arquivo ausente
            load_policy(self.tmp / "nao-existe")

    def test_g23_02b_mode_confirmations_and_unknown_keys_rejected(self):
        raw = real_raw()
        raw["sampling"]["mode_confirmations"] = 2                   # D-0070: não existe
        self.assertTrue(any("mode_confirmations" in e for e in validate_schema(raw)))
        with self.assertRaises(PolicyError):
            parse_policy(raw)
        for mutate in (lambda r: r.update(hysteresis_s=10), lambda r: r["gpu"].pop("allow_t0_colocation"),
                       lambda r: r["thresholds"]["ram_gb"].update(extra=1.0)):
            raw = real_raw()
            mutate(raw)
            with self.assertRaises(PolicyError):
                parse_policy(raw)

    def test_g23_03_ceilings_and_canonical_thresholds(self):
        raw = real_raw()
        raw["limits"]["FOREGROUND"]["agents"] = 3
        raw["limits"]["BACKGROUND"]["agents"] = 5
        raw["gpu"]["max_factory_models_loaded"] = 2
        raw["gpu"]["max_concurrent_local_calls"] = 2
        raw["gpu"]["measurement_margin_mib"] = 128
        raw["reserves"]["ram_gb"]["CONTENTION"] = 2.9               # D-0072
        v = check_ceilings(raw)
        for needle in ("FOREGROUND.agents", "BACKGROUND.agents", "max_factory_models_loaded",
                       "max_concurrent_local_calls", "measurement_margin_mib", "ram_gb.CONTENTION"):
            self.assertTrue(any(needle in x for x in v), needle)
        with self.assertRaises(PolicyError):
            parse_policy(raw)

    def test_g23_03b_no_threshold_may_be_loosened(self):
        loosen = [
            ("thresholds.ram_gb.critical", lambda r: r["thresholds"]["ram_gb"].update(critical=1.0)),
            ("thresholds.ram_gb.no_new_agents", lambda r: r["thresholds"]["ram_gb"].update(no_new_agents=2.0)),
            ("thresholds.cpu_pct.no_new_admission", lambda r: r["thresholds"]["cpu_pct"].update(no_new_admission=95)),
            ("thresholds.gpu.temp_critical_c", lambda r: r["thresholds"]["gpu"].update(temp_critical_c=95)),
            ("thresholds.gpu.contention_vram_mib", lambda r: r["thresholds"]["gpu"].update(contention_vram_mib=4000)),
            ("reserves.ram_gb.FOREGROUND", lambda r: r["reserves"]["ram_gb"].update(FOREGROUND=1.0)),
            ("reserves.vram_mib.FOREGROUND", lambda r: r["reserves"]["vram_mib"].update(FOREGROUND=100)),
            ("docker_vm_admission_ram_gb", lambda r: r["thresholds"].update(docker_vm_admission_ram_gb=1.0)),
            ("disk_gb.critical", lambda r: r["thresholds"]["disk_gb"].update(critical=1)),
            ("limits.BATTERY.heavy", lambda r: r["limits"]["BATTERY"].update(heavy=1)),
            ("limits.FOREGROUND.gpu_tiers", lambda r: r["limits"]["FOREGROUND"].update(gpu_tiers=["T0", "T1", "T2"])),
            ("cpu_window_s", lambda r: r["sampling"].update(cpu_window_s=10)),
            ("idle_threshold_min", lambda r: r.update(idle_threshold_min=1)),
        ]
        for needle, mutate in loosen:
            raw = copy.deepcopy(real_raw())
            mutate(raw)
            self.assertTrue(any(needle in x for x in check_ceilings(raw)), needle)
        # direção segura (mais restritivo) continua aceita
        raw = real_raw()
        raw["thresholds"]["ram_gb"]["critical"] = 2.0
        raw["reserves"]["ram_gb"]["CONTENTION"] = 3.5
        raw["sampling"]["interval_s"] = 5
        self.assertEqual(check_ceilings(raw), [])
        self.assertEqual(CANONICAL["reserves.ram_gb"]["CONTENTION"], 3.0)


if __name__ == "__main__":
    unittest.main()
