"""Leases em tempo ATIVO + verificação de vida (15 §4–5, D-0031).

Uma tentativa só é considerada morta quando: o boot mudou, ou o PID não existe mais, ou o PID foi
reutilizado (horário de criação diferente). Processo vivo com lease vencido ganha uma carência de
`stale_grace_leases` leases; depois disso é declarado 'stalled' e perde a posse (fencing: toda escrita
dele passa a ser recusada com LeaseLost)."""
from __future__ import annotations

from typing import Callable

ALIVE = "alive"
DEAD = "dead"
STALLED = "stalled"
ENDED = "ended"


def evaluate(att: dict, *, now_active_ms: int, current_boot_id: str, lease_ms: int, stale_grace_leases: int,
             liveness: Callable[[int | None, str | None], bool]) -> str:
    if att.get("ended_at"):
        return ENDED
    boot = att.get("boot_id")
    boot_changed = bool(boot) and boot != "unknown" and current_boot_id != "unknown" and boot != current_boot_id
    if att.get("pid") is not None:
        if not liveness(att.get("pid"), att.get("process_create_time")):
            return DEAD
        if boot_changed:
            # O identificador de boot mudou, mas o MESMO processo (PID + criação) segue vivo: o id de boot pode
            # ter variado (ex.: ajuste de relógio no Windows). Tempos ativos não são comparáveis -> conservador.
            return ALIVE
    elif boot_changed:
        return DEAD  # sem PID e outro boot: o dono antigo não pode ter sobrevivido ao reinício
    expires = int(att["lease_expires_active_ms"])
    if now_active_ms <= expires:
        return ALIVE
    if now_active_ms - expires > stale_grace_leases * lease_ms:
        return STALLED
    return ALIVE  # lease vencido, mas ainda dentro da carência
