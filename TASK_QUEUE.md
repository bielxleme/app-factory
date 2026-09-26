# TASK_QUEUE.md — Fila de tarefas

Legenda: `[x]` concluída e verificada · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueada

## FASE 0 — Preparação — CONCLUÍDA (CP-0001; commits `5aa9709`, `afc1dcc`)

## FASE 1 — Arquitetura — CONCLUÍDA (CP-0002 validado em `4082457`)

## FASE 1.1 — Revisão e correção documental — CONCLUÍDA, aguardando commit

- [x] Corrigir N1–N8 na documentação (D-0026 a D-0039)
- [x] Validar CP-0002 (`4082457`) e confirmar D-0012 a D-0025
- [x] Criar CP-0003 (pendente de commit)
- [ ] **Usuário:** revisar e fazer o commit `docs: revise architecture after Phase 1 review (Phase 1.1)`
- [ ] Após o commit: preencher `validated_commit` no CP-0003 (commit seguinte, D-0011)

## Decisões e ações do usuário previstas para a Fase 2

- [ ] Fatia 2.5 — verificar os modelos locais com `ollama show` + `/api/ps` (inclui `qwen3-coder:latest`, KI-0009)
- [ ] Fatia 2.6 — criar o usuário local `afrunner` e aplicar as ACLs (KI-0014, KI-0016)
- [ ] Fatia 2.9+ — `af daemon install-autostart` (tarefa de logon)
- [ ] Futuro — migrar os modelos do Ollama para D: (D-0034, KI-0008)
- [ ] Algum provedor externo gratuito pode ser habilitado? (padrão: nenhum)

## PRÓXIMA FASE

- [ ] **FASE 2 — Implementação**, fatia 2.1 Fundação (`docs/architecture/14-plano-fase-2.md`) — só com nova instrução
