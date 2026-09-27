"""Processo executor de TESTE (G22-44): registra o handler de teste e roda um job com o FakeSandbox.
Uso: python tests/fakes/exec_job_runner.py <root> <job_id> <behavior>"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO / "src"), str(REPO)]

from appfactory.core.paths import FactoryPaths  # noqa: E402
from appfactory.jobs.executor import Executor  # noqa: E402
from appfactory.jobs.manager import JobManager  # noqa: E402
from tests.fakes import exec_handler  # noqa: E402
from tests.fakes.sandbox import FakeSandbox  # noqa: E402

root, job_id, behavior = sys.argv[1], sys.argv[2], sys.argv[3]
exec_handler.register()
exec_handler.SANDBOXES.update({"S1h": FakeSandbox("S1h", behavior=behavior), "S2": FakeSandbox("S2", available=False)})
res = Executor(JobManager(paths=FactoryPaths(root))).run(job_id)
print(res.final_state, res.detail)
