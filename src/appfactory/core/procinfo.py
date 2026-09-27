"""Identidade de processos (PID + horário de criação), 15 §5. Na dúvida, considera o processo VIVO
(a consequência é recuperação mais lenta, nunca execução duplicada)."""
from __future__ import annotations

import os
import sys


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _kernel32():  # pragma: no cover - depende do Windows
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    k32.GetProcessTimes.restype = wintypes.BOOL
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetExitCodeProcess.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    return k32


def process_create_time(pid: int) -> str | None:
    if pid <= 0:
        return None
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as fh:
                data = fh.read()
            rest = data[data.rindex(")") + 2 :].split()
            return "linux:" + rest[19]  # campo 22 (starttime)
        except (OSError, ValueError, IndexError):
            return None
    if sys.platform == "win32":  # pragma: no cover - depende do Windows
        try:
            import ctypes
            from ctypes import wintypes

            k32 = _kernel32()
            h = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return None
            try:
                c, e, k, u = (wintypes.FILETIME() for _ in range(4))
                if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
                    return None
                return f"win:{(c.dwHighDateTime << 32) | c.dwLowDateTime}"
            finally:
                k32.CloseHandle(h)
        except Exception:
            return None
    return None


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as fh:
                data = fh.read()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        state = data[data.rindex(")") + 2 :].split()[0]
        return state not in ("Z", "X")  # zumbi/morto não conta como vivo
    if sys.platform == "win32":  # pragma: no cover - depende do Windows
        try:
            import ctypes
            from ctypes import wintypes

            k32 = _kernel32()
            h = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED => o processo existe
            try:
                code = wintypes.DWORD(0)
                if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                    return True
                return code.value == 259  # STILL_ACTIVE
            finally:
                k32.CloseHandle(h)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_matches(pid: int | None, create_time: str | None) -> bool:
    """O processo `pid` ainda é o mesmo que registrou a tentativa?"""
    if not pid_alive(pid):
        return False
    if create_time is None:
        return True
    current = process_create_time(int(pid))
    if current is None:
        return True  # não dá para confirmar: conservador (vivo)
    return current == create_time


def current_identity() -> tuple[int, str | None]:
    pid = os.getpid()
    return pid, process_create_time(pid)
