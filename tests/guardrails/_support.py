"""Apoio dos guardrails: manifesto (D-0048) e marcação de cada teste com a verificação que ele cobre.

Uma verificação `pending` é pulada com a fatia e o módulo esperado; **`pending` nunca é aprovação**.
Se o manifesto estiver ausente ou inválido, a importação falha e a suíte inteira falha (falha fechada)."""
from __future__ import annotations

import unittest
from pathlib import Path

from appfactory.security import guardrail_manifest as gm

REPO = Path(__file__).resolve().parents[2]
MANIFEST = gm.load_manifest(REPO)
CHECKS = gm.checks(MANIFEST)

# Tetos do RESOURCE_POLICY.md (guardrail I4) — cópia literal; só um humano pode aumentar.
GIB = 1024 ** 3
RESOURCE_POLICY_CEILINGS = {
    "FOREGROUND": {"memory_bytes": int(1.5 * GIB), "cpu_rate_pct": 50, "max_processes": 32},
    "BACKGROUND": {"memory_bytes": 3 * GIB, "cpu_rate_pct": 80, "max_processes": 32},
}

# Lista literal de 08-seguranca.md §5.1 (revisão 2.2: D-0051, D-0052). O arquivo protegido deve contê-la.
PROTECTED_LITERAL = (
    "config/**", "src/appfactory/security/**", "src/appfactory/toolbox/**", "src/appfactory/core/auth.py",
    "src/appfactory/core/stop.py", "src/appfactory/core/instance.py", "src/appfactory/core/api.py",
    "src/appfactory/jobs/store.py", "src/appfactory/jobs/manager.py", "src/appfactory/jobs/executor.py",
    "src/appfactory/jobs/states.py", "src/appfactory/jobs/handlers.py", "src/appfactory/jobs/state_machine.py",
    "src/appfactory/jobs/jobobjects.py", "src/appfactory/core/paths.py", "src/appfactory/core/clock.py",
    "src/appfactory/core/procinfo.py", "src/appfactory/cli/main.py", "src/appfactory/resources/**",
    "src/appfactory/routing/budget.py", "src/appfactory/routing/provider_router.py",
    "src/appfactory/routing/model_registry.py", "src/appfactory/checkpoints/**", "src/appfactory/logs/**",
    "src/appfactory/jobs/recovery.py", "src/appfactory/jobs/leases.py", "src/appfactory/jobs/locks.py",
    "tests/guardrails/**", "evals/**", "pytest.ini", "**/conftest.py", "**/sitecustomize.py", "**/usercustomize.py",
    "**/*.pth", "AGENTS.md", "DECISIONS.md", "RESOURCE_POLICY.md", "docs/architecture/**", "PROJECT_STATE.md",
    "HANDOFF.md", "TASK_QUEUE.md", "CHANGELOG.md", "KNOWN_ISSUES.md", "TEST_STATUS.md", "COMMAND_LOG.md",
    ".appfactory/job.json", ".appfactory/checkpoints/**", ".git/**", ".gitignore", ".gitattributes",
    "tools/diagnostics/**",
)


def guard(check_id: str):
    """Marca o teste com a verificação do manifesto. `pending` => skip com fatia/módulo (D-0048)."""
    check = CHECKS.get(check_id)

    def deco(fn):
        fn.__guard_check__ = check_id
        if check is not None and check["status"] == "pending":
            wrapped = unittest.skip(f"pending:{check['slice']} ({check['module']}) — D-0048: pending não é "
                                    f"aprovação")(fn)
            wrapped.__guard_check__ = check_id
            return wrapped
        return fn

    return deco
