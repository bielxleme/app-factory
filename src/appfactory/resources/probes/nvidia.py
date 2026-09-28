"""Sonda NVIDIA (D-0058). Caminho principal: **NVML via `ctypes`** (`nvml.dll` do driver, carregada só por caminho
absoluto). Fallback **implementado, permitido e isolado neste módulo**: `nvidia-smi --query-gpu`, usado somente
quando a NVML falhar — sem `shell=True`, somente consulta, ambiente limpo, tempo limite. Se os dois falharem,
os campos ficam `None` e a decisão usa o pior caso (VRAM disponível 0, temperatura crítica; 05 §1).

No WDDM não há VRAM por processo (05 §1.1): só totais, uso, temperatura, potência e PIDs na GPU.
Este é o **único** módulo que pode citar/invocar `nvidia-smi` (AC-06, G23-30)."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile

MIB = 1024 ** 2
SMI_QUERY = "--query-gpu=name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw"
SMI_TIMEOUT_S = 5
NVML_SUCCESS = 0
NVML_ERROR_INSUFFICIENT_SIZE = 7
NVML_TEMPERATURE_GPU = 0


class NvmlError(OSError):
    pass


class _Memory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


class _Utilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _ProcessInfo(ctypes.Structure):   # nvmlProcessInfo_t (v2/v3)
    _fields_ = [("pid", ctypes.c_uint), ("usedGpuMemory", ctypes.c_ulonglong), ("gpuInstanceId", ctypes.c_uint),
                ("computeInstanceId", ctypes.c_uint)]


def _process_buffer(entries: int):
    """Buffer com folga (64 bytes por entrada, bem acima dos 24 de nvmlProcessInfo_t): uma versão de driver com
    estrutura maior nunca escreve fora da memória alocada."""
    raw = (ctypes.c_ubyte * (64 * (entries + 1)))()
    return ctypes.cast(raw, ctypes.POINTER(_ProcessInfo)), raw


def _system_dir() -> str | None:
    if sys.platform != "win32":
        return None
    buf = ctypes.create_unicode_buffer(260)
    n = ctypes.windll.kernel32.GetSystemDirectoryW(buf, 260)
    return buf.value if 0 < n < 260 else None


def _candidates(filename: str) -> list[str]:
    """Somente caminhos absolutos conhecidos (nunca a ordem de busca padrão / diretório atual)."""
    out = []
    sysdir = _system_dir()
    if sysdir:
        out.append(os.path.join(sysdir, filename))
    pf = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles")
    if pf and os.path.isabs(pf):
        out.append(os.path.join(pf, "NVIDIA Corporation", "NVSMI", filename))
    return [p for p in out if os.path.isfile(p)]


class Nvml:
    """Acesso mínimo à NVML via `ctypes`."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path
        self._lib = None

    def _ensure(self):
        if self._lib is not None:
            return self._lib
        paths = [self._path] if self._path else _candidates("nvml.dll")
        if not paths or sys.platform != "win32":
            raise NvmlError("nvml.dll não encontrada em caminho absoluto conhecido")
        lib = ctypes.WinDLL(paths[0])
        self._check(lib.nvmlInit_v2(), "nvmlInit_v2")
        self._lib = lib
        return lib

    @staticmethod
    def _check(code: int, fn: str) -> None:
        if code != NVML_SUCCESS:
            raise NvmlError(f"{fn} retornou {code}")

    def query(self) -> dict:
        lib = self._ensure()
        try:
            handle = ctypes.c_void_p()
            self._check(lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)), "nvmlDeviceGetHandleByIndex_v2")
            name = ctypes.create_string_buffer(96)
            self._check(lib.nvmlDeviceGetName(handle, name, 96), "nvmlDeviceGetName")
            mem = _Memory()
            self._check(lib.nvmlDeviceGetMemoryInfo(handle, ctypes.byref(mem)), "nvmlDeviceGetMemoryInfo")
            util = _Utilization()
            self._check(lib.nvmlDeviceGetUtilizationRates(handle, ctypes.byref(util)), "nvmlDeviceGetUtilizationRates")
            temp = ctypes.c_uint(0)
            self._check(lib.nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU, ctypes.byref(temp)),
                        "nvmlDeviceGetTemperature")
            power = ctypes.c_uint(0)
            power_w = power.value / 1000.0 if lib.nvmlDeviceGetPowerUsage(handle, ctypes.byref(power)) == 0 else None
            return {"gpu_name": name.value.decode("utf-8", "replace"), "vram_total_mib": mem.total / MIB,
                    "vram_used_mib": mem.used / MIB, "gpu_util_pct": float(util.gpu), "gpu_temp_c": float(temp.value),
                    "gpu_power_w": power_w, "gpu_pids": self._pids(lib, handle)}
        except Exception:
            self.close()
            raise

    @staticmethod
    def _pids(lib, handle) -> list | None:
        pids: set[int] = set()
        found = False
        for fname in ("nvmlDeviceGetComputeRunningProcesses_v3", "nvmlDeviceGetGraphicsRunningProcesses_v3"):
            fn = getattr(lib, fname, None)
            if fn is None:
                continue
            cap = 64
            count = ctypes.c_uint(cap)
            arr, _keep = _process_buffer(cap)
            code = fn(handle, ctypes.byref(count), arr)
            if code == NVML_ERROR_INSUFFICIENT_SIZE and 0 < count.value <= 4096:
                cap = count.value
                count = ctypes.c_uint(cap)
                arr, _keep = _process_buffer(cap)
                code = fn(handle, ctypes.byref(count), arr)
            if code == NVML_SUCCESS and count.value > cap:
                code = NVML_ERROR_INSUFFICIENT_SIZE
            if code == NVML_SUCCESS:
                found = True
                pids.update(int(arr[i].pid) for i in range(count.value))
        return sorted(pids) if found else None      # desconhecido => não dispara CONTENTION sozinho (05 §1)

    def close(self) -> None:
        if self._lib is not None:
            try:
                self._lib.nvmlShutdown()
            except Exception:  # noqa: BLE001
                pass
            self._lib = None


def query_nvidia_smi(runner=subprocess.run) -> dict:
    """Fallback (D-0058): só consulta, argumentos fixos, executável por caminho absoluto, sem shell."""
    from appfactory.security.command_policy import clean_env

    exes = _candidates("nvidia-smi.exe")
    if not exes:
        raise FileNotFoundError("nvidia-smi não encontrado em caminho absoluto conhecido")
    flags = 0x08000000 if sys.platform == "win32" else 0     # CREATE_NO_WINDOW
    proc = runner([exes[0], SMI_QUERY, "--format=csv,noheader,nounits"], shell=False, capture_output=True,
                  text=True, timeout=SMI_TIMEOUT_S, check=False, env=clean_env("S0", tempfile.gettempdir()),
                  creationflags=flags)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise OSError(f"nvidia-smi retornou {proc.returncode}")
    return parse_smi_line(proc.stdout.strip().splitlines()[0])


def parse_smi_line(line: str) -> dict:
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 6:
        raise ValueError("saída inesperada do nvidia-smi")

    def num(v):
        try:
            return float(v)
        except ValueError:
            return None                              # "[N/A]" etc. => desconhecido

    total, used = num(parts[1]), num(parts[2])
    if total is None or used is None:
        raise ValueError("nvidia-smi sem VRAM total/usada")
    return {"gpu_name": parts[0], "vram_total_mib": total, "vram_used_mib": used, "gpu_util_pct": num(parts[3]),
            "gpu_temp_c": num(parts[4]), "gpu_power_w": num(parts[5]), "gpu_pids": None}


class NvidiaProbe:
    name = "nvidia"

    def __init__(self, nvml=None, smi=query_nvidia_smi) -> None:
        self.nvml = nvml if nvml is not None else Nvml()
        self.smi = smi

    def collect(self, s) -> None:
        try:
            data, source = self.nvml.query(), "nvml"
        except Exception as exc:  # noqa: BLE001 - NVML falhou => fallback isolado
            s.failures.append({"probe": "nvidia.nvml", "error": f"{type(exc).__name__}: {exc}"[:300]})
            try:
                data, source = self.smi(), "nvidia-smi"
            except Exception as exc2:  # noqa: BLE001 - os dois falharam => pior caso
                s.failures.append({"probe": "nvidia.nvidia-smi", "error": f"{type(exc2).__name__}: {exc2}"[:300]})
                return
        for k, v in data.items():
            setattr(s, k, v)
        s.gpu_source = source

    def close(self) -> None:
        closer = getattr(self.nvml, "close", None)
        if closer:
            closer()
