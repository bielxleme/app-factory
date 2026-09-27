"""Recuperação na partida (07 §3, adaptada à Fase 2.1 — sem daemon/Job Objects ainda).

Passos executados: (2) integridade do banco; (3) STOP da fábrica (tabela + arquivo gatilho);
(5) tentativas abertas: verificação de vida -> 'interrupted' e decisão pelo journal; jobs STOPPING sem
executor -> STOPPED; jobs prontos com STOP ativo -> PAUSED; checkpoints corrompidos marcados 'invalid'.
Cada job é recuperado na sua própria transação: uma falha em um job não impede os demais, e a rotina é
idempotente (pode ser executada de novo com segurança)."""
from __future__ import annotations

from appfactory.jobs import leases
from appfactory.jobs import states as S
from appfactory.jobs.store import check_database, emit


class DatabaseCorrupt(RuntimeError):
    pass


def recover(manager) -> dict:
    report = {"database": None, "factory_stop": None, "alive": [], "interrupted": [], "stopped": [],
              "paused": [], "blocked": [], "errors": []}
    with manager._conn() as conn:
        db = check_database(conn)
    report["database"] = db
    if not db["ok"]:
        # 07 §3 passo 2: nunca sobrescrever; preservar e pedir ação humana (snapshots só existem a partir da 2.7)
        raise DatabaseCorrupt(f"banco com problema: {db}. Preserve o arquivo e acione um humano.")
    manager.check_stop_file()
    stop_active = manager.refresh_factory_stop()
    report["factory_stop"] = stop_active

    with manager._conn() as conn:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM jobs WHERE current_attempt_id IS NOT NULL OR state IN ('STOPPING', 'RUNNING') "
            "ORDER BY id")]
    for job_id in ids:
        try:
            _recover_job(manager, job_id, stop_active, report)
        except Exception as exc:  # noqa: BLE001 - registrar e seguir com os demais
            report["errors"].append({"job_id": job_id, "error": repr(exc)})
            try:
                with manager._tx() as conn:
                    emit(conn, manager._now(), "recovery.error", job_id=job_id, actor="recovery",
                         reason=repr(exc)[:500])
            except Exception:  # noqa: BLE001
                pass
    with manager._tx() as conn:
        emit(conn, manager._now(), "system.recovered", actor="recovery",
             payload={k: v for k, v in report.items() if k not in ("database",)})
    return report


def _recover_job(manager, job_id: str, stop_active: bool, report: dict) -> None:
    with manager._tx() as conn:
        job = manager._get_job(conn, job_id)
        manager._resume_point(conn, job_id)  # marca checkpoints corrompidos como 'invalid' (seguro sempre)
        if job["current_attempt_id"]:
            att = manager._get_attempt(conn, job["current_attempt_id"])
            status = manager.attempt_status(att)
            if status == leases.ALIVE:
                report["alive"].append(job_id)
                return
            job = manager._interrupt_attempt(conn, job, att, status)
            report["interrupted"].append(job_id)
        if job["state"] == S.STOPPING and job["current_attempt_id"] is None:
            job = manager._transition(conn, job, S.STOPPED, reason=job.get("stop_reason") or "stop", actor="recovery")
        if job["state"] == S.RUNNING and job["current_attempt_id"] is None and stop_active:
            job = manager._transition(conn, job, S.PAUSED, reason="factory_stop", actor="recovery")
        bucket = {S.STOPPED: "stopped", S.PAUSED: "paused", S.BLOCKED: "blocked"}.get(job["state"])
        if bucket:
            report[bucket].append(job_id)
