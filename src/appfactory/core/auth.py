"""Papéis, tokens e matriz de autorização (08 §8; 12 §11; D-0027). Fase 2.2: somente em memória.

Não há API local nem arquivo de token nesta fase (API/daemon: 2.4; tokens em arquivo com ACL: 2.6).
Guardamos só o SHA-256 do token; a comparação usa `hmac.compare_digest`. Rotas desconhecidas são negadas.
Processos em S1h/S2 não recebem token (o ambiente do sandbox é uma allowlist sem tokens)."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    USER = "user"
    RUNNER = "runner"
    UI = "ui"


class AuthError(PermissionError):
    pass


@dataclass(frozen=True)
class Principal:
    role: Role
    attempt_id: str | None = None
    job_id: str | None = None
    expires_active_ms: int | None = None


class TokenRegistry:
    def __init__(self) -> None:
        self._by_hash: dict[str, Principal] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def mint(self, principal: Principal) -> str:
        if principal.role is Role.RUNNER and not (principal.attempt_id and principal.job_id
                                                   and principal.expires_active_ms):
            raise ValueError("token runner exige tentativa, job e expiração (lease)")
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._by_hash[self._digest(token)] = principal
        return token

    def verify(self, token: str, now_active_ms: int) -> Principal:
        if not isinstance(token, str) or not token:
            raise AuthError("token ausente")
        digest = self._digest(token)
        match = None
        with self._lock:
            for known, principal in self._by_hash.items():
                if hmac.compare_digest(known, digest):
                    match = principal
        if match is None:
            raise AuthError("token inválido")
        if match.expires_active_ms is not None and now_active_ms >= match.expires_active_ms:
            raise AuthError("token expirado")
        return match

    def revoke_attempt(self, attempt_id: str) -> int:
        with self._lock:
            dead = [h for h, p in self._by_hash.items() if p.attempt_id == attempt_id]
            for h in dead:
                del self._by_hash[h]
        return len(dead)


_ANY = {Role.USER, Role.RUNNER, Role.UI}
_USER_UI = {Role.USER, Role.UI}
# (método, regex da rota, papéis, exige confirmação interativa, runner só no próprio job)
ROUTES = [
    ("GET", r"/health", _ANY, False, False),
    ("POST", r"/jobs", _USER_UI, False, False),
    ("GET", r"/jobs", _USER_UI, False, False),
    ("GET", r"/jobs/[^/]+", _ANY, False, True),
    ("POST", r"/jobs/[^/]+/(pause|resume|cancel|priority)", _USER_UI, False, False),
    ("GET", r"/approvals", _USER_UI, False, False),
    ("POST", r"/approvals/[^/]+", {Role.USER}, True, False),
    ("POST", r"/runner/(heartbeat|step|result)", {Role.RUNNER}, False, True),
    ("POST", r"/llm/generate", {Role.RUNNER}, False, True),
    ("POST", r"/tools/[^/]+", {Role.RUNNER}, False, True),
    ("GET", r"/resources", _ANY, False, False),
    ("POST", r"/stop", _ANY, False, False),
    ("POST", r"/stop/release", {Role.USER}, True, False),
]


def authorize(p: Principal, method: str, route: str, target_job: str | None = None,
              confirmation_ok: bool = False) -> bool:
    """Matriz de 12 §11. Aprovar e liberar STOP: só `user` E código de confirmação digitado (08 §8)."""
    if not isinstance(p, Principal):
        return False
    for m, pattern, roles, needs_confirmation, runner_own_job in ROUTES:
        if m != method.upper() or not re.fullmatch(pattern, route):
            continue
        if p.role not in roles:
            return False
        if needs_confirmation and not confirmation_ok:
            return False
        if p.role is Role.RUNNER and runner_own_job:
            return bool(p.job_id) and target_job == p.job_id
        return True
    return False
