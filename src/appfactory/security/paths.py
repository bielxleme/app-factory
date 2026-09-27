"""Política de caminhos e de arquivos (08 §4.1 S0, §5, §6; 04 §3; D-0049, D-0051, D-0052, D-0053).

* `load_policy_file`: arquivos `.yaml` da fábrica são escritos no subconjunto JSON do YAML 1.2 e lidos com
  `json`; qualquer outra sintaxe é recusada (falha fechada, D-0049).
* `ProtectedPaths`: lista de 08 §5.1 carregada de `config/policies/protected-paths.yaml` (ela mesma protegida).
* `normalize_rel`: recusa `..`, fluxos NTFS, nomes de dispositivo, UNC, nomes terminados em ponto/espaço.
* `check_access`: decide leitura/criação/escrita/remoção/renomeação por área; padrão = NEGAR.
* `classify_repo`: tipo de repositório decidido por código confiável; na dúvida, "factory" (D-0053).
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

PROTECTED_PATHS_FILE = "config/policies/protected-paths.yaml"

RepoKind = Literal["factory", "project"]

_DEVICE_NAMES = {"con", "prn", "aux", "nul", "conin$", "conout$",
                 *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10)),
                 "com¹", "com²", "com³", "lpt¹", "lpt²", "lpt³"}
_CTRL = re.compile(r"[\x00-\x1f]")


class PolicyFileError(ValueError):
    """Arquivo de política ausente, ilegível ou fora do subconjunto JSON (falha fechada)."""


class PathRejected(ValueError):
    """Caminho malformado ou perigoso (.., fluxo NTFS, dispositivo, UNC, fora da base)."""


class Op(str, Enum):
    READ = "read"
    CREATE = "create"
    WRITE = "write"
    DELETE = "delete"
    RENAME = "rename"


WRITE_OPS = (Op.CREATE, Op.WRITE, Op.DELETE, Op.RENAME)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    op: Op
    path: str
    rule: str
    reason: str

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "op": self.op.value, "path": self.path, "rule": self.rule,
                "reason": self.reason}


# ---------------------------------------------------------------------------------------------- arquivos
def _reject_constant(value: str):
    raise PolicyFileError(f"constante não permitida em arquivo de política: {value}")


def _no_duplicates(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise PolicyFileError(f"chave duplicada em arquivo de política: {k!r}")
        out[k] = v
    return out


def load_policy_file(path: str | os.PathLike) -> dict:
    """Lê um arquivo de política `.yaml` escrito no subconjunto JSON (D-0049). Qualquer outra sintaxe,
    chave duplicada, NaN/Infinity ou raiz que não seja objeto => PolicyFileError."""
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError as exc:
        raise PolicyFileError(f"arquivo de política ilegível: {p} ({exc})") from exc
    try:
        text = raw.decode("utf-8")
        data = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except PolicyFileError:
        raise
    except (UnicodeDecodeError, ValueError) as exc:
        raise PolicyFileError(f"{p}: fora do subconjunto JSON exigido por D-0049 ({exc})") from exc
    if not isinstance(data, dict):
        raise PolicyFileError(f"{p}: a raiz deve ser um objeto JSON")
    return data


# ---------------------------------------------------------------------------------------------- padrões
def _segments(rel: str) -> list[str]:
    return [s for s in rel.replace("\\", "/").split("/") if s not in ("", ".")]


def match_pattern(pattern: str, rel_path: str) -> bool:
    """Casa um padrão ancorado na raiz. `**` = zero ou mais segmentos; `dir/**` também casa `dir`.
    Comparação sem diferenciar maiúsculas/minúsculas (Windows)."""
    pat = [s.casefold() for s in _segments(pattern)]
    path = [s.casefold() for s in _segments(rel_path)]

    def rec(i: int, j: int) -> bool:
        while i < len(pat):
            if pat[i] == "**":
                if i == len(pat) - 1:
                    return True
                return any(rec(i + 1, k) for k in range(j, len(path) + 1))
            if j >= len(path) or not fnmatch.fnmatchcase(path[j], pat[i]):
                return False
            i, j = i + 1, j + 1
        return j == len(path)

    return rec(0, 0)


@dataclass(frozen=True)
class ProtectedPaths:
    factory: tuple[str, ...]
    project: tuple[str, ...] = (".git/**", ".appfactory/**")
    credentials: tuple[str, ...] = ()
    credential_exceptions: tuple[str, ...] = ()
    source: str = "<memória>"

    @property
    def patterns(self) -> tuple[str, ...]:
        return self.factory

    @classmethod
    def load(cls, root: str | os.PathLike) -> "ProtectedPaths":
        """Carrega a lista protegida da fábrica. Ausente/inválida => PolicyFileError (falha fechada)."""
        path = Path(root) / PROTECTED_PATHS_FILE
        data = load_policy_file(path)

        def patterns(key: str, required: bool = True) -> tuple[str, ...]:
            value = data.get(key)
            if value is None and not required:
                return ()
            if not isinstance(value, list) or (required and not value) or \
                    not all(isinstance(x, str) and x.strip() for x in value):
                raise PolicyFileError(f"{path}: '{key}' deve ser lista não vazia de padrões")
            return tuple(x.strip() for x in value)

        pp = cls(factory=patterns("factory"), project=patterns("project"),
                 credentials=patterns("credentials", required=False),
                 credential_exceptions=patterns("credential_exceptions", required=False), source=str(path))
        if pp.match(PROTECTED_PATHS_FILE) is None:
            raise PolicyFileError(f"{path}: a lista protegida deve proteger a si mesma")
        return pp

    def match(self, rel_path: str, repo_kind: RepoKind = "factory") -> str | None:
        """Padrão protegido que casou (ou None). Em projetos gerados valem só as regras de projeto (D-0053)."""
        for pat in (self.factory if repo_kind == "factory" else self.project):
            if match_pattern(pat, rel_path):
                return pat
        return None

    def is_credential(self, rel_path: str) -> str | None:
        if any(match_pattern(p, rel_path) for p in self.credential_exceptions):
            return None
        for pat in self.credentials:
            if match_pattern(pat, rel_path):
                return pat
        return None


# ---------------------------------------------------------------------------------------------- normalização
def _check_component(comp: str, raw: str) -> None:
    if comp == "..":
        raise PathRejected(f"'..' não é permitido: {raw!r}")
    if _CTRL.search(comp):
        raise PathRejected(f"caractere de controle no caminho: {raw!r}")
    if ":" in comp:
        raise PathRejected(f"':' (fluxo alternativo NTFS/unidade) não é permitido: {raw!r}")
    if comp.endswith((".", " ")) and comp not in (".",):
        raise PathRejected(f"nome terminado em ponto ou espaço não é permitido: {raw!r}")
    if any(ch in comp for ch in '<>"|?*'):
        raise PathRejected(f"caractere reservado do Windows no caminho: {raw!r}")
    stem = comp.split(".")[0].strip().casefold()
    if stem in _DEVICE_NAMES:
        raise PathRejected(f"nome de dispositivo do Windows não é permitido: {raw!r}")


def _norm(p: str | os.PathLike) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(p)))


def _is_within(child: str | os.PathLike, parent: str | os.PathLike) -> bool:
    c, p = _norm(child), _norm(parent)
    return c == p or c.startswith(p.rstrip(os.sep) + os.sep)


def _rel_under(child: str | os.PathLike, parent: str | os.PathLike) -> str:
    c, p = os.path.normpath(os.fspath(child)), os.path.normpath(os.fspath(parent))
    return Path(os.path.relpath(c, p)).as_posix() if _norm(c) != _norm(p) else ""


def normalize_rel(path: str | os.PathLike, base: str | os.PathLike) -> str:
    """Caminho relativo à `base`, separador '/', sem '.'/'..'. Absoluto só se estiver dentro da base.
    Recusa UNC, prefixos de dispositivo, fluxos NTFS, nomes reservados e nomes terminados em ponto/espaço."""
    raw = os.fspath(path)
    if not isinstance(raw, str) or not raw.strip():
        raise PathRejected("caminho vazio")
    s = raw.replace("\\", "/")
    if s.startswith("//"):
        raise PathRejected(f"caminho UNC/dispositivo não é permitido: {raw!r}")
    drive = re.match(r"^[A-Za-z]:", s)
    absolute = s.startswith("/") or bool(drive)
    if drive and not s[2:3] == "/":
        raise PathRejected(f"caminho relativo a unidade não é permitido: {raw!r}")
    body = s[2:] if drive else s
    comps = [c for c in body.split("/") if c not in ("", ".")]
    for c in comps:
        _check_component(c, raw)
    if not absolute:
        return "/".join(comps)
    full = os.path.normpath(raw)
    if not _is_within(full, base):
        raise PathRejected(f"caminho fora da base: {raw!r}")
    return _rel_under(full, base)


# ---------------------------------------------------------------------------------------------- escopo
@dataclass(frozen=True)
class PathScope:
    factory_root: Path
    job_id: str
    attempt_id: str
    worktree: Path | None
    integration_worktree: Path | None = None
    reads: tuple[str, ...] = ("**",)
    writes: tuple[str, ...] = ()
    repo_kind: RepoKind = "factory"   # D-0053: preenchido por make_scope/classify_repo, nunca pela TaskSpec
    job_dir: Path | None = field(default=None)

    @property
    def jobs_root(self) -> Path:
        return Path(self.factory_root) / ".appfactory" / "jobs"

    def own_job_dir(self) -> Path:
        return self.job_dir or (self.jobs_root / self.job_id)


def make_scope(factory_root: str | os.PathLike, job_id: str, attempt_id: str,
               worktree: str | os.PathLike | None, *, reads=("**",), writes=(),
               integration_worktree: str | os.PathLike | None = None,
               declared_repo_kind: str | None = None) -> PathScope:
    """Monta o escopo com o tipo de repositório determinado por código confiável (D-0053).
    `declared_repo_kind` (vindo de TaskSpec/agente) é IGNORADO de propósito."""
    from appfactory.jobs import locks

    del declared_repo_kind  # nunca é fonte de decisão (D-0053)
    root = Path(factory_root).resolve()
    wt = Path(worktree).resolve() if worktree else None
    kind: RepoKind = classify_repo(wt, root) if wt else "factory"
    norm_writes = tuple(locks.normalize_spec(w) for w in writes)
    return PathScope(factory_root=root, job_id=job_id, attempt_id=attempt_id, worktree=wt,
                     integration_worktree=Path(integration_worktree).resolve() if integration_worktree else None,
                     reads=tuple(reads) or ("**",), writes=norm_writes, repo_kind=kind)


def classify_repo(repo: str | os.PathLike, factory_root: str | os.PathLike) -> RepoKind:
    """Tipo do repositório determinado por código confiável (D-0053).

    * diretório `.git` comum igual ao da fábrica (inclui worktrees `evo/*`) => "factory";
    * dentro da raiz da fábrica e fora de `workspaces/` => "factory";
    * branch `evo/*` => "factory";
    * qualquer erro ou dúvida => "factory" (falha fechada).
    """
    try:
        repo_p = Path(repo).resolve()
        root = Path(factory_root).resolve()
    except (OSError, RuntimeError):
        return "factory"
    if _is_within(repo_p, root) and not _is_within(repo_p, root / "workspaces"):
        return "factory"
    try:
        from appfactory.security.diff_guard import run_git

        common = run_git(["rev-parse", "--git-common-dir"], cwd=repo_p).strip()
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_p).strip()
        top = run_git(["rev-parse", "--show-toplevel"], cwd=repo_p).strip()
    except Exception:  # noqa: BLE001 - GitError, OSError, timeout: na dúvida, fábrica
        return "factory"
    if not common or not top:
        return "factory"
    common_p = Path(common) if os.path.isabs(common) else (repo_p / common)
    try:
        common_real = common_p.resolve()
        top_real = Path(top).resolve()
    except (OSError, RuntimeError):
        return "factory"
    if _norm(common_real) == _norm((root / ".git").resolve()):
        return "factory"
    if branch.startswith("evo/"):
        return "factory"
    if not _is_within(top_real, root / "workspaces"):
        # repositório fora da área de projetos gerados: não há como provar que é projeto => fábrica
        return "factory"
    if _norm(top_real) != _norm(repo_p) and not _is_within(repo_p, top_real):
        return "factory"
    return "project"


# ---------------------------------------------------------------------------------------------- decisão
def _deny(op: Op, path: str, rule: str, reason: str) -> Decision:
    return Decision(False, op, path, rule, reason)


def _covered_by_writes(rel: str, writes: tuple[str, ...]) -> bool:
    r = rel.casefold()
    for spec in writes:
        s = spec.casefold()
        if s.endswith("/**"):
            prefix = s[:-3]
            if r.startswith(prefix + "/"):
                return True
        elif r == s:
            return True
    return False


def _hardlinked(p: str) -> bool:
    try:
        st = os.lstat(p)
    except OSError:
        return False
    return not os.path.isdir(p) and st.st_nlink > 1


def _win_long_path_name(path: str) -> str:
    """GetLongPathNameW: converte cada componente EXISTENTE para o nome longo, sem seguir symlinks/junctions."""
    import ctypes
    from ctypes import wintypes

    fn = ctypes.windll.kernel32.GetLongPathNameW
    fn.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    fn.restype = wintypes.DWORD
    size = fn(path, None, 0)
    if size == 0:
        raise PathRejected(f"não foi possível resolver nomes curtos 8.3 com segurança: {path!r}")
    buf = ctypes.create_unicode_buffer(size)
    n = fn(path, buf, size)
    if n == 0 or n >= size or not buf.value:
        raise PathRejected(f"não foi possível resolver nomes curtos 8.3 com segurança: {path!r}")
    return buf.value


def _expand_short_names(path: str) -> str:
    """Windows: expande nomes curtos 8.3 (ex.: `WORKSP~1`) do caminho LITERAL para os nomes longos canônicos.

    * Só a maior parte EXISTENTE do caminho é expandida (componentes inexistentes não podem ser apelidos 8.3:
      a própria verificação de existência do Windows já resolve nomes curtos).
    * Não segue symlinks/junctions: o destino real continua sendo verificado à parte (candidato resolvido).
    * Qualquer falha na resolução => PathRejected (falha fechada); nunca vira permissão.
    Fora do Windows, ou sem `~` no caminho, devolve o caminho inalterado."""
    if sys.platform != "win32" or "~" not in path:
        return path
    head, tail = os.path.normpath(path), []
    while not os.path.lexists(head):
        parent, name = os.path.split(head)
        if not name or parent == head:
            raise PathRejected(f"não foi possível resolver nomes curtos 8.3 com segurança: {path!r}")
        tail.append(name)
        head = parent
    long_head = os.path.normpath(_win_long_path_name(head))
    if _norm(os.path.realpath(long_head)) != _norm(os.path.realpath(head)):
        raise PathRejected(f"resolução de nome curto 8.3 inconsistente: {path!r}")
    return os.path.join(long_head, *reversed(tail)) if tail else long_head


def _candidates(path: str | os.PathLike, scope: PathScope) -> tuple[str, list[str]]:
    raw = os.fspath(path)
    s = raw.replace("\\", "/")
    is_abs = s.startswith("/") or bool(re.match(r"^[A-Za-z]:/", s)) or s.startswith("//")
    if not is_abs:
        if scope.worktree is None:
            raise PathRejected("caminho relativo sem worktree no escopo")
        rel = normalize_rel(raw, scope.worktree)
        literal = os.path.normpath(os.path.join(os.fspath(scope.worktree), *rel.split("/"))) if rel else \
            os.path.normpath(os.fspath(scope.worktree))
    else:
        if s.startswith("//"):
            raise PathRejected(f"caminho UNC/dispositivo não é permitido: {raw!r}")
        # valida componentes (sem .., ADS, dispositivos) antes de qualquer resolução
        drive = re.match(r"^[A-Za-z]:", s)
        for c in [c for c in (s[2:] if drive else s).split("/") if c not in ("", ".")]:
            _check_component(c, raw)
        literal = os.path.normpath(raw)
    # Nomes curtos 8.3 são apelidos do MESMO arquivo (não são links): o caminho literal é comparado já na forma
    # longa canônica; symlinks/junctions continuam sendo verificados pelo candidato resolvido abaixo.
    literal = _expand_short_names(literal)
    resolved = os.path.realpath(literal)
    return literal, [literal] if _norm(resolved) == _norm(literal) else [literal, resolved]


def _base_for(p: str, base: str | os.PathLike | None) -> str | None:
    """Forma da base (literal ou resolvida — ex.: nomes curtos 8.3 no Windows) que contém `p`."""
    if base is None:
        return None
    for form in (os.path.normpath(os.fspath(base)), os.path.realpath(os.fspath(base))):
        if _is_within(p, form):
            return form
    return None


def _decide_one(op: Op, p: str, scope: PathScope, protected: ProtectedPaths) -> Decision:
    # 1) worktree da task (mais específico primeiro)
    wt = _base_for(p, scope.worktree)
    if wt is not None:
        rel = _rel_under(p, wt)
        cred = protected.is_credential(rel)
        if cred:
            return _deny(op, rel, "credential", f"credencial ({cred}): nenhum acesso")
        if op is Op.READ:
            if any(match_pattern(r, rel) for r in scope.reads) or rel == "":
                return Decision(True, op, rel, "reads", "leitura dentro do worktree")
            return _deny(op, rel, "reads", "fora do conjunto 'reads' da task")
        hit = protected.match(rel, scope.repo_kind)
        if hit:
            label = "protected" if scope.repo_kind == "factory" else "project_protected"
            return _deny(op, rel, f"{label}:{hit}", f"caminho protegido ({scope.repo_kind}): {hit}")
        if not _covered_by_writes(rel, scope.writes):
            return _deny(op, rel, "writes", "fora do conjunto 'writes' da task (04 §3)")
        if op is not Op.CREATE and _hardlinked(p):
            return _deny(op, rel, "hardlink", "arquivo com mais de um vínculo (hardlink) não pode ser alterado")
        return Decision(True, op, rel, "writes", "dentro do 'writes' da task")
    # 2) worktree de integração: somente leitura
    iw = _base_for(p, scope.integration_worktree)
    if iw is not None:
        rel = _rel_under(p, iw)
        if protected.is_credential(rel):
            return _deny(op, rel, "credential", "credencial: nenhum acesso")
        if op is Op.READ:
            return Decision(True, op, rel, "integration_read", "worktree de integração: somente leitura")
        return _deny(op, rel, "integration_readonly", "worktree de integração é somente leitura")
    # 3) diretório do próprio job
    job_dir = _base_for(p, scope.own_job_dir())
    if job_dir is not None:
        sub = _rel_under(p, job_dir)
        tmp_prefix = f"tmp/{scope.attempt_id}".casefold()
        s = sub.casefold()
        in_tmp = s == tmp_prefix or s.startswith(tmp_prefix + "/")
        if protected.is_credential(sub):
            return _deny(op, sub, "credential", "credencial: nenhum acesso")
        if s == "quarantine" or s.startswith("quarantine/"):
            return _deny(op, sub, "quarantine", "quarentena: só o componente de navegador (fora da 2.2)")
        if op is Op.READ:
            return Decision(True, op, sub, "job_dir", "leitura do diretório do próprio job")
        if op in (Op.CREATE, Op.WRITE):
            if in_tmp or s.startswith("artifacts/") or s.startswith("research/"):
                if op is Op.WRITE and _hardlinked(p):
                    return _deny(op, sub, "hardlink", "hardlink não pode ser alterado")
                return Decision(True, op, sub, "job_dir_write", "área gravável do job")
            return _deny(op, sub, "job_dir", "área do job não gravável")
        if in_tmp and s != tmp_prefix:
            return Decision(True, op, sub, "job_tmp", "temporário da própria tentativa (08 §6)")
        return _deny(op, sub, "job_dir_delete", "remoção só no tmp da própria tentativa (08 §6)")
    # 4) resto da fábrica (estado operacional, outros jobs, código)
    root = _base_for(p, scope.factory_root)
    if root is not None:
        rel = _rel_under(p, root)
        if rel.casefold().startswith(".appfactory"):
            return _deny(op, rel, "operational_state", "estado operacional da fábrica: nenhum acesso")
        if protected.is_credential(rel):
            return _deny(op, rel, "credential", "credencial: nenhum acesso")
        return _deny(op, rel, "outside_scope", "fora do escopo da task")
    return _deny(op, os.fspath(p), "outside_root", "fora da raiz da fábrica (R2/R3 exigem aprovação)")


def check_access(op: Op | str, path: str | os.PathLike, scope: PathScope, protected: ProtectedPaths,
                 dest: str | os.PathLike | None = None) -> Decision:
    """Decide uma operação de arquivo. O caminho literal E o resolvido (symlink/junction) precisam ser
    permitidos. Renomear exige origem e destino permitidos como escrita. Padrão = negar."""
    op = Op(op)
    try:
        _, cands = _candidates(path, scope)
    except PathRejected as exc:
        return _deny(op, os.fspath(path), "malformed", str(exc))
    decision = None
    for c in cands:
        decision = _decide_one(op, c, scope, protected)
        if not decision.allowed:
            if c is not cands[0]:
                return _deny(op, decision.path, "link_target:" + decision.rule,
                             "o destino real (symlink/junction) é negado: " + decision.reason)
            return decision
    if op is Op.RENAME:
        if dest is None:
            return _deny(op, os.fspath(path), "malformed", "renomear exige destino")
        d2 = check_access(Op.CREATE, dest, scope, protected)
        if not d2.allowed:
            return _deny(op, d2.path, "rename_dest:" + d2.rule, d2.reason)
    return decision  # type: ignore[return-value]
