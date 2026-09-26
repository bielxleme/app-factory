# 07 — Persistência (F)

**Revisão 1.1 (2026-09-26):** separação entre estado versionado e estado operacional (N6, D-0035, revisa D-0005); recuperação alinhada com o ciclo de vida do daemon (N3, `15-daemon.md`); SQLite com escritor único (N7, D-0037). Diagrama: `13-diagramas.md` §6.

## 1. Dois tipos de estado

### 1.1 Estado VERSIONADO (Git da fábrica) — desenvolvimento da própria fábrica

| Dado | Onde | Quem escreve | Quando |
| --- | --- | --- | --- |
| Estado e plano da fábrica | `PROJECT_STATE.md`, `HANDOFF.md`, `TASK_QUEUE.md` | sessões de desenvolvimento dirigidas pelo usuário (humano ou IA sob `AGENTS.md`) | ao fim de cada sessão/fase |
| Decisões e histórico | `DECISIONS.md`, `CHANGELOG.md`, `KNOWN_ISSUES.md`, `TEST_STATUS.md`, `COMMAND_LOG.md` | idem | a cada mudança |
| Normas | `AGENTS.md`, `RESOURCE_POLICY.md`, `docs/architecture/**` | idem | a cada revisão registrada |
| Resumo de marco | `.appfactory/job.json` | idem | **somente em marcos** (fim de fase/revisão) |
| Checkpoints de marco | `.appfactory/checkpoints/CP-NNNN-*.json` | idem | em marcos |
| Configuração sem segredos | `config/` | idem (protegido, 08 §5) | a cada revisão |

Esses arquivos são **protegidos** contra os agentes em execução (08 §5). O daemon **não** os reescreve.

### 1.2 Estado OPERACIONAL (ignorado pelo Git) — execução de jobs

| Dado | Onde |
| --- | --- |
| Fonte da verdade: jobs, tasks, tentativas, eventos, locks, leases, aprovações, STOP, uso de provedores, posse de modelos | `.appfactory/state/factory.db` (SQLite WAL; **só o daemon abre para escrita**) |
| Espelho legível do job ativo | **`.appfactory/runtime/job.json`** (reescrito a cada transição) |
| Status/handoff operacional da fábrica | `.appfactory/runtime/handoff/factory-status.md` (gerado pelo Handoff System) |
| Trava de instância, PIDs, tokens | `.appfactory/runtime/afd.lock`, `runtime/pids/`, `runtime/tokens/` |
| Snapshots de hardware | `.appfactory/runtime/hardware/` |
| Plano, spec, ContextPacks, respostas parciais, checkpoints de passo | `.appfactory/jobs/<job>/` |
| Logs e auditoria | `.appfactory/logs/` |
| Snapshots do banco | `.appfactory/state/snapshots/` |

### 1.3 Estado dos projetos gerados

| Dado | Onde |
| --- | --- |
| Código | `workspaces/<p>/` (repositório Git **do projeto**) + worktrees em `workspaces/_worktrees/<p>/` |
| Handoff do projeto | `workspaces/<p>/.appfactory/handoff.md` e `project_state.md`, **versionados no repo do projeto** e atualizados pelo Handoff System no branch de integração do job (entram no projeto junto com o merge aprovado) |

### 1.4 Segredos

Windows Credential Manager do usuário principal (via `keyring`). **Nunca** em arquivos do repositório.

## 2. Sobrevivência por tipo de evento

| Evento | O que sobrevive | Como o sistema reage |
| --- | --- | --- |
| Fechamento da interface (CLI/UI) | Tudo: o daemon independe da interface | Jobs continuam; ao reabrir, a UI consulta a API |
| Reinicialização do computador | Banco, arquivos, commits, checkpoints | O daemon sobe no logon (15 §3) e executa a recuperação (§3) |
| Suspensão/hibernação | Tudo (processos congelados) | Carência de 120 s na volta (15 §6); leases usam tempo ativo |
| Troca de IA (desenvolvimento da fábrica) | Estado versionado (§1.1) | A nova IA segue `AGENTS.md` → lê `HANDOFF.md` → continua |
| Troca de provedor | ContextPack, transcrições, parciais | Reenvio a partir do pack (06 §6) |
| Interrupção manual (pause/stop/Ctrl+C) | Checkpoint de passo gravado na saída cooperativa | Job `PAUSED`; `af resume` continua |
| Falha de agente (crash, OOM, limite do Job Object) | Último checkpoint de passo, commits, journal | Verificação de vida (15 §5) → tentativa `interrupted` → nova tentativa |
| Falha de rede | Tudo local | `WAITING(network)`; sonda a cada 60 s; tasks locais continuam |
| Queda de energia no meio de escrita | SQLite WAL + `synchronous=FULL` nas transições; arquivos com temp + rename | Registro parcial descartado; vale o último completo |
| Crash do daemon | Banco + arquivos | O Job Object raiz mata todos os runners/sandboxes (15 §7); na próxima partida, recuperação (§3) |
| STOP registrado | Tabela `factory_stop` | Recarregado antes de qualquer despacho (08 §9) |

## 3. Rotina de recuperação (partida do daemon)

1. Obter o mutex de instância única (15 §1); sem ele, sair.
2. Verificar o banco (`PRAGMA quick_check`). Falha → **preservar** o arquivo corrompido (`factory.db.corrupt-<data>`), restaurar o último snapshot e entrar em `BLOCKED(needs_human)` global.
3. Carregar o estado de STOP (08 §9). Se ativo: não despachar nada.
4. Encerrar sobras: processos listados em `runtime/pids/` só se PID + horário de criação + usuário coincidirem; containers com rótulo `appfactory.task` sem task viva.
5. Para cada task `RUNNING`: como o Job Object raiz anterior morreu com o daemon, nenhuma tentativa antiga está viva (confirmar pelo PID/horário de criação). Fechar a tentativa como `interrupted` e olhar o journal:
   - último passo concluído → task `QUEUED` com `resume_from`;
   - passo com efeito colateral **sem resultado** → verificar o estado real; se não der para saber → `BLOCKED(needs_human)`.
6. Liberar locks cujas tasks não estão vivas; reconciliar worktrees (incluindo `_integration-<job>`) com o banco.
7. Reconciliar modelos: consultar `/api/ps`; **descarregar somente modelos com posse da fábrica** e sem uso por terceiros (06 §2.1); modelos de terceiros ficam intactos.
8. Duas amostras do Resource Manager antes de admitir qualquer task.
9. Gerar `runtime/handoff/factory-status.md` ("recuperado após reinício").

## 4. Journal de ferramentas (idempotência)

Cada ação com efeito colateral grava `intent` (com `idempotency_key`) **antes** e `result` **depois**. Na retomada: `intent` sem `result` → verificar o estado real (ex.: o commit existe?) → se não der para saber → `BLOCKED(needs_human)`.

## 5. Estado e eventos na mesma transação

Toda transição de estado é gravada **na mesma transação SQLite** que o seu evento (`events`). O Event Bus em memória só publica **depois** do commit; consumidores são idempotentes pelo `seq`. Assim, após qualquer crash, estado e eventos nunca divergem.

## 6. Retenção

Eventos: 180 dias · amostras de recurso agregadas: 7 dias · logs: rotação 20 MB × 5 · jobs concluídos: artefatos por 30 dias (resumo e handoff para sempre) · worktrees de jobs cancelados: 7 dias · snapshots do banco: nos marcos + 1 por dia de uso (últimos 7).
