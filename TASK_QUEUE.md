# TASK_QUEUE.md — Fila de tarefas

Legenda: `[x]` concluída e verificada · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueada

## FASE 0 — Preparação — CONCLUÍDA (CP-0001)
## FASE 1 — Arquitetura — CONCLUÍDA (CP-0002, `4082457`)
## FASE 1.1 — Revisão documental — CONCLUÍDA (CP-0003, `40d4d79`)

## FASE 2.1 — Fundação: Job Manager — CONCLUÍDA E VALIDADA (CP-0004, `4373c65`)

- [x] Implementação do Job Manager e CLI mínima
- [x] 58 testes — Windows (`uv run pytest`) e Linux (Python 3.10–3.13)
- [x] Commit `4373c65` e validação pós-commit (CP-0004 preenchido)
- [ ] **Usuário:** commit da consolidação documental `chore: validate Phase 2.1 checkpoint`

## Pendências técnicas conhecidas (para a 2.4)

- [ ] KI-0019 — daemon, Job Object raiz, encerramento de processos mudos, recuperação automática na partida
- [ ] KI-0020 — daemon como único escritor do SQLite (D-0037)

## Decisões e ações do usuário previstas

- [ ] Fatia 2.5 — verificar os modelos locais com `ollama show` + `/api/ps` (KI-0009)
- [ ] Fatia 2.6 — criar o usuário local `afrunner` e aplicar as ACLs (KI-0014, KI-0016)
- [ ] Fatia 2.9+ — `af daemon install-autostart`
- [ ] Futuro — migrar os modelos do Ollama para D: (D-0034)

## PRÓXIMA FASE

- [ ] **FASE 2.2 — Guardrails** (`tests/guardrails/` I1–I7, `protected-paths.yaml`, verificador de diff) — só com nova instrução
