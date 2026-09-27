"""S1h — usuário dedicado `afrunner` + Job Object + ACL (08 §4.2; D-0026). SOMENTE ESPECIFICAÇÃO na 2.2.

`S1hLaunchSpec` descreve, como dados, o lançamento que a fatia 2.6 fará depois da prova de conceito
(KI-0014) e do setup do usuário (conta, ACLs; KI-0016). Nada aqui cria usuário, altera ACL, cria Job Object
ou lança processo: `S1hSandbox.run` sempre lança SandboxUnavailable (falha fechada)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from appfactory.security.command_policy import clean_env
from appfactory.security.sandbox import Limits, SandboxUnavailable, limits_for

# Valores de winnt.h / winbase.h (apenas constantes; nenhuma chamada à API do Windows nesta fase)
CREATE_SUSPENDED = 0x00000004
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
LOGON_WITH_PROFILE = 0x1
LOGON_NETCREDENTIALS_ONLY = 0x2          # PROIBIDO: executaria localmente como o usuário principal

JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_PRIORITY_CLASS = 0x00000020
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800           # PROIBIDO
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000    # PROIBIDO
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x1
JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x4
JOB_OBJECT_UILIMIT_HANDLES = 0x01
JOB_OBJECT_UILIMIT_READCLIPBOARD = 0x02
JOB_OBJECT_UILIMIT_WRITECLIPBOARD = 0x04
JOB_OBJECT_UILIMIT_SYSTEMPARAMETERS = 0x08
JOB_OBJECT_UILIMIT_DISPLAYSETTINGS = 0x10
JOB_OBJECT_UILIMIT_GLOBALATOMS = 0x20
JOB_OBJECT_UILIMIT_DESKTOP = 0x40
JOB_OBJECT_UILIMIT_EXITWINDOWS = 0x80
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
IDLE_PRIORITY_CLASS = 0x00000040

UI_RESTRICTIONS = (JOB_OBJECT_UILIMIT_HANDLES | JOB_OBJECT_UILIMIT_READCLIPBOARD | JOB_OBJECT_UILIMIT_WRITECLIPBOARD
                   | JOB_OBJECT_UILIMIT_SYSTEMPARAMETERS | JOB_OBJECT_UILIMIT_DISPLAYSETTINGS
                   | JOB_OBJECT_UILIMIT_GLOBALATOMS | JOB_OBJECT_UILIMIT_DESKTOP | JOB_OBJECT_UILIMIT_EXITWINDOWS)
LIMIT_FLAGS = (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_PROCESS_MEMORY
               | JOB_OBJECT_LIMIT_ACTIVE_PROCESS | JOB_OBJECT_LIMIT_PRIORITY_CLASS)
CREATION_FLAGS = CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT
ROOT_JOB = "AppFactory-afd"
DEFAULT_USER = "afrunner"
UNAVAILABLE_REASON = ("S1h indisponível na Fase 2.2: PoC de logon secundário + Job Object não aprovada (KI-0014), "
                      "usuário/ACL não configurados (KI-0016) e Job Object raiz inexistente (KI-0019)")


@dataclass(frozen=True)
class S1hLaunchSpec:
    user: str
    credential_ref: str
    logon_flags: int
    creation_flags: int
    parent_job: str
    limit_flags: int
    job_memory_bytes: int
    process_memory_bytes: int
    active_processes: int
    cpu_control_flags: int
    cpu_rate: int                # centésimos de % (5000 = 50%)
    priority_class: int
    ui_restrictions: int
    env: dict
    cwd: str
    writable_dirs: tuple[str, ...]   # Allow Modify explícito (aplicado pelo daemon na 2.6)
    timeout_s: int
    network_isolated: bool = False   # KI-0015: S1h NÃO isola rede

    def validate(self) -> None:
        if self.logon_flags & LOGON_NETCREDENTIALS_ONLY:
            raise ValueError("LOGON_NETCREDENTIALS_ONLY é proibido (executaria como o usuário principal)")
        if self.limit_flags & (JOB_OBJECT_LIMIT_BREAKAWAY_OK | JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK):
            raise ValueError("breakaway do Job Object é proibido")
        if not self.limit_flags & JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE:
            raise ValueError("KILL_ON_JOB_CLOSE é obrigatório")
        if not self.creation_flags & CREATE_SUSPENDED:
            raise ValueError("o processo deve ser criado suspenso")
        if (self.ui_restrictions & (JOB_OBJECT_UILIMIT_READCLIPBOARD | JOB_OBJECT_UILIMIT_WRITECLIPBOARD)) != \
                (JOB_OBJECT_UILIMIT_READCLIPBOARD | JOB_OBJECT_UILIMIT_WRITECLIPBOARD):
            raise ValueError("área de transferência deve estar bloqueada")
        forbidden = {k for k in self.env if k.upper() not in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG")}
        if forbidden:
            raise ValueError(f"variáveis fora da allowlist no ambiente do S1h: {sorted(forbidden)}")


def s1h_launch_spec(mode: str, battery: bool, tmp_dir: str | os.PathLike, worktree: str | os.PathLike,
                    timeout_s: int = 600, path_entries: tuple[str, ...] = (), user: str = DEFAULT_USER) -> S1hLaunchSpec:
    lim: Limits = limits_for(mode, timeout_s, battery=battery)
    spec = S1hLaunchSpec(
        user=user, credential_ref=f"secret://sandbox/{user}", logon_flags=0, creation_flags=CREATION_FLAGS,
        parent_job=ROOT_JOB, limit_flags=LIMIT_FLAGS, job_memory_bytes=lim.memory_bytes,
        process_memory_bytes=lim.memory_bytes, active_processes=lim.max_processes,
        cpu_control_flags=JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP,
        cpu_rate=lim.cpu_rate_pct * 100,
        priority_class=IDLE_PRIORITY_CLASS if lim.priority == "IDLE" else BELOW_NORMAL_PRIORITY_CLASS,
        ui_restrictions=UI_RESTRICTIONS, env=clean_env("S1h", tmp_dir, path_entries), cwd=os.fspath(worktree),
        writable_dirs=(os.fspath(Path(worktree)), os.fspath(Path(tmp_dir))), timeout_s=lim.timeout_s)
    spec.validate()
    return spec


class S1hSandbox:
    kind = "S1h"

    def available(self) -> tuple[bool, str]:
        return False, UNAVAILABLE_REASON

    def run(self, argv, cwd, env, limits, cancel):  # noqa: ARG002 - contrato 12 §6
        raise SandboxUnavailable(UNAVAILABLE_REASON)
