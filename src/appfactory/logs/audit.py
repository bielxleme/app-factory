"""Trilha de auditoria `audit.jsonl` com cadeia de hashes (08 §10; 09 I1).

Cada linha: {seq, ts, type, ..., prev_hash, hash}; `hash = sha256(json canônico da linha sem "hash")`;
a primeira linha tem `prev_hash = "0" * 64`. Escrita serializada por trava de arquivo entre processos,
com flush + fsync imediatos (01 §19). Segredos são redigidos ANTES do hash. O arquivo fica em
`.appfactory/logs/` (estado operacional, inacessível a agentes e ao `afrunner`).

Limitação conhecida (P-13, pendente): a cadeia sozinha não detecta a remoção das ÚLTIMAS linhas."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

from appfactory.logs.redaction import redact

GENESIS = "0" * 64
_THREAD_LOCK = threading.Lock()
LOCK_TIMEOUT_S = 30.0


def audit_path(paths) -> Path:
    """`.appfactory/logs/audit.jsonl` da fábrica (FactoryPaths)."""
    return Path(paths.af) / "logs" / "audit.jsonl"


def canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(entry: dict) -> str:
    return hashlib.sha256(canonical({k: v for k, v in entry.items() if k != "hash"}).encode("utf-8")).hexdigest()


class _FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, "a+b")
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    self.fh.seek(0)
                    msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.monotonic() > deadline:
                    self.fh.close()
                    raise TimeoutError(f"trava da auditoria ocupada: {self.path}")
                time.sleep(0.01)

    def __exit__(self, *exc):
        try:
            if sys.platform == "win32":
                import msvcrt

                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        finally:
            self.fh.close()


def _last_entry(path: Path) -> dict | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        chunk, pos, buf = 4096, size, b""
        while pos > 0:
            step = min(chunk, pos)
            pos -= step
            fh.seek(pos)
            buf = fh.read(step) + buf
            lines = buf.rstrip(b"\n").split(b"\n")
            if len(lines) > 1 or pos == 0:
                last = lines[-1]
                break
        else:  # pragma: no cover
            return None
    if not buf.endswith(b"\n"):
        raise ValueError("auditoria com última linha incompleta; verifique com `af audit verify`")
    return json.loads(last.decode("utf-8"))


def append(path: str | os.PathLike, record: dict) -> str:
    """Anexa um registro e devolve o hash. `record` precisa de `type`. Redação antes do hash."""
    if not isinstance(record, dict) or not record.get("type"):
        raise ValueError("registro de auditoria precisa de 'type'")
    path = Path(path)
    body = json.loads(redact(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)))
    with _THREAD_LOCK, _FileLock(path.with_name(path.name + ".lock")):
        last = _last_entry(path)
        entry = {k: v for k, v in body.items() if k not in ("seq", "prev_hash", "hash")}
        entry["seq"] = (last["seq"] + 1) if last else 1
        entry.setdefault("ts", datetime.datetime.now().astimezone().isoformat(timespec="milliseconds"))
        entry["prev_hash"] = last["hash"] if last else GENESIS
        entry["hash"] = compute_hash(entry)
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical(entry) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    return entry["hash"]


def verify_chain(path: str | os.PathLike) -> tuple[bool, int | None, str]:
    """(ok, índice da primeira linha inválida, motivo). Arquivo ausente ou vazio = íntegro."""
    path = Path(path)
    if not path.exists():
        return True, None, "auditoria ainda não criada"
    prev, expected_seq = GENESIS, 1
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        lines = data.split(b"\n")
        return False, len(lines) - 1, "última linha incompleta"
    for idx, raw in enumerate(data.split(b"\n")[:-1] if data else []):
        try:
            entry = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return False, idx, "linha não é JSON válido"
        if not isinstance(entry, dict) or "hash" not in entry:
            return False, idx, "linha sem hash"
        if entry.get("seq") != expected_seq:
            return False, idx, f"seq {entry.get('seq')} != {expected_seq} (linha removida ou reordenada)"
        if entry.get("prev_hash") != prev:
            return False, idx, "prev_hash não confere (linha removida, inserida ou reordenada)"
        if compute_hash(entry) != entry["hash"]:
            return False, idx, "hash não confere (conteúdo alterado)"
        prev, expected_seq = entry["hash"], expected_seq + 1
    return True, None, f"{expected_seq - 1} linhas íntegras"
