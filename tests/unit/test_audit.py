"""G22-17d, G22-20, G22-46: trilha de auditoria com cadeia de hashes (08 §10; I1)."""
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import appfactory
from appfactory.logs import audit

SRC = str(Path(appfactory.__file__).resolve().parents[1])


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="af-audit-"))
        self.path = self.dir / "logs" / "audit.jsonl"

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def lines(self):
        return self.path.read_text(encoding="utf-8").splitlines()

    def test_g22_46_concurrent_threads_and_processes(self):
        def worker(n):
            for i in range(25):
                audit.append(self.path, {"type": "t", "thread": n, "i": i})
        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        code = ("import sys; sys.path.insert(0, sys.argv[1]); from appfactory.logs import audit;"
                "[audit.append(sys.argv[2], {'type': 'p', 'i': i}) for i in range(25)]")
        procs = [subprocess.Popen([sys.executable, "-c", code, SRC, str(self.path)]) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for p in procs:
            self.assertEqual(p.wait(timeout=60), 0)
        ok, idx, why = audit.verify_chain(self.path)
        self.assertTrue(ok, (idx, why))
        self.assertEqual(len(self.lines()), 150)
        self.assertEqual([json.loads(x)["seq"] for x in self.lines()], list(range(1, 151)))

    def test_g22_17d_tampering_detected(self):
        for i in range(5):
            audit.append(self.path, {"type": "t", "i": i})
        original = self.lines()
        # remover a 3ª linha
        self.path.write_text("\n".join(original[:2] + original[3:]) + "\n", encoding="utf-8")
        self.assertEqual(audit.verify_chain(self.path)[:2], (False, 2))
        # alterar conteúdo
        e = json.loads(original[1])
        e["i"] = 999
        self.path.write_text("\n".join([original[0], json.dumps(e)] + original[2:]) + "\n", encoding="utf-8")
        self.assertEqual(audit.verify_chain(self.path)[:2], (False, 1))
        # reordenar
        self.path.write_text("\n".join([original[1], original[0]] + original[2:]) + "\n", encoding="utf-8")
        self.assertFalse(audit.verify_chain(self.path)[0])
        # linha incompleta
        self.path.write_text("\n".join(original) + "\n{\"type\":", encoding="utf-8")
        self.assertFalse(audit.verify_chain(self.path)[0])
        # íntegro de novo
        self.path.write_text("\n".join(original) + "\n", encoding="utf-8")
        self.assertTrue(audit.verify_chain(self.path)[0])
        # Limitação documentada (P-13, pendente): cortar as ÚLTIMAS linhas não é detectável só pela cadeia.
        self.path.write_text("\n".join(original[:3]) + "\n", encoding="utf-8")
        self.assertTrue(audit.verify_chain(self.path)[0])

    def test_g22_20_redaction_before_hash(self):
        audit.append(self.path, {"type": "t", "detail": "token=ghp_abcdefghijklmnopqrstuvwxyz0123 password=hunter2",
                                 "key": "sk-abcdefghijklmnopqrstuvwxyz"})
        text = self.path.read_text(encoding="utf-8")
        for secret in ("ghp_abcdefghijklmnopqrstuvwxyz0123", "hunter2", "sk-abcdefghijklmnopqrstuvwxyz"):
            self.assertNotIn(secret, text)
        self.assertIn("[REDACTED]", text)
        self.assertTrue(audit.verify_chain(self.path)[0])

    def test_record_requires_type_and_missing_file_is_intact(self):
        with self.assertRaises(ValueError):
            audit.append(self.path, {"x": 1})
        self.assertTrue(audit.verify_chain(self.dir / "nao-existe.jsonl")[0])
        audit.append(self.path, {"type": "t", "seq": 77, "hash": "forjado", "prev_hash": "forjado"})
        self.assertEqual(json.loads(self.lines()[0])["seq"], 1)
        self.assertTrue(audit.verify_chain(self.path)[0])


if __name__ == "__main__":
    unittest.main()
