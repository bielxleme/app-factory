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

### Commit e push (usuário, WSL) — PENDENTE
```bash
cd /mnt/d/Claude/app-factory
git remote -v
git add .
git commit -m "chore: initialize App Factory"
git push -u origin main
git status
git log --oneline -1
```
