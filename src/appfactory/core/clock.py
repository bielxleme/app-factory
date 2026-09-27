"""Relógios (15 §4): parede para humanos; tempo ATIVO (sem suspensão) para leases; boot_id."""
from __future__ import annotations

import datetime
import sys
import time


class SystemClock:
    def now_iso(self) -> str:
        return datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")

    def now_epoch(self) -> float:
        return time.time()

    def active_ms(self) -> int:
        return active_time_ms()

    def boot_id(self) -> str:
        return boot_id()


def active_time_ms() -> int:
    """Tempo ativo do sistema em ms, excluindo suspensão/hibernação.

    Windows: QueryUnbiasedInterruptTime (unidades de 100 ns).
    Linux: time.monotonic() usa CLOCK_MONOTONIC, que não avança durante a suspensão.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            value = ctypes.c_ulonglong(0)
            if ctypes.windll.kernel32.QueryUnbiasedInterruptTime(ctypes.byref(value)):
                return int(value.value // 10_000)
        except Exception:  # pragma: no cover - depende do Windows
            pass
    return int(time.monotonic() * 1000)


def boot_id() -> str:
    """Identificador do boot atual; tempos ativos só são comparáveis dentro do mesmo boot."""
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/sys/kernel/random/boot_id", encoding="ascii") as fh:
                return "linux:" + fh.read().strip()
        except OSError:
            return "unknown"
    if sys.platform == "win32":  # pragma: no cover - depende do Windows
        try:
            import ctypes

            buf = ctypes.create_string_buffer(48)
            ret_len = ctypes.c_ulong(0)
            # SystemTimeOfDayInformation = 3; BootTime (LARGE_INTEGER) é o primeiro campo.
            status = ctypes.windll.ntdll.NtQuerySystemInformation(3, buf, 48, ctypes.byref(ret_len))
            if status == 0:
                return "win:" + str(int.from_bytes(buf.raw[:8], "little", signed=True))
        except Exception:
            pass
        return "unknown"
    return "unknown"
