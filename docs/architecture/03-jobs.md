# 03 — Sistema de jobs (B)

## 1. Hierarquia

```
Job (pedido do usuário)
 `- Plan (versões v1, v2, ...)
     `- Task (nó do DAG; tipo: research | code | db | ui | qa | debug | build | security | media | evolution)
         `- Attempt (execução concreta por um agent-runner; 1..N)
             `- Step (passo com checkpoint)
```

## 2. Estados do JOB

| Estado | Significado | Entradas permitidas | Saídas permitidas | Regras |
| --- | --- | --- | --- | --- |
| `QUEUED` | Aceito, aguardando início | (criação), `PAUSED`, `WAITING`, `BLOCKED`, `FAILED` (requeue manual) | `PLANNING`, `RUNNING`\*, `CANCELLED` | Ordenado por prioridade efetiva (§6). \*Direto para `RUNNING` se já tem plano aprovado. |
| `PLANNING` | Planner produzindo/revisando o plano | `QUEUED`, `RUNNING` (replanejar) | `RUNNING`, `BLOCKED`, `WAITING`, `PAUSED`, `FAILED`, `CANCELLED` | Só 1 plano ativo por job. Plano com R2/R3/custo → `BLOCKED(approval)`. |
| `RUNNING` | Ao menos 1 task em execução ou pronta | `PLANNING`, `QUEUED`, `PAUSED`, `WAITING`, `BLOCKED` | `PAUSED`, `WAITING`, `BLOCKED`, `FAILED`, `COMPLETED`, `CANCELLED`, `PLANNING` | Heartbeat das tasks a cada 15 s; lease de 60 s. |
| `PAUSED` | Parado de propósito, com checkpoint | `PLANNING`, `RUNNING`, `WAITING` | `QUEUED`, `RUNNING`, `CANCELLED` | Causas: usuário, preempção pelo Resource Manager (modos CRITICAL/BATTERY), parada do daemon. **Só sai por comando ou quando a causa de preempção acaba.** |
| `WAITING` | Esperando condição **automática** | `PLANNING`, `RUNNING` | `QUEUED`, `RUNNING`, `PAUSED`, `BLOCKED`, `CANCELLED` | Motivos tipados: `resources`, `provider_quota`, `network`, `dependency`, `lock`, `schedule`, `disk`. Tem `retry_at` ou condição observável. Após 24 h em `WAITING` → `BLOCKED(stale)`. |
| `BLOCKED` | Precisa de **ação humana** | qualquer não terminal | `QUEUED`, `RUNNING`, `PLANNING`, `CANCELLED` | Motivos: `approval`, `credentials`, `needs_human` (debug esgotado), `conflict`, `policy_violation`, `stale`. Master notifica o usuário. Nada de gastar recursos. |
| `FAILED` | Terminou sem sucesso | `PLANNING`, `RUNNING` | `QUEUED` (requeue manual), — | Falha não recuperável automaticamente (ex.: plano impossível, 3 replanejamentos). Artefatos e branches mantidos. |
| `COMPLETED` | Entregue e verificado | `RUNNING` | — (terminal) | Exige QA + Security aprovados, handoff gerado e [H] para ações R3 de entrega. |
| `CANCELLED` | Cancelado | qualquer não terminal | — (terminal) | Só por comando do usuário (ou política, com registro). Runners param cooperativamente; worktrees preservados por 7 dias. |

Diagrama: `13-diagramas.md` §2.

## 3. Estados da TASK

Mesmos nomes, com regras locais:

- `QUEUED` → pronta quando todas as dependências estão `COMPLETED`.
- `RUNNING` exige: admissão do Resource Manager + lock dos `writes` + worktree criado.
- `WAITING(lock)` quando outro task detém o lock.
- `FAILED` em uma task **não** falha o job automaticamente: o Job Manager aciona Debug ou replanejamento. Só falha o job após 3 replanejamentos ou quando a task é marcada `critical` sem alternativa.
- Tentativas: máximo 3 por task, depois 1 escalonamento de tier, depois `BLOCKED(needs_human)`.

## 4. Leases, heartbeat e recuperação

| Parâmetro | Valor |
| --- | --- |
| Heartbeat do runner | a cada 15 s |
| Duração do lease | 60 s |
| Lease vencido | tentativa marcada `interrupted`; task volta para `QUEUED` com `resume_from=<último checkpoint>` |
| Passo não idempotente em andamento no journal | task → `BLOCKED(needs_human)` com o detalhe do passo (não repete efeitos colaterais às cegas) |

## 5. Transições registradas

Toda transição grava: `job_id`, `task_id`, `from`, `to`, `reason`, `actor` (user/system/agent), `timestamp`, `checkpoint_id`. Tabela `events` append-only + espelho em `.appfactory/job.json` (job ativo mais recente).

## 6. Prioridade efetiva

`prioridade_efetiva = base (P0=0, P1=1, P2=2, P3=3) − envelhecimento`, com **envelhecimento de 1 nível a cada 30 min** em fila, limitado a P1 (só o usuário cria P0). Empate: mais antigo primeiro. P0 pode preemptar P2/P3 **somente em fronteira de passo** (cooperativo).

## 7. Esquema mínimo (SQLite)

```sql
jobs(id TEXT PK, title, state, state_reason, priority, created_at, updated_at, plan_version, project, budget_json, owner)
tasks(id TEXT PK, job_id FK, type, state, state_reason, deps_json, writes_json, model_tier, attempts, max_attempts, created_at, updated_at)
attempts(id PK, task_id FK, runner_pid, provider, model, started_at, ended_at, outcome, resume_from)
leases(task_id PK, holder, expires_at)
locks(path_glob, task_id, acquired_at, PRIMARY KEY(path_glob, task_id))
events(seq INTEGER PK AUTOINCREMENT, ts, type, job_id, task_id, actor, payload_json)   -- append-only
checkpoints(id PK, level, job_id, task_id, git_ref, file_path, created_at)
approvals(id PK, job_id, task_id, risk, action_json, state, requested_at, decided_at, decided_by, expires_at)
```
