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
- [ ] **D-0060** — integrar a admissão do Resource Manager ao despacho de jobs (daemon)
- [ ] **D-0061** — tabelas `resource_samples` e `resource_decisions` (migração de schema)
- [ ] **D-0057** — aplicação operacional da autorização (`core/auth.py`: tokens por papel na API local, arquivo `user.token` com ACL) na fatia que implementar a API/daemon (08 §8, 12 §11)

## Decisões e ações do usuário previstas

- [ ] Fatia 2.5 — verificar os modelos locais com `ollama show` + `/api/ps` (KI-0009)
- [ ] Fatia 2.5 — cenário M5 da matriz KI-0017 (inferência da fábrica + jogo; D-0066) e contabilidade de VRAM com posse (D-0059)
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
- [x] **Usuário:** commit da consolidação documental `f44ac72` `chore: validate Phase 2.2 checkpoint` (sincronizado com `origin/main`)
- [x] P-11 decidida em D-0056 (fail-closed na 2.2; STOP por falha de integridade obrigatório na 2.4) e P-08 decidida em D-0057 (autorização com escopo limitado)
- [ ] Decidir as pendências não bloqueantes restantes (P-04, P-09, P-10, P-12, P-13, P-14); escolhas provisórias em D-0055

## FASE 2.3 — Resource Manager — VALIDAÇÃO NO WINDOWS PENDENTE (não commitada)

- [x] Especificação executável: `docs/specs/fase-2.3-resource-manager.md` (escopo E1–E11, componentes, APIs, matriz G23-01…32, matriz manual KI-0017 M1–M4, critérios AC23-01…10, pendências P23-01…P23-10, ordem)
- [x] **Usuário:** P23-01 a P23-10 decididas (2026-09-27), todas conforme as recomendações da §9
- [x] Decisões registradas em `DECISIONS.md` (D-0058 a D-0067) e aplicadas na especificação; `05-resource-manager.md` §2 corrigido (D-0062 — saída de CRITICAL exige STOP da fábrica liberado; revisão 1.2)
- [x] Fechamento documental: D-0058 ajustada (fallback `nvidia-smi` implementado, permitido e isolado em `probes/nvidia.py`, sujeito ao AC-06); D-0063 complementada (`admit` lê o histórico do `watch`; `watch` a 1 s; `resource.snapshot` append-only, sem retenção); referências de tecnologia alinhadas (01 §4, 05 §1, 11, 13 §4); `14-plano-fase-2.md` e `CHANGELOG.md` atualizados
- [x] Pendências pré-implementação resolvidas: D-0068 (`GlobalMemoryStatusEx` como fonte oficial de RAM; 01 §4 e 05 §1 atualizados) e D-0069 (histerese por tempo decorrido contínuo de 10 s)
- [x] Plano de implementação preparado; conflitos resolvidos: D-0070 (`sampling` sem `mode_confirmations`, histerese fixa, `interval_s: 1`), D-0071 (ociosidade instantânea), D-0072 (reserva de RAM de CONTENTION 3,0 GB)
- [x] Implementação E1–E10 (D-0073): política, sondas, contabilidade de VRAM, modos com histerese por tempo ativo, admissão, eventos, CLI `af resources`, guardrail I4 ativo; runbook `docs/runbooks/recursos.md`
- [x] Testes em Linux: 217 OK (10 pulados) — Python 3.10 (VM) e 3.11/3.12/3.13 (nuvem); guardrails 22 OK, 6 pulados
- [x] **Usuário (Windows, 2026-09-27):** `uv run pytest` 210 passed/7 skipped; guardrails 22 passed/6 skipped; G23-27 ok; `measure-hardware.ps1` + `af resources compare` `"ok": true`; `git diff --check` ok
- [x] **Usuário (Windows):** M1–M4 executados — M1 conforme; M2–M4 não conclusivos (CRITICAL por RAM; M4 sem modelo local no `/api/ps`)
- [x] Correção D-0074 (uso alheio da GPU pela média de 30 s, defeito visto em M2); Linux 218 OK (3.10–3.13)
- [ ] **Usuário (Windows):** executar `.appfactory\runtime\validate-2.3b.ps1` (aguardando meio de execução) — repete `uv run pytest` e os guardrails após D-0074
- [x] **Usuário (Windows, rodada 2.3b):** 211 passed/7 skipped; guardrails 22/6; M2 **PASS**; M3 e M4 **não conclusivos** (CRITICAL por RAM)
- [x] Correção D-0075: `/api/ps` a cada 15 s em segundo plano; `watch` mantém 1 s mesmo com timeout do Ollama; Linux 223 OK
- [x] Rodada 2.3c preparada: Linux 223 OK; script `.appfactory\runtime\validate-2.3c.ps1` (suíte, guardrails, M3, M4; sem M2)
- [ ] **Usuário (Windows):** executar `validate-2.3c.ps1` — repete `uv run pytest` e guardrails após D-0075 (esperado 216 passed/7 skipped; 22/6)
- [ ] **Usuário (Windows):** repetir M3 e M4 em condições controladas (caminho 1, critério inalterado); M5 na 2.5
- [ ] Registrar os resultados em `TEST_STATUS.md` e gerar o CP-0006 (só depois de todas as validações)
- [ ] **Usuário:** commit e push da 2.3
