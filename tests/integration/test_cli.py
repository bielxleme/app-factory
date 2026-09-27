import contextlib
import io
import json
import unittest

from appfactory.cli.main import main
from tests.helpers import FactoryTestCase


class CliTest(FactoryTestCase):
    def af(self, *args) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["--root", str(self.tmp), "--json", *args])
        return code, out.getvalue(), err.getvalue()

    def test_minimal_interface(self):
        code, out, _ = self.af("job", "create", "--project", "demo", "--intent", "cli", "--payload",
                               '{"numbers": [1, 2, 3]}')
        self.assertEqual(code, 0)
        job_id = json.loads(out)["id"]
        self.assertEqual(json.loads(self.af("job", "status", job_id)[1])["state"], "QUEUED")
        self.assertEqual(len(json.loads(self.af("job", "list")[1])), 1)
        self.assertEqual(len(json.loads(self.af("job", "queue")[1])), 1)
        self.assertEqual(json.loads(self.af("job", "run", job_id)[1])["final_state"], "COMPLETED")
        show = json.loads(self.af("job", "show", job_id)[1])
        self.assertEqual(show["state"], "COMPLETED")
        self.assertTrue(show["latest_valid_checkpoint"])
        ck = json.loads(self.af("job", "checkpoint", job_id)[1])
        self.assertEqual(ck["state"]["total"], 6)
        self.assertEqual(len(json.loads(self.af("job", "checkpoint", job_id, "--all")[1])), 3)
        types = [e["type"] for e in json.loads(self.af("job", "history", job_id)[1])]
        self.assertIn("job.completed", types)
        self.assertEqual(json.loads(self.af("db", "check")[1])["ok"], True)

    def test_stop_and_errors(self):
        job_id = json.loads(self.af("job", "create", "--project", "demo", "--intent", "x")[1])["id"]
        self.assertEqual(json.loads(self.af("job", "stop", job_id)[1])["state"], "STOPPED")
        code, _, err = self.af("job", "show", "JOB-00000000-0000")
        self.assertEqual(code, 2)
        self.assertIn("erro", err)
        code, _, err = self.af("job", "create", "--project", "demo", "--intent", "x", "--type", "shell")
        self.assertEqual(code, 2)

    def test_factory_stop_release_requires_interactive_terminal(self):
        self.assertEqual(self.af("stop", "--reason", "teste")[0], 0)
        code, _, err = self.af("resume-factory")       # stdin não é terminal nos testes
        self.assertEqual(code, 2)
        self.assertIn("interativo", err)
        self.assertTrue(json.loads(self.af("status")[1])["factory_stop"]["active"])


if __name__ == "__main__":
    unittest.main()
