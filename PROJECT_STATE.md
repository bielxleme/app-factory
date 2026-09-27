# PROJECT_STATE.md — Estado atual

| Campo | Valor |
| --- | --- |
| Projeto | App Factory |
| Inicializado em | 2026-09-26 13:13:26 -03:00 (`git init`) |
| Último commit | `97c82c4` — `chore: validate Phase 1.1 checkpoint` (= `origin/main`) |
| Checkpoints | `CP-0001` (Fase 0) · `CP-0002` (Fase 1, `4082457`) · `CP-0003` (Fase 1.1, `40d4d79`) · `CP-0004` (Fase 2.1, **pendente de commit**) |
| Fase atual | **Fase 2.1 — Fundação: Job Manager** |
| Status da fase | **CONCLUÍDA no código e nos testes — aguardando execução no Windows (`uv run pytest`) e commit do usuário** |
| Código | `src/appfactory/` (Job Manager, sem dependências de execução) + 58 testes |
| Testes | 58/58 OK em Linux com Python 3.10, 3.11, 3.12 e 3.13; Windows pendente (KI-0018) |
| Próximo estágio | Fase 2.2 — Guardrails (só com nova instrução do usuário) |
| Última atualização | 2026-09-26 20:05 -03:00 |

## Fase 2.1 — critérios

- [x] Identidade de jobs (IDs `JOB-YYYYMMDD-NNNN` sem colisão, timestamps, etapa, checkpoint, motivo)
- [x] Estados da arquitetura + `STOPPING`/`STOPPED` (D-0040); transições controladas e registradas
- [x] `COMPLETED` só após validação aprovada do checkpoint atual
- [x] SQLite como fonte da verdade (WAL, `synchronous=FULL`, estado+evento na mesma transação, triggers)
- [x] Fila persistente reconstruída após reinício
- [x] Checkpoints atômicos, nunca sobrescritos, com checksum; último válido após queda
- [x] Retomada após queda real de processo (aceite 1)
- [x] STOP explícito `RUNNING → STOPPING → STOPPED` com checkpoint e limpeza (aceite 2); STOP da fábrica persistente
- [x] Recuperação de órfãos (verificação de vida, journal, isolamento por job, idempotente)
- [x] 1 RUNNING por projeto (garantido pelo banco); dois executores não assumem o mesmo job (fencing)
- [x] Locks por projeto; histórico por job; CLI mínima
- [ ] `uv run pytest` no Windows (KI-0018)
- [ ] Commit da Fase 2.1 (usuário)

## O que NÃO existe ainda (proposital)

Daemon, Job Objects, API local, tokens, agentes, sandbox S1h/S2, usuário `afrunner`, Resource Manager, routers/Ollama, navegador, mídia, Evolution. Nada foi alterado no Ollama, no Windows ou fora do repositório.
