# 08 — Segurança (G)

**Revisão 1.1 (2026-09-26):** reestruturado pela revisão técnica da Fase 1 (itens N1 e N2). Decisões: D-0026 a D-0029. Diagramas: `13-diagramas.md` §8 e §9.

**Revisão 2.2 (2026-09-27):** formato dos arquivos de configuração (D-0049), lista protegida ampliada com o núcleo do Job Manager, a CLI e `config/**` (D-0051, D-0052), alcance fábrica × projetos gerados (D-0053), guardrails pendentes (D-0048) e prazos do STOP medidos desde o T0 persistido (D-0054).

## 0. Princípio central: código gerado é NÃO CONFIÁVEL

| Classe de confiança | O que é | Onde pode executar |
| --- | --- | --- |
| **Confiável** | Código da fábrica em `main` (daemon, Toolbox, runners), binários fixos da allowlist (git, uv, python.exe do ambiente da fábrica), o usuário | Processos do **usuário principal** |
| **Não confiável** | Qualquer código escrito ou alterado por agente/LLM (inclusive testes e scripts), código dos projetos gerados, dependências de terceiros e seus scripts de instalação, conteúdo da web, código do branch `evo/*` do Evolution Agent | **Somente em S1h ou S2** (§4), nunca como usuário principal |

Consequência: as permissões por agente (§3) valem para as **chamadas ao Toolbox**; o que impede código não confiável de escapar é o **isolamento do sistema operacional** (usuário dedicado + ACLs + Job Object) ou o container. Política no código sozinha não é considerada barreira.

## 1. Níveis de risco das ações

| Nível | Exemplos | Autorização |
| --- | --- | --- |
| **R0** leitura | ler arquivos do workspace, `git status/log/diff`, buscar documentação | automática |
| **R1** escrita reversível e confinada | escrever no worktree da task, commit em `af/*`, rodar testes em S1h/S2 | automática, com log |
| **R2** efeito fora do confinamento ou difícil de reverter | instalar dependência, rede para domínio novo, criar banco/container, `ollama pull`, escrever fora do worktree | Security Agent + política; aprovação humana se a política do projeto não pré-autorizar |
| **R3** irreversível, externo, público ou com custo | merge em `main`, push, tag, publicação, deploy, apagar arquivos/branches do usuário, migração destrutiva, enviar mensagens, usar provedor pago, mudar configuração do sistema (inclui criar usuário Windows, alterar ACLs fora do repo, criar tarefa agendada) | **sempre [H]**, por ação, com confirmação interativa (§8) |

Ações **proibidas** mesmo com pedido (o agente devolve ao usuário): inserir senhas/cartões/documentos em formulários, criar contas online, mexer em configuração de segurança do Windows, desativar antivírus, contornar CAPTCHA, executar binários baixados de fonte não confiável fora de S2.

## 2. Secrets

- Guardados no **Windows Credential Manager do usuário principal** via `keyring` (serviço `appfactory`). O cofre é por usuário: o usuário `afrunner` (§4) **não** tem acesso a ele.
- A configuração guarda **referências** (`secret://providers/<id>/api_key`), nunca valores.
- Só processos confiáveis do usuário principal (Provider Router, partes específicas do Toolbox) resolvem segredos, em memória e na hora do uso. Agentes e LLMs **nunca** recebem segredos no contexto; processos em S1h/S2 **nunca** recebem segredos no ambiente, em arquivos ou em argumentos.
- A senha da conta `afrunner` é gerada aleatoriamente pelo setup (Fase 2, com [H]), guardada só no Credential Manager do usuário principal e nunca exibida nem logada.
- Ambiente de processos filhos sempre limpo (allowlist: `PATH` mínimo, `SYSTEMROOT`, `TEMP` do sandbox, `LANG`).
- Redação automática em logs: padrões de chaves conhecidos + valores de todos os segredos registrados + entropia alta em campos sensíveis.
- `gitleaks` antes de todo commit de agente e em todo diff de integração.
- `.gitignore` bloqueia `.env*`, chaves, `secrets/`, `credentials*.json`.

## 3. Permissões (capabilities por agente)

Arquivo `config/policies/permissions.yaml` (versionado e protegido, §5). Formato: arquivos `.yaml` da fábrica são escritos no **subconjunto JSON** do YAML 1.2, sem comentários, e lidos por leitor protegido que recusa qualquer outra sintaxe (D-0049); o exemplo abaixo é **ilustrativo** (conteúdo normativo, sintaxe não). Exemplo:

```yaml
coder:
  fs.read:  ["{worktree}/**", "{project}/**"]
  fs.write: ["{worktree}/{task.writes}"]          # writes = arquivos explícitos e prefixos dir/** (04 §3)
  exec:     { sandbox: [S1h, S2] }                # nunca como usuário principal
  shell.exec: { allow: [python, uv, pytest, ruff, node, npm, npx, git], deny_args: ["push", "reset --hard", "clean -fdx"] }
  net: { allow: [] }                              # sem rede por padrão
  git: [status, diff, add, commit, log, show]
research:
  net: { allow: ["docs.python.org", "developer.mozilla.org", "*.readthedocs.io", "github.com", "pypi.org", "npmjs.com"] }
  fs.write: ["{job}/research/**"]
```

O Toolbox aplica a política **antes** de executar. Violação → negar + `security.violation` + task `BLOCKED(policy_violation)` na reincidência.

## 4. Sandbox

### 4.1 Níveis

| Nível | Uso | Isolamento |
| --- | --- | --- |
| **S0** em processo | ferramentas somente leitura do Toolbox (confiáveis) | validação de caminho (resolve symlinks/junctions; nega `..` e caminhos fora do escopo) |
| **S1h** (S1 endurecido) — padrão do dia a dia | executar código não confiável que **não** precisa de isolamento de rede: testes, lint, scripts do projeto, app gerado para E2E | usuário Windows dedicado + ACLs NTFS + Job Object (§4.2) |
| **S2** container Docker | tudo que exigir isolamento de rede, instalação de dependências com scripts, compilação de fontes de terceiros, servidores de banco, código de origem desconhecida | só o worktree montado, `--network none` por padrão, `--memory`/`--cpus`, usuário não root, sem Docker socket |

O antigo "S1 subprocesso simples" (Fase 1) **não é mais permitido** para código não confiável; só existe para ferramentas confiáveis (ex.: `git` executado pelo próprio Toolbox).

### 4.2 S1h — especificação

1. **Usuário dedicado:** conta local padrão (não administradora) `afrunner` (nome configurável). Criada **uma vez pelo usuário humano** no setup da Fase 2 (ação R3; nada é criado na Fase 1.1). Sem perfil interativo usado, sem acesso ao Credential Manager do usuário principal.
2. **Lançamento:** o daemon (usuário principal) lança o processo como `afrunner` via logon secundário (`CreateProcessWithLogonW`), **suspenso**, atribui ao Job Object e só então retoma. A viabilidade no Windows 11 Home deve ser provada na Fase 2 antes de qualquer uso real (KI-0014). Se não for viável, todo código não confiável passa a exigir S2 (decisão a registrar).
3. **Job Object** (um por task, aninhado no Job Object raiz do daemon):
   - `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` — fechar o handle (inclusive por crash do daemon) mata todos os processos;
   - limite de memória do job (`JobMemoryLimit`): **1,5 GB em FOREGROUND, 3 GB em BACKGROUND** (configurável, teto em `RESOURCE_POLICY.md`);
   - limite de memória por processo: igual ao do job;
   - limite de processos ativos: 32;
   - limite de CPU (`CPU_RATE_CONTROL`, hard cap): 50% em FOREGROUND, 80% em BACKGROUND;
   - prioridade BELOW_NORMAL (IDLE em BATTERY);
   - restrições de UI (`JOB_OBJECT_UILIMIT_*`): sem área de transferência, sem desktop, sem hooks globais;
   - timeouts aplicados pelo daemon (05 §6).
4. **ACLs NTFS** (aplicadas no setup pelo usuário e por task pelo daemon):
   - `afrunner` com **Deny herdado** a partir de `D:\Claude\app-factory` (e demais pastas que o usuário indicar; ver KI-0016 sobre a ACL padrão de `D:\`);
   - **Allow explícito (Modify)** só no worktree da task em execução (`workspaces\_worktrees\<p>\<task>\`) e no diretório temporário da task; revogado ao fim da task;
   - leitura explícita no ambiente Python/Node de execução (somente leitura);
   - nunca acesso a `.appfactory\`, `config\`, `src\`, `tests\guardrails\`, `docs\`, arquivos de estado da raiz, perfil do usuário principal.
5. **Rede:** o Windows Home não oferece bloqueio de rede por usuário confiável; **S1h não isola rede**. Por isso: task que precisa de isolamento de rede → S2 obrigatório; S1h nunca recebe segredos nem acesso a dados protegidos, então o risco residual é tráfego de rede do código testado (KI-0015).
6. **Comunicação:** processos S1h **não recebem token da API** e não falam com o daemon; o runner confiável (usuário principal) coleta stdout/stderr/código de saída/arquivos do worktree.

### 4.3 Dependências (npm/pip)

| Operação | Onde |
| --- | --- |
| `npm ci --ignore-scripts` de lockfile existente, registros permitidos | S1h (R2, pré-autorizável por projeto) |
| `pip install --only-binary=:all: --require-hashes -r <lock>` de índices permitidos | S1h (R2, pré-autorizável) |
| Qualquer instalação que execute scripts (`postinstall`, `setup.py`, build de wheel/sdist), `npm install` que altere lockfile, instalação sem hashes | **S2** (rede só na etapa de instalação; execução posterior com `--network none`) |
| Ferramentas globais / alteração do Python ou Node da máquina | proibido (R3 com [H], feito pelo usuário) |

Toda adição/alteração de dependência passa pelo Security Agent (pip-audit/npm audit + gitleaks) antes da integração.

### 4.4 Quando S2 é obrigatório

- a task declara `network_isolation: required` ou precisa de rede além dos registros permitidos;
- instalação/compilação com scripts (4.3);
- código de origem desconhecida (repositórios baixados, anexos, exemplos da web);
- servidores (banco de dados, filas) para o projeto gerado;
- builds de release (12 — Build/Release);
- teste de código cuja task foi marcada `untrusted_high` pelo Security Agent.

Sem Docker disponível ou sem RAM para a VM (admissão própria ≥ 3 GB, 05 §4): a task fica `WAITING(resources)` ou `BLOCKED` — **nunca** cai para S1h silenciosamente.

## 5. Infraestrutura protegida

### 5.1 Lista (`config/policies/protected-paths.yaml`, ela mesma protegida)

| Grupo | Caminhos |
| --- | --- |
| Políticas, limites e configuração | `config/**` — toda a pasta, inclusive `factory.yaml`, `policies/**`, `resources.yaml`, `providers.yaml`, `models.yaml`, `agents/**` e arquivos futuros (D-0052) |
| Código de aplicação de segurança | `src/appfactory/security/**`, `src/appfactory/toolbox/**`, `src/appfactory/core/auth.py`, `src/appfactory/core/stop.py`, `src/appfactory/core/instance.py`, `src/appfactory/core/api.py` (futuro; D-0051) |
| Núcleo do Job Manager, relógio/vida e CLI (D-0051) | `src/appfactory/jobs/store.py`, `jobs/manager.py`, `jobs/executor.py`, `jobs/states.py`, `jobs/handlers.py`, `jobs/state_machine.py` (futuro), `jobs/jobobjects.py` (futuro), `src/appfactory/core/paths.py`, `core/clock.py`, `core/procinfo.py`, `src/appfactory/cli/main.py` |
| Recursos | `src/appfactory/resources/**` |
| Orçamento e roteamento com efeito de custo/privacidade | `src/appfactory/routing/budget.py`, `src/appfactory/routing/provider_router.py`, `src/appfactory/routing/model_registry.py` |
| Checkpoints, logs, recuperação | `src/appfactory/checkpoints/**`, `src/appfactory/logs/**` (inclui `audit.py`, `redaction.py`), `src/appfactory/jobs/recovery.py`, `src/appfactory/jobs/leases.py`, `src/appfactory/jobs/locks.py` |
| Guardrails e avaliação | `tests/guardrails/**`, `evals/**`, `pytest.ini`, `conftest.py` e `**/conftest.py`, `sitecustomize.py`, `usercustomize.py`, `*.pth` (qualquer nível) |
| Normativos | `AGENTS.md`, `DECISIONS.md`, `RESOURCE_POLICY.md`, `docs/architecture/**` |
| Estado versionado | `PROJECT_STATE.md`, `HANDOFF.md`, `TASK_QUEUE.md`, `CHANGELOG.md`, `KNOWN_ISSUES.md`, `TEST_STATUS.md`, `COMMAND_LOG.md`, `.appfactory/job.json`, `.appfactory/checkpoints/**` |
| Repositório | `.git/**`, `.gitignore`, `.gitattributes` |
| Diagnóstico humano | `tools/diagnostics/**` |

Regra: a configuração do pytest só pode existir em `pytest.ini` (protegido); é proibido `[tool.pytest*]` no `pyproject.toml`.

Regra (D-0051): **todo módulo que implemente uma invariante I1–I7 (09 §1) entra nesta lista antes de ser criado**.

### 5.2 A quem se aplica

- **Aplica-se** a todos os agentes da fábrica em execução (runtime) e ao Evolution Agent, sem exceção.
- **Não impede** sessões de desenvolvimento dirigidas pelo usuário (o próprio usuário ou uma IA trabalhando sob instrução direta dele, conforme `AGENTS.md`), que continuam obrigadas a registrar mudanças em `DECISIONS.md`.
- **Alcance por repositório (D-0053):**
  - **Repositório da fábrica** (inclui worktrees `evo/*` e qualquer task que altere a própria fábrica): vale a lista completa de §5.1.
  - **Projetos gerados** (`workspaces/<projeto>`): são rejeitadas alterações em `.git/**` e `.appfactory/**` do projeto (escritos só por código confiável, como o Handoff System), symlinks (modo `120000`), gitlinks/submódulos (modo `160000`) e qualquer escrita fora do `writes` da task (04 §3). `pytest.ini`, `conftest.py`, `.gitignore` e docs do projeto são permitidos: são código/dado não confiável que só executa em S1h/S2.
  - O tipo de repositório é determinado **por código confiável**, pelo caminho real do repositório (diretório `.git` comum igual ao da fábrica ⇒ fábrica), **nunca** por campo declarado na TaskSpec ou pelo agente. **Na dúvida, vale a lista completa da fábrica.**

### 5.3 Camadas de aplicação

1. **Toolbox:** nega escrita/renomeação/remoção em caminho protegido (inclusive via symlink/junction).
2. **ACL:** `afrunner` não tem acesso algum a esses caminhos (§4.2).
3. **Revisão de diff automática:** todo diff proposto por agente (task ou EP) é verificado por código confiável (`git diff --name-status --find-renames <base>...<branch>`); qualquer arquivo protegido **adicionado, alterado, renomeado, removido ou referenciado por symlink** ⇒ **rejeição automática** (tarefa `BLOCKED(policy_violation)`; EP `REJECTED`). Qual lista se aplica segue §5.2 (D-0053); erro do git ou tipo de repositório indeterminado ⇒ rejeição (falha fechada).
4. **Guardrails:** executados por comando fixo e confiável: `python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails` com o ambiente travado da fábrica; o código candidato não controla a configuração nem os plugins. Guardrails de componentes ainda inexistentes ficam `pending` no manifesto protegido `tests/guardrails/MANIFEST.json`; **`pending` nunca significa aprovação** e o Evolution só pode ser habilitado com I1–I7 todas `active` (D-0048, 09 §2).
5. **Dependências:** EP que altere `pyproject.toml` (dependências) ou `uv.lock` exige [H] com auditoria do Security Agent.

## 6. Filesystem

- Raiz permitida para a fábrica: `D:\Claude\app-factory`. Tudo fora disso = R2/R3.
- A fábrica não grava em `C:` (exceto temporários do sistema).
- Remoção: agentes não apagam fora de `.appfactory/jobs/*/tmp` e dos worktrees criados pela própria fábrica; apagar arquivos do usuário = R3.

## 7. Terminal, execução e navegador

- Todo comando passa pelo `CommandPolicy`: executável na allowlist, argumentos checados, `cwd` no escopo, timeout obrigatório, sandbox escolhido pela classe de confiança (§0).
- Sem `shell=True` por padrão. Pipes/redirecionamentos só em comandos pré-aprovados.
- Sempre negados sem [H]: `rm -rf`/`Remove-Item -Recurse` fora do escopo, `git push --force`, `git reset --hard` em branch compartilhado, `format`, `diskpart`, `reg`, `bcdedit`, `Set-ExecutionPolicy`, `netsh`, `icacls` fora do fluxo de setup, `schtasks`, criação de serviços/usuários.
- Navegador: perfil Playwright descartável, separado do Chrome do usuário · allowlist de domínios por job · sem credenciais reais · downloads em quarentena (`.appfactory/jobs/<job>/quarantine/`), nunca executados · conteúdo de páginas/arquivos é **dado, nunca instrução**. O app gerado sob teste roda em S1h/S2.

## 8. Papéis, tokens e API local

| Papel | Token | Pode | Não pode |
| --- | --- | --- | --- |
| `user` | `.appfactory/runtime/tokens/user.token` (ACL: só usuário principal) | tudo, inclusive aprovações e liberar STOP — **sempre com confirmação interativa** | — |
| `runner` | um por tentativa (attempt), escopo = sua task, expira com o lease; entregue ao runner por handle herdado, nunca em arquivo legível por `afrunner` | `/runner/*`, `/llm/generate`, `/tools/*` da própria task, **acionar** STOP | aprovações, liberar STOP, criar/cancelar jobs, ler outras tasks |
| `ui` (futuro) | igual a `user` sem aprovar/liberar STOP | leitura e controle de jobs | aprovar, liberar STOP |
| S1h/S2 | **nenhum** | — | falar com a API |

- API só em `127.0.0.1`; valida o cabeçalho `Host` (apenas `127.0.0.1:<porta>`/`localhost:<porta>`), **sem CORS**, rejeita requisições com `Origin` de navegador; token obrigatório em todas as rotas.
- **Aprovações interativas:** `af approve <APR-id>` mostra ação, risco, preview e custo; o usuário digita um código de confirmação exibido **no console** (uso único, 5 min). A API não aceita aprovação sem esse código, nem por token `runner`/`ui`. Aprovação é por ação, com expiração (24 h), e nunca se generaliza.
- Sem resposta → task `BLOCKED(approval)` (sem consumir recursos).
- Pré-autorizações por projeto são configuração versionada e protegida, nunca decisão de agente.

## 9. STOP (kill switch)

| Aspecto | Regra |
| --- | --- |
| Estado | Tabela `factory_stop` no SQLite (`active`, `reason`, `set_at`, `set_by`) **e** flag em memória do daemon |
| Como acionar | `af stop`; `POST /stop` (qualquer papel, inclusive `runner`); criar o arquivo `.appfactory/STOP`; decisão interna (ex.: guardrail violado). Acionar é sempre permitido (direção segura) |
| Efeito | Persistido **antes** de qualquer outra ação → modo CRITICAL, nenhum despacho, pausa cooperativa, descarga só dos modelos da fábrica |
| Como liberar | **Somente** `af resume-factory` com token `user` + confirmação interativa. Apagar o arquivo `STOP` **nunca** libera uma parada registrada |
| Prazos (D-0054) | **T0** = instante persistido na transação do pedido (`factory_stop.set_at`; para job, `jobs.stop_requested_at`; cancelamento/pausa: timestamp persistido correspondente, ex.: `jobs.cancelled_at`). Código confiável supervisor cobra: **`terminate` em ≤ T0 + 30 s** e **encerramento total em ≤ T0 + 40 s**; quem executa sonda o STOP a cada ≤ 1 s (só antecipa a cooperação). Prazo efetivo = menor entre "T0 + 30 s" e "detecção + 30 s" em tempo ativo |
| Partida do daemon | Carrega `factory_stop` antes de despachar qualquer coisa; se o arquivo existir e a tabela não, registra a parada |
| Auditoria | Acionar e liberar vão para `audit.jsonl` |

## 10. Logs e auditoria

- `audit.jsonl`: ações R2/R3, aprovações, violações, uso de segredo (só o nome), STOP, troca para provedor pago. Cada linha com `prev_hash` (cadeia de hashes). O arquivo fica em `.appfactory/logs/`, inacessível a `afrunner`.
- Logs nunca contêm segredos nem conteúdo integral de arquivos do usuário por padrão.

## 11. Rollback

Ver `02-fluxo-de-tarefa.md` (tabela de rollback). Rollback **nunca** destrói histórico compartilhado; usa `revert`/novo branch. Rollback da fábrica = voltar ao commit do checkpoint de marco.

## 12. Riscos residuais aceitos (documentados)

S1h sem isolamento de rede (KI-0015) · viabilidade de logon secundário + Job Object a provar (KI-0014) · ACL padrão de `D:\` a validar no setup (KI-0016) · processos do usuário principal continuam podendo ler o cofre do próprio usuário (por isso código não confiável nunca roda como ele).
