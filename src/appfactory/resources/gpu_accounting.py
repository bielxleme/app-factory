"""Contabilidade de VRAM no WDDM (05 §1.1, D-0032). Sem VRAM por processo: tudo por diferença.

Na 2.3 não há registro de posse (2.5): `vram_factory = 0` e todo modelo do `/api/ps` é de terceiros (D-0059).
Valores desconhecidos => pior caso: VRAM disponível para a fábrica = 0 e `vram_terceiros` desconhecida."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VramAccount:
    total_mib: float | None
    used_mib: float | None
    factory_mib: float
    ollama_foreign_mib: float
    other_mib: float | None
    foreign_mib: float | None
    available_for_factory_mib: float

    def to_dict(self) -> dict:
        return asdict(self)


def account(total_mib, used_mib, ollama_models, *, base_mib: float, margin_mib: float, reserve_mib: float,
            factory_models=()) -> VramAccount:
    """`ollama_models`: lista de {"name", "size_vram_mib"} (ou None se o /api/ps falhou).
    `factory_models`: nomes com posse da fábrica — vazio até a 2.5 (D-0059)."""
    owned = set(factory_models)
    models = ollama_models or []
    factory = sum(m["size_vram_mib"] for m in models if m["name"] in owned)
    ollama_foreign = sum(m["size_vram_mib"] for m in models if m["name"] not in owned)
    if total_mib is None or used_mib is None:
        return VramAccount(total_mib, used_mib, factory, ollama_foreign, None, None, 0.0)
    other = max(0.0, used_mib - factory - ollama_foreign - base_mib)
    available = max(0.0, total_mib - used_mib - reserve_mib - margin_mib)
    return VramAccount(total_mib, used_mib, factory, ollama_foreign, other, ollama_foreign + other, available)
