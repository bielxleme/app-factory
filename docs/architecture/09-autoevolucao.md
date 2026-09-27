# 09 — Autoevolução (H)

**Revisão 1.1 (2026-09-26):** infraestrutura protegida ampliada e rejeição automática de EPs que toquem caminhos protegidos (N2, D-0029). Lista completa em `08-seguranca.md` §5.1.

**Revisão 2.2 (2026-09-27):** guardrails pendentes e habilitação do Evolution (D-0048), lista protegida ampliada (D-0051, D-0052), prazos do STOP desde o T0 persistido (D-0054).

## 1. Invariantes protegidas (não podem ser removidas nem enfraquecidas)

| # | Invariante | Teste guardião (`tests/guardrails/`) |
| --- | --- | --- |
| I1 | Todo evento de ciclo de vida é logado; `audit.jsonl` com cadeia de hashes íntegra | `test_logging_invariants.py` |
| I2 | Checkpoints de passo/task/marco são criados e restauráveis | `test_checkpoint_invariants.py` |
| I3 | Rollback funciona (revert de merge, restauração de marco) | `test_rollback_invariants.py` |
| I4 | Limites de recursos são aplicados; os valores não passam dos tetos do `RESOURCE_POLICY.md` | `test_resource_limits.py` |
| I5 | Controles de segurança: allowlists, redação de segredos, sandbox S1h/S2, ACL do `afrunner`, separação de tokens, `protected-paths` | `test_security_invariants.py` |
| I6 | Kill switch e pause/cancel param tudo em ≤ 40 s **medidos desde o T0 persistido** (`terminate` ≤ T0 + 30 s; D-0054); STOP persiste e **apagar o arquivo não libera**; Job Object mata tudo se o daemon morrer | `test_stop_mechanisms.py` |
| I7 | Ações R3 exigem aprovação humana; orçamento pago padrão = 0 | `test_human_approval.py` |

Guardrails de componentes ainda inexistentes ficam `pending` no manifesto protegido `tests/guardrails/MANIFEST.json` (D-0048). **`pending` nunca significa aprovação.**

## 2. Ciclo de uma Evolution Proposal (EP)

```
PROPOSED -> IMPLEMENTED -> TESTED -> COMPARED -> APPROVED|REJECTED -> MERGED -> (MONITORED) -> KEPT|REVERTED
```

1. **Proposta** (`evolution/proposals/EP-NNNN.md`): problema observado (com métricas), hipótese, mudança proposta, arquivos afetados, riscos, como reverter, critério de sucesso.
2. **Registro:** EP no banco e em `DECISIONS.md` como "proposta" (ainda não é decisão).
3. **Implementação** em worktree `evo/EP-NNNN` a partir de `main`.
4. **Verificação de caminhos (antes de qualquer teste):** `git diff --name-status --find-renames main...evo/EP-NNNN`, feita por código confiável. Qualquer caminho protegido (08 §5.1) adicionado, alterado, renomeado, removido ou alcançado por symlink ⇒ **`REJECTED` automático**, sem executar nada do candidato.
5. **Teste:** suíte completa em S1h/S2 (o código do candidato é não confiável) + **todos** os guardrails (I1–I7) pelo comando fixo `python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails`. Qualquer guardrail falhando **ou qualquer invariante `pending` no manifesto** = rejeição automática (D-0048).
6. **Comparação:** `evals/` (tarefas de referência fixas) baseline × candidato: taxa de sucesso, tempo, tokens, pico de RAM/VRAM, falhas. Relatório em `evolution/reports/EP-NNNN.md`.
7. **Aprovação humana** obrigatória para merge (R3), com confirmação interativa (08 §8). EP que altere dependências (`pyproject.toml`/`uv.lock`) exige também auditoria do Security Agent.
8. **Reversível:** merge `--no-ff` único por EP + checkpoint de marco antes; monitoramento por 7 dias ou 20 jobs: regressão nas métricas → proposta automática de revert (o revert também é aprovado pelo humano, mas pode ser pré-autorizado).

## 3. Limites do Evolution Agent

- Não pode editar nenhum caminho de `08-seguranca.md` §5.1 — entre eles `config/**`, `src/appfactory/toolbox/**`, `src/appfactory/security/**`, núcleo do Job Manager (`jobs/store.py`, `manager.py`, `executor.py`, `states.py`, `handlers.py`), `src/appfactory/cli/main.py`, `src/appfactory/resources/**`, `src/appfactory/routing/budget.py`, `src/appfactory/checkpoints/**`, `src/appfactory/logs/audit.py`, `src/appfactory/jobs/recovery.py`, `tests/guardrails/**`, `evals/**`, `pytest.ini`/`conftest.py`, `RESOURCE_POLICY.md`, `AGENTS.md`, `DECISIONS.md`. Aplicação em 3 camadas: Toolbox, ACL do `afrunner` e verificação automática do diff.
- Não pode aumentar limites de recursos acima dos tetos, habilitar provedores pagos, ampliar allowlists de rede/comando nem reduzir o nível de risco de ações.
- **Só pode ser habilitado quando I1–I7 estiverem todas `active`** no manifesto dos guardrails (D-0048).
- Não roda enquanto houver jobs do usuário pendentes; só em modo BACKGROUND, prioridade P3.
- Uma EP por vez; no máximo 1 EP a cada 24 h (configurável só pelo usuário).
- Mudanças em caminhos protegidos só por commits humanos, fora do fluxo de evolução.
