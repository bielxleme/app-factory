# TASK_QUEUE.md — Fila de tarefas

Legenda: `[x]` concluída e verificada · `[~]` em andamento · `[ ]` pendente · `[!]` bloqueada

## FASE 0 — Preparação (prioridade: máxima)

- [x] Preparar repositório (diretório `D:\Claude\app-factory`, `git init -b main`)
- [x] Criar estrutura de estado (arquivos `.md`, `.appfactory/job.json`, `.appfactory/checkpoints/`)
- [x] Configurar Git (remote `origin`, `.gitignore`, `.gitattributes`)
- [~] Criar primeiro commit — executado pelo usuário no WSL (depende: estrutura criada)
- [ ] Enviar para o GitHub (push) — usuário no WSL (depende: primeiro commit)
- [ ] Criar primeiro checkpoint (depende: push verificado)

## PRÓXIMA FASE

- [ ] **FASE 1 — Arquitetura da App Factory** (depende: Fase 0 validada; só iniciar com nova instrução do usuário)
