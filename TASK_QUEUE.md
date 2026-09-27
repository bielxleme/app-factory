# TASK_QUEUE.md — Fila de tarefas

Legenda: `[x]` concluída e verificada · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueada

## FASE 0 — Preparação — CONCLUÍDA (CP-0001)
## FASE 1 — Arquitetura — CONCLUÍDA (CP-0002, `4082457`)
## FASE 1.1 — Revisão documental — CONCLUÍDA (CP-0003, `40d4d79`)

## FASE 2.1 — Fundação: Job Manager — CONCLUÍDA E VALIDADA (CP-0004, `4373c65`)

- [x] Implementação do Job Manager e CLI mínima
- [x] 58 testes — Windows (`uv run pytest`) e Linux (Python 3.10–3.13)
- [x] Commit `4373c65` e validação pós-commit (CP-0004 preenchido)
- [x] **Usuário:** commit da consolidação documental `b0a80e5` `chore: validate Phase 2.1 checkpoint` (sincronizado com `origin/main`)

## Pendências técnicas conhecidas (para a 2.4)

- [ ] KI-0019 — daemon, Job Object raiz, encerramento de processos mudos, recuperação automática na partida
- [ ] KI-0020 — daemon como único escritor do SQLite (D-0037)

## Decisões e ações do usuário previstas

- [ ] Fatia 2.5 — verificar os modelos locais com `ollama show` + `/api/ps` (KI-0009)
- [ ] Fatia 2.6 — criar o usuário local `afrunner` e aplicar as ACLs (KI-0014, KI-0016)
- [ ] Fatia 2.9+ — `af daemon install-autostart`
- [ ] Futuro — migrar os modelos do Ollama para D: (D-0034)

## FASE 2.2 — Guardrails e segurança de execução — ESPECIFICAÇÃO PRONTA · DECISÕES BLOQUEANTES APLICADAS

- [x] Especificação executável: `docs/specs/fase-2.2-guardrails-e-seguranca.md` (escopo, componentes, APIs, matriz G22-01…54, critérios AC-01…14, pendências P-01…P-15, ordem)
- [x] Decisões bloqueantes aprovadas pelo usuário (2026-09-27): P-01→D-0048, P-02→D-0049, P-03→D-0050, P-05→D-0051, P-06→D-0052, P-07→D-0053, P-15→D-0054
- [x] Decisões registradas em `DECISIONS.md` e aplicadas em `AGENTS.md`, `docs/architecture/` (01, 05, 08, 09, 10, 11, 14, 15, README) e na especificação
- [ ] **Usuário:** commit da documentação da 2.2 (`docs: approve Phase 2.2 blocking decisions`)
- [ ] Pendências não bloqueantes a decidir durante a fatia: P-04, P-08, P-09, P-10, P-11, P-12, P-13, P-14
- [ ] Implementação na ordem do §10 da especificação — só com nova instrução
