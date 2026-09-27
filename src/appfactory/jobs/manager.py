"""Job Manager (01 §3; 03; 07; 15 §5) — fundação da Fase 2.1.

Regras centrais:
* SQLite é a fonte da verdade; toda mudança de estado grava o evento na MESMA transação (07 §5).
* Transições só pela máquina de estados (states.py); COMPLETED exige validação aprovada.
* No máximo 1 job PLANNING/RUNNING/STOPPING por projeto (índice único no banco, D-0036).
* Posse de um job por tentativa com lease em tempo ativo + fencing: escritas de uma tentativa que
  perdeu a posse são recusadas (LeaseLost). Nunca há duas tentativas donas do mesmo job.
* Espelhos operacionais (runtime/job.json, logs/jobs/*.jsonl) são escritos DEPOIS do commit e nunca são
  fonte da verdade.
"""
from __future__ import annotations

import contextlib
import datetime
import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from typing import Callable, Iterator

from appfactory.checkpoints import service as ckpt
from appfactory.core import stop as factory_stop
from appfactory.core.clock import SystemClock
from appfactory.core.ids import attempt_id as make_attempt_id
from appfactory.core.ids import new_job_id
from appfactory.core.paths import FactoryPaths
from appfactory.core.procinfo import current_identity, process_matches
from appfactory.jobs import leases, locks
from appfactory.jobs import states as S
from appfactory.jobs.errors import (FactoryStopped, InvalidTransition, JobAlreadyClaimed, JobNotFound,
                                    LeaseLost, NothingToRun, ProjectBusy, ValidationRequired)
from appfactory.jobs.handlers import get_handler
from appfactory.jobs.store import connect, emit, migrate, write_tx
from appfactory.logs.jsonlog import append_jsonl, write_json_atomic
from appfactory.logs.redaction import redact

_PROJECT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


@dataclass
class JobManagerConfig:
    heartbeat_s: float = 15.0      # 03 §4
    lease_s: float = 60.0          # 03 §4 (tempo ativo)
    stale_grace_leases: int = 2    # 15 §5: +2 leases (120 s) antes de tirar a posse de um processo mudo
    max_attempts: int = 3          # 03 §3
    max_interrupted: int = 5       # D-0044: evita laço infinito de crash/retomada
    aging_minutes: int = 30        # 03 §6


def _row(r: sqlite3.Row | None) -> dict | None:
    return {k: r[k] for k in r.keys()} if r is not None else None


class JobManager:
    def __init__(self, root=None, *, paths: FactoryPaths | None = None, clock=None,
                 config: JobManagerConfig | None = None,
                 liveness: Callable[[int | None, str | None], bool] | None = None) -> None:
        if paths is None:
            if root is None:
                raise ValueError("informe root ou paths")
            paths = FactoryPaths(root)
        self.paths = paths
        self.clock = clock or SystemClock()
        self.config = config or JobManagerConfig()
        self.liveness = liveness or process_matches
        self.factory_stop_flag = threading.Event()   # espelho em memória do STOP (D-0028)
        with self._conn() as conn:
            migrate(conn)
        self.check_stop_file()
        self.refresh_factory_stop()

    # ------------------------------------------------------------------ infraestrutura
    @contextlib.contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = connect(self.paths.db)
        try:
            yield conn
        finally:
            conn.close()

    @contextlib.contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._conn() as conn:
            before = conn.execute("SELECT COALESCE(MAX(seq), 0) FROM events").fetchone()[0]
            with write_tx(conn):
                yield conn
            self._mirror(conn, before)

    def _mirror(self, conn: sqlite3.Connection, after_seq: int) -> None:
        """Espelhos operacionais pós-commit (best effort; nunca fonte da verdade)."""
        rows = conn.execute("SELECT * FROM events WHERE seq > ? ORDER BY seq", (after_seq,)).fetchall()
        last_job = None
        for r in rows:
            ev = _row(r)
            if ev["job_id"]:
                append_jsonl(self.paths.job_log(ev["job_id"]), ev)
                last_job = ev["job_id"]
        if last_job:
            job = _row(conn.execute("SELECT * FROM jobs WHERE id = ?", (last_job,)).fetchone())
            if job:
                job.pop("payload_json", None)
                write_json_atomic(self.paths.runtime_job_json, {
                    "note": "Espelho operacional (07 §1.2). Fonte da verdade: .appfactory/state/factory.db",
                    "generated_at": self.clock.now_iso(), "job": job})

    def _now(self) -> str:
        return self.clock.now_iso()

    def _lease_ms(self) -> int:
        return int(self.config.lease_s * 1000)

    @staticmethod
    def _get_job(conn: sqlite3.Connection, job_id: str) -> dict:
        job = _row(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())
        if job is None:
            raise JobNotFound(job_id)
        return job

    @staticmethod
    def _get_attempt(conn: sqlite3.Connection, attempt_id: str) -> dict | None:
        return _row(conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone())

    def _transition(self, conn: sqlite3.Connection, job: dict, target: str, *, reason: str | None,
                    actor: str, sets: dict | None = None, _completion_validated: bool = False) -> dict:
        current = job["state"]
        S.check_transition(current, target)
        if target == S.COMPLETED and not _completion_validated:
            raise ValidationRequired("COMPLETED só pode ser atribuído por complete() após validação aprovada")
        ts = self._now()
        cols = {"state": target, "state_reason": reason, "updated_at": ts}
        stamp = {S.QUEUED: "queued_at", S.COMPLETED: "completed_at", S.FAILED: "failed_at",
                 S.STOPPED: "stopped_at", S.CANCELLED: "cancelled_at"}.get(target)
        if stamp:
            cols[stamp] = ts
        if target == S.RUNNING and not job.get("started_at"):
            cols["started_at"] = ts
        if sets:
            cols.update(sets)
        assignments = ", ".join(f"{k} = ?" for k in cols)
        try:
            conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ? AND state = ?",
                         (*cols.values(), job["id"], current))
        except sqlite3.IntegrityError as exc:
            if "jobs.project" in str(exc) or "UNIQUE" in str(exc):
                raise ProjectBusy(f"projeto {job['project']} já tem job ativo") from exc
            raise
        if conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise InvalidTransition(f"{job['id']} mudou de estado concorrentemente")
        emit(conn, ts, "job.state_changed", job_id=job["id"], attempt_id=job.get("current_attempt_id"),
             actor=actor, from_state=current, to_state=target, reason=reason)
        job.update(cols)
        return job

    def _close_attempt(self, conn: sqlite3.Connection, attempt_id: str, outcome: str, detail: str | None) -> None:
        ts = self._now()
        conn.execute("UPDATE attempts SET ended_at = ?, outcome = ?, detail = ? WHERE id = ? AND ended_at IS NULL",
                     (ts, outcome, redact(detail)[:2000] if detail else None, attempt_id))
        conn.execute("UPDATE jobs SET current_attempt_id = NULL, updated_at = ? WHERE current_attempt_id = ?",
                     (ts, attempt_id))
        att = self._get_attempt(conn, attempt_id)
        emit(conn, ts, f"attempt.{outcome}", job_id=att["job_id"] if att else None, attempt_id=attempt_id,
             actor="system", reason=(redact(detail)[:500] if detail else None))

    def _fenced(self, conn: sqlite3.Connection, attempt_id: str, allowed: set[str]) -> tuple[dict, dict]:
        """Fencing (15 §5): só a tentativa dona, ainda aberta, com o job num estado permitido, pode escrever."""
        att = self._get_attempt(conn, attempt_id)
        if att is None or att["ended_at"] is not None:
            raise LeaseLost(f"tentativa {attempt_id} encerrada ou inexistente")
        job = self._get_job(conn, att["job_id"])
        if job["current_attempt_id"] != attempt_id or job["state"] not in allowed:
            raise LeaseLost(f"tentativa {attempt_id} não é mais dona de {job['id']} (estado {job['state']})")
        return att, job

    def _renew_lease(self, conn: sqlite3.Connection, attempt_id: str) -> None:
        now = self.clock.active_ms()
        conn.execute("UPDATE attempts SET lease_expires_active_ms = ?, last_heartbeat_active_ms = ?, "
                     "last_heartbeat_at = ? WHERE id = ?", (now + self._lease_ms(), now, self._now(), attempt_id))

    def attempt_status(self, att: dict) -> str:
        return leases.evaluate(att, now_active_ms=self.clock.active_ms(), current_boot_id=self.clock.boot_id(),
                               lease_ms=self._lease_ms(), stale_grace_leases=self.config.stale_grace_leases,
                               liveness=self.liveness)

    def _resume_point(self, conn: sqlite3.Connection, job_id: str) -> dict | None:
        return ckpt.latest_valid(conn, job_id, mark_invalid_ts=self._now())

    def _interrupt_attempt(self, conn: sqlite3.Connection, job: dict, att: dict, status: str) -> dict:
        """Tentativa morta/muda: fecha como 'interrupted' e decide o destino do job (07 §3.5, 15 §5)."""
        self._close_attempt(conn, att["id"], "interrupted", f"verificação de vida: {status}")
        job = self._get_job(conn, job["id"])
        conn.execute("UPDATE jobs SET interrupted_attempts = interrupted_attempts + 1 WHERE id = ?", (job["id"],))
        job["interrupted_attempts"] += 1
        pending = conn.execute("SELECT step_index FROM step_journal WHERE attempt_id = ? AND side_effect = 1 "
                               "AND result_at IS NULL ORDER BY step_index", (att["id"],)).fetchall()
        point = self._resume_point(conn, job["id"])
        resume_from = point["id"] if point else None
        conn.execute("UPDATE jobs SET resume_from = ? WHERE id = ?", (resume_from, job["id"]))
        job["resume_from"] = resume_from
        if job["state"] == S.STOPPING:
            return self._transition(conn, job, S.STOPPED, reason=job.get("stop_reason") or "stop", actor="recovery")
        if pending:
            return self._transition(conn, job, S.BLOCKED, actor="recovery",
                                    reason=f"needs_human: passo {pending[0][0]} com efeito colateral sem resultado")
        if job["interrupted_attempts"] > self.config.max_interrupted:
            return self._transition(conn, job, S.BLOCKED, actor="recovery",
                                    reason="needs_human: interrupções repetidas (possível laço de falha)")
        conn.execute("UPDATE jobs SET state_reason = 'recovered', updated_at = ? WHERE id = ?", (self._now(), job["id"]))
        emit(conn, self._now(), "job.recovered", job_id=job["id"], actor="recovery",
             reason=f"retomar de {resume_from or 'início'}", payload={"resume_from": resume_from})
        job["state_reason"] = "recovered"
        return job

    # ------------------------------------------------------------------ criação e consulta
    def create_job(self, project: str, intent: str, job_type: str = "demo.steps", payload: dict | None = None,
                   priority: int = 1, max_attempts: int | None = None, actor: str = "user") -> dict:
        if not isinstance(project, str) or not _PROJECT_RE.match(project):
            raise ValueError("projeto inválido (use letras, números, '.', '_' e '-'; até 64 caracteres)")
        if not isinstance(intent, str) or not intent.strip() or len(intent) > 2000:
            raise ValueError("intenção/descrição obrigatória (até 2000 caracteres)")
        if priority not in (0, 1, 2, 3):
            raise ValueError("prioridade deve ser 0..3")
        payload = get_handler(job_type).validate_payload(payload or {})
        max_attempts = max_attempts or self.config.max_attempts
        with self._tx() as conn:
            ts = self._now()
            day = datetime.date.fromisoformat(ts[:10]).strftime("%Y%m%d")
            job_id = new_job_id(conn, day)
            conn.execute(
                "INSERT INTO jobs (id, project, intent, job_type, payload_json, state, priority, max_attempts, "
                "created_at, queued_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, project, intent.strip(), job_type, json.dumps(payload, sort_keys=True), S.QUEUED, priority,
                 max_attempts, ts, ts, ts))
            emit(conn, ts, "job.created", job_id=job_id, actor=actor, to_state=S.QUEUED,
                 payload={"project": project, "job_type": job_type, "priority": priority})
            emit(conn, ts, "job.queued", job_id=job_id, actor=actor, to_state=S.QUEUED)
            return self._get_job(conn, job_id)

    def get_job(self, job_id: str) -> dict:
        with self._conn() as conn:
            return self._get_job(conn, job_id)

    def list_jobs(self, state: str | None = None, project: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM jobs WHERE 1=1", []
        if state:
            sql += " AND state = ?"
            args.append(state.upper())
        if project:
            sql += " AND project = ?"
            args.append(project)
        with self._conn() as conn:
            return [_row(r) for r in conn.execute(sql + " ORDER BY created_at, id", args)]

    def queue(self) -> list[dict]:
        """Fila reconstruída do SQLite: prontos para retomar primeiro, depois QUEUED por prioridade efetiva."""
        with self._conn() as conn:
            return self._queue(conn)

    def _queue(self, conn: sqlite3.Connection) -> list[dict]:
        ready = [_row(r) for r in conn.execute(
            "SELECT * FROM jobs WHERE state = 'RUNNING' AND current_attempt_id IS NULL ORDER BY updated_at")]
        queued = [_row(r) for r in conn.execute("SELECT * FROM jobs WHERE state = 'QUEUED'")]
        now = self.clock.now_epoch()

        def eff(job: dict) -> tuple:
            base = job["priority"]
            try:
                waited = now - datetime.datetime.fromisoformat(job["queued_at"]).timestamp()
            except (TypeError, ValueError):
                waited = 0
            aged = base - int(max(waited, 0) // (self.config.aging_minutes * 60))
            if base > 0:
                aged = max(aged, 1)  # envelhecimento limitado a P1; só o usuário cria P0 (03 §6)
            return (aged, job["queued_at"] or "", job["id"])

        return ready + sorted(queued, key=eff)

    def history(self, job_id: str) -> list[dict]:
        with self._conn() as conn:
            self._get_job(conn, job_id)
            rows = conn.execute("SELECT * FROM events WHERE job_id = ? ORDER BY seq", (job_id,)).fetchall()
            out = []
            for r in rows:
                ev = _row(r)
                ev["payload"] = json.loads(ev.pop("payload_json")) if ev.get("payload_json") else None
                out.append(ev)
            return out

    def attempts(self, job_id: str) -> list[dict]:
        with self._conn() as conn:
            return [_row(r) for r in conn.execute("SELECT * FROM attempts WHERE job_id = ? ORDER BY n", (job_id,))]

    def list_checkpoints(self, job_id: str) -> list[dict]:
        with self._conn() as conn:
            self._get_job(conn, job_id)
            return ckpt.list_checkpoints(conn, job_id)

    def latest_valid_checkpoint(self, job_id: str) -> dict | None:
        with self._conn() as conn:
            self._get_job(conn, job_id)
            return ckpt.latest_valid(conn, job_id)

    # ------------------------------------------------------------------ execução (usado pelo executor)
    def claim(self, executor_id: str, job_id: str | None = None, pid: int | None = None,
              process_create_time: str | None = None) -> dict:
        """Assume a posse de um job (QUEUED -> RUNNING, ou RUNNING pronto para retomar)."""
        if pid is None:  # a tentativa sempre registra a identidade do processo dono (15 §5)
            pid, process_create_time = current_identity()
        self.check_stop_file()
        result, error, stopped = None, None, False
        with self._tx() as conn:  # reaproveitamentos/recuperações feitos no caminho são sempre commitados
            if factory_stop.get_state(conn).get("active"):
                stopped = True
            else:
                candidates = [self._get_job(conn, job_id)] if job_id else self._queue(conn)
                if job_id is None:
                    candidates += [_row(r) for r in conn.execute(
                        "SELECT * FROM jobs WHERE state = 'RUNNING' AND current_attempt_id IS NOT NULL")]
                for job in candidates:
                    try:
                        result = self._claim_one(conn, job, executor_id, pid, process_create_time)
                        break
                    except (ProjectBusy, JobAlreadyClaimed, InvalidTransition) as exc:
                        if job_id:
                            error = exc
                            break
        if stopped:
            self.factory_stop_flag.set()
            raise FactoryStopped("STOP da fábrica ativo: nenhum despacho")
        if result is not None:
            return result
        raise error or NothingToRun("nenhum job pronto para executar")

    def _claim_one(self, conn, job: dict, executor_id: str, pid, create_time) -> dict:
        if job["state"] == S.RUNNING and job["current_attempt_id"]:
            att = self._get_attempt(conn, job["current_attempt_id"])
            status = self.attempt_status(att)
            if status == leases.ALIVE:
                raise JobAlreadyClaimed(f"{job['id']} já está sendo executado por {att['executor_id']}")
            job = self._interrupt_attempt(conn, job, att, status)
        if job["state"] == S.QUEUED:
            other = conn.execute("SELECT id FROM jobs WHERE project = ? AND id != ? AND state IN "
                                 "('PLANNING', 'RUNNING', 'STOPPING')", (job["project"], job["id"])).fetchone()
            if other:
                if job.get("state_reason") != "project_busy":
                    conn.execute("UPDATE jobs SET state_reason = 'project_busy', updated_at = ? WHERE id = ?",
                                 (self._now(), job["id"]))
                    emit(conn, self._now(), "job.waiting_project", job_id=job["id"], actor="system",
                         reason=f"project_busy: {other[0]}")
                raise ProjectBusy(f"projeto {job['project']} ocupado por {other[0]}")
            # D-0041: jobs de tipo registrado têm plano implícito aprovado -> QUEUED -> RUNNING (03 §2 *)
            job = self._transition(conn, job, S.RUNNING, reason="claimed", actor=executor_id)
        elif not (job["state"] == S.RUNNING and job["current_attempt_id"] is None):
            raise InvalidTransition(f"{job['id']} em {job['state']} não pode ser executado")
        point = self._resume_point(conn, job["id"])
        n = job["attempt_count"] + 1
        aid = make_attempt_id(job["id"], n)
        ts, now_ms = self._now(), self.clock.active_ms()
        conn.execute(
            "INSERT INTO attempts (id, job_id, n, executor_id, pid, process_create_time, boot_id, started_at, "
            "resume_from_checkpoint, lease_expires_active_ms, last_heartbeat_active_ms, last_heartbeat_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (aid, job["id"], n, executor_id, pid, create_time, self.clock.boot_id(), ts,
             point["id"] if point else None, now_ms + self._lease_ms(), now_ms, ts))
        conn.execute("UPDATE jobs SET current_attempt_id = ?, attempt_count = ?, resume_from = ?, updated_at = ? "
                     "WHERE id = ?", (aid, n, point["id"] if point else None, ts, job["id"]))
        emit(conn, ts, "attempt.started", job_id=job["id"], attempt_id=aid, actor=executor_id,
             reason="retomada" if point else "início",
             payload={"n": n, "resume_from": point["id"] if point else None, "pid": pid})
        if point:
            emit(conn, ts, "job.resumed", job_id=job["id"], attempt_id=aid, actor=executor_id,
                 reason=f"a partir de {point['id']} (passo {point['step_index']})")
        return {"attempt_id": aid, "attempt_n": n, "job": self._get_job(conn, job["id"]), "resume_point": point}

    def heartbeat(self, attempt_id: str) -> dict:
        self.check_stop_file()
        with self._tx() as conn:
            _att, job = self._fenced(conn, attempt_id, {S.RUNNING, S.STOPPING})
            self._renew_lease(conn, attempt_id)
            fs = bool(factory_stop.get_state(conn).get("active"))
        if fs:
            self.factory_stop_flag.set()
        return {"stop": job["state"] == S.STOPPING, "factory_stop": fs, "state": job["state"]}

    def save_checkpoint(self, attempt_id: str, step_index: int, step_name: str | None, state: dict,
                        kind: str = "step", before_commit: Callable[[], None] | None = None) -> dict:
        with self._tx() as conn:
            _att, job = self._fenced(conn, attempt_id, {S.RUNNING, S.STOPPING})
            self._renew_lease(conn, attempt_id)
            return ckpt.insert_checkpoint(conn, self._now(), job["id"], attempt_id, step_index, step_name, state,
                                          kind=kind, before_commit=before_commit)

    def journal_intent(self, attempt_id: str, step_index: int) -> str:
        with self._tx() as conn:
            att, job = self._fenced(conn, attempt_id, {S.RUNNING})
            key = f"{job['id']}:step-{step_index:04d}:a{att['n']:02d}"
            conn.execute("INSERT INTO step_journal (idempotency_key, job_id, attempt_id, step_index, side_effect, "
                         "intent_at) VALUES (?, ?, ?, ?, 1, ?)", (key, job["id"], attempt_id, step_index, self._now()))
            return key

    def journal_result(self, attempt_id: str, key: str, result: dict) -> None:
        with self._tx() as conn:
            self._fenced(conn, attempt_id, {S.RUNNING, S.STOPPING})
            conn.execute("UPDATE step_journal SET result_at = ?, result_json = ? WHERE idempotency_key = ?",
                         (self._now(), json.dumps(result, sort_keys=True), key))

    def record_validation(self, attempt_id: str, passed: bool, report: dict) -> int:
        with self._tx() as conn:
            _att, job = self._fenced(conn, attempt_id, {S.RUNNING})
            ts = self._now()
            cur = conn.execute("INSERT INTO validations (job_id, attempt_id, checkpoint_id, passed, report_json, "
                               "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                               (job["id"], attempt_id, job["current_checkpoint_id"], 1 if passed else 0,
                                json.dumps(report, sort_keys=True), ts))
            emit(conn, ts, "validation.recorded", job_id=job["id"], attempt_id=attempt_id, actor="validator",
                 reason="aprovada" if passed else "reprovada", payload=report)
            return int(cur.lastrowid)

    def complete(self, attempt_id: str) -> dict:
        """RUNNING -> COMPLETED somente com validação aprovada desta tentativa sobre o checkpoint atual."""
        with self._tx() as conn:
            _att, job = self._fenced(conn, attempt_id, {S.RUNNING})
            ok = conn.execute("SELECT id FROM validations WHERE attempt_id = ? AND passed = 1 AND checkpoint_id IS ? "
                              "ORDER BY id DESC LIMIT 1", (attempt_id, job["current_checkpoint_id"])).fetchone()
            if not ok:
                raise ValidationRequired(f"{job['id']}: sem validação aprovada para o checkpoint atual")
            self._close_attempt(conn, attempt_id, "completed", None)
            job = self._get_job(conn, job["id"])
            job = self._transition(conn, job, S.COMPLETED, reason=f"validação {ok[0]} aprovada", actor="validator",
                                   _completion_validated=True)
            locks.release_owner(conn, job["id"])
            emit(conn, self._now(), "job.completed", job_id=job["id"], actor="validator")
            return job

    def fail_attempt(self, attempt_id: str, error: str, fatal: bool = False) -> dict | None:
        """Falha durante a execução. Retorna o job, ou None se a tentativa já não era dona (fencing)."""
        with self._tx() as conn:
            try:
                _att, job = self._fenced(conn, attempt_id, {S.RUNNING, S.STOPPING})
            except LeaseLost:
                return None
            self._close_attempt(conn, attempt_id, "failed", error)
            conn.execute("UPDATE jobs SET failed_attempts = failed_attempts + 1 WHERE id = ?", (job["id"],))
            job = self._get_job(conn, job["id"])
            point = self._resume_point(conn, job["id"])
            conn.execute("UPDATE jobs SET resume_from = ? WHERE id = ?", (point["id"] if point else None, job["id"]))
            if job["state"] == S.STOPPING:  # a parada pedida prevalece (direção segura)
                emit(conn, self._now(), "job.stop_degraded", job_id=job["id"], actor="executor",
                     reason=f"falha durante a parada: {redact(error)[:300]}")
                return self._transition(conn, job, S.STOPPED, reason=job.get("stop_reason") or "stop", actor="executor")
            if fatal:
                return self._transition(conn, job, S.FAILED, reason=redact(error)[:500], actor="executor",
                                        sets={"fail_reason": redact(error)[:2000]})
            if job["failed_attempts"] >= job["max_attempts"]:
                return self._transition(conn, job, S.BLOCKED, actor="executor",
                                        reason=f"needs_human: {job['failed_attempts']} tentativas falharam")
            conn.execute("UPDATE jobs SET state_reason = 'retry_pending', updated_at = ? WHERE id = ?",
                         (self._now(), job["id"]))
            emit(conn, self._now(), "job.retry_pending", job_id=job["id"], actor="executor",
                 reason=f"tentativa {job['failed_attempts']}/{job['max_attempts']} falhou")
            return self._get_job(conn, job["id"])

    # ------------------------------------------------------------------ STOP de job (D-0040)
    def request_stop(self, job_id: str, reason: str = "user_request", actor: str = "user") -> dict:
        with self._tx() as conn:
            job = self._get_job(conn, job_id)
            if job["state"] in (S.STOPPING, S.STOPPED):
                return job
            ts = self._now()
            if job["state"] in (S.RUNNING, S.PLANNING):
                conn.execute("UPDATE jobs SET stop_requested_at = ?, stop_reason = ? WHERE id = ?", (ts, reason, job_id))
                job = self._transition(conn, job, S.STOPPING, reason=reason, actor=actor,
                                       sets={"stop_requested_at": ts, "stop_reason": reason})
                emit(conn, ts, "job.stop_requested", job_id=job_id, actor=actor, reason=reason)
                if job["current_attempt_id"] is None:  # ninguém executando: parada imediata
                    job = self._transition(conn, job, S.STOPPED, reason=reason, actor=actor)
                return job
            if job["state"] in (S.QUEUED, S.PAUSED, S.WAITING, S.BLOCKED):
                emit(conn, ts, "job.stop_requested", job_id=job_id, actor=actor, reason=reason)
                return self._transition(conn, job, S.STOPPED, reason=reason, actor=actor,
                                        sets={"stop_requested_at": ts, "stop_reason": reason})
            raise InvalidTransition(f"{job_id} em {job['state']} não pode ser parado")

    def finish_stop(self, attempt_id: str, degraded: bool = False, detail: str | None = None) -> dict:
        with self._tx() as conn:
            _att, job = self._fenced(conn, attempt_id, {S.STOPPING})
            self._close_attempt(conn, attempt_id, "stopped", detail)
            job = self._get_job(conn, job["id"])
            point = self._resume_point(conn, job["id"])
            conn.execute("UPDATE jobs SET resume_from = ? WHERE id = ?", (point["id"] if point else None, job["id"]))
            if degraded:
                emit(conn, self._now(), "job.stop_degraded", job_id=job["id"], attempt_id=attempt_id, actor="executor",
                     reason=redact(detail or "checkpoint de parada não gravado")[:300],
                     payload={"resume_from": point["id"] if point else None})
            return self._transition(conn, job, S.STOPPED, reason=job.get("stop_reason") or "stop", actor="executor")

    def pause_for_factory_stop(self, attempt_id: str) -> dict:
        with self._tx() as conn:
            _att, job = self._fenced(conn, attempt_id, {S.RUNNING})
            self._close_attempt(conn, attempt_id, "paused", "STOP da fábrica")
            job = self._get_job(conn, job["id"])
            return self._transition(conn, job, S.PAUSED, reason="factory_stop", actor="executor")

    def resume(self, job_id: str, actor: str = "user") -> dict:
        """Comando explícito: STOPPED/PAUSED/BLOCKED/WAITING/FAILED -> QUEUED (retoma do último checkpoint válido)."""
        with self._tx() as conn:
            job = self._get_job(conn, job_id)
            if job["state"] == S.PAUSED and job["state_reason"] == "factory_stop" and \
                    factory_stop.get_state(conn).get("active"):
                raise FactoryStopped("STOP da fábrica ativo: use `af resume-factory` primeiro")
            if job["state"] not in (S.STOPPED, S.PAUSED, S.BLOCKED, S.WAITING, S.FAILED):
                raise InvalidTransition(f"{job_id} em {job['state']} não pode ser retomado")
            point = self._resume_point(conn, job_id)
            job = self._transition(conn, job, S.QUEUED, reason="resume", actor=actor,
                                   sets={"failed_attempts": 0, "interrupted_attempts": 0,
                                         "resume_from": point["id"] if point else None,
                                         "stop_requested_at": None, "stop_reason": None})
            emit(conn, self._now(), "job.resume_requested", job_id=job_id, actor=actor,
                 reason=f"retomar de {point['id'] if point else 'início'}")
            return job

    def cancel(self, job_id: str, reason: str = "user_cancel", actor: str = "user") -> dict:
        with self._tx() as conn:
            job = self._get_job(conn, job_id)
            if job["state"] in S.TERMINAL:
                raise InvalidTransition(f"{job_id} já está em {job['state']}")
            if job["current_attempt_id"]:
                self._close_attempt(conn, job["current_attempt_id"], "cancelled", reason)
                job = self._get_job(conn, job_id)
            job = self._transition(conn, job, S.CANCELLED, reason=reason, actor=actor)
            locks.release_owner(conn, job_id)
            return job

    # ------------------------------------------------------------------ STOP da fábrica (D-0028)
    def factory_stop_state(self) -> dict:
        self.check_stop_file()
        with self._conn() as conn:
            return factory_stop.get_state(conn)

    def refresh_factory_stop(self) -> bool:
        with self._conn() as conn:
            active = bool(factory_stop.get_state(conn).get("active"))
        (self.factory_stop_flag.set if active else self.factory_stop_flag.clear)()
        return active

    def stop_factory(self, reason: str = "user", actor: str = "user") -> bool:
        with self._tx() as conn:
            changed = factory_stop.set_stop(conn, self._now(), reason, actor)
            for r in conn.execute("SELECT * FROM jobs WHERE state = 'RUNNING' AND current_attempt_id IS NULL").fetchall():
                self._transition(conn, _row(r), S.PAUSED, reason="factory_stop", actor=actor)
        self.factory_stop_flag.set()
        return changed

    def resume_factory(self, actor: str = "user", confirmed: bool = False) -> bool:
        """Libera o STOP. Exige confirmação explícita (a CLI pede um código digitado no console)."""
        if confirmed is not True:
            raise PermissionError("liberar o STOP exige confirmação interativa do usuário")
        with self._tx() as conn:
            changed = factory_stop.release(conn, self._now(), actor)
            if changed:
                for r in conn.execute("SELECT * FROM jobs WHERE state = 'PAUSED' AND state_reason = 'factory_stop'"
                                      ).fetchall():
                    self._transition(conn, _row(r), S.QUEUED, reason="factory_stop_released", actor=actor)
        self.refresh_factory_stop()
        return changed

    def check_stop_file(self) -> bool:
        """O arquivo .appfactory/STOP só ACIONA a parada; apagá-lo nunca libera (08 §9)."""
        if not self.paths.stop_file.exists():
            return False
        with self._conn() as conn:
            if factory_stop.get_state(conn).get("active"):
                self.factory_stop_flag.set()
                return False
        return self.stop_factory(reason="file_trigger", actor="stop_file")

    # ------------------------------------------------------------------ locks por projeto (04 §3)
    def acquire_locks(self, project: str, owner_id: str, specs: list[str]) -> list[str]:
        with self._tx() as conn:
            return locks.acquire_all(conn, self._now(), project, owner_id, specs)

    def release_locks(self, owner_id: str) -> int:
        with self._tx() as conn:
            return locks.release_owner(conn, owner_id)

    # ------------------------------------------------------------------ recuperação
    def recover(self) -> dict:
        from appfactory.jobs.recovery import recover

        return recover(self)
