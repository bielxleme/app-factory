"""I4 — limites aplicados e nunca acima dos tetos do RESOURCE_POLICY.md (09 §1)."""
import importlib
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
        importlib.import_module("appfactory.resources.manager")   # fatia 2.3


if __name__ == "__main__":
    unittest.main()
