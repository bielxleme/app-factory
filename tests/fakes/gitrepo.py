"""Repositórios git temporários para testes (sem alterar a configuração global do usuário)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

GIT = shutil.which("git")
_CFG = ["-c", "user.name=AF Test", "-c", "user.email=af-test@example.invalid", "-c", "commit.gpgsign=false",
        "-c", "core.autocrlf=false", "-c", "init.defaultBranch=main", "-c", "core.hooksPath=",
        "-c", "core.symlinks=false"]


def git(repo, *args, check=True) -> str:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    proc = subprocess.run([GIT, *_CFG, *args], cwd=str(repo), capture_output=True, text=True, env=env,
                          stdin=subprocess.DEVNULL, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr}")
    return proc.stdout


def init_repo(path) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    git(path, "checkout", "-q", "-b", "main")
    return path


def write(repo, rel: str, content: str = "x\n") -> None:
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8", newline="\n")


def commit_all(repo, msg: str = "c") -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", msg)
    return git(repo, "rev-parse", "HEAD").strip()


def add_symlink_entry(repo, rel: str, target: str = "config/policies") -> None:
    """Cria uma entrada 120000 (symlink) no índice sem criar symlink no disco (portável, sem privilégio)."""
    sha = subprocess.run([GIT, *_CFG, "hash-object", "-w", "--stdin"], cwd=str(repo), input=target,
                         capture_output=True, text=True, check=True).stdout.strip()
    git(repo, "update-index", "--add", "--cacheinfo", f"120000,{sha},{rel}")


def add_gitlink_entry(repo, rel: str) -> None:
    head = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "update-index", "--add", "--cacheinfo", f"160000,{head},{rel}")


def commit_index(repo, msg: str = "idx") -> str:
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD").strip()
