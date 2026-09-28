"""I4 — limites aplicados e nunca acima dos tetos do RESOURCE_POLICY.md (09 §1)."""
import copy
import sqlite3
import unittest

from appfactory.jobs.errors import ProjectBusy
from appfactory.security.sandbox import CEILINGS, Limits, limits_for, validate_limits
from appfactory.security.sandbox.docker import docker_spec
from appfactory.security.sandbox.s1h_runner_user import s1h_launch_spec
from tests.guardrails._support import RESOURCE_POLICY_CEILINGS, guard
from tests.helpers import FactoryTestCase


class ResourceLimits(FactoryTestCase):
    @guard("I4.sandbox_limits_within_ceilings")
    def test_sandbox_limits_never_above_ceilings(self):
        for mode, ceil in RESOURCE_POLICY_CEILINGS.items():
            for key, value in ceil.items():
                self.assertLessEqual(CEILINGS[mode][key], value, (mode, key))
            spec = s1h_launch_spec(mode, False, "/t/tmp", "/t/wt")
            self.assertLessEqual(spec.job_memory_bytes, ceil["memory_bytes"])
            self.assertLessEqual(spec.process_memory_bytes, ceil["memory_bytes"])
            self.assertLessEqual(spec.cpu_rate, ceil["cpu_rate_pct"] * 100)
            self.assertLessEqual(spec.active_processes, ceil["max_processes"])
            self.assertLessEqual(docker_spec("T", "/t/wt", mode, False, "img", cpu_count=12).memory_bytes,
                                 ceil["memory_bytes"])
            self.assertLessEqual(limits_for(mode, 60).memory_bytes, ceil["memory_bytes"])
            with self.assertRaises(ValueError):
                validate_limits(Limits(ceil["memory_bytes"] + 1, ceil["cpu_rate_pct"], 32, "BELOW_NORMAL", 60), mode)
            with self.assertRaises(ValueError):
                validate_limits(Limits(ceil["memory_bytes"], ceil["cpu_rate_pct"] + 1, 32, "BELOW_NORMAL", 60), mode)

    @guard("I4.one_running_per_project")
    def test_one_active_job_per_project(self):
        m = self.manager()
        a = m.create_job("demo", "a", payload={"numbers": [1]})
        b = m.create_job("demo", "b", payload={"numbers": [1]})
        m.claim("e1", job_id=a["id"])
        with self.assertRaises(ProjectBusy):
            m.claim("e2", job_id=b["id"])
        conn = __import__("appfactory.jobs.store", fromlist=["connect"]).connect(self.paths.db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE jobs SET state = 'RUNNING' WHERE id = ?", (b["id"],))
        finally:
            conn.close()

    @guard("I4.resources_config_within_ceilings")
    def test_resources_config_within_ceilings(self):
        """Fatia 2.3 (D-0064, D-0070, D-0072). Cópia literal dos tetos e dos valores canônicos: não depende só do
        validador do próprio módulo (defesa em profundidade)."""
        from appfactory.resources.policy import PolicyError, check_ceilings, load_policy, parse_policy
        from appfactory.security.paths import load_policy_file
        from tests.guardrails._support import REPO

        raw = load_policy_file(REPO / "config" / "resources.yaml")
        self.assertEqual(check_ceilings(load_policy(REPO)), [])
        self.assertNotIn("mode_confirmations", raw["sampling"])                         # D-0070
        self.assertEqual(raw["sampling"]["interval_s"], 1)
        lim, gpu, th = raw["limits"], raw["gpu"], raw["thresholds"]
        self.assertLessEqual(lim["FOREGROUND"]["agents"], 2)
        self.assertLessEqual(lim["BACKGROUND"]["agents"], 4)
        self.assertLessEqual(gpu["max_factory_models_loaded"], 1)
        self.assertLessEqual(gpu["max_concurrent_local_calls"], 1)
        self.assertGreaterEqual(gpu["measurement_margin_mib"], 256)
        self.assertLessEqual(raw["max_processes"], 8)
        for mode, canon in {"FOREGROUND": 3.0, "BACKGROUND": 2.0, "BATTERY": 3.0, "CONTENTION": 3.0}.items():
            self.assertGreaterEqual(raw["reserves"]["ram_gb"][mode], canon, mode)
        for mode, canon in {"FOREGROUND": 768, "BACKGROUND": 384}.items():
            self.assertGreaterEqual(raw["reserves"]["vram_mib"][mode], canon, mode)
        for k, canon in {"no_new_agents": 3.0, "shed_heavy": 2.0, "critical": 1.5, "critical_exit": 2.5}.items():
            self.assertGreaterEqual(th["ram_gb"][k], canon, k)
        for k, canon in {"one_admission_per_min": 70, "no_new_admission": 85}.items():
            self.assertLessEqual(th["cpu_pct"][k], canon, k)
        for k, canon in {"contention_util_pct": 20, "contention_vram_mib": 1536, "contention_vram_growth_mib_30s": 512,
                         "temp_throttle_c": 80, "temp_critical_c": 87}.items():
            self.assertLessEqual(th["gpu"][k], canon, k)
        self.assertGreaterEqual(th["docker_vm_admission_ram_gb"], 3.0)
        for k, canon in {"build_min": 20, "critical": 5, "system_drive_warn": 15}.items():
            self.assertGreaterEqual(th["disk_gb"][k], canon, k)
        # afrouxar qualquer valor (ou reintroduzir mode_confirmations) torna a política inválida
        for mutate in (lambda r: r["limits"]["FOREGROUND"].update(agents=3),
                       lambda r: r["reserves"]["ram_gb"].update(CONTENTION=2.9),
                       lambda r: r["thresholds"]["gpu"].update(temp_critical_c=90),
                       lambda r: r["sampling"].update(mode_confirmations=2)):
            bad = copy.deepcopy(raw)
            mutate(bad)
            with self.assertRaises(PolicyError):
                parse_policy(bad)


if __name__ == "__main__":
    unittest.main()
