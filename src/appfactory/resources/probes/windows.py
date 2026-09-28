"""Sondas Windows via `ctypes` (D-0058, D-0068): somente leitura, sem WMI/CIM, sem subprocesso.

CPU `GetSystemTimes` · RAM/commit `GlobalMemoryStatusEx` · energia `GetSystemPowerStatus` · disco
`GetDiskFreeSpaceExW` · ociosidade `GetLastInputInfo` (leitura instantânea, D-0071) · tela cheia/D3D
`SHQueryUserNotificationState` · processos `CreateToolhelp32Snapshot`. Cada grupo falha isolado (pior caso)."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

GIB = 1024 ** 3
DRIVES = ("C", "D")
_FULLSCREEN_STATES = {2, 3, 4}   # QUNS_BUSY, QUNS_RUNNING_D3D_FULL_SCREEN, QUNS_PRESENTATION_MODE
TH32CS_SNAPPROCESS = 0x00000002


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class _SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def _filetime_pair():
    return ctypes.c_ulonglong(0), ctypes.c_ulonglong(0), ctypes.c_ulonglong(0)


class WindowsProbe:
    name = "windows"

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("WindowsProbe só existe no Windows")
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.u32 = ctypes.WinDLL("user32", use_last_error=True)
        self.shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        self.k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        self.k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self.k32.CloseHandle.argtypes = [wintypes.HANDLE]
        for fn in (self.k32.Process32FirstW, self.k32.Process32NextW):
            fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
            fn.restype = wintypes.BOOL
        self.k32.GetTickCount.restype = wintypes.DWORD
        self._prev_cpu = None

    # ------------------------------------------------------------------ grupos (cada um falha isolado)
    def collect(self, s) -> None:
        for name, fn in (("windows.cpu", self._cpu), ("windows.memory", self._memory), ("windows.power", self._power),
                         ("windows.disk", self._disks), ("windows.idle", self._idle),
                         ("windows.fullscreen", self._fullscreen), ("windows.processes", self._processes)):
            try:
                fn(s)
            except Exception as exc:  # noqa: BLE001 - pior caso daquele recurso
                s.failures.append({"probe": name, "error": f"{type(exc).__name__}: {exc}"[:300]})

    def _cpu(self, s) -> None:
        s.logical_cpus = os.cpu_count()
        idle, kernel, user = _filetime_pair()
        if not self.k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            raise ctypes.WinError(ctypes.get_last_error())
        total = kernel.value + user.value          # kernel inclui o ocioso
        cur = (idle.value, total)
        if self._prev_cpu is not None:
            d_idle, d_total = cur[0] - self._prev_cpu[0], cur[1] - self._prev_cpu[1]
            if d_total > 0:
                s.cpu_pct = max(0.0, min(100.0, 100.0 * (d_total - d_idle) / d_total))
        self._prev_cpu = cur

    def _memory(self, s) -> None:
        st = _MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not self.k32.GlobalMemoryStatusEx(ctypes.byref(st)):
            raise ctypes.WinError(ctypes.get_last_error())
        s.ram_total_gb = st.ullTotalPhys / GIB
        s.ram_available_gb = st.ullAvailPhys / GIB
        s.commit_free_gb = st.ullAvailPageFile / GIB

    def _power(self, s) -> None:
        st = _SYSTEM_POWER_STATUS()
        if not self.k32.GetSystemPowerStatus(ctypes.byref(st)):
            raise ctypes.WinError(ctypes.get_last_error())
        s.on_ac = {0: False, 1: True}.get(st.ACLineStatus)                 # 255 = desconhecido => None
        s.has_battery = None if st.BatteryFlag == 255 else not (st.BatteryFlag & 128)
        s.battery_pct = None if st.BatteryLifePercent == 255 else float(st.BatteryLifePercent)

    def _disks(self, s) -> None:
        for d in DRIVES:
            free, total, total_free = ctypes.c_ulonglong(0), ctypes.c_ulonglong(0), ctypes.c_ulonglong(0)
            ok = self.k32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(f"{d}:\\"), ctypes.byref(free), ctypes.byref(total),
                                             ctypes.byref(total_free))
            s.disks[d] = {"free_gb": free.value / GIB, "size_gb": total.value / GIB} if ok else None

    def _idle(self, s) -> None:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not self.u32.GetLastInputInfo(ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        s.idle_s = ((self.k32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0

    def _fullscreen(self, s) -> None:
        state = ctypes.c_int(0)
        hr = self.shell32.SHQueryUserNotificationState(ctypes.byref(state))
        if hr != 0:
            raise OSError(f"SHQueryUserNotificationState HRESULT {hr & 0xFFFFFFFF:#x}")
        s.fullscreen = state.value in _FULLSCREEN_STATES

    def _processes(self, s) -> None:
        snap = self.k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        names, by_pid = [], {}
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
            ok = self.k32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                names.append(entry.szExeFile)
                by_pid[int(entry.th32ProcessID)] = entry.szExeFile
                ok = self.k32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            self.k32.CloseHandle(snap)
        s.processes = sorted(set(names), key=str.lower)
        if s.gpu_pids:
            s.gpu_pids = [{"pid": p, "name": by_pid.get(p)} for p in
                          (x["pid"] if isinstance(x, dict) else x for x in s.gpu_pids)]
