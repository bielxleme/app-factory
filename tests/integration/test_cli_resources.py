"""G23-24, G23-25, G23-28, G23-32 — CLI `af resources`, eventos append-only e `watch` (D-0061, D-0063, D-0070)."""
import contextlib
import io
import json
import shutil
import sqlite3
from unittest import mock

from appfactory.cli.main import main
from appfactory.jobs.store import connect, migrate
from tests.fakes.probes import REPO, ScriptedProbe, fake_manager
from tests.helpers import FactoryTestCase

HW = {
    "schema_version": 1, "measured_at": "2026-09-26T16:36:45-03:00",
    "cpu": {"logical_processors": 12}, "ram": {"visible_total_gb": 23.71, "available_gb": 5.34, "commit_free_gb": 18.19},
    "gpu": {"nvidia_query": {"found": True, "output": "NVIDIA GeForce RTX 4050 Laptop GPU, 617.14, 6141, 105, 5816, 0, "
                                                      "1, 45, 2.31, 62.00, P8"}},
    "disks": [{"drive": "C:", "size_gb": 475.7, "free_gb": 32.9}, {"drive": "D:", "size_gb": 465.7, "free_gb": 177.8}],
    "power": {"has_battery": True, "battery_charge_pct": 79}, "user_idle_seconds": 4,
}


class CliResources(FactoryTestCase):
    def setUp(self):
        super().setUp()
        (self.tmp / "config").mkdir()
        shutil.copy(REPO / "config" / "resources.yaml", self.tmp / "config" / "resources.yaml")
        self.probe = ScriptedProbe()
        self.patch = mock.patch("appfactory.resources.manager.default_probes", return_value=[self.probe])
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        super().tearDown()

    def af(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--root", str(self.tmp), *argv])
        return code, out.getvalue()

    def test_g23_25_cli_exit_codes_and_json(self):
        code, out = self.af("resources", "snapshot", "--samples", "1")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["mode"], "FOREGROUND")
        code, out = self.af("resources", "mode")
        self.assertEqual((code, json.loads(out)["source"]), (0, "instant"))
        code, out = self.af("resources", "admit", "--kind", "agent")
        data = json.loads(out)
        self.assertEqual((code, data["decision"], data["simulation"]), (3, "WAIT", True))
        code, out = self.af("resources", "watch", "--interval", "0.01", "--count", "3")
        self.assertEqual((code, len(out.strip().splitlines())), (0, 3))
        code, out = self.af("resources", "mode")
        self.assertEqual(json.loads(out)["source"], "watch")
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.af("resources", "admit", "--kind", "gpu", "--tier", "T9")
            (self.tmp / "config" / "resources.yaml").write_text('{"sampling": {"mode_confirmations": 2}}',
                                                                 encoding="utf-8")
            self.assertEqual(self.af("resources", "snapshot")[0], 2)          # política inválida => erro

    def test_g23_28_compare(self):
        hw = self.tmp / "hw.json"
        hw.write_text(json.dumps(HW), encoding="utf-8-sig")                   # PowerShell grava com BOM
        code, out = self.af("resources", "compare", "--hardware-snapshot", str(hw))
        rep = json.loads(out)
        self.assertEqual((code, rep["ok"]), (0, True), rep)
        self.assertEqual({c["check"] for c in rep["static"]},
                         {"logical_cpus", "ram_total_gb", "vram_total_mib", "disk_C_size_gb", "disk_D_size_gb",
                          "has_battery"})
        self.probe.set(ram_total_gb=23.60)                                    # fora de ± 0,05 GB
        code, out = self.af("resources", "compare", "--hardware-snapshot", str(hw))
        self.assertEqual(code, 3)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.af("resources", "compare", "--hardware-snapshot", str(self.tmp / "x.json"))[0], 2)

    def test_g23_24_events_only_no_schema_change(self):
        fresh = sqlite3.connect(":memory:")
        fresh.row_factory = sqlite3.Row
        migrate(fresh)
        expected = sorted(r[0] for r in fresh.execute("SELECT name FROM sqlite_master"))
        rm, probe, clock = fake_manager(self.tmp, probe=ScriptedProbe(ram_available_gb=2.9))
        rm.watch(count=66)
        rm.admit(__import__("appfactory.resources.manager", fromlist=["x"]).AdmissionRequest("agent"))
        with connect(self.paths.db) as conn:
            names = sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master"))
            types = {r[0]: r[1] for r in conn.execute("SELECT type, COUNT(*) FROM events WHERE job_id IS NULL "
                                                      "GROUP BY type")}
        self.assertEqual(names, expected)                                      # nenhuma tabela/índice novo
        self.assertEqual(types["resource.snapshot"], 66)
        self.assertEqual(types["resource.admission_denied"], 1)
        self.assertFalse([n for n in names if n.startswith("resource")])

    def test_g23_32_watch_interval_and_append_only(self):
        rm, probe, clock = fake_manager(self.tmp)
        waits = []
        rm.sleep = lambda s: (waits.append(s), clock.advance(s))
        payloads = []
        rm.watch(count=3, on_sample=payloads.append)
        self.assertEqual(waits, [1.0, 1.0])                                   # padrão sampling.interval_s = 1 (D-0070)
        self.assertEqual([p["interval_s"] for p in payloads], [1.0] * 3)
        waits.clear()
        rm.watch(interval_s=5, count=2)
        self.assertEqual(waits, [5.0])
        with connect(self.paths.db) as conn:
            n = conn.execute("SELECT COUNT(*) FROM events WHERE type = 'resource.snapshot'").fetchone()[0]
            self.assertEqual(n, 5)
            for sql in ("UPDATE events SET reason = 'x' WHERE type = 'resource.snapshot'",
                        "DELETE FROM events WHERE type = 'resource.snapshot'"):
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(sql)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM events WHERE type = 'resource.snapshot'"
                                          ).fetchone()[0], 5)                  # nenhuma limpeza
        # D-0075: o tempo gasto na amostra é descontado — o período continua o nominal
        class SlowProbe(ScriptedProbe):
            def collect(self, s):
                super().collect(s)
                clock.advance(0.3)

        rm._source = None
        rm._probes = [SlowProbe()]
        waits.clear()
        rm.watch(count=3)
        self.assertEqual([round(w, 3) for w in waits], [0.7, 0.7])
        first = payloads[0]
        for key in ("active_ms", "suspend_ms", "boot_id", "policy_sha256", "mode_state", "account", "sample"):
            self.assertIn(key, first)
