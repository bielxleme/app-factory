"""Utilitários de teste (sem dependências externas)."""
from __future__ import annotations

import datetime
import os
import shutil
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from appfactory.core.paths import FactoryPaths
from appfactory.jobs.manager import JobManager, JobManagerConfig


class FakeClock:
    """Relógio controlável: tempo ativo, boot e hora de parede."""

    def __init__(self) -> None:
        self._active = 1_000_000
        self._boot = "boot-A"
        self._epoch = time.time()

    def now_iso(self) -> str:
        return datetime.datetime.fromtimestamp(self._epoch).astimezone().isoformat(timespec="milliseconds")

    def now_epoch(self) -> float:
        return self._epoch

    def active_ms(self) -> int:
        return self._active

    def boot_id(self) -> str:
        return self._boot

    def advance(self, seconds: float) -> None:
        self._active += int(seconds * 1000)
        self._epoch += seconds

    def reboot(self) -> None:
        self._boot = "boot-" + uuid.uuid4().hex[:6]
        self._active = 500


class FakeLiveness:
    """Controla quais PIDs 'estão vivos' nos testes de posse/recuperação."""

    def __init__(self) -> None:
        self.alive: set[int] = set()

    def __call__(self, pid, create_time) -> bool:
        return pid in self.alive


FAST = JobManagerConfig(heartbeat_s=0.05, lease_s=60.0, stale_grace_leases=2, max_attempts=3, max_interrupted=5)


class FactoryTestCase(unittest.TestCase):
    """Cria uma raiz de fábrica temporária isolada por teste."""

    faults = False

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="af-test-"))
        (self.tmp / ".appfactory").mkdir()
        (self.tmp / "AGENTS.md").write_text("teste\n", encoding="utf-8")
        self.paths = FactoryPaths(self.tmp)
        self._old_env = os.environ.get("AF_ALLOW_FAULT_INJECTION")
        if self.faults:
            os.environ["AF_ALLOW_FAULT_INJECTION"] = "1"
        else:
            os.environ.pop("AF_ALLOW_FAULT_INJECTION", None)

    def tearDown(self) -> None:
        if self._old_env is None:
            os.environ.pop("AF_ALLOW_FAULT_INJECTION", None)
        else:
            os.environ["AF_ALLOW_FAULT_INJECTION"] = self._old_env
        shutil.rmtree(self.tmp, ignore_errors=True)

    def manager(self, clock=None, liveness=None, config=None) -> JobManager:
        return JobManager(paths=FactoryPaths(self.tmp), clock=clock, liveness=liveness, config=config or FAST)

    def events(self, m: JobManager, job_id: str) -> list[str]:
        return [e["type"] for e in m.history(job_id)]

    def transitions(self, m: JobManager, job_id: str) -> list[tuple]:
        return [(e["from_state"], e["to_state"]) for e in m.history(job_id) if e["type"] == "job.state_changed"]
