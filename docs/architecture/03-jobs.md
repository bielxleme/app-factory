# 03 — Sistema de jobs (B)

**Revisão 2.1 (2026-09-26):** estados `STOPPING`/`STOPPED` para o STOP explícito de job (D-0040); implementação em `src/appfactory/jobs/` (D-0041 a D-0047).

**Revisão 1.1 (2026-09-26):** 1 job RUNNING por projeto, BATTERY, leases por tempo ativo com verificação de vida, estado+evento na mesma transação (N3, N7).

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
| `QUEUED` | Aceito, aguardando início | (criação), `PAUSED`, `WAITING`, `BLOCKED`, `FAILED` (requeue manual) | `PLANNING`, `RUNNING`\*, `CANCELLED` | Ordenado por prioridade efetiva (§6). \*Direto para `RUNNING` se já tem plano aprovado. **Só sai para `PLANNING`/`RUNNING` se não houver outro job `PLANNING`/`RUNNING` no mesmo projeto** (04 §0); senão permanece com motivo `project_busy`. |
| `PLANNING` | Planner produzindo/revisando o plano | `QUEUED`, `RUNNING` (replanejar) | `RUNNING`, `BLOCKED`, `WAITING`, `PAUSED`, `FAILED`, `CANCELLED` | Só 1 plano ativo por job. Plano com R2/R3/custo → `BLOCKED(approval)`. |
| `RUNNING` | Ao menos 1 task em execução ou pronta | `PLANNING`, `QUEUED`, `PAUSED`, `WAITING`, `BLOCKED` | `PAUSED`, `WAITING`, `BLOCKED`, `FAILED`, `COMPLETED`, `CANCELLED`, `PLANNING` | Máximo 1 por projeto. Heartbeat das tasks a cada 15 s; lease de 60 s de **tempo ativo** (15 §4–5). |
| `PAUSED` | Parado de propósito, com checkpoint | `PLANNING`, `RUNNING`, `WAITING` | `QUEUED`, `RUNNING`, `CANCELLED` | Causas: usuário; STOP/CRITICAL; **BATTERY somente com bateria < 30%** (acima disso o modo BATTERY só limita admissões, 05 §3); parada do daemon. **Só sai por comando ou quando a causa acaba** (STOP só com `af resume-factory`). |
| `WAITING` | Esperando condição **automática** | `PLANNING`, `RUNNING` | `QUEUED`, `RUNNING`, `PAUSED`, `BLOCKED`, `CANCELLED` | Motivos tipados: `resources`, `provider_quota`, `network`, `dependency`, `lock`, `schedule`, `disk`. Tem `retry_at` ou condição observável. Após 24 h em `WAITING` → `BLOCKED(stale)`. |
| `BLOCKED` | Precisa de **ação humana** | qualquer não terminal | `QUEUED`, `RUNNING`, `PLANNING`, `CANCELLED` | Motivos: `approval`, `credentials`, `needs_human` (debug esgotado), `conflict`, `policy_violation`, `stale`. Master notifica o usuário. Nada de gastar recursos. |
| `FAILED` | Terminou sem sucesso | `PLANNING`, `RUNNING` | `QUEUED` (requeue manual), — | Falha não recuperável automaticamente (ex.: plano impossível, 3 replanejamentos). Artefatos e branches mantidos. |
| `STOPPING` | STOP do job pedido; o executor termina o passo atual, grava checkpoint `stop` e limpa temporários (D-0040) | `RUNNING`, `PLANNING` | `STOPPED`, `CANCELLED` | Ocupa a vaga do projeto. Sem executor vivo → `STOPPED` direto (na hora ou em `af recover`). Falha durante a parada → `STOPPED` com evento `job.stop_degraded` (D-0046). |
| `STOPPED` | Parado de forma controlada, com o último checkpoint válido preservado | `STOPPING`, `QUEUED`, `PAUSED`, `WAITING`, `BLOCKED` | `QUEUED` (`af job resume`), `CANCELLED` | **Não** é retomado automaticamente, nem após reinício. Diferente do STOP da fábrica, que leva a `PAUSED(factory_stop)`. |
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
| Relógio | tempo ativo do sistema (exclui suspensão); carência de 120 s após retorno do sono (15 §6) |
| Lease vencido | **verificação de vida** primeiro (PID + horário de criação + Job Object, 15 §5); só então tentativa `interrupted` e task em `QUEUED` com `resume_from=<último checkpoint>` |
| Duplicidade | proibida: nova tentativa só depois de confirmado que o Job Object da anterior está vazio |
| Passo não idempotente em andamento no journal | task → `BLOCKED(needs_human)` com o detalhe do passo (não repete efeitos colaterais às cegas) |

## 5. Transições registradas

Toda transição grava: `job_id`, `task_id`, `from`, `to`, `reason`, `actor` (user/system/agent), `timestamp`, `checkpoint_id`, **na mesma transação** que o evento em `events` (append-only). Espelho legível do job ativo: **`.appfactory/runtime/job.json`** (operacional, ignorado pelo Git; 07 §1.2). Só o daemon grava no SQLite (D-0037).

## 6. Prioridade efetiva

`prioridade_efetiva = base (P0=0, P1=1, P2=2, P3=3) − envelhecimento`, com **envelhecimento de 1 nível a cada 30 min** em fila, limitado a P1 (só o usuário cria P0). Empate: mais antigo primeiro. P0 pode preemptar P2/P3 **somente em fronteira de passo** (cooperativo).

## 7. Esquema mínimo (SQLite)

```sql
jobs(id TEXT PK, title, state, state_reason, priority, created_at, updated_at, plan_version, project, budget_json, owner)
attempts_liveness(attempt_id PK, pid, process_create_time, job_object_name, last_heartbeat_active_ms)
factory_stop(id INTEGER PK CHECK (id = 1), active, reason, set_at, set_by)
model_loads(model, digest, loaded_at, loaded_by_factory, last_call_at, expected_expires_at)
tasks(id TEXT PK, job_id FK, type, state, state_reason, deps_json, writes_json, model_tier, attempts, max_attempts, created_at, updated_at)
attempts(id PK, task_id FK, runner_pid, provider, model, started_at, ended_at, outcome, resume_from)
leases(task_id PK, holder, expires_at)
locks(project, path_spec, task_id, acquired_at, PRIMARY KEY(project, path_spec, task_id))   -- path_spec: arquivo explícito ou 'dir/**'
events(seq INTEGER PK AUTOINCREMENT, ts, type, job_id, task_id, actor, payload_json)   -- append-only
checkpoints(id PK, level, job_id, task_id, git_ref, file_path, created_at)
approvals(id PK, job_id, task_id, risk, action_json, state, requested_at, decided_at, decided_by, expires_at)
```

## 8. Implementação da Fase 2.1 (D-0041 a D-0047)

- Tipos de job **registrados no código** (hoje só `demo.steps`) têm plano implícito aprovado: `QUEUED → RUNNING` direto (§2, nota \*). `PLANNING` só será usado quando houver Planner.
- Enquanto não há tasks, a unidade executada é o próprio job: `RUNNING` sem tentativa aberta = "pronto para retomar" (§2: "ao menos 1 task em execução **ou pronta**").
- Posse por tentativa (`attempts`) com lease em tempo ativo e **fencing**: escrita de tentativa que perdeu a posse → `LeaseLost`.
- `failed_attempts ≥ max_attempts (3)` → `BLOCKED(needs_human)`; falha fatal ou validação reprovada → `FAILED`; `interrupted_attempts > 5` → `BLOCKED(needs_human)` (laço de queda).
- Tabelas extras do schema v1: `validations`, `step_journal`, `id_counters`, `schema_meta`; `events` e `checkpoints` protegidos por triggers (append-only / imutáveis).
