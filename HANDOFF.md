# HANDOFF.md — Ponto de parada

**Atualizado em:** 2026-09-27 04:50 -03:00 · **Por:** Claude (Cowork)

## Situação
**Fase 2.2 (Guardrails e segurança de execução) concluída e validada.** Commit `6fb983c` (= `origin/main`); **CP-0005 validado** (`phase_2_2_validated`, `validated_commit: 6fb983c`). Falta só o commit desta consolidação documental.

## O que foi implementado
- `config/policies/protected-paths.yaml` e `commands.yaml` (subconjunto JSON, D-0049).
- `src/appfactory/security/`: `paths.py` (política de caminhos/arquivos, `classify_repo`), `diff_guard.py`, `command_policy.py`, `guardrail_manifest.py`, `sandbox/` (contrato, seleção, S1h/S2 **falhando fechados**).
- `src/appfactory/logs/audit.py` (cadeia de hashes), `src/appfactory/core/auth.py` (papéis/tokens em memória), `src/appfactory/toolbox/fs.py` e `shell.py` (D-0050).
- Integração aditiva com o Job Manager da 2.1 (`manager.py`, `executor.py`, `handlers.py`) e CLI (`af guard`, `af audit`, `af guardrails`) — registrada em D-0055.
- `tests/guardrails/` (I1–I7 + `MANIFEST.json` + `pytest.ini` próprio), testes G22-01…G22-54, `tests/fakes/` (FakeSandbox só em testes), `docs/runbooks/seguranca.md`.

## Resultado dos testes
- Linux (VM 3.10 e nuvem 3.11/3.12/3.13, `unittest`): **164 testes OK**, 10 pulados (7 guardrails `pending`, 2 que exigem pytest, 1 só-Windows). Os 58 testes da 2.1 continuam passando e não foram alterados.
- Windows real (CPython 3.13.14, pytest 9.1.1): 1ª execução 156 passed, 7 skipped, 1 failed (nomes 8.3) → corrigido em `security/paths.py`; revalidação **`uv run pytest`: 157 passed, 7 skipped, 0 failed**; **guardrails: 21 passed, 7 skipped, 0 failed**; `git diff --check` sem erro (aviso LF→CRLF em `tools/diagnostics/measure-hardware.ps1`, arquivo não alterado pela 2.2).

## Limitações conhecidas
- KI-0019: sem Job Object até a 2.4 — passo confiável no próprio processo que ignore `should_stop` não pode ser morto.
- S1h/S2 não existem de verdade (KI-0014, KI-0015, KI-0016, KI-0011): toda execução não confiável termina em `BLOCKED(sandbox_unavailable)`.
- P-13: corte das últimas linhas do `audit.jsonl` não é detectável só pela cadeia (KI-0021); P-14: hooks do git em worktrees graváveis (KI-0022).
- P-11 decidida em D-0056 (fail-closed na 2.2; STOP por falha de integridade obrigatório na 2.4) e P-08 em D-0057 (autorização com escopo limitado). Escolhas provisórias de P-09, P-10, P-12, P-13 e P-14 em D-0055 aguardam decisão; P-04 também segue aberta.

## Próxima ação (usuário, PowerShell em `D:\Claude\app-factory`)
```powershell
git status
git add .
git commit -m "chore: validate Phase 2.2 checkpoint"
git push
```

## Regras para a próxima IA
- Ler `AGENTS.md`, `DECISIONS.md` (D-0048 a D-0057), a especificação da 2.2 e `docs/runbooks/seguranca.md`.
- Não iniciar a 2.3 (Resource Manager) sem nova instrução do usuário. Obrigações já registradas para a 2.4 (D-0056) e para a fatia da API/daemon (D-0057) estão na `TASK_QUEUE.md`.
