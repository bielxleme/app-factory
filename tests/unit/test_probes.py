"""G23-20 (isolamento de falhas), G23-22 (somente leitura), G23-27 (sondas Windows reais), G23-30 (NVML e fallback
`nvidia-smi` isolado) — D-0058, D-0059, D-0067, D-0068."""
import ast
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

from appfactory.resources.probes import RawSample, SampleSource, default_probes
from appfactory.resources.probes import nvidia as nv
from appfactory.resources.probes.runtime_local import OLLAMA_PS_URL, OllamaPsProbe, parse_ps
from tests.fakes.probes import FakeResourceClock, ScriptedProbe

RES = Path(__file__).resolve().parents[2] / "src" / "appfactory" / "resources"


def _trees():
    for p in sorted(RES.rglob("*.py")):
        yield p.relative_to(RES).as_posix(), ast.parse(p.read_text(encoding="utf-8"))


class FakeNvml:
    def __init__(self, fail=False):
        self.fail = fail

    def query(self):
        if self.fail:
            raise nv.NvmlError("nvml indisponível")
        return {"gpu_name": "RTX", "vram_total_mib": 6141.0, "vram_used_mib": 105.0, "gpu_util_pct": 0.0,
                "gpu_temp_c": 46.0, "gpu_power_w": 2.3, "gpu_pids": [11216]}


class Failures(unittest.TestCase):
    def test_g23_20_probe_exception_is_recorded_and_isolated(self):
        bad = ScriptedProbe()
        bad.fail = True
        good = ScriptedProbe(ram_available_gb=8.0)
        good.name = "good"
        c = FakeResourceClock()
        s = SampleSource([bad, good], c, c.suspend_ms).sample()
        self.assertEqual([f["probe"] for f in s.failures], ["fake"])
        self.assertEqual(s.ram_available_gb, 8.0)
        self.assertEqual((s.active_ms, s.suspend_ms, s.boot_id), (c.active, c.suspend, c.boot))


class NvidiaFallback(unittest.TestCase):
    def test_g23_30_nvml_is_primary_path(self):
        smi = mock.Mock(side_effect=AssertionError("nvidia-smi não pode rodar com a NVML ok"))
        s = RawSample()
        nv.NvidiaProbe(nvml=FakeNvml(), smi=smi).collect(s)
        smi.assert_not_called()
        self.assertEqual((s.gpu_source, s.vram_total_mib, s.failures), ("nvml", 6141.0, []))

    def test_g23_30_fallback_only_after_nvml_failure(self):
        smi = mock.Mock(return_value={"gpu_name": "RTX", "vram_total_mib": 6141.0, "vram_used_mib": 200.0,
                                      "gpu_util_pct": 5.0, "gpu_temp_c": 50.0, "gpu_power_w": None, "gpu_pids": None})
        s = RawSample()
        nv.NvidiaProbe(nvml=FakeNvml(fail=True), smi=smi).collect(s)
        smi.assert_called_once()
        self.assertEqual(s.gpu_source, "nvidia-smi")
        self.assertEqual([f["probe"] for f in s.failures], ["nvidia.nvml"])
        s = RawSample()
        nv.NvidiaProbe(nvml=FakeNvml(fail=True), smi=mock.Mock(side_effect=OSError("x"))).collect(s)
        self.assertEqual([f["probe"] for f in s.failures], ["nvidia.nvml", "nvidia.nvidia-smi"])
        self.assertIsNone(s.vram_total_mib)                                     # pior caso

    def test_g23_30_smi_invocation_is_fixed_query_without_shell(self):
        runner = mock.Mock(return_value=mock.Mock(returncode=0, stdout="RTX 4050, 6141, 105, 0, 45, [N/A]\n"))
        with mock.patch.object(nv, "_candidates", return_value=[r"C:\Windows\System32\nvidia-smi.exe"]):
            data = nv.query_nvidia_smi(runner=runner)
        args, kwargs = runner.call_args
        self.assertEqual(args[0], [r"C:\Windows\System32\nvidia-smi.exe", nv.SMI_QUERY,
                                   "--format=csv,noheader,nounits"])
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], nv.SMI_TIMEOUT_S)
        self.assertNotIn("USERPROFILE", kwargs["env"])
        self.assertEqual((data["vram_total_mib"], data["gpu_power_w"]), (6141.0, None))
        with mock.patch.object(nv, "_candidates", return_value=[]):
            with self.assertRaises(FileNotFoundError):
                nv.query_nvidia_smi(runner=runner)

    def test_g23_30_subprocess_only_in_smi_fallback(self):
        tree = ast.parse((RES / "probes" / "nvidia.py").read_text(encoding="utf-8"))
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            uses = [n for n in ast.walk(fn) if isinstance(n, ast.Attribute) and getattr(n.value, "id", "") == "subprocess"]
            if uses:
                self.assertEqual(fn.name, "query_nvidia_smi")


class ReadOnly(unittest.TestCase):
    def test_g23_22_ollama_only_get_api_ps(self):
        urls = set()
        for rel, tree in _trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    urls.update(re.findall(r"[a-z]+://[^\s`'\"]+", node.value))
                if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in (
                        "Request", "urlopen", "open"):
                    for kw in node.keywords:
                        self.assertNotEqual(kw.arg, "data", rel)
                        if kw.arg == "method":
                            self.assertEqual(kw.value.value, "GET", rel)
        self.assertEqual(urls, {OLLAMA_PS_URL})
        self.assertEqual(OLLAMA_PS_URL, "http://127.0.0.1:11434/api/ps")

    def test_g23_22_no_job_state_changes_or_sql_writes(self):
        banned_calls = {"stop_factory", "resume_factory", "check_stop_file", "factory_stop_state", "set_stop",
                        "_transition", "claim", "hold_attempt", "record_violation"}
        allowed_store = {"connect", "emit", "migrate", "write_tx"}
        for rel, tree in _trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertNotIn(node.module, ("appfactory.jobs.manager", "appfactory.jobs.executor",
                                                   "appfactory.jobs.states", "appfactory.jobs.handlers"), rel)
                    if node.module == "appfactory.jobs.store":
                        self.assertLessEqual({a.name for a in node.names}, allowed_store, rel)
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "attr", getattr(node.func, "id", None))
                    self.assertNotIn(name, banned_calls, rel)
                    if isinstance(node.func, ast.Attribute) and getattr(node.func.value, "id", "") == "factory_stop":
                        self.assertEqual(node.func.attr, "get_state", rel)
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    head = node.value.lstrip().upper()
                    for verb in ("UPDATE ", "DELETE ", "INSERT ", "CREATE ", "ALTER ", "DROP "):
                        self.assertFalse(head.startswith(verb), f"SQL de escrita em {rel}")

    def test_ollama_probe_parses_ps_readonly(self):
        body = b'{"models": [{"name": "qwen3:4b", "size_vram": 2621440000}, {"model": "x", "size_vram": -5}]}'
        s = RawSample()
        OllamaPsProbe(fetch=lambda: body).collect(s)
        self.assertEqual(s.ollama_models[0]["name"], "qwen3:4b")
        self.assertAlmostEqual(s.ollama_models[0]["size_vram_mib"], 2500.0)
        self.assertEqual(s.ollama_models[1]["size_vram_mib"], 0)
        with self.assertRaises(ValueError):
            parse_ps(b'{"x": 1}')


class OllamaSchedule(unittest.TestCase):
    """D-0075: /api/ps no máximo a cada 15 s (05 §1), em segundo plano; timeout não atrasa as amostras; falha =
    pior caso registrado (G23-20, G23-32)."""

    class Mono:
        def __init__(self):
            self.t = 1000.0

        def __call__(self):
            return self.t

    BODY = b'{"models": [{"name": "qwen3:8b", "size_vram": 4026531840}]}'

    def test_g23_32_ollama_queried_at_most_every_15s(self):
        mono, calls = self.Mono(), []
        probe = OllamaPsProbe(fetch=lambda: (calls.append(mono.t), self.BODY)[1], monotonic=mono,
                              spawn=lambda fn: fn())
        for _ in range(61):                                  # 61 amostras de 1 s
            s = RawSample()
            probe.collect(s)
            self.assertEqual(s.ollama_models[0]["name"], "qwen3:8b")
            self.assertEqual(s.failures, [])
            mono.t += 1.0
        self.assertEqual(len(calls), 5)                      # t = 0, 15, 30, 45, 60
        self.assertTrue(all(b - a >= 15.0 for a, b in zip(calls, calls[1:])), calls)

    def test_g23_32_background_query_never_blocks_sample(self):
        mono, pending = self.Mono(), []
        probe = OllamaPsProbe(fetch=lambda: self.BODY, monotonic=mono, spawn=pending.append)
        probe.collect(RawSample())                           # 1ª consulta: síncrona
        mono.t += 15.0
        s = RawSample()
        probe.collect(s)                                     # vencida: só agenda, não executa aqui
        self.assertEqual(len(pending), 1)
        self.assertEqual(s.ollama_models[0]["name"], "qwen3:8b")   # usa o último resultado concluído
        mono.t += 15.0
        probe.collect(RawSample())                           # consulta anterior ainda em andamento: não duplica
        self.assertEqual(len(pending), 1)

    def test_g23_20_ollama_failure_is_recorded_worst_case_until_success(self):
        mono, state = self.Mono(), {"fail": True}

        def fetch():
            if state["fail"]:
                raise TimeoutError("timed out")
            return self.BODY

        probe = OllamaPsProbe(fetch=fetch, monotonic=mono, spawn=lambda fn: fn())
        for _ in range(15):                                  # falha vale até a próxima consulta
            s = RawSample()
            probe.collect(s)
            self.assertIsNone(s.ollama_models)               # pior caso: desconhecido
            self.assertEqual([f["probe"] for f in s.failures], ["runtime_local"])
            mono.t += 1.0
        state["fail"] = False
        s = RawSample()
        probe.collect(s)                                     # t = 15 s: nova consulta, sucesso
        self.assertEqual((s.failures, s.ollama_models[0]["name"]), ([], "qwen3:8b"))

    def test_stale_result_is_worst_case(self):
        mono, pending = self.Mono(), []
        probe = OllamaPsProbe(fetch=lambda: self.BODY, monotonic=mono, spawn=pending.append)
        probe.collect(RawSample())
        mono.t += 40.0                                       # consulta travada: nada concluído desde t=0
        s = RawSample()
        probe.collect(s)
        self.assertIsNone(s.ollama_models)
        self.assertIn("velho demais", s.failures[0]["error"])

    def test_g23_32_real_timeout_does_not_change_watch_cadence(self):
        """Tempo real: Ollama que demora 0,4 s e falha não altera o intervalo nominal das amostras."""
        import tempfile
        import time as _time
        from pathlib import Path
        from unittest import mock as _mock

        from appfactory.resources.manager import ResourceManager
        from appfactory.resources.policy import load_policy
        from tests.fakes.probes import REPO

        def slow_fail():
            _time.sleep(0.4)
            raise TimeoutError("timed out")

        root = Path(tempfile.mkdtemp(prefix="af-ollama-"))
        self.addCleanup(__import__("shutil").rmtree, root, True)
        probe = OllamaPsProbe(fetch=slow_fail, interval_s=0.3)
        rm = ResourceManager(root=root, probes=[ScriptedProbe(), probe], policy=load_policy(REPO))
        stamps, payloads = [], []
        with _mock.patch.object(ResourceManager, "_stop_state", return_value=(False, False)):
            rm.watch(interval_s=0.1, count=12, on_sample=lambda p: (stamps.append(_time.monotonic()), payloads.append(p)))
        gaps = [b - a for a, b in zip(stamps[1:], stamps[2:])]      # a 1ª amostra inclui a consulta síncrona
        self.assertLess(max(gaps), 0.25, gaps)                        # bloqueando, seria >= 0,5 s
        self.assertTrue(all(any(f["probe"] == "runtime_local" for f in p["failures"]) for p in payloads))
        self.assertTrue(all(p["sample"]["ollama_models"] is None for p in payloads))


@unittest.skipUnless(sys.platform.startswith("linux"), "sonda Linux")
class LinuxProbeTests(unittest.TestCase):
    def test_d0067_minimal_linux_probe(self):
        from appfactory.resources.probes.linux import LinuxProbe
        c = FakeResourceClock()
        src = SampleSource([LinuxProbe()], c, c.suspend_ms)
        src.sample()
        s = src.sample()
        self.assertGreater(s.ram_total_gb, 0)
        self.assertIsNotNone(s.ram_available_gb)
        self.assertIn("D", s.disks)
        self.assertIsNone(s.gpu_temp_c)                    # inexistente => pior caso na decisão
        self.assertIsNone(s.on_ac)


@unittest.skipUnless(sys.platform == "win32", "só Windows (G23-27)")
class WindowsRealProbes(unittest.TestCase):
    def test_g23_27_real_windows_values(self):
        src = SampleSource(default_probes()[:2])          # NVIDIA + Windows; Ollama não é necessário aqui
        src.sample()
        s = src.sample()
        src.close()
        self.assertFalse([f for f in s.failures if f["probe"].startswith("windows.")], s.failures)
        self.assertEqual(s.gpu_source, "nvml", s.failures)
        self.assertEqual(s.logical_cpus, 12)
        self.assertAlmostEqual(s.ram_total_gb, 23.71, delta=0.05)
        self.assertEqual(round(s.vram_total_mib), 6141)
        self.assertIsNotNone(s.ram_available_gb)
        self.assertIsNotNone(s.commit_free_gb)
        self.assertIsInstance(s.fullscreen, bool)
        self.assertIsNotNone(s.idle_s)
        self.assertIn(s.on_ac, (True, False))
        self.assertTrue(s.disks.get("C") and s.disks.get("D"))
        self.assertTrue(s.processes)


if __name__ == "__main__":
    unittest.main()
