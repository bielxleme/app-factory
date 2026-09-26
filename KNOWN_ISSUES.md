# KNOWN_ISSUES.md — Problemas e limitações conhecidos

## KI-0001 · Aberto · Shell do Claude não é o WSL do usuário
- **Descrição:** o shell que o Claude (Cowork) usa no PC é uma VM Linux isolada (Ubuntu 22.04.5, git 2.34.1), com `D:\Claude` montado via FUSE. Não há `wsl.exe` nem acesso ao WSL, à configuração Git ou às credenciais do usuário.
- **Impacto:** WSL, distro do WSL e `git config` do usuário não puderam ser verificados pelo Claude; commit/push feitos pelo usuário.
- **Contorno:** o usuário executa os comandos de Git no WSL e devolve a saída.

## KI-0002 · Aberto · GitHub bloqueado no shell local do Claude
- **Descrição:** `git ls-remote https://github.com/bielxleme/app-factory` na VM local → `Received HTTP code 403 from proxy after CONNECT` (política de rede da sessão).
- **Impacto:** push não é possível a partir da VM.
- **Contorno:** leitura verificada a partir do ambiente de nuvem do Claude (sem credenciais de escrita); push pelo usuário no WSL.

## KI-0003 · Resolvido · Arquivos temporários do git deixados em `.git/`
- **Descrição:** após `git init`/`git status` na VM, ficaram `.git/index.lock` e `.git/tU1XehK` (vazios), porque a montagem não permitia apagar arquivos.
- **Solução:** com autorização do usuário para exclusão, ambos foram removidos com `rm -v` (2026-09-26). O `index.lock` teria travado o git no WSL.

## KI-0004 · Observação · Hardware não verificado integralmente
- **Descrição:** a VM enxerga o modelo da CPU (i5-13420H, confirmado), mas só 2 vCPUs e ~4 GB de RAM (limites da VM). RAM total, GPU e VRAM do host não puderam ser verificadas.
- **Ação sugerida:** na Fase 1, rodar no Windows/WSL `nvidia-smi`, `free -h` e `nproc` e atualizar `RESOURCE_POLICY.md`.

## KI-0005 · Possível · "dubious ownership" no WSL
- **Descrição:** o `.git` foi criado pela VM do Cowork. Se o git do WSL recusar o repositório com "detected dubious ownership", rode:
  `git config --global --add safe.directory /mnt/d/Claude/app-factory` (altera a config global do usuário; só se necessário).
