import threading
import unittest

from appfactory.jobs import states as S
from appfactory.jobs.errors import JobAlreadyClaimed, LeaseLost, NothingToRun, ProjectBusy
from appfactory.jobs.executor import Executor
from tests.helpers import FactoryTestCase, FakeClock, FakeLiveness


class ProjectSlotTest(FactoryTestCase):
    def test_one_running_per_project(self):
        m = self.manager()
        a1 = m.create_job("A", "a1", payload={"numbers": [1]})
        a2 = m.create_job("A", "a2", payload={"numbers": [1]})
        b1 = m.create_job("B", "b1", payload={"numbers": [1]})
        m.claim("e1", a1["id"])
        with self.assertRaises(ProjectBusy):
            m.claim("e2", a2["id"])
        self.assertEqual(m.claim("e3", b1["id"])["job"]["state"], S.RUNNING)   # outro projeto: permitido
        running_a = [j for j in m.list_jobs(project="A") if j["state"] == S.RUNNING]
        self.assertEqual(len(running_a), 1)
        m.cancel(a1["id"])
        self.assertEqual(m.claim("e2", a2["id"])["job"]["state"], S.RUNNING)

    def test_claim_next_respects_project_slot_under_race(self):
        m0 = self.manager()
        for i in range(4):
            m0.create_job("A", f"a{i}", payload={"numbers": [1]})
        managers = [self.manager() for _ in range(4)]
        barrier, wins = threading.Barrier(4), []

        def worker(mgr, n):
            barrier.wait()
            try:
                wins.append(mgr.claim(f"e{n}")["job"]["id"])
            except (NothingToRun, ProjectBusy):
                pass

        ts = [threading.Thread(target=worker, args=(mg, i)) for i, mg in enumerate(managers)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(wins), 1)
        self.assertEqual(len([j for j in m0.list_jobs() if j["state"] == S.RUNNING]), 1)


class ClaimExclusivityTest(FactoryTestCase):
    def test_two_executors_cannot_claim_same_job(self):
        m = self.manager()
        job = m.create_job("A", "x", payload={"numbers": [1, 2]})
        m.claim("exec-1", job["id"])
        with self.assertRaises(JobAlreadyClaimed):
            self.manager().claim("exec-2", job["id"])

    def test_race_on_same_job(self):
        m0 = self.manager()
        job = m0.create_job("A", "x", payload={"numbers": [1]})
        managers = [self.manager() for _ in range(6)]
        barrier, wins, losses = threading.Barrier(6), [], []

        def worker(mgr, n):
            barrier.wait()
            try:
                wins.append(mgr.claim(f"e{n}", job["id"])["attempt_id"])
            except JobAlreadyClaimed:
                losses.append(n)

        ts = [threading.Thread(target=worker, args=(mg, i)) for i, mg in enumerate(managers)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(wins), 1)
        self.assertEqual(len(losses), 5)
        self.assertEqual(len(m0.attempts(job["id"])), 1)


class LeaseTest(FactoryTestCase):
    def setUp(self):
        super().setUp()
        self.clock, self.live = FakeClock(), FakeLiveness()
        self.live.alive.update({111, 222})
        self.m = self.manager(clock=self.clock, liveness=self.live)
        self.job = self.m.create_job("A", "x", payload={"numbers": [1, 2, 3]})
        self.a1 = self.m.claim("e1", self.job["id"], pid=111)["attempt_id"]
        self.m.save_checkpoint(self.a1, 0, "s0", {"total": 1, "processed": 1})

    def test_expired_lease_of_dead_process_is_recovered_and_fenced(self):
        self.live.alive.discard(111)                        # processo morreu
        self.clock.advance(61)
        claim2 = self.m.claim("e2", self.job["id"], pid=222)
        self.assertEqual(claim2["resume_point"]["step_index"], 0)
        self.assertEqual(self.m.attempts(self.job["id"])[0]["outcome"], "interrupted")
        with self.assertRaises(LeaseLost):                  # fencing: o antigo não escreve mais
            self.m.save_checkpoint(self.a1, 1, "s1", {"total": 3, "processed": 2})
        with self.assertRaises(LeaseLost):
            self.m.heartbeat(self.a1)

    def test_alive_process_keeps_job_within_grace(self):
        self.clock.advance(61)                              # lease vencido, processo vivo, dentro da carência
        with self.assertRaises(JobAlreadyClaimed):
            self.m.claim("e2", self.job["id"], pid=222)
        self.clock.advance(60)                              # heartbeat volta: lease renovado
        self.m.heartbeat(self.a1)
        with self.assertRaises(JobAlreadyClaimed):
            self.m.claim("e2", self.job["id"], pid=222)

    def test_stalled_process_loses_ownership_after_grace(self):
        self.clock.advance(60 + 121)                        # mudo além de +2 leases (15 §5)
        self.m.claim("e2", self.job["id"], pid=222)
        self.assertEqual(self.m.attempts(self.job["id"])[0]["detail"], "verificação de vida: stalled")
        with self.assertRaises(LeaseLost):
            self.m.heartbeat(self.a1)

    def test_active_time_does_not_expire_during_sleep(self):
        # suspensão: o tempo de parede avança, o tempo ativo não (15 §4)
        self.clock._epoch += 3600
        with self.assertRaises(JobAlreadyClaimed):
            self.m.claim("e2", self.job["id"], pid=222)

    def test_reboot_means_previous_owner_is_dead(self):
        self.clock.reboot()
        self.live.alive.discard(111)                        # após reinício o processo antigo não existe
        claim2 = self.m.claim("e2", self.job["id"], pid=222)
        self.assertEqual(claim2["attempt_n"], 2)

    def test_boot_id_change_alone_never_steals_a_live_owner(self):
        self.clock.reboot()                                 # id de boot mudou, mas o dono segue vivo
        with self.assertRaises(JobAlreadyClaimed):
            self.m.claim("e2", self.job["id"], pid=222)


if __name__ == "__main__":
    unittest.main()
