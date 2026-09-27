"""Checkpoints por job (N8/F): anexados (nunca sobrescritos), com checksum, gravados na mesma transação
que atualiza o job. O "último checkpoint válido" é o de maior seq com status 'valid' e checksum íntegro."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Callable

from appfactory.core.ids import checkpoint_id
from appfactory.jobs.store import emit

MAX_STATE_BYTES = 1_000_000


def canonical(state: dict) -> str:
    if not isinstance(state, dict):
        raise TypeError("o estado do checkpoint deve ser um dict JSON")
    text = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(text.encode("utf-8")) > MAX_STATE_BYTES:
        raise ValueError("estado do checkpoint maior que 1 MB")
    return text


def compute_checksum(job_id: str, seq: int, step_index: int, kind: str, state_json: str) -> str:
    raw = f"{job_id}|{seq}|{step_index}|{kind}|{state_json}".encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def row_is_intact(row: sqlite3.Row) -> bool:
    try:
        json.loads(row["state_json"])
    except (TypeError, ValueError):
        return False
    return row["checksum"] == compute_checksum(row["job_id"], row["seq"], row["step_index"], row["kind"],
                                               row["state_json"])


def insert_checkpoint(conn: sqlite3.Connection, ts: str, job_id: str, attempt_id: str | None,
                      step_index: int, step_name: str | None, state: dict, kind: str = "step",
                      before_commit: Callable[[], None] | None = None) -> dict:
    """Deve ser chamado dentro de write_tx. Se qualquer coisa falhar antes do COMMIT, nada é gravado e o
    checkpoint válido anterior continua sendo o último."""
    state_json = canonical(state)
    seq_row = conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM checkpoints WHERE job_id = ?",
                           (job_id,)).fetchone()
    seq = int(seq_row[0])
    ck_id = checkpoint_id(job_id, seq)
    checksum = compute_checksum(job_id, seq, step_index, kind, state_json)
    conn.execute(
        "INSERT INTO checkpoints (id, job_id, seq, attempt_id, kind, step_index, step_name, state_json, "
        "checksum, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'valid', ?)",
        (ck_id, job_id, seq, attempt_id, kind, step_index, step_name, state_json, checksum, ts))
    if before_commit is not None:
        before_commit()  # ponto de injeção de falha nos testes (antes de a transação terminar)
    conn.execute(
        "UPDATE jobs SET current_checkpoint_id = ?, current_step = ?, step_index = ?, updated_at = ? "
        "WHERE id = ?", (ck_id, step_name, step_index, ts, job_id))
    emit(conn, ts, "checkpoint.saved", job_id=job_id, attempt_id=attempt_id, actor="executor",
         payload={"checkpoint_id": ck_id, "seq": seq, "kind": kind, "step_index": step_index,
                  "step_name": step_name})
    return {"id": ck_id, "seq": seq, "kind": kind, "step_index": step_index, "step_name": step_name,
            "state": state, "checksum": checksum, "created_at": ts}


def to_dict(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "job_id": row["job_id"], "seq": row["seq"], "attempt_id": row["attempt_id"],
            "kind": row["kind"], "step_index": row["step_index"], "step_name": row["step_name"],
            "state": json.loads(row["state_json"]), "checksum": row["checksum"], "status": row["status"],
            "created_at": row["created_at"]}


def latest_valid(conn: sqlite3.Connection, job_id: str, *, mark_invalid_ts: str | None = None) -> dict | None:
    """Último checkpoint válido. Com `mark_invalid_ts` (dentro de write_tx), marca como 'invalid' os
    registros corrompidos encontrados no caminho e registra o evento."""
    rows = conn.execute("SELECT * FROM checkpoints WHERE job_id = ? AND status = 'valid' ORDER BY seq DESC",
                        (job_id,)).fetchall()
    for row in rows:
        if row_is_intact(row):
            return to_dict(row)
        if mark_invalid_ts is not None:
            conn.execute("UPDATE checkpoints SET status = 'invalid' WHERE id = ?", (row["id"],))
            emit(conn, mark_invalid_ts, "checkpoint.invalid", job_id=job_id, actor="system",
                 reason="checksum_mismatch", payload={"checkpoint_id": row["id"], "seq": row["seq"]})
    return None


def list_checkpoints(conn: sqlite3.Connection, job_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM checkpoints WHERE job_id = ? ORDER BY seq", (job_id,)).fetchall()
    out = []
    for row in rows:
        d = {k: row[k] for k in row.keys() if k != "state_json"}
        d["intact"] = row_is_intact(row)
        out.append(d)
    return out
