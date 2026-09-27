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
- [ ] **D-0056 (obrigatório)** — verificar a integridade dos guardrails (`protected-paths.yaml`, `commands.yaml`, `MANIFEST.json`, cadeia do `audit.jsonl`) antes de qualquer execução real, a partir da partida do daemon; falha de integridade **aciona o STOP da fábrica** (`reason="guardrail"`), antes das execuções das fatias que dependem do daemon
- [ ] **D-0057** — aplicação operacional da autorização (`core/auth.py`: tokens por papel na API local, arquivo `user.token` com ACL) na fatia que implementar a API/daemon (08 §8, 12 §11)

## Decisões e ações do usuário previstas

- [ ] Fatia 2.5 — verificar os modelos locais com `ollama show` + `/api/ps` (KI-0009)
- [ ] Fatia 2.6 — criar o usuário local `afrunner` e aplicar as ACLs (KI-0014, KI-0016)
- [ ] Fatia 2.9+ — `af daemon install-autostart`
- [ ] Futuro — migrar os modelos do Ollama para D: (D-0034)

## FASE 2.2 — Guardrails e segurança de execução — CONCLUÍDA E VALIDADA (CP-0005, `6fb983c`)

- [x] Especificação executável: `docs/specs/fase-2.2-guardrails-e-seguranca.md` (escopo, componentes, APIs, matriz G22-01…54, critérios AC-01…14, pendências P-01…P-15, ordem)
- [x] Decisões bloqueantes aprovadas pelo usuário (2026-09-27): P-01→D-0048, P-02→D-0049, P-03→D-0050, P-05→D-0051, P-06→D-0052, P-07→D-0053, P-15→D-0054
- [x] Decisões registradas em `DECISIONS.md` e aplicadas em `AGENTS.md`, `docs/architecture/` (01, 05, 08, 09, 10, 11, 14, 15, README) e na especificação
- [x] **Usuário:** commit da documentação da 2.2 — `683b9e2` `docs: approve Phase 2.2 blocking decisions`
- [x] Pendências não bloqueantes registradas (P-04, P-08…P-14) — situação atual nos itens abaixo
- [x] Implementação (componentes E1–E11 da especificação; D-0055 registra as alterações aditivas em arquivos protegidos)
- [x] Testes em Linux: 164 OK (Python 3.10, 3.11, 3.12, 3.13; 10 pulados com motivo)
- [x] **Usuário (Windows):** `uv run pytest` — 1ª execução: 156 passed, 7 skipped, 1 failed (nomes 8.3) → corrigido; revalidação: **157 passed, 7 skipped, 0 failed** (CPython 3.13.14)
- [x] **Usuário (Windows):** `uv run python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails` — **21 passed, 7 skipped, 0 failed**
- [x] **Usuário:** commit `6fb983c` `feat: add guardrails and execution security (Phase 2.2)` e push; validação pós-commit do CP-0005 feita
- [ ] **Usuário:** commit da consolidação documental `chore: validate Phase 2.2 checkpoint`
- [x] P-11 decidida em D-0056 (fail-closed na 2.2; STOP por falha de integridade obrigatório na 2.4) e P-08 decidida em D-0057 (autorização com escopo limitado)
- [ ] Decidir as pendências não bloqueantes restantes (P-04, P-09, P-10, P-12, P-13, P-14); escolhas provisórias em D-0055
