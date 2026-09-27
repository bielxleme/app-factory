"""Handlers de job REGISTRADOS NO CÓDIGO da fábrica (código confiável). Nenhum código vindo de agente,
payload ou usuário é executado (08 §0): o payload é só dado JSON validado.

Fase 2.1 tem um único tipo, `demo.steps`, usado para validar o ciclo de vida do Job Manager.
Injeção de falhas (`_faults`) só é aceita com AF_ALLOW_FAULT_INJECTION=1 (usado pelos testes).

Fase 2.2 (aditivo): o StepContext passa a levar a identidade da tentativa e o manager, para o Toolbox mínimo
(D-0050) registrar resultado/violação com fencing; StepInterrupted/StepHeld sinalizam ao executor que um
passo foi interrompido por STOP/perda de posse ou que a tentativa já foi retida (BLOCKED/WAITING).
Nenhum handler novo é registrado em produção (D-0047)."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable

from appfactory.jobs.errors import FatalStepError, JobManagerError, StepError


def faults_enabled() -> bool:
    return os.environ.get("AF_ALLOW_FAULT_INJECTION") == "1"


class StepInterrupted(JobManagerError):
    """O passo foi interrompido por STOP do job, STOP da fábrica ou perda de posse (D-0054). O resultado
    parcial já foi registrado no journal; o executor decide parar/pausar sem gravar checkpoint do passo."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


class StepHeld(JobManagerError):
    """A tentativa já foi retida (BLOCKED/WAITING) por hold_attempt; o executor só encerra."""


@dataclass
class StepContext:
    attempt_n: int
    tmp_dir: str
    should_stop: Callable[[], bool] = field(default=lambda: False)
    job_id: str | None = None
    attempt_id: str | None = None
    manager: object | None = None
    step_index: int | None = None


class DemoStepsHandler:
    """Soma `numbers` um passo por vez. Validação: total == soma esperada e todos os passos processados."""

    job_type = "demo.steps"
    MAX_NUMBERS = 1000

    def validate_payload(self, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("payload deve ser um objeto JSON")
        allowed = {"numbers", "expected_sum", "step_delay_ms", "side_effect_steps", "_faults"}
        extra = set(payload) - allowed
        if extra:
            raise ValueError(f"campos não permitidos no payload: {sorted(extra)}")
        nums = payload.get("numbers")
        if not isinstance(nums, list) or not nums or len(nums) > self.MAX_NUMBERS:
            raise ValueError("numbers deve ser uma lista com 1 a 1000 inteiros")
        if not all(isinstance(n, int) and not isinstance(n, bool) for n in nums):
            raise ValueError("numbers deve conter apenas inteiros")
        if "expected_sum" in payload and not isinstance(payload["expected_sum"], int):
            raise ValueError("expected_sum deve ser inteiro")
        delay = payload.get("step_delay_ms", 0)
        if not isinstance(delay, int) or not 0 <= delay <= 10_000:
            raise ValueError("step_delay_ms deve estar entre 0 e 10000")
        side = payload.get("side_effect_steps", [])
        if not isinstance(side, list) or not all(isinstance(i, int) for i in side):
            raise ValueError("side_effect_steps deve ser lista de inteiros")
        if "_faults" in payload and not faults_enabled():
            raise ValueError("_faults só é aceito com AF_ALLOW_FAULT_INJECTION=1")
        return payload

    def total_steps(self, payload: dict) -> int:
        return len(payload["numbers"])

    def step_name(self, index: int) -> str:
        return f"somar-item-{index + 1}"

    def initial_state(self, payload: dict) -> dict:
        return {"total": 0, "processed": 0}

    def has_side_effect(self, payload: dict, index: int) -> bool:
        return index in payload.get("side_effect_steps", [])

    def run_step(self, payload: dict, state: dict, index: int, ctx: StepContext) -> dict:
        faults = payload.get("_faults", {}) if faults_enabled() else {}
        delay = payload.get("step_delay_ms", 0)
        deadline = time.monotonic() + delay / 1000
        while time.monotonic() < deadline:
            time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
        if faults.get("crash_at_step") == index and ctx.attempt_n <= faults.get("crash_attempts", 1):
            os._exit(86)  # simula encerramento inesperado do processo
        if faults.get("fatal_at_step") == index:
            raise FatalStepError(f"falha fatal simulada no passo {index}")
        if faults.get("fail_at_step") == index and ctx.attempt_n <= faults.get("fail_attempts", 1):
            raise StepError(f"falha simulada no passo {index} (tentativa {ctx.attempt_n})")
        if state.get("processed") != index:
            raise FatalStepError(f"estado inconsistente: processed={state.get('processed')} passo={index}")
        return {"total": state["total"] + payload["numbers"][index], "processed": index + 1}

    def validate(self, payload: dict, state: dict) -> tuple[bool, dict]:
        expected = sum(payload["numbers"])
        report = {"expected_total": expected, "total": state.get("total"), "processed": state.get("processed"),
                  "steps": len(payload["numbers"])}
        ok = state.get("total") == expected and state.get("processed") == len(payload["numbers"])
        if "expected_sum" in payload:
            report["expected_sum"] = payload["expected_sum"]
            ok = ok and payload["expected_sum"] == state.get("total")
        return ok, report


HANDLERS = {DemoStepsHandler.job_type: DemoStepsHandler()}


def get_handler(job_type: str):
    from appfactory.jobs.errors import UnknownJobType

    try:
        return HANDLERS[job_type]
    except KeyError:
        raise UnknownJobType(f"tipo de job não registrado: {job_type!r}") from None
