"""CLI mínima `af` para validar o Job Manager (Fase 2.1). Não é a interface completa da App Factory."""
from __future__ import annotations

import argparse
import json
import secrets
import sys

from appfactory import __version__
from appfactory.core.paths import FactoryPaths, discover_root
from appfactory.jobs.errors import JobManagerError
from appfactory.jobs.manager import JobManager
from appfactory.jobs.store import check_database, connect, migrate

JOB_FIELDS = ("id", "project", "state", "state_reason", "current_step", "step_index", "intent", "job_type",
              "priority", "attempt_count", "failed_attempts", "interrupted_attempts", "current_attempt_id",
              "current_checkpoint_id", "resume_from", "created_at", "queued_at", "started_at", "updated_at",
              "completed_at", "failed_at", "stopped_at", "cancelled_at", "stop_requested_at", "stop_reason",
              "fail_reason")


def _print(data, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    elif isinstance(data, list):
        for item in data:
            print(item if isinstance(item, str) else json.dumps(item, ensure_ascii=False, default=str))
    elif isinstance(data, dict):
        for k, v in data.items():
            print(f"{k:22} {v}")
    else:
        print(data)


def _job_view(job: dict) -> dict:
    return {k: job.get(k) for k in JOB_FIELDS}


def _manager(args) -> JobManager:
    root = args.root or discover_root()
    return JobManager(paths=FactoryPaths(root))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="af", description="App Factory — Job Manager (Fase 2.1)")
    p.add_argument("--version", action="version", version=f"appfactory {__version__}")
    p.add_argument("--root", help="raiz da App Factory (padrão: AF_ROOT ou descoberta a partir do diretório atual)")
    p.add_argument("--json", action="store_true", help="saída em JSON")
    sub = p.add_subparsers(dest="cmd", required=True)

    job = sub.add_parser("job", help="gerenciar jobs").add_subparsers(dest="action", required=True)
    c = job.add_parser("create", help="criar job (entra em QUEUED)")
    c.add_argument("--project", required=True)
    c.add_argument("--intent", required=True)
    c.add_argument("--type", default="demo.steps", dest="job_type")
    c.add_argument("--payload", default='{"numbers": [1, 2, 3]}', help="JSON do payload (somente dados)")
    c.add_argument("--priority", type=int, default=1)
    job.add_parser("list", help="listar jobs").add_argument("--state")
    job.add_parser("queue", help="fila reconstruída do SQLite")
    for name, helptext in (("show", "detalhes do job"), ("status", "estado atual"), ("stop", "STOP do job"),
                           ("checkpoint", "último checkpoint válido"), ("history", "histórico de eventos"),
                           ("resume", "recolocar na fila a partir do último checkpoint"), ("cancel", "cancelar")):
        sp = job.add_parser(name, help=helptext)
        sp.add_argument("job_id")
        if name == "stop":
            sp.add_argument("--reason", default="user_request")
        if name == "checkpoint":
            sp.add_argument("--all", action="store_true", help="listar todos os checkpoints")
    r = job.add_parser("run", help="executar um job neste processo (executor em primeiro plano)")
    r.add_argument("job_id", nargs="?", help="omitido: próximo da fila")

    sub.add_parser("recover", help="recuperação após reinício/queda (07 §3)")
    sub.add_parser("stop", help="STOP da fábrica (kill switch)").add_argument("--reason", default="user")
    sub.add_parser("resume-factory", help="liberar o STOP da fábrica (confirmação interativa)")
    sub.add_parser("status", help="estado do STOP da fábrica e contagem de jobs")
    db = sub.add_parser("db", help="banco de dados").add_subparsers(dest="action", required=True)
    db.add_parser("check", help="integridade e schema")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except (JobManagerError, ValueError, PermissionError, FileNotFoundError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2


def _dispatch(args) -> int:
    if args.cmd == "db":
        root = args.root or discover_root()
        conn = connect(FactoryPaths(root).db)
        try:
            migrate(conn)
            report = check_database(conn)
        finally:
            conn.close()
        _print(report, True)
        return 0 if report["ok"] else 1

    m = _manager(args)
    if args.cmd == "job":
        a = args.action
        if a == "create":
            job = m.create_job(args.project, args.intent, job_type=args.job_type, payload=json.loads(args.payload),
                               priority=args.priority)
            _print(_job_view(job), args.json)
        elif a == "list":
            rows = [_job_view(j) for j in m.list_jobs(state=args.state)]
            _print(rows if args.json else [f"{j['id']}  {j['project']:15} {j['state']:10} {j['current_step'] or '-'}"
                                          for j in rows], args.json)
        elif a == "queue":
            rows = m.queue()
            _print([_job_view(j) for j in rows] if args.json else
                   [f"{j['id']}  {j['project']:15} {j['state']:10} prioridade={j['priority']}" for j in rows], args.json)
        elif a == "show":
            job = _job_view(m.get_job(args.job_id))
            job["latest_valid_checkpoint"] = (m.latest_valid_checkpoint(args.job_id) or {}).get("id")
            _print(job, args.json)
        elif a == "status":
            job = m.get_job(args.job_id)
            _print({"id": job["id"], "state": job["state"], "state_reason": job["state_reason"],
                    "current_step": job["current_step"], "updated_at": job["updated_at"]}, args.json)
        elif a == "stop":
            _print(_job_view(m.request_stop(args.job_id, reason=args.reason)), args.json)
        elif a == "checkpoint":
            if args.all:
                _print(m.list_checkpoints(args.job_id), args.json)
            else:
                ck = m.latest_valid_checkpoint(args.job_id)
                _print(ck if ck else {"checkpoint": None, "detalhe": "nenhum checkpoint válido"}, args.json)
        elif a == "history":
            ev = m.history(args.job_id)
            _print(ev if args.json else [f"{e['seq']:>6} {e['ts']} {e['type']:24} {e['from_state'] or ''}"
                                         f"{' -> ' + e['to_state'] if e['to_state'] else ''} {e['reason'] or ''}"
                                         for e in ev], args.json)
        elif a == "resume":
            _print(_job_view(m.resume(args.job_id)), args.json)
        elif a == "cancel":
            _print(_job_view(m.cancel(args.job_id)), args.json)
        elif a == "run":
            from appfactory.jobs.executor import Executor

            res = Executor(m).run(args.job_id)
            _print({"job_id": res.job_id, "attempt_id": res.attempt_id, "final_state": res.final_state,
                    "detail": res.detail}, args.json)
        return 0
    if args.cmd == "recover":
        _print(m.recover(), True)
        return 0
    if args.cmd == "stop":
        changed = m.stop_factory(reason=args.reason, actor="user")
        _print({"factory_stop": True, "changed": changed}, args.json)
        return 0
    if args.cmd == "resume-factory":
        if not sys.stdin.isatty():
            print("erro: liberar o STOP exige terminal interativo", file=sys.stderr)
            return 2
        code = secrets.token_hex(3).upper()
        print(f"Para liberar o STOP da fábrica, digite o código {code}: ", end="", flush=True)
        typed = sys.stdin.readline().strip().upper()
        if typed != code:
            print("código incorreto; STOP mantido", file=sys.stderr)
            return 2
        _print({"released": m.resume_factory(actor="user", confirmed=True)}, args.json)
        return 0
    if args.cmd == "status":
        jobs = m.list_jobs()
        counts: dict[str, int] = {}
        for j in jobs:
            counts[j["state"]] = counts.get(j["state"], 0) + 1
        _print({"factory_stop": m.factory_stop_state(), "jobs": counts}, True)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
