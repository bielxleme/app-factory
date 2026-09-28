"""Histórico do `watch` (D-0061, D-0063, D-0069, D-0071): eventos `resource.snapshot` na tabela `events` existente.

`admit` lê **somente** este histórico — não coleta amostras nem espera. Histórico suficiente = amostras contíguas
(mesmo `boot_id`, sem lacuna > 5 s em tempo ativo, sem sono, mesma política) cobrindo cada janela exigida até o
instante da consulta, com a amostra mais recente recente (≤ 5 s) e no mínimo 2 amostras (01 §4). Só as métricas
com janela explícita exigem histórico; a ociosidade é instantânea (D-0071)."""
from __future__ import annotations

import json
import math

from appfactory.resources.policy import MAX_SAMPLE_GAP_S, SLEEP_TOLERANCE_MS

SNAPSHOT_EVENT = "resource.snapshot"
BATCH = 200
MAX_ROWS = 5000


def load_recent(conn, now_active_ms: int, oldest_needed_ms: int) -> list[dict]:
    """Payloads mais recentes primeiro, lidos em lotes até cobrir `oldest_needed_ms` (sem índice novo)."""
    out: list[dict] = []
    before = None
    while len(out) < MAX_ROWS:
        if before is None:
            rows = conn.execute("SELECT seq, payload_json FROM events WHERE job_id IS NULL AND type = ? "
                                "ORDER BY seq DESC LIMIT ?", (SNAPSHOT_EVENT, BATCH)).fetchall()
        else:
            rows = conn.execute("SELECT seq, payload_json FROM events WHERE job_id IS NULL AND type = ? AND seq < ? "
                                "ORDER BY seq DESC LIMIT ?", (SNAPSHOT_EVENT, before, BATCH)).fetchall()
        if not rows:
            break
        for r in rows:
            try:
                p = json.loads(r["payload_json"] or "{}")
            except ValueError:
                p = {}
            out.append(p)
        before = rows[-1]["seq"]
        last = out[-1].get("active_ms")
        if not isinstance(last, int) or last <= oldest_needed_ms or last > now_active_ms:
            break
    return out


class History:
    def __init__(self, payloads: list[dict], *, now_active_ms: int, now_suspend_ms: int, boot_id: str,
                 policy_sha256: str) -> None:
        self.now = int(now_active_ms)
        self.contiguous: list[dict] = []          # mais recente primeiro
        self.problem: str | None = None
        if not payloads:
            self.problem = "no_history"
            return
        newest = payloads[0]
        if newest.get("boot_id") != boot_id or boot_id == "unknown":
            self.problem = "boot_changed"
            return
        if newest.get("policy_sha256") != policy_sha256:
            self.problem = "policy_changed"
            return
        age = self.now - int(newest.get("active_ms", -10**12))
        slept = (int(now_suspend_ms) - int(newest.get("suspend_ms", 0))) - age
        if age < 0 or age > MAX_SAMPLE_GAP_S * 1000:
            self.problem = "stale"
            return
        if slept > SLEEP_TOLERANCE_MS:
            self.problem = "slept"
            return
        self.contiguous.append(newest)
        for p in payloads[1:]:
            prev = self.contiguous[-1]
            gap = int(prev["active_ms"]) - int(p.get("active_ms", -10**12))
            slept = (int(prev.get("suspend_ms", 0)) - int(p.get("suspend_ms", 0))) - gap
            if (p.get("boot_id") != boot_id or p.get("policy_sha256") != policy_sha256 or gap < 0
                    or gap > MAX_SAMPLE_GAP_S * 1000 or slept > SLEEP_TOLERANCE_MS):
                break
            self.contiguous.append(p)

    @property
    def latest(self) -> dict | None:
        return self.contiguous[0] if self.contiguous else None

    def covered_s(self) -> float:
        if not self.contiguous:
            return 0.0
        return (self.now - int(self.contiguous[-1]["active_ms"])) / 1000.0

    def missing(self, windows: dict) -> dict:
        """{nome: segundos que faltam}; vazio = suficiente."""
        if self.problem:
            return {self.problem: float(max(windows.values(), default=0))}
        out = {}
        if len(self.contiguous) < 2:
            out["samples"] = 1.0
        cov = self.covered_s()
        for name, w in windows.items():
            if cov < w:
                out[name] = round(w - cov, 1)
        return out

    def window(self, seconds: float) -> list[dict]:
        start = self.now - seconds * 1000
        return [p for p in self.contiguous if int(p["active_ms"]) >= start]

    @staticmethod
    def _values(payloads, key, none_as):
        return [none_as if p.get("sample", {}).get(key) is None else float(p["sample"][key]) for p in payloads]

    def avg(self, key: str, seconds: float, none_as: float) -> float:
        vals = self._values(self.window(seconds), key, none_as)
        return sum(vals) / len(vals) if vals else none_as

    def min(self, key: str, seconds: float, none_as: float) -> float:
        vals = self._values(self.window(seconds), key, none_as)
        return min(vals) if vals else none_as

    def max(self, key: str, seconds: float, none_as: float = math.inf) -> float:
        vals = self._values(self.window(seconds), key, none_as)
        return max(vals) if vals else none_as
