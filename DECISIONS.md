# DECISIONS.md — Registro de decisões

Formato: ID · data · decisão · motivo · status.

## D-0001 · 2026-09-26 · Localização oficial do projeto
- **Decisão:** o projeto vive em `D:\Claude\app-factory` (`/mnt/d/Claude/app-factory` no WSL).
- **Motivo:** exigência do usuário; manter o projeto no disco D e fora de `~`.
- **Status:** ativa.

## D-0002 · 2026-09-26 · Uso de Git
- **Decisão:** versionar tudo com Git, branch padrão `main`, commits no padrão Conventional Commits.
- **Motivo:** histórico auditável e continuidade entre IAs.
- **Status:** ativa.

## D-0003 · 2026-09-26 · Uso do GitHub
- **Decisão:** remote oficial `origin` = `https://github.com/bielxleme/app-factory.git`.
- **Motivo:** backup remoto e ponto único de verdade.
- **Status:** ativa.

## D-0004 · 2026-09-26 · Uso do WSL
- **Decisão:** o ambiente de desenvolvimento principal é o WSL no Windows; commits e pushes com credenciais do usuário são feitos no WSL.
- **Motivo:** ambiente escolhido pelo usuário; as credenciais do GitHub estão lá. O shell do Claude (Cowork) é uma VM Linux isolada, sem acesso ao WSL nem às credenciais (ver KI-0001).
- **Status:** revisada por D-0010.

## D-0005 · 2026-09-26 · Arquivos de estado como memória operacional
- **Decisão:** usar `AGENTS.md`, `PROJECT_STATE.md`, `TASK_QUEUE.md`, `DECISIONS.md`, `CHANGELOG.md`, `HANDOFF.md`, `KNOWN_ISSUES.md`, `TEST_STATUS.md`, `RESOURCE_POLICY.md`, `COMMAND_LOG.md`, `.appfactory/job.json` e `.appfactory/checkpoints/`.
- **Motivo:** permitir que qualquer IA continue o trabalho sem reiniciar o projeto.
- **Status:** ativa; complementada por D-0015 (o banco SQLite passa a ser a fonte da verdade da execução; esses arquivos são visões humanas mantidas pelo Handoff System). **Revisada por D-0035 (Fase 1.1):** os arquivos de estado da raiz são o estado *versionado* do desenvolvimento da fábrica, mantidos pelas sessões de desenvolvimento; o daemon não os escreve; o estado operacional fica em `.appfactory/runtime/` e `.appfactory/state/` (ignorados).

## D-0006 · 2026-09-26 · Separação entre preparação e arquitetura
- **Decisão:** a Fase 0 só prepara infraestrutura; nenhuma arquitetura, agente, Job Manager, Resource Manager ou Toolbox é criado nela.
- **Motivo:** evitar construir sobre base não validada.
- **Status:** ativa.

## D-0007 · 2026-09-26 · Arquivo COMMAND_LOG.md
- **Decisão:** registrar comandos relevantes em `COMMAND_LOG.md` (o `CHANGELOG.md` resume e aponta para ele).
- **Motivo:** reprodutibilidade sem poluir o changelog.
- **Status:** ativa.

## D-0008 · 2026-09-26 · Finais de linha LF e `core.filemode=false`
- **Decisão:** `.gitattributes` com `* text=auto eol=lf`; `core.filemode=false` no repositório.
- **Motivo:** o repositório fica em NTFS e é acessado por Windows, WSL e VMs; evita diffs falsos de CRLF e de permissão.
- **Status:** ativa.

## D-0009 · 2026-09-26 · Commit e push feitos pelo usuário
- **Decisão:** o primeiro commit e o push são executados pelo usuário no WSL, com a identidade Git dele.
- **Motivo:** escolha do usuário; autoria correta e uso das credenciais já configuradas no WSL.
- **Status:** ativa (executado via PowerShell, ver D-0010).

## D-0010 · 2026-09-26 · Git para Windows (PowerShell) como ambiente Git oficial; WSL/OpenClaw separado
- **Decisão:** commits e pushes são feitos pelo usuário com Git para Windows no PowerShell, em `D:\Claude\app-factory`. O ambiente WSL/OpenClaw continua separado e **não** deve ser usado para recriar ou duplicar o projeto.
- **Motivo:** o primeiro commit (`5aa9709`) e o push foram feitos assim pelo usuário; manter uma única cópia do projeto.
- **Status:** ativa. Revisa D-0004.

## D-0011 · 2026-09-26 · Checkpoint referencia o commit anterior
- **Decisão:** um checkpoint registra o commit que ele valida (`base_commit`); o arquivo do checkpoint é versionado no commit seguinte.
- **Motivo:** um arquivo não pode conter o hash do commit que o contém.
- **Status:** ativa.

---

# Fase 1 — Arquitetura (2026-09-26) · base: hardware medido em 2026-09-26 16:17 -03:00

## D-0012 · 2026-09-26 · Especificação normativa em `docs/architecture/`
- **Decisão:** a arquitetura fica em `docs/architecture/` (índice em `README.md`) e é normativa para qualquer IA implementadora.
- **Motivo:** permitir implementação sem redesenho; um só lugar de verdade.
- **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Especificação atualizada para a versão 1.1 (D-0026 a D-0039).

## D-0013 · 2026-09-26 · Execução nativa no Windows; WSL fora; Docker só para sandbox
- **Decisão:** o daemon e os agentes rodam nativamente no Windows (Python 3.13 via uv). O WSL/OpenClaw não é usado. O Docker Desktop é usado só como sandbox S2, iniciado sob demanda.
- **Motivo:** Ollama e GPU estão no Windows; D-0010 já separa o WSL; Docker/WSL2 custa 1–4 GB de RAM e o baseline tem 5,2 GB livres.
- **Alternativas:** rodar tudo no WSL2 (duplicaria o ambiente e disputaria RAM).
- **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Complementada por D-0026 (usuário dedicado `afrunner` para código não confiável) e D-0030 (início no logon).

## D-0014 · 2026-09-26 · Um daemon + um subprocesso por task; comunicação por quadro-negro
- **Decisão:** um processo supervisor (`afd`) hospeda os serviços; cada task roda num `agent-runner` separado. Os agentes não falam entre si: usam Event Bus + Job Store e a API local (127.0.0.1 + token) para modelos e ferramentas.
- **Motivo:** isolamento de falhas, kill limpo, contabilidade de recursos por PID, ponto único de política.
- **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Complementada por D-0027 (tokens por papel) e D-0037 (escritor único do SQLite).

## D-0015 · 2026-09-26 · SQLite (WAL) como fonte da verdade; sem servidores de fila
- **Decisão:** `.appfactory/state/factory.db` guarda jobs, tasks, eventos, locks, leases, aprovações e uso. Nada de Redis, Celery ou RabbitMQ.
- **Motivo:** zero serviço extra, transacional, arquivo único, pouca RAM.
- **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Complementada por D-0037.

## D-0016 · 2026-09-26 · Orquestrador próprio, sem framework de agentes
- **Decisão:** máquina de estados, scheduler e protocolo de agentes próprios (contratos em `12-contratos.md`).
- **Motivo:** controle fino de recursos, segurança e persistência; evitar acoplamento a LangGraph/CrewAI/AutoGen.
- **Risco:** mais código a manter. **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`).

## D-0017 · 2026-09-26 · Ollama padrão; um modelo por vez na GPU; tiers
- **Decisão:** Ollama é o provedor padrão; lease único de GPU; tiers T0 (≤1 GB), T1 (≤3,5 GB), T2 (≤5,5 GB, exclusivo), EXT. Modelos `*-cloud` do Ollama são tratados como **externos**. `ollama pull` exige aprovação.
- **Motivo:** VRAM medida de 6141 MiB.
- **Status:** **ativa, revisada** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Revisada por D-0033 (classificação de modelos, posse, cloud = externo) e D-0032 (limite de 1 modelo passa a ser configuração com teto).

## D-0018 · 2026-09-26 · Política de recursos por modos
- **Decisão:** modos CRITICAL > BATTERY > CONTENTION > BACKGROUND > FOREGROUND com os limites de `RESOURCE_POLICY.md` e `05-resource-manager.md`. Substitui as políticas provisórias da Fase 0.
- **Motivo:** o usuário usa o computador enquanto a fábrica trabalha; notebook com bateria; GPU compartilhada com jogos.
- **Status:** **ativa, revisada** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Revisada por D-0032 (GPU no WDDM) e D-0038 (limiares de CPU e BATTERY).

## D-0019 · 2026-09-26 · Custo zero automático
- **Decisão:** orçamento padrão 0; provedores pagos vêm desligados; habilitar exige configuração do usuário + aprovação por job; o router nunca troca automaticamente para provedor pago (sem alternativa gratuita a task vai para WAITING).
- **Motivo:** exigência do usuário.
- **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Reforçada por D-0033 (`cost_class` ausente = pago e desligado).

## D-0020 · 2026-09-26 · Paralelismo com worktrees, locks de escrita e integração sequencial
- **Decisão:** 1 worktree/branch por task de escrita; `writes` declarados e impostos pelo Toolbox; hot files serializados; merge `--no-ff` sequencial na integração com QA após cada merge; merge em `main` só com aprovação humana.
- **Motivo:** evitar dois agentes no mesmo arquivo e manter rollback simples.
- **Status:** **ativa, revisada** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Revisada por D-0036 (1 job RUNNING por projeto, locks por projeto, regra de `writes`, worktree de integração).

## D-0021 · 2026-09-26 · Modelo de segurança
- **Decisão:** riscos R0–R3 (R3 sempre humano); sandbox S0/S1/S2; segredos no Windows Credential Manager via `keyring`, só por referência; ambiente de subprocessos limpo; auditoria append-only com hash encadeado; kill switch `.appfactory/STOP`.
- **Status:** **ativa, revisada** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Revisada por D-0026 (código não confiável/S1h), D-0027 (tokens e aprovações interativas) e D-0028 (STOP persistente).

## D-0022 · 2026-09-26 · Autoevolução com invariantes protegidas
- **Decisão:** o Evolution Agent só propõe (`EP-NNNN`), implementa em `evo/*`, passa nos guardrails I1–I7, compara com o baseline e depende de merge humano; não toca caminhos protegidos.
- **Status:** **ativa, revisada** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Revisada por D-0029 (infraestrutura protegida ampliada e rejeição automática).

## D-0023 · 2026-09-26 · Projetos gerados em `workspaces/`
- **Decisão:** cada app gerado é um repositório Git próprio em `workspaces/<projeto>/` (ignorado pelo Git da fábrica); worktrees em `workspaces/_worktrees/`.
- **Motivo:** separar a fábrica dos produtos; tudo sob `D:\Claude\app-factory` (D-0001).
- **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Complementada por D-0036 (worktree de integração).

## D-0024 · 2026-09-26 · Dados da fábrica só em D:
- **Decisão:** a fábrica não grava em C: (32,9 GB livres medidos). Recomenda-se ao usuário mover os modelos do Ollama para D: (KI-0008).
- **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`). Complementada por D-0034 (migração dos modelos do Ollama adiada).

## D-0025 · 2026-09-26 · Diagnóstico de hardware como utilitário versionado
- **Decisão:** `tools/diagnostics/measure-hardware.ps1` (somente leitura, sem nome de usuário/máquina) é versionado; snapshots ficam em `.appfactory/runtime/hardware/` (ignorado).
- **Motivo:** medir de novo quando o hardware ou o uso mudarem; não é código de produção.
- **Status:** **ativa** — confirmada na Fase 1.1 (histórico: proposta em 2026-09-26; v1.0 commitada em `4082457`).

---

# Fase 1.1 — Revisão e correção documental (2026-09-26) · base: revisão técnica do commit `4082457` (achados N1–N8)

Decisões do usuário registradas nesta revisão: sandbox opção B (S1 endurecido), 1 job RUNNING por projeto, daemon com início no logon e instância única (sem serviço), regras de classificação dos modelos do Ollama. Status: **aprovadas pelo usuário; pendentes de commit**.

## D-0026 · 2026-09-26 · Código gerado por agentes é não confiável; S1 endurecido (S1h)
- **Decisão:** todo código escrito/alterado por agentes, código dos projetos gerados, dependências e conteúdo externo são **não confiáveis** e só executam em **S1h** (usuário local dedicado `afrunner`, logon secundário, Job Object por task com limites de memória/CPU/processos e `KILL_ON_JOB_CLOSE`, ACL com Modify só no worktree da task e Deny herdado no resto da fábrica, sem token e sem segredos) ou **S2** (Docker). S2 é obrigatório para isolamento de rede, instalações com scripts, código de origem desconhecida, servidores e builds de release. `npm`/`pip` em S1h só sem scripts (08 §4.3).
- **Motivo:** achado N1 — o S1 anterior executava código não confiável com os privilégios do usuário. Opção B escolhida pelo usuário.
- **Riscos aceitos:** S1h sem isolamento de rede (KI-0015); viabilidade a provar (KI-0014); ACL padrão de `D:\` (KI-0016).
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0021.

## D-0027 · 2026-09-26 · Tokens por papel e aprovações interativas
- **Decisão:** papéis `user` (CLI), `runner` (por tentativa, escopo da task) e `ui` (futuro); S1h/S2 sem token. Aprovações e liberação de STOP só com token `user` **e** código de confirmação digitado no console. API em 127.0.0.1 com validação de `Host`, sem CORS.
- **Motivo:** N1 — impedir autoaprovação e uso indevido da API.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0021; complementa D-0014.

## D-0028 · 2026-09-26 · STOP persistente e em memória
- **Decisão:** STOP registrado na tabela `factory_stop` (antes de qualquer outra ação) e em memória. Qualquer papel pode acionar; só `af resume-factory` (usuário, com confirmação) libera. O arquivo `.appfactory/STOP` é apenas gatilho: apagá-lo **nunca** libera.
- **Motivo:** N1.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0021. Complementada por D-0054 (prazos do STOP medidos desde o T0 persistido).

## D-0029 · 2026-09-26 · Infraestrutura protegida ampliada e rejeição automática
- **Decisão:** lista de caminhos protegidos de `08-seguranca.md` §5.1 (inclui toolbox, resources, budget, provider_router, model_registry, checkpoints, logs/audit, jobs/recovery/leases/locks, core/auth/stop/instance, config de recursos/provedores/modelos/agentes, `pytest.ini`, `conftest.py`, `sitecustomize.py`, `*.pth`, guardrails, evals, normativos e estado versionado). Aplicada em 3 camadas (Toolbox, ACL, verificação de diff). EP ou task cujo diff toque caminho protegido ⇒ **rejeição automática**. Guardrails rodam por comando fixo com `--noconftest`. Vale para agentes em execução e Evolution; não impede sessões de desenvolvimento dirigidas pelo usuário (que registram em `DECISIONS.md`).
- **Motivo:** N2.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0022. Ampliada por D-0051 (núcleo do Job Manager e CLI) e D-0052 (`config/**`); alcance por tipo de repositório definido por D-0053; guardrails pendentes regidos por D-0048.

## D-0030 · 2026-09-26 · Ciclo de vida do daemon
- **Decisão:** instância única (mutex `Local\AppFactory-afd-<hash>` + `.appfactory/runtime/afd.lock` com PID e horário de criação); comandos `af daemon start/stop/status/restart`; início automático no logon via Agendador de Tarefas, **somente para o usuário conectado**, sem privilégios elevados; **não** é serviço do Windows nesta fase. A tarefa de logon é criada pelo usuário (`af daemon install-autostart`, R3).
- **Motivo:** N3 e decisão do usuário.
- **Status:** aprovada pelo usuário (Fase 1.1).

## D-0031 · 2026-09-26 · Leases em tempo ativo, verificação de vida, sono e Job Objects
- **Decisão:** leases e heartbeats medidos em tempo ativo do sistema (`QueryUnbiasedInterruptTime`); antes de declarar `interrupted`, verificar PID + horário de criação + Job Object; carência de 120 s após retorno do sono; Job Object raiz com `KILL_ON_JOB_CLOSE`; *dead-man switch* nos runners (45 s); nunca duas tentativas vivas da mesma task.
- **Motivo:** N3 — evitar execução duplicada após sono e órfãos após crash.
- **Status:** aprovada pelo usuário (Fase 1.1). Complementada por D-0054 (prazos de parada ancorados no T0 persistido).

## D-0032 · 2026-09-26 · Medição de GPU no Windows/WDDM
- **Decisão:** não depender de VRAM por processo (medido: `[N/A]`). VRAM da fábrica = `size_vram` dos modelos com posse da fábrica + overhead; VRAM de terceiros = modelos de outras ferramentas no Ollama + diferença do total; margem de medição 512 MiB (mín. 256); uso alheio só medido sem inferência da fábrica (janela de observação de 2 s); heurísticas de tela cheia/D3D e lista de processos. Limite de modelos na GPU passa a ser configuração com teto (`gpu.max_factory_models_loaded: 1`). Validação na fatia 2.3 (KI-0017).
- **Motivo:** N4.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0018 e D-0017.

## D-0033 · 2026-09-26 · Classificação de modelos do Ollama e posse
- **Decisão:** classes LOCAL_VERIFICADO (só por verificação real registrada em `local_allowlist`), CLOUD (`*-cloud` ou mesmo digest, sempre externo), DESCONHECIDO (não usado) e DE TERCEIROS (carregado por outras ferramentas). A fábrica só carrega LOCAL_VERIFICADO e só descarrega o que ela mesma carregou (registro de posse). `cost_class` ausente = `paid` + desligado (provedores e ferramentas); `privacy` ausente = externo. `qwen3-coder:latest` fica como CLOUD até verificação real.
- **Motivo:** N5 e decisão do usuário.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0017; reforça D-0019.

## D-0034 · 2026-09-26 · Migração dos modelos do Ollama para D: — ADIADA
- **Decisão:** registrar como **decisão futura** do usuário. Nesta fase nada foi alterado na instalação do Ollama, nas variáveis de ambiente ou na pasta de modelos.
- **Motivo:** C: com 32,9 GB livres (KI-0008), mas a mudança afeta outras ferramentas do usuário.
- **Status:** adiada (decisão do usuário).

## D-0035 · 2026-09-26 · Estado versionado × estado operacional
- **Decisão:** estado **versionado** = arquivos da raiz, `docs/architecture/`, `config/`, checkpoints e `.appfactory/job.json` (este só como resumo de marco). Estado **operacional** = `.appfactory/runtime/**` (inclui `runtime/job.json`, espelho de cada transição), `.appfactory/state/**`, `.appfactory/jobs/**`, `.appfactory/logs/**`, todos ignorados pelo Git. O Handoff System escreve só handoffs operacionais e do projeto gerado.
- **Motivo:** N6 — evitar repositório sempre alterado e mistura de estados.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0005 (texto original preservado).

## D-0036 · 2026-09-26 · Concorrência por projeto
- **Decisão:** no máximo **1 job RUNNING por projeto** na Fase 2 (paralelismo entre projetos permitido); locks **por projeto**; `writes` só com arquivos explícitos ou prefixos `dir/**`; worktree de integração em `workspaces/_worktrees/<p>/_integration-<job>`; checkout principal do projeto não é usado por agentes. Arquitetura preparada para mais jobs por projeto via `max_running_jobs_per_project` (hoje 1, protegido).
- **Motivo:** N7 e decisão do usuário.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0020.

## D-0037 · 2026-09-26 · Daemon como único escritor do SQLite
- **Decisão:** só o daemon abre `factory.db`; runners, CLI e UI usam a API. Estado e evento gravados na mesma transação; `synchronous=FULL` nas transições.
- **Motivo:** N7.
- **Status:** aprovada pelo usuário (Fase 1.1). Complementa D-0015.

## D-0038 · 2026-09-26 · Limiares canônicos de CPU e regra de BATTERY
- **Decisão:** `05-resource-manager.md` é a fonte canônica. CPU média 60 s > 70% → no máximo 1 admissão por minuto; > 85% → nenhuma nova admissão (agente ou pesado), o que roda continua. BATTERY limita admissões e só leva a `PAUSED` com bateria < 30% (exceto P0).
- **Motivo:** N7 — contradições entre `03`, `04` e `05`.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0018.

## D-0039 · 2026-09-26 · Fechamento da Fase 1 e checkpoint da Fase 1.1
- **Decisão:** CP-0002 validado no commit `4082457`; decisões D-0012 a D-0025 confirmadas (ativas, algumas revisadas); CP-0003 registra a Fase 1.1 e terá `validated_commit` preenchido no commit seguinte ao commit da revisão (D-0011).
- **Motivo:** N8.
- **Status:** aprovada pelo usuário (Fase 1.1).

---

# Fase 2.1 — Fundação: Job Manager (2026-09-26) · base: commit `97c82c4`

Decisões tomadas durante a implementação. Status: **em vigor no código da Fase 2.1** (commit `4373c65`, validado em `b0a80e5`).

## D-0040 · 2026-09-26 · Estados STOPPING e STOPPED para o STOP explícito de job
- **Decisão:** acrescentar aos 9 estados de `03-jobs.md` os estados `STOPPING` (transitório, ocupa a vaga do projeto) e `STOPPED` (parado de forma controlada, não terminal). `RUNNING/PLANNING → STOPPING → STOPPED`; `QUEUED/PAUSED/WAITING/BLOCKED → STOPPED` direto; `STOPPED → QUEUED` só por `af job resume`. O STOP da **fábrica** (kill switch, D-0028) continua separado e leva a `PAUSED(factory_stop)`.
- **Motivo:** o pedido da Fase 2.1 exige `running → stopping → stopped`; a arquitetura não tinha esses estados. Mantidos todos os estados já definidos.
- **Status:** em vigor (Fase 2.1). Revisa `03-jobs.md` §2.

## D-0041 · 2026-09-26 · Escopo da Fase 2.1 redefinido: fundação + núcleo do Job Manager
- **Decisão:** a Fase 2.1 passa a incluir o núcleo do Job Manager (antes previsto na 2.4), sem daemon, Job Objects, agentes ou sandbox. Tipos de job registrados no código têm plano implícito aprovado (`QUEUED → RUNNING`, 03 §2 nota \*); `PLANNING` fica sem uso até existir o Planner. Enquanto não há tasks, o job é a unidade executada e `RUNNING` sem tentativa aberta significa "pronto para retomar".
- **Motivo:** instrução do usuário para a Fase 2.1.
- **Status:** em vigor. Revisa `14-plano-fase-2.md`.

## D-0042 · 2026-09-26 · Fase 2.1 sem dependências de execução
- **Decisão:** somente biblioteca padrão (`sqlite3`, `argparse`, `dataclasses`, `threading`, `ctypes`). Testes em estilo `unittest`, executáveis também pelo pytest (`pytest.ini`). Typer, Pydantic e FastAPI (11-tecnologias) entram quando a API local e os contratos forem implementados.
- **Motivo:** o PyPI estava inacessível nos dois ambientes de verificação desta sessão; menos dependências = menos superfície e instalação trivial no Windows.
- **Status:** em vigor. Não revoga as escolhas de `11-tecnologias.md`, só as adia. Complementada por D-0049 (formato dos arquivos de configuração sem dependência de YAML).

## D-0043 · 2026-09-26 · Escritor único do SQLite: regime transitório
- **Decisão:** até existir o daemon (2.4), a CLI e os executores gravam pela mesma biblioteca, sempre em transações `BEGIN IMMEDIATE` (serializadas pelo SQLite, `busy_timeout` 30 s). D-0037 (só o daemon escreve) continua sendo o alvo e será aplicado na 2.4.
- **Motivo:** não há daemon nesta fase; a concorrência entre processos precisa ser segura mesmo assim (testado com threads e processos).
- **Status:** em vigor (transitório).

## D-0044 · 2026-09-26 · Posse por tentativa, verificação de vida e fencing
- **Decisão:** cada execução é uma tentativa com PID + horário de criação + `boot_id` e lease em tempo ativo (60 s; heartbeat 15 s). Lease vencido → verificação de vida; processo vivo ganha +2 leases de carência; depois disso perde a posse (`stalled`). Toda escrita do executor é **cercada** (*fencing*): tentativa que não é mais a dona recebe `LeaseLost` e para. Mudança de `boot_id` sozinha não tira a posse de um processo que continua vivo com a mesma identidade. Tentativa sem PID nunca é dada como morta pelo PID. `interrupted_attempts > 5` → `BLOCKED(needs_human)`.
- **Motivo:** 15 §5 sem Job Objects ainda; impedir dois executores no mesmo job; evitar laço infinito de queda.
- **Status:** em vigor. Na 2.4, processos mudos passam também a ser encerrados pelo Job Object.

## D-0045 · 2026-09-26 · Checkpoints de job no SQLite
- **Decisão:** tabela `checkpoints` com `seq` crescente (nunca sobrescreve), `kind` (`step`/`stop`/`pause`), checksum SHA-256 e triggers que proíbem apagar ou alterar (só `valid → invalid`). Gravação na mesma transação que atualiza o job. Último válido = maior `seq` com `status = 'valid'` e checksum íntegro; corrompidos são marcados `invalid` na recuperação. Arquivos de checkpoint de passo em `.appfactory/jobs/` ficam para quando houver tasks/ContextPacks.
- **Motivo:** atomicidade e "nunca ficar sem checkpoint recuperável".
- **Status:** em vigor.

## D-0046 · 2026-09-26 · Regras de falha
- **Decisão:** falha recuperável de passo → tentativa `failed`, job segue `RUNNING` (`retry_pending`) a partir do último checkpoint; após `max_attempts` (3) → `BLOCKED(needs_human)`. Falha fatal ou validação reprovada → `FAILED` (requeue manual). Falha ao gravar checkpoint → o anterior continua válido e a tentativa falha. Falha durante a parada → `STOPPED` com evento `job.stop_degraded` (a parada pedida prevalece; direção segura). Falha durante a recuperação de um job → evento `recovery.error`, os demais seguem, e a rotina é idempotente.
- **Motivo:** 03 §3, 07 §3–4 aplicados ao job sem tasks.
- **Status:** em vigor.

## D-0047 · 2026-09-26 · Somente handlers registrados; injeção de falhas controlada
- **Decisão:** o executor só roda handlers registrados no código (`demo.steps` nesta fase); o payload é JSON validado, sem código. Chaves `_faults` (simulação de quedas e falhas) só são aceitas com `AF_ALLOW_FAULT_INJECTION=1`, usado apenas pelos testes.
- **Motivo:** 08 §0 — nenhuma execução de código vindo de agente/usuário.
- **Status:** em vigor.

---

# Fase 2.2 — Decisões bloqueantes (2026-09-27) · base: commit `b0a80e5`

Pendências P-01, P-02, P-03, P-05, P-06, P-07 e P-15 da especificação `docs/specs/fase-2.2-guardrails-e-seguranca.md` (§9). Todas **aprovadas pelo usuário em 2026-09-27**. Aplicadas somente à documentação; nada implementado.

## D-0048 · 2026-09-27 · Guardrails pendentes: manifesto protegido; `pending` nunca é aprovação (P-01)
- **Decisão:** guardrails cujo componente ainda não existe **não falham**: seus testes são pulados com motivo e ficam registrados em `tests/guardrails/MANIFEST.json` (protegido por `tests/guardrails/**`), com cada invariante I1–I7 marcada `active` ou `pending:<fatia>` e o módulo esperado. Um teste de controle (`tests/guardrails/test_manifest.py`) **falha** se: (1) alguma invariante I1–I7 estiver fora do manifesto; (2) um `pending` não indicar fatia e módulo; (3) o módulo do componente já existir e o guardrail continuar `pending`; (4) uma invariante `active` tiver qualquer teste pulado. **`pending` nunca significa aprovação:** nenhum portão que dependa dos guardrails (EP do Evolution, 09 §2) pode aprovar com pendências; o **Evolution Agent só pode ser habilitado quando I1–I7 estiverem todas `active`**. Voltar uma invariante de `active` para `pending` exige decisão humana registrada neste arquivo.
- **Motivo:** conciliar `14-plano-fase-2.md` ("esqueletos falham até o componente existir") com `AGENTS.md` §5 ("nenhuma fase é concluída com teste crítico falhando"), sem esconder pendências e mantendo o portão fechado.
- **Alternativas rejeitadas:** `xfail(strict=True)` (esconde falhas pelo motivo errado); suíte falhando de verdade (viola `AGENTS.md` §5 e torna o portão inútil como sinal).
- **Status:** aprovada pelo usuário (2026-09-27). Revisa `14-plano-fase-2.md` (fatia 2.2); complementa D-0022/D-0029.

## D-0049 · 2026-09-27 · Arquivos de configuração `.yaml` no subconjunto JSON (P-02)
- **Decisão:** os arquivos de configuração mantêm os nomes `.yaml` definidos na arquitetura, mas são escritos **no subconjunto JSON do YAML 1.2** e lidos com o módulo `json` da biblioteca padrão. O leitor **recusa** tudo que não for JSON válido (falha fechada, sem tentativa de ler "quase YAML") e fica em módulo protegido (`src/appfactory/security/`) para que nenhum agente o substitua por um que devolva política vazia. Não há comentários nesses arquivos. Os exemplos com sintaxe YAML de `05-resource-manager.md` §9 e `08-seguranca.md` §3 passam a ser **ilustrativos** (conteúdo normativo, sintaxe não). Adotar um leitor YAML completo no futuro é decisão separada (os arquivos continuarão válidos).
- **Motivo:** a biblioteca padrão não lê YAML, `11-tecnologias.md` nunca escolheu biblioteca de YAML e D-0042 proíbe dependências sem decisão; o PyPI está bloqueado na VM de verificação.
- **Alternativas rejeitadas:** PyYAML (dependência nova, quebra a verificação na VM); renomear para `.json` (mudaria nomes em 05/08/10/12 sem ganho técnico).
- **Status:** aprovada pelo usuário (2026-09-27). Complementa D-0042; nenhuma dependência nova.

## D-0050 · 2026-09-27 · Toolbox mínimo na Fase 2.2 (P-03)
- **Decisão:** a fatia 2.2 inclui **somente** `src/appfactory/toolbox/fs.py` (ler, gravar, apagar, renomear com a política de caminhos) e `src/appfactory/toolbox/shell.py` (`exec_untrusted`: STOP → `CommandPolicy` → seleção de sandbox → journal → sandbox → resultado). `git.py`, `web.py`, `browser.py`, `db.py` e o restante do Toolbox ficam para a fatia 2.8. A `CommandPolicy` continua em `src/appfactory/security/`; o Toolbox só a aplica. Na 2.2 os sandboxes de produção (S1h/S2) falham fechados: **o Toolbox não executa código não confiável**.
- **Motivo:** a arquitetura exige o Toolbox como camada 1 de aplicação (08 §5.3) e ele não estava atribuído a nenhuma fatia; sem ele, STOP e falha durante execução não seriam testáveis na 2.2.
- **Alternativa rejeitada:** só bibliotecas de política na 2.2 (camada 1 inexistente; testes de execução reduzidos a unidade).
- **Status:** aprovada pelo usuário (2026-09-27). Revisa `14-plano-fase-2.md` (fatias 2.2 e 2.8).

## D-0051 · 2026-09-27 · Núcleo do Job Manager, CLI e módulos de invariantes são protegidos (P-05)
- **Decisão:** ampliar `08-seguranca.md` §5.1 com: `src/appfactory/jobs/store.py`, `jobs/manager.py`, `jobs/executor.py`, `jobs/states.py`, `jobs/handlers.py`, `src/appfactory/core/paths.py`, `core/clock.py`, `core/procinfo.py`, `src/appfactory/cli/main.py` e os futuros `jobs/state_machine.py`, `jobs/jobobjects.py` e `core/api.py`. Regra geral: **todo módulo que implemente uma invariante I1–I7 entra na lista antes de ser criado**. Os guardrails comportamentais continuam como segunda defesa.
- **Motivo:** a lógica que garante STOP, imutabilidade de checkpoints/eventos, confirmação para liberar STOP, escopo de remoção e verificação de vida está nesses arquivos, que não eram protegidos.
- **Alternativa rejeitada:** confiar só nos guardrails comportamentais (um EP poderia enfraquecer detalhe não coberto por teste).
- **Impacto:** melhorias nesses arquivos passam a exigir sessão de desenvolvimento dirigida pelo usuário (`AGENTS.md` §3.15); o código da 2.1 não muda.
- **Status:** aprovada pelo usuário (2026-09-27). Amplia D-0029.

## D-0052 · 2026-09-27 · Toda a pasta `config/` é protegida (P-06)
- **Decisão:** a linha "Políticas e limites" de `08-seguranca.md` §5.1 passa a ser `config/**` (inclui `factory.yaml`, subpastas e arquivos futuros de qualquer extensão), alinhando 08 com `10-diretorios.md`.
- **Motivo:** `factory.yaml` define portas, caminhos e o workspace padrão — mudar o workspace desviaria o escopo de escrita da política de arquivos e das ACLs; arquivos novos em `config/` passam a nascer protegidos.
- **Status:** aprovada pelo usuário (2026-09-27). Amplia D-0029.

## D-0053 · 2026-09-27 · Alcance dos caminhos protegidos: fábrica × projetos gerados (P-07)
- **Decisão:** a lista completa de `08-seguranca.md` §5.1 vale **no repositório da fábrica** (inclui worktrees `evo/*` do Evolution e qualquer task que altere a própria fábrica). Nos **repositórios de projetos gerados** (`workspaces/<projeto>`), o verificador de diff e o Toolbox rejeitam: alterações em `.git/**` e em `.appfactory/**` do projeto (escritos só por código confiável, como o Handoff System), symlinks (modo `120000`) e gitlinks/submódulos (modo `160000`), e qualquer escrita fora do `writes` da task (04 §3). O tipo de repositório é determinado **por código confiável**, pelo caminho real do repositório (diretório `.git` comum igual ao da fábrica ⇒ fábrica) — **nunca** por campo declarado na TaskSpec ou pelo agente; **na dúvida, vale a lista completa da fábrica**.
- **Motivo:** projetos gerados têm legitimamente `pytest.ini`, `conftest.py`, `.gitignore`, `README`/docs; o `conftest.py` de um projeto é código não confiável que só executa em S1h/S2 e não dá privilégio novo.
- **Alternativa rejeitada:** lista completa em todo repositório (bloquearia quase todo projeto Python, inviabilizando a fatia 2.8).
- **Status:** aprovada pelo usuário (2026-09-27). Complementa D-0029 e 08 §5.2–§5.3.

## D-0054 · 2026-09-27 · Prazos do STOP medidos desde o T0 persistido (P-15)
- **Decisão:** para STOP da fábrica, STOP/pausa/cancelamento de job e `af daemon stop`, **T0** é o instante gravado no SQLite na transação que registrou o pedido (`factory_stop.set_at`; `jobs.stop_requested_at`; para cancelamento ou pausa, o timestamp persistido correspondente, ex.: `jobs.cancelled_at`). Os prazos são cobrados pelo **código confiável que supervisiona a execução** (na 2.2, o laço de espera de `toolbox/shell.exec_untrusted`; a partir da 2.4/2.6, daemon e Job Object), nunca pelo código executado: **`terminate` em ≤ T0 + 30 s e encerramento total (kill da árvore) em ≤ T0 + 40 s**. A detecção do STOP por quem executa é feita por sondagem a cada **≤ 1 s** e só antecipa a cooperação — não adia os prazos. Proteção contra saltos de relógio: o prazo efetivo é o **menor** entre "T0 + 30 s" e "detecção + 30 s" medida em tempo ativo (15 §4). Os números 30 s, 10 s e 40 s de `01-componentes.md` §0 e 09 I6 não mudam; esta decisão fixa o marco zero. Limitação declarada até a 2.4 (KI-0019): passo de handler confiável executado no próprio processo que não consulte `should_stop` não pode ser morto sem Job Object.
- **Motivo:** heartbeat de 15 s + carência de 30 s + kill de 10 s poderia chegar a ~55 s se contado da detecção; medir desde a chegada do sinal ao runner enfraqueceria o STOP.
- **Alternativas rejeitadas:** reduzir a carência para 29 s (muda 01 §0 e continua dependendo da detecção); medir desde a chegada do sinal (enfraquece I6).
- **Status:** aprovada pelo usuário (2026-09-27). Complementa D-0028 e D-0031; esclarece 09 I6, 01 §0 e 15 §2/§9.

---

# Fase 2.2 — Implementação (2026-09-27) · base: commit `683b9e2`

## D-0055 · 2026-09-27 · Alterações aditivas em arquivos protegidos e escolhas provisórias da implementação da 2.2
- **Registro (AGENTS §3.15, D-0051):** para integrar a 2.2 ao Job Manager, a sessão dirigida pelo usuário alterou arquivos protegidos, de forma **aditiva** e mínima, sem mudar estados, tabelas, checkpoints, leases, locks nem o STOP existente:
  - `src/appfactory/jobs/manager.py`: `hold_attempt` (RUNNING → BLOCKED/WAITING com fencing, transições já existentes) e `record_violation` (evento `security.violation` + auditoria); `stop_factory` passa a auditar (`stop.set`, falha da auditoria nunca impede o STOP); `resume_factory` audita `stop.released` **antes** do commit (sem auditoria não há liberação).
  - `src/appfactory/jobs/executor.py`: `should_stop` também observa o STOP da fábrica (D-0054); trata `StepInterrupted` (para/pausa sem checkpoint do passo interrompido), `StepHeld` (tentativa já retida) e repassa `LeaseLost` levantado dentro do passo.
  - `src/appfactory/jobs/handlers.py`: `StepContext` ganha `job_id`, `attempt_id`, `manager`, `step_index`; exceções `StepInterrupted`/`StepHeld`. Nenhum handler novo em produção (D-0047).
  - `src/appfactory/cli/main.py`: `af guard check-diff|check-path`, `af audit verify`, `af guardrails run|status`.
- **Escolhas provisórias** (comportamento adotado na implementação para pendências não bloqueantes; nem todas seguem a recomendação da especificação — ver P-11, P-13 e P-14; **nenhuma pendência foi resolvida por esta decisão**; P-11 e P-08 foram decididas depois em D-0056 e D-0057; as demais, assim como P-04, continuam **pendentes de decisão do usuário**):
  - P-08: autorização só em memória (`core/auth.py`), sem API e sem arquivo de token. → **Decidida em D-0057** (aprovação com escopo limitado).
  - P-09: S1h exigido e indisponível ⇒ `BLOCKED` (sem escalonar automaticamente para S2).
  - P-10: instaladores fora da tabela 08 §4.3 (`uv pip/sync/add/run…`, `npx`, `yarn`, `pnpm`) ⇒ S2; limites do container = tetos do S1h; imagem sem política definida.
  - P-11: STOP da fábrica por guardrail não é acionado automaticamente nesta fase (só violações ⇒ `BLOCKED`; lista protegida inválida faz a operação falhar fechada, sem executar). **Difere** da recomendação (a) da especificação (§2.5 item 6, §9), que acionaria `stop_factory(reason="guardrail")` em falha de integridade. → **Decidida em D-0056** (aceito como provisório na 2.2; STOP por falha de integridade obrigatório na 2.4).
  - P-12: reincidência = 2ª violação no mesmo job ⇒ `BLOCKED(policy_violation)`; diff protegido bloqueia na 1ª.
  - P-13: sem âncora da auditoria no SQLite (recomendação (a) da especificação **não** implementada); corte das últimas linhas do `audit.jsonl` não é detectável só pela cadeia (KI-0021).
  - P-14: o Toolbox da 2.2 não executa `git` (S0 é recusado); o verificador de diff roda `git diff` com `--no-ext-diff --no-textconv` e `core.fsmonitor=false`. A recomendação (a) da especificação (`core.hooksPath` vazio, `GIT_CONFIG_NOSYSTEM`, verificação do `.git`) **não** foi implementada (KI-0022).
- **Status:** registrada na implementação (2026-09-27); as escolhas provisórias aguardam decisão do usuário, exceto P-11 (D-0056) e P-08 (D-0057).

## D-0056 · 2026-09-27 · STOP por perda de integridade dos guardrails: fail-closed na 2.2, STOP obrigatório na 2.4 (P-11)
- **Decisão (Fase 2.2):** perda de integridade dos próprios guardrails — `config/policies/protected-paths.yaml`, `config/policies/commands.yaml` ou `tests/guardrails/MANIFEST.json` ausente ou inválido — leva a **falha fechada**: a operação é recusada e **nenhuma execução é permitida**. O STOP global da fábrica **não** é acionado automaticamente nesta fase. A cadeia do `audit.jsonl` continua sendo verificada **manualmente** por `af audit verify`. Este comportamento fica **explicitamente aceito como provisório**.
- **Obrigação (Fase 2.4):** a integridade dos guardrails (arquivos de política, manifesto e cadeia de auditoria) deve ser verificada **antes de qualquer execução real**, a partir da partida do daemon; falha de integridade deve **obrigatoriamente** acionar o STOP da fábrica (`reason="guardrail"`, 08 §9; 12 §12), antes das execuções das fatias que dependem do daemon. Registrada em `TASK_QUEUE.md` e em `14-plano-fase-2.md` (fatia 2.4).
- **Motivo:** na 2.2 não há agentes nem execução não confiável (os sandboxes falham fechados), então o ganho imediato do STOP é pequeno e a verificação da cadeia a cada execução teria custo crescente; o lugar natural da verificação é a partida do daemon. A falha fechada já impede qualquer execução, e o STOP existente não é enfraquecido. Análise na especificação da 2.2 §9 (P-11).
- **Alternativa rejeitada:** alterar a implementação da 2.2 para acionar o STOP agora (reabriria a fase: arquivos protegidos, testes novos e nova validação no Windows).
- **Status:** aprovada pelo usuário (2026-09-27). Decide P-11; atualiza a escolha provisória registrada em D-0055; complementa D-0028 e D-0054.

## D-0057 · 2026-09-27 · Autorização `core/auth.py` aprovada na 2.2 com escopo limitado (P-08)
- **Decisão:** `src/appfactory/core/auth.py` fica aprovado como parte da Fase 2.2 **somente** para: matriz de autorização por papel (`user`/`runner`/`ui`, 12 §11); registro de tokens **em memória**; armazenamento **somente do hash** do token; comparação em tempo constante; expiração associada ao lease; revogação conforme a implementação atual; e os testes correspondentes (G22-18e, G22-47 e a verificação `I5.token_separation` dos guardrails).
- **O que a aprovação NÃO significa:** não existe API local; não existe daemon integrado; não existe arquivo persistente de tokens (`user.token`); não existe ACL; não existe autenticação operacional completa; a autorização **não** está aplicada a nenhuma API (ainda inexistente).
- **Obrigação futura:** a aplicação operacional completa da autorização fica para a fatia que implementar a API local/daemon (tokens por papel; 08 §8, 12 §11, D-0027). Registrada em `TASK_QUEUE.md` e em `14-plano-fase-2.md`.
- **Motivo:** o módulo é pequeno, protegido (D-0051), coberto por testes e fixa a matriz de 12 §11 antes da API; retirá-lo exigiria mudar código e testes, rebaixar uma verificação ativa dos guardrails e revalidar no Windows, sem ganho de segurança.
- **Alternativa rejeitada:** retirar ou adiar `core/auth.py` para a 2.6.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P-08; atualiza a escolha provisória registrada em D-0055; complementa D-0027.

---

# Fase 2.3 — Decisões do Resource Manager (2026-09-27) · base: commit `f44ac72`

Pendências P23-01 a P23-10 da especificação `docs/specs/fase-2.3-resource-manager.md` (§9). Todas **aprovadas pelo usuário em 2026-09-27**, conforme as recomendações da §9. Aplicadas somente à documentação; nada implementado. As pendências P-04, P-09, P-10, P-12, P-13 e P-14 da Fase 2.2 continuam independentes e abertas.

## D-0058 · 2026-09-27 · Coleta de métricas somente com a biblioteca padrão; NVML via `ctypes` (P23-01)
- **Decisão:** as sondas do Resource Manager usam **somente a biblioteca padrão**: APIs Win32 via `ctypes` e, para a coleta NVIDIA principal, a NVML pela `nvml.dll` do driver, também via `ctypes`. **Não** se usa psutil nem nvidia-ml-py, e o caminho principal **não** abre subprocesso `nvidia-smi`. Nenhuma dependência nova (D-0042).
- **Fallback `nvidia-smi` (implementado, permitido e isolado — não é só uma menção documental):** `nvidia-smi --query-gpu` é um fallback **implementado** na 2.3, conforme a especificação (§9, opção (b)), sujeito a estas regras: (1) existe **exclusivamente** em `src/appfactory/resources/probes/nvidia.py`; (2) só é usado quando a NVML estiver indisponível ou falhar — o caminho principal nunca abre subprocesso; se o fallback também falhar, vale o pior caso (05 §1); (3) está **sujeito ao AC-06**: a lista de subprocessos permitidos em `tests/unit/test_repo_hygiene.py` é ampliada, de forma aditiva, **somente** com `resources/probes/nvidia.py`; (4) **nenhum outro módulo** pode invocar `nvidia-smi` (verificação G23-30 da especificação); (5) somente consulta, sem `shell=True`.
- **Consequência:** as referências que apresentavam psutil e nvidia-ml-py como tecnologia prevista do Resource Manager foram atualizadas no fechamento documental da 2.3: `01-componentes.md` §4, `05-resource-manager.md` §1, `11-tecnologias.md` e `13-diagramas.md` §4. Referências explicitamente históricas foram preservadas.
- **Motivo:** D-0042 proíbe dependências sem decisão; o PyPI está bloqueado na VM de verificação; o AC-06 da 2.2 restringe subprocessos.
- **Alternativas rejeitadas:** (a) adicionar psutil + nvidia-ml-py; (c) biblioteca padrão sem fallback.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-01; complementa D-0042.

## D-0059 · 2026-09-27 · Leitura do `/api/ps` do Ollama; todo modelo conta como de terceiros até a 2.5 (P23-02)
- **Decisão:** na 2.3 a sonda de runtime local lê `GET http://127.0.0.1:11434/api/ps` **somente para leitura** e trata **todo** modelo carregado como de terceiros até existir o registro de posse (fatia 2.5, 06 §2.1): `vram_factory = 0` e toda VRAM vista no `/api/ps` entra em `vram_ollama_terceiros` (direção segura, 05 §1.1). Nenhuma chamada de escrita ao Ollama; nada é alterado na instalação, nas variáveis ou nos modelos (D-0034).
- **Motivo:** a contabilidade de VRAM do WDDM (D-0032) precisa distinguir modelos de terceiros, e a posse só existe na 2.5.
- **Alternativa rejeitada:** (b) não ler o Ollama na 2.3 (VRAM só pelo total).
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-02; complementa D-0032.

## D-0060 · 2026-09-27 · Admissão como biblioteca + CLI na 2.3; integração ao despacho de jobs na 2.4 (P23-03)
- **Decisão:** a 2.3 entrega a admissão (`ResourceManager.admit`, lease de GPU em memória) **somente como biblioteca e CLI** (`af resources admit` é simulação: nada é reservado). O Job Manager não muda: nenhuma transição `QUEUED → WAITING`, nenhuma mudança no `claim`, nenhuma mudança de estado de job por decisão de recurso. A integração da admissão ao despacho de jobs fica para a **Fase 2.4** (daemon).
- **Motivo:** `QUEUED → WAITING` não existe na máquina de estados (03), o despacho contínuo é do daemon (2.4) e o núcleo do Job Manager é protegido (D-0051).
- **Alternativas rejeitadas:** (b) `claim` consultar a admissão com `state_reason`; (c) nova transição `QUEUED → WAITING`.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-03. Obrigação registrada na `TASK_QUEUE.md` (2.4).

## D-0061 · 2026-09-27 · Persistência por eventos na 2.3; tabelas estruturadas na 2.4 (P23-04)
- **Decisão:** na 2.3 a persistência do Resource Manager é feita **somente por eventos** `resource.*` na tabela `events` existente (append-only). **Sem migração de schema** e sem alteração em `src/appfactory/jobs/store.py`. As tabelas `resource_samples` e `resource_decisions` (01 §4) ficam para a **Fase 2.4**.
- **Motivo:** não há daemon para amostragem contínua; `store.py` é protegido (D-0051); escritor único do SQLite ainda transitório (D-0043, KI-0020).
- **Alternativa rejeitada:** (a) migração de schema 2 na 2.3.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-04. Obrigação registrada na `TASK_QUEUE.md` (2.4).

## D-0062 · 2026-09-27 · Saída do modo CRITICAL exige o STOP da fábrica liberado (P23-05)
- **Decisão:** o modo CRITICAL só termina quando **todas** as condições de saída da política forem satisfeitas — RAM ≥ 2,5 GB **e** GPU ≤ 80 °C **e** disco de trabalho ≥ 10 GB por 60 s — **e** o STOP da fábrica estiver **liberado** (`factory_stop` inativo, liberado somente por `af resume-factory`, com confirmação do usuário — D-0028). **Apagar `.appfactory/STOP` nunca faz sair de CRITICAL.** O Resource Manager apenas **lê** `factory_stop` (fonte da verdade) e nunca o libera. A condição de entrada de 05 §2 não muda.
- **Correção documental:** `05-resource-manager.md` §2 corrigido ("kill switch removido" substituído pela liberação registrada do STOP), eliminando a contradição com D-0028.
- **Motivo:** o texto anterior de 05 §2 permitiria interpretar a remoção do arquivo como liberação, o que enfraqueceria o STOP (D-0028, 08 §9, 09 I6).
- **Alternativa rejeitada:** (b) manter o texto de 05 §2.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-05; complementa D-0028 e D-0038.

## D-0063 · 2026-09-27 · Histórico insuficiente para a janela ⇒ `WAIT`; `watch` acumula histórico (P23-06)
- **Decisão:** enquanto não houver amostras suficientes para a janela de decisão exigida (60 s de CPU, 30 s de RAM/GPU, 120 s de saída de CONTENTION, 10 min de ociosidade — 05 §1–§2), `admit` responde **`WAIT`** (falha fechada) e a CLI indica "janela incompleta". `af resources watch` acumula histórico em primeiro plano para permitir as avaliações. As janelas de 05 não são reduzidas. Continua valendo a regra de partida de 01 §4 (2 amostras antes de qualquer admissão).
- **Complemento (2026-09-27, fechamento documental da 2.3, aprovado pelo usuário):**
  - **Fonte do histórico:** `admit` (biblioteca e `af resources admit`) **lê o histórico acumulado pelo `watch`** — eventos `resource.snapshot` na tabela `events` (D-0061). `admit` **não** coleta amostras para completar janelas e **não** espera 60 s.
  - **Histórico suficiente:** para cada janela temporal exigida (05 §1–§2), amostras que cubram a janela inteira até o instante da consulta, sem lacuna entre amostras consecutivas e sem que a amostra mais recente seja mais antiga que a frequência da métrica em 05 §1; e no mínimo 2 amostras (01 §4). Sem `watch` em andamento, com histórico antigo ou com lacunas ⇒ **`WAIT`** ("janela incompleta").
  - **Frequência do `watch`:** intervalo padrão de coleta de **1 s**; configurável **somente** pela opção `--interval S` já prevista na CLI da especificação — nenhuma chave nova em `config/resources.yaml`.
  - **Eventos `resource.snapshot`:** cada amostra do `watch` vira um evento `resource.snapshot`, **append-only** nesta fase (triggers `events_no_update`/`events_no_delete` da 2.1). **Sem retenção nem limpeza automática** nesta fase.
  - O intervalo de 1 s não encurta nenhuma janela de 05 §1–§2 nem a histerese de 05 §2: janelas continuam medidas em tempo.
- **Motivo:** sem daemon (2.4) não há amostragem contínua; decidir sem a janela seria otimista.
- **Alternativa rejeitada:** (b) janelas reduzidas na 2.3.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-06; complementada no fechamento documental da 2.3 (fonte do histórico, frequência do `watch`, eventos append-only). Revisada por D-0070 (`sampling.interval_s: 1` como padrão do `watch`) e D-0071 (ociosidade é leitura instantânea; sai da lista de janelas).

## D-0064 · 2026-09-27 · Escopo do guardrail I4 para `config/resources.yaml` (P23-07)
- **Decisão:** o guardrail `I4.resources_config_within_ceilings` verifica os tetos do `RESOURCE_POLICY.md` e a margem de medição ≥ 256 MiB (D-0032) **e também** impede afrouxar qualquer limiar de `05-resource-manager.md` §4: reservas não podem ser menores e limiares de RAM, CPU e temperatura não podem ser mais permissivos que os valores canônicos (D-0038).
- **Motivo:** os limiares de 05 §4 não tinham "direção segura" formal; sem isso, `config/resources.yaml` poderia ser afrouxado dentro dos tetos.
- **Alternativa rejeitada:** (a) I4 verificar só a tabela de tetos + margem.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-07; complementa D-0038 e D-0048.

## D-0065 · 2026-09-27 · Limites do S1h continuam nas constantes da 2.2 (P23-08)
- **Decisão:** `config/resources.yaml` **não** ganha seção `sandbox` na 2.3; os limites do S1h continuam nas constantes da 2.2 (`security/sandbox`, `CEILINGS`/`limits_for`) até a 2.6. **P-09 continua aberta** (escolha provisória em D-0055).
- **Motivo:** evitar decidir P-09 indiretamente na 2.3.
- **Alternativa rejeitada:** (a) seção `sandbox` no `resources.yaml`.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-08; não decide P-09.

## D-0066 · 2026-09-27 · Matriz KI-0017: M1–M4 na 2.3, M5 na 2.5 (P23-09)
- **Decisão:** a 2.3 executa e registra os cenários M1 (ocioso), M2 (vídeo no navegador), M3 (jogo abrindo) e M4 (Ollama usado por outra ferramenta). O cenário M5 (inferência da fábrica + jogo) fica para a **Fase 2.5**, pois depende do Model Router e do registro de posse.
- **Alternativa rejeitada:** (b) exigir M5 na 2.3.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-09. Obrigação registrada na `TASK_QUEUE.md` (2.5).

## D-0067 · 2026-09-27 · Sonda Linux mínima só para desenvolvimento/VM (P23-10)
- **Decisão:** `src/appfactory/resources/probes/linux.py` é uma sonda mínima, **só para desenvolvimento e VM** (`/proc/meminfo`, `/proc/stat`, `statvfs`); o que não existir retorna o **pior caso** (05 §1). A plataforma-alvo continua sendo o Windows (D-0013).
- **Alternativa rejeitada:** (b) só sondas falsas fora do Windows.
- **Status:** aprovada pelo usuário (2026-09-27). Decide P23-10.

## D-0068 · 2026-09-27 · `GlobalMemoryStatusEx` é a fonte oficial de RAM do Resource Manager
- **Decisão:** a RAM do Resource Manager (disponível, total e commit livre) é lida pela API Win32 `GlobalMemoryStatusEx` via `ctypes` (`ullAvailPhys`, `ullTotalPhys`, `ullAvailPageFile`), conforme a especificação da 2.3 (§2.1). WMI/CIM **não** é fonte do Resource Manager. Referências da 2.3 atualizadas: `01-componentes.md` §4 (entradas) e `05-resource-manager.md` §1 (commit livre). Referências a WMI/CIM de outros contextos foram preservadas: medição da temperatura da CPU (05 §1, `RESOURCE_POLICY.md`) e a equivalência com WMI `FreeVirtualMemory` usada para comparar com `measure-hardware.ps1` (especificação §2.1).
- **Motivo:** coerência com D-0058 (somente biblioteca padrão, APIs Win32 via `ctypes`); WMI/CIM exigiria COM ou subprocesso.
- **Status:** aprovada pelo usuário (2026-09-27). Complementa D-0058.

## D-0069 · 2026-09-27 · Histerese dos modos medida por tempo decorrido contínuo de 10 s
- **Decisão:** a regra normativa de 05 §2 continua sendo **10 s**; ela **não** é reinterpretada como "2 avaliações a cada 5 s". A coleta pode ocorrer a cada 1 s (D-0063), mas a mudança de modo só vale quando a condição do novo modo estiver satisfeita de forma **contínua por pelo menos 10 s de tempo decorrido**, medido assim:
  - relógio: **tempo ativo monotônico** (`core/clock.py`, `active_ms`; 15 §4) — nunca o relógio de parede;
  - início da contagem: primeira amostra em que a condição do novo modo aparece; a mudança vale na primeira amostra em que `agora − início ≥ 10 s` com a condição ainda satisfeita;
  - continuidade: qualquer amostra em que a condição deixe de valer **reinicia** a contagem; lacuna entre amostras consecutivas maior que a frequência da métrica em 05 §1, troca de `boot_id` ou retorno do sono (15 §4) também **reiniciam** a contagem;
  - o número de amostras não conta: 10 amostras a 1 s em 9 s não bastam; 2 amostras separadas por 10 s só bastam se não houver lacuna maior que a frequência da métrica;
  - exceções de 05 §2 inalteradas: entrada em CRITICAL e volta do usuário são imediatas; as saídas com janela própria (CRITICAL 60 s, BATTERY 60 s, CONTENTION 120 s) seguem a mesma medição contínua por tempo, com as suas durações;
  - cada evento `resource.snapshot` registra o tempo ativo e o `boot_id`, para que `admit` aplique a mesma regra sobre o histórico do `watch` (D-0063).
- **Motivo:** com coleta a 1 s, contar "2 avaliações" reduziria a histerese para ~2 s e enfraqueceria a regra de 05 §2.
- **Status:** aprovada pelo usuário (2026-09-27). Complementa D-0018, D-0038 e D-0063.

## D-0070 · 2026-09-27 · `sampling` sem `mode_confirmations`; histerese fixa de 10 s; `interval_s: 1`
- **Decisão:** `config/resources.yaml` **não** tem `mode_confirmations`. A histerese de 10 s é regra normativa **fixa** (D-0069) e **não é configurável**; nenhuma chave nova de duração é criada. A chave existente `sampling.interval_s` passa a valer **1** e é a cadência padrão do `watch` (D-0063); `af resources watch --interval S` só a substitui naquela execução. Um intervalo maior não afrouxa nada: lacunas acima da frequência de 05 §1 tornam o histórico insuficiente (`WAIT`, D-0063) e reiniciam a histerese (D-0069). Os demais campos de `sampling` (`cpu_window_s: 60`, `gpu_window_s: 30`) não mudam.
- **Aplicação documental:** exemplo de `05-resource-manager.md` §9 atualizado; texto da histerese em 05 §2 e em `13-diagramas.md` §4 alinhado a D-0069 (10 s contínuos, não "2 avaliações/leituras").
- **Motivo:** `mode_confirmations: 2` contradizia D-0069 (histerese por tempo) e `interval_s: 5` contradizia o padrão de 1 s do `watch` (D-0063).
- **Status:** aprovada pelo usuário (2026-09-27). Resolve o conflito A do plano de implementação da 2.3; complementa D-0063 e D-0069.

## D-0071 · 2026-09-27 · Ociosidade é leitura instantânea
- **Decisão:** a ociosidade do usuário é lida como **valor atual** (`GetLastInputInfo`, 05 §1), sem histórico. A decisão BACKGROUND/FOREGROUND usa o valor atual: ocioso ≥ 10 min ⇒ condição de BACKGROUND (sujeita à histerese de 10 s, D-0069); qualquer entrada do usuário ⇒ FOREGROUND imediato (05 §2). `admit` **não** exige 10 min de histórico. O histórico temporal (D-0063) é exigido **somente** pelas métricas com janela explícita na política: CPU média de 60 s, RAM mínima de 30 s, GPU média de 30 s, crescimento de `vram_terceiros` em 30 s e as saídas de modo por tempo (CRITICAL 60 s, BATTERY 60 s, CONTENTION 120 s).
- **Motivo:** D-0063 citava "10 min de ociosidade" como janela de histórico, em conflito com 05 §1 ("valor atual").
- **Status:** aprovada pelo usuário (2026-09-27). Resolve o conflito B do plano de implementação da 2.3; corrige a lista de janelas de D-0063.

## D-0072 · 2026-09-27 · Reserva de RAM do modo CONTENTION = 3,0 GB
- **Decisão:** `reserves.ram_gb.CONTENTION = 3.0`. Em CONTENTION, esse valor é a `reserva[modo]` das fórmulas de `slots_ram`, de processos pesados (`ram_disp ≥ reserva + 1,0`) e de S2 (`ram_disp ≥ reserva + 3,0 GB`). Vale como valor canônico para o guardrail I4 (D-0064: reserva não pode ser menor).
- **Aplicação documental:** exemplo de `05-resource-manager.md` §9, `04` §8 (lista de reservas) e especificação da 2.3.
- **Motivo:** 05 §9 só definia reservas para FOREGROUND, BACKGROUND e BATTERY, mas CONTENTION admite 2 agentes e 1 pesado; 3,0 GB é a maior reserva existente (direção segura).
- **Status:** aprovada pelo usuário (2026-09-27). Resolve o conflito C do plano de implementação da 2.3; complementa D-0038 e D-0064.

---

# Fase 2.3 — Implementação (2026-09-27) · base: commit `f44ac72`

## D-0073 · 2026-09-27 · Arquivos protegidos da 2.3 e escolhas de implementação do Resource Manager
- **Registro (AGENTS §3.15, D-0051):** a sessão dirigida pelo usuário **criou** arquivos em caminhos protegidos — `config/resources.yaml` e `src/appfactory/resources/**` (`policy.py`, `probes/{__init__,windows,nvidia,runtime_local,linux}.py`, `gpu_accounting.py`, `modes.py`, `history.py`, `manager.py`, `compare.py`) — e alterou, de forma **aditiva**, arquivos protegidos:
  - `src/appfactory/cli/main.py`: grupo `af resources snapshot|mode|admit|watch|compare` (nenhum comando existente mudou);
  - `tests/guardrails/test_resource_limits.py`: o teste `I4.resources_config_within_ceilings` deixa de só importar o módulo e verifica tetos, margem, reservas (CONTENTION 3,0 GB) e limiares canônicos, com cópia literal própria;
  - `tests/guardrails/MANIFEST.json`: `I4.resources_config_within_ceilings` passa de `pending` a `active` (D-0048, regra 3); nenhuma outra verificação mudou;
  - `tests/unit/test_repo_hygiene.py` (não protegido): lista do AC-06 ganha só `resources/probes/nvidia.py`; novo teste G23-30 (`nvidia-smi` citado só nesse módulo).
  Não foram alterados: Job Manager (`jobs/**`), `core/stop.py`, `core/clock.py`, `security/**`, `pyproject.toml`, `protected-paths.yaml`, `commands.yaml`, `measure-hardware.ps1`, Ollama. Nenhuma tabela, índice ou migração nova.
- **Escolhas de implementação** (dentro de D-0058 a D-0072; nenhuma afrouxa limiar ou teto):
  - constantes fixas, não configuráveis, em `resources/policy.py`: lacuna máxima entre amostras 5 s (menor frequência de 05 §1), tolerância de sono 1 s (relógio com suspensão — `GetTickCount64`/`CLOCK_BOOTTIME` — contra o tempo ativo), saída de disco de CRITICAL 10 GB (05 §2), `vram_base` 105 MiB (medido; recalibrar só por decisão, KI-0017), 0,4 GB por agente e +1,0 GB por pesado (04 §8);
  - esquema fechado de `config/resources.yaml`: chave desconhecida ou ausente torna a política inválida (falha fechada);
  - modo inicial nunca mais permissivo que FOREGROUND (CRITICAL/BATTERY/CONTENTION valem de imediato na partida; BACKGROUND só pela histerese); modo sem reserva própria usa a maior reserva definida;
  - valores desconhecidos: RAM/disco 0, CPU 100%, temperatura da GPU crítica, energia = bateria 0%, tela cheia = sim, ociosidade = ativo; lista de processos desconhecida não dispara CONTENTION sozinha (05 §1); na VM Linux o modo resulta sempre CRITICAL;
  - admissão: STOP da fábrica (tabela ou arquivo-gatilho, lidos a cada consulta) ⇒ `DENY`; CRITICAL ⇒ `WAIT`; tier desconhecido ⇒ tratado como T2; `gpu` sem estimativa de VRAM ⇒ `DENY`; BATTERY com bateria abaixo de `pause_below_pct` ⇒ `WAIT` exceto P0; histórico gerado com outra política (hash) ou outro boot ⇒ `WAIT`;
  - contadores de agentes/pesados, lease de GPU e o limite "1 admissão por minuto" existem só na memória do processo (entre processos na 2.4, D-0060);
  - `resource.probe_failed` é gravado na transição ok → falha de cada sonda; a lista de falhas vai em todo `resource.snapshot`; `af resources snapshot` não grava eventos;
  - `af resources watch --count N` (opção adicional, para validação) limita o número de amostras.
- **Status:** registrada na implementação (2026-09-27). Validação no Windows, comparação com `measure-hardware.ps1` e matriz KI-0017 (M1–M4) pendentes do usuário.

## D-0074 · 2026-09-27 · Correção: uso alheio da GPU avaliado pela média de 30 s (05 §1)
- **Defeito encontrado na validação real (matriz KI-0017, M2):** `modes.py` avaliava o critério de CONTENTION "uso alheio da GPU > 20%" pelo **valor instantâneo** de cada amostra, mas 05 §1 define a janela de decisão da GPU como **média de 30 s**. Com vídeo no navegador, o uso real alternou entre 0% e ~40% a cada amostra; pelo valor instantâneo a condição nunca ficava contínua por 10 s (D-0069), o que tornava o critério mais permissivo do que a especificação.
- **Correção (só o necessário):** o critério passa a usar a média das amostras **sem chamada da fábrica** (05 §1.1) nos últimos `sampling.gpu_window_s` (30 s) de tempo ativo; valor desconhecido entra como 100% (pior caso); a média é zerada nos mesmos casos em que a continuidade é perdida (D-0069) e registrada em `reasons.gpu_util_avg`. Os demais critérios não mudam (temperatura e VRAM continuam pela leitura instantânea, que é mais restritiva na entrada). Teste novo `test_g23_16_foreign_util_uses_30s_average` (falharia com o valor instantâneo).
- **Efeito nos dados reais** (reprocessamento dos JSONL, só análise): amostras com o critério de uso da GPU ativo — M1 0 → 0; M2 62 → 91; M3 69 → 98; M4 16 → 38. Modo final igual em M1–M4 (M2–M4 continuam em CRITICAL por RAM).
- **Status:** registrada na validação (2026-09-27). Arquivos: `src/appfactory/resources/modes.py` (protegido; sessão dirigida pelo usuário) e `tests/unit/test_resource_modes.py`. Exige repetir `uv run pytest` e os guardrails no Windows.

## D-0075 · 2026-09-27 · Correção: `/api/ps` a cada 15 s, em segundo plano; `watch` mantém o intervalo nominal
- **Defeito encontrado na validação real (rodada 2.3b, M2 e M3):** a sonda do Ollama era consultada em **toda** amostra, de forma síncrona. Com o Ollama sem responder, cada consulta esperava o timeout de 2 s e o intervalo real do `watch` passou de ~1 s para ~3,1 s (180 amostras em ~555 s). Isso contrariava 05 §1 (`/api/ps` a cada 15 s) e o intervalo padrão de 1 s (D-0063, D-0070).
- **Correção (só o necessário):** `resources/probes/runtime_local.py` consulta `/api/ps` **no máximo a cada 15 s**; a 1ª consulta é síncrona (para `snapshot`/`compare` de uma amostra) e as seguintes rodam **em segundo plano** (uma de cada vez), sem nunca atrasar a amostra. Entre consultas, cada amostra usa o último resultado concluído. **Fail-closed mantido:** consulta que falha, ou resultado com mais de 32 s (2 × 15 s + timeout), deixa os modelos desconhecidos (`None`, pior caso) e registra falha `runtime_local` em **toda** amostra até a próxima consulta bem-sucedida. A amostra passa a registrar `ollama_age_s`. `manager.watch` desconta o tempo gasto em cada amostra, de modo que o período fica no intervalo nominal (1 s) em vez de intervalo + duração da amostra.
- **Não muda:** critérios G23/AC23, precedência dos modos, janelas, histerese, limiares, D-0059 (somente `GET /api/ps`).
- **Testes:** `OllamaSchedule` em `tests/unit/test_probes.py` (no máximo 1 consulta a cada 15 s; consulta vencida só agendada; sem duplicar consulta em andamento; falha registrada e pior caso até o sucesso; resultado velho = pior caso; em tempo real, Ollama lento e com falha não altera a cadência) e desconto do tempo da amostra em `tests/integration/test_cli_resources.py`.
- **Status:** registrada na validação (2026-09-27). Arquivos: `resources/probes/runtime_local.py`, `resources/probes/__init__.py`, `resources/manager.py` (protegidos; sessão dirigida pelo usuário), `tests/fakes/probes.py`, `tests/unit/test_probes.py`, `tests/integration/test_cli_resources.py`. Exige repetir `uv run pytest` e os guardrails no Windows.
