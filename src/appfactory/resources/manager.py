"""ResourceManager (12 §6–§7): snapshot, modo, admissão e lease de GPU **em memória** (Fase 2.3).

- Somente leitura do sistema e do Job Manager: lê `factory_stop` (core.stop.get_state) e a presença de
  `.appfactory/STOP`; **nunca** libera o STOP, nunca muda estado de job (D-0060, D-0062).
- Persistência **só por eventos** `resource.*` na tabela `events` existente (D-0061): sem tabela nova, sem migração.
- `admit` lê **somente** o histórico do `watch` (D-0063/D-0071); histórico insuficiente => WAIT.
- Qualquer falha de sonda => pior caso; nunca GRANT otimista (05 §1)."""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from appfactory.core import stop as factory_stop
from appfactory.core.clock import SystemClock
from appfactory.core.paths import FactoryPaths
from appfactory.jobs.store import connect, emit, migrate, write_tx
from appfactory.resources.gpu_accounting import account
from appfactory.resources.history import History, load_recent
from appfactory.resources.modes import ModeState, ModeTracker, contention_process, work_disk_free
from appfactory.resources.policy import (HEAVY_EXTRA_RAM_GB, MODES, RAM_PER_AGENT_GB, RAM_WINDOW_S, TIERS,
                                         VRAM_BASE_MIB, load_policy)
from appfactory.resources.probes import RawSample, SampleSource, default_probes, suspend_inclusive_ms

KINDS = ("agent", "heavy", "gpu", "s2")
ACTOR = "resources"
EXIT_OK, EXIT_DENIED, EXIT_ERROR = 0, 3, 2


@dataclass(frozen=True)
class AdmissionRequest:
    kind: str
    priority: int = 1
    est_ram_gb: float = RAM_PER_AGENT_GB
    est_vram_mib: float | None = None
    model: str | None = None
    tier: str | None = None
    task_id: str | None = None

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"kind inválido: {self.kind!r} (use {', '.join(KINDS)})")
        if self.tier is not None and self.tier not in TIERS:
            raise ValueError(f"tier inválido: {self.tier!r}")


@dataclass
class Admission:
    decision: str                       # GRANT | DENY | WAIT
    reason: str
    mode: str | None = None
    retry_after_s: float | None = None
    details: dict = field(default_factory=dict)

    @property
    def granted(self) -> bool:
        return self.decision == "GRANT"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GpuLease:
    id: str
    model: str
    tier: str
    est_vram_mib: float
    priority: int
    acquired_active_ms: int


def _r(v, nd=2):
    return None if v is None else round(float(v), nd)


def sample_payload(s: RawSample, acct, state: ModeState, policy, interval_s: float) -> dict:
    """Conteúdo do evento `resource.snapshot` (append-only; D-0061, D-0063, D-0069)."""
    sample = {k: getattr(s, k) for k in ("cpu_pct", "logical_cpus", "ram_total_gb", "ram_available_gb",
                                         "commit_free_gb", "gpu_name", "gpu_util_pct", "vram_total_mib",
                                         "vram_used_mib", "gpu_temp_c", "gpu_power_w", "gpu_source", "fullscreen",
                                         "idle_s", "on_ac", "has_battery", "battery_pct", "disks", "ollama_models",
                                         "ollama_age_s")}
    sample["contention_process"] = contention_process(s, policy)
    return {"v": 1, "ts": s.ts, "active_ms": int(s.active_ms), "suspend_ms": int(s.suspend_ms), "boot_id": s.boot_id,
            "policy_sha256": policy.sha256, "interval_s": interval_s, "sample": sample, "account": acct.to_dict(),
            "mode_state": state.to_dict(), "failures": list(s.failures)}


class ResourceManager:
    def __init__(self, root=None, probes=None, clock=None, policy=None, suspend_clock=None, persist: bool = True,
                 sleep=time.sleep, monotonic=time.monotonic) -> None:
        self.paths = FactoryPaths(root if root is not None else Path.cwd())
        self.root = self.paths.root
        self.clock = clock or SystemClock()
        self.suspend_clock = suspend_clock or suspend_inclusive_ms
        self.policy = policy or load_policy(self.root)
        self._probes = probes
        self._source: SampleSource | None = None
        self.persist = persist
        self.sleep = sleep
        self.monotonic = monotonic
        self._agents = 0
        self._heavy = 0
        self._leases: list[GpuLease] = []
        self._last_admission_ms: int | None = None

    # ------------------------------------------------------------------ infraestrutura
    @property
    def source(self) -> SampleSource:
        if self._source is None:
            probes = self._probes if self._probes is not None else default_probes(self.root)
            self._source = SampleSource(probes, self.clock, self.suspend_clock)
        return self._source

    def close(self) -> None:
        if self._source is not None:
            self._source.close()

    def _conn(self):
        conn = connect(self.paths.db)
        migrate(conn)                       # só garante o schema existente (sem migração nova — D-0061)
        return conn

    def _stop_state(self, conn) -> tuple[bool, bool]:
        """Somente leitura: `factory_stop` (fonte da verdade) e presença do arquivo-gatilho. Nunca libera."""
        return bool(factory_stop.get_state(conn).get("active")), self.paths.stop_file.exists()

    def _account(self, s: RawSample, mode: str):
        return account(s.vram_total_mib, s.vram_used_mib, s.ollama_models, base_mib=VRAM_BASE_MIB,
                       margin_mib=self.policy.gpu["measurement_margin_mib"], reserve_mib=self.policy.vram_reserve(mode))

    def _history(self, conn, seconds: float) -> History:
        now_a, now_s = int(self.clock.active_ms()), int(self.suspend_clock())
        payloads = load_recent(conn, now_a, now_a - int(seconds * 1000) - 5000)
        return History(payloads, now_active_ms=now_a, now_suspend_ms=now_s, boot_id=str(self.clock.boot_id()),
                       policy_sha256=self.policy.sha256)

    def _emit(self, conn, type_: str, payload: dict, reason: str | None = None) -> None:
        if not self.persist:
            return
        with write_tx(conn):
            emit(conn, self.clock.now_iso(), type_, actor=ACTOR, reason=reason, payload=payload)

    # ------------------------------------------------------------------ leitura
    def sample(self) -> RawSample:
        return self.source.sample()

    def snapshot(self, samples: int = 2, interval_s: float = 1.0) -> dict:
        """ResourceSnapshot (12 §7). Faz `samples` leituras (01 §4: 2); janelas vêm do histórico do `watch`.
        Não grava nada."""
        tracker = ModeTracker(self.policy)
        s = state = acct = None
        for i in range(max(1, int(samples))):
            if i:
                self.sleep(interval_s)
            s = self.sample()
            conn = self._conn()
            try:
                stop_active, stop_file = self._stop_state(conn)
            finally:
                conn.close()
            acct = self._account(s, tracker.state.mode if tracker.state else "FOREGROUND")
            state = tracker.update(s, acct, factory_stop_active=stop_active, stop_file_present=stop_file)
            acct = self._account(s, state.mode)
        conn = self._conn()
        try:
            hist = self._history(conn, self.policy.cpu_window_s)
        finally:
            conn.close()
        mode, source = state.mode, "instant"
        if hist.latest is not None:
            mode, source = hist.latest["mode_state"]["mode"], "watch"
        complete = not hist.missing({"cpu": self.policy.cpu_window_s, "ram": RAM_WINDOW_S})
        return self._snapshot_dict(s, acct, mode, source, hist if complete else None, state)

    def _snapshot_dict(self, s: RawSample, acct, mode: str, source: str, hist, state) -> dict:
        th = self.policy.thresholds
        alerts = []
        c = (s.disks or {}).get("C")
        if c is None or c.get("free_gb", 0) < th["disk_gb"]["system_drive_warn"]:
            alerts.append("system_drive_low")                                     # 05 §4 (KI-0008)
        if s.ram_available_gb is None or s.ram_available_gb < th["ram_gb"]["shed_heavy"]:
            alerts.append("ram_below_shed_heavy")
        lease = self._leases[0].model if self._leases else None
        return {
            "ts": s.ts, "mode": mode, "mode_source": source, "candidate_mode": state.candidate if state else None,
            "cpu_pct_60s": _r(hist.avg("cpu_pct", self.policy.cpu_window_s, 100.0)) if hist else None,
            "cpu_pct_now": _r(s.cpu_pct), "logical_cpus": s.logical_cpus,
            "ram_available_gb": _r(s.ram_available_gb), "ram_total_gb": _r(s.ram_total_gb),
            "commit_free_gb": _r(s.commit_free_gb),
            "gpu": {"name": s.gpu_name, "source": s.gpu_source, "util_pct": _r(s.gpu_util_pct, 1),
                    "vram_total_mib": _r(s.vram_total_mib, 0), "vram_used_mib": _r(s.vram_used_mib, 0),
                    "temp_c": _r(s.gpu_temp_c, 1), "power_w": _r(s.gpu_power_w),
                    "vram_factory_mib": _r(acct.factory_mib, 0), "vram_ollama_foreign_mib": _r(acct.ollama_foreign_mib, 0),
                    "vram_other_mib": _r(acct.other_mib, 0), "vram_foreign_mib": _r(acct.foreign_mib, 0),
                    "vram_available_for_factory_mib": _r(acct.available_for_factory_mib, 0),
                    "foreign_util_pct": _r(s.gpu_util_pct, 1), "foreign_util_measured_at": s.ts,
                    "fullscreen_or_d3d": s.fullscreen, "contention_process": contention_process(s, self.policy)},
            "user_idle_s": _r(s.idle_s, 1), "on_ac": s.on_ac, "has_battery": s.has_battery,
            "battery_pct": _r(s.battery_pct, 0),
            "disk_free_gb": {k: (_r(v["free_gb"], 1) if v else None) for k, v in sorted((s.disks or {}).items())},
            "loaded_models": list(s.ollama_models or []),
            "active": {"agents": self._agents, "heavy": self._heavy, "gpu_lease": lease},
            "window_complete": hist is not None, "probe_failures": list(s.failures), "alerts": alerts,
            "boot_id": s.boot_id, "active_ms": s.active_ms,
        }

    def mode(self) -> dict:
        """Modo pelo histórico do `watch` (com histerese); sem histórico válido, candidato instantâneo."""
        conn = self._conn()
        try:
            hist = self._history(conn, 0)
            stop_active, stop_file = self._stop_state(conn)
        finally:
            conn.close()
        if hist.latest is not None:
            ms = hist.latest["mode_state"]
            pending_for = None
            if ms.get("pending_since_ms") is not None:
                pending_for = round((hist.now - ms["pending_since_ms"]) / 1000.0, 1)
            return {"mode": ms["mode"], "source": "watch", "candidate": ms.get("candidate"),
                    "pending": ms.get("pending"), "pending_for_s": pending_for, "reasons": ms.get("reasons"),
                    "factory_stop": stop_active or stop_file}
        s = self.sample()
        tracker = ModeTracker(self.policy)
        st = tracker.update(s, self._account(s, "FOREGROUND"), factory_stop_active=stop_active,
                            stop_file_present=stop_file)
        return {"mode": st.mode, "source": "instant", "candidate": st.candidate, "pending": st.pending,
                "pending_for_s": None, "reasons": st.reasons, "factory_stop": stop_active or stop_file,
                "history": hist.problem, "note": "sem histórico do watch: modo instantâneo, sem histerese"}

    # ------------------------------------------------------------------ admissão (04 §8; 05 §3–§4)
    def admit(self, req: AdmissionRequest) -> Admission:
        conn = self._conn()
        try:
            result = self._decide(conn, req)
            if result.decision != "GRANT":
                self._emit(conn, "resource.admission_denied",
                           {"request": asdict(req), "decision": result.decision, "reason": result.reason,
                            "mode": result.mode, "retry_after_s": result.retry_after_s, "details": result.details},
                           reason=result.reason)
        finally:
            conn.close()
        if result.granted:
            self._last_admission_ms = int(self.clock.active_ms())
            if req.kind == "agent":
                self._agents += 1
            elif req.kind == "heavy":
                self._heavy += 1
        return result

    def release(self, kind: str) -> None:
        if kind == "agent" and self._agents:
            self._agents -= 1
        elif kind == "heavy" and self._heavy:
            self._heavy -= 1

    def _decide(self, conn, req: AdmissionRequest) -> Admission:
        pol, th = self.policy, self.policy.thresholds
        stop_active, stop_file = self._stop_state(conn)
        if stop_active or stop_file:                                           # D-0028, D-0062
            return Admission("DENY", "factory_stop", "CRITICAL", details={"stop_file": stop_file})
        windows = {"cpu": pol.cpu_window_s, "ram": RAM_WINDOW_S}
        if req.kind == "gpu":
            windows["gpu"] = pol.gpu_window_s
        hist = self._history(conn, max(windows.values()))
        missing = hist.missing(windows)
        if missing:                                                             # D-0063: sem histórico => WAIT
            return Admission("WAIT", "window_incomplete", None, max(1.0, max(missing.values())),
                             {"missing": missing, "hint": "rode `af resources watch` para acumular histórico"})
        latest = hist.latest
        mode = latest["mode_state"]["mode"]
        if mode not in MODES or mode == "CRITICAL":
            return Admission("WAIT", "mode_critical", mode, 60.0)
        sample = RawSample.from_dict(latest["sample"])
        now = hist.now
        details: dict = {}
        cpu = hist.avg("cpu_pct", pol.cpu_window_s, 100.0)
        ram = hist.min("ram_available_gb", RAM_WINDOW_S, 0.0)
        details.update(cpu_pct_60s=round(cpu, 1), ram_min_30s_gb=round(ram, 2))
        if ram < th["ram_gb"]["shed_heavy"]:
            details["recommended_actions"] = ["pause_newest_heavy", "unload_idle_factory_model"]   # 05 §4
        if cpu > th["cpu_pct"]["no_new_admission"]:
            return Admission("WAIT", "cpu_saturated", mode, 60.0, details)
        if cpu > th["cpu_pct"]["one_admission_per_min"] and self._last_admission_ms is not None:
            elapsed = (int(self.clock.active_ms()) - self._last_admission_ms) / 1000.0
            if elapsed < 60:
                return Admission("WAIT", "cpu_rate_limited", mode, round(60 - elapsed, 1), details)
        lim = pol.limit(mode)
        reserve = pol.ram_reserve(mode)                                         # CONTENTION = 3,0 GB (D-0072)
        details["ram_reserve_gb"] = reserve
        if mode == "BATTERY" and req.priority != 0:
            pct = sample.battery_pct if sample.battery_pct is not None else 0.0
            if pct < lim.get("pause_below_pct", 30):
                return Admission("WAIT", "battery_low", mode, 60.0, details)
        if req.kind == "agent":
            if ram < th["ram_gb"]["no_new_agents"]:
                return Admission("WAIT", "ram_low", mode, 30.0, details)
            slots = max(0, math.floor((ram - reserve) / RAM_PER_AGENT_GB))
            max_agents = min(int(lim["agents"]), slots)
            details.update(slots_ram=slots, max_agents=max_agents, active_agents=self._agents)
            if self._agents >= max_agents:
                return Admission("WAIT", "agent_slots", mode, 30.0, details)
        elif req.kind == "heavy":
            details.update(active_heavy=self._heavy, heavy_limit=lim["heavy"])
            if lim["heavy"] <= 0:
                return Admission("WAIT", "heavy_not_allowed_in_mode", mode, 60.0, details)
            if self._heavy >= lim["heavy"]:
                return Admission("WAIT", "heavy_slots", mode, 30.0, details)
            if ram < reserve + HEAVY_EXTRA_RAM_GB:
                return Admission("WAIT", "ram_low", mode, 30.0, details)
            if work_disk_free(sample, pol) < th["disk_gb"]["build_min"]:
                return Admission("WAIT", "disk", mode, 300.0, details)
        elif req.kind == "gpu":
            tier = req.tier or "T2"                                            # desconhecido => o mais exigente
            if tier not in lim["gpu_tiers"]:
                return Admission("WAIT", "gpu_tier_not_allowed_in_mode", mode, 60.0, {**details, "tier": tier})
            if ram < th["ram_gb"]["no_new_agents"]:
                return Admission("WAIT", "ram_low", mode, 30.0, details)
            temp = hist.max("gpu_temp_c", pol.gpu_window_s)
            details["gpu_temp_max_c"] = temp if math.isfinite(temp) else None
            if temp >= th["gpu"]["temp_throttle_c"]:
                return Admission("WAIT", "gpu_hot", mode, 60.0, details)
            if req.est_vram_mib is None or req.est_vram_mib <= 0:
                return Admission("DENY", "est_vram_required", mode, None, details)
            avail = float(latest["account"]["available_for_factory_mib"] or 0.0)
            held = sum(le.est_vram_mib for le in self._leases)
            details.update(vram_available_for_factory_mib=round(avail), vram_leased_mib=held, tier=tier)
            if self._leases:
                coloc = (tier == "T0" and pol.gpu["allow_t0_colocation"] and len(self._leases) == 1
                         and self._leases[0].tier != "T0")
                if not coloc:
                    return Admission("WAIT", "gpu_lease_busy", mode, 5.0, details)
            if req.est_vram_mib > avail - held:
                return Admission("WAIT", "vram", mode, 30.0, details)
        elif req.kind == "s2":
            need = reserve + th["docker_vm_admission_ram_gb"]                   # 08 §4.4
            details["s2_ram_needed_gb"] = need
            if ram < need:
                return Admission("WAIT", "ram_s2", mode, 60.0, details)
        return Admission("GRANT", "ok", mode, None, details)

    # ------------------------------------------------------------------ lease de GPU (em memória)
    def acquire_gpu(self, model: str, est_vram_mib: float, priority: int, tier: str | None = None) -> GpuLease | None:
        adm = self.admit(AdmissionRequest("gpu", priority, est_vram_mib=est_vram_mib, model=model, tier=tier))
        if not adm.granted:
            return None
        lease = GpuLease(uuid.uuid4().hex[:12], model, tier or "T2", float(est_vram_mib), priority,
                         int(self.clock.active_ms()))
        self._leases.append(lease)
        return lease

    def release_gpu(self, lease: GpuLease) -> None:
        self._leases = [x for x in self._leases if x.id != lease.id]

    # ------------------------------------------------------------------ watch (primeiro plano)
    def watch(self, interval_s: float | None = None, count: int | None = None, on_sample=None) -> int:
        """Amostra a cada `interval_s` (padrão `sampling.interval_s` = 1 s; D-0070), roda a histerese e grava
        `resource.snapshot` (append-only, sem retenção — D-0063), `resource.mode_changed` e `resource.probe_failed`."""
        interval = float(interval_s if interval_s is not None else self.policy.interval_s)
        if interval <= 0:
            raise ValueError("intervalo deve ser > 0")
        tracker = ModeTracker(self.policy)
        failing: set[str] = set()
        prev_mode = None
        n = 0
        conn = self._conn()
        try:
            wait = 0.0
            while count is None or n < count:
                if n:
                    self.sleep(wait)
                started = self.monotonic()
                s = self.sample()
                stop_active, stop_file = self._stop_state(conn)
                acct = self._account(s, tracker.state.mode if tracker.state else "FOREGROUND")
                state = tracker.update(s, acct, factory_stop_active=stop_active, stop_file_present=stop_file)
                acct = self._account(s, state.mode)
                payload = sample_payload(s, acct, state, self.policy, interval)
                now_failing = {f["probe"] for f in s.failures}
                if self.persist:
                    with write_tx(conn):
                        ts = self.clock.now_iso()
                        emit(conn, ts, "resource.snapshot", actor=ACTOR, payload=payload)
                        if prev_mode is not None and state.mode != prev_mode:
                            emit(conn, ts, "resource.mode_changed", actor=ACTOR, from_state=prev_mode,
                                 to_state=state.mode, reason=state.candidate, payload={"reasons": state.reasons})
                        for f in s.failures:
                            if f["probe"] not in failing:
                                emit(conn, ts, "resource.probe_failed", actor=ACTOR, reason=f["probe"], payload=f)
                failing = now_failing
                prev_mode = state.mode
                n += 1
                # intervalo nominal (D-0070): desconta o tempo gasto na amostra; nunca soma atrasos (D-0075)
                wait = max(0.0, interval - (self.monotonic() - started))
                if on_sample:
                    on_sample(payload)
        finally:
            conn.close()
        return n
