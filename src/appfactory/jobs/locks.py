"""Locks por projeto (04 §3, D-0036). `writes` só aceita arquivo explícito ou prefixo `dir/**`.
Aquisição tudo-ou-nada dentro de uma transação — sem deadlock."""
from __future__ import annotations

import posixpath
import sqlite3

from appfactory.jobs.errors import JobManagerError


class LockConflict(JobManagerError):
    pass


def normalize_spec(spec: str) -> str:
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("path_spec vazio")
    s = spec.strip().replace("\\", "/")
    is_dir = s.endswith("/**")
    base = s[:-3] if is_dir else s
    if any(ch in base for ch in "*?[]"):
        raise ValueError(f"curinga não permitido em writes: {spec!r} (use arquivo explícito ou dir/**)")
    if base.startswith("/") or (len(base) > 1 and base[1] == ":"):
        raise ValueError(f"caminho absoluto não permitido: {spec!r}")
    norm = posixpath.normpath(base)
    if norm in (".", "") or norm == ".." or norm.startswith("../"):
        raise ValueError(f"caminho fora do projeto: {spec!r}")
    norm = norm.lower()  # Windows: sem diferenciar maiúsculas de minúsculas
    return norm + "/**" if is_dir else norm


def overlaps(a: str, b: str) -> bool:
    a_dir, b_dir = a.endswith("/**"), b.endswith("/**")
    a_base, b_base = (a[:-3] if a_dir else a), (b[:-3] if b_dir else b)
    if not a_dir and not b_dir:
        return a_base == b_base
    if a_dir and not b_dir:
        return b_base == a_base or b_base.startswith(a_base + "/")
    if b_dir and not a_dir:
        return a_base == b_base or a_base.startswith(b_base + "/")
    return a_base == b_base or a_base.startswith(b_base + "/") or b_base.startswith(a_base + "/")


def acquire_all(conn: sqlite3.Connection, ts: str, project: str, owner_id: str, specs: list[str]) -> list[str]:
    """Dentro de write_tx."""
    wanted = [normalize_spec(s) for s in specs]
    held = conn.execute("SELECT path_spec, owner_id FROM locks WHERE project = ? AND owner_id != ?",
                        (project, owner_id)).fetchall()
    for w in wanted:
        for row in held:
            if overlaps(w, row["path_spec"]):
                raise LockConflict(f"{w} conflita com {row['path_spec']} (dono {row['owner_id']})")
    for w in wanted:
        conn.execute("INSERT OR IGNORE INTO locks (project, path_spec, owner_id, acquired_at) VALUES (?, ?, ?, ?)",
                     (project, w, owner_id, ts))
    return wanted


def release_owner(conn: sqlite3.Connection, owner_prefix: str) -> int:
    cur = conn.execute("DELETE FROM locks WHERE owner_id = ? OR owner_id LIKE ?", (owner_prefix, owner_prefix + "-%"))
    return cur.rowcount
