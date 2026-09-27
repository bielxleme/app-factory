"""Contrato de sandbox e seleção S1h × S2 (08 §4; 12 §6; D-0026, D-0054).

Na Fase 2.2 as implementações reais (S1h e S2) FALHAM FECHADAS: nenhum código não confiável executa.
A seleção nunca rebaixa de S2 para S1h; sem o sandbox exigido a task fica WAITING(resources) ou BLOCKED.

Prazos do STOP (D-0054): T0 = instante persistido no SQLite; `terminate` em ≤ T0 + 30 s e encerramento
total em ≤ T0 + 40 s, cobrados pelo código confiável supervisor; sondagem do STOP a cada ≤ 1 s; o prazo
efetivo é o menor entre o calculado a partir do T0 e o calculado a partir da detecção (tempo ativo).
Limitação até a 2.4 (KI-0019): sem Job Object, um passo confiável que rode no próprio processo e ignore
`should_stop` não pode ser morto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Protocol

GIB = 1024 ** 3

STOP_TERMINATE_S = 30      # D-0054 / 01 §0
STOP_KILL_S = 40           # D-0054 / 09 I6
STOP_POLL_MAX_S = 1.0      # D-0054

S2_TRIGGERS = frozenset({"network_isolation_required", "needs_network", "unknown_origin", "server",
                         "release_build", "untrusted_high"})

# Tetos do RESOURCE_POLICY.md (guardrail I4): só um humano pode aumentar.
CEILINGS = {
    "FOREGROUND": {"memory_bytes": int(1.5 * GIB), "cpu_rate_pct": 50, "max_processes": 32},
    "BACKGROUND": {"memory_bytes": 3 * GIB, "cpu_rate_pct": 80, "max_processes": 32},
}
MODE_ALIASES = {"FOREGROUND": "FOREGROUND", "BACKGROUND": "BACKGROUND", "BATTERY": "FOREGROUND",
                "CONTENTION": "FOREGROUND", "CRITICAL": "FOREGROUND"}


class SandboxUnavailable(RuntimeError):
    """O sandbox exigido não existe/não foi provado nesta máquina. Nunca rebaixar (08 §4.4)."""


@dataclass(frozen=True)
class Limits:
    memory_bytes: int
    cpu_rate_pct: int
    max_processes: int
    priority: str
    timeout_s: int


def limits_for(mode: str, timeout_s: int, battery: bool = False) -> Limits:
    base = CEILINGS[MODE_ALIASES.get(mode, "FOREGROUND")]
    lim = Limits(base["memory_bytes"], base["cpu_rate_pct"], base["max_processes"],
                 "IDLE" if battery or mode == "BATTERY" else "BELOW_NORMAL", int(timeout_s))
    validate_limits(lim, mode)
    return lim


def validate_limits(lim: Limits, mode: str) -> None:
    """I4: nenhum limite acima do teto do RESOURCE_POLICY.md; recusa em vez de truncar."""
    ceil = CEILINGS[MODE_ALIASES.get(mode, "FOREGROUND")]
    if lim.memory_bytes <= 0 or lim.memory_bytes > ceil["memory_bytes"]:
        raise ValueError(f"memória {lim.memory_bytes} acima do teto {ceil['memory_bytes']} ({mode})")
    if not 0 < lim.cpu_rate_pct <= ceil["cpu_rate_pct"]:
        raise ValueError(f"CPU {lim.cpu_rate_pct}% acima do teto {ceil['cpu_rate_pct']}% ({mode})")
    if not 0 < lim.max_processes <= ceil["max_processes"]:
        raise ValueError(f"processos {lim.max_processes} acima do teto {ceil['max_processes']}")
    if lim.priority not in ("BELOW_NORMAL", "IDLE"):
        raise ValueError(f"prioridade não permitida: {lim.priority}")
    if lim.timeout_s <= 0:
        raise ValueError("timeout obrigatório")


@dataclass(frozen=True)
class StopSignal:
    """Pedido de parada com prazos em TEMPO ATIVO (15 §4), ancorados no T0 persistido (D-0054)."""
    reason: Literal["job_stop", "factory_stop", "cancel", "lease", "timeout"]
    t0_iso: str | None
    detected_active_ms: int
    terminate_at_ms: int
    kill_at_ms: int

    @property
    def outcome(self) -> str:
        return {"job_stop": "killed_stop", "factory_stop": "killed_factory_stop"}.get(self.reason, "killed_lease")


def deadlines(detected_active_ms: int, elapsed_since_t0_s: float | None) -> tuple[int, int]:
    """Prazo efetivo = menor entre (T0 + prazo) e (detecção + prazo). Nunca maior por causa da latência."""
    elapsed = max(0.0, float(elapsed_since_t0_s)) if elapsed_since_t0_s is not None else 0.0
    term = detected_active_ms + int(max(0.0, STOP_TERMINATE_S - elapsed) * 1000)
    kill = detected_active_ms + int(max(0.0, STOP_KILL_S - elapsed) * 1000)
    return min(term, detected_active_ms + STOP_TERMINATE_S * 1000), min(kill, detected_active_ms + STOP_KILL_S * 1000)


@dataclass
class RunResult:
    outcome: Literal["ok", "failed", "timeout", "killed_stop", "killed_factory_stop", "killed_lease",
                     "limit_memory", "limit_processes", "error", "unavailable"]
    exit_code: int | None
    duration_ms: int
    sandbox: str
    limits: Limits | None = None
    stdout_ref: str | None = None
    stderr_ref: str | None = None
    truncated: bool = False
    detail: str | None = None
    terminate_at_ms: int | None = None
    terminated_at_ms: int | None = None
    killed_at_ms: int | None = None
    stdout: str = field(default="", repr=False)   # transitório: redigido/gravado pelo Toolbox e descartado
    stderr: str = field(default="", repr=False)

    def to_record(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k not in ("stdout", "stderr", "limits")}
        d["limits"] = self.limits.__dict__ if self.limits else None
        return d


class Sandbox(Protocol):
    kind: str

    def available(self) -> tuple[bool, str]: ...

    def run(self, argv: list[str], cwd: Path, env: dict[str, str], limits: Limits,
            cancel: Callable[[], StopSignal | None]) -> RunResult: ...


@dataclass(frozen=True)
class SandboxChoice:
    kind: Literal["S1h", "S2"] | None
    hold: Literal["WAITING", "BLOCKED"] | None
    reason: str


def select_sandbox(decision, flags: frozenset[str], s1h: Sandbox, s2: Sandbox, s2_admitted: bool) -> SandboxChoice:
    """Escolhe o sandbox exigido (08 §4.4). S2 exigido nunca cai para S1h. Indisponível => hold."""
    if not getattr(decision, "allowed", False):
        return SandboxChoice(None, "BLOCKED", f"policy:{getattr(decision, 'rule', 'denied')}")
    if decision.sandbox not in ("S1h", "S2"):
        return SandboxChoice(None, "BLOCKED", "s0_not_sandbox: S0 é só para ferramentas confiáveis")
    required = "S2" if decision.sandbox == "S2" or (frozenset(flags) & S2_TRIGGERS) else "S1h"
    if required == "S2":
        ok, why = s2.available()
        if not ok:
            return SandboxChoice(None, "BLOCKED", f"sandbox_unavailable:S2 ({why})")
        if not s2_admitted:
            return SandboxChoice(None, "WAITING", "resources: admissão do S2 negada (RAM ≥ reserva + 3 GB)")
        return SandboxChoice("S2", None, "S2 exigido")
    ok, why = s1h.available()
    if not ok:
        # P-09 (não decidida): sem escalonamento automático para S2; bloqueia (falha fechada).
        return SandboxChoice(None, "BLOCKED", f"sandbox_unavailable:S1h ({why})")
    return SandboxChoice("S1h", None, "S1h")


def production_sandboxes() -> dict:
    """Únicos sandboxes registrados em produção. Ambos falham fechados na Fase 2.2."""
    from appfactory.security.sandbox.docker import DockerSandbox
    from appfactory.security.sandbox.s1h_runner_user import S1hSandbox

    return {"S1h": S1hSandbox(), "S2": DockerSandbox()}
