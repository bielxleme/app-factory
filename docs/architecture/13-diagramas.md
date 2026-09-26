# 13 — Diagramas (K)

## 1. Visão geral

```
                              +------------------+
                              |     USUARIO      |
                              +--------+---------+
                                       | CLI "af" / UI (futura)
                                       v
+--------------------------------------------------------------------------------------+
|  afd - App Factory Daemon (Windows, 1 processo, BELOW_NORMAL)                        |
|                                                                                      |
|  +-------------+   +--------------+   +-----------------+   +--------------------+   |
|  | API local   |-->| Master Agent |-->|   Job Manager   |<->|  Resource Manager  |   |
|  | 127.0.0.1   |   | (via runner) |   | fila/DAG/leases |   | modos/admissao/GPU |   |
|  +-------------+   +--------------+   +--------+--------+   +---------+----------+   |
|                                                |                      |              |
|  +----------------+  +----------------+        |             +--------v---------+    |
|  | Approval Gate  |  | Security (pol.)|        |             |   Model Router   |    |
|  +----------------+  +----------------+        |             +--------+---------+    |
|  +----------------+  +----------------+        |             +--------v---------+    |
|  | Checkpoint Svc |  | Logging/Audit  |        |             | Provider Router  |    |
|  +----------------+  +----------------+        |             +--+------------+--+    |
|  +----------------+  +----------------+        |                |            |       |
|  | Handoff Svc    |  | Memory/Context |        |                |            |       |
|  +----------------+  +----------------+        |                |            |       |
|        Event Bus  <====================================>  SQLite factory.db (WAL)    |
+------------------------------------------------+----------------+------------+-------+
                                                 | spawn          |            |
                     +---------------------------v---+     +------v-----+  +---v------------+
                     | agent-runner (1 por task)      |     |  Ollama    |  | Provedores     |
                     | Planner Research Browser Coder |     | (GPU 6 GB) |  | externos       |
                     | DB UI/UX Debug QA Build Sec    |     | 1 modelo   |  | (desligados    |
                     | Media Evolution                |     | por vez    |  |  por padrao)   |
                     +---------------+----------------+     +------------+  +----------------+
                                     | Toolbox (fs/shell/git/web/browser/db) + politica
                                     v
                     +--------------------------------+     +-----------------------------+
                     | workspaces/<projeto> (git)     |     | Sandbox S1 subprocess       |
                     | _worktrees/<projeto>/<task>    |     | Sandbox S2 Docker (demanda) |
                     +--------------------------------+     +-----------------------------+
```

## 2. Fluxo de jobs (máquina de estados)

```
                 +-----------+
   (criacao) --> |  QUEUED   |<---------------------------------------------+
                 +-----+-----+                                              |
                       | admitido                                           | resume / requeue
                       v                                                    |
                 +-----------+  plano c/ R2/R3/custo   +-----------+        |
                 | PLANNING  |------------------------>|  BLOCKED  |--------+
                 +-----+-----+                          +-----------+  (acao humana)
                       | plano aprovado                     ^   ^
                       v                                    |   | credenciais / conflito /
                 +-----------+  falha 3x / conflito ---------+   | debug esgotado / stale
          +----->|  RUNNING  |---------------------------------+  |
          |      +--+--+--+--+                                    |
          |         |  |  | cond. automatica (recurso, cota,      |
          |         |  |  | rede, lock, dependencia, disco)       |
          |         |  |  v                                       |
          |         |  | +-----------+  > 24 h ------------------+
          +---------|--|-|  WAITING  |
          | condicao|  | +-----------+
          | resolvida  |
          |         |  | usuario / CRITICAL / BATTERY / parada do daemon
          |         |  v
          |         | +-----------+
          +---------|-|  PAUSED   |  (sempre com checkpoint)
            resume  | +-----------+
                    |
        +-----------+-------------+-------------------+
        v                         v                   v
  +-----------+             +-----------+       +-----------+
  | COMPLETED |             |  FAILED   |       | CANCELLED |   <- de qualquer estado nao terminal
  +-----------+             +-----------+       +-----------+      (comando do usuario)
  QA+Security ok,           requeue manual -> QUEUED
  handoff, [H] p/ R3
```

## 3. Comunicação entre agentes (blackboard + eventos)

```
  +---------+   JobRequest   +---------+  plan.json   +-------------+
  | Master  |--------------->| Planner |------------->| Job Manager |
  +----^----+                +---------+              +------+------+
       | approval.requested /                               | TaskSpec + ContextPack
       | job.state_changed                                  v
       |                          +-------------------------------------------------+
       |                          | agent-runners (sem falar entre si diretamente)  |
       |                          |  Research  Coder  DB  UI/UX  Browser  Media     |
       |                          +-----+-------------------------------------+-----+
       |                                | TaskResult / eventos                | /llm /tools
       |                                v                                     v
  +----+-----------------------------------------------------+        +---------------+
  |  EVENT BUS  +  JOB STORE (SQLite)  = "quadro-negro"       |<------>| Routers,      |
  +----+--------------+-------------+--------------+----------+        | Toolbox,      |
       |              |             |              |                   | Approval Gate |
       v              v             v              v                   +---------------+
   +------+      +-------+     +--------+     +----------+
   |  QA  |----->| Debug |     |Security|---->|  Build   |
   +------+ fail +-------+     +--------+ ok  +----------+
      ^  pass       | fix (novo commit)             |
      +-------------+                               v
                                            Handoff / Entrega
```

## 4. Resource Manager

```
 Sondas (5 s)                          Decisao                          Atuacao
 +---------------------+     +----------------------------+     +-----------------------------+
 | psutil: CPU/RAM/bat |---->| 1. CRITICAL?  RAM<1,5 GB,  |     | admit(agent|heavy|gpu)      |
 | NVML: GPU/VRAM/temp |---->|    GPU>=87C, D:<5GB, STOP  |---->|   GRANT / DENY / WAIT       |
 | GetLastInputInfo    |---->| 2. BATTERY? sem tomada     |     | gpu lease (1 por vez)       |
 | Ollama /api/ps      |---->| 3. CONTENTION? GPU alheia  |     | unload modelos (keep_alive=0)|
 | disco C:/D:         |---->|    >20% ou VRAM>1,5 GB     |     | pausa cooperativa de tasks  |
 +---------------------+     | 4. BACKGROUND? ocioso>=10m |     | eventos resource.*          |
                             | 5. FOREGROUND (padrao)     |     +-----------------------------+
                             | + limiares de pressao      |
                             | + histerese (2 leituras)   |
                             +----------------------------+
  Limites por modo:    FG: 2 agentes, T0/T1, 1 pesado | BG: 4, ate T2, 2 pesados
                       BAT: 1, sem GPU, 0 pesados      | CONT: 2, sem GPU | CRIT: 0 novos
```

## 5. Provider / Model Router

```
 task_type + contexto + capacidades
            |
            v
 +---------------------+   perfil (tier, ctx)   +-------------------------------+
 |    MODEL ROUTER     |----------------------->| candidatos ordenados          |
 | catalogo models.yaml|<-- modo de recursos ---| ex.: qwen3.5:4b, qwen3-coder, |
 +---------------------+                        |      qwen3:8b, EXT            |
                                                +---------------+---------------+
                                                                |
                                                                v
 +---------------------------------------------------------------------------------+
 | PROVIDER ROUTER                                                                 |
 |  filtro: capacidade | enabled | privacidade | CUSTO (pago=0 sem [H]) | saude    |
 |          | admissao GPU (local)                                                 |
 |  pontua: tier .40 + custo .25 + latencia .15 + cota .10 + carga local .10       |
 +------+--------------------------+-----------------------------+-----------------+
        |                          |                             |
        v                          v                             v
  +------------+           +---------------+             +-----------------+
  |ollama-local|           | ollama-cloud  |             | externo pago    |
  | GPU lease  |           | (EXT, off)    |             | (off, orcam. 0) |
  +-----+------+           +-------+-------+             +--------+--------+
        |   erro?                  |                              |
        v                          v                              v
  transitorio -> retry 3x | cota -> exhausted -> proximo candidato PERMITIDO
  auth -> BLOCKED(credentials) | nenhum candidato -> WAITING(provider_quota, retry_at)
  [CP antes de trocar] [ContextPack reaproveitado] [evento provider.switched]
```

## 6. Checkpoint / Handoff

```
  passo N do agente                task concluida              marco (fase/entrega)
  +------------------+             +------------------+        +--------------------------+
  | step-NNN.json    |             | commit no branch |        | CP-NNNN.json  [Git]      |
  | journal intent/  |             | af/<job>/<task>  |        | commit de referencia     |
  | result           |             | + estado no DB   |        | snapshot DB (VACUUM INTO)|
  +--------+---------+             +--------+---------+        +------------+-------------+
           |                                |                               |
           +---------------+----------------+---------------+---------------+
                           v                                v
                 +--------------------+           +------------------------------+
                 | tabela checkpoints |           | HANDOFF SYSTEM               |
                 +---------+----------+           | gatilhos: pausa, BLOCKED,    |
                           |                      | fim de job, troca de provedor|
             retomada      |                      | fim de sessao, a cada 30 min |
   crash/reboot -> recovery: lease vencido ->     +--------------+---------------+
   ultimo checkpoint completo -> QUEUED(resume)                  v
                                                  HANDOFF.md / PROJECT_STATE.md /
                                                  TASK_QUEUE.md / jobs/<job>/handoff.md
                                                  -> outra IA continua via AGENTS.md
```

## 7. Execução paralela

```
 main -----o-----------------------------------------------------------o--> (merge so com [H])
            \                                                         /
 af/J/integration o-----------o(merge T1)----o(merge T2)----o(merge T3)
                   \           ^   QA int.     ^   QA int.     ^
                    \          |               |               |
 af/J/T1 (worktree)  o--o--o---+  writes: src/api/**           |
 af/J/T2 (worktree)  o--o------------o---------+  writes: src/ui/**
 af/J/T3 (worktree)       (espera lock de "package.json" / hot file) o--o--+

 Locks:   T1 {src/api/**}   T2 {src/ui/**}   T3 {package.json, uv.lock}  -> disjuntos ok
 GPU:     [T1 call]..[T2 call]..[T1 call]..   (1 lease; chamadas intercaladas)
 Slots:   FOREGROUND = 2 runners  -> T3 espera slot ou lock
 Conflito no merge -> Coder resolvedor (1x) -> senao BLOCKED(conflict)
```

## 8. Fluxo de segurança

```
 agente pede acao ----> Toolbox
                          |
                          v
                 +-----------------+  nao   +--------------------------+
                 | capability ok?  |------->| NEGA + security.violation|
                 | (permissions)   |        +--------------------------+
                 +--------+--------+
                          | sim
                          v
                 +-----------------+  proibida   +--------------------------+
                 | classificar     |------------>| devolve ao usuario       |
                 | risco R0..R3    |             +--------------------------+
                 +--+-----+----+---+
               R0/R1|     |R2  |R3
                    |     |    +--------------------------+
                    |     v                               v
                    |  +-----------------+  nega   +----------------------+
                    |  | Security Agent  |-------->| BLOCKED / replanejar |
                    |  | + pre-autoriz.  |         +----------------------+
                    |  +--+----------+---+
                    |     | ok       | exige humano
                    |     |          v
                    |     |   +----------------+ nega/expira
                    |     |   | Approval Gate  |------------> BLOCKED(approval)
                    |     |   | [H] por acao   |
                    |     |   +-------+--------+
                    |     |           | aprova
                    v     v           v
              +------------------------------+
              | journal intent -> [CP] ->    |
              | executa em sandbox S0/S1/S2  |
              | env limpo, segredos so no    |
              | Provider Router, timeout     |
              +--------------+---------------+
                             v
              journal result -> audit.jsonl (hash encadeado) -> logs com redacao
              falha/efeito indesejado -> ROLLBACK (revert / branch do checkpoint)
```
