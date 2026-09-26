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
