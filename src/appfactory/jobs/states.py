"""Máquina de estados de jobs (03 §2 + D-0040: STOPPING/STOPPED para o STOP explícito de job)."""
from __future__ import annotations

from appfactory.jobs.errors import InvalidTransition

QUEUED = "QUEUED"
PLANNING = "PLANNING"
RUNNING = "RUNNING"
PAUSED = "PAUSED"
WAITING = "WAITING"
BLOCKED = "BLOCKED"
STOPPING = "STOPPING"
STOPPED = "STOPPED"
FAILED = "FAILED"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"

ALL_STATES = (QUEUED, PLANNING, RUNNING, PAUSED, WAITING, BLOCKED, STOPPING, STOPPED, FAILED, COMPLETED, CANCELLED)
TERMINAL = frozenset({COMPLETED, CANCELLED})
# Estados que ocupam a vaga única do projeto (04 §0, D-0036). STOPPING ainda está executando.
PROJECT_SLOT_STATES = frozenset({PLANNING, RUNNING, STOPPING})

TRANSITIONS: dict[str, frozenset[str]] = {
    QUEUED: frozenset({PLANNING, RUNNING, STOPPED, CANCELLED}),
    PLANNING: frozenset({RUNNING, BLOCKED, WAITING, PAUSED, FAILED, CANCELLED, STOPPING}),
    RUNNING: frozenset({PAUSED, WAITING, BLOCKED, FAILED, COMPLETED, CANCELLED, PLANNING, STOPPING}),
    PAUSED: frozenset({QUEUED, RUNNING, CANCELLED, STOPPED}),
    WAITING: frozenset({QUEUED, RUNNING, PAUSED, BLOCKED, CANCELLED, STOPPED}),
    BLOCKED: frozenset({QUEUED, RUNNING, PLANNING, CANCELLED, STOPPED}),
    STOPPING: frozenset({STOPPED, CANCELLED}),
    STOPPED: frozenset({QUEUED, CANCELLED}),
    FAILED: frozenset({QUEUED}),
    COMPLETED: frozenset(),
    CANCELLED: frozenset(),
}


def check_transition(current: str, target: str) -> None:
    if current not in TRANSITIONS or target not in TRANSITIONS:
        raise InvalidTransition(f"estado desconhecido: {current!r} -> {target!r}")
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(f"transição não permitida: {current} -> {target}")
