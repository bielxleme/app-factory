"""FakeSandbox — dublê do contrato `Sandbox` (12 §6) usado SOMENTE nos testes.

Executa apenas código confiável do próprio teste (não lança processos, não executa código de agente).
Simula: sucesso, falha, erro interno, timeout, limites, queda do processo e execução bloqueada que
reage (ou não) ao cancelamento, cobrando os prazos do StopSignal (D-0054)."""
from __future__ import annotations

import os
import threading
import time

from appfactory.security.sandbox import STOP_POLL_MAX_S, RunResult


class FakeSandbox:
    def __init__(self, kind: str = "S1h", available: bool = True, behavior: str = "ok", exit_code: int = 0,
                 stdout: str = "", stderr: str = "", poll_s: float = 0.05, clock=None, simulate: bool = False,
                 cooperative: bool = True, obey_terminate: bool = True, max_block_s: float = 60.0,
                 crash_code: int = 88) -> None:
        self.kind = kind
        self._available = available
        self.behavior = behavior
        self.exit_code = exit_code
        self.stdout, self.stderr = stdout, stderr
        self.poll_s = poll_s
        self.clock = clock
        self.simulate = simulate
        self.cooperative = cooperative
        self.obey_terminate = obey_terminate
        self.max_block_s = max_block_s
        self.crash_code = crash_code
        self.calls: list[dict] = []
        self.started = threading.Event()
        self.signal = None
        self.poll_gaps_ms: list[int] = []
        self.terminated_at_ms = None
        self.killed_at_ms = None

    def available(self):
        return self._available, "fake"

    def _now(self) -> int:
        return self.clock.active_ms() if self.clock else int(time.monotonic() * 1000)

    def _tick(self, after_signal: bool = False) -> None:
        """Antes do sinal: espera real curta (o teste age em tempo real). Depois do sinal, em modo simulado,
        o relógio falso avança `poll_s` por iteração (prazos de 30/40 s verificados sem esperar)."""
        if after_signal and self.simulate and self.clock is not None:
            self.clock.advance(self.poll_s)
        else:
            time.sleep(min(self.poll_s, 0.02) if self.simulate else self.poll_s)

    def _result(self, outcome, start, code=None, **kw) -> RunResult:
        return RunResult(outcome, code, max(0, self._now() - start), self.kind, stdout=self.stdout,
                         stderr=self.stderr, **kw)

    def run(self, argv, cwd, env, limits, cancel) -> RunResult:
        assert self.poll_s <= STOP_POLL_MAX_S, "o sandbox deve sondar o STOP a cada <= 1 s (D-0054)"
        self.calls.append({"argv": list(argv), "cwd": str(cwd), "env": dict(env), "limits": limits})
        start = self._now()
        self.started.set()
        b = self.behavior
        if b == "ok":
            return self._result("ok", start, self.exit_code)
        if b == "fail":
            return self._result("failed", start, self.exit_code or 1)
        if b == "error":
            raise RuntimeError("falha interna simulada do sandbox")
        if b == "timeout":
            self.terminated_at_ms = self._now()
            return self._result("timeout", start, None, terminated_at_ms=self.terminated_at_ms)
        if b in ("limit_memory", "limit_processes"):
            return self._result(b, start, None)
        if b == "crash":
            os._exit(self.crash_code)  # queda do processo do executor no meio da execução
        # "block": executa até ser cancelado, cobrando os prazos do StopSignal
        last = self._now()
        real_start = time.monotonic()
        while True:
            sig = cancel()
            now = self._now()
            self.poll_gaps_ms.append(now - last)
            last = now
            if sig is not None:
                self.signal = sig
                if self.cooperative:
                    self.terminated_at_ms = now
                    return self._result(sig.outcome, start, None, terminate_at_ms=sig.terminate_at_ms,
                                        terminated_at_ms=now)
                while self._now() < sig.terminate_at_ms:
                    self._tick(after_signal=True)
                self.terminated_at_ms = self._now()
                if self.obey_terminate:
                    return self._result(sig.outcome, start, None, terminate_at_ms=sig.terminate_at_ms,
                                        terminated_at_ms=self.terminated_at_ms)
                while self._now() < sig.kill_at_ms:
                    self._tick(after_signal=True)
                self.killed_at_ms = self._now()
                return self._result(sig.outcome, start, None, terminate_at_ms=sig.terminate_at_ms,
                                    terminated_at_ms=self.terminated_at_ms, killed_at_ms=self.killed_at_ms)
            if time.monotonic() - real_start > self.max_block_s:
                return self._result("timeout", start, None)
            self._tick()
