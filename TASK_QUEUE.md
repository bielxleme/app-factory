# TASK_QUEUE.md — Fila de tarefas

Legenda: `[x]` concluída e verificada · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueada

## FASE 0 — Preparação — CONCLUÍDA (CP-0001)
## FASE 1 — Arquitetura — CONCLUÍDA (CP-0002, `4082457`)
## FASE 1.1 — Revisão documental — CONCLUÍDA (CP-0003, `40d4d79`; validado em `97c82c4`)

## FASE 2.1 — Fundação: Job Manager — CONCLUÍDA no código, aguardando validação no Windows e commit

- [x] Núcleo: schema SQLite v1, estados, IDs, relógio de tempo ativo, identidade de processos
- [x] Manager, executor, checkpoints, STOP de job e da fábrica, recuperação, leases/fencing, locks, CLI
- [x] 58 testes (unitários + integração com queda real de processo) — OK em Linux, Python 3.10–3.13
- [x] Documentação: D-0040 a D-0047, runbook, 03/10/14, KI-0018 a KI-0020, CP-0004
- [ ] **Usuário:** `uv run pytest` no Windows (KI-0018) e registrar o resultado
- [ ] **Usuário:** commit `feat: add Job Manager foundation (Phase 2.1)`
- [ ] Após o commit: preencher `validated_commit` no CP-0004 (D-0011)

## Decisões e ações do usuário previstas

- [ ] Fatia 2.5 — verificar os modelos locais com `ollama show` + `/api/ps` (KI-0009)
- [ ] Fatia 2.6 — criar o usuário local `afrunner` e aplicar as ACLs (KI-0014, KI-0016)
- [ ] Fatia 2.9+ — `af daemon install-autostart`
- [ ] Futuro — migrar os modelos do Ollama para D: (D-0034)

## PRÓXIMA FASE

- [ ] **FASE 2.2 — Guardrails** (`tests/guardrails/` I1–I7, `protected-paths.yaml`, verificador de diff) — só com nova instrução
