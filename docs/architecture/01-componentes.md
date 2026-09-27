# 01 — Componentes

Cada componente tem os 14 campos exigidos. Onde aparece **Padrão**, vale o §0.

**Revisão 1.1 (2026-09-26):** código gerado por agentes é não confiável e só executa em S1h/S2 (N1); o daemon é o único escritor do SQLite (N7); ciclo de vida de runners com Job Object (N3); posse de modelos (N5); handoff operacional separado do estado versionado (N6).

## 0. Padrões comuns

- **Serviços** (Job Manager, Resource Manager, routers, Checkpoint, Logging, Handoff, Memory) rodam **dentro do daemon `afd`**.
- **Agentes** rodam como **subprocesso `agent-runner`** (código confiável da fábrica, usuário principal, dentro do Job Object do daemon), um por task, sem estado próprio. Todo código **não confiável** que o agente mandar executar (testes, scripts, app gerado) roda em **S1h** (usuário `afrunner`) ou **S2** via Toolbox (08 §0 e §4). O runner recebe `TaskSpec` + `ContextPack` e devolve `TaskResult` + artefatos (ver `12-contratos.md`).
- **Comunicação (Padrão):** agentes nunca falam diretamente entre si. Publicam/consomem eventos e leem/escrevem o **Job Store** (padrão *blackboard*) **exclusivamente pela API local do daemon**, com token `runner` de escopo da própria task (08 §8). **Somente o daemon abre o SQLite** (D-0037). Chamadas a modelos e ferramentas também vão pela API.
- **Registro de estado (Padrão):** eventos `task.*` no Event Store (SQLite) + checkpoint de passo em `.appfactory/jobs/<job>/tasks/<task>/step-NNN.json` + log JSONL.
- **Interrupção (Padrão):** cooperativa. O runner checa o *cancel token* entre passos; ao receber `pause/cancel` termina o passo atual, grava checkpoint e sai. Se não sair em 30 s: `terminate`; mais 10 s: kill da árvore de processos. **Os prazos contam desde o T0 persistido no SQLite** (`factory_stop.set_at`, `jobs.stop_requested_at` ou, em cancelamento/pausa, o timestamp persistido do pedido) e são cobrados pelo código confiável supervisor, não pelo código executado: `terminate` ≤ T0 + 30 s, encerramento total ≤ T0 + 40 s; quem executa sonda o STOP a cada ≤ 1 s (D-0054). Operações marcadas como não-interrompíveis (ex.: `git commit`, escrita de migração) terminam antes, sempre dentro desses prazos. Se o daemon desaparecer, o Job Object raiz (`KILL_ON_JOB_CLOSE`) encerra tudo; o runner também tem *dead-man switch* (15 §7–8).
- **Retomada (Padrão):** novo `agent-runner` com o mesmo `TaskSpec`, a partir do último checkpoint de passo e do `ContextPack` salvo. Passos com efeito colateral usam o **journal de ferramentas** (intenção gravada antes, resultado depois) para não repetir ações já feitas. Nova tentativa só depois da verificação de vida da anterior (15 §5).
- **Modelos:** tiers `T0` (≤1 GB), `T1` (≤3,5 GB), `T2` (≤5,5 GB, exclusivo da GPU), `EXT` (externo). Ver `06-provider-model-router.md`.

---

## 1. MASTER AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Interface conversacional com o usuário: entender a intenção, pedir esclarecimentos, criar o Job, repassar pedidos de aprovação, informar status e entregar resultados. **Não escreve código nem planeja em detalhe.** |
| Entradas | Mensagem do usuário (CLI/UI), eventos `job.*`, `approval.requested`, `task.blocked`. |
| Saídas | `JobRequest` (objetivo, restrições, critérios de aceite iniciais), respostas ao usuário, decisões de aprovação registradas. |
| Ferramentas | Memory (leitura), Job Manager API (criar/pausar/cancelar), Approval Gate. |
| Permissões | R0 (somente leitura de arquivos) + criar/pausar/cancelar jobs do próprio usuário. Não executa shell nem escreve em workspaces. |
| Dependências | Job Manager, Memory/Context, Model Router, Approval Gate, Logging. |
| Quando executar | Sempre que houver entrada do usuário ou evento que precise de resposta humana. |
| Quando NÃO executar | Para tarefas técnicas (delegar ao Planner); quando o daemon estiver em modo CRITICAL, só responde com status. |
| Paralelo | Sim, é leve; 1 instância por conversa ativa. |
| Recursos | Modelo T0/T1 (ex.: `qwen3.5:2b`) ou EXT se permitido; ~150 MB RAM de runner. Prioridade P0. |
| Comunicação | Padrão + canal direto com a interface do usuário. |
| Registro de estado | Padrão + transcrição da conversa em `.appfactory/jobs/<job>/conversation.jsonl`. |
| Interrupção | Padrão. Resposta parcial é descartada; a mensagem do usuário continua registrada. |
| Retomada | Relê a transcrição e o estado do job; responde a partir da última mensagem sem resposta. |

## 2. PLANNER / ARCHITECT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Transformar o `JobRequest` em **especificação** + **plano DAG de tasks**, com critérios de aceite, conjunto de arquivos que cada task escreve (`writes`), tier de modelo sugerido, riscos e pontos de aprovação. Replaneja quando uma task falha além do limite. |
| Entradas | `JobRequest`, memória do projeto (DECISIONS, arquitetura, código existente via índice), resultados do Research Agent. |
| Saídas | `spec.md`, `plan.json` (DAG), decisões propostas para `DECISIONS.md` do projeto gerado. |
| Ferramentas | Memory/índice de código, leitura de arquivos, Research Agent (via tasks), Model Router. |
| Permissões | R0 no workspace; escreve apenas em `.appfactory/jobs/<job>/`. |
| Dependências | Master, Memory, Research, Model Router, Job Manager. |
| Quando executar | Job novo em `PLANNING`; replanejamento após falha repetida ou mudança de escopo aprovada. |
| Quando NÃO executar | Pedidos triviais de uma task (o Master cria plano de 1 task direto); durante `PAUSED`. |
| Paralelo | Não dentro do mesmo job (um plano por vez). Jobs diferentes podem planejar em paralelo se houver slot. |
| Recursos | Melhor modelo disponível: EXT (se permitido) ou T2 local (`qwen3:8b`) com lease exclusivo de GPU. |
| Comunicação | Padrão; publica `plan.created` / `plan.revised`. |
| Registro de estado | Padrão + versões `plan.v<N>.json` (nunca sobrescreve). |
| Interrupção | Padrão. |
| Retomada | Retoma do último rascunho salvo; se o contexto mudou (commit novo), reinicia a análise. |

## 3. JOB MANAGER

| Campo | Definição |
| --- | --- |
| Responsabilidade | Dono do ciclo de vida de jobs e tasks: fila, prioridades, dependências do DAG, leases/heartbeats (tempo ativo), locks de arquivos **por projeto**, regra de **no máximo 1 job RUNNING por projeto**, lançamento e término de `agent-runner` em Job Objects, retries, integração (merge) de branches, recuperação após falha. |
| Entradas | `JobRequest`, `plan.json`, eventos de tasks, decisões de admissão do Resource Manager, comandos do usuário (pause/resume/cancel/priority). |
| Saídas | Transições de estado, processos iniciados/terminados, eventos `job.*`/`task.*`, espelho `.appfactory/job.json`. |
| Ferramentas | SQLite, Toolbox (git worktree/merge), gerenciamento de processos (psutil). |
| Permissões | Criar/remover worktrees em `workspaces/_worktrees/` (inclusive `_integration-<job>`), conceder/revogar a ACL do `afrunner` no worktree da task, merge em branches `af/*`. **Nunca** em `main` sem aprovação. |
| Dependências | Resource Manager, Checkpoint, Logging, Security (políticas), Event Bus. |
| Quando executar | Sempre (serviço do daemon); ciclo do scheduler a cada 2 s ou em evento. |
| Quando NÃO executar | Nunca desliga com o daemon ativo; no arquivo `.appfactory/STOP` só pausa despacho. |
| Paralelo | Instância única (é o coordenador); gerencia N tasks em paralelo. |
| Recursos | Parte do daemon (~50–100 MB RAM, CPU desprezível). |
| Comunicação | Dono do Job Store; publica e consome todos os eventos de ciclo de vida. |
| Registro de estado | Tabelas `jobs`, `tasks`, `attempts`, `attempts_liveness`, `leases`, `locks`, `events` (estado + evento na mesma transação) + espelho operacional `.appfactory/runtime/job.json` a cada transição. |
| Interrupção | Parada do daemon: sequência de `15-daemon.md` §9. STOP registrado (08 §9) congela todo despacho. |
| Retomada | Na partida: rotina de recuperação (`07-persistencia.md` §3) — tentativas antigas confirmadas mortas (PID + horário de criação) viram `interrupted` e voltam à fila a partir do checkpoint. |

## 4. RESOURCE MANAGER

| Campo | Definição |
| --- | --- |
| Responsabilidade | Medir CPU/RAM/GPU/VRAM/disco/energia/atividade do usuário, decidir o **modo** (FOREGROUND, BACKGROUND, BATTERY, CONTENTION, CRITICAL), fazer o **controle de admissão** (slots de agentes, processos pesados e o lease exclusivo de GPU) e pedir pausa ou descarregamento de modelos. |
| Entradas | Sondas: WMI/CIM (CPU, RAM, bateria), NVML/`nvidia-smi` (GPU e VRAM **totais**, temperatura — sem VRAM por processo no WDDM), `SHQueryUserNotificationState` (tela cheia), `GetLastInputInfo` (ociosidade), disco, runtime local (`/api/ps`) + registro de posse de modelos. Política `config/resources.yaml`. Método de cálculo: `05-resource-manager.md` §1.1. |
| Saídas | `ResourceSnapshot` (a cada 5 s), `resource.mode_changed`, respostas de admissão (`grant/deny/wait`), ordens `unload_model`, `pause_task`. |
| Ferramentas | psutil, nvidia-ml-py (fallback `nvidia-smi`), API do Ollama, ctypes (Win32). |
| Permissões | Somente leitura do sistema + descarregar **apenas modelos carregados pela fábrica** + pedir pausa a tasks. **Nunca** descarrega modelos de outras ferramentas nem altera configurações do Windows, drivers, planos de energia ou a instalação do Ollama. |
| Dependências | Nenhuma de negócio; é consultado por Job Manager e Model Router. |
| Quando executar | Sempre (serviço do daemon). |
| Quando NÃO executar | — (se uma sonda falhar, assume o pior caso daquele recurso). |
| Paralelo | Instância única. |
| Recursos | Amostragem leve (<1% CPU); `nvidia-smi` no máximo a cada 5 s. |
| Comunicação | Publica eventos `resource.*`; API síncrona `admit(request)`. |
| Registro de estado | Tabela `resource_samples` (agregada por minuto, 7 dias) + `resource_decisions` (auditoria de cada negação/preempção). |
| Interrupção | Parte do daemon. |
| Retomada | Na partida, faz 2 amostras antes de liberar qualquer admissão. |

## 5. RESEARCH AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Pesquisar documentação, APIs, versões e boas práticas; entregar resumo com **fontes (URLs) e datas de acesso**. Não executa código. |
| Entradas | `TaskSpec` com perguntas objetivas e escopo. |
| Saídas | `research/<topic>.md` com citações; itens de cache. |
| Ferramentas | Busca web (provedor configurável), HTTP fetch somente leitura, cache local. |
| Permissões | `net.fetch` para domínios permitidos; R0 no filesystem; escreve só em `.appfactory/jobs/<job>/research/` e `.appfactory/cache/research/`. |
| Dependências | Provider Router (busca), Memory, Security (allowlist de domínios). |
| Quando executar | Planner precisa de informação externa; bibliotecas/versões desconhecidas; erro sem solução local. |
| Quando NÃO executar | Informação já em cache válida (TTL 7 dias para docs); modo offline; quando o conteúdo exigiria login. |
| Paralelo | Sim (I/O-bound), até 2 instâncias. |
| Recursos | T1 para resumir; ~150 MB RAM; rede. |
| Comunicação | Padrão. |
| Registro de estado | Padrão + URLs visitadas no log. |
| Interrupção | Padrão. |
| Retomada | Pula URLs já processadas (registradas no checkpoint). |

## 6. WEB/BROWSER AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Interagir com páginas quando HTTP simples não basta: páginas dinâmicas, testes E2E dos apps gerados, capturas de tela para o UI/UX Agent. |
| Entradas | `TaskSpec` com URL(s) e objetivo; política de domínios. |
| Saídas | Texto extraído, screenshots, relatórios E2E, trace do Playwright. |
| Ferramentas | Playwright (Chromium isolado), perfil descartável por task; o app gerado sob teste roda em S1h ou S2. |
| Permissões | Navegação só em allowlist ou `localhost` do app gerado. **Proibido:** digitar credenciais reais, pagar, criar contas, aceitar termos, enviar formulários externos sem aprovação, usar o perfil do Chrome do usuário. Downloads vão para quarentena. |
| Dependências | Security, Resource Manager (processo pesado), Toolbox. |
| Quando executar | E2E e verificação visual de apps gerados; sites que exigem JavaScript. |
| Quando NÃO executar | Quando `Research` via HTTP resolve; modo BATTERY ou CRITICAL; sites fora da allowlist. |
| Paralelo | **Máximo 1 navegador ativo** (300–600 MB RAM cada). |
| Recursos | 1 slot de processo pesado; CPU moderada. |
| Comunicação | Padrão. |
| Registro de estado | Padrão + trace/screenshots em `.appfactory/jobs/<job>/artifacts/`. |
| Interrupção | Padrão; fecha o navegador e descarta o perfil. |
| Retomada | Recomeça o cenário do início (sessões de navegador não são retomáveis). |

## 7. CODER AGENTS

| Campo | Definição |
| --- | --- |
| Responsabilidade | Implementar uma task do plano: escrever/alterar código e testes unitários **dentro do seu worktree**, respeitando o `writes` declarado. |
| Entradas | `TaskSpec` (objetivo, critérios de aceite, `writes`, arquivos relevantes), `ContextPack`. |
| Saídas | Commits no branch `af/<job>/<task>`, `TaskResult` com resumo e arquivos alterados. |
| Ferramentas | Toolbox: fs (escopo do worktree), shell (lista permitida), git (commit local), execução de testes — **todo código executado vai para S1h ou S2** (08 §4). |
| Permissões | R1: escrita só no worktree (`writes` = arquivos explícitos ou `dir/**`); execução só em S1h/S2; instalar dependências = R2 com as restrições de 08 §4.3 (scripts de instalação só em S2); sem rede por padrão. |
| Dependências | Job Manager (worktree/locks), Model Router, Memory, Toolbox, QA. |
| Quando executar | Task `code.*` com dependências concluídas e lock dos arquivos obtido. |
| Quando NÃO executar | Sem lock dos arquivos; arquivo fora de `writes` (pede replanejamento); modo CRITICAL. |
| Paralelo | Sim, várias instâncias, em worktrees separados e com `writes` disjuntos; limite pelo Resource Manager. |
| Recursos | T2 local (lease de GPU) ou EXT; ~200 MB RAM por runner. Chamadas locais à GPU são **serializadas** pelo lease. |
| Comunicação | Padrão. |
| Registro de estado | Padrão + commit a cada passo significativo (checkpoint Git). |
| Interrupção | Padrão; o trabalho sem commit vai para um commit WIP `wip(af): checkpoint` no branch da task. |
| Retomada | A partir do último commit do branch + checkpoint de passo. |

## 8. DATABASE AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Modelagem de dados, migrações versionadas, seeds, consultas e índices dos apps gerados. |
| Entradas | Spec, modelo de domínio, migrações existentes. |
| Saídas | Arquivos de migração (up/down), seeds, diagrama do esquema, testes de migração. |
| Ferramentas | Toolbox db (SQLite local; Postgres/MySQL em container S2), ferramenta de migração do projeto. |
| Permissões | R1 em banco **de desenvolvimento** do worktree. Migração em banco fora de dev, `DROP`/`TRUNCATE` ou perda de dados = R3 (aprovação humana). |
| Dependências | Coder (integração), QA, Security, Docker (quando houver servidor de banco). |
| Quando executar | Tasks `db.*`; mudança de esquema. |
| Quando NÃO executar | Em paralelo com outra task que toque migrações (a pasta de migrações é *hot file*). |
| Paralelo | Não entre tasks de migração do mesmo projeto; sim com tasks de outras áreas. |
| Recursos | T1/T2; container de banco só quando necessário (≥1 GB RAM). |
| Comunicação | Padrão. |
| Registro de estado | Padrão + registro da versão do esquema por checkpoint. |
| Interrupção | Padrão; migração em curso termina ou sofre rollback transacional antes de sair. |
| Retomada | Verifica a versão do esquema aplicada antes de continuar. |

## 9. UI/UX AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Fluxos de tela, design system (tokens, componentes), acessibilidade (WCAG AA), textos de interface e revisão visual por screenshots. |
| Entradas | Spec, público-alvo, screenshots do Browser Agent. |
| Saídas | Wireframes em texto/HTML, tokens, componentes (via Coder), relatório de acessibilidade. |
| Ferramentas | Toolbox fs (worktree), Browser Agent (screenshots), linters de acessibilidade (ex.: axe via Playwright). |
| Permissões | R1 no worktree (arquivos de UI declarados em `writes`). |
| Dependências | Planner, Coder, Browser, QA. |
| Quando executar | Projetos com interface; tasks `ui.*`; revisão antes da entrega. |
| Quando NÃO executar | APIs/CLIs sem interface; modo BATTERY (revisão visual adiada). |
| Paralelo | Sim, com `writes` disjuntos. |
| Recursos | T1/T2; modelos com visão só se disponíveis (EXT ou local futuro). |
| Comunicação | Padrão. |
| Registro de estado | Padrão. |
| Interrupção | Padrão. |
| Retomada | Padrão. |

## 10. DEBUG AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Diagnosticar falhas (testes, build, runtime): reproduzir → isolar → hipótese → correção mínima → confirmar com teste. |
| Entradas | Relatório de falha do QA/Build, logs, stack traces, diff recente. |
| Saídas | Correção em branch próprio, teste de regressão, nota de causa-raiz. |
| Ferramentas | Toolbox (shell, testes, git bisect/diff), leitura de logs. |
| Permissões | R1 no worktree da task com falha; reprodução e execução em S1h/S2. |
| Dependências | QA, Build, Model Router, Memory. |
| Quando executar | Evento `qa.failed` ou `build.failed`. |
| Quando NÃO executar | Falhas de infraestrutura (disco, rede, cota) → Job Manager coloca em WAITING; falhas já com 3 tentativas → BLOCKED para humano ou tier superior. |
| Paralelo | Um por falha distinta; nunca dois na mesma falha/arquivo. |
| Recursos | Tier escalonado: T1 → T2 → EXT (se permitido) a cada tentativa. |
| Comunicação | Padrão. |
| Registro de estado | Padrão + `debug/<issue>.md` com hipóteses testadas. |
| Interrupção | Padrão. |
| Retomada | Não repete hipóteses já descartadas (registradas). |

## 11. TEST/QA AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Definir e executar a verificação: lint, tipos, testes unitários/integração/E2E, cobertura mínima e checagem dos critérios de aceite. É quem diz se uma task está **pronta**. |
| Entradas | Branch da task ou de integração, critérios de aceite, configuração de testes do projeto. |
| Saídas | `qa-report.json` (aprovado/reprovado, falhas, cobertura) e eventos `qa.passed`/`qa.failed`. |
| Ferramentas | pytest, ruff, runners JS do projeto, Playwright via Browser Agent, sandbox **S1h/S2** (testes são código não confiável). |
| Permissões | R1: executa testes no sandbox; não altera código (só arquivos de teste quando a task pedir). |
| Dependências | Job Manager, Toolbox/sandbox, Resource Manager (processo pesado), Browser. |
| Quando executar | Após cada task de código, após cada merge na integração e antes do Build. |
| Quando NÃO executar | Sem mudanças desde o último relatório aprovado (cache por hash do commit); modo CRITICAL. |
| Paralelo | Suítes independentes em paralelo, limitadas pelos slots de processo pesado (1 com usuário ativo, 2 ocioso). |
| Recursos | CPU/RAM dos testes; LLM só para analisar falhas (T1). Timeout padrão 15 min por suíte. |
| Comunicação | Padrão. |
| Registro de estado | Padrão + relatórios por commit em `.appfactory/jobs/<job>/qa/<sha>.json`. |
| Interrupção | Padrão; a suíte em execução é abortada e marcada como incompleta. |
| Retomada | Reexecuta a suíte inteira (resultados parciais não contam). |

## 12. BUILD/RELEASE AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Gerar builds reproduzíveis, empacotar artefatos, gerar notas de versão e preparar a publicação. |
| Entradas | Branch aprovado por QA e Security, configuração de build. |
| Saídas | Artefatos em `workspaces/<p>/dist/` (ignorado), `build-report.json`, rascunho de release. |
| Ferramentas | Ferramentas de build do projeto, sandbox S2 (Docker) quando houver dependências não confiáveis. |
| Permissões | R1 para build local. **R3** para tag, push, publicação, deploy ou envio de artefato para fora da máquina. |
| Dependências | QA, Security, Resource Manager, Approval Gate. |
| Quando executar | Job chegou à fase de entrega; pedido explícito de build. |
| Quando NÃO executar | QA ou Security reprovados; modo BATTERY/CRITICAL (build fica em WAITING); disco de destino com menos de 20 GB livres. |
| Paralelo | Um build por projeto; builds de projetos diferentes só com usuário ocioso. |
| Recursos | Processo pesado (CPU alta); Docker ≥1–2 GB RAM quando usado. |
| Comunicação | Padrão. |
| Registro de estado | Padrão + hash dos artefatos. |
| Interrupção | Padrão; build abortado não gera artefato (saída em diretório temporário, movido só no fim). |
| Retomada | Reinicia o build (ferramentas de build já fazem cache incremental). |

## 13. SECURITY AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Portão de segurança: busca de segredos, auditoria de dependências, análise estática, revisão de permissões pedidas por agentes e checagem de ações R2/R3 antes de irem para aprovação humana. |
| Entradas | Diffs, lockfiles, pedidos de permissão, configuração de políticas. |
| Saídas | `security-report.json` (bloqueante/aviso) e recomendações ao Approval Gate. |
| Ferramentas | gitleaks, pip-audit, npm audit, bandit (Python); regras próprias. |
| Permissões | R0 no código; executa scanners no sandbox. Não pode aprovar sozinho ações R3. |
| Dependências | Toolbox, Approval Gate, Logging (auditoria). |
| Quando executar | Antes de todo commit na integração, antes do Build/Release, ao adicionar dependência, quando um agente pede permissão R2+. |
| Quando NÃO executar | Diff somente de documentação (roda só a busca de segredos). |
| Paralelo | Sim (leve), 1 por diff. |
| Recursos | CPU baixa/média; sem GPU. |
| Comunicação | Padrão + canal síncrono com o Approval Gate. |
| Registro de estado | Padrão + log de auditoria (append-only). |
| Interrupção | Padrão; sem relatório concluído, o portão fica **fechado**. |
| Retomada | Reexecuta os scanners. |

## 14. MEDIA ENGINE

| Campo | Definição |
| --- | --- |
| Responsabilidade | Futuro: gerar imagens, áudio, vídeo e animações para os apps (ícones, sprites, trilhas, narração). Interface única com backends plugáveis. |
| Entradas | `MediaRequest` (tipo, prompt, dimensões, estilo, licença exigida). |
| Saídas | Arquivos em `workspaces/<p>/assets/generated/` + metadados (modelo, seed, licença, prompt). |
| Ferramentas | Backends: local (ex.: ComfyUI, a avaliar na sua fase), externos (via Provider Router), ferramentas determinísticas (ffmpeg, geração SVG). |
| Permissões | R1 em `assets/generated/`; backends externos seguem a política de custo (paga = aprovação). |
| Dependências | Resource Manager (GPU exclusiva), Provider Router, Security (licenças). |
| Quando executar | Tasks `media.*`, preferencialmente em modo BACKGROUND. |
| Quando NÃO executar | FOREGROUND com geração local pesada; BATTERY; CONTENTION; quando houver outro modelo na GPU. |
| Paralelo | **Não** na GPU (lease exclusivo); gerações externas podem rodar em paralelo. |
| Recursos | Geração de imagem local ocupa quase todos os 6 GB de VRAM, portanto exige descarregar os LLMs **da fábrica** (modelos de terceiros nunca são descarregados; se não houver VRAM, a geração espera). Vídeo local não é viável neste hardware além de clipes curtos em baixa resolução, então o padrão é externo. |
| Comunicação | Padrão. |
| Registro de estado | Padrão + fila própria de gerações. |
| Interrupção | Padrão; a geração em curso é descartada. |
| Retomada | Refaz a geração com a mesma seed. |

## 15. PROVIDER ROUTER

| Campo | Definição |
| --- | --- |
| Responsabilidade | Escolher o **provedor/endpoint** para cada requisição de modelo ou ferramenta externa, aplicando política de custo (zero gasto automático), privacidade, cotas e saúde; fazer failover preservando contexto. |
| Entradas | `ModelRequest` já resolvida pelo Model Router (perfil + modelos candidatos), registro de provedores, cotas/uso, status de saúde. |
| Saídas | Chamada executada, `ModelResponse`, métricas de uso, eventos `provider.exhausted`/`provider.failed`/`provider.switched`. |
| Ferramentas | Adaptadores: Ollama (nativo), OpenAI-compatível (genérico), adaptadores específicos quando necessário; httpx. |
| Permissões | Único componente que lê segredos de provedores (via Secrets Manager); agentes nunca veem chaves. |
| Dependências | Model Router, Secrets, Resource Manager (para local), Logging. |
| Quando executar | Em toda chamada a modelo ou API externa. |
| Quando NÃO executar | Sem permissão de custo/privacidade para o provedor candidato; kill switch ativo. |
| Paralelo | Sim; respeita o limite de concorrência por provedor (local = 1). |
| Recursos | Leve (dentro do daemon). |
| Comunicação | API síncrona interna; eventos `provider.*`. |
| Registro de estado | Tabelas `providers`, `provider_usage`, `provider_health`. |
| Interrupção | Requisições em voo são canceladas; o contexto está no `ContextPack`, então nada se perde. |
| Retomada | Reenvia a partir do `ContextPack`; respostas longas já recebidas ficam salvas como parciais. |

## 16. MODEL ROUTER

| Campo | Definição |
| --- | --- |
| Responsabilidade | Mapear **tipo de tarefa** para **perfil de modelo** (tier, contexto, capacidades) e escolher o modelo concreto conforme recursos e política; gerenciar o ciclo de vida dos modelos locais (carregar/manter/descarregar) junto com o Resource Manager. |
| Entradas | `task_type`, tamanho do contexto, capacidades exigidas (tools, visão, JSON), modo de recursos, catálogo `config/models.yaml`. |
| Saídas | Lista ordenada de candidatos para o Provider Router; ordens de load/unload. |
| Ferramentas | Runtime local (Ollama: `/api/ps`, `keep_alive`), catálogo e `local_allowlist` de `config/models.yaml`, registro de posse `model_loads`. |
| Permissões | Carregar **somente modelos LOCAL_VERIFICADO**; descarregar **somente modelos que a fábrica carregou** (06 §2.1). **Não** baixa modelos novos (`ollama pull` exige aprovação) nem altera a instalação do Ollama. |
| Dependências | Resource Manager (lease de GPU), Provider Router, Memory (orçamento de tokens). |
| Quando executar | Antes de toda chamada de modelo; periodicamente para descarregar modelos ociosos. |
| Quando NÃO executar | — |
| Paralelo | Sim (leve); decisões de GPU são serializadas pelo lease. |
| Recursos | Leve. |
| Comunicação | API síncrona interna; eventos `model.loaded`/`model.unloaded`/`model.swapped`. |
| Registro de estado | Tabela `model_events` + medições reais de VRAM por modelo/contexto (`model_profiles`), que calibram as estimativas. |
| Interrupção | Parte do daemon. |
| Retomada | Na partida, consulta `/api/ps` e reconcilia com o registro de posse; modelos de terceiros ficam intactos. |

## 17. MEMORY/CONTEXT SYSTEM

| Campo | Definição |
| --- | --- |
| Responsabilidade | Guardar e montar contexto: memória do projeto (arquivos de estado, decisões), memória do job (spec, plano, resumos), índice de código e memória episódica (resumos de execuções). Monta `ContextPack` dentro do orçamento de tokens do modelo escolhido. |
| Entradas | Arquivos do repositório, eventos, resultados de tasks, janela de contexto do modelo-alvo. |
| Saídas | `ContextPack` (arquivo JSON + anexos) e resumos. |
| Ferramentas | SQLite (FTS5 para busca textual), índice de símbolos (tree-sitter, fase posterior), embeddings locais opcionais (fase posterior, `sqlite-vec`). |
| Permissões | R0 em workspaces; escrita em `.appfactory/jobs/*/context/` e no banco. |
| Dependências | Model Router (tamanho da janela), Logging. |
| Quando executar | Antes de cada passo de agente; após cada task (resumo); em troca de modelo/provedor (reempacotamento). |
| Quando NÃO executar | — (é biblioteca/serviço sob demanda). |
| Paralelo | Sim (leitura); escrita serializada por job. |
| Recursos | Leve; embeddings (futuro) usam modelo T0 e só em BACKGROUND. |
| Comunicação | API interna. |
| Registro de estado | `ContextPack` versionado por passo; índices no SQLite. |
| Interrupção | Sem estado volátil relevante. |
| Retomada | Índices são reconstruíveis a partir dos arquivos. |

## 18. CHECKPOINT SYSTEM

| Campo | Definição |
| --- | --- |
| Responsabilidade | Criar e restaurar checkpoints em 3 níveis: **passo** (JSON por passo de agente), **task** (commit Git no branch da task + estado), **marco** (`CP-NNNN` do job/fase, com referência de commit). Executa rollback. |
| Entradas | Pedidos de checkpoint (agentes, Job Manager, mudança de modo), pedidos de rollback. |
| Saídas | Arquivos de checkpoint, commits, snapshot do banco (`VACUUM INTO`) nos marcos, eventos `checkpoint.*`. |
| Ferramentas | Git, SQLite backup, cópia de arquivos. |
| Permissões | Commits em branches `af/*`; rollback só via novo commit (`git revert`) ou novo branch a partir do checkpoint, **nunca** `reset --hard` em branch compartilhado sem aprovação. |
| Dependências | Job Manager, Logging, Handoff. |
| Quando executar | Fim de cada passo; fim de task; antes de ação R2/R3; antes de troca de modelo/provedor; ao pausar; em marcos de fase. |
| Quando NÃO executar | Durante escrita não atômica (espera terminar). |
| Paralelo | Sim por task; marcos serializados. |
| Recursos | Leve (checkpoints de passo < 100 KB). |
| Comunicação | API interna + eventos. |
| Registro de estado | Tabela `checkpoints` + arquivos; marcos também em `.appfactory/checkpoints/` (versionados). |
| Interrupção | Escrita atômica (arquivo temporário + rename). Interrupção no meio não corrompe o anterior. |
| Retomada | Checkpoint incompleto é descartado; vale o último completo. |

## 19. LOGGING SYSTEM

| Campo | Definição |
| --- | --- |
| Responsabilidade | Logs estruturados (JSONL) de tudo, trilha de auditoria separada e imutável para ações sensíveis, redação automática de segredos, rotação. |
| Entradas | Registros de todos os componentes. |
| Saídas | `.appfactory/logs/afd.jsonl`, `.appfactory/logs/jobs/<job>.jsonl`, `.appfactory/logs/audit.jsonl` (append-only com hash encadeado). |
| Ferramentas | `logging` da biblioteca padrão + formatador JSON próprio + filtro de redação. |
| Permissões | Somente o daemon escreve; agentes enviam logs pela API/stdout capturado. |
| Dependências | Secrets (padrões de redação). |
| Quando executar | Sempre. |
| Quando NÃO executar | — (não pode ser desligado; só o nível de detalhe muda). |
| Paralelo | Escrita serializada por arquivo (fila em memória com flush a cada 1 s ou por nível). |
| Recursos | Rotação: 20 MB × 5 arquivos por log; auditoria não é rotacionada, só arquivada. |
| Comunicação | Recebe de todos. |
| Registro de estado | É o próprio registro. |
| Interrupção | Flush ao sair; no crash perde no máximo 1 s de logs não críticos (auditoria faz flush imediato). |
| Retomada | Continua anexando. |

## 20. HANDOFF SYSTEM

| Campo | Definição |
| --- | --- |
| Responsabilidade | Produzir o "ponto de parada" **operacional**: `.appfactory/runtime/handoff/factory-status.md`, `handoff.md` de cada job e `workspaces/<p>/.appfactory/handoff.md` do projeto (07 §1). **Não** escreve os arquivos de estado versionados da fábrica (`HANDOFF.md`, `PROJECT_STATE.md`, `TASK_QUEUE.md`), que pertencem às sessões de desenvolvimento (D-0035). |
| Entradas | Estado do banco, último checkpoint, eventos recentes, pendências e bloqueios. |
| Saídas | Markdown de handoff + `handoff.json` estruturado. |
| Ferramentas | Templates, Memory (resumos). |
| Permissões | Escrita apenas em `.appfactory/runtime/handoff/`, `.appfactory/jobs/<job>/` e no `.appfactory/` do projeto (no branch de integração). |
| Dependências | Job Manager, Checkpoint, Memory. |
| Quando executar | Pausa/parada do daemon, fim de job, mudança para BLOCKED, troca de provedor, fim de sessão de IA, a cada 30 min de job ativo. |
| Quando NÃO executar | Sem mudança desde o último handoff. |
| Paralelo | Serializado (um escritor). |
| Recursos | Leve; resumo com T0/T1. |
| Comunicação | Consome eventos. |
| Registro de estado | Os próprios arquivos + versão no banco. |
| Interrupção | Escrita atômica. |
| Retomada | Regera a partir do banco. |

## 21. EVOLUTION AGENT

| Campo | Definição |
| --- | --- |
| Responsabilidade | Analisar métricas da própria fábrica (falhas, tempo, uso de recursos, custo) e **propor** melhorias como Evolution Proposals (`EP-NNNN`), implementá-las em branch isolado, testá-las contra as invariantes e compará-las com o baseline. **Nunca** faz merge sozinho. |
| Entradas | Métricas do banco, logs agregados, `evals/`, feedback do usuário. |
| Saídas | `evolution/proposals/EP-NNNN.md`, branch `evo/EP-NNNN`, relatório de comparação. |
| Ferramentas | Toolbox (worktree `evo/*` do repo da fábrica, executado em S1h/S2), suíte `tests/guardrails/` via comando fixo e protegido (08 §5.3), `evals/`. |
| Permissões | R1 somente no worktree `evo/*`. **Proibido** alterar qualquer caminho protegido (08 §5.1): diff que toque caminho protegido ⇒ **EP rejeitada automaticamente**. Merge = R3 (humano). |
| Dependências | QA, Security, Checkpoint, Approval Gate. |
| Quando executar | Sob pedido do usuário ou agendado em modo BACKGROUND, prioridade P3. |
| Quando NÃO executar | Há jobs do usuário na fila (P0–P2); FOREGROUND/BATTERY/CRITICAL; existe EP anterior não resolvida. |
| Paralelo | Não (1 proposta por vez). |
| Recursos | Mesmos do Coder, porém só com usuário ocioso. |
| Comunicação | Padrão. |
| Registro de estado | Padrão + estado da EP (`proposed → implemented → tested → compared → approved/rejected → merged/reverted`). |
| Interrupção | Padrão. |
| Retomada | Padrão; a EP guarda o estado. |
