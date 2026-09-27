"""G22-18e, G22-47: papéis e tokens (08 §8; 12 §11). Somente em memória nesta fase."""
import unittest

from appfactory.core.auth import AuthError, Principal, Role, TokenRegistry, authorize

USER, UI = Principal(Role.USER), Principal(Role.UI)
RUNNER = Principal(Role.RUNNER, attempt_id="J1-A01", job_id="J1", expires_active_ms=10_000)


class AuthTests(unittest.TestCase):
    def test_g22_47_role_matrix(self):
        for route in ("/stop/release", "/approvals/APR-1"):
            self.assertFalse(authorize(RUNNER, "POST", route, confirmation_ok=True))
            self.assertFalse(authorize(UI, "POST", route, confirmation_ok=True))
            self.assertFalse(authorize(USER, "POST", route, confirmation_ok=False))
            self.assertTrue(authorize(USER, "POST", route, confirmation_ok=True))
        for p in (USER, UI, RUNNER):
            self.assertTrue(authorize(p, "POST", "/stop"))            # acionar é sempre permitido
        self.assertFalse(authorize(RUNNER, "POST", "/jobs"))
        self.assertFalse(authorize(RUNNER, "POST", "/jobs/J1/cancel"))
        self.assertFalse(authorize(RUNNER, "GET", "/jobs"))
        self.assertTrue(authorize(RUNNER, "GET", "/jobs/J1", target_job="J1"))
        self.assertFalse(authorize(RUNNER, "GET", "/jobs/J2", target_job="J2"))
        self.assertTrue(authorize(RUNNER, "POST", "/tools/fs.write", target_job="J1"))
        self.assertFalse(authorize(RUNNER, "POST", "/tools/fs.write", target_job="J2"))
        self.assertFalse(authorize(USER, "POST", "/runner/heartbeat", target_job="J1"))
        self.assertTrue(authorize(UI, "POST", "/jobs/J1/pause"))
        self.assertFalse(authorize(USER, "DELETE", "/jobs/J1"))           # rota desconhecida => negar
        self.assertFalse(authorize("user", "GET", "/health"))             # não é Principal

    def test_g22_18e_runner_cannot_release_stop(self):
        self.assertFalse(authorize(RUNNER, "POST", "/stop/release", confirmation_ok=True))

    def test_tokens(self):
        reg = TokenRegistry()
        tok = reg.mint(RUNNER)
        self.assertEqual(reg.verify(tok, 5_000), RUNNER)
        with self.assertRaises(AuthError):
            reg.verify(tok, 10_000)                                        # expira com o lease
        with self.assertRaises(AuthError):
            reg.verify("x" + tok, 1)
        with self.assertRaises(AuthError):
            reg.verify("", 1)
        with self.assertRaises(ValueError):
            reg.mint(Principal(Role.RUNNER))
        user_tok = reg.mint(USER)
        self.assertNotIn(user_tok, repr(reg.__dict__))                     # só o hash é guardado
        self.assertEqual(reg.revoke_attempt("J1-A01"), 1)
        with self.assertRaises(AuthError):
            reg.verify(tok, 1)


if __name__ == "__main__":
    unittest.main()
