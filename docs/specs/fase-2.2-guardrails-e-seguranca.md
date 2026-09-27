# Fase 2.2 — Guardrails e segurança de execução · Especificação executável

**Status:** especificação pronta; **decisões bloqueantes aprovadas e aplicadas em 2026-09-27** (P-01→D-0048, P-02→D-0049, P-03→D-0050, P-05→D-0051, P-06→D-0052, P-07→D-0053, P-15→D-0054). Pendências não bloqueantes (P-04, P-08…P-14) continuam abertas (§9). **Nada foi implementado.**
**Base:** commit `b0a80e5` (Fase 2.1 validada, CP-0004). **Data:** 2026-09-26.
**Fontes normativas:** `AGENTS.md`, `DECISIONS.md` (D-0021, D-0022, D-0026 a D-0029, D-0031, D-0035 a D-0047), `RESOURCE_POLICY.md`, `docs/architecture/01` §0/§13/§18/§19, `04` §3–4, `05` §6/§9, `08` (inteiro), `09`, `10`, `12` §1/§6/§8/§11/§12/§14, `13` §8–9, `14`, `15` §7–10.

Convenções deste documento: **[ARQ]** = exigido pela arquitetura aprovada · **[2.1]** = já existe no código · **[PROP]** = proposta desta especificação que precisa de aprovação (não é requisito novo, é a forma de cumprir um requisito existente) · **P-NN** = pendência/decisão necessária (§9).

---

## 1. Escopo exato

### 1.1 Princípio

A Fase 2.2 implementa **somente código confiável que decide e bloqueia** (política, verificação e trilha de auditoria) e a **suíte de guardrails**. Tudo que exige mudar o sistema operacional (usuário `afrunner`, ACLs, Job Objects, Docker) continua na fatia 2.6/2.4 (`14-plano-fase-2.md`); na 2.2 esses mecanismos ficam **especificados como contrato** e as implementações de sandbox **falham fechadas** (recusam executar). Consequência: ao fim da 2.2, **nenhum caminho de produção executa código não confiável** — toda tentativa termina em `BLOCKED(sandbox_unavailable)`/`WAITING(resources)`, nunca em execução como usuário principal (08 §0, §4.4).

### 1.2 Dentro do escopo (implementar na 2.2, após aprovação)

| # | Entrega | Base |
| --- | --- | --- |
| E1 | `config/policies/protected-paths.yaml` com a lista de 08 §5.1 (ela mesma protegida) + carregador e *matcher* | [ARQ] 08 §5.1, 14 (2.2) |
| E2 | Política de caminhos (camada S0 do Toolbox): normalização, resolução de symlink/junction, regras de leitura/escrita/criação/remoção/renomeação por área | [ARQ] 08 §4.1 S0, §5.3(1), §6; 04 §3 |
| E3 | Verificador de diff de caminhos protegidos (`git diff --name-status --find-renames`), com rejeição automática | [ARQ] 08 §5.3(3), 09 §2(4), 14 (2.2) |
| E4 | `CommandPolicy`: allowlist, comandos negados, argumentos, `cwd`, timeout obrigatório, sem shell, ambiente limpo, classificação npm/pip | [ARQ] 08 §2, §4.3, §7 |
| E5 | Contrato `Sandbox` + seletor S1h/S2 (08 §4.4, nunca rebaixar) + especificação executável do lançamento S1h e S2 **como dados**; `run()` das duas implementações falha fechado | [ARQ] 08 §4, 12 §6; [PROP] fail-closed |
| E6 | Trilha de auditoria `audit.jsonl` com `prev_hash` + verificação; STOP (acionar/liberar) e violações auditados | [ARQ] 08 §9–10, 09 I1 |
| E7 | Integração com o Job Manager: bloqueio por violação (`BLOCKED(policy_violation)`), espera por sandbox (`WAITING(resources)`), STOP de job/fábrica interrompendo execução, registro do resultado | [ARQ] 08 §3, §4.4, §9; [2.1] |
| E8 | Toolbox mínimo **somente** para os caminhos de execução e arquivo usados pela 2.2 (`toolbox/fs.py`, `toolbox/shell.py`) | [ARQ] 10; escopo fixado por **D-0050** (só `fs.py` e `shell.py`; resto na 2.8) |
| E9 | `tests/guardrails/` I1–I7 com `pytest.ini` próprio, executada pelo comando fixo com `--noconftest` | [ARQ] 08 §5.3(4), 09 §1, 14 (2.2); pendências no manifesto conforme **D-0048** |
| E10 | Matriz de autorização por papel (`user`/`runner`/`ui`) e emissão/verificação de token **em memória** (sem API, sem arquivo com ACL) | [ARQ] 08 §8, 12 §11; **opcional, depende de P-08** |
| E11 | CLI mínima: `af guard check-diff`, `af guard check-path`, `af audit verify`, `af guardrails run` | [PROP] necessária para os critérios de aceite automáticos |

### 1.3 Fora do escopo (proibido nesta fase)

Criar o usuário `afrunner` · alterar ACLs (`security/acl.py` fica para a 2.6) · criar Job Objects (`jobs/jobobjects.py`, 2.4) · instalar/usar Docker · alterar configuração do Windows ou do Ollama · executar código gerado por agentes (inclusive em testes) · daemon, API local (FastAPI, D-0042), escritor único (KI-0020) · aprovações interativas `af approve` e `approvals.yaml` (2.6) · keyring/segredos reais (2.6) · Resource Manager e `config/resources.yaml` (2.3) · rollback (2.7) · `permissions.yaml` por agente e agentes (2.8) · rede/navegador/allowlist de domínios · gitleaks/pip-audit (Security Agent, 2.9+) · provedores pagos · credenciais reais · commit/push.

### 1.4 Cobertura parcial declarada das invariantes (09 §1)

| Inv. | Coberto na 2.2 | Pendente (fatia) |
| --- | --- | --- |
| I1 logs/auditoria | eventos append-only [2.1], `audit.jsonl` com cadeia (E6), STOP e violações auditados | rotação/arquivamento (2.4) |
| I2 checkpoints | criação/restauração/imutabilidade [2.1] exercitadas por guardrail | checkpoint de task/marco (2.7) |
| I3 rollback | — | 2.7 |
| I4 limites | especificação S1h/S2 ≤ tetos do `RESOURCE_POLICY.md`; 1 RUNNING/projeto [2.1] | `resources.yaml`, modos (2.3) |
| I5 segurança | caminhos protegidos, diff guard, CommandPolicy, redação, ambiente limpo, seleção de sandbox, separação de tokens (se P-08) | ACL do `afrunner` e S1h/S2 reais (2.6) |
| I6 STOP | STOP persistente, arquivo não libera, liberação só confirmada, interrupção de execução com `terminate` ≤ T0 + 30 s e fim ≤ T0 + 40 s, T0 persistido (D-0054; contrato + dublê de teste) | Job Object mata tudo (2.4/2.6); passo confiável em processo que ignore `should_stop` (KI-0019) |

Regra (D-0048): as invariantes/partes pendentes ficam `pending:<fatia>` em `tests/guardrails/MANIFEST.json`. **`pending` nunca significa aprovação**: nenhum portão que dependa dos guardrails aprova com pendências, e o **Evolution só pode ser habilitado quando I1–I7 estiverem todas `active`**.
| I7 aprovação humana | liberar STOP exige confirmação [2.1]; ações R2/R3 negadas por falta de aprovação (fail-closed) | `af approve`, orçamento pago = 0 (2.5/2.6) |

---

## 2. Componentes

| Componente | Arquivo | Responsabilidade | Confiança / proteção |
| --- | --- | --- | --- |
| Lista protegida | `config/policies/protected-paths.yaml` | Padrões de 08 §5.1, incluindo `config/**` (D-0052) e o núcleo do Job Manager/CLI (D-0051); formato subconjunto JSON (D-0049) | [P] |
| Política de caminhos | `src/appfactory/security/paths.py` | `normalize_rel`, `ProtectedPaths`, `PathScope`, `check_access` | [P] (`security/**`) |
| Verificador de diff | `src/appfactory/security/diff_guard.py` | `check_diff` sobre `git diff --raw -z --find-renames` | [P] |
| Política de comandos | `src/appfactory/security/command_policy.py` + `config/policies/commands.yaml` | Decide permitido/negado, risco, sandbox; ambiente limpo | [P] |
| Sandbox (contrato + seleção) | `src/appfactory/security/sandbox/__init__.py` | `Sandbox` (12 §6), `SandboxRequest`, `RunResult`, `select_sandbox` | [P] |
| S1h (especificação) | `src/appfactory/security/sandbox/s1h_runner_user.py` | `S1hLaunchSpec` (dados); `run()` → `SandboxUnavailable` | [P] |
| S2 (especificação) | `src/appfactory/security/sandbox/docker.py` | `DockerSpec` (argumentos); `run()` → `SandboxUnavailable` | [P] |
| Auditoria | `src/appfactory/logs/audit.py` | `append`, `verify_chain` | [P] (`logs/**`) |
| Autorização (opcional) | `src/appfactory/core/auth.py` | papéis, matriz de rotas, tokens em memória | [P] — P-08 |
| Toolbox mínimo | `src/appfactory/toolbox/fs.py`, `toolbox/shell.py` | operações de arquivo guardadas; `exec_untrusted` (política → seleção → journal → sandbox → resultado) | [P] — D-0050 |
| Integração Job Manager | `src/appfactory/jobs/manager.py`, `executor.py`, `handlers.py` (mudanças aditivas) | `hold_attempt`, STOP da fábrica no `should_stop`, auditoria do STOP, contexto de execução | [P] desde D-0051 — alterados só em sessão de desenvolvimento dirigida pelo usuário (`AGENTS.md` §3.15), com registro |
| Guardrails | `tests/guardrails/**` | I1–I7 + manifesto | [P] |
| CLI | `src/appfactory/cli/main.py` | subcomandos `guard`, `audit`, `guardrails` | — |

### 2.1 Regras de arquivo (E2) — por área e operação

Caminhos avaliados **depois** da normalização (§5.1) e comparados **tanto no caminho literal quanto no caminho final resolvido**; qualquer um negado ⇒ negado. Padrão: **negar**.

| Área | READ | CREATE / WRITE | DELETE | RENAME |
| --- | --- | --- | --- | --- |
| Worktree da task (`workspaces/_worktrees/<p>/<task>/`) | sim, dentro de `reads` (padrão: todo o worktree) | só se o caminho estiver coberto por `writes` (mesma semântica de `locks.normalize_spec`/`overlaps`, 04 §3) **e** não for protegido | igual a WRITE | origem **e** destino como WRITE |
| Worktree de integração (`_integration-<job>/`) | sim | não | não | não |
| Diretório do job (`.appfactory/jobs/<job>/`) do próprio job | sim | só `tmp/<attempt>/**` da própria tentativa, `artifacts/**`, `research/**` | só `tmp/<attempt>/**` da própria tentativa (08 §6; `FactoryPaths.is_factory_tmp`) | só dentro de `tmp/<attempt>/**` |
| `quarantine/` do job | não | só o componente de navegador (fora da 2.2) | não | não |
| Outros jobs, `.appfactory/{state,logs,runtime,locks,cache,checkpoints}/`, `.appfactory/job.json`, `.appfactory/STOP` | **não** | **não** | **não** | **não** |
| Caminhos protegidos (08 §5.1) — só no repositório da fábrica (D-0053) | só se estiverem em `reads` (ex.: Evolution) | **não** | **não** | **não** (nem como origem nem como destino) |
| Credenciais: `.env*` (exceto `.env.example`), `*.key`, `secrets/**`, `credentials*.json`, `.appfactory/runtime/tokens/**`, perfil do usuário | **não** | **não** | **não** | **não** |
| Fora de `D:\Claude\app-factory`, qualquer caminho em `C:` | **não** (R2/R3 exigiriam aprovação, inexistente na 2.2) | **não** | **não** | **não** |
| Criar symlink/junction/hardlink | — | **não** (operação inexistente no Toolbox) | — | — |

Regras adicionais de normalização (Windows): recusar componente com `:` (fluxos alternativos NTFS), nomes terminados em `.` ou espaço, nomes de dispositivo (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`, com ou sem extensão), prefixos `\\?\`, `\\.\` e UNC; resolver nomes curtos 8.3 pelo caminho final; comparação sem diferenciar maiúsculas/minúsculas; separador `/`. Escrita em arquivo com `st_nlink > 1` é negada (hardlink para fora do escopo).

Projetos gerados (D-0053): no worktree de um projeto, `pytest.ini`, `conftest.py`, `.gitignore` e docs do projeto seguem só a regra de `writes`; `.git/**` e `.appfactory/**` do projeto são sempre negados. O tipo de repositório vem de `classify_repo` (§5.1), nunca da TaskSpec; indeterminado ⇒ fábrica.

### 2.2 Código não confiável — o que, onde, permissões, interrupção, resultado

| Aspecto | Especificação |
| --- | --- |
| O que é | 08 §0: código escrito/alterado por agente (inclusive testes e scripts), código dos projetos gerados, dependências e seus scripts, conteúdo externo, branch `evo/*` [ARQ] |
| Onde executa | Somente S1h ou S2 via `toolbox/shell.exec_untrusted`. Na 2.2 as duas implementações recusam (`SandboxUnavailable`) ⇒ nada executa [PROP fail-closed] |
| Permissões | Decididas antes da execução: `CommandPolicy` (executável, argumentos, `cwd`, timeout, risco) + política de caminhos + seleção de sandbox. R2 sem pré-autorização ⇒ negado com `approval_required` (não há aprovações na 2.2); R3 ⇒ sempre negado com `needs_human` |
| Seleção S1h × S2 | §2.4 |
| Interrupção | `CancelToken` alimentado por: STOP do job, STOP da fábrica, perda de posse (*fencing*), timeout; sondado a cada ≤ 1 s. Prazos (D-0054) contados desde o **T0 persistido** (`factory_stop.set_at`, `jobs.stop_requested_at` ou, em cancelamento, `jobs.cancelled_at`): `terminate` em ≤ T0 + 30 s e matar a árvore em ≤ T0 + 40 s (na 2.6: `TerminateJobObject` e conferir 0 processos ativos); prazo efetivo = menor entre "T0 + 30 s" e "detecção + 30 s" em tempo ativo. Para perda de posse e timeout, T0 = instante da detecção. O sandbox **não** coopera; quem cobra os prazos é o código confiável supervisor |
| Registro do resultado | `RunResult` (§5.4) gravado em `journal_result` (SQLite, cercado por *fencing*), linha no log JSONL do job, stdout/stderr **redigidos** e truncados em `.appfactory/jobs/<job>/artifacts/runs/<attempt>/<n>.{out,err}`, auditoria se R2+ ou violação |
| Recuperação | Execução é passo com efeito colateral (`journal_intent` antes): queda sem resultado ⇒ `BLOCKED(needs_human)` (D-0046, sem regra nova); STOP/timeout/erro ⇒ resultado gravado com `outcome` correspondente, então a retomada reexecuta o passo em nova tentativa |

### 2.3 S1h detalhado (especificação para a 2.6; na 2.2 só `S1hLaunchSpec` como dados)

| Item | Valor/regra | Base |
| --- | --- | --- |
| Usuário | conta local padrão `afrunner` (nome configurável), criada pelo **usuário humano** (R3); senha aleatória só no Credential Manager do usuário principal, referência `secret://sandbox/afrunner` | 08 §2, §4.2(1) |
| Lançamento | `CreateProcessWithLogonW`, `CREATE_SUSPENDED` → atribuir ao Job Object da task (aninhado no raiz `AppFactory-afd`) → `ResumeThread`. **Nunca** `LOGON_NETCREDENTIALS_ONLY` (rodaria localmente como o usuário principal). Uso de perfil (`LOGON_WITH_PROFILE` × sem perfil) decidido na PoC | 08 §4.2(2), 15 §7; KI-0014 |
| Job Object | `KILL_ON_JOB_CLOSE`; `JOB_MEMORY` e `PROCESS_MEMORY` = 1,5 GB (FG) / 3 GB (BG); `ACTIVE_PROCESS` = 32; `CPU_RATE_CONTROL` *hard cap* 50% (FG) / 80% (BG); `PRIORITY_CLASS` BELOW_NORMAL (IDLE em BATTERY); **sem** `BREAKAWAY_OK`/`SILENT_BREAKAWAY_OK` | 08 §4.2(3), `RESOURCE_POLICY.md` tetos |
| Sem área de transferência / UI | `JOB_OBJECT_UILIMIT_READCLIPBOARD`, `WRITECLIPBOARD`, `DESKTOP`, `GLOBALATOMS`, `HANDLES`, `SYSTEMPARAMETERS`, `DISPLAYSETTINGS`, `EXITWINDOWS` | 08 §4.2(3) |
| Tokens separados | processo S1h **sem** token da API, sem segredos em ambiente/arquivo/argumento; não fala com o daemon; só handles de stdin/stdout/stderr | 08 §4.2(6), §8 |
| Ambiente | allowlist: `PATH` mínimo, `SYSTEMROOT`, `TEMP`/`TMP` = tmp da tentativa, `LANG` | 08 §2 |
| Permissões de FS | Deny herdado para `afrunner` a partir de `D:\Claude\app-factory`; Allow Modify só no worktree da task e no tmp da tentativa (revogado ao fim); leitura no ambiente Python/Node de execução; nunca `.appfactory\`, `config\`, `src\`, `tests\guardrails\`, `docs\`, estado da raiz, perfil do usuário principal | 08 §4.2(4); KI-0016 |
| Bloqueio de comandos | antes do lançamento, pela `CommandPolicy` (§5.3); dentro do sandbox o bloqueio real é o do SO (usuário padrão + ACL + Job Object) | 08 §0, §7 |
| npm/pip | `npm ci --ignore-scripts` (lockfile existente) e `pip install --only-binary=:all: --require-hashes -r <lock>` ⇒ S1h, R2; qualquer coisa com scripts/sem hashes/alterando lockfile ⇒ S2; global ⇒ proibido | 08 §4.3 |
| Scripts | `python <script>`, `node <script>`, `pytest`, `ruff` do projeto ⇒ S1h salvo gatilho de S2 | 08 §4.1 |
| Timeouts | passo 10 min, suíte de testes 15 min, build 30 min, comando 5 min (padrões) | 05 §6 |
| Rede | **não isolada** (risco aceito KI-0015) ⇒ tarefas que exigem isolamento vão para S2 | 08 §4.2(5) |
| PoC (2.6) | 15 §10 (a)–(c) + ACL negando fora do worktree + clipboard bloqueado + sem acesso ao cofre do usuário principal + handles herdados só os de E/S | KI-0014, KI-0016 |

### 2.4 Critérios de S2 e seleção S1h × S2

`select_sandbox` [ARQ 08 §4.4] retorna `S2` se **qualquer** condição for verdadeira; senão `S1h`:

1. `network_isolation: required` na TaskSpec, ou rede além dos registros permitidos;
2. instalação/compilação que executa scripts (tabela 08 §4.3), inclusive `npm install` que altere lockfile e instalação sem hashes;
3. código de origem desconhecida (repositório baixado, anexo, exemplo da web);
4. servidores (banco, filas) do projeto gerado;
5. build de release;
6. task marcada `untrusted_high`.

Disponibilidade: S2 exigido e Docker indisponível ou sem RAM (admissão própria ≥ reserva do modo + 3 GB, 05 §4) ⇒ `WAITING(resources)` ou `BLOCKED` — **nunca** S1h. S1h exigido e indisponível ⇒ ver P-09. Na 2.2 ambos estão indisponíveis por definição.

`DockerSpec` [ARQ]: `docker run --rm --network none --user <uid não root> --memory <m> --cpus <c> --label appfactory.task=<id>`, **só** o worktree montado, sem `docker.sock`; rede apenas na etapa de instalação quando exigida (08 §4.3). Endurecimentos extras (`--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit`, raiz somente leitura) e política de imagem **não estão na arquitetura** ⇒ P-10.

### 2.5 STOP — integração sem enfraquecer o que existe

O STOP da 2.1 permanece como está: `factory_stop` persistido antes de tudo; flag em memória; arquivo só aciona; liberação só com `resume_factory(confirmed=True)` + código digitado na CLI; `RUNNING → STOPPING → STOPPED`; `PAUSED(factory_stop)`. A 2.2 **acrescenta**:

1. `exec_untrusted` consulta o STOP da fábrica (`check_stop_file()` + `factory_stop_state()`) antes de iniciar; ativo ⇒ não executa.
2. `StepContext.should_stop` passa a incluir o STOP da fábrica (hoje só STOP do job e perda de posse — `executor.py` linha 73) e é consultado pelo laço de espera do sandbox a cada ≤ 1 s.
2a. O laço de espera cobra os prazos de D-0054 a partir do T0 persistido (`terminate` ≤ T0 + 30 s, encerramento total ≤ T0 + 40 s); a detecção só antecipa a cooperação, nunca adia os prazos.
3. STOP do job durante execução ⇒ cancelamento da execução ⇒ `_graceful_stop` existente (checkpoint `stop`, `finish_stop`).
4. STOP da fábrica durante execução ⇒ cancelamento ⇒ `_pause_factory` existente (checkpoint `pause`, `PAUSED(factory_stop)`).
5. `stop_factory` e `resume_factory` gravam também em `audit.jsonl` (08 §9 "Auditoria").
6. Violação de integridade dos próprios guardrails (lista protegida ausente/inválida, cadeia de auditoria quebrada na partida) ⇒ `stop_factory(reason="guardrail", actor="system")` — ver P-11.

---

## 3. Dependências

| Dependência | Tipo | Situação |
| --- | --- | --- |
| Job Manager 2.1 (`jobs/*`, `checkpoints/service.py`, `core/stop.py`, `core/paths.py`) | código | pronto (CP-0004) |
| `git` no PATH (Windows: Git para Windows; VM: 2.34.1) | ferramenta confiável | disponível; caminho absoluto a fixar na configuração (KI-0012) |
| Python 3.10+ (VM) / 3.13 via `uv` (Windows) | runtime | disponível |
| pytest (só dev, `dependency-groups.dev`) | teste | Windows sim; VM não (PyPI bloqueado) — testes compatíveis com `unittest` |
| Parser de YAML | biblioteca | **não existe na biblioteca padrão** ⇒ arquivos `.yaml` no subconjunto JSON lidos com `json` (D-0049) |
| Resource Manager (admissão S2, modo FG/BG/BATTERY) | fatia 2.3 | ausente ⇒ entra como parâmetro nos testes |
| Daemon, Job Object raiz, API (tokens reais) | 2.4 / D-0042 | ausentes ⇒ P-08, KI-0019 |
| `afrunner`, ACLs, Docker | 2.6 (usuário, R3) | ausentes ⇒ sandboxes falham fechados |
| Aprovações (`af approve`) | 2.6 | ausentes ⇒ R2/R3 negados |

Nenhuma dependência de execução nova (D-0042, D-0049).

---

## 4. Arquivos a criar / modificar

### 4.1 Criar

| Arquivo | Conteúdo |
| --- | --- |
| `config/policies/protected-paths.yaml` | lista 08 §5.1 revisada (D-0051, D-0052), no subconjunto JSON, sem comentários (D-0049) |
| `config/policies/commands.yaml` | allowlist `python, uv, pytest, ruff, node, npm, npx, git`; negações de 08 §7; limites de timeout (05 §6) |
| `src/appfactory/security/__init__.py` | — |
| `src/appfactory/security/paths.py` | E1/E2 |
| `src/appfactory/security/diff_guard.py` | E3 |
| `src/appfactory/security/command_policy.py` | E4 |
| `src/appfactory/security/sandbox/__init__.py` | contrato + `select_sandbox` |
| `src/appfactory/security/sandbox/s1h_runner_user.py` | `S1hLaunchSpec`, `S1hSandbox.run` → `SandboxUnavailable` |
| `src/appfactory/security/sandbox/docker.py` | `DockerSpec`, `DockerSandbox.run` → `SandboxUnavailable` |
| `src/appfactory/logs/audit.py` | E6 |
| `src/appfactory/toolbox/__init__.py`, `toolbox/fs.py`, `toolbox/shell.py` | E8 (D-0050) |
| `src/appfactory/core/auth.py` | E10 (se P-08 aprovar) |
| `tests/guardrails/__init__.py`, `tests/guardrails/pytest.ini` | `[pytest]` com `pythonpath = ../../src` e `addopts = -p no:cacheprovider` |
| `tests/guardrails/MANIFEST.json` | invariante → arquivo → `active`/`pending:<fatia>` + módulo esperado (D-0048) |
| `tests/guardrails/test_logging_invariants.py` (I1), `test_checkpoint_invariants.py` (I2), `test_rollback_invariants.py` (I3), `test_resource_limits.py` (I4), `test_security_invariants.py` (I5), `test_stop_mechanisms.py` (I6), `test_human_approval.py` (I7), `test_manifest.py` | nomes de 09 §1 |
| `tests/unit/test_paths_policy.py`, `test_diff_guard.py`, `test_command_policy.py`, `test_sandbox_selection.py`, `test_audit.py`, `test_auth.py` (P-08) | unidade |
| `tests/integration/test_exec_pipeline.py`, `test_guardrails_command.py`, `test_cli_guard.py` | integração |
| `tests/fakes/sandbox.py` | `FakeSandbox` — **só em `tests/`**, nunca registrado em `src/` |
| `docs/runbooks/seguranca.md` | operação: verificar diff, verificar auditoria, rodar guardrails |

### 4.2 Modificar (aditivo; nenhuma semântica da 2.1 muda)

Desde D-0051, `jobs/manager.py`, `executor.py`, `handlers.py` e `cli/main.py` são caminhos protegidos: estas mudanças aditivas só podem ser feitas em sessão de desenvolvimento dirigida pelo usuário (`AGENTS.md` §3.15), registradas em `DECISIONS.md`, e nunca por agentes em execução ou pelo Evolution.

| Arquivo | Mudança |
| --- | --- |
| `src/appfactory/jobs/manager.py` | `hold_attempt(attempt_id, target, reason)`; auditoria em `stop_factory`/`resume_factory`; evento `security.violation` |
| `src/appfactory/jobs/executor.py` | `should_stop` inclui STOP da fábrica; `StepContext` recebe `job_id`, `attempt_id`, manager e escopo (sem novos estados) |
| `src/appfactory/jobs/handlers.py` | campos novos em `StepContext`; **nenhum handler novo em produção** (D-0047) |
| `src/appfactory/cli/main.py` | subcomandos de E11 |
| `pytest.ini` | nenhuma mudança necessária (`testpaths = tests` já inclui `tests/guardrails`) |
| `docs/architecture/**`, `DECISIONS.md`, `AGENTS.md` | decisões bloqueantes já aplicadas (D-0048 a D-0054, 2026-09-27); novas mudanças só com as decisões das pendências restantes |
| Arquivos de estado | ao fim da implementação (AGENTS §4) |

---

## 5. APIs e interfaces

### 5.1 Política de caminhos (`security/paths.py`)

```python
class Op(str, Enum): READ = "read"; CREATE = "create"; WRITE = "write"; DELETE = "delete"; RENAME = "rename"

class PathRejected(ValueError): ...           # caminho malformado (.., ADS, dispositivo, UNC, fora da base)

@dataclass(frozen=True)
class Decision:
    allowed: bool; op: Op; path: str; rule: str; reason: str   # rule: "writes", "protected:<padrão>", "credential", "outside_root", ...

@dataclass(frozen=True)
class PathScope:
    factory_root: Path; job_id: str; attempt_id: str
    worktree: Path | None; integration_worktree: Path | None
    reads: tuple[str, ...]; writes: tuple[str, ...]            # formato de locks.normalize_spec
    repo_kind: Literal["factory", "project"]                    # D-0053: sempre preenchido por classify_repo, nunca pela TaskSpec

class ProtectedPaths:
    @classmethod
    def load(cls, root: Path) -> "ProtectedPaths": ...          # arquivo ausente/inválido => erro (fail-closed)
    def match(self, rel_path: str) -> str | None: ...           # padrão que casou; sem diferenciar maiúsculas
    patterns: tuple[str, ...]

def normalize_rel(path: str | Path, base: Path) -> str: ...
def classify_repo(repo: Path, factory_root: Path) -> Literal["factory", "project"]: ...
    # D-0053: `git rev-parse --git-common-dir` resolvido == .git da fábrica => "factory"; erro/dúvida => "factory"
def load_policy_file(path: Path) -> dict: ...   # D-0049: só JSON válido (json.loads); qualquer outra sintaxe => erro
def check_access(op: Op, path: str | Path, scope: PathScope, protected: ProtectedPaths,
                 dest: str | Path | None = None) -> Decision: ...
```

Semântica de padrões: `**` = qualquer profundidade; `*.pth` e `**/conftest.py` casam em qualquer nível; padrões relativos à raiz da fábrica e aplicados só a `repo_kind="factory"` (D-0053).

### 5.2 Verificador de diff (`security/diff_guard.py`)

```python
@dataclass(frozen=True)
class DiffEntry: status: str; path: str; old_path: str | None; old_mode: str; new_mode: str
@dataclass(frozen=True)
class Violation: path: str; status: str; rule: str; detail: str   # rule: protected:<p> | symlink | gitlink | pytest_config
@dataclass(frozen=True)
class DiffVerdict: ok: bool; base: str; head: str; entries: tuple[DiffEntry, ...]; violations: tuple[Violation, ...]; error: str | None

def check_diff(repo: Path, base: str, head: str, protected: ProtectedPaths,
               factory_root: Path) -> DiffVerdict: ...   # repo_kind = classify_repo(repo, factory_root) (D-0053)
```

Execução confiável de `git -c core.quotepath=off diff --raw -z --find-renames <base>...<head>` (com `--find-copies`). Rejeita: caminho protegido em qualquer lado de A/M/D/R/C/T; modo `120000` (symlink) ou `160000` (gitlink); `pyproject.toml` que passe a conter `[tool.pytest`. Erro do git ⇒ `ok=False` (fail-closed). Nenhum código do candidato é executado. Em `repo_kind="project"` (D-0053) rejeita: `.git/**`, `.appfactory/**`, modos `120000`/`160000`; a lista de 08 §5.1 não se aplica; o escopo `writes` é verificado pelo Toolbox/integrador.

### 5.3 CommandPolicy (`security/command_policy.py`)

```python
@dataclass(frozen=True)
class CommandRequest:
    argv: tuple[str, ...]; cwd: Path; timeout_s: int | None
    trust: Literal["trusted", "untrusted"]; kind: Literal["shell", "tests", "build", "install", "script"]
    flags: frozenset[str]   # network_isolation_required, needs_network, unknown_origin, server, release_build, untrusted_high

@dataclass(frozen=True)
class CommandDecision:
    allowed: bool; risk: Literal["R0", "R1", "R2", "R3"]; sandbox: Literal["S0", "S1h", "S2"] | None
    rule: str; reason: str; needs_human: bool

def evaluate(req: CommandRequest, scope: PathScope, policy: "CommandPolicyConfig") -> CommandDecision: ...
def clean_env(sandbox: str, tmp_dir: Path, path_entries: list[str]) -> dict[str, str]: ...
```

Regras: `argv` lista não vazia (string ⇒ recusa; sem `shell=True`); executável (nome base, minúsculas, sem `.exe`) na allowlist; interpretadores de shell (`cmd`, `powershell`, `pwsh`, `bash`, `sh`, `wsl`) negados; negações de 08 §7; `git` só `status, diff, add, commit, log, show` e sempre `S0` (confiável, executado pelo Toolbox); timeout obrigatório e ≤ máximo da classe; `cwd` dentro do worktree; `untrusted` nunca recebe `S0`.

### 5.4 Sandbox (`security/sandbox/`)

```python
class SandboxUnavailable(RuntimeError): ...

@dataclass(frozen=True)
class Limits: memory_bytes: int; cpu_rate_pct: int; max_processes: int; priority: str; timeout_s: int

@dataclass(frozen=True)
class SandboxChoice: kind: Literal["S1h", "S2"] | None; hold: Literal["WAITING", "BLOCKED"] | None; reason: str

@dataclass
class RunResult:
    outcome: Literal["ok", "failed", "timeout", "killed_stop", "killed_factory_stop", "killed_lease",
                     "limit_memory", "limit_processes", "error"]
    exit_code: int | None; duration_ms: int; sandbox: str; limits: Limits
    stdout_ref: str | None; stderr_ref: str | None; truncated: bool; detail: str | None

class Sandbox(Protocol):                                   # 12 §6 (versão síncrona nesta fase)
    kind: str
    def available(self) -> tuple[bool, str]: ...
    def run(self, argv: list[str], cwd: Path, env: dict[str, str], limits: Limits,
            cancel: Callable[[], "StopSignal | None"]) -> RunResult: ...
    # StopSignal(reason, t0, terminate_at, kill_at) em tempo ativo; o sandbox cobra terminate_at/kill_at (D-0054)

def select_sandbox(decision: CommandDecision, flags: frozenset[str],
                   s1h: Sandbox, s2: Sandbox, s2_admitted: bool) -> SandboxChoice: ...
def s1h_launch_spec(mode: str, battery: bool, tmp_dir: Path, worktree: Path) -> "S1hLaunchSpec": ...
def docker_spec(task_id: str, worktree: Path, mode: str, install_step: bool) -> "DockerSpec": ...
```

### 5.5 Auditoria (`logs/audit.py`)

```python
def append(path: Path, record: dict) -> str: ...     # adiciona seq, ts, prev_hash, hash; redige; flush+fsync; trava de arquivo
def verify_chain(path: Path) -> tuple[bool, int | None, str]: ...   # (ok, índice da 1ª linha inválida, motivo)
```

`hash = sha256(canonical(record sem "hash"))`; primeira linha com `prev_hash = "0"*64`. Tipos: `stop.set`, `stop.released`, `security.violation`, `diff.rejected`, `command.denied` (R2+), `sandbox.unavailable`.

### 5.6 Toolbox mínimo (`toolbox/`, D-0050)

```python
def fs_read(scope, protected, path) -> bytes
def fs_write(scope, protected, path, data: bytes) -> None        # escrita atômica (tmp + rename)
def fs_delete(scope, protected, path) -> None
def fs_rename(scope, protected, src, dst) -> None
def exec_untrusted(ctx: StepContext, req: CommandRequest, sandboxes, policy) -> RunResult
```

Pipeline de `exec_untrusted`: STOP da fábrica? → `evaluate` → `select_sandbox` → (violação/indisponível ⇒ `hold_attempt`) → `journal_intent` → `sandbox.run(cancel=…)` (prazos do T0 persistido, D-0054) → redigir/gravar saídas → `journal_result` → log/auditoria. Violação de caminho: 1ª ⇒ negar + `security.violation`; reincidência ⇒ `BLOCKED(policy_violation)` (P-12).

### 5.7 Autorização (`core/auth.py`, P-08)

```python
class Role(str, Enum): USER = "user"; RUNNER = "runner"; UI = "ui"
@dataclass(frozen=True)
class Principal: role: Role; attempt_id: str | None; job_id: str | None; expires_active_ms: int | None
class TokenRegistry:                                  # só em memória; guarda sha256 do token
    def mint(self, principal: Principal) -> str: ...  # secrets.token_urlsafe(32)
    def verify(self, token: str, now_active_ms: int) -> Principal: ...   # hmac.compare_digest; expirado => erro
def authorize(p: Principal, method: str, route: str, target_job: str | None, confirmation_ok: bool) -> bool: ...
```

Matriz = 12 §11. `POST /stop`: qualquer papel. `POST /stop/release` e `POST /approvals/{id}`: só `user` **e** `confirmation_ok`. `runner`: só o próprio job. S1h/S2: nenhum token (verificado no ambiente do `S1hLaunchSpec`/`DockerSpec`).

### 5.8 APIs do Job Manager consumidas (2.1) — nada duplicado

| API existente | Uso na 2.2 |
| --- | --- |
| `claim`, `heartbeat` (retorna `stop`/`factory_stop`), *fencing* (`LeaseLost`) | tentativa dona da execução; cancelamento por perda de posse |
| `save_checkpoint(kind="step"/"stop"/"pause")`, `latest_valid_checkpoint`, `list_checkpoints` | checkpoint depois do passo de execução; guardrail I2 |
| `journal_intent`, `journal_result` | registro do resultado da execução (idempotência, D-0046) |
| `fail_attempt(error, fatal)` | falha da execução (recuperável/fatal) |
| `record_validation`, `complete` | inalterados |
| `request_stop`, `finish_stop`, `pause_for_factory_stop`, `resume`, `cancel` | STOP de job e da fábrica durante execução |
| `stop_factory`, `resume_factory(confirmed)`, `check_stop_file`, `factory_stop_state`, `refresh_factory_stop`, `factory_stop_flag` | STOP persistente; guardrail I6 |
| `acquire_locks`/`release_locks`, `locks.normalize_spec`/`overlaps` | semântica de `writes` na política de caminhos |
| `history`, `store.emit`, `store.check_database`, triggers de imutabilidade | eventos `security.violation`; guardrails I1/I2 |
| `recover` | recuperação após interrupção durante execução |
| `FactoryPaths.job_tmp`, `is_factory_tmp`, `stop_file`, `job_log` | áreas de trabalho e limpeza |
| `Executor.run`, `StepContext`, `HANDLERS` | handler de teste registrado só nos testes |
| `logs.redaction.redact`, `logs.jsonlog.append_jsonl` | redação e log do job |

**Única API nova do Job Manager:** `hold_attempt(attempt_id, target: Literal["BLOCKED","WAITING"], reason: str)` — cercada por *fencing*, usa `_transition` e `_close_attempt` existentes, transições já permitidas (`RUNNING → BLOCKED`, `RUNNING → WAITING`), libera locks; **nenhum estado, tabela, checkpoint, lease, lock ou STOP novo**.

---

## 6. Matriz de testes

Legenda de ambiente: todos rodam em Linux (unittest) e Windows (`uv run pytest`), salvo indicação. "Dublê" = `FakeSandbox` de `tests/fakes/` (código confiável do teste; nenhum código de agente é executado).

### A. Acesso a arquivos (permitido/negado)

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G22-01 | Leitura permitida | worktree temporário; `reads=["**"]` | `check_access(READ, "src/a.py")` | `allowed=True` |
| G22-02 | Escrita permitida dentro de `writes` | `writes=["src/api/**"]` | `WRITE "src/api/h.py"` | `allowed=True`, `rule="writes"` |
| G22-03 | Escrita fora de `writes` negada | idem | `WRITE "src/db/x.py"` | `allowed=False`, `rule="writes"` |
| G22-04 | `..` recusado | idem | `WRITE "../../AGENTS.md"`, `"src/../../x"` | `PathRejected` |
| G22-05 | Absoluto/UNC/C: recusado | idem | `C:\Windows\x`, `/etc/passwd`, `\\?\D:\x`, `\\srv\s\x` | negado `outside_root` |
| G22-06 | Symlink/junction para fora | link no worktree → `config/` (junction via `_winapi.CreateJunction` no Windows; symlink no Linux; *skip* com motivo se o SO não permitir) | `WRITE "link/x.yaml"` | negado (caminho resolvido protegido/fora) |
| G22-07 | Truques de nome do Windows | — | `a.txt:evil`, `AGENTS.md.`, `NUL`, `con.txt`, `CONFIG/POLICIES/x.yaml` | recusado ou normalizado e negado |
| G22-08 | Hardlink | arquivo com `st_nlink=2` dentro de `writes` | `WRITE` | negado `hardlink` |
| G22-09 | Remoção por área | tmp da tentativa A, tmp da tentativa B, arquivo em `writes`, arquivo fora | `DELETE` em cada | permitido só tmp(A) e dentro de `writes` |
| G22-10 | Renomeação | origem em `writes`, destino protegido/fora | `RENAME` | negado |
| G22-11 | Estado operacional inacessível | — | qualquer op em `.appfactory/state/factory.db`, `logs/audit.jsonl`, `runtime/**`, `STOP`, outro job | negado |

### B. Caminhos protegidos

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G22-12 | Matcher cobre 08 §5.1 | lista carregada | tabela de amostras (`x/y/z.pth`, `a/conftest.py`, `src/appfactory/core/stop.py`, `Config/Resources.yaml`, `config/factory.yaml`, `config/novo/x.json`, `src/appfactory/jobs/manager.py`, `jobs/store.py`, `cli/main.py`, `core/paths.py`, `.git/HEAD`, `evals/t.json`...) e não protegidas (`README.md`, `src/appfactory/jobs/errors.py`) | cada amostra casa/não casa como esperado |
| G22-13 | Lista não pode encolher | guardrail com a lista literal de 08 §5.1 revisada (inclui `config/**` e os arquivos de D-0051) | comparar com `protected-paths.yaml` | arquivo ⊇ lista literal; o próprio arquivo está listado |
| G22-14 | Arquivo ausente/inválido | lista removida/corrompida em raiz temporária | `ProtectedPaths.load` | erro (fail-closed); nenhuma escrita permitida |

### C. Tentativas específicas exigidas

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G22-15 | Modificação de configuração | `repo_kind="factory"`, `writes=["config/**"]` (simula Evolution) | `WRITE config/policies/commands.yaml`; diff alterando `config/resources.yaml` | negado `protected`; diff rejeitado |
| G22-16 | Modificação de checkpoint | job com checkpoints | (a) `WRITE .appfactory/checkpoints/CP-0004…json`; (b) SQL `UPDATE`/`DELETE` em `checkpoints`; (c) diff alterando `src/appfactory/checkpoints/service.py` | (a) negado; (b) trigger aborta; (c) rejeitado |
| G22-17 | Remoção de log | log do job e `audit.jsonl` com 5 linhas | (a) `DELETE .appfactory/logs/jobs/<job>.jsonl`; (b) diff removendo `src/appfactory/logs/audit.py`; (c) `DELETE FROM events`; (d) remover a 3ª linha do `audit.jsonl` | (a) negado; (b) rejeitado; (c) trigger aborta; (d) `verify_chain` → falha no índice 2 |
| G22-18 | Alteração de STOP | STOP ativo | (a) diff alterando `core/stop.py`; (b) apagar `.appfactory/STOP` e reiniciar o manager; (c) `resume_factory(confirmed=False)`; (d) `WRITE .appfactory/STOP` pelo Toolbox; (e) `authorize(runner, POST /stop/release)` (P-08) | (a) rejeitado; (b) STOP continua ativo; (c) `PermissionError`; (d) negado; (e) `False` |
| G22-19 | Acesso a credenciais | ambiente pai com `OPENAI_API_KEY`, `GITHUB_TOKEN`, `AF_TOKEN` | `READ .env`, `secrets/k`, `credentials.json`, `.appfactory/runtime/tokens/user.token`; `clean_env("S1h", …)` | leituras negadas; ambiente só com `PATH`, `SYSTEMROOT`, `TEMP`, `TMP`, `LANG` |
| G22-20 | Redação | `RunResult` com `ghp_…` e `password=x` na saída | gravar saída e auditoria | arquivos e `audit.jsonl` contêm `[REDACTED]`, nunca o valor |

### D. Verificador de diff

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G22-21 | Todos os status | repositório git temporário (autor via variáveis de ambiente, sem mexer em config global) | commits com A, M, D, R (protegido→livre e livre→protegido), C, T sobre caminho protegido | `ok=False`, uma violação por entrada |
| G22-22 | Diff limpo | só `src/app/x.py` alterado | `check_diff` | `ok=True`, sem violações |
| G22-23 | Symlink e gitlink | entrada `120000` criada com `git update-index --cacheinfo` (portável, sem privilégio) e `160000` | `check_diff` | rejeitado `symlink`/`gitlink` |
| G22-24 | `[tool.pytest]` no `pyproject.toml` | diff adicionando a seção | `check_diff` | rejeitado `pytest_config` |
| G22-25 | Falha do git | ref inexistente / repositório inválido | `check_diff` | `ok=False`, `error` preenchido |
| G22-26 | Maiúsculas | `Pytest.INI`, `tests/Guardrails/t.py` | `check_diff` | rejeitado |
| G22-27 | Diff rejeitado bloqueia o job | job de teste em `RUNNING` | handler de teste chama o verificador com diff protegido | `BLOCKED(policy_violation)`, evento `security.violation`, linha de auditoria |

### E. Comandos, scripts e dependências

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G22-28 | Comandos proibidos | política carregada | `format`, `diskpart`, `reg add`, `bcdedit`, `Set-ExecutionPolicy`, `netsh`, `icacls`, `schtasks`, `sc create`, `net user`, `git push`, `git push --force`, `git reset --hard`, `git clean -fdx`, `rm -rf /`, `Remove-Item -Recurse C:\`, `cmd /c`, `powershell -c`, `bash -c`, `curl`, `certutil` | todos negados com a regra correspondente; R3 ⇒ `needs_human=True` |
| G22-29 | Forma do comando | — | string em vez de lista; sem timeout; timeout > máximo; `cwd` fora do worktree | negado |
| G22-30 | npm/pip | — | `npm ci --ignore-scripts`; `npm ci`; `npm install`; `npm i -g x`; `pip install --only-binary=:all: --require-hashes -r req.lock`; `pip install x`; `pip install -e .`; `python setup.py install`; `pip install --user x`; `uv pip install`, `yarn`, `pnpm install` | S1h/R2; S2; S2; proibido; S1h/R2; S2; S2; S2; proibido; S2 (padrão seguro, P-10) |
| G22-31 | Execução de script | `untrusted` | `python scripts/x.py`; `node x.js`; `pytest`; mesmo com `network_isolation_required`/`untrusted_high`/`unknown_origin`/`server`/`release_build` | S1h; com qualquer gatilho ⇒ S2; `untrusted` nunca S0 |
| G22-32 | Nunca rebaixar | S2 exigido; dublê S2 indisponível; S1h disponível (dublê) | `select_sandbox` | `WAITING(resources)` ou `BLOCKED`, nunca `S1h` |
| G22-33 | Produção não executa | classes reais S1h/S2 | `exec_untrusted` num job de teste | `SandboxUnavailable` ⇒ `BLOCKED(sandbox_unavailable)`; nenhum processo criado (espião em `subprocess`/`ctypes`) |
| G22-34 | `S1hLaunchSpec` | modos FG, BG, BATTERY | construir a especificação | 1,5 GB/50%/32 (FG), 3 GB/80%/32 (BG), prioridade BELOW_NORMAL/IDLE, `KILL_ON_JOB_CLOSE`, sem *breakaway*, limites de UI com clipboard, sem `LOGON_NETCREDENTIALS_ONLY`, ambiente sem token |
| G22-35 | `DockerSpec` | — | construir argumentos | `--rm`, `--network none` (exceto etapa de instalação), usuário não root, `--memory`, `--cpus`, só o worktree montado, sem `docker.sock`, rótulo `appfactory.task` |
| G22-36 | Tetos (I4) | configuração com memória/CPU/processos acima do teto | carregar/construir | recusado com erro; nunca aplicado acima do teto |

### F. Execução (dublê), STOP, falha e recuperação

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G22-37 | Execução bem-sucedida | handler de teste registrado só no teste; dublê retorna `ok` | `Executor.run` | `journal_intent`+`journal_result`, `RunResult` no journal e no log do job, saídas redigidas em `artifacts/runs/`, checkpoint do passo, `COMPLETED` após validação |
| G22-38 | STOP do job durante execução | dublê bloqueia até `cancel()` | `request_stop` durante a execução | dublê recebe cancelamento em ≤ 1 s de sondagem; `terminate` ≤ T0 + 30 s e fim ≤ T0 + 40 s, T0 = `jobs.stop_requested_at` (D-0054; variante com dublê que ignora o cancelamento); `RunResult.outcome="killed_stop"`; checkpoint `stop`; `RUNNING→STOPPING→STOPPED`; tmp limpo; `resume` ⇒ passo reexecutado em nova tentativa ⇒ `COMPLETED` |
| G22-39 | STOP da fábrica durante execução | idem | `stop_factory()` e, em outra variante, criar `.appfactory/STOP` | `terminate` ≤ T0 + 30 s e fim ≤ T0 + 40 s, T0 = `factory_stop.set_at` (D-0054); `PAUSED(factory_stop)`; auditoria `stop.set`; apagar o arquivo não libera; `resume_factory(confirmed=True)` ⇒ `QUEUED` e auditoria `stop.released`; cadeia íntegra |
| G22-40 | STOP ativo antes de executar | STOP da fábrica ativo | `claim` / `exec_untrusted` | `FactoryStopped`; dublê nunca chamado |
| G22-41 | Falha durante execução | dublê retorna `failed` (exit ≠ 0), depois `error`, depois `timeout` | `Executor.run` repetidas vezes | tentativa `failed` recuperável (`retry_pending`, D-0046); após 3 ⇒ `BLOCKED(needs_human)`; `timeout` ⇒ `terminate` chamado e outcome registrado |
| G22-42 | Limite atingido | dublê retorna `limit_memory`/`limit_processes` | `Executor.run` | outcome registrado; falha recuperável; auditoria |
| G22-43 | Perda de posse durante execução | lease vencido com relógio falso; outro executor assume | executor antigo continua | cancelamento `killed_lease`; o antigo não grava resultado (`LeaseLost`) |
| G22-44 | Recuperação após interrupção | processo real do executor com injeção de falha (`AF_ALLOW_FAULT_INJECTION=1`, `crash_in_exec`) usando o dublê | `os._exit` no meio da execução → novo manager → `recover` | intenção sem resultado ⇒ `BLOCKED(needs_human)` (D-0046); último checkpoint válido preservado; nenhuma segunda tentativa enquanto a anterior estiver viva |
| G22-45 | Violação no pipeline | handler de teste tenta escrever fora de `writes` duas vezes | `toolbox.fs_write` | 1ª: negada + `security.violation` + auditoria; 2ª: `BLOCKED(policy_violation)` (P-12) |

### G. Auditoria e tokens

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G22-46 | Cadeia de hashes | `audit.jsonl` vazio | 100 `append` de 4 threads e 2 processos; alterar 1 linha; reordenar; truncar o fim | íntegra antes; alteração/reordenação detectadas no índice certo; truncamento do fim só detectado se P-13 aprovar a âncora |
| G22-47 | Matriz de papéis (P-08) | registro em memória | `runner` aprova/libera/cria/lê outro job; `ui` aprova/libera; `user` libera sem confirmação; token expirado; comparação | todos negados; `user`+confirmação permitido; `hmac.compare_digest` usado |

### H. Suíte de guardrails

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G22-48 | Comando fixo | pytest instalado (Windows); *skip* com motivo se ausente | `python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails` | código 0; *skips* = exatamente os `pending` do manifesto; o resultado não é tratado como aprovação enquanto houver `pending` (D-0048) |
| G22-49 | `conftest.py` malicioso ignorado | cópia da suíte em pasta temporária com `conftest.py` que força falha/sucesso | comando fixo na cópia | resultado idêntico ao original |
| G22-50 | Manifesto | `MANIFEST.json` | teste meta | falha se: invariante I1–I7 ausente; `pending` sem fatia/módulo; módulo existente com guardrail ainda `pending`; invariante `active` com teste pulado (D-0048) |
| G22-51 | Configuração do pytest travada | repositório | `git ls-files` | nenhum `conftest.py`, `sitecustomize.py`, `usercustomize.py`, `*.pth`; `pyproject.toml` sem `[tool.pytest` |
| G22-52 | Regressão 2.1 | — | suíte completa | os 58 testes da 2.1 passam sem alteração |

| G22-53 | Alcance fábrica × projeto (D-0053) | repositório de projeto temporário e repositório com `.git` comum da fábrica | diff de projeto com `pytest.ini`/`conftest.py`; diff de projeto em `.appfactory/handoff.md`, symlink e gitlink; `classify_repo` com `.git` ilegível; TaskSpec declarando `project` para worktree da fábrica | projeto: permitido; `.appfactory/**`/symlink/gitlink: rejeitado; indeterminado ⇒ `factory`; declaração da TaskSpec ignorada |
| G22-54 | Formato de configuração (D-0049) | `protected-paths.yaml` com sintaxe YAML (comentário, chave sem aspas) | `load_policy_file` | erro; nenhuma política vazia aplicada (fail-closed) |

Cobertura das exigências: acesso permitido/negado (01–11), caminho protegido (12–14), configuração (15), checkpoint (16), logs (17), STOP (18), credenciais (19), comando proibido (28), script (31), STOP durante execução (38–39), falha durante execução (41–42), recuperação após interrupção (44).

---

## 7. Critérios de aceite (verificáveis automaticamente)

| # | Critério | Verificação |
| --- | --- | --- |
| AC-01 | Suíte completa sem falhas | `uv run pytest` (Windows) → `0 failed, 0 errors`; ≥ 58 + novos; *skips* só os listados no manifesto (D-0048: `pending` não é aprovação) |
| AC-02 | Guardrails pelo comando fixo | comando de 08 §5.3(4) → código de saída 0 |
| AC-03 | Linux sem pytest | `PYTHONPATH=src python3 -m unittest discover -s tests -t .` → `OK` (VM, 3.10) |
| AC-04 | Diff protegido rejeitado (critério de 14) | `af guard check-diff --repo <fixture> --base A --head B --json` → código ≠ 0 e violação listada; fixture limpa → 0 |
| AC-05 | Lista protegida completa | G22-13 passa; `protected-paths.yaml` carrega |
| AC-06 | Sem shell e sem subprocesso fora do lugar | teste AST: nenhum `shell=True` em `src/`; `subprocess` só em `security/diff_guard.py`, `toolbox/shell.py`, `cli/main.py` (guardrails run) |
| AC-07 | Sem dependências novas | `pyproject.toml`: `dependencies = []` (D-0049) |
| AC-08 | Nenhum código não confiável executa em produção | G22-33; nenhuma classe de sandbox além de S1h/S2 em `src/`; `FakeSandbox` só em `tests/` (teste AST) |
| AC-09 | Nenhuma mudança no SO | teste AST/grep: `src/` sem `CreateProcessWithLogonW`, `CreateJobObject`, `icacls`, `net user`, `docker run` executados (só como texto em especificações de dados) |
| AC-10 | Prazos do STOP durante execução (D-0054) | G22-38/39: `terminate` ≤ T0 + 30 s e encerramento total ≤ T0 + 40 s, T0 persistido no SQLite |
| AC-14 | Alcance e formato | G22-53 e G22-54 passam |
| AC-11 | Auditoria íntegra | `af audit verify` → 0 após os cenários; fixture adulterada → ≠ 0 |
| AC-12 | Higiene | `git diff --check` vazio; busca de segredos sem ocorrências; nada de runtime rastreado |
| AC-13 | 2.1 intacta | arquivos de teste da 2.1 inalterados (`git diff --stat tests/unit tests/integration` só com arquivos novos) e passando |

---

## 8. KIs relacionados

| KI | Relação com a 2.2 |
| --- | --- |
| KI-0014 | S1h depende da PoC de logon secundário + Job Object (2.6); na 2.2 S1h falha fechado |
| KI-0015 | S1h não isola rede ⇒ critério 1 de S2 |
| KI-0016 | ACL padrão de `D:\` ⇒ camada 2 de proteção ainda inexistente; a 2.2 só tem as camadas 1 (Toolbox) e 3 (diff) |
| KI-0011 | Docker a confirmar ⇒ S2 indisponível por definição |
| KI-0019 | Sem daemon/Job Objects ⇒ I6 "Job Object mata tudo" fica pendente; STOP depende de cooperação do código confiável |
| KI-0020 | Escritor único transitório ⇒ auditoria e eventos gravados pela biblioteca, não pelo daemon |
| KI-0012 | `git`/`python` do PATH não confiáveis por padrão ⇒ fixar caminhos absolutos dos binários confiáveis |
| KI-0007 | RAM livre baixa ⇒ admissão de S2 (≥ reserva + 3 GB) raramente satisfeita em FG |
| KI-0001/0002 | VM não roda `uv run pytest`; validação final no Windows pelo usuário |

Candidatos a KI novos (registrar só se o usuário aprovar): P-13 (truncamento do fim da auditoria) e P-14 (hooks/config do git em worktree gravável).

---

## 9. Contradições e decisões pendentes

| ID | Contradição / lacuna | Onde | Opções | Recomendação / decisão |
| --- | --- | --- | --- | --- |
| P-01 | 14 diz que os esqueletos de guardrail "falham até o componente existir"; `AGENTS.md` §5 proíbe concluir fase com teste crítico falhando | 14 × AGENTS | (a) *skip* com motivo + manifesto com teste meta que falha se o componente existir e o guardrail continuar pendente; (b) `xfail(strict=True)`; (c) falhar de verdade | **DECIDIDA — D-0048** (aprovada em 2026-09-27): (a) |
| P-02 | Configurações são `.yaml` (08, 10), mas não há parser YAML na biblioteca padrão e D-0042 proíbe dependências sem decisão | 08/10 × D-0042 | (a) adicionar PyYAML (decisão + `uv.lock`); (b) `.yaml` escrito no subconjunto JSON (JSON é YAML 1.2 válido) lido com `json`; (c) trocar para `.json` | **DECIDIDA — D-0049** (aprovada em 2026-09-27): (b) — sem dependência e sem mudar nomes |
| P-03 | O Toolbox (e a `CommandPolicy`) não está atribuído a nenhuma fatia revisada de 14; a 2.2 precisa de um ponto de aplicação | 14 | (a) Toolbox mínimo (fs + `exec_untrusted`) na 2.2; (b) só bibliotecas de política na 2.2, Toolbox na 2.8 | **DECIDIDA — D-0050** (aprovada em 2026-09-27): (a), limitado ao §5.6 |
| P-04 | Escopo: o pedido inclui segurança de execução (S1h, S2, tokens), que 14 coloca na 2.6 | 14 × pedido | (a) 2.2 = decisão/guardrails + contratos; isolamento real na 2.6; (b) antecipar partes da 2.6 | (a) — é o que esta especificação faz |
| P-05 | A lógica que garante STOP/imutabilidade está em arquivos **não** protegidos: `jobs/manager.py`, `jobs/store.py` (triggers, `factory_stop`), `jobs/executor.py`, `jobs/states.py`, `jobs/handlers.py` (porta da injeção de falhas), `core/paths.py`, `core/clock.py`, `core/procinfo.py`, `cli/main.py` (código de confirmação) | 08 §5.1 × código 2.1 | (a) ampliar 08 §5.1 (decisão); (b) manter e confiar nos guardrails comportamentais I2/I6 | **DECIDIDA — D-0051** (aprovada em 2026-09-27): (a) para `store.py`, `manager.py`, `executor.py`, `states.py`, `cli/main.py`; guardrails continuam como 2ª defesa |
| P-06 | `10-diretorios.md` marca todo `config/` como [P]; 08 §5.1 lista só `policies/**`, `resources`, `providers`, `models`, `agents/**` (fica de fora `factory.yaml`); o pedido fala em `config/*.yaml` | 10 × 08 | (a) `config/**`; (b) manter a lista de 08 | **DECIDIDA — D-0052** (aprovada em 2026-09-27): (a) — o mais restritivo, alinhado a 10 e ao pedido |
| P-07 | Os padrões de 08 §5.1 são do repositório da fábrica; projetos gerados legitimamente têm `pytest.ini`, `conftest.py`, `.gitignore`. 08 §5.3(3) manda verificar "todo diff proposto por agente" | 08 §5.1 × §5.3 | (a) lista completa só no repositório da fábrica; em projetos: `.git/**`, `.appfactory/**`, symlink/gitlink e escopo `writes`; (b) lista completa em todo repositório | **DECIDIDA — D-0053** (aprovada em 2026-09-27): (a) |
| P-08 | Tokens dependem da API (FastAPI adiado, D-0042) e do daemon (2.4); a 2.6 prevê "tokens por papel"; o arquivo `user.token` exige ACL (proibido agora) | 08 §8 × D-0042 × 14 | (a) na 2.2 só matriz de autorização e registro em memória (§5.7); (b) tudo na 2.6 | (a) |
| P-09 | Onde ficam os limites configuráveis do S1h: 08 diz "configurável, teto no RESOURCE_POLICY", mas `resources.yaml` (05 §9) não tem seção de sandbox; e o que fazer quando S1h é exigido mas não existe (escalar para S2, mais restrito, ou bloquear) | 08 §4.2 × 05 §9; 08 §4.4 | limites: (a) seção `sandbox:` no `resources.yaml` (2.3) e constantes ≤ teto na 2.2; (b) arquivo novo. Indisponível: (a) escalar para S2 se disponível; (b) sempre `BLOCKED` | limites (a); indisponível: decisão do usuário (14 já prevê "usar só S2" como alternativa) |
| P-10 | Casos fora da tabela 08 §4.3 (`uv pip`, `uv sync`, `yarn`, `pnpm`, `npx` que baixa pacote) e endurecimentos/imagem do S2 não definidos | 08 §4.3–4.4 | (a) padrão seguro S2 para o que não está na tabela; extras do Docker como proposta; (b) negar | (a) |
| P-11 | 08 §9 prevê STOP por "guardrail violado", sem dizer quais violações acionam STOP da fábrica × só `BLOCKED` da task | 08 §3 × §9 | (a) STOP só por falha de integridade dos mecanismos (lista protegida inválida, auditoria quebrada, `factory_stop` ilegível); violações de agente ⇒ `BLOCKED`; (b) toda violação ⇒ STOP | (a) |
| P-12 | "Reincidência" (08 §3) não definida | 08 §3 | (a) 2ª violação no mesmo job; (b) 2ª na mesma tentativa; (c) 1ª já bloqueia | (a); diff protegido bloqueia na 1ª (08 §5.3) |
| P-13 | A cadeia `prev_hash` não detecta truncamento do fim do `audit.jsonl` | 08 §10 | (a) âncora: hash da última linha também gravado no SQLite (evento append-only); (b) aceitar como risco | (a), sem tabela nova |
| P-14 | Lacuna de segurança não coberta pela arquitetura: o Toolbox roda `git` como usuário principal dentro de worktree gravável por `afrunner`; o arquivo `.git` do worktree ou configurações podem apontar para *hooks* ⇒ código não confiável executado como usuário principal | 08 §4.1 × §4.2 | (a) git confiável sempre com `-c core.hooksPath=<vazio>`, `core.fsmonitor=false`, `GIT_CONFIG_NOSYSTEM=1`, verificação do conteúdo de `.git` antes de cada chamada; (b) só `--no-verify` | (a) — registrar como decisão de segurança |
| P-15 | I6 exige parar tudo em ≤ 40 s, mas a detecção por heartbeat (15 s) + carência (30 s) + kill (10 s) pode chegar a 55 s; não está definido de quando se mede | 09 I6 × 01 §0 × 15 | (a) medir desde a persistência do STOP e sondar STOP localmente a cada ≤ 1 s (detecção ≤ 1 s + 30 + 10 > 40 ainda); (b) reduzir a carência para 29 s; (c) medir desde a chegada do sinal ao runner | **DECIDIDA — D-0054** (aprovada em 2026-09-27): opção (a) com prazos ancorados no T0 persistido — `terminate` ≤ T0 + 30 s, encerramento total ≤ T0 + 40 s, cobrados pelo código confiável supervisor; sondagem ≤ 1 s; prazo efetivo = menor entre "T0 + 30 s" e "detecção + 30 s"; números de 01 §0 inalterados |

As pendências bloqueantes (**P-01, P-02, P-03, P-05, P-06, P-07, P-15**) foram **decididas** (D-0048 a D-0054) e aplicadas à documentação em 2026-09-27. Continuam abertas, sem bloquear o início: P-04, P-08, P-09, P-10, P-11, P-12, P-13, P-14.

---

## 10. Ordem recomendada de implementação

1. ~~**Decisões bloqueantes**~~ — **concluído** (D-0048 a D-0054 registradas; 08, 09, 10, 11, 14, 15, 01, 05 e `AGENTS.md` atualizados).
2. **Guardrails primeiro (esqueleto):** `tests/guardrails/pytest.ini`, `MANIFEST.json`, os 7 arquivos com os testes já possíveis ativos (I2, partes de I1/I6/I7 sobre a 2.1) e os demais `pending` (D-0048); G22-48/50/51/52.
3. **Lista protegida + política de caminhos:** `protected-paths.yaml`, `security/paths.py`; G22-01…14.
4. **Verificador de diff + CLI:** `security/diff_guard.py`, `af guard check-diff`; G22-21…26 (critério de pronto de 14).
5. **Auditoria:** `logs/audit.py`, STOP auditado, `af audit verify`; G22-17(d), 18, 46.
6. **CommandPolicy:** `commands.yaml`, `security/command_policy.py`, `clean_env`; G22-19, 28…31.
7. **Sandbox (contrato, seleção, especificações S1h/S2 fail-closed):** G22-32…36.
8. **Integração com o Job Manager + Toolbox mínimo:** `hold_attempt`, `should_stop` com STOP da fábrica, `toolbox/fs.py`, `toolbox/shell.py`, dublê em `tests/fakes/`; G22-15, 16, 20, 27, 37…45.
9. **Autorização (se P-08):** `core/auth.py`; G22-47.
10. **Fechamento:** ativar no manifesto os guardrails cobertos; regressão Linux; `uv run pytest` e comando fixo no Windows (usuário); `docs/runbooks/seguranca.md`; arquivos de estado; checkpoint CP-0005.
