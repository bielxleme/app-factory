# Runbook — Guardrails e segurança de execução (Fase 2.2)

Especificação: `docs/specs/fase-2.2-guardrails-e-seguranca.md` · Decisões: D-0048 a D-0057 · Normativo: `docs/architecture/08-seguranca.md`.

## O que existe nesta fase

- **Política de caminhos e de arquivos** (`src/appfactory/security/paths.py`): lista protegida em `config/policies/protected-paths.yaml`; tudo que não é explicitamente permitido é negado.
- **Verificador de diff** (`security/diff_guard.py`): rejeita diff que toque caminho protegido, symlink, gitlink ou `[tool.pytest` no `pyproject.toml`. Erro do git = rejeição.
- **CommandPolicy** (`security/command_policy.py` + `config/policies/commands.yaml`): allowlist, negações, sem shell, timeout obrigatório, npm/pip.
- **Sandboxes S1h/S2** (`security/sandbox/`): só contrato e especificação. **Os dois falham fechados**: nenhum código não confiável é executado nesta fase.
- **Auditoria** (`logs/audit.py`): `.appfactory/logs/audit.jsonl` com cadeia de hashes.
- **Toolbox mínimo** (`toolbox/fs.py`, `toolbox/shell.py`, D-0050).
- **Guardrails** (`tests/guardrails/`, manifesto `MANIFEST.json`, D-0048).

## Comandos

Todos aceitam `--root <raiz>`. Códigos de saída: `0` ok/permitido, `3` rejeitado/negado/adulterado, `2` erro.

| Comando | Para quê |
| --- | --- |
| `uv run af guard check-diff --base main --head <branch> [--repo <repo>]` | Verifica um diff antes de integrar. Projetos gerados (`workspaces/`) têm regras próprias (D-0053). |
| `uv run af guard check-path --op write --path src/x.py --worktree <wt> --writes "src/**"` | Mostra a decisão da política de arquivos. |
| `uv run af audit verify` | Verifica a cadeia de hashes de `audit.jsonl`. |
| `uv run af guardrails status` | Mostra invariantes `active`/`pending` e se o Evolution poderia ser habilitado. |
| `uv run af guardrails run` | Roda o comando fixo dos guardrails e mostra a aprovação. |

Comando fixo (08 §5.3), a partir da raiz do repositório:

```powershell
uv run python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails
```

## Regras que não mudam

- **`pending` nunca significa aprovação.** A suíte verde com pendências não aprova nada; o Evolution só pode ser habilitado com I1–I7 todas `active` (D-0048).
- STOP: `terminate` em ≤ T0 + 30 s e encerramento total em ≤ T0 + 40 s, com T0 = instante persistido no SQLite (D-0054). Apagar `.appfactory/STOP` nunca libera; só `af resume-factory` com código digitado.
- Até a fatia 2.4 não há Job Object (KI-0019): um passo confiável executado no próprio processo que ignore `should_stop` não pode ser morto.
- Arquivos protegidos só mudam em sessão de desenvolvimento dirigida pelo usuário, com registro em `DECISIONS.md` (`AGENTS.md` §3.15).

## Diagnóstico

| Sintoma | Causa provável | Ação |
| --- | --- | --- |
| Job `BLOCKED` com `sandbox_unavailable:S1h`/`S2` | Esperado na 2.2: não há sandbox real | Nenhuma; S1h/S2 chegam na fatia 2.6 |
| Job `BLOCKED` com `approval: approval_required (R2)` | Comando R2 sem pré-autorização | Aprovações interativas chegam na 2.6 |
| Job `BLOCKED` com `policy_violation` | 2ª violação no mesmo job, ou diff protegido | Ver `af job history <id>` e `audit.jsonl` |
| `af audit verify` com código 3 | Linha removida/alterada/reordenada | Tratar como incidente; não editar o arquivo |
| Erro "fora do subconjunto JSON (D-0049)" | Arquivo `.yaml` com sintaxe YAML/comentários | Reescrever em JSON puro |
