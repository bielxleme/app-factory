# TASK_QUEUE.md — Fila de tarefas

Legenda: `[x]` concluída e verificada · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueada

## FASE 0 — Preparação — CONCLUÍDA

- [x] Preparar repositório (diretório `D:\Claude\app-factory`, `git init -b main`)
- [x] Criar estrutura de estado (arquivos `.md`, `.appfactory/job.json`, `.appfactory/checkpoints/`)
- [x] Configurar Git (remote `origin`, `.gitignore`, `.gitattributes`)
- [x] Criar primeiro commit — `5aa9709` (usuário, PowerShell)
- [x] Enviar para o GitHub — `origin/main` = `5aa9709`
- [x] Criar primeiro checkpoint — `CP-0001`
- [ ] Commitar e enviar o checkpoint e as atualizações de estado (usuário, PowerShell)

## PRÓXIMA FASE

- [ ] **FASE 1 — Arquitetura da App Factory** (depende: Fase 0 validada ✔; só iniciar com nova instrução do usuário)
  - Sugestão inicial: medir RAM/GPU/VRAM reais e atualizar `RESOURCE_POLICY.md` (KI-0004)
