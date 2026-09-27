"""Caminhos da fábrica (07 §1). Estado operacional sempre sob .appfactory/ (ignorado pelo Git)."""
from __future__ import annotations

import os
import re
from pathlib import Path

_SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")


class FactoryPaths:
    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root).resolve()
        self.af = self.root / ".appfactory"
        self.state_dir = self.af / "state"
        self.db = self.state_dir / "factory.db"
        self.runtime = self.af / "runtime"
        self.runtime_job_json = self.runtime / "job.json"
        self.logs_jobs = self.af / "logs" / "jobs"
        self.jobs_dir = self.af / "jobs"
        self.stop_file = self.af / "STOP"

    def job_log(self, job_id: str) -> Path:
        return self.logs_jobs / f"{safe_name(job_id)}.jsonl"

    def job_tmp(self, job_id: str, attempt_id: str) -> Path:
        return self.jobs_dir / safe_name(job_id) / "tmp" / safe_name(attempt_id)

    def is_factory_tmp(self, path: Path) -> bool:
        """True somente para diretórios temporários de tentativa criados pela própria fábrica."""
        p = Path(path).resolve()
        base = self.jobs_dir.resolve()
        try:
            rel = p.relative_to(base)
        except ValueError:
            return False
        parts = rel.parts
        return len(parts) == 3 and parts[1] == "tmp"


def safe_name(value: str) -> str:
    if not _SAFE.match(value):
        raise ValueError(f"identificador inválido para nome de arquivo: {value!r}")
    return value


def discover_root(start: str | os.PathLike | None = None) -> Path:
    """Raiz da fábrica: AF_ROOT, ou o primeiro diretório acima com AGENTS.md e .appfactory/."""
    env = os.environ.get("AF_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(start or os.getcwd()).resolve()
    for d in (here, *here.parents):
        if (d / "AGENTS.md").is_file() and (d / ".appfactory").is_dir():
            return d
    raise FileNotFoundError("raiz da App Factory não encontrada (defina AF_ROOT ou use --root)")
