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
- **Status:** ativa.

## D-0005 · 2026-09-26 · Arquivos de estado como memória operacional
- **Decisão:** usar `AGENTS.md`, `PROJECT_STATE.md`, `TASK_QUEUE.md`, `DECISIONS.md`, `CHANGELOG.md`, `HANDOFF.md`, `KNOWN_ISSUES.md`, `TEST_STATUS.md`, `RESOURCE_POLICY.md`, `COMMAND_LOG.md`, `.appfactory/job.json` e `.appfactory/checkpoints/`.
- **Motivo:** permitir que qualquer IA continue o trabalho sem reiniciar o projeto.
- **Status:** ativa.

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
- **Status:** ativa.
