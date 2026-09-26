# CHANGELOG.md

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Comandos detalhados em `COMMAND_LOG.md`.

## [Não lançado]

### Fase 1 — Arquitetura (2026-09-26) — pendente de commit

#### Adicionado
- `docs/architecture/` (15 documentos): visão geral, 21 componentes com 14 campos cada, fluxo de tarefa, sistema de jobs, execução paralela, Resource Manager, Provider/Model Router, persistência, segurança, autoevolução, diretórios, tecnologias, contratos, 8 diagramas ASCII, proposta de fatiamento da Fase 2.
- `tools/diagnostics/measure-hardware.ps1` — diagnóstico somente leitura de hardware e ferramentas.
- `.appfactory/checkpoints/CP-0002-fase1.json` (pendente de commit).
- Decisões D-0012 a D-0025; issues KI-0007 a KI-0013; verificações V21–V34.

#### Alterado
- `RESOURCE_POLICY.md`: valores **medidos** e política por modos (substitui a política provisória).
- `.gitignore`: `.appfactory/state/`, `jobs/`, `cache/`, `STOP` e `workspaces/`.
- `AGENTS.md`: leitura da arquitetura e regra de recursos atualizada.
- `DECISIONS.md` (D-0005 complementada), `KNOWN_ISSUES.md` (KI-0004 resolvido), `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `TEST_STATUS.md`, `COMMAND_LOG.md`, `.appfactory/job.json`.

#### Corrigido
- Título vazio no CHANGELOG (KI-0013).

### Fase 0 — Checkpoint (2026-09-26)

#### Adicionado
- `.appfactory/checkpoints/CP-0001-fase0.json` — primeiro checkpoint; base `5aa9709`.
- Decisões D-0010 (Git para Windows/PowerShell; WSL/OpenClaw separado) e D-0011 (checkpoint referencia commit anterior).
- KI-0006 e verificações V17–V20.

#### Alterado
- `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `.appfactory/job.json`: Fase 0 marcada como **concluída**.
- `TEST_STATUS.md`: V14–V16 com resultados reais. `KNOWN_ISSUES.md`: KI-0001/0002 contornados, KI-0005 não ocorreu.
- `COMMAND_LOG.md`, `RESOURCE_POLICY.md`, `DECISIONS.md` (D-0004 revisada).

### Fase 0 — Preparação · commit inicial `5aa9709` (2026-09-26)

#### Adicionado
- Diretório do projeto `D:\Claude\app-factory` e repositório Git (`main`).
- Remote `origin` → `https://github.com/bielxleme/app-factory.git`.
- Arquivos de estado: `AGENTS.md`, `PROJECT_STATE.md`, `TASK_QUEUE.md`, `DECISIONS.md`, `CHANGELOG.md`, `HANDOFF.md`, `KNOWN_ISSUES.md`, `TEST_STATUS.md`, `RESOURCE_POLICY.md`, `COMMAND_LOG.md`.
- `.appfactory/job.json` (estado: inicializado, sem job de implementação) e `.appfactory/checkpoints/` (com `.gitkeep`).
- `.gitignore` (segredos, `.env`, caches, venvs, builds, logs, pesos de modelos) e `.gitattributes` (LF).

#### Comandos principais (resumo)
- `mkdir -p app-factory/.appfactory/checkpoints`
- `git init -b main`
- `git remote add origin https://github.com/bielxleme/app-factory.git`
- `git remote -v` · `git status` · `git ls-remote https://github.com/bielxleme/app-factory`
- Commit/push (usuário, PowerShell): `git add .` · `git commit -m "chore: initialize App Factory"` · `git push -u origin main`
