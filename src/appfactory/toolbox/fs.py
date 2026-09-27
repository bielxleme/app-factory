"""Operações de arquivo guardadas (08 §4.1 S0, §5.3 camada 1, §6; 04 §3). Toda operação passa por
`security.paths.check_access` ANTES de tocar o disco; negação => AccessDenied (+ violação registrada quando há
contexto de job). Escrita atômica (tmp + rename). Não existe operação de symlink/hardlink."""
from __future__ import annotations

import os
import uuid

from appfactory.security.paths import Op, PathScope, ProtectedPaths, check_access
from appfactory.toolbox import AccessDenied, report_violation


def _guard(scope: PathScope, protected: ProtectedPaths, op: Op, path, dest=None, ctx=None):
    decision = check_access(op, path, scope, protected, dest=dest)
    if not decision.allowed:
        report_violation(ctx, decision.rule, f"{op.value} {decision.path}: {decision.reason}")
        raise AccessDenied(decision)
    return decision


def _abs(scope: PathScope, path) -> str:
    p = os.fspath(path)
    return p if os.path.isabs(p) else os.path.join(os.fspath(scope.worktree), p)


def fs_read(scope: PathScope, protected: ProtectedPaths, path, *, ctx=None) -> bytes:
    _guard(scope, protected, Op.READ, path, ctx=ctx)
    with open(os.path.realpath(_abs(scope, path)), "rb") as fh:
        return fh.read()


def fs_write(scope: PathScope, protected: ProtectedPaths, path, data: bytes, *, ctx=None) -> None:
    target = _abs(scope, path)
    op = Op.WRITE if os.path.lexists(target) else Op.CREATE
    _guard(scope, protected, op, path, ctx=ctx)
    real = os.path.realpath(target)
    os.makedirs(os.path.dirname(real), exist_ok=True)
    tmp = os.path.join(os.path.dirname(real), f".af-tmp-{uuid.uuid4().hex}")
    try:
        with open(tmp, "xb") as fh:
            fh.write(bytes(data))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, real)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def fs_delete(scope: PathScope, protected: ProtectedPaths, path, *, ctx=None) -> None:
    _guard(scope, protected, Op.DELETE, path, ctx=ctx)
    target = _abs(scope, path)
    if os.path.isdir(target) and not os.path.islink(target):
        os.rmdir(target)   # só diretório vazio; nada de remoção recursiva
    else:
        os.remove(target)


def fs_rename(scope: PathScope, protected: ProtectedPaths, src, dst, *, ctx=None) -> None:
    _guard(scope, protected, Op.RENAME, src, dest=dst, ctx=ctx)
    real_dst = os.path.realpath(_abs(scope, dst))
    if os.path.lexists(real_dst):
        raise AccessDenied(message=f"destino já existe: {dst}")
    os.makedirs(os.path.dirname(real_dst), exist_ok=True)
    os.rename(os.path.realpath(_abs(scope, src)), real_dst)
