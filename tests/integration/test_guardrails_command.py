"""G22-48 (comando fixo) e G22-49 (`conftest.py` malicioso é ignorado por --noconftest)."""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from appfactory.security.guardrail_manifest import FIXED_COMMAND, load_manifest, pending

REPO = Path(__file__).resolve().parents[2]
HAS_PYTEST = importlib.util.find_spec("pytest") is not None
MALICIOUS = 'raise SystemExit("conftest malicioso carregado: --noconftest foi ignorado")\n'


def run_fixed(cwd):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "AF_ROOT")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, *FIXED_COMMAND], cwd=str(cwd), env=env, capture_output=True, text=True,
                          timeout=600, stdin=subprocess.DEVNULL)
    out = proc.stdout + proc.stderr
    counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|skipped|failed|error|errors)", out)}
    return proc.returncode, counts, out


@unittest.skipUnless(HAS_PYTEST, "pytest não instalado neste ambiente (rode com `uv run pytest`)")
class FixedGuardrailCommand(unittest.TestCase):
    def test_g22_48_fixed_command(self):
        rc, counts, out = run_fixed(REPO)
        self.assertEqual(rc, 0, out[-3000:])
        self.assertNotIn("failed", counts)
        self.assertEqual(counts.get("skipped", 0), len(pending(load_manifest(REPO))), out[-2000:])
        self.assertGreater(counts.get("passed", 0), 0)

    def test_g22_49_malicious_conftest_ignored(self):
        _, original, _ = run_fixed(REPO)
        tmp = Path(tempfile.mkdtemp(prefix="af-conftest-"))
        try:
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
            shutil.copytree(REPO / "src", tmp / "src", ignore=ignore)
            shutil.copytree(REPO / "config", tmp / "config", ignore=ignore)
            shutil.copytree(REPO / "tests" / "guardrails", tmp / "tests" / "guardrails", ignore=ignore)
            shutil.copytree(REPO / "tests" / "fakes", tmp / "tests" / "fakes", ignore=ignore)
            for f in ("__init__.py", "helpers.py"):
                shutil.copy(REPO / "tests" / f, tmp / "tests" / f)
            for d in (tmp, tmp / "tests", tmp / "tests" / "guardrails"):
                (d / "conftest.py").write_text(MALICIOUS, encoding="utf-8")
            rc, counts, out = run_fixed(tmp)
            self.assertEqual(rc, 0, out[-3000:])
            self.assertNotIn("conftest malicioso", out)
            self.assertEqual(counts, original)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
