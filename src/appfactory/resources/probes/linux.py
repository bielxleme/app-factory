"""Sonda Linux mínima (D-0067): **só desenvolvimento/VM**. `/proc/meminfo`, `/proc/stat`, `statvfs`.
GPU, energia, tela cheia, ociosidade e processos não existem aqui => `None` => pior caso (05 §1)."""
from __future__ import annotations

import os
from pathlib import Path

GIB = 1024 ** 3


class LinuxProbe:
    name = "linux"

    def __init__(self, root=None) -> None:
        self.root = Path(root) if root else Path.cwd()
        self._prev_cpu = None

    def collect(self, s) -> None:
        s.logical_cpus = os.cpu_count()
        info = {}
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts:
                    info[key] = int(parts[0]) * 1024
        s.ram_total_gb = info["MemTotal"] / GIB
        s.ram_available_gb = info["MemAvailable"] / GIB
        if "CommitLimit" in info and "Committed_AS" in info:
            s.commit_free_gb = max(0, info["CommitLimit"] - info["Committed_AS"]) / GIB
        with open("/proc/stat", encoding="ascii") as fh:
            fields = [int(x) for x in fh.readline().split()[1:]]
        idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
        cur = (idle, sum(fields[:8]))
        if self._prev_cpu is not None:
            d_idle, d_total = cur[0] - self._prev_cpu[0], cur[1] - self._prev_cpu[1]
            if d_total > 0:
                s.cpu_pct = max(0.0, min(100.0, 100.0 * (d_total - d_idle) / d_total))
        self._prev_cpu = cur
        for letter, path in (("C", "/"), ("D", self.root)):
            st = os.statvfs(path)
            s.disks[letter] = {"free_gb": st.f_bavail * st.f_frsize / GIB, "size_gb": st.f_blocks * st.f_frsize / GIB}
