# HANDOFF.md — Ponto de parada

**Atualizado em:** 2026-09-26 20:05 -03:00 · **Por:** Claude (Cowork)

## Situação
**Fase 2.1 (Fundação: Job Manager) implementada e testada; aguardando `uv run pytest` no Windows e o commit do usuário.** Nada foi commitado.

## O que foi implementado
- **Job Manager** em `src/appfactory/` (somente biblioteca padrão):
  - `jobs/store.py` — schema SQLite v1 + migrações; WAL, `synchronous=FULL`; `events` append-only e `checkpoints` imutáveis por triggers; índice único "1 job PLANNING/RUNNING/STOPPING por projeto".
  - `jobs/states.py` — 9 estados da arquitetura + `STOPPING`/`STOPPED` (D-0040).
  - `jobs/manager.py` — criar/listar/consultar, fila persistente com prioridade e envelhecimento, `claim` com lease, heartbeat, *fencing*, checkpoints, journal, validação, `complete` (só com validação), falhas/retry/BLOCKED, STOP de job, STOP da fábrica, resume, cancel, locks.
  - `jobs/executor.py` — executa só handlers registrados (`jobs/handlers.py`, tipo `demo.steps`); retoma do último checkpoint válido; parada graciosa com checkpoint `stop` e limpeza de temporários.
  - `jobs/recovery.py` — recuperação de órfãos (07 §3 adaptado), isolada por job e idempotente.
  - `jobs/leases.py` — verificação de vida (PID + criação + boot) e carência de 2 leases.
  - `checkpoints/service.py` — checkpoints anexados com checksum SHA-256.
  - `core/` (caminhos, relógio de tempo ativo, IDs, identidade de processos, STOP da fábrica), `logs/` (espelho JSONL + redação), `cli/main.py` (`af`).
- **Testes:** 58 em `tests/unit` e `tests/integration`, incluindo os 2 cenários de aceite com queda real de processo.

## Resultados dos testes
58/58 OK em Linux com Python 3.10 (VM do Cowork) e 3.11/3.12/3.13 (nuvem). Pytest e Windows **não** executados aqui: PyPI bloqueado nos dois ambientes (KI-0018).

## Decisões tomadas
D-0040 (STOPPING/STOPPED) · D-0041 (escopo da 2.1, plano implícito) · D-0042 (sem dependências de execução) · D-0043 (escritor único transitório) · D-0044 (posse, verificação de vida, fencing) · D-0045 (checkpoints no SQLite) · D-0046 (regras de falha) · D-0047 (só handlers registrados; injeção de falhas controlada).

## Limitações
Sem daemon/Job Objects (recuperação via `af recover`; processo mudo perde a posse mas não é encerrado — KI-0019); escritor único ainda transitório (KI-0020); caminhos Windows não executados em Windows (KI-0018); tipo de job único (`demo.steps`).

## Correção feita fora do código
`.gitignore`: `logs/` → `/logs/` (a regra antiga ignoraria o pacote `src/appfactory/logs/`).

## Próxima ação (usuário, PowerShell em `D:\Claude\app-factory`)
```powershell
uv run pytest
git status
git add .
git commit -m "feat: add Job Manager foundation (Phase 2.1)"
git push
```
Depois: a próxima IA registra o resultado do `uv run pytest` no `TEST_STATUS.md` (T17) e preenche `validated_commit` no CP-0004.

## Regras para a próxima IA
- Ler `AGENTS.md` e `docs/runbooks/job-manager.md`.
- Não adicionar dependências sem decisão (D-0042); pytest só via `pytest.ini`.
- **Não iniciar a Fase 2.2** sem nova instrução do usuário.

## Próximo passo exato
Rodar `uv run pytest` no Windows, em `D:\Claude\app-factory`.
