"""STOP da fábrica (08 §9, D-0028): persistido no SQLite + espelhado em memória pelo manager.
Qualquer um pode acionar; só `af resume-factory` (com confirmação interativa) libera. Apagar o arquivo
`.appfactory/STOP` nunca libera uma parada registrada."""
from __future__ import annotations

import sqlite3

from appfactory.jobs.store import emit


def get_state(conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM factory_stop WHERE id = 1").fetchone()
    return {k: row[k] for k in row.keys()} if row else {"active": 0}


def set_stop(conn: sqlite3.Connection, ts: str, reason: str, set_by: str) -> bool:
    """Dentro de write_tx. Retorna True se acionou agora (False se já estava ativo)."""
    if get_state(conn).get("active"):
        return False
    conn.execute("UPDATE factory_stop SET active = 1, reason = ?, set_at = ?, set_by = ?, "
                 "released_at = NULL, released_by = NULL WHERE id = 1", (reason, ts, set_by))
    emit(conn, ts, "system.stop_set", actor=set_by, reason=reason)
    return True


def release(conn: sqlite3.Connection, ts: str, released_by: str) -> bool:
    if not get_state(conn).get("active"):
        return False
    conn.execute("UPDATE factory_stop SET active = 0, released_at = ?, released_by = ? WHERE id = 1",
                 (ts, released_by))
    emit(conn, ts, "system.stop_released", actor=released_by)
    return True
