"""Handler de TESTE `test.exec` (registrado só pelos testes, nunca em produção — D-0047).

Usa o Toolbox mínimo (D-0050) com o FakeSandbox configurado pelo teste em `SANDBOXES`."""
from __future__ import annotations

from pathlib import Path

from appfactory.jobs.errors import StepError
from appfactory.jobs.handlers import HANDLERS
from appfactory.security.command_policy import CommandPolicyConfig, CommandRequest
from appfactory.security.diff_guard import check_diff, enforce_verdict
from appfactory.security.paths import ProtectedPaths, make_scope
from appfactory.toolbox import AccessDenied
from appfactory.toolbox.fs import fs_write
from appfactory.toolbox.shell import exec_untrusted

REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOXES: dict = {}
LAST_RESULTS: list = []


class ExecTestHandler:
    job_type = "test.exec"

    def validate_payload(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or "worktree" not in payload:
            raise ValueError("payload de teste exige 'worktree'")
        return payload

    def total_steps(self, payload: dict) -> int:
        return int(payload.get("steps", 1))

    def step_name(self, index: int) -> str:
        return f"exec-{index + 1}"

    def initial_state(self, payload: dict) -> dict:
        return {"done": 0}

    def has_side_effect(self, payload: dict, index: int) -> bool:
        return False  # o Toolbox registra intenção/resultado da execução

    def run_step(self, payload: dict, state: dict, index: int, ctx) -> dict:
        m = ctx.manager
        scope = make_scope(m.paths.root, ctx.job_id, ctx.attempt_id, payload["worktree"],
                           writes=tuple(payload.get("writes", ())), declared_repo_kind=payload.get("repo_kind"))
        protected = ProtectedPaths.load(REPO_ROOT)
        action = payload.get("action", "exec")
        if action == "exec":
            req = CommandRequest(argv=tuple(payload.get("argv", ["python", "-c", "print(1)"])),
                                 cwd=Path(payload["worktree"]), timeout_s=payload.get("timeout_s", 60),
                                 kind=payload.get("kind", "tests"), flags=frozenset(payload.get("flags", ())))
            sandboxes = SANDBOXES or None
            result = exec_untrusted(ctx, req, scope=scope, sandboxes=sandboxes,
                                    policy=CommandPolicyConfig.load(REPO_ROOT),
                                    s2_admitted=bool(payload.get("s2_admitted", False)))
            LAST_RESULTS.append(result)
            if result.outcome != "ok":
                raise StepError(f"execução terminou com {result.outcome}")
        elif action == "write_outside":
            for _ in range(int(payload.get("times", 2))):
                try:
                    fs_write(scope, protected, payload.get("target", "fora/x.txt"), b"x", ctx=ctx)
                except AccessDenied:
                    pass
        elif action == "diff":
            verdict = check_diff(payload["repo"], payload["base"], payload["head"], protected, m.paths.root)
            enforce_verdict(m, ctx.attempt_id, verdict)
        return {"done": state["done"] + 1}

    def validate(self, payload: dict, state: dict):
        ok = state.get("done") == self.total_steps(payload)
        return ok, {"done": state.get("done")}


def register() -> None:
    HANDLERS[ExecTestHandler.job_type] = ExecTestHandler()


def unregister() -> None:
    HANDLERS.pop(ExecTestHandler.job_type, None)
    SANDBOXES.clear()
    LAST_RESULTS.clear()
