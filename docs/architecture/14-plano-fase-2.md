# 14 — Proposta de fatiamento da implementação (NÃO executar sem instrução)

**Revisão 1.1 (2026-09-26):** fatias reordenadas para incorporar N1–N7 (segurança do código não confiável, infraestrutura protegida, ciclo de vida do daemon, GPU no WDDM, classificação de modelos, estado operacional, concorrência por projeto).

Cada fatia termina com testes, checkpoint e registro nos arquivos de estado. Ações fora do repositório (criar usuário Windows, ACLs, tarefa agendada, mudanças no Ollama) são **R3** e feitas **pelo usuário**, com confirmação.

| Fatia | Conteúdo | Critério de pronto |
| --- | --- | --- |
| 2.1 Fundação + Job Manager (**redefinida pelo usuário, D-0041; implementada**) | `pyproject.toml`, `pytest.ini`, `src/`, IDs, relógio de tempo ativo, logging JSONL + redação, SQLite (WAL, `synchronous=FULL`, estado+evento na mesma transação, triggers de imutabilidade); Job Manager: estados (+`STOPPING`/`STOPPED`), fila persistente, checkpoints atômicos, retomada, STOP de job e da fábrica, recuperação de órfãos, leases com verificação de vida e fencing, 1 RUNNING por projeto, locks por projeto, histórico por job, CLI mínima | cenários de aceite automatizados (crash→recuperação→retomada→COMPLETED; RUNNING→STOPPING→STOPPED) |
| 2.2 Guardrails primeiro | `tests/guardrails/` I1–I7 (com `pytest.ini` próprio, `--noconftest`), `protected-paths.yaml`, verificador de diff de caminhos protegidos | suíte roda pelo comando fixo; diff de teste tocando caminho protegido é rejeitado |
| 2.3 Resource Manager | sondas Windows/NVIDIA/runtime local, contabilidade de VRAM do WDDM (05 §1.1), modos, admissão, CLI `af resources` | valores batem com `measure-hardware.ps1`; **matriz de validação da GPU** executada (KI-0017) |
| 2.4 Daemon (o núcleo do Job Manager já veio na 2.1) | instância única, `af daemon start/stop/status`, Job Object raiz, encerramento de processos mudos, carência pós-sono, escritor único do SQLite (D-0037), recuperação automática na partida | testes de crash/retomada com daemon, sono real, órfãos mortos pelo Job Object |
| 2.5 Routers | adaptador Ollama, `local_allowlist`, **verificação real dos modelos com o usuário** (inclui `qwen3-coder:latest`, KI-0009), registro de posse, Provider Router *fail-closed* | nenhum modelo não verificado usado como local; só modelos próprios descarregados |
| 2.6 Segurança de execução | tokens por papel, aprovações interativas, secrets via keyring; **prova de conceito S1h** (usuário `afrunner` criado pelo usuário, logon secundário + Job Object + ACL) e S2 | PoC aprovada (KI-0014/KI-0016) ou decisão registrada de usar só S2 |
| 2.7 Checkpoint + Handoff | 3 níveis, rollback, handoff operacional (`runtime/handoff/`) e do projeto | restauração testada; estado versionado intocado pelo daemon |
| 2.8 Primeiros agentes | Master (T1), Planner, Coder, QA, Debug num projeto de exemplo, executando código em S1h/S2 | job "hello API" completo, local |
| 2.9+ | Research, Browser, DB, UI/UX, Build, Security Agent, Media, Evolution; `af daemon install-autostart` (com o usuário) | conforme novas fases |

Pré-requisitos do usuário, em momentos indicados: criação do usuário `afrunner` e ACLs (2.6) · tarefa de logon (2.9+) · verificação dos modelos (2.5) · eventual migração dos modelos do Ollama para D: (D-0034, decisão futura).
