# KNOWN_ISSUES.md — Problemas e limitações conhecidos

## KI-0001 · Aberto (contornado) · Shell do Claude não é o WSL do usuário
- **Descrição:** o shell que o Claude (Cowork) usa no PC é uma VM Linux isolada (Ubuntu 22.04.5, git 2.34.1), com `D:\Claude` montado via FUSE. Não há `wsl.exe` nem acesso ao WSL, à configuração Git ou às credenciais do usuário.
- **Impacto:** WSL, distro do WSL e `git config` do usuário não puderam ser verificados pelo Claude; commit/push feitos pelo usuário.
- **Contorno:** o usuário executa commit/push com Git para Windows (PowerShell) e informa o resultado (D-0010).

## KI-0002 · Aberto (contornado) · GitHub bloqueado no shell local do Claude
- **Descrição:** `git ls-remote https://github.com/bielxleme/app-factory` na VM local → `Received HTTP code 403 from proxy after CONNECT` (política de rede da sessão).
- **Impacto:** push não é possível a partir da VM.
- **Contorno:** leitura verificada a partir do ambiente de nuvem do Claude (sem credenciais de escrita); push pelo usuário no WSL.

## KI-0003 · Resolvido · Arquivos temporários do git deixados em `.git/`
- **Descrição:** após `git init`/`git status` na VM, ficaram `.git/index.lock` e `.git/tU1XehK` (vazios), porque a montagem não permitia apagar arquivos.
- **Solução:** com autorização do usuário para exclusão, ambos foram removidos com `rm -v` (2026-09-26). O `index.lock` teria travado o git no WSL.

## KI-0004 · Resolvido (2026-09-26) · Hardware não verificado integralmente
- **Descrição:** a VM enxerga o modelo da CPU (i5-13420H, confirmado), mas só 2 vCPUs e ~4 GB de RAM (limites da VM). RAM total, GPU e VRAM do host não puderam ser verificadas.
- **Ação sugerida:** na Fase 1, rodar no Windows/WSL `nvidia-smi`, `free -h` e `nproc` e atualizar `RESOURCE_POLICY.md`.
- **Solução:** medido no Windows com `tools/diagnostics/measure-hardware.ps1` (Fase 1). Valores em `RESOURCE_POLICY.md` §1.

## KI-0005 · Não ocorreu · "dubious ownership" no WSL
- **Descrição:** o `.git` foi criado pela VM do Cowork. Se o git do WSL recusar o repositório com "detected dubious ownership", rode:
  `git config --global --add safe.directory /mnt/d/Claude/app-factory` (altera a config global do usuário; só se necessário).
- **Resultado (2026-09-26):** o commit foi feito via PowerShell sem erro; nenhuma alteração de configuração global foi necessária.

## KI-0006 · Observação · Commit/push executados fora do ambiente do Claude
- **Descrição:** o commit `5aa9709` e o push foram executados pelo usuário no PowerShell. O Claude verificou o resultado de forma independente (`git log`, `git rev-parse main origin/main`, `git status` na VM e `git ls-remote` na nuvem), mas não viu a saída original do `git push`.
- **Impacto:** nenhum — estado local e remoto coincidem em `5aa9709`.

## KI-0007 · Aberto · RAM livre baixa durante o uso normal
- **Descrição:** medição de 2026-09-26: 5,2 GB disponíveis de 23,71 GB (78% em uso) com Chrome, Word, Norton etc. abertos.
- **Impacto:** com o usuário ativo, a fábrica fica limitada a 2 agentes e a modelos T0/T1 na GPU; offload para a CPU é proibido.
- **Mitigação:** modos do Resource Manager (D-0018). Remedir em outros momentos (ocioso) na Fase 2.

## KI-0008 · Aberto · Pouco espaço no C: e modelos do Ollama no C:
- **Descrição:** C: com 32,9 GB livres. Nenhuma `OLLAMA_MODELS` definida → modelos no perfil do usuário no C: (os tamanhos listados por `ollama list` somam ~22,7 GB; dois modelos têm o mesmo ID, então o uso real deve ser menor).
- **Impacto:** baixar novos modelos pode esgotar o C:.
- **Ação (decisão do usuário):** definir `OLLAMA_MODELS` em D: e mover os modelos. A fábrica não faz isso sozinha.

## KI-0009 · Aberto · `qwen3-coder:latest` e `qwen3-coder:480b-cloud` com o mesmo ID
- **Descrição:** `ollama list` mostra os dois com ID `57874a6e9034` e 5,2 GB. Não se sabe se o `latest` é um modelo local ou um alias do modelo de nuvem.
- **Ação:** na Fase 2, rodar `ollama show qwen3-coder:latest` e medir com `/api/ps`. Até lá, os dois são tratados como **externos** (privacidade externa).

## KI-0010 · Limitação · Temperatura da CPU indisponível
- **Descrição:** `MSAcpi_ThermalZoneTemperature` volta vazio sem administrador.
- **Impacto:** a política térmica usa só a GPU (`nvidia-smi`). CPU é protegida por limites de uso.

## KI-0011 · Observação · Estado do Docker/WSL a confirmar
- **Descrição:** `docker info` respondeu (Docker Desktop 29.8.0), mas `wsl -l -v` mostrou `docker-desktop` como Stopped. Pode ser só o momento da medição.
- **Ação:** confirmar na fatia de sandbox (Fase 2). Até lá, S2 é considerado "disponível sob demanda, não garantido".

## KI-0012 · Observação · Antivírus e caminhos de ferramentas
- **Descrição:** Norton está ativo (pode deixar operações com muitos arquivos, como `npm install` e builds, mais lentas). O `git` do PATH vem de `AppData\Local\hermes\git` e o `python` do PATH é o alias do WindowsApps (o `py` aponta para `Python313`).
- **Ação:** a fábrica usará Python gerenciado pelo `uv` (fixado no projeto) e registrará os caminhos absolutos das ferramentas na configuração da Fase 2. Exclusões no antivírus são decisão do usuário.

## KI-0013 · Resolvido · Título vazio no CHANGELOG
- **Descrição:** a edição da Fase 0 deixou um título "Commit inicial `5aa9709`" sem conteúdo.
- **Solução:** corrigido na Fase 1.
