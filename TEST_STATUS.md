# TEST_STATUS.md — Testes e verificações

Ambientes: **VM** = shell local do Cowork (Ubuntu 22.04.5, isolado) · **Nuvem** = ambiente de nuvem do Claude · **WSL** = WSL do usuário · **PS** = PowerShell do usuário (Git para Windows).

| # | Verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| V01 | Sistema operacional do host | VM (`get_device_info`) | OK — Windows (`win32`, x64), máquina "gabriel" |
| V02 | SO do shell | VM (`uname -a`, `/etc/os-release`) | OK — Ubuntu 22.04.5 LTS (VM do Cowork, não é o WSL) |
| V03 | WSL / distribuição | — | NÃO VERIFICADO (sem acesso ao WSL; KI-0001) |
| V04 | Versão do Git | VM | OK — git 2.34.1 |
| V05 | Configuração Git | VM | Sem `~/.gitconfig` na VM (esperado). Config do WSL não verificada |
| V06 | Conexão GitHub | VM | FALHA — 403 do proxy (KI-0002) |
| V07 | Conexão GitHub (leitura) | Nuvem (`git ls-remote`) | OK — exit 0, repositório existe e está vazio |
| V08 | `D:\Claude` existe | VM | OK — continha `Agent research/` e `Historinhas da biblia/` (intocados) |
| V09 | Repositório local prévio | VM | OK — `D:\Claude\app-factory` não existia |
| V10 | `git init -b main` | VM | OK |
| V11 | `git remote -v` | VM | OK — `origin https://github.com/bielxleme/app-factory.git` (fetch/push) |
| V12 | `git status` inicial | VM | OK — "On branch main / No commits yet"; deixou `index.lock` (KI-0003, resolvido) |
| V13 | Estrutura de arquivos + `git status --short --untracked-files=all` | VM | OK — 14 arquivos não rastreados, nenhum ignorado indevidamente; sem `index.lock` |
| V14 | Primeiro commit | PS (usuário) + VM | OK — `5aa9709` `chore: initialize App Factory`, autor Gabriel Ximenes, 2026-09-26 16:01:32 -03:00 |
| V15 | Push | PS (usuário) + Nuvem | OK — `git ls-remote` (nuvem): `refs/heads/main` = `5aa9709ada8bb608e1192a9f022b38ff5ef32b31` |
| V16 | Sincronização local/remoto | VM | OK — `git rev-parse main origin/main` iguais; `git status --short --branch` → `## main...origin/main`, sem alterações |
| V17 | Arquivos versionados no commit base | VM (`git ls-files`) | OK — 14 arquivos esperados |
| V18 | Finais de linha | VM (`git ls-files --eol`) | OK — todos `i/lf w/lf` |
| V19 | `.git` sem lock/temporários | VM (`ls .git`) | OK |
| V20 | JSON válido (`job.json`, `CP-0001-fase0.json`) | VM (`python3 -m json.tool`) | OK |

## Fase 1 — Arquitetura (2026-09-26)

| # | Verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| V21 | Leitura integral dos arquivos de estado + CP-0001 | VM | OK |
| V22 | `git status` / `git log --oneline -5` | VM | OK — limpo; `afc1dcc` (CP-0001) sobre `5aa9709` |
| V23 | Remoto sincronizado | Nuvem (`git ls-remote`) | OK — `main` = `afc1dcc42f4f…` |
| V24 | Sintaxe do `measure-hardware.ps1` | Nuvem (PowerShell 7.4.6, `Parser::ParseFile`) | OK — "PARSE OK", só ASCII |
| V25 | Execução do diagnóstico no Windows | PS (usuário) | OK — sem erros; snapshot `snapshot-20260926-161709.json` |
| V26 | Leitura do snapshot (JSON) | VM (`python3`, utf-8-sig) | OK — valores em `RESOURCE_POLICY.md` §1 |
| V27 | Ferramentas no Windows | PS (via snapshot) | Git 2.54.0 · Python 3.13.14 · Node 26.10.0 / npm 11.19.1 · uv 0.12.12 · Docker 29.8.0 · WSL2 (3 distros, paradas) · Ollama 0.34.4 · gh e pnpm **ausentes** |
| V28 | Ferramentas na VM do Cowork | VM | Python 3.10.12 · Node 22.23.2 · git 2.34.1 · uv 0.12.13 · sem Docker/Ollama/nvidia-smi (esperado) |
| V29 | 21 componentes × 14 campos | VM (script Python) | OK — 21 componentes, todos os nomes exigidos, nenhum campo faltando |
| V30 | 8 diagramas | VM (script Python) | OK — 8 seções, blocos de código balanceados |
| V31 | JSON válidos (job.json, CP-0001, CP-0002) | VM (`json.load`) | OK |
| V32 | `.gitignore` cobre state/jobs/cache/STOP/workspaces e não ignora docs/tools/checkpoints | VM (`git check-ignore -v`) | OK |
| V33 | Busca de segredos (ghp_, github_pat_, sk-, AKIA, chaves privadas) | VM (script Python) | OK — nenhum |
| V34 | Links e referências internas entre documentos | VM (script Python) | OK — nenhum quebrado |

## Revisão técnica da Fase 1 (2026-09-26, somente leitura)

| # | Verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| R01 | Working tree = commit analisado | VM (`git diff 4082457 \| wc -l`) | OK — 0 linhas |
| R02 | Remoto | Nuvem (`git ls-remote`) | OK — `main` = `40824577b9b8…` |
| R03 | Revisão técnica da arquitetura | leitura | 8 achados (N1–N8) → Fase 1.1 |

## Fase 1.1 — Revisão e correção documental (2026-09-26)

| # | Verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| V35 | Markdown: blocos de código fechados e tabelas com número de colunas consistente, em todos os `.md` | VM (script Python) | OK |
| V36 | JSON válidos (`job.json`, CP-0001, CP-0002, CP-0003) | VM (`json.load` + `python3 -m json.tool`) | OK — 4 arquivos |
| V37 | Links internos, referências `NN-*.md` e referências de seção (`NN §x.y`) | VM (script Python) | OK — nenhuma quebrada |
| V38 | 21 componentes × 14 campos (após edições) | VM (script Python) | OK |
| V39 | Diagramas | VM (script Python) | OK — 10 (8 obrigatórios + 2 da revisão 1.1) |
| V40 | Frases obsoletas/contraditórias da v1.0 (22 padrões: `models: auto`, `qwen3-coder (local)`, `slots_cpu`, `descarrega tudo`, `path_glob`, `PAUSED ou EXT` etc.) | VM (script Python) | OK — nenhuma nos documentos normativos |
| V41 | Consistência cruzada entre Resource Manager, Job Manager, Segurança, Persistência e Model Router (11 termos-chave presentes em todos os documentos que devem citá-los) | VM (script Python) + revisão manual | OK — 3 contradições encontradas e corrigidas durante a revisão: GPU preemptada ia para `PAUSED` em 02/06 (agora `WAITING(resources)` como em 05 §3); "descarrega tudo" em 05/RESOURCE_POLICY (agora só modelos da fábrica); limite de 8 processos × 32 por Job Object (05 §6 esclarecido) |
| V42 | Nenhuma implementação da Fase 2 (`.py`, `.toml`, `.ini`, `.yaml`, `src/`, `config/`, `tests/` etc.) | VM (`git ls-files` + não rastreados) | OK — nenhuma |
| V43 | Escopo: só documentação, especificação, decisões e estado; `tools/`, `.gitignore`, `.gitattributes` inalterados; nada alterado fora de `D:\Claude\app-factory` | VM (`git status`, `git diff --stat`, `find -newer` em `D:\Claude`) | OK — 27 modificados + 2 novos, todos previstos; nenhum arquivo externo modificado |
| V44 | `git diff --check`, busca de segredos, `.git` sem lock | VM | OK |

## Fase 2.1 — Fundação: Job Manager (2026-09-26)

Ambientes: **VM** = Linux do Cowork, Python 3.10.12 · **Nuvem** = Linux, Python 3.11.15 / 3.12.3 / 3.13.13 · **Windows** = máquina do usuário (ainda não executado, KI-0018). O pytest não pôde ser instalado (PyPI bloqueado nos dois ambientes); os testes são `unittest` compatíveis com pytest (`pytest.ini`).

Comando: `PYTHONPATH=src python -m unittest discover -s tests -t .`

| # | Suíte / verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| T01 | `tests/unit/test_states.py` — transições válidas, rejeição de todas as inválidas, terminais, estados desconhecidos (5) | VM, Nuvem 3.11–3.13 | OK |
| T02 | `tests/unit/test_store.py` — migração idempotente, WAL + `synchronous=FULL`, schema mais novo recusado, `events` append-only, `checkpoints` imutáveis, índice único 1 ativo/projeto, rollback (6) | idem | OK |
| T03 | `tests/unit/test_manager.py` — identidade/IDs únicos (60 criações concorrentes), validação de entrada, persistência após reinício (job, estado, eventos, timestamps), fila após reinício + prioridade/envelhecimento, espelho runtime não é fonte da verdade, COMPLETED só com validação aprovada do checkpoint atual, validação reprovada → FAILED, retry → COMPLETED, 3 falhas → BLOCKED, falha fatal → FAILED, cancelamento (13) | idem | OK |
| T04 | `tests/unit/test_checkpoints.py` — criação/leitura/último, nunca sobrescreve, falha no meio da gravação mantém o anterior, registro corrompido ignorado e marcado `invalid`, último válido após reinício, estado só JSON (5) | idem | OK |
| T05 | `tests/unit/test_stop.py` — STOP gracioso `RUNNING→STOPPING→STOPPED` com checkpoint `stop` e limpeza de temporários, STOP persiste após reinício e é honrado na recuperação, STOP de job na fila/terminal, falha durante a parada (degradada, checkpoint anterior preservado), fencing após parada, STOP da fábrica (bloqueia despacho, persiste, exige confirmação), arquivo STOP aciona e apagá-lo não libera, job em execução pausa e volta à fila na liberação (8) | idem | OK |
| T06 | `tests/unit/test_concurrency.py` — 1 RUNNING por projeto (e outro projeto liberado), corrida de 4 executores na fila do mesmo projeto, dois executores no mesmo job, corrida de 6 executores no mesmo job (1 vence), processo morto → retomada + fencing, processo vivo dentro da carência mantém a posse, processo mudo perde a posse, suspensão não vence lease, reinício, mudança de boot_id sozinha não tira a posse (10) | idem | OK |
| T07 | `tests/unit/test_locks.py` — normalização de `writes` (recusa curingas, absolutos, `..`), sobreposição, tudo-ou-nada por projeto, liberação (3) | idem | OK |
| T08 | `tests/integration/test_acceptance.py` — **ACEITE 1** com processo real: criar → QUEUED → RUNNING → checkpoints → `os._exit` no passo 3 → novo JobManager → `recover` → último válido = passo 2 → retomada (passos 3–5 apenas) → validação → COMPLETED; queda no meio da gravação de checkpoint; queda em passo com efeito colateral → BLOCKED; falha durante a recuperação isolada por job e rotina idempotente; **ACEITE 2** com processo real: RUNNING → STOP → STOPPING → checkpoint `stop` → STOPPED, STOP persiste após reinício, retomada explícita → COMPLETED (5) | idem | OK |
| T09 | `tests/integration/test_cli.py` — create/list/queue/status/run/show/checkpoint/history/db check, stop de job, erros com código 2, liberar STOP exige terminal interativo (3) | idem | OK |
| T10 | Total | VM (3.10) · Nuvem (3.11, 3.12, 3.13) | **58/58 OK** em cada versão |
| T11 | Sintaxe: compilação de 38 arquivos `.py` (src + tests), sem gerar `.pyc`; checagem de imports não usados | VM | OK |
| T12 | SQLite: banco novo → `af db check`: `quick_check=ok`, 0 violações de FK, schema 1, tabelas e triggers presentes, `journal_mode=wal` | VM | OK |
| T13 | `git diff --check` | VM | OK |
| T14 | Segredos (padrões de tokens/chaves) | VM | nenhum |
| T15 | Runtime fora do Git: nenhum `__pycache__`, `.pyc`, `.pytest_cache`, `.db`, `.venv` no repositório; `.appfactory/state|logs|runtime|jobs` ignorados | VM | OK |
| T16 | `.gitignore` não ignora código: **falha encontrada e corrigida** — a regra `logs/` ignorava `src/appfactory/logs/`; ancorada como `/logs/` | VM (`git check-ignore -v`) | OK após correção |
| T17 | `uv run pytest` no Windows | Windows (usuário) | **OK — 58 passaram** (informado pelo usuário; ver V2.1-01) |

## Validação pós-commit da Fase 2.1 (2026-09-26) — commit `4373c65`

| # | Verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| V2.1-01 | `uv run pytest` | Windows (usuário) | **58 passaram** (informado pelo usuário). Evidências no disco: `.venv` criado por uv 0.12.12 com CPython 3.13.14 (`pyvenv.cfg`), pytest 9.1.1 e pluggy 1.6.0 instalados, bytecode `*.cpython-313-pytest-9.1.1.pyc` dos 9 módulos de teste, `uv.lock` commitado |
| V2.1-02 | `git status` | VM | `On branch main` · `Your branch is up to date with 'origin/main'` · `nothing to commit, working tree clean` |
| V2.1-03 | `git log -1 --oneline` | VM | `4373c65 feat: add Job Manager foundation (Phase 2.1)` (autor Gabriel Ximenes, 2026-09-26 23:16:09 -0300; 58 arquivos) |
| V2.1-04 | `git ls-remote` | Nuvem | `refs/heads/main` = `4373c650b084c8ca909f9451bc43e387dced20fb` (sincronizado) |
| V2.1-05 | `git diff --check` | VM | sem saída (OK) |
| V2.1-06 | `uv run pytest` a partir da VM do Cowork | VM | **não executável**: o uv tenta baixar o CPython 3.13 do GitHub e a rede da VM recusa (`tunnel error: unsuccessful`). Nada foi criado no repositório (ambiente e cache fora da pasta) |
| V2.1-07 | `PYTHONPATH=src python3 -m unittest discover -s tests -t .` no commit `4373c65` | VM (Python 3.10.12) | **Ran 58 tests — OK** |
| V2.1-08 | Artefatos ignorados após a execução no Windows | VM (`git status --ignored`) | `.venv/` e `__pycache__/` presentes e **ignorados** pelo Git; nenhum arquivo de runtime rastreado |

## Fase 2.2 — Especificação (2026-09-26, somente leitura; nada implementado)

| # | Verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| S2.2-01 | `git status -sb` / `git log --oneline -3` antes da especificação | VM | `## main...origin/main`, limpo; HEAD `b0a80e5` sobre `4373c65` |
| S2.2-02 | Arquivos rastreados de `src/` × padrões de 08 §5.1 | VM (`git ls-files` + leitura) | Lacuna encontrada: `jobs/manager.py`, `jobs/store.py`, `jobs/executor.py`, `jobs/states.py`, `jobs/handlers.py`, `core/paths.py`, `core/clock.py`, `core/procinfo.py`, `cli/main.py` não são protegidos (registrada como P-05) |
| S2.2-03 | `config/` existe? | VM (`ls`) | Não existe (esperado; criado na implementação da 2.2) |
| S2.2-04 | `StepContext.should_stop` observa o STOP da fábrica? | VM (leitura de `executor.py`) | Não — só STOP do job e perda de posse; mudança aditiva prevista na especificação (§2.5) |
| S2.2-05 | Testes | — | **Não executados** nesta etapa (nenhum código alterado) |

## Fase 2.2 — Aplicação das decisões D-0048 a D-0054 (2026-09-27, somente documentação)

| # | Verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| S2.2-06 | D-0048 a D-0054 definidas uma vez em `DECISIONS.md`; nenhuma referência a decisão inexistente nos 17 documentos verificados | VM (script Python) | OK |
| S2.2-07 | Frases obsoletas (esqueletos que "falham", lista antiga de `config/` em 08/09, "30 s + 10 s" sem marco, "não decidida", "não protegidos hoje", estado "aguardando decisões") | VM (script Python) | OK — nenhuma nos documentos normativos e de estado |
| S2.2-08 | Arquivos de D-0051 presentes em 08 §5.1 e marcados `[P]` em `10-diretorios.md`; `config/**` em 08, 09, 10 e na especificação | VM (script Python) | OK |
| S2.2-09 | "`pending` nunca é aprovação" e "Evolution só com I1–I7 `active`" em `DECISIONS.md`, `AGENTS.md`, 08, 09, 14, especificação, `HANDOFF.md` | VM (script Python) | OK |
| S2.2-10 | Prazos do STOP `T0 + 30 s` / `T0 + 40 s` em `DECISIONS.md`, 01, 08, 15 e especificação; nenhuma menção a "40 s" sem T0 em `docs/architecture/` | VM (script Python) | OK — corrigido durante a verificação: T0 de cancelamento/pausa (o `cancel` da 2.1 não grava `stop_requested_at`) passou a ser o timestamp persistido do pedido (ex.: `jobs.cancelled_at`) |
| S2.2-11 | Regra D-0053 ("na dúvida, fábrica"; tipo de repositório por código confiável) em `DECISIONS.md`, 08 e especificação | VM (script Python) | OK |
| S2.2-12 | Markdown: blocos de código fechados, tabelas com número de colunas consistente; `git diff --check` | VM | OK |
| S2.2-13 | Nenhuma mudança em `src/`, `tests/`, `pytest.ini`, `pyproject.toml`, `uv.lock` | VM (`git diff --stat`) | OK — vazio |
| S2.2-14 | Testes | — | **Não executados** (nenhum código alterado) |

## Fase 2.2 — Implementação (2026-09-27) · base `683b9e2` · não commitada

Ambientes: **VM** = Linux do Cowork, Python 3.10.12 · **Nuvem** = Linux, Python 3.11/3.12/3.13 (cópia dos arquivos) · **Windows** = ainda não executado. Pytest indisponível na VM e na nuvem (PyPI bloqueado pela política de rede); os testes são `unittest` compatíveis com pytest. Comando: `PYTHONPATH=src python -m unittest discover -s tests -t .`

| # | Suíte / verificação | IDs | Ambiente | Resultado |
| --- | --- | --- | --- | --- |
| T2.2-01 | `tests/unit/test_paths_policy.py` — leitura/escrita/remoção/renomeação por área, `..`, absolutos/UNC/outra unidade, symlink/junction, nomes do Windows, hardlink, estado operacional, lista protegida, credenciais, formato D-0049 (21) | G22-01…15, 16a, 17a, 18d, 19, 54 | VM, Nuvem | OK (1 pulado fora do Windows: nomes 8.3) |
| T2.2-02 | `tests/unit/test_diff_guard.py` — A/M/D/R/C/T, diff limpo, symlink/gitlink, `[tool.pytest`, falha do git, maiúsculas, fábrica × projeto, `evo/*`, declaração da TaskSpec ignorada (10) | G22-15b, 16c, 17b, 18a, 21…26, 53 | VM, Nuvem | OK |
| T2.2-03 | `tests/unit/test_command_policy.py` — comandos proibidos, forma do comando, npm/pip, scripts, ambiente limpo (6) | G22-19, 28…31 | VM, Nuvem | OK |
| T2.2-04 | `tests/unit/test_sandbox_selection.py` — nunca rebaixa, produção falha fechada, `S1hLaunchSpec`, `DockerSpec`, tetos, fórmula dos prazos do STOP (6) | G22-32…36 | VM, Nuvem | OK |
| T2.2-05 | `tests/unit/test_audit.py` — concorrência (4 threads + 2 processos, 150 linhas), adulteração, redação antes do hash (4) | G22-17d, 20, 46 | VM, Nuvem | OK (limitação P-13 documentada no teste) |
| T2.2-06 | `tests/unit/test_auth.py` — matriz de papéis, tokens em memória (3) | G22-18e, 47 | VM, Nuvem | OK |
| T2.2-07 | `tests/unit/test_repo_hygiene.py` — config do pytest travada, sem `shell=True`, subprocess confinado, sem dependências, só sandboxes fail-closed em `src/`, nenhuma chamada que altere o SO, `.yaml` em JSON (6) | G22-51, AC-06…09 | VM, Nuvem | OK |
| T2.2-08 | `tests/integration/test_exec_pipeline.py` — execução OK/falha/erro/timeout/limites, produção bloqueia, R2 bloqueia, violação e reincidência, diff rejeitado bloqueia, STOP do job/da fábrica durante a execução (tempo real e simulado), latência de detecção, STOP antes, cancelamento, queda real + recuperação, imutabilidade (16) | G22-16b, 17c, 18b/c, 20, 27, 28b, 30b, 33, 37…45 | VM, Nuvem | OK |
| T2.2-09 | `tests/integration/test_cli_guard.py` — `af guard check-diff` (0/3), `check-path`, `af audit verify` (0/3), `af guardrails status` (4) | AC-04, AC-11 | VM, Nuvem | OK |
| T2.2-10 | `tests/integration/test_guardrails_command.py` — comando fixo e `conftest.py` malicioso ignorado (2) | G22-48, 49 | VM, Nuvem | **pulados** (pytest indisponível) — executar no Windows |
| T2.2-11 | `tests/guardrails/` via `unittest` — I1–I7 + controle do manifesto (28) | I1–I7, G22-50 | VM, Nuvem | OK, 7 pulados = exatamente as verificações `pending` do manifesto |
| T2.2-12 | Suíte completa | todos | VM 3.10 · Nuvem 3.11/3.12/3.13 | **164 testes OK** em cada versão (10 pulados: 7 `pending`, 2 pytest, 1 só-Windows) |
| T2.2-13 | Os 58 testes da 2.1 | — | VM, Nuvem | OK; nenhum arquivo de teste da 2.1 alterado (`git diff --stat tests/unit tests/integration` vazio para arquivos existentes) |
| T2.2-14 | `git diff --check` · busca de segredos · runtime fora do Git | AC-12 | VM | OK (valor fictício `AKIA…` num teste passou a ser montado em tempo de execução) |
| T2.2-15 | `af guardrails status` na raiz real | — | VM | I1 `active`; I2–I7 com pendências (2.3–2.7); `evolution_allowed: false` |
| T2.2-16 | `uv run pytest` e comando fixo dos guardrails | AC-01, AC-02 | **Windows** | **PENDENTE** (usuário) |
| T2.2-17 | `uv run pytest` | todos | **Windows (usuário)** | **156 passed, 7 skipped, 1 failed** — `test_paths_policy.py::FileAccessTests::test_g22_07b_short_names_resolved` (caminho curto 8.3 classificado como `outside_root`) |
| T2.2-18 | Comando fixo dos guardrails | I1–I7 | **Windows (usuário)** | **21 passed, 7 skipped** |
| T2.2-19 | Correção 8.3: `security/paths.py` expande nomes curtos do caminho literal com `GetLongPathNameW` (sem seguir links; falha => negar) ; suíte completa | G22-07b | VM 3.10 | 164 OK (10 pulados); lógica do ramo Windows exercitada por simulação fora do repositório (curto válido permitido; link negado; falha de resolução negada). **Revalidação no Windows: PENDENTE (usuário)** |

## Validação da Fase 2.2 no Windows (2026-09-27) — base `683b9e2` · implementação ainda não commitada

Ambiente: **Windows real** do usuário, `D:\Claude\app-factory`, `uv run` com **CPython 3.13.14** e pytest 9.1.1 (evidências no disco: `.venv/pyvenv.cfg` com `version_info = 3.13.14`, `uv = 0.12.12`; `pytest-9.1.1.dist-info`; bytecode `*.cpython-313-pytest-9.1.1.pyc`). Resultados informados pelo operador.

| # | Verificação | Ambiente | Resultado |
| --- | --- | --- | --- |
| V2.2-01 | `uv run pytest` (após a correção 8.3) | Windows | **157 passed, 7 skipped, 0 failed** (87,02 s). Os 7 pulados são exatamente as verificações `pending` do manifesto dos guardrails (D-0048); G22-48/49 (pytest) e G22-07b (nomes 8.3) executaram |
| V2.2-02 | `uv run python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails` | Windows | **21 passed, 7 skipped, 0 failed** (4,27 s) |
| V2.2-03 | Correção Windows 8.3 (T2.2-19) | Windows | **validada**: `tests/unit/test_paths_policy.py` passou integralmente, incluindo `test_g22_07b_short_names_resolved` (falha registrada em T2.2-17) |
| V2.2-04 | `git diff --check` | Windows | **sem erro**. Único aviso: `warning: in the working copy of 'tools/diagnostics/measure-hardware.ps1', LF will be replaced by CRLF the next time Git touches it` — normalização de final de linha; arquivo não alterado pela 2.2 (`.gitattributes` define `*.ps1 eol=crlf` e a cópia de trabalho está em LF) |
| V2.2-05 | Critérios AC-01 e AC-02 (antes PENDENTES em T2.2-16) | Windows | **OK** |
| V2.2-06 | `git diff --check` · `git status --short` após esta consolidação documental | VM | ver `COMMAND_LOG.md`; nenhuma alteração de código, teste ou configuração |
