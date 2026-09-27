# CHANGELOG.md

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Comandos detalhados em `COMMAND_LOG.md`.

## [Não lançado]

### Fase 2.1 — Fundação: Job Manager (2026-09-26) — pendente de commit

#### Adicionado
- `pyproject.toml` (sem dependências de execução, `af` como script), `pytest.ini`, `.python-version` (3.13).
- `src/appfactory/`: `core/` (caminhos, relógio de tempo ativo, IDs, identidade de processo, STOP da fábrica), `jobs/` (estados, store SQLite + migrações, manager, executor, handlers registrados, leases, locks, recuperação, erros), `checkpoints/service.py`, `logs/` (espelho JSONL e redação), `cli/main.py`.
- Job Manager: estados da arquitetura + `STOPPING`/`STOPPED`, fila persistente, checkpoints atômicos com checksum, retomada do último checkpoint válido, STOP de job gracioso, STOP da fábrica persistente, recuperação de órfãos, leases com verificação de vida e fencing, 1 RUNNING por projeto (índice único), locks por projeto, histórico por job (tabela `events` append-only), CLI mínima.
- 58 testes (`tests/unit`, `tests/integration`), incluindo os dois cenários de aceite com queda real de processo.
- `docs/runbooks/job-manager.md`; decisões D-0040 a D-0047; KI-0018 a KI-0020.

#### Alterado
- `docs/architecture/03-jobs.md` (estados STOPPING/STOPPED, §8), `14-plano-fase-2.md` (2.1 redefinida, 2.4 ajustada), `10-diretorios.md`, `AGENTS.md` (convenções de teste e dependências).

#### Corrigido
- `.gitignore`: `logs/` → `/logs/` (a regra antiga ignorava o pacote `src/appfactory/logs/`).

### Fase 1.1 — Revisão e correção documental (2026-09-26) — pendente de commit

Base: revisão técnica do commit `4082457` (achados N1–N8). Somente documentação, especificação, decisões e estado.

#### Adicionado
- `docs/architecture/15-daemon.md` — instância única, `af daemon`, início no logon, leases em tempo ativo, sono, Job Objects, órfãos (N3).
- `.appfactory/checkpoints/CP-0003-fase1-1.json` (pendente de commit).
- Decisões D-0026 a D-0039; issues KI-0014 a KI-0017; verificações V35–V44.
- Diagramas 9 (execução não confiável e papéis) e 10 (ciclo de vida do daemon).

#### Alterado
- `08-seguranca.md` reestruturado: código gerado não confiável, S1h (usuário `afrunner`, Job Object, ACL), S2 obrigatório, tokens por papel, aprovações interativas, STOP persistente, npm/pip, infraestrutura protegida ampliada (N1, N2).
- `05-resource-manager.md`: GPU no WDDM (VRAM própria/de terceiros, margem, janela de observação, heurísticas), limiares canônicos de CPU, BATTERY, tetos de GPU (N4, N7).
- `06-provider-model-router.md`: classes de modelo, registro de posse, custo *fail-closed*, Ollama inalterado (N5).
- `07-persistencia.md`: estado versionado × operacional, recuperação com verificação de vida (N6, N3).
- `03-jobs.md`, `04-execucao-paralela.md`: 1 job RUNNING por projeto, locks por projeto, regra de `writes`, worktree de integração, escritor único do SQLite (N7).
- `00`, `01`, `02`, `09`, `10`, `11`, `12`, `13`, `14`, `README.md` alinhados à revisão 1.1.
- `AGENTS.md` (regras 13–15), `RESOURCE_POLICY.md` (tetos e limiares), `DECISIONS.md` (status de D-0005 e D-0012–D-0025), `KNOWN_ISSUES.md`, `TEST_STATUS.md`, `COMMAND_LOG.md`, `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `.appfactory/job.json` (agora resumo de marco).
- `CP-0002-fase1.json`: `validated_commit` = `4082457` (N8).

### Fase 1 — Arquitetura (2026-09-26) — commit `4082457`

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
