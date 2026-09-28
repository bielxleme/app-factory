# HANDOFF.md — Ponto de parada

**Atualizado em:** 2026-09-27 19:27 -03:00 · **Por:** Claude (Cowork)

## Situação
**Fase 2.2 concluída, validada e consolidada** — `6fb983c` + `f44ac72` (= `origin/main`); CP-0005 `phase_2_2_validated`.
**Fase 2.3 (Resource Manager): implementada (D-0073), validada parcialmente no Windows — PENDENTE. NÃO commitada. CP-0006 não gerado.**
- Windows (2026-09-27): `uv run pytest` 210 passed/7 skipped; guardrails 22/6; G23-27 ok; `af resources compare` `"ok": true`; `git diff --check` ok; M1–M4 sem falha de sonda.
- M1 conforme. M2/M3 ficaram em CRITICAL por RAM real baixa (0,19–1,66 GB) — detecção de CONTENTION visível nas razões, modo esperado não observável. M4: nenhum modelo no `/api/ps` (possível modelo `*-cloud`).
- Defeito encontrado e corrigido depois da validação: uso alheio da GPU pela média de 30 s (D-0074). Linux 218 OK; **o Windows precisa rodar de novo**.

## O que foi implementado
- `config/resources.yaml` (subconjunto JSON; sem `mode_confirmations`; `interval_s: 1`; reserva de CONTENTION 3,0 GB).
- `src/appfactory/resources/`: `policy.py` (esquema fechado, tetos e limiares canônicos — D-0064), `probes/` (Windows via `ctypes` com `GlobalMemoryStatusEx`; NVIDIA pela NVML com `nvidia-smi` só como fallback isolado; Ollama só `GET /api/ps`; Linux mínima), `gpu_accounting.py`, `modes.py` (histerese de 10 s por tempo ativo; ociosidade instantânea), `history.py` (histórico do `watch`), `manager.py` (snapshot, modo, admissão, lease de GPU em memória, `watch`), `compare.py`.
- CLI `af resources snapshot|mode|admit|watch|compare` (aditivo em `cli/main.py`); guardrail `I4.resources_config_within_ceilings` **ativo**; AC-06 ampliado só com `resources/probes/nvidia.py`.
- Testes: `test_resource_policy`, `test_resource_modes`, `test_gpu_accounting`, `test_admission`, `test_probes`, `test_cli_resources`, `tests/fakes/probes.py`. Runbook `docs/runbooks/recursos.md`.
- Job Manager, `core/stop.py`, `core/clock.py`, `security/**`, `pyproject.toml`, Ollama e `measure-hardware.ps1` **não** foram alterados. Nenhuma tabela ou migração nova.

## Resultado dos testes (Linux)
- VM Python 3.10.12 e nuvem 3.11/3.12/3.13 (`unittest`): **217 testes OK, 10 pulados** (6 guardrails `pending`, 2 que exigem pytest, 2 só-Windows: G22 e G23-27).
- Guardrails (`unittest`): **22 OK, 6 pulados**. `git diff --check`: sem erro.

## Próxima ação
- Rodada 2.3b (Windows): 211 passed/7 skipped, guardrails 22/6, M2 **PASS**, M3/M4 **não conclusivos** (CRITICAL por RAM). Ver `TEST_STATUS.md`.
- Correção D-0075 aplicada depois da rodada (Ollama a cada 15 s em segundo plano; `watch` mantém 1 s). Linux 223 OK.
- **Usuário (Windows):** `cd D:\Claude\app-factory` e `powershell -ExecutionPolicy Bypass -File .appfactory\runtime\validate-2.3c.ps1` — suíte (esperado 216 passed/7 skipped), guardrails (22/6), M3 e M4 com portão de RAM ≥ 3,0 GB; M4 exige `qwen3:8b` no `ollama ps`. Resultados em `.appfactory\runtime\validation-2.3c\` e `ki0017-M3/M4.jsonl` (rodadas anteriores em `*.run1/run2.jsonl`). CRITICAL durante M3/M4 = NON-CONCLUSIVE. **Até lá: Fase 2.3 PENDENTE, sem CP-0006, sem commit, sem push.**

## Regras para a próxima IA
- Ler `AGENTS.md`, `DECISIONS.md` (até D-0075), `docs/architecture/05-resource-manager.md`, a especificação e o runbook da 2.3.
- Não gerar o CP-0006 sem os resultados do Windows e de M1–M4. Não alterar o Ollama nem `tools/diagnostics/measure-hardware.ps1`.
- Obrigações da 2.4 (D-0056, D-0060, D-0061), da 2.5 (D-0066) e da fatia da API/daemon (D-0057) estão na `TASK_QUEUE.md`. Pendências da 2.2 (P-04, P-09, P-10, P-12, P-13, P-14) seguem abertas.
