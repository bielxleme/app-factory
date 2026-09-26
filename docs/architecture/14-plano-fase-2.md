# 14 — Proposta de fatiamento da implementação (NÃO executar sem instrução)

Ordem pensada para que cada fatia seja testável e segura antes da próxima. Cada fatia termina com testes, checkpoint e handoff.

| Fatia | Conteúdo | Critério de pronto |
| --- | --- | --- |
| 2.1 Fundação | `pyproject.toml` (uv, Python 3.13), estrutura `src/`, config loader, IDs, logging JSONL + redação, SQLite + migrações do esquema de `03-jobs.md` | `af --version`, testes unitários, log sem segredos |
| 2.2 Guardrails primeiro | `tests/guardrails/` I1–I7 como esqueletos que falham até o componente existir; `protected-paths` | suíte roda e reporta |
| 2.3 Resource Manager | sondas Windows/NVIDIA/Ollama, modos, admissão, CLI `af resources` | valores batem com `measure-hardware.ps1` |
| 2.4 Job Manager | máquina de estados, leases, locks, recuperação, runner "eco" (agente falso) | testes de crash/retomada e de lock |
| 2.5 Routers | adaptador Ollama, Model Router com catálogo, Provider Router com política de custo 0, medição real de VRAM por modelo | chamada local ok; troca por cota simulada vai para WAITING |
| 2.6 Toolbox + Security | fs/shell/git com política, journal, Approval Gate, secrets via keyring, sandbox S1 | testes de violação negada |
| 2.7 Checkpoint + Handoff | 3 níveis, rollback, geração dos arquivos de estado | restauração testada |
| 2.8 Primeiros agentes | Master (T1), Planner, Coder, QA, Debug num projeto de exemplo | job "hello API" completo, local |
| 2.9+ | Research, Browser, DB, UI/UX, Build, Security Agent, Media, Evolution | conforme novas fases |

Pré-requisitos a decidir pelo usuário antes da 2.3/2.5: KI-0008 (mover modelos do Ollama para D:), KI-0009 (natureza do `qwen3-coder:latest`), variáveis `OLLAMA_*` recomendadas, se Docker Desktop pode ser iniciado sob demanda.
