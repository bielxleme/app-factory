# CHANGELOG.md

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Comandos detalhados em `COMMAND_LOG.md`.

## [Não lançado]

### Fase 2.3 — Resource Manager: rodada 2.3b e correção D-0075 (2026-09-27) — **PENDENTE**; sem commit

#### Verificado
- Windows após D-0074: `uv run pytest` 211 passed, 7 skipped; guardrails 22/6; M2 PASS (CONTENTION após tela cheia, sem `critical`); M3 e M4 não conclusivos (CRITICAL por RAM; M4 com `qwen3:8b` local contabilizado como terceiros).

#### Corrigido
- `resources/probes/runtime_local.py`: `/api/ps` no máximo a cada 15 s (05 §1), em segundo plano depois da 1ª consulta; falha ou resultado velho = pior caso registrado em toda amostra. `resources/manager.py`: o `watch` desconta o tempo da amostra e mantém o intervalo nominal de 1 s. Antes, com o Ollama sem responder, o intervalo real era ~3,1 s (D-0075). Linux: 223 testes OK (3.10–3.13).

### Fase 2.3 — Resource Manager: validação no Windows (2026-09-27) — **PENDENTE**; sem commit

#### Verificado
- Windows (CPython 3.13.14): `uv run pytest` 210 passed, 7 skipped; guardrails 22 passed, 6 skipped; G23-27 (sondas reais) passou; `af resources compare` `"ok": true`; `git diff --check` sem erro; M1–M4 executados sem falha de sonda (M1 conforme; M2–M4 não demonstraram o critério de cada cenário — ver `TEST_STATUS.md`).

#### Corrigido
- `src/appfactory/resources/modes.py`: o critério "uso alheio da GPU > 20%" passa a usar a **média de 30 s** das amostras sem chamada da fábrica (05 §1), e não o valor instantâneo — defeito encontrado nos dados reais de M2 (D-0074). Novo teste em `tests/unit/test_resource_modes.py`. Linux: 218 testes OK (3.10–3.13).

#### Alterado
- `TEST_STATUS.md`, `COMMAND_LOG.md`, `DECISIONS.md` (D-0074), `KNOWN_ISSUES.md` (KI-0017), `docs/runbooks/recursos.md` (observações da 1ª execução), especificação e `14-plano-fase-2.md` (status), `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `.appfactory/job.json`. CP-0006 **não** gerado.

### Fase 2.3 — Resource Manager: implementação (2026-09-27) — pendente de validação no Windows e de commit

#### Adicionado
- `config/resources.yaml` (subconjunto JSON, protegido): política de 05 §9 sem `mode_confirmations`, `sampling.interval_s: 1`, reserva de RAM de CONTENTION 3,0 GB (D-0070, D-0072).
- `src/appfactory/resources/`: `policy.py` (esquema fechado, tetos e limiares canônicos — D-0064), `probes/{windows,nvidia,runtime_local,linux}.py` (somente biblioteca padrão; NVML via `ctypes`, `nvidia-smi` só como fallback isolado; `GlobalMemoryStatusEx`; `/api/ps` somente leitura — D-0058, D-0059, D-0067, D-0068), `gpu_accounting.py` (05 §1.1), `modes.py` (histerese por tempo ativo — D-0069; ociosidade instantânea — D-0071; saída de CRITICAL com STOP liberado — D-0062), `history.py` e `manager.py` (admissão sobre o histórico do `watch` — D-0063; eventos `resource.*` — D-0061), `compare.py` (AC23-07).
- CLI `af resources snapshot|mode|admit|watch|compare`.
- Testes G23-01…G23-32 (`test_resource_policy`, `test_resource_modes`, `test_gpu_accounting`, `test_admission`, `test_probes`, `test_cli_resources`, `tests/fakes/probes.py`); `docs/runbooks/recursos.md`; decisão D-0073.

#### Alterado (aditivo; registrado em D-0073)
- `src/appfactory/cli/main.py` (grupo `af resources`); `tests/guardrails/test_resource_limits.py` e `MANIFEST.json` (`I4.resources_config_within_ceilings` **active**); `tests/unit/test_repo_hygiene.py` (AC-06 com `resources/probes/nvidia.py`; G23-30).
- Especificação da 2.3 (status), `14-plano-fase-2.md` (2.3 implementada, aguardando validação), `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `TEST_STATUS.md`, `COMMAND_LOG.md`, `.appfactory/job.json`.
- Não alterados: Job Manager, `core/stop.py`, `core/clock.py`, `security/**`, `pyproject.toml`, Ollama, `measure-hardware.ps1`. Sem tabela ou migração nova. CP-0006 ainda não gerado.

### Fase 2.3 — Resource Manager: especificação, decisões e fechamento documental (2026-09-27) — pendente de commit; **nada implementado**

#### Adicionado
- `docs/specs/fase-2.3-resource-manager.md` — especificação executável da Fase 2.3 (escopo E1–E11, componentes, APIs, matriz G23-01…G23-32, matriz manual KI-0017 M1–M4, critérios AC23-01…AC23-10, decisões P23-01…P23-10, ordem de implementação).
- Decisões D-0068 (`GlobalMemoryStatusEx` como fonte oficial de RAM) e D-0069 (histerese por tempo decorrido contínuo de 10 s).
- Decisões D-0070 (`sampling` sem `mode_confirmations`, histerese fixa, `interval_s: 1`), D-0071 (ociosidade instantânea) e D-0072 (reserva de RAM de CONTENTION 3,0 GB); exemplo de 05 §9, 05 §2, 04 §8 e 13 §4 alinhados.
- Decisões D-0058 a D-0067 (P23-01 a P23-10), todas aprovadas pelo usuário; D-0058 ajustada (fallback `nvidia-smi` implementado, permitido e isolado em `probes/nvidia.py`, sujeito ao AC-06) e D-0063 complementada (`admit` lê o histórico do `watch`; `watch` a 1 s; `resource.snapshot` append-only, sem retenção) no fechamento documental.

#### Alterado
- `docs/architecture/05-resource-manager.md` (revisão 1.2): fontes das sondas (§1) alinhadas a D-0058; saída do modo CRITICAL exige o STOP da fábrica liberado — apagar `.appfactory/STOP` não libera (§2, D-0062).
- `docs/architecture/01-componentes.md` §4, `11-tecnologias.md`, `13-diagramas.md` §4: psutil e nvidia-ml-py deixam de aparecer como tecnologia prevista do Resource Manager (D-0058).
- `docs/architecture/14-plano-fase-2.md`: 2.3 especificada, decisões tomadas, pronta para implementação (não implementada); obrigações da 2.4 (D-0060, D-0061) e da 2.5 (D-0066).
- `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`.
- Nenhum código, teste ou configuração alterado; `config/resources.yaml` não criado.

### Fase 2.2 — Validação pós-commit (2026-09-27) — commit `f44ac72`

#### Alterado
- `CP-0005-fase2-2.json`: `validated_commit` = `6fb983c`, estado `phase_2_2_validated`.
- `TEST_STATUS.md` (V2.2-07 a V2.2-12), `PROJECT_STATE.md`, `HANDOFF.md`, `TASK_QUEUE.md`, `COMMAND_LOG.md`, `.appfactory/job.json`.

### Fase 2.2 — Guardrails e segurança de execução (2026-09-27) — commit `6fb983c` (validado no Windows: 157 passed, 7 skipped; guardrails 21 passed, 7 skipped)

#### Adicionado
- `config/policies/protected-paths.yaml` e `config/policies/commands.yaml` (subconjunto JSON, D-0049).
- `src/appfactory/security/`: `paths.py`, `diff_guard.py`, `command_policy.py`, `guardrail_manifest.py`, `sandbox/{__init__,s1h_runner_user,docker}.py` (S1h/S2 falham fechados).
- `src/appfactory/logs/audit.py` (auditoria com cadeia de hashes), `src/appfactory/core/auth.py` (papéis/tokens em memória), `src/appfactory/toolbox/{__init__,fs,shell}.py` (Toolbox mínimo, D-0050).
- `tests/guardrails/` (I1–I7, `MANIFEST.json`, `pytest.ini` próprio), `tests/fakes/`, novos testes unitários e de integração (G22-01…G22-54; 106 testes).
- `docs/runbooks/seguranca.md`; decisões D-0055, D-0056 (P-11: fail-closed na 2.2, STOP por falha de integridade obrigatório na 2.4) e D-0057 (P-08: `core/auth.py` com escopo limitado); KI-0021 e KI-0022.

#### Alterado (aditivo; registrado em D-0055)
- `src/appfactory/jobs/manager.py` (`hold_attempt`, `record_violation`, STOP auditado), `executor.py` (STOP da fábrica em `should_stop`, `StepInterrupted`/`StepHeld`), `handlers.py` (`StepContext` ampliado), `cli/main.py` (`af guard`, `af audit`, `af guardrails`).
- `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `TEST_STATUS.md`, `COMMAND_LOG.md`, `KNOWN_ISSUES.md`, `.appfactory/job.json`; novo `CP-0005` (pronto para commit).
- Documentação: especificação da 2.2 (estado, P-08/E10, P-11), `docs/architecture/10-diretorios.md` (legenda), `docs/architecture/14-plano-fase-2.md` (obrigações da 2.4 e da fatia da API, D-0056/D-0057), D-0055 (referências a D-0056/D-0057).

#### Corrigido
- `src/appfactory/security/paths.py`: nomes curtos 8.3 do Windows no caminho literal passam a ser expandidos (`GetLongPathNameW`, sem seguir links; falha ⇒ negar) antes da decisão — falha `test_g22_07b_short_names_resolved` na 1ª validação no Windows; revalidado no Windows.

### Fase 2.2 — Especificação e decisões bloqueantes (2026-09-27) — commit `683b9e2`

#### Adicionado
- `docs/specs/fase-2.2-guardrails-e-seguranca.md` — especificação executável da Fase 2.2 (escopo, componentes, APIs, matriz G22-01…G22-54, critérios AC-01…AC-14, pendências).
- Decisões D-0048 a D-0054 (pendências bloqueantes P-01, P-02, P-03, P-05, P-06, P-07, P-15).

#### Alterado
- `docs/architecture/08-seguranca.md` (§3 formato, §5.1 lista ampliada e `config/**`, §5.2 alcance fábrica × projetos, §5.3 falha fechada e `pending`, §9 prazos do STOP), `09-autoevolucao.md` (I6, `pending`, habilitação do Evolution, lista), `10-diretorios.md`, `11-tecnologias.md`, `14-plano-fase-2.md` (2.2, 2.8, 2.9+), `15-daemon.md` (§2, §9), `01-componentes.md` (§0), `05-resource-manager.md` (§9), `README.md` da arquitetura; `AGENTS.md` (§3.15, §5).
- `DECISIONS.md`: status de D-0028, D-0029, D-0031, D-0042 remetem às novas decisões; cabeçalho da Fase 2.1 deixa de dizer "pendentes de commit".
- `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `TEST_STATUS.md`.
- Nenhum código, teste ou configuração alterado.

### Fase 2.1 — Validação pós-commit (2026-09-26) — commit `b0a80e5`

#### Alterado
- `CP-0004-fase2-1.json`: `validated_commit` = `4373c65`, estado `phase_2_1_validated`.
- `TEST_STATUS.md` (T17 e V2.1-01 a V2.1-08), `KNOWN_ISSUES.md` (KI-0018 resolvido), `PROJECT_STATE.md`, `HANDOFF.md`, `TASK_QUEUE.md`, `COMMAND_LOG.md`, `.appfactory/job.json`.

### Fase 2.1 — Fundação: Job Manager (2026-09-26) — commit `4373c65`

- Também no commit: `uv.lock` (gerado pelo `uv` no Windows do usuário).

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
