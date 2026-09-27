"""IDs (README da arquitetura): JOB-YYYYMMDD-NNNN, gerados por contador no SQLite dentro da mesma
transação da inserção — sem colisão mesmo com vários processos (BEGIN IMMEDIATE serializa)."""
from __future__ import annotations

import sqlite3


def next_counter(conn: sqlite3.Connection, scope: str) -> int:
    conn.execute("INSERT OR IGNORE INTO id_counters (scope, value) VALUES (?, 0)", (scope,))
    conn.execute("UPDATE id_counters SET value = value + 1 WHERE scope = ?", (scope,))
    return int(conn.execute("SELECT value FROM id_counters WHERE scope = ?", (scope,)).fetchone()[0])


def new_job_id(conn: sqlite3.Connection, yyyymmdd: str) -> str:
    n = next_counter(conn, f"job:{yyyymmdd}")
    return f"JOB-{yyyymmdd}-{n:04d}"


def attempt_id(job_id: str, n: int) -> str:
    return f"{job_id}-A{n:02d}"


def checkpoint_id(job_id: str, seq: int) -> str:
    return f"{job_id}-CK{seq:04d}"
