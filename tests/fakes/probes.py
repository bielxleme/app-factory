"""Sondas e relógio falsos do Resource Manager — **somente em testes** (nunca em src/)."""
from __future__ import annotations

import datetime
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

HEALTHY = {
    "logical_cpus": 12, "cpu_pct": 10.0, "ram_total_gb": 23.71, "ram_available_gb": 8.0, "commit_free_gb": 18.0,
    "gpu_name": "Fake RTX", "gpu_util_pct": 0.0, "vram_total_mib": 6141.0, "vram_used_mib": 105.0,
    "gpu_temp_c": 46.0, "gpu_power_w": 2.3, "gpu_source": "nvml", "gpu_pids": [], "ollama_models": [],
    "fullscreen": False, "idle_s": 0.0, "on_ac": True, "has_battery": True, "battery_pct": 79.0,
    "disks": {"C": {"free_gb": 32.9, "size_gb": 475.7}, "D": {"free_gb": 177.8, "size_gb": 465.7}},
    "processes": ["explorer.exe", "chrome.exe"],
}


class FakeResourceClock:
    """Tempo ativo, relógio com suspensão, boot e parede — controláveis."""

    def __init__(self) -> None:
        self.active = 5_000_000
        self.suspend = 9_000_000
        self.boot = "boot-A"
        self.epoch = time.time()

    def active_ms(self) -> int:
        return self.active

    def suspend_ms(self) -> int:
        return self.suspend

    def monotonic(self) -> float:
        return self.suspend / 1000.0

    def boot_id(self) -> str:
        return self.boot

    def now_iso(self) -> str:
        return datetime.datetime.fromtimestamp(self.epoch).astimezone().isoformat(timespec="milliseconds")

    def now_epoch(self) -> float:
        return self.epoch

    def advance(self, seconds: float) -> None:
        self.active += int(seconds * 1000)
        self.suspend += int(seconds * 1000)
        self.epoch += seconds

    def sleep_machine(self, seconds: float) -> None:
        """Suspensão: o relógio com suspensão avança, o tempo ativo não."""
        self.suspend += int(seconds * 1000)
        self.epoch += seconds

    def reboot(self) -> None:
        self.boot = "boot-" + uuid.uuid4().hex[:6]
        self.active = 1000


class ScriptedProbe:
    """Preenche a amostra com `values` (mutável entre chamadas). `fail=True` => exceção (pior caso)."""

    name = "fake"

    def __init__(self, **overrides) -> None:
        self.values = dict(HEALTHY)
        self.values.update(overrides)
        self.fail = False
        self.calls = 0

    def set(self, **kw) -> None:
        self.values.update(kw)

    def collect(self, s) -> None:
        self.calls += 1
        if self.fail:
            raise OSError("sonda falsa falhou")
        for k, v in self.values.items():
            setattr(s, k, v.copy() if isinstance(v, (dict, list)) else v)


def fake_manager(root, probe=None, clock=None, persist=True):
    from appfactory.resources.manager import ResourceManager
    from appfactory.resources.policy import load_policy

    clock = clock or FakeResourceClock()
    probe = probe or ScriptedProbe()
    rm = ResourceManager(root=root, probes=[probe], clock=clock, policy=load_policy(REPO),
                         suspend_clock=clock.suspend_ms, persist=persist, sleep=clock.advance,
                         monotonic=clock.monotonic)
    return rm, probe, clock
