"""Espelho JSONL por job (operacional, NÃO é fonte da verdade — 07 §1.2). Falhas aqui nunca afetam o SQLite."""
from __future__ import annotations

import json
import os
from pathlib import Path

from appfactory.logs.redaction import redact


def append_jsonl(path: Path, record: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = redact(json.dumps(record, ensure_ascii=False, sort_keys=True))
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return True
    except OSError:
        return False


def write_json_atomic(path: Path, data: dict) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(redact(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return True
    except OSError:
        return False
