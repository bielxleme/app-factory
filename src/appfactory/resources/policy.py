"""Política de recursos: `config/resources.yaml` (subconjunto JSON, D-0049) validada de forma estrita.

- Esquema fechado: chave desconhecida ou ausente => erro. `mode_confirmations` não existe (D-0070): a histerese
  de 10 s é regra fixa (D-0069) e não é configurável.
- Tetos do RESOURCE_POLICY.md e direção segura dos limiares canônicos de 05 §4/§9 (D-0064, D-0072): qualquer valor
  mais permissivo que o canônico torna a política inválida (falha fechada).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from appfactory.security.paths import PolicyFileError, load_policy_file

MODES = ("CRITICAL", "BATTERY", "CONTENTION", "BACKGROUND", "FOREGROUND")   # ordem de avaliação (05 §2)
TIERS = ("T0", "T1", "T2")
POLICY_REL = "config/resources.yaml"

# Regras fixas (não configuráveis) — 05 §1–§2, D-0069, D-0070, D-0071.
HYSTERESIS_S = 10                 # D-0069/D-0070: condição contínua por 10 s de tempo ativo
EXIT_WINDOW_S = {"CRITICAL": 60, "BATTERY": 60, "CONTENTION": 120}
RAM_WINDOW_S = 30                 # 05 §1: RAM = mínimo de 30 s
VRAM_GROWTH_WINDOW_S = 30         # 05 §1.1: crescimento de vram_terceiros em 30 s
MAX_SAMPLE_GAP_S = 5              # menor frequência de 05 §1 das métricas com janela (D-0063, D-0069)
SLEEP_TOLERANCE_MS = 1000         # relógio com suspensão avançou além do tempo ativo => houve sono (D-0069)
DISK_CRITICAL_EXIT_GB = 10.0      # 05 §2
VRAM_BASE_MIB = 105               # 05 §1.1: medido com tudo ocioso (calibração KI-0017)
RAM_PER_AGENT_GB = 0.4            # 04 §8
HEAVY_EXTRA_RAM_GB = 1.0          # 04 §8

# Valores canônicos (05 §3, §4, §9; RESOURCE_POLICY.md; D-0032, D-0038, D-0064, D-0072). Direção segura indicada.
CANONICAL = {
    "reserves.ram_gb": {"FOREGROUND": 3.0, "BACKGROUND": 2.0, "BATTERY": 3.0, "CONTENTION": 3.0},   # >=
    "reserves.vram_mib": {"FOREGROUND": 768, "BACKGROUND": 384},                                     # >=
    "limits.agents": {"FOREGROUND": 2, "BACKGROUND": 4, "BATTERY": 1, "CONTENTION": 2, "CRITICAL": 0},  # <=
    "limits.heavy": {"FOREGROUND": 1, "BACKGROUND": 2, "BATTERY": 0, "CONTENTION": 1, "CRITICAL": 0},   # <=
    "limits.gpu_tiers": {"FOREGROUND": ("T0", "T1"), "BACKGROUND": ("T0", "T1", "T2"), "BATTERY": (),
                         "CONTENTION": (), "CRITICAL": ()},                                          # subconjunto
    "limits.cpu_offload_gb": {"FOREGROUND": 0, "BACKGROUND": 4, "BATTERY": 0, "CONTENTION": 0, "CRITICAL": 0},  # <=
    "ram_gb": {"no_new_agents": 3.0, "shed_heavy": 2.0, "critical": 1.5, "critical_exit": 2.5},      # >=
    "cpu_pct": {"one_admission_per_min": 70, "no_new_admission": 85},                                # <=
    "gpu_le": {"contention_util_pct": 20, "contention_vram_mib": 1536, "contention_vram_growth_mib_30s": 512,
               "temp_throttle_c": 80, "temp_critical_c": 87},                                        # <=
    "docker_vm_admission_ram_gb": 3.0,                                                               # >=
    "disk_gb": {"build_min": 20, "critical": 5, "system_drive_warn": 15},                            # >=
}
CEILINGS = {  # RESOURCE_POLICY.md — tetos (só um humano aumenta; guardrail I4)
    "agents": {"FOREGROUND": 2, "BACKGROUND": 4},
    "max_factory_models_loaded": 1,
    "max_concurrent_local_calls": 1,
    "measurement_margin_min_mib": 256,
    "max_processes": 8,
}

_SCHEMA = {
    "sampling": {"interval_s", "cpu_window_s", "gpu_window_s"},
    "idle_threshold_min": None,
    "reserves": {"ram_gb", "vram_mib"},
    "limits": set(MODES),
    "gpu": {"max_factory_models_loaded", "max_concurrent_local_calls", "allow_t0_colocation",
            "measurement_margin_mib", "context_overhead_mib", "observation_window_s", "contention_processes",
            "benign_processes"},
    "thresholds": {"ram_gb", "cpu_pct", "gpu", "docker_vm_admission_ram_gb", "disk_gb"},
    "max_processes": None,
}
_LIMIT_KEYS_REQUIRED = {"agents", "heavy", "gpu_tiers"}
_LIMIT_KEYS_ALLOWED = _LIMIT_KEYS_REQUIRED | {"keep_alive", "cpu_offload_gb", "pause_below_pct"}


class PolicyError(ValueError):
    """Política de recursos inválida ou mais permissiva que o permitido (falha fechada)."""


@dataclass(frozen=True)
class ResourcePolicy:
    raw: dict
    sha256: str

    def __getitem__(self, key):
        return self.raw[key]

    @property
    def interval_s(self) -> float:
        return float(self.raw["sampling"]["interval_s"])

    @property
    def cpu_window_s(self) -> int:
        return int(self.raw["sampling"]["cpu_window_s"])

    @property
    def gpu_window_s(self) -> int:
        return int(self.raw["sampling"]["gpu_window_s"])

    def limit(self, mode: str) -> dict:
        return self.raw["limits"][mode]

    def ram_reserve(self, mode: str) -> float:
        """Reserva de RAM do modo (04 §8; D-0072). Modo sem reserva própria => a maior reserva (direção segura)."""
        res = self.raw["reserves"]["ram_gb"]
        return float(res.get(mode, max(res.values())))

    def vram_reserve(self, mode: str) -> int:
        res = self.raw["reserves"]["vram_mib"]
        return int(res.get(mode, max(res.values())))

    @property
    def thresholds(self) -> dict:
        return self.raw["thresholds"]

    @property
    def gpu(self) -> dict:
        return self.raw["gpu"]


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _check_keys(where: str, obj, required: set, allowed: set | None = None) -> list[str]:
    if not isinstance(obj, dict):
        return [f"{where}: deve ser objeto"]
    allowed = required if allowed is None else allowed
    errs = [f"{where}: chave não prevista '{k}'" for k in sorted(set(obj) - allowed)]
    errs += [f"{where}: chave ausente '{k}'" for k in sorted(required - set(obj))]
    return errs


def validate_schema(raw: dict) -> list[str]:
    """Esquema fechado (D-0049, D-0070). Devolve a lista de erros (vazia = ok)."""
    errs = _check_keys("raiz", raw, set(_SCHEMA))
    if errs:
        return errs
    for key, sub in _SCHEMA.items():
        if sub is not None:
            errs += _check_keys(key, raw[key], sub)
    if errs:
        return errs
    for k in ("interval_s", "cpu_window_s", "gpu_window_s"):
        if not _num(raw["sampling"][k]) or raw["sampling"][k] <= 0:
            errs.append(f"sampling.{k}: número > 0")
    if not _num(raw["idle_threshold_min"]) or raw["idle_threshold_min"] <= 0:
        errs.append("idle_threshold_min: número > 0")
    for group in ("ram_gb", "vram_mib"):
        g = raw["reserves"][group]
        if not isinstance(g, dict) or not g:
            errs.append(f"reserves.{group}: objeto não vazio")
            continue
        for mode, v in g.items():
            if mode not in MODES or not _num(v) or v < 0:
                errs.append(f"reserves.{group}.{mode}: modo válido e número >= 0")
    for mode in MODES:
        lim = raw["limits"][mode]
        errs += _check_keys(f"limits.{mode}", lim, _LIMIT_KEYS_REQUIRED, _LIMIT_KEYS_ALLOWED)
        if not isinstance(lim, dict):
            continue
        for k in ("agents", "heavy", "cpu_offload_gb", "pause_below_pct"):
            if k in lim and (not _num(lim[k]) or lim[k] < 0):
                errs.append(f"limits.{mode}.{k}: número >= 0")
        tiers = lim.get("gpu_tiers")
        if not isinstance(tiers, list) or any(t not in TIERS for t in tiers):
            errs.append(f"limits.{mode}.gpu_tiers: lista de {TIERS}")
        if "keep_alive" in lim and not isinstance(lim["keep_alive"], str):
            errs.append(f"limits.{mode}.keep_alive: texto")
    gpu = raw["gpu"]
    for k in ("max_factory_models_loaded", "max_concurrent_local_calls", "measurement_margin_mib",
              "context_overhead_mib", "observation_window_s"):
        if not _num(gpu[k]) or gpu[k] < 0:
            errs.append(f"gpu.{k}: número >= 0")
    if not isinstance(gpu["allow_t0_colocation"], bool):
        errs.append("gpu.allow_t0_colocation: booleano")
    for k in ("contention_processes", "benign_processes"):
        if not isinstance(gpu[k], list) or any(not isinstance(x, str) or not x for x in gpu[k]):
            errs.append(f"gpu.{k}: lista de nomes de executável")
    th = raw["thresholds"]
    errs += _check_keys("thresholds.ram_gb", th["ram_gb"], set(CANONICAL["ram_gb"]))
    errs += _check_keys("thresholds.cpu_pct", th["cpu_pct"], set(CANONICAL["cpu_pct"]))
    errs += _check_keys("thresholds.gpu", th["gpu"], set(CANONICAL["gpu_le"]))
    errs += _check_keys("thresholds.disk_gb", th["disk_gb"], set(CANONICAL["disk_gb"]) | {"work_drive"})
    if errs:
        return errs
    for group in ("ram_gb", "cpu_pct", "gpu"):
        for k, v in th[group].items():
            if not _num(v):
                errs.append(f"thresholds.{group}.{k}: número")
    for k, v in th["disk_gb"].items():
        if k == "work_drive":
            if not (isinstance(v, str) and len(v) == 1 and v.isalpha()):
                errs.append("thresholds.disk_gb.work_drive: letra de unidade")
        elif not _num(v):
            errs.append(f"thresholds.disk_gb.{k}: número")
    if not _num(th["docker_vm_admission_ram_gb"]):
        errs.append("thresholds.docker_vm_admission_ram_gb: número")
    if not _num(raw["max_processes"]):
        errs.append("max_processes: número")
    return errs


def check_ceilings(policy) -> list[str]:
    """Tetos do RESOURCE_POLICY.md + margem >= 256 MiB + limiares não mais permissivos que os canônicos
    (D-0064; reserva de CONTENTION 3,0 GB — D-0072). Vazio = ok."""
    raw = policy.raw if isinstance(policy, ResourcePolicy) else policy
    v: list[str] = []
    lim = raw["limits"]
    for mode, ceil in CEILINGS["agents"].items():
        if lim[mode]["agents"] > ceil:
            v.append(f"teto: limits.{mode}.agents {lim[mode]['agents']} > {ceil}")
    g = raw["gpu"]
    if g["max_factory_models_loaded"] > CEILINGS["max_factory_models_loaded"]:
        v.append(f"teto: gpu.max_factory_models_loaded {g['max_factory_models_loaded']} > 1")
    if g["max_concurrent_local_calls"] > CEILINGS["max_concurrent_local_calls"]:
        v.append(f"teto: gpu.max_concurrent_local_calls {g['max_concurrent_local_calls']} > 1")
    if g["measurement_margin_mib"] < CEILINGS["measurement_margin_min_mib"]:
        v.append(f"margem: gpu.measurement_margin_mib {g['measurement_margin_mib']} < 256 (D-0032)")
    if raw["max_processes"] > CEILINGS["max_processes"]:
        v.append(f"teto: max_processes {raw['max_processes']} > 8")
    for group in ("ram_gb", "vram_mib"):
        canon = CANONICAL[f"reserves.{group}"]
        for mode, value in canon.items():
            got = raw["reserves"][group].get(mode)
            if got is None or got < value:
                v.append(f"reserva: reserves.{group}.{mode} {got} < {value}")
    for mode in MODES:
        m = lim[mode]
        for key in ("agents", "heavy", "cpu_offload_gb"):
            canon = CANONICAL[f"limits.{key}"][mode]
            if m.get(key, 0) > canon:
                v.append(f"limite: limits.{mode}.{key} {m.get(key)} > {canon}")
        extra = set(m["gpu_tiers"]) - set(CANONICAL["limits.gpu_tiers"][mode])
        if extra:
            v.append(f"limite: limits.{mode}.gpu_tiers inclui {sorted(extra)}")
    if lim["BATTERY"].get("pause_below_pct", 0) < 30:
        v.append("limite: limits.BATTERY.pause_below_pct < 30")
    th = raw["thresholds"]
    for k, value in CANONICAL["ram_gb"].items():
        if th["ram_gb"][k] < value:
            v.append(f"limiar: thresholds.ram_gb.{k} {th['ram_gb'][k]} < {value}")
    for k, value in CANONICAL["cpu_pct"].items():
        if th["cpu_pct"][k] > value:
            v.append(f"limiar: thresholds.cpu_pct.{k} {th['cpu_pct'][k]} > {value}")
    for k, value in CANONICAL["gpu_le"].items():
        if th["gpu"][k] > value:
            v.append(f"limiar: thresholds.gpu.{k} {th['gpu'][k]} > {value}")
    if th["docker_vm_admission_ram_gb"] < CANONICAL["docker_vm_admission_ram_gb"]:
        v.append("limiar: thresholds.docker_vm_admission_ram_gb < 3.0")
    for k, value in CANONICAL["disk_gb"].items():
        if th["disk_gb"][k] < value:
            v.append(f"limiar: thresholds.disk_gb.{k} {th['disk_gb'][k]} < {value}")
    s = raw["sampling"]
    if s["cpu_window_s"] < 60:
        v.append("janela: sampling.cpu_window_s < 60 (05 §1)")
    if s["gpu_window_s"] < 30:
        v.append("janela: sampling.gpu_window_s < 30 (05 §1)")
    if raw["idle_threshold_min"] < 10:
        v.append("limiar: idle_threshold_min < 10 (05 §2)")
    if g["observation_window_s"] < 2:
        v.append("janela: gpu.observation_window_s < 2 (05 §1.1)")
    return v


def parse_policy(raw: dict, sha256: str = "") -> ResourcePolicy:
    if not isinstance(raw, dict):
        raise PolicyError("política deve ser objeto")
    errs = validate_schema(raw)
    if errs:
        raise PolicyError("config/resources.yaml inválido: " + "; ".join(errs))
    violations = check_ceilings(raw)
    if violations:
        raise PolicyError("config/resources.yaml mais permissivo que o permitido: " + "; ".join(violations))
    if not sha256:
        sha256 = hashlib.sha256(json.dumps(raw, sort_keys=True).encode("utf-8")).hexdigest()
    return ResourcePolicy(raw=raw, sha256=sha256)


def load_policy(root) -> ResourcePolicy:
    """Carrega e valida `config/resources.yaml` (D-0049). Qualquer problema => PolicyError (falha fechada)."""
    path = Path(root) / POLICY_REL
    try:
        raw = load_policy_file(path)
        data = path.read_bytes()
    except (PolicyFileError, OSError) as exc:
        raise PolicyError(f"config/resources.yaml ilegível ou fora do subconjunto JSON: {exc}") from exc
    return parse_policy(raw, hashlib.sha256(data).hexdigest())
