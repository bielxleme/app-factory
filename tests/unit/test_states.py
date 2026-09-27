import unittest

from appfactory.jobs import states as S
from appfactory.jobs.errors import InvalidTransition


class StateMachineTest(unittest.TestCase):
    def test_every_state_has_rules(self):
        self.assertEqual(set(S.TRANSITIONS), set(S.ALL_STATES))

    def test_valid_transitions(self):
        for src, targets in S.TRANSITIONS.items():
            for dst in targets:
                S.check_transition(src, dst)

    def test_invalid_transitions_rejected(self):
        for src in S.ALL_STATES:
            for dst in S.ALL_STATES:
                if dst not in S.TRANSITIONS[src]:
                    with self.assertRaises(InvalidTransition, msg=f"{src}->{dst}"):
                        S.check_transition(src, dst)

    def test_key_rules(self):
        with self.assertRaises(InvalidTransition):
            S.check_transition(S.QUEUED, S.COMPLETED)          # nunca completa sem executar
        with self.assertRaises(InvalidTransition):
            S.check_transition(S.STOPPED, S.RUNNING)           # retomada só via QUEUED (comando explícito)
        for dst in S.ALL_STATES:
            with self.assertRaises(InvalidTransition):
                S.check_transition(S.COMPLETED, dst)           # terminal
        self.assertIn(S.STOPPING, S.TRANSITIONS[S.RUNNING])
        self.assertEqual(S.TRANSITIONS[S.STOPPING], frozenset({S.STOPPED, S.CANCELLED}))

    def test_unknown_state(self):
        with self.assertRaises(InvalidTransition):
            S.check_transition("running", S.PAUSED)


if __name__ == "__main__":
    unittest.main()
