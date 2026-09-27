"""CommandPolicy (08 §3, §4.3, §7; 05 §6). Decide ANTES de qualquer execução: executável na allowlist,
argumentos, `cwd` no escopo, timeout obrigatório, sem shell, risco (R0–R3) e sandbox exigido.
Não executa nada. R2 sem pré-autorização e R3 são negados (não há aprovações na Fase 2.2)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from appfactory.security.paths import PathScope, _base_for, load_policy_file

COMMANDS_FILE = "config/policies/commands.yaml"
Risk = Literal["R0", "R1", "R2", "R3"]
KINDS = ("shell", "script", "tests", "build", "install")
ENV_ALLOWLIST = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "LANG")


@dataclass(frozen=True)
class CommandPolicyConfig:
    allow: frozenset[str]
    installers_s2_only: frozenset[str]
    shell_interpreters: frozenset[str]
    denied_executables: frozenset[str]
    git_allowed: frozenset[str]
    git_r3: frozenset[str]
    timeouts_max_s: dict
    preauthorized_r2: frozenset[str] = frozenset()

    @classmethod
    def load(cls, root: str | os.PathLike) -> "CommandPolicyConfig":
        data = load_policy_file(Path(root) / COMMANDS_FILE)

        def names(key: str) -> frozenset[str]:
            v = data.get(key, [])
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise ValueError(f"{COMMANDS_FILE}: '{key}' deve ser lista de nomes")
            return frozenset(x.casefold() for x in v)

        tmo = data.get("timeouts_max_s")
        if not isinstance(tmo, dict) or set(tmo) != set(KINDS) or \
                not all(isinstance(v, int) and v > 0 for v in tmo.values()):
            raise ValueError(f"{COMMANDS_FILE}: 'timeouts_max_s' deve definir {KINDS}")
        cfg = cls(allow=names("allow"), installers_s2_only=names("installers_s2_only"),
                  shell_interpreters=names("shell_interpreters"), denied_executables=names("denied_executables"),
                  git_allowed=names("git_allowed_subcommands"), git_r3=names("git_r3_subcommands"),
                  timeouts_max_s=dict(tmo), preauthorized_r2=names("preauthorized_r2"))
        if not cfg.allow or cfg.allow & cfg.shell_interpreters or cfg.allow & cfg.denied_executables:
            raise ValueError(f"{COMMANDS_FILE}: allowlist vazia ou em conflito com negações")
        return cfg


@dataclass(frozen=True)
class CommandRequest:
    argv: tuple[str, ...]
    cwd: Path
    timeout_s: int | None
    trust: Literal["trusted", "untrusted"] = "untrusted"
    kind: Literal["shell", "script", "tests", "build", "install"] = "script"
    flags: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CommandDecision:
    allowed: bool
    risk: Risk
    sandbox: Literal["S0", "S1h", "S2"] | None
    rule: str
    reason: str
    needs_human: bool = False
    kind: str = "script"

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _exe_name(arg0: str) -> str:
    name = arg0.casefold()
    for ext in (".exe", ".cmd", ".bat", ".ps1", ".com"):
        if name.endswith(ext):
            return name[: -len(ext)]
    return name


def _deny(rule: str, reason: str, risk: Risk = "R2", sandbox=None, needs_human=False, kind="script"):
    return CommandDecision(False, risk, sandbox, rule, reason, needs_human, kind)


def _npm(args: list[str]) -> tuple[str, Risk, str, str]:
    """(sandbox, risco, kind, regra) para npm (08 §4.3)."""
    sub = args[0].casefold() if args else ""
    flags = {a.casefold() for a in args[1:]}
    global_flag = bool({"-g", "--global", "--location=global"} & flags)
    if sub in ("install", "i", "add", "ci", "update", "up", "uninstall", "rm", "remove", "link") and global_flag:
        return "FORBIDDEN", "R3", "install", "global_install"
    if sub == "ci":
        if "--ignore-scripts" in flags:
            return "S1h", "R2", "install", "npm_ci_ignore_scripts"
        return "S2", "R2", "install", "install_with_scripts"
    if sub in ("install", "i", "add", "update", "up", "uninstall", "rm", "remove", "link", "rebuild"):
        return "S2", "R2", "install", "install_changes_lockfile"
    return "S1h", "R1", "script", "npm_script"


def _pip(args: list[str]) -> tuple[str, Risk, str, str]:
    sub = args[0].casefold() if args else ""
    rest = [a.casefold() for a in args[1:]]
    if sub != "install":
        return ("S1h", "R1", "script", "pip_readonly") if sub in ("list", "show", "freeze", "check", "--version") \
            else ("S2", "R2", "install", "pip_other")
    if "--user" in rest or any(a.startswith(("--prefix", "--root", "--target")) for a in rest) or "-t" in rest:
        return "FORBIDDEN", "R3", "install", "global_install"
    only_binary = "--only-binary=:all:" in rest or any(
        rest[i] == "--only-binary" and i + 1 < len(rest) and rest[i + 1] == ":all:" for i in range(len(rest)))
    hashes = "--require-hashes" in rest
    editable = "-e" in rest or "--editable" in rest or any(a.startswith("--editable=") for a in rest)
    positional, i, has_req = [], 0, False
    while i < len(rest):
        a = rest[i]
        if a in ("-r", "--requirement"):
            has_req = True
            i += 2
            continue
        if a.startswith("--requirement="):
            has_req = True
        elif a == "--only-binary":
            i += 2
            continue
        elif not a.startswith("-"):
            positional.append(a)
        i += 1
    if only_binary and hashes and has_req and not editable and not positional:
        return "S1h", "R2", "install", "pip_hashed_binary"
    return "S2", "R2", "install", "install_with_scripts"


def evaluate(req: CommandRequest, scope: PathScope, policy: CommandPolicyConfig) -> CommandDecision:
    """Decisão da CommandPolicy. Nunca executa. Padrão = negar."""
    argv = req.argv
    if isinstance(argv, (str, bytes)):
        return _deny("string_command", "comando deve ser lista de argumentos (sem shell)")
    if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(a, str) and a for a in argv):
        return _deny("malformed", "argv vazio ou inválido")
    if any("\0" in a for a in argv):
        return _deny("malformed", "NUL em argumento")
    kind = req.kind if req.kind in KINDS else "script"
    if req.timeout_s is None:
        return _deny("timeout_required", "timeout é obrigatório (08 §7)", kind=kind)
    if not isinstance(req.timeout_s, int) or req.timeout_s <= 0 or req.timeout_s > policy.timeouts_max_s[kind]:
        return _deny("timeout_exceeds", f"timeout fora do limite da classe {kind} "
                     f"(máx. {policy.timeouts_max_s[kind]} s, 05 §6)", kind=kind)
    if scope.worktree is None or _base_for(os.path.realpath(os.fspath(req.cwd)), scope.worktree) is None:
        return _deny("cwd_outside_scope", "cwd fora do worktree da task", kind=kind)
    arg0 = argv[0]
    if "/" in arg0 or "\\" in arg0 or ":" in arg0:
        return _deny("executable_path_not_allowed", "o executável deve ser um nome da allowlist, não um caminho")
    exe = _exe_name(arg0)
    args = list(argv[1:])
    if exe in policy.shell_interpreters:
        return _deny("shell_interpreter", f"interpretador de shell não é permitido ({exe})")
    if exe in policy.denied_executables:
        return _deny(f"denied:{exe}", f"comando sempre negado sem aprovação humana ({exe}, 08 §7)",
                     risk="R3", needs_human=True)
    if exe in policy.installers_s2_only:
        return _gate(req, policy, "S2", "R2", "install", "install_s2_only")
    if exe not in policy.allow:
        return _deny("not_allowlisted", f"executável fora da allowlist ({exe})")
    if exe == "git":
        if not args or args[0].startswith("-"):
            return _deny("git_global_option", "opções globais do git não são permitidas", risk="R3", needs_human=True)
        sub = args[0].casefold()
        lowered = [a.casefold() for a in args]
        if sub in policy.git_allowed and not (sub == "commit" and ("--no-verify" in lowered or "-n" in lowered)):
            risk: Risk = "R1" if sub in ("add", "commit") else "R0"
            return CommandDecision(True, risk, "S0", f"git_{sub}", "git confiável executado pelo Toolbox (S0)",
                                   False, kind)
        r3 = sub in policy.git_r3
        return _deny(f"git_subcommand:{sub}", f"git {sub} não é permitido" + (" sem [H]" if r3 else ""),
                     risk="R3" if r3 else "R2", needs_human=r3)
    if exe == "npm":
        sb, risk, k, rule = _npm(args)
    elif exe == "npx":
        sb, risk, k, rule = "S2", "R2", "install", "npx_download"          # P-10: padrão seguro
    elif exe == "uv":
        sub = args[0].casefold() if args else ""
        if sub in ("pip", "sync", "add", "remove", "lock", "run", "tool", "python", "venv", "export"):
            sb, risk, k, rule = "S2", "R2", "install", f"uv_{sub or 'x'}"   # P-10: padrão seguro
        else:
            sb, risk, k, rule = "S1h", "R1", kind, "uv_readonly"
    elif exe == "python":
        if len(args) >= 2 and args[0] == "-m" and args[1].casefold() == "pip":
            sb, risk, k, rule = _pip(args[2:])
        elif args and args[0].casefold().endswith("setup.py"):
            sb, risk, k, rule = "S2", "R2", "install", "setup_py"
        else:
            sb, risk, k, rule = "S1h", "R1", kind, "python_script"
    else:
        sb, risk, k, rule = "S1h", "R1", kind, f"{exe}_run"
    if sb == "FORBIDDEN":
        return _deny(rule, "instalação global / alteração do ambiente da máquina é proibida (08 §4.3)",
                     risk="R3", needs_human=True, kind="install")
    return _gate(req, policy, sb, risk, k, rule)


def _gate(req: CommandRequest, policy: CommandPolicyConfig, sandbox: str, risk: Risk, kind: str,
          rule: str) -> CommandDecision:
    if risk == "R2" and rule not in policy.preauthorized_r2:
        return CommandDecision(False, risk, sandbox, "approval_required",
                               f"{rule}: ação R2 exige pré-autorização/aprovação (inexistente na Fase 2.2)",
                               False, kind)
    if risk == "R3":
        return CommandDecision(False, risk, sandbox, rule, "R3 exige aprovação humana", True, kind)
    return CommandDecision(True, risk, sandbox, rule, "permitido pela política", False, kind)


def clean_env(sandbox: str, tmp_dir: str | os.PathLike, path_entries: list[str] | tuple[str, ...] = ()) -> dict:
    """Ambiente de processo filho a partir de uma allowlist (08 §2): nada do ambiente do usuário principal é
    herdado além de SYSTEMROOT (Windows). Tokens, chaves e segredos nunca entram."""
    del sandbox
    env = {"PATH": os.pathsep.join(str(p) for p in path_entries), "TEMP": os.fspath(tmp_dir),
           "TMP": os.fspath(tmp_dir), "LANG": "C.UTF-8"}
    if os.environ.get("SYSTEMROOT"):
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    if not set(env) <= set(ENV_ALLOWLIST):  # pragma: no cover - defesa em profundidade
        raise RuntimeError("variável fora da allowlist no ambiente do sandbox")
    return env
