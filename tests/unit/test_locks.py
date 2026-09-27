import unittest

from appfactory.jobs.locks import LockConflict, normalize_spec, overlaps
from tests.helpers import FactoryTestCase


class LockSpecTest(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_spec("src/API/health.py"), "src/api/health.py")
        self.assertEqual(normalize_spec("src\\ui\\**"), "src/ui/**")
        self.assertEqual(normalize_spec("./src/./a.py"), "src/a.py")
        for bad in ("src/*.py", "src/**/test_*.py", "/etc/passwd", "C:/x", "../fora", "", "a/../../b"):
            with self.assertRaises(ValueError, msg=bad):
                normalize_spec(bad)

    def test_overlaps(self):
        self.assertTrue(overlaps("a/b.py", "a/b.py"))
        self.assertFalse(overlaps("a/b.py", "a/c.py"))
        self.assertTrue(overlaps("a/**", "a/b/c.py"))
        self.assertTrue(overlaps("a/b/c.py", "a/**"))
        self.assertFalse(overlaps("a/**", "ab/c.py"))
        self.assertTrue(overlaps("a/**", "a/b/**"))
        self.assertFalse(overlaps("a/**", "b/**"))


class LockStoreTest(FactoryTestCase):
    def test_all_or_nothing_and_release(self):
        m = self.manager()
        m.acquire_locks("p", "JOB-1-T01", ["src/api/**"])
        with self.assertRaises(LockConflict):
            m.acquire_locks("p", "JOB-2-T01", ["docs/readme.md", "src/api/health.py"])
        # nada da segunda aquisição ficou gravado (tudo ou nada)
        m.acquire_locks("p", "JOB-3-T01", ["docs/readme.md"])
        m.acquire_locks("outro", "JOB-4-T01", ["src/api/**"])   # locks são por projeto
        self.assertEqual(m.release_locks("JOB-1"), 1)
        m.acquire_locks("p", "JOB-2-T01", ["src/api/health.py"])


if __name__ == "__main__":
    unittest.main()
