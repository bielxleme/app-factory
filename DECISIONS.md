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
- **Status:** ativa; complementada por D-0015 (o banco SQLite passa a ser a fonte da verdade da execução; esses arquivos são visões humanas mantidas pelo Handoff System).

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
- **Status:** proposta (vira ativa com o commit aprovado pelo usuário).

## D-0013 · 2026-09-26 · Execução nativa no Windows; WSL fora; Docker só para sandbox
- **Decisão:** o daemon e os agentes rodam nativamente no Windows (Python 3.13 via uv). O WSL/OpenClaw não é usado. O Docker Desktop é usado só como sandbox S2, iniciado sob demanda.
- **Motivo:** Ollama e GPU estão no Windows; D-0010 já separa o WSL; Docker/WSL2 custa 1–4 GB de RAM e o baseline tem 5,2 GB livres.
- **Alternativas:** rodar tudo no WSL2 (duplicaria o ambiente e disputaria RAM).
- **Status:** proposta.

## D-0014 · 2026-09-26 · Um daemon + um subprocesso por task; comunicação por quadro-negro
- **Decisão:** um processo supervisor (`afd`) hospeda os serviços; cada task roda num `agent-runner` separado. Os agentes não falam entre si: usam Event Bus + Job Store e a API local (127.0.0.1 + token) para modelos e ferramentas.
- **Motivo:** isolamento de falhas, kill limpo, contabilidade de recursos por PID, ponto único de política.
- **Status:** proposta.

## D-0015 · 2026-09-26 · SQLite (WAL) como fonte da verdade; sem servidores de fila
- **Decisão:** `.appfactory/state/factory.db` guarda jobs, tasks, eventos, locks, leases, aprovações e uso. Nada de Redis, Celery ou RabbitMQ.
- **Motivo:** zero serviço extra, transacional, arquivo único, pouca RAM.
- **Status:** proposta.

## D-0016 · 2026-09-26 · Orquestrador próprio, sem framework de agentes
- **Decisão:** máquina de estados, scheduler e protocolo de agentes próprios (contratos em `12-contratos.md`).
- **Motivo:** controle fino de recursos, segurança e persistência; evitar acoplamento a LangGraph/CrewAI/AutoGen.
- **Risco:** mais código a manter. **Status:** proposta.

## D-0017 · 2026-09-26 · Ollama padrão; um modelo por vez na GPU; tiers
- **Decisão:** Ollama é o provedor padrão; lease único de GPU; tiers T0 (≤1 GB), T1 (≤3,5 GB), T2 (≤5,5 GB, exclusivo), EXT. Modelos `*-cloud` do Ollama são tratados como **externos**. `ollama pull` exige aprovação.
- **Motivo:** VRAM medida de 6141 MiB.
- **Status:** proposta.

## D-0018 · 2026-09-26 · Política de recursos por modos
- **Decisão:** modos CRITICAL > BATTERY > CONTENTION > BACKGROUND > FOREGROUND com os limites de `RESOURCE_POLICY.md` e `05-resource-manager.md`. Substitui as políticas provisórias da Fase 0.
- **Motivo:** o usuário usa o computador enquanto a fábrica trabalha; notebook com bateria; GPU compartilhada com jogos.
- **Status:** proposta.

## D-0019 · 2026-09-26 · Custo zero automático
- **Decisão:** orçamento padrão 0; provedores pagos vêm desligados; habilitar exige configuração do usuário + aprovação por job; o router nunca troca automaticamente para provedor pago (sem alternativa gratuita a task vai para WAITING).
- **Motivo:** exigência do usuário.
- **Status:** proposta.

## D-0020 · 2026-09-26 · Paralelismo com worktrees, locks de escrita e integração sequencial
- **Decisão:** 1 worktree/branch por task de escrita; `writes` declarados e impostos pelo Toolbox; hot files serializados; merge `--no-ff` sequencial na integração com QA após cada merge; merge em `main` só com aprovação humana.
- **Motivo:** evitar dois agentes no mesmo arquivo e manter rollback simples.
- **Status:** proposta.

## D-0021 · 2026-09-26 · Modelo de segurança
- **Decisão:** riscos R0–R3 (R3 sempre humano); sandbox S0/S1/S2; segredos no Windows Credential Manager via `keyring`, só por referência; ambiente de subprocessos limpo; auditoria append-only com hash encadeado; kill switch `.appfactory/STOP`.
- **Status:** proposta.

## D-0022 · 2026-09-26 · Autoevolução com invariantes protegidas
- **Decisão:** o Evolution Agent só propõe (`EP-NNNN`), implementa em `evo/*`, passa nos guardrails I1–I7, compara com o baseline e depende de merge humano; não toca caminhos protegidos.
- **Status:** proposta.

## D-0023 · 2026-09-26 · Projetos gerados em `workspaces/`
- **Decisão:** cada app gerado é um repositório Git próprio em `workspaces/<projeto>/` (ignorado pelo Git da fábrica); worktrees em `workspaces/_worktrees/`.
- **Motivo:** separar a fábrica dos produtos; tudo sob `D:\Claude\app-factory` (D-0001).
- **Status:** proposta.

## D-0024 · 2026-09-26 · Dados da fábrica só em D:
- **Decisão:** a fábrica não grava em C: (32,9 GB livres medidos). Recomenda-se ao usuário mover os modelos do Ollama para D: (KI-0008).
- **Status:** proposta.

## D-0025 · 2026-09-26 · Diagnóstico de hardware como utilitário versionado
- **Decisão:** `tools/diagnostics/measure-hardware.ps1` (somente leitura, sem nome de usuário/máquina) é versionado; snapshots ficam em `.appfactory/runtime/hardware/` (ignorado).
- **Motivo:** medir de novo quando o hardware ou o uso mudarem; não é código de produção.
- **Status:** proposta.
