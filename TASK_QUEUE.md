# TASK_QUEUE.md — Fila de tarefas

Legenda: `[x]` concluída e verificada · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueada

## FASE 0 — Preparação — CONCLUÍDA (CP-0001, commits `5aa9709` e `afc1dcc`)

- [x] Repositório, estrutura de estado, Git, primeiro commit, push, checkpoint CP-0001

## FASE 1 — Arquitetura — CONCLUÍDA, aguardando commit

- [x] Ler estado e verificar o Git
- [x] Medir hardware real e ferramentas (`tools/diagnostics/measure-hardware.ps1`)
- [x] Especificar os 21 componentes e os itens A–K em `docs/architecture/`
- [x] Registrar decisões D-0012 a D-0025
- [x] Atualizar arquivos de estado e criar CP-0002 (pendente de commit)
- [ ] **Usuário:** revisar e aprovar o commit da Fase 1 (`docs: define App Factory architecture (Phase 1)`)
- [ ] Após o commit: preencher `validated_commit` no CP-0002 (commit seguinte, D-0011)

## Decisões pendentes do usuário (antes da Fase 2)

- [ ] KI-0008 — mover os modelos do Ollama para D: (`OLLAMA_MODELS`)?
- [ ] KI-0009 — confirmar se `qwen3-coder:latest` é local
- [ ] Definir `OLLAMA_MAX_LOADED_MODELS=1` / `OLLAMA_NUM_PARALLEL=1`?
- [ ] Docker Desktop pode ser iniciado sob demanda pela fábrica?
- [ ] Algum provedor externo gratuito pode ser habilitado? (padrão: nenhum)

## PRÓXIMA FASE

- [ ] **FASE 2 — Implementação**, fatia 2.1 Fundação (ver `docs/architecture/14-plano-fase-2.md`) — só com nova instrução
