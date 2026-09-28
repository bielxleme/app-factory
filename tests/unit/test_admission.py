"""G23-07..G23-14, G23-18..G23-21, G23-23, G23-31 — admissão sobre o histórico do `watch` (D-0060..D-0063,
D-0071, D-0072)."""
import json
import unittest

from appfactory.jobs.manager import JobManager
from appfactory.resources.manager import AdmissionRequest
from appfactory.resources.policy import parse_policy
from tests.fakes.probes import REPO, fake_manager
from tests.helpers import FactoryTestCase


def agent(priority=1):
    return AdmissionRequest("agent", priority)


class AdmissionBase(FactoryTestCase):
    def rm(self, policy=None, **values):
        rm, probe, clock = fake_manager(self.tmp)
        if policy is not None:
            rm.policy = policy
        probe.set(**values)
        return rm, probe, clock

    def warm(self, rm, seconds=65):
        rm.watch(count=seconds + 1)


class History(AdmissionBase):
    def test_g23_21_startup_and_windows(self):
        rm, probe, clock = self.rm()
        a = rm.admit(agent())
        self.assertEqual((a.decision, a.reason), ("WAIT", "window_incomplete"))
        self.assertIn("no_history", a.details["missing"])
        rm.watch(count=1)
        a = rm.admit(agent())
        self.assertEqual(a.decision, "WAIT")
        self.assertIn("samples", a.details["missing"])
        rm.watch(count=31)                                                     # cobre 30 s
        a = rm.admit(agent())
        self.assertEqual(a.decision, "WAIT")
        self.assertIn("cpu", a.details["missing"])
        self.assertNotIn("ram", a.details["missing"])

    def test_g23_21_idle_needs_no_history(self):
        rm, probe, clock = self.rm(idle_s=700.0)
        rm.watch(count=91)
        self.assertEqual(rm.mode()["mode"], "BACKGROUND")
        a = rm.admit(agent())
        self.assertEqual((a.decision, a.mode), ("GRANT", "BACKGROUND"))       # D-0071

    def test_g23_31_admit_reads_only_watch_history(self):
        rm, probe, clock = self.rm()
        self.warm(rm)
        calls = probe.calls
        rm.sleep = lambda s: self.fail("admit não pode esperar")
        self.assertTrue(rm.admit(agent()).granted)
        self.assertEqual(probe.calls, calls)                                    # nenhuma coleta no admit
        clock.advance(10)                                                       # sem watch: antigo
        a = rm.admit(agent())
        self.assertEqual((a.decision, a.reason), ("WAIT", "window_incomplete"))
        self.assertIn("stale", a.details["missing"])
        rm2, probe2, clock2 = fake_manager(self.tmp, clock=clock)
        rm2.watch(count=31)                                                     # lacuna de 10 s: só 30 s contíguos
        a = rm2.admit(agent())
        self.assertEqual(a.decision, "WAIT")
        self.assertIn("cpu", a.details["missing"])

    def test_g23_31_policy_or_boot_change_invalidates_history(self):
        rm, probe, clock = self.rm()
        self.warm(rm)
        raw = json.loads((REPO / "config" / "resources.yaml").read_text(encoding="utf-8"))
        raw["thresholds"]["ram_gb"]["critical"] = 2.0
        rm.policy = parse_policy(raw)
        self.assertIn("policy_changed", rm.admit(agent()).details["missing"])
        rm, probe, clock = self.rm()
        self.warm(rm)
        clock.boot = "boot-Z"
        self.assertIn("boot_changed", rm.admit(agent()).details["missing"])


class Thresholds(AdmissionBase):
    def test_g23_07_factory_stop_denies(self):
        rm, probe, clock = self.rm()
        self.warm(rm)
        JobManager(paths=rm.paths).stop_factory(reason="test")
        a = rm.admit(agent())
        self.assertEqual((a.decision, a.reason), ("DENY", "factory_stop"))
        rm, probe, clock = self.rm()
        self.paths.stop_file.write_text("", encoding="utf-8")
        self.assertEqual(rm.admit(agent()).reason, "factory_stop")

    def test_g23_08_cpu(self):
        rm, probe, clock = self.rm(cpu_pct=71.0)
        self.warm(rm)
        self.assertTrue(rm.admit(agent()).granted)
        a = rm.admit(agent())
        self.assertEqual((a.decision, a.reason), ("WAIT", "cpu_rate_limited"))
        rm.watch(count=61)
        self.assertTrue(rm.admit(agent()).granted)
        rm, probe, clock = self.rm(cpu_pct=86.0)
        self.warm(rm)
        self.assertEqual(rm.admit(agent()).reason, "cpu_saturated")

    def test_g23_09_ram(self):
        rm, probe, clock = self.rm(ram_available_gb=2.9)
        self.warm(rm)
        a = rm.admit(agent())
        self.assertEqual((a.decision, a.reason), ("WAIT", "ram_low"))
        rm, probe, clock = self.rm(ram_available_gb=1.9)
        self.warm(rm)
        a = rm.admit(agent())
        self.assertEqual(a.reason, "ram_low")
        self.assertIn("pause_newest_heavy", a.details["recommended_actions"])
        rm, probe, clock = self.rm(ram_available_gb=1.4)
        self.warm(rm)
        a = rm.admit(agent())
        self.assertEqual((a.decision, a.reason, a.mode), ("WAIT", "mode_critical", "CRITICAL"))

    def test_g23_10_formula(self):
        rm, probe, clock = self.rm(ram_available_gb=5.2)
        self.warm(rm)
        results = [rm.admit(agent()) for _ in range(3)]
        self.assertEqual([r.decision for r in results], ["GRANT", "GRANT", "WAIT"])
        self.assertEqual(results[2].reason, "agent_slots")
        self.assertEqual(results[0].details["slots_ram"], 5)

    def test_g23_11_heavy_and_battery(self):
        rm, probe, clock = self.rm()
        self.warm(rm)
        self.assertTrue(rm.admit(AdmissionRequest("heavy")).granted)
        self.assertEqual(rm.admit(AdmissionRequest("heavy")).reason, "heavy_slots")
        rm, probe, clock = self.rm(on_ac=False)
        self.warm(rm)
        a = rm.admit(AdmissionRequest("heavy"))
        self.assertEqual((a.decision, a.reason, a.mode), ("WAIT", "heavy_not_allowed_in_mode", "BATTERY"))

    def test_g23_12_s2_and_contention_reserve(self):
        for ram, expected in ((5.9, "WAIT"), (6.0, "GRANT")):
            rm, probe, clock = self.rm(ram_available_gb=ram)
            self.warm(rm)
            self.assertEqual(rm.admit(AdmissionRequest("s2")).decision, expected, ram)
        # CONTENTION usa reserva de 3,0 GB (D-0072)
        for ram, kind, expected in ((5.9, "s2", "WAIT"), (6.0, "s2", "GRANT"), (3.3, "agent", "WAIT"),
                                    (3.9, "heavy", "WAIT"), (4.0, "heavy", "GRANT")):
            rm, probe, clock = self.rm(ram_available_gb=ram, fullscreen=True)
            self.warm(rm)
            a = rm.admit(AdmissionRequest(kind))
            self.assertEqual((a.mode, a.decision), ("CONTENTION", expected), (ram, kind))
            self.assertEqual(a.details["ram_reserve_gb"], 3.0)

    def test_g23_13_gpu_tier_by_mode(self):
        rm, probe, clock = self.rm()
        self.warm(rm)
        a = rm.admit(AdmissionRequest("gpu", tier="T2", est_vram_mib=3000))
        self.assertEqual(a.reason, "gpu_tier_not_allowed_in_mode")
        self.assertEqual(rm.admit(AdmissionRequest("gpu", est_vram_mib=500)).reason,
                         "gpu_tier_not_allowed_in_mode")                   # tier desconhecido => T2
        rm, probe, clock = self.rm(on_ac=False)
        self.warm(rm)
        self.assertEqual(rm.admit(AdmissionRequest("gpu", tier="T0", est_vram_mib=300)).reason,
                         "gpu_tier_not_allowed_in_mode")

    def test_g23_14_gpu_lease(self):
        rm, probe, clock = self.rm()
        self.warm(rm)
        lease = rm.acquire_gpu("qwen-t1", 3000, 1, tier="T1")
        self.assertIsNotNone(lease)
        self.assertIsNone(rm.acquire_gpu("outro-t1", 500, 1, tier="T1"))
        self.assertIsNone(rm.acquire_gpu("t0-grande", 2000, 1, tier="T0"))   # 4756 − 3000 < 2000
        t0 = rm.acquire_gpu("t0", 500, 1, tier="T0")
        self.assertIsNotNone(t0)
        self.assertIsNone(rm.acquire_gpu("t0-b", 100, 1, tier="T0"))
        rm.release_gpu(t0)
        rm.release_gpu(lease)
        self.assertIsNotNone(rm.acquire_gpu("qwen-t1", 3000, 1, tier="T1"))
        raw = json.loads((REPO / "config" / "resources.yaml").read_text(encoding="utf-8"))
        raw["gpu"]["allow_t0_colocation"] = False
        rm2, probe2, clock2 = self.rm(policy=parse_policy(raw))
        self.warm(rm2)
        self.assertIsNotNone(rm2.acquire_gpu("t1", 3000, 1, tier="T1"))
        self.assertIsNone(rm2.acquire_gpu("t0", 100, 1, tier="T0"))
        self.assertEqual(rm2.admit(AdmissionRequest("gpu", tier="T1")).reason, "est_vram_required")

    def test_g23_18_gpu_temperature(self):
        rm, probe, clock = self.rm(gpu_temp_c=80.0)
        self.warm(rm)
        self.assertEqual(rm.admit(AdmissionRequest("gpu", tier="T1", est_vram_mib=1000)).reason, "gpu_hot")
        rm, probe, clock = self.rm(gpu_temp_c=79.0)
        self.warm(rm)
        self.assertTrue(rm.admit(AdmissionRequest("gpu", tier="T1", est_vram_mib=1000)).granted)

    def test_g23_19_disk(self):
        disks = {"C": {"free_gb": 14.0, "size_gb": 475.7}, "D": {"free_gb": 19.0, "size_gb": 465.7}}
        rm, probe, clock = self.rm(disks=disks)
        self.warm(rm)
        a = rm.admit(AdmissionRequest("heavy"))
        self.assertEqual((a.decision, a.reason), ("WAIT", "disk"))
        self.assertIn("system_drive_low", rm.snapshot(samples=1)["alerts"])

    def test_g23_20_probe_failure_never_optimistic(self):
        rm, probe, clock = self.rm()
        probe.fail = True
        self.warm(rm)
        with __import__("appfactory.jobs.store", fromlist=["connect"]).connect(self.paths.db) as conn:
            types = [r[0] for r in conn.execute("SELECT type FROM events WHERE job_id IS NULL ORDER BY seq")]
        self.assertEqual(types.count("resource.probe_failed"), 1)             # na transição ok → falha
        self.assertEqual(types.count("resource.snapshot"), 66)
        for req in (agent(), AdmissionRequest("heavy"), AdmissionRequest("s2"),
                    AdmissionRequest("gpu", tier="T0", est_vram_mib=100)):
            self.assertNotEqual(rm.admit(req).decision, "GRANT")
        snap = rm.snapshot(samples=1)
        self.assertEqual(snap["mode"], "CRITICAL")
        self.assertEqual(snap["gpu"]["vram_available_for_factory_mib"], 0)

    def test_denials_are_events(self):
        rm, probe, clock = self.rm(ram_available_gb=2.9)
        self.warm(rm)
        rm.admit(agent())
        with __import__("appfactory.jobs.store", fromlist=["connect"]).connect(self.paths.db) as conn:
            row = conn.execute("SELECT * FROM events WHERE type = 'resource.admission_denied'").fetchone()
        self.assertEqual(row["reason"], "ram_low")
        self.assertIsNone(row["job_id"])
        self.assertEqual(json.loads(row["payload_json"])["decision"], "WAIT")


class Snapshot(AdmissionBase):
    def test_g23_23_snapshot_contract(self):
        rm, probe, clock = self.rm(ollama_models=[{"name": "qwen", "size_vram_mib": 2500.0}], vram_used_mib=2700.0)
        snap = rm.snapshot()
        for key in ("ts", "mode", "cpu_pct_60s", "ram_available_gb", "ram_total_gb", "gpu", "user_idle_s", "on_ac",
                    "battery_pct", "disk_free_gb", "loaded_models", "active"):
            self.assertIn(key, snap)
        for key in ("util_pct", "vram_total_mib", "vram_used_mib", "temp_c", "vram_factory_mib",
                    "vram_ollama_foreign_mib", "vram_other_mib", "vram_foreign_mib", "vram_available_for_factory_mib",
                    "foreign_util_pct", "foreign_util_measured_at", "fullscreen_or_d3d", "contention_process"):
            self.assertIn(key, snap["gpu"])
        self.assertEqual(snap["gpu"]["vram_factory_mib"], 0)
        self.assertEqual(snap["gpu"]["vram_ollama_foreign_mib"], 2500)
        self.assertIsNone(snap["cpu_pct_60s"])                                  # sem histórico do watch
        self.assertFalse(snap["window_complete"])
        self.assertEqual(snap["mode_source"], "instant")
        self.assertEqual(set(snap["active"]), {"agents", "heavy", "gpu_lease"})
        self.warm(rm)
        snap = rm.snapshot(samples=1)
        self.assertTrue(snap["window_complete"])
        self.assertIsInstance(snap["cpu_pct_60s"], float)
        self.assertEqual(snap["mode_source"], "watch")
        json.dumps(snap)


if __name__ == "__main__":
    unittest.main()
