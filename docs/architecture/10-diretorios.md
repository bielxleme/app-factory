# 10 — Estrutura de diretórios (I)

Legenda: **[V]** versionado no Git da fábrica · **[I]** ignorado · **[P]** caminho protegido (08 §5.1) · *(Fx)* criado na fase indicada. Nada de código de produção existe ainda.

**Fase 2.1 (2026-09-26):** existem `pyproject.toml`, `pytest.ini`, `.python-version`, `src/appfactory/{core,jobs,checkpoints,logs,cli}/`, `tests/{unit,integration}/`, `docs/runbooks/job-manager.md`. O restante da árvore continua planejado.

**Revisão 2.2 (2026-09-27, documentação; nada implementado):** `config/**` inteiro protegido (D-0052) e escrito no subconjunto JSON (D-0049); núcleo do Job Manager, relógio/vida e CLI protegidos (D-0051); Toolbox mínimo (`fs.py`, `shell.py`) previsto para a fatia 2.2 (D-0050); `docs/specs/` com especificações de fatia.

**Revisão 1.1 (2026-09-26):** estado operacional em `.appfactory/runtime/`, worktree de integração, arquivos de autenticação/STOP/instância, `pytest.ini` protegido.

```
D:\Claude\app-factory\
├── AGENTS.md  PROJECT_STATE.md  TASK_QUEUE.md  DECISIONS.md  CHANGELOG.md          [V][P]
├── HANDOFF.md  KNOWN_ISSUES.md  TEST_STATUS.md  RESOURCE_POLICY.md  COMMAND_LOG.md  [V][P]
│     (estado VERSIONADO do desenvolvimento da fábrica; o daemon não escreve aqui)
├── README.md                                    [V] (F2)
├── pyproject.toml  uv.lock  .python-version     [V] (F2)  Python 3.13 via uv (sem [tool.pytest])
├── pytest.ini                                   [V][P] (F2) única configuração do pytest
├── .gitignore  .gitattributes                   [V][P]
│
├── config/                                      [V][P] (F2) configuração SEM segredos; toda a pasta é protegida (D-0052); `.yaml` no subconjunto JSON (D-0049)
│   ├── factory.yaml            portas, caminhos, workspace padrão
│   ├── resources.yaml          limites (espelho executável do RESOURCE_POLICY.md)
│   ├── models.yaml             catálogo, local_allowlist (modelos verificados) e perfis
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
│   ├── core/          daemon.py, api.py [P] (FastAPI), auth.py [P], stop.py [P], instance.py [P], eventbus.py, config.py, ids.py, clock.py [P] (tempo ativo), paths.py [P], procinfo.py [P]
│   ├── jobs/          manager.py [P], store.py [P], executor.py [P], states.py [P], handlers.py [P], errors.py, scheduler.py, state_machine.py [P], dag.py,
│   │                  leases.py [P], locks.py [P], integrator.py, recovery.py [P], jobobjects.py [P]
│   ├── resources/ [P] manager.py, policy.py, modes.py, gpu_accounting.py, probes/{windows.py, nvidia.py, runtime_local.py, linux.py}
│   ├── routing/       model_router.py, provider_router.py [P], budget.py [P], model_registry.py [P], health.py,
│   │                  providers/{base.py, ollama.py, openai_compat.py, tool.py}
│   ├── agents/        base.py, runner.py, prompts/,
│   │                  master/ planner/ research/ browser/ coder/ database/ uiux/ debug/ qa/ build/ security/ evolution/
│   ├── media/         engine.py, backends/
│   ├── memory/        context_pack.py, store.py, summaries.py, index/
│   ├── checkpoints/ [P] service.py, rollback.py, snapshot.py
│   ├── logs/ [P]      jsonlog.py, redaction.py, audit.py
│   ├── handoff/       generator.py, templates/
│   ├── security/ [P]  permissions.py, command_policy.py, approvals.py, secrets.py, paths.py, diff_guard.py, acl.py,
│   │                  sandbox/{s1h_runner_user.py, docker.py}
│   ├── toolbox/ [P]   fs.py, shell.py (mínimos na fatia 2.2, D-0050), git.py, web.py, browser.py, db.py, journal.py (fatia 2.8)
│   └── cli/           main.py [P] (comando "af")
│
├── tests/                                       [V] (F2+)
│   ├── unit/  integration/  fixtures/
│   └── guardrails/ [P] invariantes I1–I7 + pytest.ini próprio (rodado com --noconftest) + MANIFEST.json (active/pending, D-0048)
├── evals/                                       [V][P] (F-evo) tarefas de referência
├── evolution/                                   [V] (F-evo)
│   ├── proposals/EP-NNNN.md
│   └── reports/EP-NNNN.md
├── docs/
│   ├── architecture/   esta especificação   [V][P]
│   ├── runbooks/       operação (iniciar/parar/recuperar) [V] (F2+)
│   └── specs/          especificações executáveis de fatia (ex.: fase-2.2-guardrails-e-seguranca.md) [V]
├── tools/diagnostics/  measure-hardware.ps1 [V][P] (F1) utilitários de diagnóstico (não é o Toolbox)
├── scripts/            scripts de desenvolvimento [V] (F2+)
│
├── workspaces/                                  [I] projetos gerados; cada um é um repo Git próprio
│   ├── <projeto>/      checkout em main (não usado por agentes); .appfactory/handoff.md versionado no repo do projeto
│   └── _worktrees/<projeto>/
│       ├── _integration-<job>/   branch af/<job>/integration
│       └── <task>/               branch af/<job>/<task> (ACL do afrunner só aqui, durante a task)
│
└── .appfactory/
    ├── job.json                    [V][P] RESUMO DE MARCO (só muda em fim de fase/revisão)
    ├── checkpoints/CP-NNNN-*.json  [V][P] marcos
    ├── state/factory.db            [I] SQLite (fonte da verdade; só o daemon abre)
    ├── state/snapshots/            [I] VACUUM INTO nos marcos
    ├── jobs/<job-id>/              [I] spec, plan.vN.json, context/, tasks/, responses/, qa/, research/, artifacts/, quarantine/, tmp/
    ├── logs/                       [I] afd.jsonl, jobs/<job>.jsonl, audit.jsonl
    ├── cache/                      [I] research/, índices
    ├── runtime/                    [I] ESTADO OPERACIONAL: runtime/job.json (espelho do job ativo), afd.lock,
    │                                   pids/, tokens/ (user.token; ACL só usuário principal), handoff/, hardware/
    ├── locks/  tmp/                [I]
    └── STOP                        [I] gatilho do kill switch (criar = parar; apagar NÃO libera — 08 §9)
```

Regra: o nome `tools/` na raiz é só para utilitários humanos de diagnóstico; o **Toolbox** dos agentes fica em `src/appfactory/toolbox/`.
