"""Verificador de diff de caminhos protegidos (08 §5.3 camada 3; 09 §2 passo 4; D-0029, D-0053).

Executa somente o `git` confiável, sem shell, sem diff externo nem textconv, e nunca executa código do
candidato. Qualquer caminho protegido adicionado, alterado, renomeado, copiado, removido ou com tipo
alterado, qualquer symlink/gitlink e qualquer `[tool.pytest` no pyproject.toml => rejeição.
Erro do git => rejeição (falha fechada).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass

from appfactory.security.paths import ProtectedPaths, classify_repo

GIT_TIMEOUT_S = 60
_REV_RE = re.compile(r"^[A-Za-z0-9_./@^~{}:+-]{1,200}$")
_PYTEST_CFG = re.compile(r"^\s*\[\[?\s*tool\s*\.\s*pytest", re.MULTILINE)
SYMLINK_MODE = "120000"
GITLINK_MODE = "160000"


class GitError(RuntimeError):
    pass


def git_executable() -> str:
    exe = shutil.which("git")
    if not exe:
        raise GitError("git não encontrado no PATH")
    return exe


def run_git(args: list[str], cwd: str | os.PathLike, timeout: int = GIT_TIMEOUT_S, binary: bool = False):
    """Executa o git confiável: lista de argumentos (sem shell), sem prompt, sem fsmonitor."""
    cmd = [git_executable(), "-c", "core.quotepath=off", "-c", "core.fsmonitor=false", *args]
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    try:
        proc = subprocess.run(cmd, cwd=os.fspath(cwd), capture_output=True, timeout=timeout, env=env,
                              stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(f"falha ao executar git: {exc}") from exc
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args[:3])} falhou ({proc.returncode}): "
                       f"{proc.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return proc.stdout if binary else proc.stdout.decode("utf-8", "surrogateescape")


@dataclass(frozen=True)
class DiffEntry:
    status: str
    path: str
    old_path: str | None
    old_mode: str
    new_mode: str
    new_sha: str = ""


@dataclass(frozen=True)
class Violation:
    path: str
    status: str
    rule: str
    detail: str


@dataclass(frozen=True)
class DiffVerdict:
    ok: bool
    base: str
    head: str
    repo_kind: str
    entries: tuple[DiffEntry, ...] = ()
    violations: tuple[Violation, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict:
        return {"ok": self.ok, "base": self.base, "head": self.head, "repo_kind": self.repo_kind,
                "error": self.error,
                "entries": [e.__dict__ for e in self.entries],
                "violations": [v.__dict__ for v in self.violations]}


def parse_raw_z(out: str) -> list[DiffEntry]:
    """Interpreta `git diff --raw -z`: ':<om> <nm> <osha> <nsha> <status>\\0<path>[\\0<path2>]\\0'."""
    tokens = out.split("\0")
    entries: list[DiffEntry] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok:
            i += 1
            continue
        if not tok.startswith(":"):
            raise GitError(f"saída inesperada do git diff: {tok[:80]!r}")
        fields = tok[1:].split()
        if len(fields) < 5:
            raise GitError(f"cabeçalho inesperado do git diff: {tok[:80]!r}")
        old_mode, new_mode, _old_sha, new_sha, status = fields[:5]
        letter = status[0]
        if letter in ("R", "C"):
            if i + 2 >= len(tokens):
                raise GitError("saída truncada do git diff (renomeação/cópia)")
            entries.append(DiffEntry(letter, tokens[i + 2], tokens[i + 1], old_mode, new_mode, new_sha))
            i += 3
        else:
            if i + 1 >= len(tokens):
                raise GitError("saída truncada do git diff")
            entries.append(DiffEntry(letter, tokens[i + 1], None, old_mode, new_mode, new_sha))
            i += 2
    return entries


def _check_rev(rev: str) -> None:
    if not isinstance(rev, str) or not _REV_RE.match(rev) or rev.startswith("-"):
        raise GitError(f"revisão inválida: {rev!r}")


def check_diff(repo: str | os.PathLike, base: str, head: str, protected: ProtectedPaths,
               factory_root: str | os.PathLike) -> DiffVerdict:
    """Verifica `git diff <base>...<head>` no repositório. O tipo de repositório vem de `classify_repo`
    (código confiável, D-0053); nunca de parâmetro do chamador."""
    kind = classify_repo(repo, factory_root)
    try:
        _check_rev(base)
        _check_rev(head)
        out = run_git(["diff", "--raw", "-z", "--no-abbrev", "--find-renames", "--find-copies",
                       "--no-ext-diff", "--no-textconv", "--no-color", f"{base}...{head}", "--"], cwd=repo)
        entries = parse_raw_z(out)
    except GitError as exc:
        return DiffVerdict(False, str(base), str(head), kind, error=str(exc))
    violations: list[Violation] = []
    for e in entries:
        for side in (e.path, e.old_path):
            if side is None:
                continue
            hit = protected.match(side, kind)
            if hit:
                rule = ("protected:" if kind == "factory" else "project_protected:") + hit
                violations.append(Violation(side, e.status, rule, f"{e.status} em caminho protegido ({hit})"))
        if SYMLINK_MODE in (e.old_mode, e.new_mode):
            violations.append(Violation(e.path, e.status, "symlink", "symlink no diff é rejeitado"))
        if GITLINK_MODE in (e.old_mode, e.new_mode):
            violations.append(Violation(e.path, e.status, "gitlink", "submódulo/gitlink no diff é rejeitado"))
        if e.status not in ("A", "M", "D", "R", "C", "T"):
            violations.append(Violation(e.path, e.status, "unknown_status", f"status desconhecido {e.status!r}"))
        if kind == "factory" and e.path.casefold() == "pyproject.toml" and e.status != "D":
            try:
                text = run_git(["cat-file", "-p", e.new_sha], cwd=repo)
            except GitError as exc:
                return DiffVerdict(False, base, head, kind, tuple(entries), tuple(violations), error=str(exc))
            if _PYTEST_CFG.search(text):
                violations.append(Violation(e.path, e.status, "pytest_config",
                                            "[tool.pytest*] é proibido no pyproject.toml (08 §5.1)"))
    return DiffVerdict(not violations, base, head, kind, tuple(entries), tuple(violations))


def enforce_verdict(manager, attempt_id: str, verdict: DiffVerdict) -> None:
    """Diff rejeitado bloqueia a task na PRIMEIRA ocorrência (08 §5.3): evento `security.violation`,
    auditoria e `BLOCKED(policy_violation)`. Lança StepHeld para o executor parar sem novas escritas."""
    if verdict.ok:
        return
    from appfactory.jobs.handlers import StepHeld

    detail = verdict.error or "; ".join(f"{v.rule}:{v.path}" for v in verdict.violations[:10])
    manager.record_violation(attempt_id, "diff_rejected", detail, audit_type="diff.rejected",
                             payload=verdict.to_dict())
    manager.hold_attempt(attempt_id, "BLOCKED", f"policy_violation: diff rejeitado ({detail[:200]})")
    raise StepHeld("policy_violation: diff rejeitado")
