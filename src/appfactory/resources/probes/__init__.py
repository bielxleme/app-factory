"""Sondas do Resource Manager (05 §1). Somente leitura; somente biblioteca padrão (D-0058).

Cada sonda preenche uma parte de `RawSample`. Campo `None` = desconhecido => a decisão usa o **pior caso**
daquele recurso (05 §1). Toda falha é registrada em `failures` (vira evento `resource.probe_failed` no `watch`)."""
from __future__ import annotations

import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Protocol

from appfactory.core.clock import SystemClock


@dataclass
class RawSample:
    active_ms: int = 0                      # tempo ativo (sem suspensão) — core/clock, 15 §4
    suspend_ms: int = 0                     # relógio que INCLUI a suspensão (detecta sono; D-0069)
    boot_id: str = "unknown"
    ts: str = ""
    logical_cpus: int | None = None
    cpu_pct: float | None = None            # uso total desde a amostra anterior
    ram_total_gb: float | None = None
    ram_available_gb: float | None = None   # GlobalMemoryStatusEx.ullAvailPhys (D-0068)
    commit_free_gb: float | None = None     # GlobalMemoryStatusEx.ullAvailPageFile (D-0068)
    gpu_name: str | None = None
    gpu_util_pct: float | None = None
    vram_total_mib: float | None = None
    vram_used_mib: float | None = None
    gpu_temp_c: float | None = None
    gpu_power_w: float | None = None
    gpu_source: str | None = None           # "nvml" ou o fallback de probes/nvidia.py; None = falhou
    gpu_pids: list | None = None
    ollama_models: list | None = None       # [{"name", "size_vram_mib"}] — /api/ps (somente leitura, D-0059)
    ollama_age_s: float | None = None       # idade do último resultado do /api/ps (consulta a cada 15 s, D-0075)
    fullscreen: bool | None = None
    idle_s: float | None = None             # leitura instantânea (D-0071)
    on_ac: bool | None = None
    has_battery: bool | None = None
    battery_pct: float | None = None
    disks: dict = field(default_factory=dict)   # {"C": {"free_gb", "size_gb"} | None, ...}
    processes: list | None = None           # nomes de executáveis em execução
    failures: list = field(default_factory=list)   # [{"probe", "error"}]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RawSample":
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)


class Probe(Protocol):
    name: str

    def collect(self, sample: RawSample) -> None: ...   # preenche campos; exceção => falha registrada


def suspend_inclusive_ms() -> int:
    """Relógio monotônico que avança durante a suspensão: GetTickCount64 (Windows) / CLOCK_BOOTTIME (Linux)."""
    if sys.platform == "win32":
        try:
            import ctypes

            fn = ctypes.windll.kernel32.GetTickCount64
            fn.restype = ctypes.c_ulonglong
            return int(fn())
        except Exception:  # pragma: no cover - depende do Windows
            pass
    boottime = getattr(time, "CLOCK_BOOTTIME", None)
    if boottime is not None:
        return int(time.clock_gettime(boottime) * 1000)
    return int(time.monotonic() * 1000)


class SampleSource:
    """Compõe as sondas numa amostra. Uma sonda que lança exceção vira falha registrada (pior caso)."""

    def __init__(self, probes, clock=None, suspend_clock=suspend_inclusive_ms) -> None:
        self.probes = list(probes)
        self.clock = clock or SystemClock()
        self.suspend_clock = suspend_clock

    def sample(self) -> RawSample:
        s = RawSample(active_ms=int(self.clock.active_ms()), suspend_ms=int(self.suspend_clock()),
                      boot_id=str(self.clock.boot_id() or "unknown"), ts=self.clock.now_iso())
        for probe in self.probes:
            try:
                probe.collect(s)
            except Exception as exc:  # noqa: BLE001 - qualquer falha => pior caso (05 §1)
                s.failures.append({"probe": getattr(probe, "name", type(probe).__name__),
                                   "error": f"{type(exc).__name__}: {exc}"[:300]})
        return s

    def close(self) -> None:
        for probe in self.probes:
            closer = getattr(probe, "close", None)
            if closer:
                try:
                    closer()
                except Exception:  # noqa: BLE001
                    pass


def default_probes(root=None) -> list:
    """Sondas reais da plataforma. Windows: Win32 + NVIDIA + runtime local. Outros: Linux mínima (D-0067)."""
    from appfactory.resources.probes.runtime_local import OllamaPsProbe

    if sys.platform == "win32":
        from appfactory.resources.probes.nvidia import NvidiaProbe
        from appfactory.resources.probes.windows import WindowsProbe

        return [NvidiaProbe(), WindowsProbe(), OllamaPsProbe()]   # NVIDIA antes: nomes dos PIDs na GPU
    from appfactory.resources.probes.linux import LinuxProbe

    return [LinuxProbe(root), OllamaPsProbe()]
