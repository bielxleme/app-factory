# TEST_STATUS.md — Testes e verificações

Ambientes: **VM** = shell local do Cowork (Ubuntu 22.04.5, isolado) · **Nuvem** = ambiente de nuvem do Claude · **WSL** = WSL do usuário.

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
| V14 | Primeiro commit | WSL | PENDENTE |
| V15 | Push | WSL | PENDENTE |
| V16 | Sincronização local/remoto | WSL + Nuvem | PENDENTE |
