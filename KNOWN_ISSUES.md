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
- **Fase 1.1:** registrada como decisão futura (D-0034). Nada foi alterado.

## KI-0009 · Aberto · `qwen3-coder:latest` e `qwen3-coder:480b-cloud` com o mesmo ID
- **Descrição:** `ollama list` mostra os dois com ID `57874a6e9034` e 5,2 GB. Não se sabe se o `latest` é um modelo local ou um alias do modelo de nuvem.
- **Ação:** na Fase 2, rodar `ollama show qwen3-coder:latest` e medir com `/api/ps`. Até lá, os dois são tratados como **externos** (privacidade externa).
- **Fase 1.1:** classe formal **CLOUD** até verificação real com o usuário (D-0033, fatia 2.5). Nenhuma suposição por nome ou tamanho.

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

## KI-0014 · Aberto (a validar na Fase 2) · Logon secundário + Job Object no Windows 11 Home
- **Descrição:** o S1h (D-0026) depende de lançar processos como `afrunner` via `CreateProcessWithLogonW`, suspensos, e atribuí-los a um Job Object aninhado com `KILL_ON_JOB_CLOSE`. A interação entre o serviço de logon secundário e Job Objects precisa ser provada nesta máquina.
- **Ação:** prova de conceito na fatia 2.6 (`15-daemon.md` §10). Se inviável, registrar decisão de usar só S2 para código não confiável.

## KI-0015 · Risco aceito · S1h não isola rede
- **Descrição:** o Windows Home não oferece bloqueio de rede confiável por usuário. Código em S1h pode acessar a rede.
- **Mitigação:** S1h não tem segredos, token nem acesso a áreas protegidas; tasks que exigem isolamento de rede vão obrigatoriamente para S2.

## KI-0016 · Aberto (a validar no setup) · ACL padrão do disco D:
- **Descrição:** em discos NTFS secundários, a ACL padrão costuma dar "Usuários autenticados: Modificar" na raiz. Sem ajuste, `afrunner` poderia escrever fora do worktree.
- **Ação:** no setup da fatia 2.6 (feito pelo usuário, R3), aplicar Deny herdado para `afrunner` a partir de `D:\Claude\app-factory` (e de outras pastas que o usuário indicar) e verificar com teste real. Nada foi alterado na Fase 1.1.

## KI-0017 · Aberto (a validar na fatia 2.3) · Heurísticas de uso da GPU por terceiros
- **Descrição:** a contabilidade de VRAM por diferença, a janela de observação e as heurísticas de tela cheia/processos (05 §1.1) são estimativas.
- **Ação:** executar a matriz de validação (ocioso, vídeo, jogo, Ollama usado por outra ferramenta, inferência + jogo) e calibrar `overhead_contexto`, `vram_base` e `margem_medicao`.

## KI-0018 · Resolvido (2026-09-26) · Caminhos Windows do código não executados em Windows
- **Descrição:** `core/clock.py` (`QueryUnbiasedInterruptTime`, `NtQuerySystemInformation`) e `core/procinfo.py` (`OpenProcess`, `GetProcessTimes`, `GetExitCodeProcess`) só foram verificados por leitura; os testes rodaram em Linux (VM do Cowork, Python 3.10; nuvem, Python 3.11–3.13). O pytest em si não pôde ser executado (PyPI bloqueado nos dois ambientes); os testes são `unittest` compatíveis com pytest.
- **Ação:** rodar `uv run pytest` no Windows (PowerShell) e registrar o resultado em `TEST_STATUS.md`. Em caso de erro nessas funções, o comportamento previsto é conservador (processo considerado vivo → recuperação mais lenta, nunca execução duplicada).
- **Solução:** `uv run pytest` executado no Windows pelo usuário: 58 testes passaram (CPython 3.13.14, pytest 9.1.1), incluindo os testes de integração que usam o relógio e a identidade de processos reais. Registrado em `TEST_STATUS.md` (V2.1-01). Suspensão/hibernação real do notebook continua sem teste automatizado (previsto na 2.4).

## KI-0019 · Limitação (até a 2.4) · Sem daemon nem Job Objects
- **Descrição:** a recuperação só acontece com `af recover` (ou ao tentar executar o job); um processo mudo perde a posse por *fencing*, mas não é encerrado; `STOPPING` com executor morto só vira `STOPPED` na recuperação.
- **Ação:** fatia 2.4 (daemon, Job Object raiz, recuperação automática na partida).

## KI-0020 · Limitação (até a 2.4) · Escritor único transitório
- **Descrição:** vários processos (CLI/executores) escrevem no SQLite, serializados por `BEGIN IMMEDIATE` (D-0043), em vez de só o daemon (D-0037).
- **Ação:** fatia 2.4.
