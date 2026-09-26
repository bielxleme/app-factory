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
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0021.

## D-0029 · 2026-09-26 · Infraestrutura protegida ampliada e rejeição automática
- **Decisão:** lista de caminhos protegidos de `08-seguranca.md` §5.1 (inclui toolbox, resources, budget, provider_router, model_registry, checkpoints, logs/audit, jobs/recovery/leases/locks, core/auth/stop/instance, config de recursos/provedores/modelos/agentes, `pytest.ini`, `conftest.py`, `sitecustomize.py`, `*.pth`, guardrails, evals, normativos e estado versionado). Aplicada em 3 camadas (Toolbox, ACL, verificação de diff). EP ou task cujo diff toque caminho protegido ⇒ **rejeição automática**. Guardrails rodam por comando fixo com `--noconftest`. Vale para agentes em execução e Evolution; não impede sessões de desenvolvimento dirigidas pelo usuário (que registram em `DECISIONS.md`).
- **Motivo:** N2.
- **Status:** aprovada pelo usuário (Fase 1.1). Revisa D-0022.

## D-0030 · 2026-09-26 · Ciclo de vida do daemon
- **Decisão:** instância única (mutex `Local\AppFactory-afd-<hash>` + `.appfactory/runtime/afd.lock` com PID e horário de criação); comandos `af daemon start/stop/status/restart`; início automático no logon via Agendador de Tarefas, **somente para o usuário conectado**, sem privilégios elevados; **não** é serviço do Windows nesta fase. A tarefa de logon é criada pelo usuário (`af daemon install-autostart`, R3).
- **Motivo:** N3 e decisão do usuário.
- **Status:** aprovada pelo usuário (Fase 1.1).

## D-0031 · 2026-09-26 · Leases em tempo ativo, verificação de vida, sono e Job Objects
- **Decisão:** leases e heartbeats medidos em tempo ativo do sistema (`QueryUnbiasedInterruptTime`); antes de declarar `interrupted`, verificar PID + horário de criação + Job Object; carência de 120 s após retorno do sono; Job Object raiz com `KILL_ON_JOB_CLOSE`; *dead-man switch* nos runners (45 s); nunca duas tentativas vivas da mesma task.
- **Motivo:** N3 — evitar execução duplicada após sono e órfãos após crash.
- **Status:** aprovada pelo usuário (Fase 1.1).

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
