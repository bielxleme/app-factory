# CHANGELOG.md

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Comandos detalhados em `COMMAND_LOG.md`.

## [Não lançado]

### Fase 0 — Checkpoint (2026-09-26)

#### Adicionado
- `.appfactory/checkpoints/CP-0001-fase0.json` — primeiro checkpoint; base `5aa9709`.
- Decisões D-0010 (Git para Windows/PowerShell; WSL/OpenClaw separado) e D-0011 (checkpoint referencia commit anterior).
- KI-0006 e verificações V17–V20.

#### Alterado
- `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `.appfactory/job.json`: Fase 0 marcada como **concluída**.
- `TEST_STATUS.md`: V14–V16 com resultados reais. `KNOWN_ISSUES.md`: KI-0001/0002 contornados, KI-0005 não ocorreu.
- `COMMAND_LOG.md`, `RESOURCE_POLICY.md`, `DECISIONS.md` (D-0004 revisada).

### Fase 0 — Commit inicial `5aa9709` (2026-09-26)

### Fase 0 — Preparação (2026-09-26)

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
