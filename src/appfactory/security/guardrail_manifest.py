"""Manifesto dos guardrails (D-0048). Arquivo protegido: `tests/guardrails/MANIFEST.json`.

* Cada verificação de I1–I7 é `active` ou `pending` (com fatia e módulo esperado).
* **`pending` nunca significa aprovação.** Um resultado verde da suíte com pendências NÃO aprova nada.
* O Evolution só pode ser habilitado quando I1–I7 estiverem todas `active` (`evolution_allowed`)."""
from __future__ import annotations

import os
from pathlib import Path

from appfactory.security.paths import PolicyFileError, load_policy_file

MANIFEST_FILE = "tests/guardrails/MANIFEST.json"
INVARIANTS = ("I1", "I2", "I3", "I4", "I5", "I6", "I7")
FIXED_COMMAND = ("-m", "pytest", "-c", "tests/guardrails/pytest.ini", "--noconftest", "-p", "no:cacheprovider",
                 "tests/guardrails")


def load_manifest(root: str | os.PathLike) -> dict:
    data = load_policy_file(Path(root) / MANIFEST_FILE)
    validate(data)
    return data


def validate(data: dict) -> None:
    inv = data.get("invariants")
    if not isinstance(inv, dict):
        raise PolicyFileError("manifesto sem 'invariants'")
    missing = [i for i in INVARIANTS if i not in inv]
    if missing:
        raise PolicyFileError(f"invariantes ausentes do manifesto: {missing}")
    for name, spec in inv.items():
        if name not in INVARIANTS:
            raise PolicyFileError(f"invariante desconhecida: {name}")
        checks = spec.get("checks") if isinstance(spec, dict) else None
        if not isinstance(checks, dict) or not checks:
            raise PolicyFileError(f"{name}: sem verificações")
        if not isinstance(spec.get("file"), str):
            raise PolicyFileError(f"{name}: sem arquivo de teste")
        for cid, c in checks.items():
            if not cid.startswith(name + "."):
                raise PolicyFileError(f"{cid}: id deve começar com {name}.")
            if not isinstance(c, dict) or c.get("status") not in ("active", "pending"):
                raise PolicyFileError(f"{cid}: status deve ser 'active' ou 'pending'")
            if c["status"] == "pending" and not (isinstance(c.get("slice"), str) and c.get("slice")
                                                 and isinstance(c.get("module"), str) and c.get("module")):
                raise PolicyFileError(f"{cid}: 'pending' exige 'slice' e 'module' (D-0048)")


def checks(data: dict) -> dict:
    return {cid: c for spec in data["invariants"].values() for cid, c in spec["checks"].items()}


def pending(data: dict) -> dict:
    return {cid: c for cid, c in checks(data).items() if c["status"] == "pending"}


def invariant_status(data: dict) -> dict:
    out = {}
    for name in INVARIANTS:
        pend = [c for c in data["invariants"][name]["checks"].values() if c["status"] == "pending"]
        out[name] = "active" if not pend else "pending:" + ",".join(sorted({c["slice"] for c in pend}))
    return out


def evolution_allowed(data: dict) -> bool:
    """D-0048: o Evolution só pode ser habilitado com I1–I7 todas `active`."""
    return not pending(data)


def approval(data: dict, suite_returncode: int) -> dict:
    """Resultado do portão: aprovado só com a suíte verde E nenhuma pendência (pending ≠ aprovação)."""
    pend = pending(data)
    return {"suite_ok": suite_returncode == 0, "pending": sorted(pend), "approved": suite_returncode == 0 and not pend,
            "evolution_allowed": evolution_allowed(data),
            "note": "D-0048: `pending` nunca significa aprovação; Evolution só com I1–I7 `active`."}
