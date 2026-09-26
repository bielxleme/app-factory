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

### Commit da Fase 1 (usuário, PowerShell) — PENDENTE DE APROVAÇÃO
```powershell
git add .
git commit -m "docs: define App Factory architecture (Phase 1)"
git push
```
