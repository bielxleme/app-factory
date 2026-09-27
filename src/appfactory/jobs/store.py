"""SQLite: fonte da verdade (D-0015, D-0037). WAL + synchronous=FULL; estado e evento na mesma transação (07 §5).

Transições são feitas em transações `BEGIN IMMEDIATE`. Eventos e checkpoints são protegidos por triggers
(append-only / imutáveis), para que nenhum código apague histórico automaticamente.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path
from typing import Iterator

from appfactory.jobs.states import ALL_STATES

SCHEMA_VERSION = 1
_STATES_SQL = ", ".join(f"'{s}'" for s in ALL_STATES)

MIGRATIONS: dict[int, list[str]] = {
    1: [
        "CREATE TABLE id_counters (scope TEXT PRIMARY KEY, value INTEGER NOT NULL)",
        f"""CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            intent TEXT NOT NULL,
            job_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{{}}',
            state TEXT NOT NULL CHECK (state IN ({_STATES_SQL})),
            state_reason TEXT,
            current_step TEXT,
            step_index INTEGER,
            priority INTEGER NOT NULL DEFAULT 1 CHECK (priority BETWEEN 0 AND 3),
            attempt_count INTEGER NOT NULL DEFAULT 0,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            interrupted_attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            current_attempt_id TEXT,
            current_checkpoint_id TEXT,
            resume_from TEXT,
            created_at TEXT NOT NULL,
            queued_at TEXT,
            started_at TEXT,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            failed_at TEXT,
            stopped_at TEXT,
            cancelled_at TEXT,
            stop_requested_at TEXT,
            stop_reason TEXT,
            fail_reason TEXT
        )""",
        # Vaga única por projeto garantida pelo banco (D-0036), não só pelo código.
        "CREATE UNIQUE INDEX jobs_one_active_per_project ON jobs(project) "
        "WHERE state IN ('PLANNING', 'RUNNING', 'STOPPING')",
        "CREATE INDEX jobs_state ON jobs(state, priority, queued_at)",
        """CREATE TABLE attempts (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id),
            n INTEGER NOT NULL,
            executor_id TEXT NOT NULL,
            pid INTEGER,
            process_create_time TEXT,
            boot_id TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            outcome TEXT,
            detail TEXT,
            resume_from_checkpoint TEXT,
            lease_expires_active_ms INTEGER NOT NULL,
            last_heartbeat_active_ms INTEGER NOT NULL,
            last_heartbeat_at TEXT NOT NULL,
            UNIQUE (job_id, n)
        )""",
        "CREATE INDEX attempts_open ON attempts(job_id) WHERE ended_at IS NULL",
        """CREATE TABLE checkpoints (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id),
            seq INTEGER NOT NULL,
            attempt_id TEXT,
            kind TEXT NOT NULL DEFAULT 'step' CHECK (kind IN ('step', 'stop', 'pause')),
            step_index INTEGER NOT NULL,
            step_name TEXT,
            state_json TEXT NOT NULL,
            checksum TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'valid' CHECK (status IN ('valid', 'invalid')),
            created_at TEXT NOT NULL,
            UNIQUE (job_id, seq)
        )""",
        # Checkpoints nunca são apagados nem sobrescritos; só podem ser marcados 'invalid'.
        """CREATE TRIGGER checkpoints_no_delete BEFORE DELETE ON checkpoints
           BEGIN SELECT RAISE(ABORT, 'checkpoints nao podem ser apagados'); END""",
        """CREATE TRIGGER checkpoints_immutable BEFORE UPDATE ON checkpoints
           WHEN NOT (OLD.status = 'valid' AND NEW.status = 'invalid'
                     AND NEW.id = OLD.id AND NEW.job_id = OLD.job_id AND NEW.seq = OLD.seq
                     AND NEW.step_index = OLD.step_index AND NEW.state_json = OLD.state_json
                     AND NEW.checksum = OLD.checksum AND NEW.kind = OLD.kind)
           BEGIN SELECT RAISE(ABORT, 'checkpoints sao imutaveis'); END""",
        """CREATE TABLE events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            type TEXT NOT NULL,
            job_id TEXT,
            attempt_id TEXT,
            actor TEXT NOT NULL,
            from_state TEXT,
            to_state TEXT,
            reason TEXT,
            payload_json TEXT
        )""",
        "CREATE INDEX events_job ON events(job_id, seq)",
        """CREATE TRIGGER events_no_update BEFORE UPDATE ON events
           BEGIN SELECT RAISE(ABORT, 'events sao append-only'); END""",
        """CREATE TRIGGER events_no_delete BEFORE DELETE ON events
           BEGIN SELECT RAISE(ABORT, 'events sao append-only'); END""",
        """CREATE TABLE validations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(id),
            attempt_id TEXT NOT NULL REFERENCES attempts(id),
            checkpoint_id TEXT,
            passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
            report_json TEXT,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE step_journal (
            idempotency_key TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id),
            attempt_id TEXT NOT NULL,
            step_index INTEGER NOT NULL,
            side_effect INTEGER NOT NULL,
            intent_at TEXT NOT NULL,
            result_at TEXT,
            result_json TEXT
        )""",
        """CREATE TABLE factory_stop (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            active INTEGER NOT NULL CHECK (active IN (0, 1)),
            reason TEXT,
            set_at TEXT,
            set_by TEXT,
            released_at TEXT,
            released_by TEXT
        )""",
        "INSERT INTO factory_stop (id, active) VALUES (1, 0)",
        """CREATE TABLE locks (
            project TEXT NOT NULL,
            path_spec TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            PRIMARY KEY (project, path_spec, owner_id)
        )""",
    ],
}

REQUIRED_TABLES = {"schema_meta", "id_counters", "jobs", "attempts", "checkpoints", "events",
                   "validations", "step_journal", "factory_stop", "locks"}
REQUIRED_TRIGGERS = {"checkpoints_no_delete", "checkpoints_immutable", "events_no_update", "events_no_delete"}


class SchemaError(RuntimeError):
    pass


def connect(db_path: Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None, check_same_thread=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    return conn


@contextlib.contextmanager
def write_tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transação de escrita exclusiva (BEGIN IMMEDIATE): serializa escritores concorrentes."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def schema_version(conn: sqlite3.Connection) -> int:
    has_meta = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_meta'").fetchone()
    if not has_meta:
        return 0
    row = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    return int(row[0]) if row else 0


def migrate(conn: sqlite3.Connection) -> int:
    with write_tx(conn):
        conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        current = schema_version(conn)
        if current > SCHEMA_VERSION:
            raise SchemaError(f"banco com schema {current} mais novo que o código ({SCHEMA_VERSION})")
        for version in sorted(MIGRATIONS):
            if version <= current:
                continue
            for stmt in MIGRATIONS[version]:
                conn.execute(stmt)
            conn.execute("INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
                         (str(version),))
            current = version
    return current


def check_database(conn: sqlite3.Connection) -> dict:
    """Integridade + schema (usado por `af db check` e pela recuperação, 07 §3 passo 2)."""
    quick = [r[0] for r in conn.execute("PRAGMA quick_check").fetchall()]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    triggers = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    report = {
        "quick_check": quick,
        "foreign_key_violations": len(fk),
        "schema_version": schema_version(conn),
        "expected_schema_version": SCHEMA_VERSION,
        "missing_tables": sorted(REQUIRED_TABLES - tables),
        "missing_triggers": sorted(REQUIRED_TRIGGERS - triggers),
        "journal_mode": mode,
    }
    report["ok"] = (quick == ["ok"] and not fk and report["schema_version"] == SCHEMA_VERSION
                    and not report["missing_tables"] and not report["missing_triggers"])
    return report


def emit(conn: sqlite3.Connection, ts: str, type_: str, *, job_id: str | None = None,
         attempt_id: str | None = None, actor: str = "system", from_state: str | None = None,
         to_state: str | None = None, reason: str | None = None, payload: dict | None = None) -> dict:
    """Grava um evento (sempre dentro da transação da mudança de estado)."""
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload is not None else None
    cur = conn.execute(
        "INSERT INTO events (ts, type, job_id, attempt_id, actor, from_state, to_state, reason, payload_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, type_, job_id, attempt_id, actor, from_state, to_state, reason, payload_json))
    return {"seq": cur.lastrowid, "ts": ts, "type": type_, "job_id": job_id, "attempt_id": attempt_id,
            "actor": actor, "from_state": from_state, "to_state": to_state, "reason": reason,
            "payload": payload}
