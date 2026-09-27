"""Redação de segredos em logs (08 §2)."""
from __future__ import annotations

import re

_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)((?:password|passwd|secret|token|api[_-]?key)\s*[\"']?\s*[:=]\s*[\"']?)([^\s\"',}]+)"),
]


def redact(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in _PATTERNS[:-1]:
        out = pat.sub("[REDACTED]", out)
    out = _PATTERNS[-1].sub(lambda m: m.group(1) + "[REDACTED]", out)
    return out
