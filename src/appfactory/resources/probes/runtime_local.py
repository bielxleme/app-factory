"""Runtime local (D-0059): **somente leitura** de `GET http://127.0.0.1:11434/api/ps`.

Nenhuma outra rota, nenhum outro método HTTP, sem proxy, sem redirecionamento. Nada é alterado no Ollama
(D-0034). Na 2.3 todo modelo listado conta como **de terceiros** (sem registro de posse até a 2.5).

Frequência (05 §1; D-0075): a consulta acontece **no máximo a cada 15 s** e, depois da primeira, **em segundo
plano** — uma lentidão ou timeout do Ollama nunca atrasa as amostras de 1 s do `watch`. Entre consultas, cada
amostra usa o último resultado concluído. Falha (ou resultado velho demais) => modelos desconhecidos (`None`, pior
caso) e falha registrada em **toda** amostra até a próxima consulta bem-sucedida (fail-closed)."""
from __future__ import annotations

import json
import threading
import time
import urllib.request

OLLAMA_PS_URL = "http://127.0.0.1:11434/api/ps"
TIMEOUT_S = 2.0
MAX_BYTES = 1_000_000
MIB = 1024 ** 2
QUERY_INTERVAL_S = 15.0                          # 05 §1: /api/ps a cada 15 s
STALE_AFTER_S = 2 * QUERY_INTERVAL_S + TIMEOUT_S  # sem resultado novo por mais que isso => desconhecido


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):   # noqa: D401 - redirecionamento é recusado
        return None


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def parse_ps(body: bytes) -> list[dict]:
    data = json.loads(body.decode("utf-8"))
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        raise ValueError("resposta do /api/ps sem lista 'models'")
    out = []
    for m in models:
        if not isinstance(m, dict):
            continue
        size = m.get("size_vram", 0)
        size = size if isinstance(size, (int, float)) and not isinstance(size, bool) and size >= 0 else 0
        out.append({"name": str(m.get("name") or m.get("model") or "?")[:200], "size_vram_mib": size / MIB})
    return out


def _spawn_thread(fn) -> None:
    threading.Thread(target=fn, name="af-ollama-ps", daemon=True).start()


class OllamaPsProbe:
    name = "runtime_local"

    def __init__(self, fetch=None, *, interval_s: float = QUERY_INTERVAL_S, monotonic=time.monotonic,
                 spawn=_spawn_thread) -> None:
        self.fetch = fetch or self._fetch
        self.interval_s = float(interval_s)
        self.monotonic = monotonic
        self.spawn = spawn
        self._lock = threading.Lock()
        self._last_start: float | None = None
        self._inflight = False
        self._result = None             # (concluído_em, modelos | None, erro | None)

    @staticmethod
    def _fetch() -> bytes:
        req = urllib.request.Request(OLLAMA_PS_URL, method="GET", headers={"Accept": "application/json"})
        with _opener().open(req, timeout=TIMEOUT_S) as resp:
            body = resp.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("resposta do /api/ps grande demais")
        return body

    def _query(self) -> None:
        try:
            models, error = parse_ps(self.fetch()), None
        except Exception as exc:  # noqa: BLE001 - qualquer falha => pior caso
            models, error = None, f"{type(exc).__name__}: {exc}"[:300]
        with self._lock:
            self._result = (self.monotonic(), models, error)
            self._inflight = False

    def collect(self, s) -> None:
        now = self.monotonic()
        with self._lock:
            first = self._last_start is None
            due = first or (now - self._last_start >= self.interval_s and not self._inflight)
            if due:
                self._last_start = now
                self._inflight = True
        if due:
            if first:
                self._query()               # 1ª consulta síncrona (snapshot/compare de uma amostra só)
            else:
                self.spawn(self._query)     # demais: em segundo plano, nunca atrasam a amostra
        with self._lock:
            result = self._result
        if result is None:
            s.ollama_models = None
            s.failures.append({"probe": self.name, "error": "sem resultado do /api/ps ainda"})
            return
        done_at, models, error = result
        age = self.monotonic() - done_at
        s.ollama_age_s = round(age, 1)
        if error is not None:
            s.ollama_models = None
            s.failures.append({"probe": self.name, "error": error})
        elif age > STALE_AFTER_S:
            s.ollama_models = None
            s.failures.append({"probe": self.name, "error": f"resultado do /api/ps com {age:.0f} s (velho demais)"})
        else:
            s.ollama_models = models
