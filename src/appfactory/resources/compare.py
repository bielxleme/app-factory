"""Comparação com o snapshot do `tools/diagnostics/measure-hardware.ps1` (14, fatia 2.3; AC23-07).

Estáticos (devem bater): CPUs lógicas iguais · RAM total ± 0,05 GB · VRAM total igual · tamanho de C:/D: ± 0,5 GB ·
presença de bateria igual. Dinâmicos (RAM livre, VRAM usada, disco livre, bateria %, ociosidade) só informativos.
O arquivo é só lido (JSON do PowerShell, possivelmente com BOM)."""
from __future__ import annotations

import json
from pathlib import Path

TOL_RAM_GB = 0.05
TOL_DISK_GB = 0.5


def load_hardware_snapshot(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("snapshot do measure-hardware inválido")
    return data


def _vram_total_from_query(hw: dict):
    q = ((hw.get("gpu") or {}).get("nvidia_query") or {})
    out = q.get("output")
    if not q.get("found") or not isinstance(out, str):
        return None
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    try:
        return float(parts[2])               # name, driver_version, memory.total, ...
    except (IndexError, ValueError):
        return None


def compare_hardware(sample, hw: dict) -> dict:
    checks = []

    def add(name, ours, theirs, tol):
        if ours is None or theirs is None:
            ok = False
        elif tol is None:
            ok = ours == theirs
        else:
            ok = abs(float(ours) - float(theirs)) <= tol
        checks.append({"check": name, "af": ours, "measure_hardware": theirs, "tolerance": tol, "ok": ok})

    add("logical_cpus", sample.logical_cpus, (hw.get("cpu") or {}).get("logical_processors"), None)
    add("ram_total_gb", None if sample.ram_total_gb is None else round(sample.ram_total_gb, 2),
        (hw.get("ram") or {}).get("visible_total_gb"), TOL_RAM_GB)
    add("vram_total_mib", None if sample.vram_total_mib is None else round(sample.vram_total_mib),
        None if _vram_total_from_query(hw) is None else round(_vram_total_from_query(hw)), None)
    for d in hw.get("disks") or []:
        letter = str(d.get("drive", "")).rstrip(":").upper()
        if letter in ("C", "D"):
            ours = (sample.disks or {}).get(letter)
            add(f"disk_{letter}_size_gb", None if not ours else round(ours["size_gb"], 1), d.get("size_gb"),
                TOL_DISK_GB)
    add("has_battery", sample.has_battery, (hw.get("power") or {}).get("has_battery"), None)
    info = {
        "ram_available_gb": {"af": sample.ram_available_gb, "measure_hardware": (hw.get("ram") or {}).get("available_gb")},
        "commit_free_gb": {"af": sample.commit_free_gb, "measure_hardware": (hw.get("ram") or {}).get("commit_free_gb")},
        "disk_free_gb": {"af": {k: (v or {}).get("free_gb") for k, v in (sample.disks or {}).items()},
                         "measure_hardware": {str(d.get("drive")): d.get("free_gb") for d in hw.get("disks") or []}},
        "battery_pct": {"af": sample.battery_pct, "measure_hardware": (hw.get("power") or {}).get("battery_charge_pct")},
        "user_idle_s": {"af": sample.idle_s, "measure_hardware": hw.get("user_idle_seconds")},
    }
    return {"ok": bool(checks) and all(c["ok"] for c in checks), "static": checks, "informative": info,
            "measured_at": hw.get("measured_at"), "probe_failures": list(sample.failures)}
