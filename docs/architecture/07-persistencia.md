# 07 — Persistência (F)

Diagrama: `13-diagramas.md` §6.

## 1. O que é durável

| Dado | Onde | Formato | Versionado no Git da fábrica? |
| --- | --- | --- | --- |
| Jobs, tasks, tentativas, eventos, locks, leases, aprovações, uso de provedores | `.appfactory/state/factory.db` | SQLite WAL | Não (snapshot nos marcos em `.appfactory/state/snapshots/`, também ignorado) |
| Plano, spec, ContextPacks, respostas parciais, checkpoints de passo | `.appfactory/jobs/<job>/` | JSON/Markdown | Não |
| Código dos projetos | `workspaces/<p>/` (repo próprio) + worktrees | Git | No repo do projeto |
| Checkpoints de marco da fábrica | `.appfactory/checkpoints/CP-NNNN-*.json` | JSON | **Sim** |
| Estado resumido | `.appfactory/job.json`, `PROJECT_STATE.md`, `HANDOFF.md`, `TASK_QUEUE.md` | JSON/MD | **Sim** |
| Decisões/histórico | `DECISIONS.md`, `CHANGELOG.md`, `KNOWN_ISSUES.md`, `TEST_STATUS.md`, `COMMAND_LOG.md` | MD | **Sim** |
| Logs | `.appfactory/logs/` | JSONL | Não |
| Configuração (sem segredos) | `config/` | YAML | **Sim** |
| Segredos | Windows Credential Manager (via `keyring`) | — | **Nunca** |

## 2. Sobrevivência por tipo de evento

| Evento | O que sobrevive | Como o sistema reage |
| --- | --- | --- |
| Fechamento da interface (CLI/UI) | Tudo: o daemon é independente da interface | Jobs continuam; ao reabrir, a UI relê o estado |
| Reinicialização do computador | Banco, arquivos, commits, checkpoints | Na partida do daemon: recuperação (§3); jobs `RUNNING` voltam do último checkpoint |
| Troca de IA (outra ferramenta/assistente) | Arquivos de estado + `HANDOFF.md` + checkpoints + banco | A nova IA segue `AGENTS.md` → lê o handoff → continua |
| Troca de provedor | ContextPack, transcrições, parciais | Reenvio a partir do pack (ver `06` §6) |
| Interrupção manual (pause/stop/Ctrl+C) | Checkpoint de passo gravado na saída cooperativa | Job `PAUSED`; `af resume` continua |
| Falha de agente (crash, OOM) | Último checkpoint de passo, commits, journal | Lease vence → tentativa `interrupted` → nova tentativa |
| Falha de rede | Tudo local | `WAITING(network)`; sonda a cada 60 s; tasks locais continuam |
| Queda de energia no meio de escrita | SQLite WAL (atômico); arquivos gravados com temp + rename | Registro parcial é descartado; vale o último completo |
| Crash do daemon | Banco + arquivos | Na partida: recuperação (§3); runners órfãos são encerrados pelo PID gravado |

## 3. Rotina de recuperação (partida do daemon)

1. Verificar a integridade do banco (`PRAGMA quick_check`); se houver falha → restaurar o último snapshot de marco e entrar em modo `BLOCKED(needs_human)`.
2. Encerrar processos órfãos da fábrica (PIDs em `.appfactory/runtime/pids/`, validando nome e horário de criação).
3. Para cada task `RUNNING` com lease vencido: fechar a tentativa como `interrupted`; olhar o journal:
   - último passo concluído → task `QUEUED` com `resume_from`;
   - passo com efeito colateral **sem resultado registrado** → `BLOCKED(needs_human)` (não repetir às cegas).
4. Remover locks órfãos; reconciliar worktrees com o banco.
5. Reconciliar modelos carregados (`/api/ps`); descarregar os que não estão em uso.
6. Duas amostras do Resource Manager antes de admitir qualquer task.
7. Gerar handoff "recuperado após reinício".

## 4. Journal de ferramentas (idempotência)

Cada ação com efeito colateral grava `intent` (com `idempotency_key`) **antes** e `result` **depois**. Na retomada: `intent` sem `result` → verificar o estado real (ex.: o commit existe?) → se não der para saber → `BLOCKED(needs_human)`.

## 5. Retenção

Eventos: 180 dias · amostras de recurso agregadas: 7 dias · logs: rotação 20 MB × 5 · jobs concluídos: artefatos por 30 dias (resumo e handoff para sempre) · worktrees de jobs cancelados: 7 dias.
