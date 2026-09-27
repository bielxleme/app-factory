"""Execução de código NÃO CONFIÁVEL pelo contrato de sandbox (08 §0, §4, §7; D-0050, D-0054).

Pipeline de `exec_untrusted`:
  STOP ativo? -> CommandPolicy -> seleção S1h/S2 (nunca rebaixa) -> journal_intent -> sandbox.run(cancel=StopMonitor)
  -> saídas redigidas/truncadas -> journal_result -> log do job / auditoria.
Negação: violação (1ª negada + registrada; reincidência => BLOCKED(policy_violation)); R2 sem pré-autorização
ou R3 => BLOCKED(approval); sandbox indisponível => BLOCKED/WAITING. Na Fase 2.2 os sandboxes de produção
falham fechados, portanto NENHUM código não confiável é executado em produção.

STOP (D-0054): `StopMonitor` consulta o SQLite a cada chamada (o sandbox chama a cada ≤ 1 s) e devolve um
StopSignal com prazos ancorados no T0 persistido; o sandbox (código confiável) cobra `terminate` em
≤ T0 + 30 s e o encerramento total em ≤ T0 + 40 s. Limitação até a 2.4 (KI-0019): sem Job Object."""
from __future__ import annotations

import datetime
import time
from pathlib import Path

from appfactory.jobs import states as S
from appfactory.jobs.errors import LeaseLost
from appfactory.jobs.handlers import StepHeld, StepInterrupted
from appfactory.logs import audit
from appfactory.logs.jsonlog import append_jsonl
from appfactory.logs.redaction import redact
from appfactory.security.command_policy import CommandPolicyConfig, CommandRequest, clean_env, evaluate
from appfactory.security.paths import PathScope
from appfactory.security.sandbox import (RunResult, SandboxUnavailable, StopSignal, deadlines, limits_for,
                                         production_sandboxes, select_sandbox)
from appfactory.toolbox import AccessDenied, report_violation

MAX_OUTPUT_BYTES = 1024 * 1024
_KILLED = ("killed_stop", "killed_factory_stop", "killed_lease")


def _epoch(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return datetime.datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return None


class StopMonitor:
    """Chamado pelo sandbox a cada ≤ 1 s. Lê o estado persistido (fonte da verdade) e devolve o StopSignal
    mais urgente, com prazos = min(T0 + prazo, detecção + prazo) em tempo ativo (D-0054)."""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self.m = ctx.manager
        self.signal: StopSignal | None = None
        self.calls = 0

    def _make(self, reason: str, t0_iso: str | None) -> StopSignal:
        now_active, now_epoch = self.m.clock.active_ms(), self.m.clock.now_epoch()
        t0 = _epoch(t0_iso)
        term, kill = deadlines(now_active, (now_epoch - t0) if t0 is not None else None)
        return StopSignal(reason, t0_iso, now_active, term, kill)

    def __call__(self) -> StopSignal | None:
        self.calls += 1
        if self.signal is not None:
            return self.signal
        found: list[StopSignal] = []
        try:
            job = self.m.get_job(self.ctx.job_id)
            if job["state"] == S.CANCELLED:
                found.append(self._make("cancel", job.get("cancelled_at")))
            elif job["current_attempt_id"] != self.ctx.attempt_id:
                found.append(self._make("lease", None))
            elif job["state"] == S.STOPPING:
                found.append(self._make("job_stop", job.get("stop_requested_at")))
            fs = self.m.factory_stop_state()   # também aciona o STOP pelo arquivo .appfactory/STOP
            if fs.get("active"):
                found.append(self._make("factory_stop", fs.get("set_at")))
        except Exception:  # noqa: BLE001 - banco ocupado: usa os sinais em memória do executor
            if self.ctx.should_stop():
                found.append(self._make("lease", None))
        if not found and self.ctx.should_stop():
            # sinal em memória sem confirmação no banco (ex.: posse perdida detectada pelo heartbeat)
            found.append(self._make("lease", None))
        if found:
            self.signal = min(found, key=lambda s: (s.terminate_at_ms, s.kill_at_ms))
        return self.signal


def _write_output(path: Path, text: str) -> tuple[str, bool]:
    data = redact(text or "").encode("utf-8", "replace")
    truncated = len(data) > MAX_OUTPUT_BYTES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data[:MAX_OUTPUT_BYTES])
    return str(path), truncated


def _audit(m, record: dict) -> None:
    try:
        audit.append(audit.audit_path(m.paths), record)
    except Exception:  # noqa: BLE001 - o registro principal está no SQLite
        pass


def exec_untrusted(ctx, req: CommandRequest, *, scope: PathScope, sandboxes: dict | None = None,
                   policy: CommandPolicyConfig | None = None, s2_admitted: bool = False,
                   mode: str = "FOREGROUND") -> RunResult:
    m = ctx.manager
    if m is None or not ctx.attempt_id or not ctx.job_id or ctx.step_index is None:
        raise ValueError("exec_untrusted exige StepContext completo (manager, job_id, attempt_id, step_index)")
    # 1) STOP antes de qualquer execução
    m.check_stop_file()
    if m.factory_stop_state().get("active"):
        raise StepInterrupted("factory_stop", "STOP da fábrica ativo: nada é executado")
    if m.get_job(ctx.job_id)["state"] == S.STOPPING:
        raise StepInterrupted("job_stop", "STOP do job pedido: nada é executado")
    # 2) política
    policy = policy or CommandPolicyConfig.load(scope.factory_root)
    decision = evaluate(req, scope, policy)
    base = {"job_id": ctx.job_id, "attempt_id": ctx.attempt_id, "argv0": str(req.argv[0]) if req.argv else None,
            "risk": decision.risk, "rule": decision.rule}
    if not decision.allowed:
        if decision.rule == "approval_required" or decision.needs_human:
            _audit(m, {"type": "command.denied", **base, "reason": decision.reason})
            m.hold_attempt(ctx.attempt_id, S.BLOCKED, f"approval: {decision.rule} ({decision.risk})")
            raise StepHeld(f"approval: {decision.rule}")
        report_violation(ctx, decision.rule, decision.reason)
        raise AccessDenied(message=f"comando negado ({decision.rule}): {decision.reason}")
    if decision.sandbox == "S0":
        raise AccessDenied(message="S0 (git confiável) não está no Toolbox da Fase 2.2 (git.py: fatia 2.8, D-0050)")
    # 3) sandbox exigido (nunca rebaixa)
    sandboxes = sandboxes or production_sandboxes()
    choice = select_sandbox(decision, req.flags, sandboxes["S1h"], sandboxes["S2"], s2_admitted)
    if choice.hold:
        _audit(m, {"type": "sandbox.unavailable", **base, "reason": choice.reason, "hold": choice.hold})
        m.hold_attempt(ctx.attempt_id, choice.hold, choice.reason)
        raise StepHeld(choice.reason)
    limits = limits_for(mode, req.timeout_s)
    env = clean_env(choice.kind, ctx.tmp_dir)
    # 4) intenção antes do efeito (D-0046)
    try:
        key = m.journal_intent(ctx.attempt_id, ctx.step_index)
    except LeaseLost:
        if m.get_job(ctx.job_id)["state"] == S.STOPPING:
            raise StepInterrupted("job_stop", "STOP do job pedido antes da execução") from None
        raise
    monitor = StopMonitor(ctx)
    started = time.monotonic()
    try:
        result = sandboxes[choice.kind].run(list(req.argv), Path(req.cwd), env, limits, monitor)
    except SandboxUnavailable as exc:
        result = RunResult("unavailable", None, int((time.monotonic() - started) * 1000), choice.kind, limits,
                           detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - falha do próprio sandbox vira resultado registrado
        result = RunResult("error", None, int((time.monotonic() - started) * 1000), choice.kind, limits,
                           detail=f"{type(exc).__name__}: {exc}")
    result.limits = limits
    # 5) saídas redigidas e truncadas, fora do alcance do código executado
    runs = m.paths.jobs_dir / ctx.job_id / "artifacts" / "runs" / ctx.attempt_id
    out_ref, t1 = _write_output(runs / f"{ctx.step_index:04d}.out", result.stdout)
    err_ref, t2 = _write_output(runs / f"{ctx.step_index:04d}.err", result.stderr)
    result.stdout_ref, result.stderr_ref, result.truncated = out_ref, err_ref, t1 or t2
    result.stdout = result.stderr = ""
    if result.detail:
        result.detail = redact(result.detail)[:2000]
    record = {"run": result.to_record(), "decision": decision.to_dict(), "sandbox": choice.kind,
              "stop_signal": monitor.signal.__dict__ if monitor.signal else None}
    m.journal_result(ctx.attempt_id, key, record)       # com fencing: posse perdida => LeaseLost
    append_jsonl(m.paths.job_log(ctx.job_id), {"type": "exec.result", "job_id": ctx.job_id,
                                               "attempt_id": ctx.attempt_id, "step": ctx.step_index, **record})
    if decision.risk in ("R2", "R3") or result.outcome.startswith("limit_") or result.outcome in _KILLED:
        _audit(m, {"type": "sandbox.run", **base, "outcome": result.outcome, "exit_code": result.exit_code})
    if result.outcome == "unavailable":
        m.hold_attempt(ctx.attempt_id, S.BLOCKED, f"sandbox_unavailable:{choice.kind}")
        raise StepHeld(f"sandbox_unavailable:{choice.kind}")
    if result.outcome in _KILLED:
        raise StepInterrupted(result.outcome, monitor.signal.reason if monitor.signal else "")
    return result
