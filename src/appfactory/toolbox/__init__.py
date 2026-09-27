"""Toolbox mínimo da Fase 2.2 (D-0050): somente `fs.py` e `shell.py`. `git.py`, `web.py`, `browser.py`,
`db.py` e `journal.py` ficam para a fatia 2.8. Caminho protegido (08 §5.1)."""
from __future__ import annotations

from appfactory.security.paths import Decision


class AccessDenied(PermissionError):
    """Operação negada pela política (primeira violação: o chamador pode tratar)."""

    def __init__(self, decision: Decision | None = None, message: str | None = None) -> None:
        self.decision = decision
        super().__init__(message or (f"negado ({decision.rule}): {decision.reason}" if decision else "negado"))


def report_violation(ctx, rule: str, detail: str) -> None:
    """08 §3: violação => negar + `security.violation` + auditoria; reincidência no mesmo job =>
    `BLOCKED(policy_violation)` (P-12, recomendação (a)). Lança StepHeld quando retém a tentativa."""
    manager = getattr(ctx, "manager", None)
    attempt_id = getattr(ctx, "attempt_id", None)
    if manager is None or attempt_id is None:
        return
    count = manager.record_violation(attempt_id, rule, detail)
    if count >= 2:
        from appfactory.jobs.handlers import StepHeld

        manager.hold_attempt(attempt_id, "BLOCKED", f"policy_violation: reincidência ({rule})")
        raise StepHeld(f"policy_violation: reincidência ({rule})")
