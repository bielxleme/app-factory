"""Modos com histerese por **tempo ativo contínuo** (05 §2; D-0069, D-0070, D-0071).

Ordem: CRITICAL > BATTERY > CONTENTION > BACKGROUND > FOREGROUND (o primeiro que casar vence).
- Entrar num modo de maior prioridade exige a condição **contínua por 10 s de tempo ativo** (regra fixa, não
  configurável), exceto CRITICAL (imediato). Voltar de BACKGROUND para FOREGROUND é imediato (volta do usuário).
- Saídas com janela própria, medidas do mesmo jeito: CRITICAL 60 s (+ STOP da fábrica liberado — D-0062),
  BATTERY 60 s, CONTENTION 120 s.
- Contagem reinicia se a condição falhar, se houver lacuna > 5 s entre amostras, troca de `boot_id` ou sono.
- O número de amostras não conta. Ociosidade = leitura instantânea (D-0071).
- Uso alheio da GPU: **média de 30 s** (`sampling.gpu_window_s`, 05 §1) só das amostras sem chamada da fábrica
  (05 §1.1; D-0074). Valores desconhecidos => pior caso (05 §1)."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import asdict, dataclass, field

from appfactory.resources.policy import (DISK_CRITICAL_EXIT_GB, EXIT_WINDOW_S, HYSTERESIS_S, MAX_SAMPLE_GAP_S,
                                         MODES, SLEEP_TOLERANCE_MS, VRAM_GROWTH_WINDOW_S)

PRIORITY = {m: i for i, m in enumerate(MODES)}          # menor = maior prioridade
RESTRICTIVE_AT_START = {"CRITICAL", "BATTERY", "CONTENTION"}


@dataclass
class ModeState:
    mode: str
    since_ms: int
    candidate: str = "FOREGROUND"
    pending: str | None = None
    pending_since_ms: int | None = None
    exit_since_ms: int | None = None
    continuity_reset: bool = False
    reasons: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ModeState":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def work_disk_free(sample, policy) -> float:
    d = (sample.disks or {}).get(policy.thresholds["disk_gb"]["work_drive"])
    return float(d["free_gb"]) if d and d.get("free_gb") is not None else 0.0      # desconhecido => 0 GB


def contention_process(sample, policy) -> str | None:
    if not sample.processes:
        return None                                     # lista desconhecida não dispara sozinha (05 §1)
    benign = {p.lower() for p in policy.gpu["benign_processes"]}
    wanted = {p.lower() for p in policy.gpu["contention_processes"]} - benign
    for name in sample.processes:
        if name and name.lower() in wanted:
            return name
    return None


class ModeTracker:
    def __init__(self, policy) -> None:
        self.policy = policy
        self.state: ModeState | None = None
        self._last = None                                   # (active_ms, suspend_ms, boot_id)
        self._vram_hist: deque = deque()                    # (active_ms, vram_foreign_mib)
        self._util_hist: deque = deque()                    # (active_ms, uso da GPU) sem chamada da fábrica

    # ------------------------------------------------------------------ continuidade (D-0069)
    def _continuous(self, s) -> bool:
        if self._last is None:
            return True
        a, sus, boot = self._last
        gap = s.active_ms - a
        slept = (s.suspend_ms - sus) - gap
        return (s.boot_id == boot and s.boot_id != "unknown" and 0 <= gap <= MAX_SAMPLE_GAP_S * 1000
                and slept <= SLEEP_TOLERANCE_MS)

    # ------------------------------------------------------------------ condições instantâneas
    def conditions(self, s, account, *, factory_stop_active: bool, stop_file_present: bool,
                   factory_call_active: bool = False) -> dict:
        th = self.policy.thresholds
        ram = s.ram_available_gb if s.ram_available_gb is not None else 0.0
        temp = s.gpu_temp_c if s.gpu_temp_c is not None else math.inf
        disk = work_disk_free(s, self.policy)
        stop = bool(factory_stop_active or stop_file_present)
        crit = []
        if ram < th["ram_gb"]["critical"]:
            crit.append("ram")
        if temp >= th["gpu"]["temp_critical_c"]:
            crit.append("gpu_temp" if s.gpu_temp_c is not None else "gpu_unknown")
        if disk < th["disk_gb"]["critical"]:
            crit.append("disk")
        if stop:
            crit.append("factory_stop")
        exit_ok = (ram >= th["ram_gb"]["critical_exit"] and temp <= th["gpu"]["temp_throttle_c"]
                   and disk >= DISK_CRITICAL_EXIT_GB and not stop)
        cont = []
        util_avg = None
        if not factory_call_active:          # uso alheio só em amostras sem chamada da fábrica (05 §1.1)
            util_avg = self._util_average(s)                  # média de 30 s (05 §1; D-0074)
            if util_avg > th["gpu"]["contention_util_pct"]:
                cont.append("gpu_util")
        foreign = account.foreign_mib if account is not None else None
        if foreign is None or foreign > th["gpu"]["contention_vram_mib"]:
            cont.append("vram_foreign")
        if foreign is not None:
            window_start = s.active_ms - VRAM_GROWTH_WINDOW_S * 1000
            past = [v for t, v in self._vram_hist if t >= window_start]
            if past and foreign - min(past) > th["gpu"]["contention_vram_growth_mib_30s"]:
                cont.append("vram_growth")
        if s.fullscreen is not False:        # desconhecido => assume tela cheia (05 §1)
            cont.append("fullscreen_or_d3d")
        proc = contention_process(s, self.policy)
        if proc:
            cont.append("process:" + proc)
        idle_s = s.idle_s if s.idle_s is not None else 0.0          # desconhecido => usuário ativo
        background = idle_s >= self.policy["idle_threshold_min"] * 60   # leitura instantânea (D-0071)
        battery = s.on_ac is not True        # desconhecido => na bateria
        if crit:
            cand = "CRITICAL"
        elif battery:
            cand = "BATTERY"
        elif cont:
            cand = "CONTENTION"
        elif background:
            cand = "BACKGROUND"
        else:
            cand = "FOREGROUND"
        return {"candidate": cand, "critical": crit, "critical_exit_ok": exit_ok, "battery": battery,
                "contention": cont, "background": background, "idle_s": idle_s,
                "gpu_util_avg": None if util_avg is None else round(util_avg, 1)}

    @staticmethod
    def _util_now(s) -> float:
        return float(s.gpu_util_pct) if s.gpu_util_pct is not None else 100.0     # desconhecido => pior caso

    def _util_average(self, s) -> float:
        start = s.active_ms - self.policy.gpu_window_s * 1000
        vals = [u for t, u in self._util_hist if t >= start] + [self._util_now(s)]
        return sum(vals) / len(vals)

    # ------------------------------------------------------------------ atualização
    def update(self, s, account=None, *, factory_stop_active: bool, stop_file_present: bool = False,
               factory_call_active: bool = False) -> ModeState:
        now = int(s.active_ms)
        continuous = self._continuous(s)
        if not continuous:
            self._vram_hist.clear()
            self._util_hist.clear()
        cond = self.conditions(s, account, factory_stop_active=factory_stop_active,
                               stop_file_present=stop_file_present, factory_call_active=factory_call_active)
        cand = cond["candidate"]
        st = self.state
        if st is None:
            initial = cand if cand in RESTRICTIVE_AT_START else "FOREGROUND"
            st = ModeState(mode=initial, since_ms=now)
            if cand != initial:
                st.pending, st.pending_since_ms = cand, now
        else:
            st.continuity_reset = not continuous
            if not continuous:                                   # D-0069: reinicia todas as contagens
                st.pending = st.pending_since_ms = st.exit_since_ms = None
            self._step(st, cand, cond, now)
        st.candidate = cand
        st.reasons = {k: cond[k] for k in ("critical", "contention", "battery", "background", "critical_exit_ok",
                                           "idle_s", "gpu_util_avg")}
        self.state = st
        self._last = (now, int(s.suspend_ms), s.boot_id)
        if not factory_call_active:
            self._util_hist.append((now, self._util_now(s)))
            while self._util_hist and self._util_hist[0][0] < now - self.policy.gpu_window_s * 1000:
                self._util_hist.popleft()
        foreign = account.foreign_mib if account is not None else None
        if foreign is not None:
            self._vram_hist.append((now, foreign))
            while self._vram_hist and self._vram_hist[0][0] < now - VRAM_GROWTH_WINDOW_S * 1000:
                self._vram_hist.popleft()
        return ModeState.from_dict(st.to_dict())

    @staticmethod
    def _switch(st: ModeState, mode: str, now: int) -> None:
        st.mode, st.since_ms = mode, now
        st.pending = st.pending_since_ms = st.exit_since_ms = None

    @staticmethod
    def _own_condition(mode: str, cond: dict) -> bool:
        return {"BATTERY": cond["battery"], "CONTENTION": bool(cond["contention"]),
                "BACKGROUND": cond["background"]}.get(mode, True)

    def _step(self, st: ModeState, cand: str, cond: dict, now: int) -> None:
        cur = st.mode
        if cand == "CRITICAL":                                   # entrada imediata
            if cur != "CRITICAL":
                self._switch(st, "CRITICAL", now)
            else:
                st.pending = st.pending_since_ms = st.exit_since_ms = None
            return
        if cur == "CRITICAL":                                    # saída: 60 s contínuos + STOP liberado (D-0062)
            st.pending = st.pending_since_ms = None
            if cond["critical_exit_ok"]:
                if st.exit_since_ms is None:
                    st.exit_since_ms = now
                if now - st.exit_since_ms >= EXIT_WINDOW_S["CRITICAL"] * 1000:
                    self._switch(st, cand, now)
            else:
                st.exit_since_ms = None
            return
        # janela de saída do modo atual: conta enquanto a condição do próprio modo estiver ausente
        if self._own_condition(cur, cond):
            st.exit_since_ms = None
        elif st.exit_since_ms is None:
            st.exit_since_ms = now
        if cand == cur:
            st.pending = st.pending_since_ms = None
            return
        if PRIORITY[cand] < PRIORITY[cur]:                       # modo de maior prioridade: 10 s contínuos
            if st.pending != cand:
                st.pending, st.pending_since_ms = cand, now
            if now - st.pending_since_ms >= HYSTERESIS_S * 1000:
                self._switch(st, cand, now)
            return
        st.pending = st.pending_since_ms = None                  # candidato de menor prioridade
        if cur == "BACKGROUND":                                  # volta do usuário: imediata (05 §2)
            self._switch(st, cand, now)
            return
        window = EXIT_WINDOW_S.get(cur, 0)
        if now - st.exit_since_ms >= window * 1000:
            self._switch(st, cand, now)
