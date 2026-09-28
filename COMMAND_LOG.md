# COMMAND_LOG.md — Registro de comandos

Ambientes: **VM** = shell local do Cowork (Ubuntu 22.04.5; `D:\Claude` montado em `$HOME/mnt/Claude`) · **Nuvem** = ambiente de nuvem do Claude · **WSL** = WSL do usuário.
Saídas reais resumidas em `TEST_STATUS.md`.

## 2026-09-26 — Fase 0

### Verificação do ambiente
| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `get_device_info` (ferramenta do Cowork) | Windows x64, máquina "gabriel" |
| VM | `ls -la $HOME/mnt/` ; `ls -la $HOME/mnt/Claude` | `Agent research/`, `Historinhas da biblia/`; sem `app-factory` |
| VM | `uname -a` ; `cat /etc/os-release \| head -5` | Linux 6.8.0 / Ubuntu 22.04.5 LTS |
| VM | `which git gh wsl.exe cmd.exe powershell.exe` | só `/usr/bin/git` |
| VM | `git --version` | git version 2.34.1 |
| VM | `git config --global --list` | sem `~/.gitconfig` |
| VM | `git ls-remote https://github.com/bielxleme/app-factory` | 403 do proxy |
| VM | `curl -sS -o /dev/null -w "%{http_code}" https://api.github.com/repos/bielxleme/app-factory` | 403 do proxy |
| VM | `grep -m1 "model name" /proc/cpuinfo ; nproc ; grep MemTotal /proc/meminfo` | i5-13420H ; 2 ; ~4 GB (limites da VM) |
| Nuvem | `git ls-remote https://github.com/bielxleme/app-factory` | exit 0, sem refs (repo vazio) |

### Criação e Git
| Amb. | Comando |
| --- | --- |
| VM | `cd "$HOME/mnt/Claude" && mkdir -p app-factory/.appfactory/checkpoints && cd app-factory` |
| VM | `git init -b main` |
| VM | `git remote add origin https://github.com/bielxleme/app-factory.git` |
| VM | `git remote -v` ; `git config --local --list` ; `git status` |
| VM | `rm -v .git/index.lock .git/tU1XehK` (com autorização do usuário; KI-0003) |

### Arquivos
| Amb. | Comando |
| --- | --- |
| VM | `cat > <arquivo> <<'EOF' … EOF` para cada arquivo de estado, `.gitignore`, `.gitattributes`, `.appfactory/job.json` |
| VM | `: > .appfactory/checkpoints/.gitkeep` |
| VM | `python3 -m json.tool .appfactory/job.json` (validação) |

### Commit e push (usuário, PowerShell em `D:\Claude\app-factory`) — CONCLUÍDO
Comandos informados pelo usuário:
```powershell
git commit -m "chore: initialize App Factory"   # → 5aa9709
git push -u origin main                          # → sucesso
git status                                       # → working tree clean
git ls-remote origin                             # → main = 5aa9709ada8bb608e1192a9f022b38ff5ef32b31
```

### Validação pós-push e checkpoint (Claude)
| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `ls -la` ; `ls -la .git` | 14 arquivos; sem `index.lock` |
| VM | `git log --oneline --decorate -5` | `5aa9709 (HEAD -> main, origin/main)` |
| VM | `git log -1 --format='%H%n%an%n%ad%n%s' --date=iso` | `5aa9709ada8b…`, Gabriel Ximenes, 2026-09-26 16:01:32 -0300 |
| VM | `git status --short --branch` | `## main...origin/main` (limpo) |
| VM | `git ls-files \| sort` ; `git ls-files --eol` | 14 arquivos; todos LF |
| VM | `git rev-parse main origin/main` | ambos `5aa9709ada8b…` |
| VM | `git config --local --list` | `branch.main.remote=origin` |
| Nuvem | `git ls-remote https://github.com/bielxleme/app-factory` | `refs/heads/main` = `5aa9709ada8b…` |
| VM | `cat > .appfactory/checkpoints/CP-0001-fase0.json <<'EOF' … EOF` | checkpoint criado |
| VM | `cat > <arquivo> <<'EOF' … EOF` (job.json, PROJECT_STATE, TASK_QUEUE, HANDOFF) | reescritos |
| VM | `python3 - <<'PY' … PY` (edições pontuais em DECISIONS, KNOWN_ISSUES, TEST_STATUS, RESOURCE_POLICY, COMMAND_LOG, CHANGELOG) | atualizados |
| VM | `python3 -m json.tool <json>` | ambos válidos |

### Commit do checkpoint (usuário, PowerShell) — PENDENTE
```powershell
git add .
git commit -m "chore: add Phase 0 checkpoint CP-0001"
git push
git status
git log --oneline -2
```

## 2026-09-26 — Fase 1 (Arquitetura)

### Leitura e verificação
| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `git status --short --branch` ; `git log --oneline -5` | limpo; `afc1dcc` sobre `5aa9709` |
| VM | `find . -path ./.git -prune -o -type f -print \| sort` | 15 arquivos |
| VM | `cat AGENTS.md PROJECT_STATE.md HANDOFF.md TASK_QUEUE.md DECISIONS.md CHANGELOG.md KNOWN_ISSUES.md TEST_STATUS.md RESOURCE_POLICY.md .appfactory/checkpoints/CP-0001-fase0.json .appfactory/job.json COMMAND_LOG.md` | lidos |
| VM | `git show --stat --format= afc1dcc` | 11 arquivos |
| Nuvem | `git ls-remote https://github.com/bielxleme/app-factory` | `main` = `afc1dcc42f4f…` |
| VM | `for t in python3 node npm git docker ollama nvidia-smi uv pip3; do …; done` | ver V28 |

### Diagnóstico de hardware
| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `mkdir -p tools/diagnostics && cat > tools/diagnostics/measure-hardware.ps1 <<'EOF' … EOF` | script criado (130 linhas, só ASCII) |
| VM | `LC_ALL=C grep -nP '[^\x00-\x7F]' tools/diagnostics/measure-hardware.ps1` | nenhum caractere fora do ASCII |
| Nuvem | `curl -sSL -o pwsh.tgz …/PowerShell/releases/download/v7.4.6/powershell-7.4.6-linux-x64.tar.gz` + `tar xzf` | PowerShell 7.4.6 temporário (fora do projeto) |
| Nuvem | `pwsh -Command '[System.Management.Automation.Language.Parser]::ParseFile(...)'` | PARSE OK |
| PS (usuário) | `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\diagnostics\measure-hardware.ps1` | OK, snapshot `snapshot-20260926-161709.json` |
| VM | `python3 - <arquivo>` (leitura do snapshot com `utf-8-sig`) | valores em `RESOURCE_POLICY.md` |

### Documentação e estado
| Amb. | Comando |
| --- | --- |
| VM | `mkdir -p docs/architecture` + `cat > docs/architecture/<doc>.md <<'EOF' … EOF` (15 documentos) |
| VM | `sed -i` (alinhamento de uma caixa do diagrama 1) |
| VM | `python3 - <<'PY' … PY` (edições em `.gitignore`, `DECISIONS.md`, `KNOWN_ISSUES.md`, `TEST_STATUS.md`, `CHANGELOG.md`, `AGENTS.md`) |
| VM | `cat > RESOURCE_POLICY.md / PROJECT_STATE.md / TASK_QUEUE.md / HANDOFF.md / .appfactory/job.json / .appfactory/checkpoints/CP-0002-fase1.json <<'EOF' … EOF` |
| VM | `git check-ignore -v …` (confirma o que é e o que não é ignorado) |
| VM | `python3 -m json.tool .appfactory/job.json` ; `python3 -m json.tool .appfactory/checkpoints/CP-0002-fase1.json` |
| VM | script de verificação da documentação (V29–V34) |

### Commit da Fase 1 (usuário, PowerShell) — CONCLUÍDO: `4082457` (informado pelo usuário; confirmado com `git log` na VM e `git ls-remote` na nuvem)
```powershell
git add .
git commit -m "docs: define App Factory architecture (Phase 1)"
git push
```

## 2026-09-26 — Revisão técnica da Fase 1 (somente leitura)

| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `git status --short --branch` ; `git log --oneline -4` ; `git show --stat 4082457` ; `git diff 4082457 \| wc -l` | limpo; working tree = `4082457` (0 linhas de diferença) |
| Nuvem | `git ls-remote https://github.com/bielxleme/app-factory` | `main` = `40824577b9b8…` |
| VM | `cat docs/architecture/*.md RESOURCE_POLICY.md AGENTS.md …` | leitura para a revisão (achados N1–N8) |

## 2026-09-26 — Fase 1.1 (revisão e correção documental)

| Amb. | Comando |
| --- | --- |
| VM | `git status --short --branch` ; `git log --oneline -1` ; `grep -n … docs/architecture/01-componentes.md` (localizar trechos) |
| VM | `cat > docs/architecture/08-seguranca.md <<'EOF' … EOF` (reescrito) · `cat > docs/architecture/15-daemon.md` (novo) · `cat > docs/architecture/07-persistencia.md` (reescrito) · `cat > docs/architecture/14-plano-fase-2.md` (reescrito) |
| VM | `python3 - <<'PY' … PY` (substituições verificadas por `assert` em 00, 01, 02, 03, 04, 05, 06, 09, 10, 11, 12, 13, README, AGENTS.md, RESOURCE_POLICY.md, DECISIONS.md, KNOWN_ISSUES.md, CHANGELOG.md, COMMAND_LOG.md, CP-0002) |
| VM | `cat >> docs/architecture/13-diagramas.md` (diagramas 9 e 10) |
| VM | `cat > .appfactory/checkpoints/CP-0003-fase1-1.json` · `cat > .appfactory/job.json` · `cat > PROJECT_STATE.md / TASK_QUEUE.md / HANDOFF.md` |
| VM | `sed -i` (ajuste de horário nos JSON; `vram_available_for_factory_mib` no exemplo de `12-contratos.md`) |
| VM | `python3 -m json.tool` nos JSON; script de validação (V35–V44) |

### Commit da Fase 1.1 (usuário, PowerShell) — CONCLUÍDO: `40d4d79` (+ `97c82c4` validando o CP-0003, feito pelo usuário)
```powershell
git add .
git commit -m "docs: revise architecture after Phase 1 review (Phase 1.1)"
git push
```

## 2026-09-26 — Fase 2.1 (Job Manager)

| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `git status --short --branch` ; `git log --oneline -5` ; leitura de HANDOFF/TASK_QUEUE/03/07/08/14/15/DECISIONS | limpo em `97c82c4` |
| VM | `python3 -c "import pytest"` ; `pip3 download pytest` | pytest ausente; PyPI inacessível |
| Nuvem | `uv pip install pytest` ; `pip download pytest` | 403 do proxy (PyPI bloqueado) |
| VM | `mkdir -p src/appfactory/... tests/...` + `cat > <arquivo> <<'EOF' … EOF` (código e testes) ; `python3 - <<'PY' … PY` (correções pontuais) | criado |
| VM | `cd /tmp/afsmoke && PYTHONPATH=… python3 -m appfactory job create/run/history ; db check` (fora do repo) | ciclo completo OK |
| VM | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . [-v]` | 1ª execução: 3 falhas (tentativa sem PID tratada como morta) → corrigido; depois 58/58 OK |
| VM → Nuvem | `device_stage_files` (41 arquivos; depois reenvio de `leases.py` e `test_concurrency.py`) ; `python3.11/3.12/3.13 -m unittest discover -s tests -t .` | 57/57 na 1ª rodada; **58/58** em 3.11, 3.12 e 3.13 após a correção do `boot_id` |
| VM | compilação de todos os `.py` em memória ; `af --root /tmp/afdb db check` ; `git diff --check` ; busca de segredos ; `git status --porcelain --ignored` ; `git check-ignore -v …` | OK; `.gitignore` corrigido (`/logs/`) |

### Commit da Fase 2.1 (usuário, PowerShell) — CONCLUÍDO: `4373c65` (após `uv run pytest` com 58 testes aprovados, informado pelo usuário)
```powershell
uv run pytest
git add .
git commit -m "feat: add Job Manager foundation (Phase 2.1)"
git push
```

## 2026-09-26 — Validação pós-commit da Fase 2.1

| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `git status` ; `git log -3 --oneline` ; `git log -1 --format=...` ; `git diff --check` ; `git show --stat/--name-status HEAD` | limpo, sincronizado, `4373c65`, sem problemas |
| Nuvem | `git ls-remote https://github.com/bielxleme/app-factory` | `main` = `4373c650…` |
| VM | `UV_PROJECT_ENVIRONMENT=$HOME/afvenv UV_CACHE_DIR=$HOME/uvcache uv run pytest` | falhou: download do CPython 3.13 bloqueado (rede) |
| VM | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .` | 58 testes OK |
| VM | `cat .venv/pyvenv.cfg` ; `ls .venv/Lib/site-packages` ; `ls tests/*/__pycache__` | evidências da execução no Windows (CPython 3.13.14, pytest 9.1.1) |
| VM | `python3 - <<'PY' … PY` (CP-0004, job.json, TEST_STATUS, KNOWN_ISSUES, CHANGELOG, COMMAND_LOG) ; `cat > PROJECT_STATE.md / HANDOFF.md / TASK_QUEUE.md` | atualizados |

## 2026-09-27 — Fase 2.2: implementação (base `683b9e2`, sem commit)

| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `git status -sb` ; `git log --oneline -3` ; leitura de manager/executor/handlers/cli/paths/store/testes | limpo em `683b9e2` |
| VM | `mkdir -p config/policies src/appfactory/{security/sandbox,toolbox} tests/{fakes,guardrails}` + `cat > <arquivo> <<'EOF' … EOF` ; `python3 - <<'EOF' … EOF` (edições aditivas) | criado/alterado |
| VM | `PYTHONPATH=src:. python3 -m unittest tests.<módulo>` (por módulo, durante o desenvolvimento) | 2 falhas encontradas e corrigidas: `git checkout` sem `-f` após commit só de índice; `LeaseLost` dentro do passo capturado como falha genérica (executor passou a repassá-lo); 1 ajuste de tolerância de 1 ms no teste de latência |
| VM | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .` | **164 OK** (10 pulados) |
| VM → Nuvem | `device_stage_files` (83 arquivos) ; `python3.11/3.12/3.13 -m unittest discover -s tests -t .` | **164 OK** em cada versão (10 pulados) |
| Nuvem | `pip download pytest` ; `curl https://pypi.org/simple/pytest/` | 403 — PyPI bloqueado pela política de rede (não repetido) |
| VM | `python3 -m appfactory guardrails status` ; `guard check-path` ; `audit verify` | I1 active, demais com pendências; `evolution_allowed: false`; códigos 0/3 corretos |
| VM | `git diff --check` ; busca de segredos ; `git status --short --ignored` | OK (valor fictício `AKIA…` passou a ser montado em tempo de execução) |

### Validação e commit da Fase 2.2 (usuário, PowerShell) — PENDENTE
```powershell
uv run pytest
uv run python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails
git add .
git commit -m "feat: add guardrails and execution security (Phase 2.2)"
git push
```

## 2026-09-27 — Fase 2.2: correção 8.3 e validação no Windows (base `683b9e2`, sem commit)

| Amb. | Comando | Resultado |
| --- | --- | --- |
| PS (usuário) | `uv run pytest` (1ª execução) | 156 passed, 7 skipped, 1 failed (`test_g22_07b_short_names_resolved`) |
| VM | `python3 - <<'EOF' … EOF` (edição de `src/appfactory/security/paths.py`: expansão de nomes 8.3) ; `PYTHONPATH=src python3 -m unittest discover -s tests -t .` | 164 OK (10 pulados) |
| PS (usuário) | `uv run pytest` | **157 passed, 7 skipped in 87.02s** (0 failed) — CPython 3.13.14 |
| PS (usuário) | `uv run python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails` | **21 passed, 7 skipped in 4.27s** (0 failed) |
| PS (usuário) | `git diff --check` | sem erro; aviso LF→CRLF em `tools/diagnostics/measure-hardware.ps1` |
| VM | `cat .venv/pyvenv.cfg` ; `ls .venv/Lib/site-packages` ; `ls tests/unit/__pycache__` | evidências: CPython 3.13.14, uv 0.12.12, pytest 9.1.1 |
| VM | `python3 - <<'EOF' … EOF` (TEST_STATUS, CP-0005, job.json, PROJECT_STATE, TASK_QUEUE, HANDOFF, CHANGELOG, COMMAND_LOG) ; `git diff --check` ; `git status --short` | consolidação documental; nenhum código/teste/configuração alterado |

### Commit da Fase 2.2 (usuário, PowerShell) — PENDENTE
```powershell
git add .
git commit -m "feat: add guardrails and execution security (Phase 2.2)"
git push
```

## 2026-09-27 — Validação pós-commit da Fase 2.2

| Amb. | Comando | Resultado |
| --- | --- | --- |
| PS (usuário) | `git add .` ; `git commit -m "feat: add guardrails and execution security (Phase 2.2)"` ; `git push` | `6fb983c` (informado pelo usuário; verificado abaixo) |
| VM | `git status -sb` ; `git log -3` ; `git show --stat HEAD` ; `git diff --check HEAD~1 HEAD` ; `git status --porcelain` ; `git ls-files` | limpo, sincronizado, `6fb983c`, 60 arquivos, sem problemas |
| Nuvem | `git ls-remote https://github.com/bielxleme/app-factory refs/heads/main` | `6fb983c161af6aa41b895ee65ded0ddbc216a577` |
| VM | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .` | 164 OK (10 pulados) |
| VM | `python3 - <<'EOF' … EOF` (CP-0005, job.json, PROJECT_STATE, TASK_QUEUE, HANDOFF, TEST_STATUS, CHANGELOG, COMMAND_LOG) | atualizados; nenhum código/teste/configuração alterado |

### Commit da consolidação (usuário, PowerShell) — PENDENTE
```powershell
git add .
git commit -m "chore: validate Phase 2.2 checkpoint"
git push
```

## 2026-09-27 — Fase 2.3: implementação (base `f44ac72`, sem commit)

| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .` (linha de base) | 164 OK (10 pulados) |
| VM | `cat > … <<'EOF'` / `python3 - <<'EOF' … EOF` (criação de `config/resources.yaml`, `src/appfactory/resources/**`, testes; edições aditivas em `cli/main.py`, `test_resource_limits.py`, `MANIFEST.json`, `test_repo_hygiene.py`) | ver D-0073 |
| VM | `python3 -m unittest tests.unit.test_resource_policy …` (por etapa: política, modos, contabilidade, admissão, sondas, CLI) | falhas de contagem de tempo nos próprios testes de histerese (limites t0 … t0+N) e de mesma raiz em dois gerentes corrigidas; depois OK |
| VM | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .` | **217 OK (10 pulados)** — Python 3.10.12 |
| VM | `PYTHONPATH=src:. python3 -m unittest discover -s tests/guardrails -t .` | **28 testes: 22 OK, 6 pulados** |
| VM | `af --root <tmp> resources snapshot/watch --count 3/admit --kind agent/compare` (raiz temporária) | JSON válido; Linux => CRITICAL (pior caso, esperado); `admit` => `WAIT` janela incompleta (código 3) |
| Nuvem | `git clone https://github.com/bielxleme/app-factory` (`f44ac72`) + arquivos da 2.3 copiados ; `python3.11/3.12/3.13 -m unittest discover -s tests -t .` | **217 OK (10 pulados)** em cada versão |
| VM | `git diff --check` ; `git diff --no-index --check /dev/null <novos>` | sem erro |

## 2026-09-27 — Fase 2.3: validação no Windows e correção D-0074 (sem commit)

| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | criação de `.appfactory/runtime/validate-2.3.ps1` (runtime, ignorado pelo Git) | script da validação |
| PS (usuário) | `powershell -ExecutionPolicy Bypass -File .appfactory\runtime\validate-2.3.ps1` (10:59–11:17): `uv run pytest` ; guardrails ; `git diff --check` ; `measure-hardware.ps1` ; `af resources compare` ; G23-27 (filtro e direto) ; `af resources snapshot` ; M1–M4 (`uv run af --json resources watch --count 180`, `mode`, `snapshot`) ; repetição de pytest, guardrails, `git diff --check`, `git status --short` | todos com código 0; ver `TEST_STATUS.md` (V2.3-01…08, matriz M1–M4) |
| VM | `python3` (análise dos arquivos de `validation-2.3/` e dos quatro `ki0017-M*.jsonl`) | defeito do critério de uso da GPU (valor instantâneo × média de 30 s) |
| VM | `python3 - <<'EOF' … EOF` (edição de `resources/modes.py` e `tests/unit/test_resource_modes.py`) ; `python3 -m unittest tests.unit.test_resource_modes` | 1ª versão do teste novo com erro de montagem (histórico inicial de 0% diluía a média); corrigido o teste; OK |
| VM | reprocessamento dos JSONL reais com o rastreador corrigido | M1 0→0, M2 62→91, M3 69→98, M4 16→38 amostras com `gpu_util`; modos finais iguais |
| VM | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .` ; guardrails ; `git diff --check` | 218 OK (10 pulados) ; 22 OK, 6 pulados ; sem erro |
| Nuvem | `python3.11/3.12/3.13 -m unittest discover -s tests -t .` (com `modes.py` e o teste copiados) | 218 OK (10 pulados) em cada versão |

## 2026-09-27 — Fase 2.3: rodada 2.3b e correção D-0075 (sem commit)

| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `mv -n ki0017-M{2,3,4}.jsonl ki0017-M{2,3,4}.run1.jsonl` ; criação de `.appfactory/runtime/validate-2.3b.ps1` | 1ª rodada preservada; script da revalidação |
| PS (usuário) | `powershell -ExecutionPolicy Bypass -File .appfactory\runtime\validate-2.3b.ps1` (11:35–12:47) | ver `TEST_STATUS.md` (V2.3-09…12, M2–M4) |
| VM | `python3` (análise de `validation-2.3b/` e `ki0017-M2/M3/M4.jsonl`) | M2 PASS; M3/M4 não conclusivos; `runtime_local` com timeout em 180/180 amostras de M2/M3 e intervalo real ~3,1 s |
| VM | edição de `resources/probes/runtime_local.py`, `probes/__init__.py`, `manager.py`, `tests/fakes/probes.py`, `tests/unit/test_probes.py`, `tests/integration/test_cli_resources.py` ; testes específicos | OK |
| VM | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t .` ; guardrails ; `git diff --check` | 223 OK (10 pulados) ; 22 OK, 6 pulados ; sem erro |
| Nuvem | `python3.11/3.12/3.13 -m unittest discover -s tests -t .` | 223 OK (10 pulados) em cada versão |

## 2026-09-27 — Fase 2.3: preparação da rodada 2.3c (sem commit)

| Amb. | Comando | Resultado |
| --- | --- | --- |
| VM | `UV_PROJECT_ENVIRONMENT=$HOME/.af-venv-linux uv run pytest -q` (e com `--python /usr/bin/python3.10`) | falhou: download do CPython 3.13 / pytest recusado pelo proxy da VM |
| VM | `git status --short` | deixou `.git/index.lock` (a VM não pode apagar arquivos da pasta conectada); movido com `mv -n` para `.git/index.lock.stale-vm-20260927` (arquivo vazio, ignorado pelo Git; pode ser apagado pelo usuário). Dali em diante: `GIT_OPTIONAL_LOCKS=0` |
| VM | `python3 -m unittest discover -s tests -t .` ; testes do Resource Manager ; guardrails ; `git diff --check` | 223 OK (10 pulados) ; 65 OK (1 pulado) ; 22 OK, 6 pulados ; sem erro |
| VM | `mv -n ki0017-M{3,4}.jsonl ki0017-M{3,4}.run2.jsonl` ; criação de `.appfactory/runtime/validate-2.3c.ps1` | rodada 2.3b preservada; script da rodada 2.3c |
