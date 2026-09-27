"""Executor de jobs (fundação 2.1). Executa SOMENTE handlers registrados no código (handlers.py).

Ciclo: claim -> retomar do último checkpoint válido -> para cada passo: heartbeat (observa STOP de job e
STOP da fábrica) -> [journal intent] -> passo -> [journal result] -> checkpoint -> validação -> COMPLETED.
STOP de job: termina o passo atual, grava checkpoint 'stop', limpa temporários, STOPPING -> STOPPED.

Fase 2.2 (aditivo, D-0054): `should_stop` também observa o STOP da fábrica; um passo interrompido
(StepInterrupted) nunca ganha checkpoint de passo — o job para/pausa a partir do último checkpoint válido.
Passo retido (StepHeld) encerra sem novas escritas (a tentativa já foi fechada por hold_attempt).
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import uuid
from dataclasses import dataclass

from appfactory.core.procinfo import current_identity
from appfactory.jobs.errors import FatalStepError, LeaseLost, UnknownJobType
from appfactory.jobs.handlers import StepContext, StepHeld, StepInterrupted, faults_enabled, get_handler


@dataclass
class RunResult:
    job_id: str | None
    attempt_id: str | None
    final_state: str | None
    detail: str = ""


class Executor:
    def __init__(self, manager, executor_id: str | None = None, heartbeat_s: float | None = None) -> None:
        self.m = manager
        self.executor_id = executor_id or f"exec-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.heartbeat_s = heartbeat_s if heartbeat_s is not None else manager.config.heartbeat_s
        self._stop_seen = threading.Event()
        self._factory_stop_seen = threading.Event()
        self._lost = threading.Event()
        self._hb_stop = threading.Event()

    # heartbeat em segundo plano para passos longos
    def _hb_loop(self, attempt_id: str) -> None:
        while not self._hb_stop.wait(self.heartbeat_s):
            try:
                d = self.m.heartbeat(attempt_id)
            except LeaseLost:
                self._lost.set()
                return
            except Exception:  # noqa: BLE001 - banco ocupado etc.: tenta de novo no próximo ciclo
                continue
            if d["stop"]:
                self._stop_seen.set()
            if d["factory_stop"]:
                self._factory_stop_seen.set()

    def run(self, job_id: str | None = None) -> RunResult:
        pid, ctime = current_identity()
        claim = self.m.claim(self.executor_id, job_id=job_id, pid=pid, process_create_time=ctime)
        attempt_id, job = claim["attempt_id"], claim["job"]
        point = claim["resume_point"]
        tmp_dir = self.m.paths.job_tmp(job["id"], attempt_id)
        hb = threading.Thread(target=self._hb_loop, args=(attempt_id,), daemon=True)
        try:
            try:
                handler = get_handler(job["job_type"])
            except UnknownJobType as exc:
                self.m.fail_attempt(attempt_id, str(exc), fatal=True)
                return self._result(job["id"], attempt_id, str(exc))
            payload = json.loads(job["payload_json"])
            state = point["state"] if point else handler.initial_state(payload)
            last_done = point["step_index"] if point else -1
            tmp_dir.mkdir(parents=True, exist_ok=True)
            hb.start()
            ctx = StepContext(attempt_n=claim["attempt_n"], tmp_dir=str(tmp_dir),
                              should_stop=lambda: (self._stop_seen.is_set() or self._lost.is_set()
                                                   or self._factory_stop_seen.is_set()),
                              job_id=job["id"], attempt_id=attempt_id, manager=self.m)
            faults = payload.get("_faults", {}) if faults_enabled() else {}
            total = handler.total_steps(payload)
            index = last_done + 1
            while index < total:
                d = self.m.heartbeat(attempt_id)
                if d["stop"] or self._stop_seen.is_set():
                    return self._graceful_stop(attempt_id, job["id"], state, last_done, faults)
                if d["factory_stop"] or self._factory_stop_seen.is_set():
                    return self._pause_factory(attempt_id, job["id"], state, last_done)
                key = self.m.journal_intent(attempt_id, index) if handler.has_side_effect(payload, index) else None
                ctx.step_index = index
                try:
                    state = handler.run_step(payload, state, index, ctx)
                except StepHeld as exc:
                    return self._result(job["id"], attempt_id, f"tentativa retida: {exc}")
                except StepInterrupted as exc:
                    d = self.m.heartbeat(attempt_id)   # LeaseLost aqui => posse perdida (tratado abaixo)
                    if d["stop"] or self._stop_seen.is_set():
                        return self._graceful_stop(attempt_id, job["id"], state, last_done, faults)
                    if d["factory_stop"] or self._factory_stop_seen.is_set():
                        return self._pause_factory(attempt_id, job["id"], state, last_done)
                    self.m.fail_attempt(attempt_id, f"passo interrompido: {exc}")
                    return self._result(job["id"], attempt_id, str(exc))
                except FatalStepError as exc:
                    self.m.fail_attempt(attempt_id, str(exc), fatal=True)
                    return self._result(job["id"], attempt_id, str(exc))
                except LeaseLost:
                    raise  # posse perdida dentro do passo (ex.: cancelamento durante a execução): não escreve mais
                except Exception as exc:  # noqa: BLE001 - falha de passo conta como tentativa falha
                    self.m.fail_attempt(attempt_id, f"{type(exc).__name__}: {exc}")
                    return self._result(job["id"], attempt_id, str(exc))
                if key:
                    self.m.journal_result(attempt_id, key, {"ok": True})
                hook = None
                if faults.get("crash_in_checkpoint_at") == index and claim["attempt_n"] <= faults.get("crash_attempts", 1):
                    hook = lambda: os._exit(87)  # noqa: E731 - simula queda no meio da gravação
                try:
                    self.m.save_checkpoint(attempt_id, index, handler.step_name(index), state, before_commit=hook)
                except LeaseLost:
                    raise
                except Exception as exc:  # noqa: BLE001 - checkpoint não gravado: o anterior continua válido
                    self.m.fail_attempt(attempt_id, f"falha ao gravar checkpoint do passo {index}: {exc}")
                    return self._result(job["id"], attempt_id, str(exc))
                last_done = index
                index += 1
            d = self.m.heartbeat(attempt_id)
            if d["stop"] or self._stop_seen.is_set():
                return self._graceful_stop(attempt_id, job["id"], state, last_done, faults)
            passed, report = handler.validate(payload, state)
            self.m.record_validation(attempt_id, passed, report)
            if passed:
                self.m.complete(attempt_id)
                return self._result(job["id"], attempt_id, "validação aprovada")
            self.m.fail_attempt(attempt_id, f"validation_failed: {report}", fatal=True)
            return self._result(job["id"], attempt_id, "validação reprovada")
        except LeaseLost as exc:
            # perdeu a posse (outra tentativa/parada/cancelamento): não escreve mais nada
            return self._result(job["id"], attempt_id, f"posse perdida: {exc}")
        finally:
            self._hb_stop.set()
            if hb.is_alive():
                hb.join(timeout=5)
            self._cleanup(tmp_dir)

    def _graceful_stop(self, attempt_id: str, job_id: str, state: dict, last_done: int, faults: dict) -> RunResult:
        degraded, detail = False, None
        try:
            if faults.get("fail_stop_checkpoint"):
                raise OSError("falha simulada ao gravar o checkpoint de parada")
            self.m.save_checkpoint(attempt_id, last_done, "parada", state, kind="stop")
        except LeaseLost:
            raise
        except Exception as exc:  # noqa: BLE001 - o último checkpoint válido anterior continua disponível
            degraded, detail = True, f"checkpoint de parada falhou: {exc}"
        self._cleanup(self.m.paths.job_tmp(job_id, attempt_id))
        self.m.finish_stop(attempt_id, degraded=degraded, detail=detail)
        return self._result(job_id, attempt_id, "parada graciosa" + (" (degradada)" if degraded else ""))

    def _pause_factory(self, attempt_id: str, job_id: str, state: dict, last_done: int) -> RunResult:
        try:
            self.m.save_checkpoint(attempt_id, last_done, "pausa-stop-fabrica", state, kind="pause")
        except LeaseLost:
            raise
        except Exception:  # noqa: BLE001
            pass
        self.m.pause_for_factory_stop(attempt_id)
        return self._result(job_id, attempt_id, "pausado pelo STOP da fábrica")

    def _cleanup(self, tmp_dir) -> None:
        """Remove só o diretório temporário da tentativa, criado pela própria fábrica (08 §6)."""
        try:
            if tmp_dir.exists() and self.m.paths.is_factory_tmp(tmp_dir):
                shutil.rmtree(tmp_dir)
        except OSError:
            pass

    def _result(self, job_id: str, attempt_id: str, detail: str) -> RunResult:
        try:
            state = self.m.get_job(job_id)["state"]
        except Exception:  # noqa: BLE001
            state = None
        return RunResult(job_id, attempt_id, state, detail)
