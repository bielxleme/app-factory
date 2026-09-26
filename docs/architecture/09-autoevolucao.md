# 09 — Autoevolução (H)

## 1. Invariantes protegidas (não podem ser removidas nem enfraquecidas)

| # | Invariante | Teste guardião (`tests/guardrails/`) |
| --- | --- | --- |
| I1 | Todo evento de ciclo de vida é logado; `audit.jsonl` com cadeia de hashes íntegra | `test_logging_invariants.py` |
| I2 | Checkpoints de passo/task/marco são criados e restauráveis | `test_checkpoint_invariants.py` |
| I3 | Rollback funciona (revert de merge, restauração de marco) | `test_rollback_invariants.py` |
| I4 | Limites de recursos são aplicados; os valores não passam dos tetos do `RESOURCE_POLICY.md` | `test_resource_limits.py` |
| I5 | Controles de segurança: allowlists, redação de segredos, sandbox, `protected-paths` | `test_security_invariants.py` |
| I6 | Kill switch e pause/cancel param tudo em ≤ 40 s | `test_stop_mechanisms.py` |
| I7 | Ações R3 exigem aprovação humana; orçamento pago padrão = 0 | `test_human_approval.py` |

## 2. Ciclo de uma Evolution Proposal (EP)

```
PROPOSED -> IMPLEMENTED -> TESTED -> COMPARED -> APPROVED|REJECTED -> MERGED -> (MONITORED) -> KEPT|REVERTED
```

1. **Proposta** (`evolution/proposals/EP-NNNN.md`): problema observado (com métricas), hipótese, mudança proposta, arquivos afetados, riscos, como reverter, critério de sucesso.
2. **Registro:** EP no banco e em `DECISIONS.md` como "proposta" (ainda não é decisão).
3. **Implementação** em worktree `evo/EP-NNNN` a partir de `main`.
4. **Teste:** suíte completa + **todos** os guardrails (I1–I7). Qualquer guardrail falhando = rejeição automática.
5. **Comparação:** `evals/` (tarefas de referência fixas) baseline × candidato: taxa de sucesso, tempo, tokens, pico de RAM/VRAM, falhas. Relatório em `evolution/reports/EP-NNNN.md`.
6. **Aprovação humana** obrigatória para merge (R3).
7. **Reversível:** merge `--no-ff` único por EP + checkpoint de marco antes; monitoramento por 7 dias ou 20 jobs: regressão nas métricas → proposta automática de revert (o revert também é aprovado pelo humano, mas pode ser pré-autorizado).

## 3. Limites do Evolution Agent

- Não pode editar `config/policies/protected-paths.yaml`, os caminhos listados nele, `tests/guardrails/**` nem `evals/` de referência. O Toolbox impõe isso; tentativas geram `security.violation`.
- Não pode aumentar limites de recursos acima dos tetos, habilitar provedores pagos, ampliar allowlists de rede/comando nem reduzir o nível de risco de ações.
- Não roda enquanto houver jobs do usuário pendentes; só em modo BACKGROUND, prioridade P3.
- Uma EP por vez; no máximo 1 EP a cada 24 h (configurável só pelo usuário).
- Mudanças em caminhos protegidos só por commits humanos, fora do fluxo de evolução.
