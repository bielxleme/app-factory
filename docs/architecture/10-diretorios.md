# 10 — Estrutura de diretórios (I)

Legenda: **[V]** versionado no Git da fábrica · **[I]** ignorado · *(Fx)* criado na fase indicada. Nada de código de produção existe ainda.

```
D:\Claude\app-factory\
├── AGENTS.md  PROJECT_STATE.md  TASK_QUEUE.md  DECISIONS.md  CHANGELOG.md          [V]
├── HANDOFF.md  KNOWN_ISSUES.md  TEST_STATUS.md  RESOURCE_POLICY.md  COMMAND_LOG.md  [V]
├── README.md                                    [V] (F2)
├── pyproject.toml  uv.lock  .python-version     [V] (F2)  Python 3.13 via uv
├── .gitignore  .gitattributes                   [V]
│
├── config/                                      [V] (F2) configuração SEM segredos
│   ├── factory.yaml            portas, caminhos, workspace padrão
│   ├── resources.yaml          limites (espelho executável do RESOURCE_POLICY.md)
│   ├── models.yaml             catálogo de modelos e perfis de tarefa
│   ├── providers.yaml          provedores (secret_ref, nunca chaves)
│   ├── agents/<agente>.yaml    prompt de sistema, ferramentas, tier padrão
│   └── policies/
│       ├── permissions.yaml    capabilities por agente
│       ├── commands.yaml       allowlist/denylist de comandos
│       ├── approvals.yaml      o que é R2/R3, pré-autorizações
│       ├── network.yaml        domínios permitidos por agente
│       └── protected-paths.yaml
│
├── src/appfactory/                              [V] (F2+)
│   ├── core/          daemon.py, api.py (FastAPI), eventbus.py, config.py, ids.py, clock.py
│   ├── jobs/          manager.py, scheduler.py, state_machine.py, dag.py, leases.py, locks.py, integrator.py, recovery.py
│   ├── resources/     manager.py, policy.py, modes.py, probes/{windows.py, nvidia.py, ollama.py, linux.py}
│   ├── routing/       model_router.py, provider_router.py, budget.py, health.py,
│   │                  providers/{base.py, ollama.py, openai_compat.py, tool.py}
│   ├── agents/        base.py, runner.py, prompts/,
│   │                  master/ planner/ research/ browser/ coder/ database/ uiux/ debug/ qa/ build/ security/ evolution/
│   ├── media/         engine.py, backends/
│   ├── memory/        context_pack.py, store.py, summaries.py, index/
│   ├── checkpoints/   service.py, rollback.py, snapshot.py
│   ├── logs/          jsonlog.py, redaction.py, audit.py
│   ├── handoff/       generator.py, templates/
│   ├── security/      permissions.py, command_policy.py, approvals.py, secrets.py, paths.py, sandbox/{subprocess.py, docker.py}
│   ├── toolbox/       fs.py, shell.py, git.py, web.py, browser.py, db.py, journal.py
│   └── cli/           main.py  (comando "af")
│
├── tests/                                       [V] (F2+)
│   ├── unit/  integration/  fixtures/
│   └── guardrails/     invariantes I1–I7 (caminho protegido)
├── evals/                                       [V] (F-evo) tarefas de referência (protegido)
├── evolution/                                   [V] (F-evo)
│   ├── proposals/EP-NNNN.md
│   └── reports/EP-NNNN.md
├── docs/
│   ├── architecture/   esta especificação   [V]
│   └── runbooks/       operação (iniciar/parar/recuperar) [V] (F2+)
├── tools/diagnostics/  measure-hardware.ps1 [V] (F1) utilitários de diagnóstico (não é o Toolbox)
├── scripts/            scripts de desenvolvimento [V] (F2+)
│
├── workspaces/                                  [I] projetos gerados; cada um é um repo Git próprio
│   ├── <projeto>/      (com seu próprio .appfactory/ de estado do projeto)
│   └── _worktrees/<projeto>/<task>/
│
└── .appfactory/
    ├── job.json                    [V] espelho do job ativo
    ├── checkpoints/CP-NNNN-*.json  [V] marcos
    ├── state/factory.db            [I] SQLite (fonte da verdade)
    ├── state/snapshots/            [I] VACUUM INTO nos marcos
    ├── jobs/<job-id>/              [I] spec, plan.vN.json, context/, tasks/, responses/, qa/, research/, artifacts/, quarantine/, tmp/
    ├── logs/                       [I] afd.jsonl, jobs/<job>.jsonl, audit.jsonl
    ├── cache/                      [I] research/, índices
    ├── runtime/                    [I] pids/, hardware/ (snapshots do diagnóstico), api.token
    ├── locks/  tmp/                [I]
    └── STOP                        [I] kill switch (existe = parado)
```

Regra: o nome `tools/` na raiz é só para utilitários humanos de diagnóstico; o **Toolbox** dos agentes fica em `src/appfactory/toolbox/`.
