"""G23-04..G23-07, G23-16..G23-19 (parte de modo) — modos e histerese por tempo ativo (D-0062, D-0069, D-0071)."""
import copy
import json
import unittest

from appfactory.resources.gpu_accounting import account
from appfactory.resources.modes import ModeTracker
from appfactory.resources.policy import VRAM_BASE_MIB, load_policy, parse_policy
from appfactory.resources.probes import RawSample
from tests.fakes.probes import HEALTHY, REPO, FakeResourceClock

POLICY = load_policy(REPO)


class Driver:
    def __init__(self, policy=POLICY, **over):
        self.pol = policy
        self.t = ModeTracker(policy)
        self.clock = FakeResourceClock()
        self.vals = copy.deepcopy(HEALTHY)
        self.vals.update(over)
        self.first = True

    def set(self, **kw):
        self.vals.update(kw)

    def step(self, seconds=1.0, stop=False, file=False, call=False):
        if not self.first:
            self.clock.advance(seconds)
        self.first = False
        s = RawSample(active_ms=self.clock.active, suspend_ms=self.clock.suspend, boot_id=self.clock.boot)
        for k, v in self.vals.items():
            setattr(s, k, copy.deepcopy(v))
        acct = account(s.vram_total_mib, s.vram_used_mib, s.ollama_models, base_mib=VRAM_BASE_MIB,
                       margin_mib=512, reserve_mib=768)
        return self.t.update(s, acct, factory_stop_active=stop, stop_file_present=file, factory_call_active=call)

    def run(self, seconds, **kw):
        st = None
        for _ in range(int(seconds)):
            st = self.step(1, **kw)
        return st


class ModeOrder(unittest.TestCase):
    def test_g23_04_evaluation_order(self):
        d = Driver(ram_available_gb=1.0, on_ac=False, fullscreen=True, idle_s=900)
        self.assertEqual(d.step().candidate, "CRITICAL")
        d.set(ram_available_gb=8.0)
        self.assertEqual(d.step().candidate, "BATTERY")
        d.set(on_ac=True)
        self.assertEqual(d.step().candidate, "CONTENTION")
        d.set(fullscreen=False)
        self.assertEqual(d.step().candidate, "BACKGROUND")
        d.set(idle_s=0)
        self.assertEqual(d.step().candidate, "FOREGROUND")

    def test_unknown_values_are_worst_case(self):
        d = Driver()
        d.vals = {}
        st = d.step()
        self.assertEqual(st.mode, "CRITICAL")                       # RAM/disco/GPU desconhecidos
        self.assertIn("gpu_unknown", st.reasons["critical"])
        self.assertTrue(st.reasons["battery"])                      # energia desconhecida => bateria
        self.assertIn("fullscreen_or_d3d", st.reasons["contention"])

    def test_initial_mode_never_looser_than_foreground(self):
        self.assertEqual(Driver(idle_s=900).step().mode, "FOREGROUND")
        self.assertEqual(Driver(fullscreen=True).step().mode, "CONTENTION")
        self.assertEqual(Driver(on_ac=False).step().mode, "BATTERY")


class Hysteresis(unittest.TestCase):
    def test_g23_05_ten_seconds_of_active_time(self):
        d = Driver()
        d.run(3)
        d.set(fullscreen=True)
        st = d.step()                                               # t=0 da condição
        for _ in range(9):
            st = d.step()
        self.assertEqual(st.mode, "FOREGROUND")                     # 9 s: não muda
        self.assertEqual(d.step().mode, "CONTENTION")              # 10 s: muda

    def test_g23_05_interruption_gap_boot_sleep_restart(self):
        d = Driver()
        d.run(2)
        d.set(fullscreen=True)
        d.run(6)
        d.set(fullscreen=False)
        d.step()                                                    # interrompida aos 6 s
        d.set(fullscreen=True)
        st = d.run(10)                                              # t0 .. t0+9 s
        self.assertEqual(st.mode, "FOREGROUND")
        self.assertEqual(d.step().mode, "CONTENTION")
        # lacuna > 5 s reinicia
        d = Driver()
        d.step()
        d.set(fullscreen=True)
        d.run(5)
        st = d.step(seconds=6)
        self.assertTrue(st.continuity_reset)
        self.assertEqual(d.run(9).mode, "FOREGROUND")
        self.assertEqual(d.step().mode, "CONTENTION")
        # troca de boot reinicia
        d = Driver()
        d.step()
        d.set(fullscreen=True)
        d.run(8)
        d.clock.boot = "boot-B"
        st = d.step()
        self.assertTrue(st.continuity_reset)
        self.assertEqual(d.run(9).mode, "FOREGROUND")
        # sono (relógio com suspensão avança além do tempo ativo) reinicia
        d = Driver()
        d.step()
        d.set(fullscreen=True)
        d.run(8)
        d.clock.sleep_machine(30)
        st = d.step()
        self.assertTrue(st.continuity_reset)
        self.assertEqual(d.run(9).mode, "FOREGROUND")
        self.assertEqual(d.step().mode, "CONTENTION")

    def test_g23_05_sample_count_does_not_matter(self):
        d = Driver()
        d.step()
        d.set(fullscreen=True)
        d.step(0.1)
        self.assertEqual(d.step(2).mode, "FOREGROUND")              # 2 amostras em 2 s: não muda
        d2 = Driver()
        d2.step()
        d2.set(fullscreen=True)
        for _ in range(10):
            st = d2.step(0.9)                                       # 10 amostras em 8,1 s: não muda
        self.assertEqual(st.mode, "FOREGROUND")
        d3 = Driver()
        d3.step()
        d3.set(fullscreen=True)
        d3.step(5)
        self.assertEqual(d3.step(5).mode, "FOREGROUND")            # 2 amostras, 5 s: não muda
        self.assertEqual(d3.step(5).mode, "CONTENTION")            # 10 s contínuos, lacunas <= 5 s

    def test_g23_05_critical_and_user_return_immediate(self):
        d = Driver()
        d.run(3)
        d.set(ram_available_gb=1.4)
        self.assertEqual(d.step().mode, "CRITICAL")
        d = Driver(idle_s=700)
        d.step()
        self.assertEqual(d.run(10).mode, "BACKGROUND")
        d.set(idle_s=2)
        self.assertEqual(d.step().mode, "FOREGROUND")

    def test_d0071_idle_is_instantaneous(self):
        d = Driver(idle_s=650)
        st = d.step()
        self.assertEqual(st.candidate, "BACKGROUND")               # sem histórico de 10 min
        self.assertTrue(st.reasons["background"])
        d.set(idle_s=599)
        self.assertEqual(d.step().candidate, "FOREGROUND")


class Exits(unittest.TestCase):
    def test_g23_06_contention_battery_critical_exit_windows(self):
        d = Driver(fullscreen=True)
        d.step()
        d.set(fullscreen=False)
        self.assertEqual(d.run(120).mode, "CONTENTION")          # ausente t0 .. t0+119 s
        self.assertEqual(d.step().mode, "FOREGROUND")
        d = Driver(on_ac=False)
        d.step()
        d.set(on_ac=True)
        self.assertEqual(d.run(60).mode, "BATTERY")               # tomada t0 .. t0+59 s
        self.assertEqual(d.step().mode, "FOREGROUND")
        d = Driver(ram_available_gb=1.4)
        d.step()
        d.set(ram_available_gb=2.0)                                 # entre 1,5 e 2,5: fica em CRITICAL
        self.assertEqual(d.run(120).mode, "CRITICAL")
        d.set(ram_available_gb=2.5)
        self.assertEqual(d.run(60).mode, "CRITICAL")
        self.assertEqual(d.step().mode, "FOREGROUND")

    def test_g23_07_stop_keeps_critical_until_released(self):
        d = Driver()
        st = d.step(stop=False, file=True)                          # arquivo-gatilho => CRITICAL
        self.assertEqual(st.mode, "CRITICAL")
        st = d.run(120, stop=True, file=False)                      # arquivo apagado, STOP ainda ativo
        self.assertEqual(st.mode, "CRITICAL")
        self.assertIn("factory_stop", st.reasons["critical"])
        self.assertFalse(st.reasons["critical_exit_ok"])
        self.assertEqual(d.run(60, stop=False).mode, "CRITICAL")   # liberado: t0 .. t0+59 s
        self.assertEqual(d.step(stop=False).mode, "FOREGROUND")


class GpuRules(unittest.TestCase):
    def test_g23_16_foreign_util_only_without_factory_call(self):
        d = Driver(gpu_util_pct=90.0)
        self.assertNotIn("gpu_util", d.step(call=True).reasons["contention"])
        self.assertIn("gpu_util", d.step(call=False).reasons["contention"])

    def test_g23_16_foreign_util_uses_30s_average(self):
        """05 §1: GPU = média de 30 s (D-0074). Dado real de M2: uso alternando 0/~40% a cada amostra."""
        d = Driver()
        self.assertEqual(d.run(3, call=True).mode, "FOREGROUND")        # só amostras com chamada: sem histórico
        modes = []
        for i in range(11):                                             # t0 .. t0+10 s
            d.set(gpu_util_pct=0.0 if i % 2 else 50.0)
            st = d.step()
            self.assertIn("gpu_util", st.reasons["contention"])         # média > 20% em toda amostra
            modes.append(st.mode)
        self.assertEqual(modes[:10], ["FOREGROUND"] * 10)               # 9 s: não muda
        self.assertEqual(modes[10], "CONTENTION")                       # 10 s contínuos
        d = Driver()
        d.run(29)
        d.set(gpu_util_pct=100.0)
        st = d.step()                                                   # pico isolado: média ~3%
        self.assertNotIn("gpu_util", st.reasons["contention"])
        self.assertLess(st.reasons["gpu_util_avg"], 20)
        d = Driver(gpu_util_pct=90.0)
        for _ in range(5):
            d.step(call=True)                                           # amostras com chamada não entram
        d.set(gpu_util_pct=0.0)
        self.assertEqual(d.step().reasons["gpu_util_avg"], 0.0)
        d = Driver(gpu_util_pct=None)
        self.assertIn("gpu_util", d.step().reasons["contention"])      # desconhecido => pior caso

    def test_g23_17_heuristics(self):
        raw = json.loads((REPO / "config" / "resources.yaml").read_text(encoding="utf-8"))
        raw["gpu"]["contention_processes"] = ["Game.exe", "EpicGamesLauncher.exe"]
        pol = parse_policy(raw)
        self.assertEqual(Driver(pol, fullscreen=True).step().candidate, "CONTENTION")
        st = Driver(pol, processes=["explorer.exe", "game.exe"]).step()
        self.assertEqual(st.candidate, "CONTENTION")
        self.assertIn("process:game.exe", st.reasons["contention"])
        self.assertEqual(Driver(pol, processes=["EpicGamesLauncher.exe"]).step().candidate, "FOREGROUND")
        d = Driver(pol)
        d.run(3)
        d.set(vram_used_mib=105.0 + 600)
        st = d.step()
        self.assertEqual(st.reasons["contention"], ["vram_growth"])
        d = Driver(pol, vram_used_mib=105.0 + 1600)
        self.assertIn("vram_foreign", d.step().reasons["contention"])

    def test_g23_18_19_temperature_and_disk(self):
        self.assertEqual(Driver(gpu_temp_c=87.0).step().mode, "CRITICAL")
        self.assertEqual(Driver(gpu_temp_c=80.0).step().mode, "FOREGROUND")
        disks = {"C": {"free_gb": 32.9, "size_gb": 475.7}, "D": {"free_gb": 4.9, "size_gb": 465.7}}
        self.assertEqual(Driver(disks=disks).step().mode, "CRITICAL")


if __name__ == "__main__":
    unittest.main()
