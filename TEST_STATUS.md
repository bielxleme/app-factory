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
