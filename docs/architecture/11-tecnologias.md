# 11 — Tecnologias (J)

Critérios: gratuito → open source → local → multiplataforma → modular → substituível. Todas as escolhas abaixo são **gratuitas**. Licenças e versões devem ser reconfirmadas na Fase 2 antes de fixar no lockfile.

| Tecnologia | Por que | Alternativa | Custo | Impacto no computador | Dependências | Riscos | Substituição |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Python 3.13** (medido: 3.13.14 instalado) | Ecossistema de IA/automação, já instalado, multiplataforma | Node/TypeScript; Go | 0 | Daemon ~80–150 MB RAM | — | GIL limita CPU-bound (não é o nosso caso: I/O-bound) | Alta: agentes falam por API/processos |
| **uv** (medido: 0.12.12) | Ambientes e lock rápidos e reproduzíveis; gerencia a versão do Python | pip+venv; Poetry | 0 | Desprezível; cache em disco | — | Ferramenta jovem | Alta (`pyproject.toml` é padrão) |
| **SQLite (WAL)** + `sqlite3` da stdlib | Fonte da verdade transacional sem servidor; arquivo único; backup simples | PostgreSQL; Redis | 0 | ~0 RAM extra; arquivo em D: | nenhuma | Escrita concorrente limitada (1 escritor): ok para 1 máquina | Média: camada de repositório isola o SQL |
| **Pydantic v2** | Contratos tipados (TaskSpec, eventos) + validação + JSON Schema | dataclasses + jsonschema | 0 | Baixo | — | Mudanças de API entre majors | Alta |
| **FastAPI + Uvicorn** (só 127.0.0.1) | API local para CLI/UI/runners; gera OpenAPI | aiohttp; JSON-RPC via stdio | 0 | ~30–60 MB | Starlette | Exposição de rede → mitigado: bind em localhost + token | Alta |
| **Typer** | CLI `af` | argparse; Click | 0 | Desprezível | Click | — | Alta |
| **httpx** | Cliente HTTP assíncrono para provedores | aiohttp; requests | 0 | Baixo | — | — | Alta |
| **psutil** | CPU/RAM/processos/bateria/disco multiplataforma | WMI puro; `/proc` | 0 | Desprezível | — | — | Alta |
| **nvidia-ml-py (NVML)** + fallback `nvidia-smi` (medido: driver 617.14) | Métricas da GPU sem abrir processo a cada 5 s | só `nvidia-smi` | 0 | Desprezível | Driver NVIDIA | Sem suporte a GPU não NVIDIA → sonda desativa GPU | Alta (interface `GpuProbe`) |
| **Ollama** (medido: 0.34.4) | Já instalado, API HTTP simples, gerencia load/unload e `keep_alive` | llama.cpp server; LM Studio; vLLM (não cabe em 6 GB) | 0 | Modelos no C: (KI-0008); VRAM conforme modelo | Driver/CUDA | Modelos `*-cloud` são externos (KI-0009) | Alta (adaptador `Provider`) |
| **Adaptador OpenAI-compatível** próprio | Uma interface para vários provedores externos sem SDK de fornecedor | LiteLLM | 0 | Desprezível | httpx | Diferenças sutis entre APIs | Alta |
| **Orquestrador próprio** (sem framework de agentes) | Controle total de estados, recursos e segurança; sem acoplamento | LangGraph; CrewAI; AutoGen | 0 | Baixo | — | Mais código para manter | Média: contratos em `12-contratos.md` permitem trocar |
| **Git + worktrees** (medido: 2.54.0 Windows) | Isolamento de agentes, checkpoints e rollback nativos | cópias de diretório | 0 | Disco por worktree (em D:) | — | Caminhos longos no Windows → `core.longpaths=true` no repo do projeto | Baixa (fundamental) |
| **Docker Desktop** (medido: 29.8.0) para sandbox S2 | Único isolamento forte disponível no Windows Home | Podman Desktop; WSL2 dedicado | 0 para uso pessoal (reconfirmar os termos atuais) | **1–4 GB de RAM** com a VM ativa → iniciado só sob demanda | WSL2 | Consumo de RAM; termos de licença | Média (interface `Sandbox`) |
| **Playwright (Chromium)** | E2E, screenshots, páginas dinâmicas; perfil isolado | Selenium; Puppeteer | 0 | 300–600 MB por navegador; ~500 MB de download | Node ou Python | Sites anti-bot (não contornar) | Alta |
| **pytest / ruff** | Testes e lint rápidos | unittest; flake8+black | 0 | Baixo | — | — | Alta |
| **keyring** → Windows Credential Manager | Segredos fora de arquivos | `.env` local; cofre externo | 0 | — | — | Acesso por outros processos do mesmo usuário | Alta (interface `SecretStore`) |
| **gitleaks, pip-audit, npm audit, bandit** | Portão de segurança | Semgrep; Trivy | 0 | Baixo, sob demanda | Binário (gitleaks) | Falsos positivos | Alta |
| **`logging` (stdlib) + JSONL próprio** | Sem dependência; formato universal | structlog; loguru | 0 | Desprezível | — | — | Alta |
| **Node.js** (medido: v26.10.0 / npm 11.19.1) | Para apps web/JS gerados e ferramentas JS | Bun; Deno | 0 | Sob demanda | — | Versão ímpar/par: fixar por projeto | Alta |
| **ComfyUI** (futuro, Media Engine) | Geração de imagem local open source | Diffusers direto; provedores externos | 0 | Ocupa quase toda a VRAM → só BACKGROUND | CUDA, PyTorch (~vários GB em D:) | Peso de instalação; licenças dos modelos | Alta (interface `MediaBackend`) |
| **Job Objects do Windows** (via `pywin32` ou `ctypes`) — revisão 1.1 | Limite de memória/CPU/processos e `KILL_ON_JOB_CLOSE` para runners e S1h | só monitorar com psutil | 0 | Desprezível | Windows 8+ (jobs aninhados) | Comportamento com logon secundário a provar (KI-0014) | Média (interface `Sandbox`) |
| **Usuário local dedicado + logon secundário** (`CreateProcessWithLogonW`) + **ACLs NTFS** — revisão 1.1 | Isolar código não confiável sem Windows Pro/Hyper-V | só S2 (Docker); AppContainer | 0 | Desprezível | Serviço "Logon secundário" ativo; criação da conta pelo usuário | Configuração de ACL errada; sem isolamento de rede (KI-0015/0016) | Média |
| **Agendador de Tarefas** (tarefa de logon) — revisão 1.1 | Iniciar o daemon no logon sem virar serviço e sem admin | serviço do Windows; atalho na pasta Inicializar | 0 | Nenhum | — | Tarefa desabilitada por políticas/antivírus | Alta |
| **`QueryUnbiasedInterruptTime` / `SHQueryUserNotificationState`** (Win32 via `ctypes`) — revisão 1.1 | Tempo ativo sem suspensão para leases; detecção de tela cheia/D3D | relógio de parede; só ociosidade | 0 | Nenhum | — | APIs só do Windows (isoladas em `probes/windows.py`) | Alta |
| **SQLite FTS5** (+ `sqlite-vec` futuro) | Busca em memória/código sem servidor | Chroma; Qdrant | 0 | Baixo | — | Qualidade da busca semântica depende do modelo de embedding | Alta |

**Serviços deliberadamente evitados:** Redis, Celery, RabbitMQ, Kubernetes, bancos em servidor para a fábrica. Motivo: consumo de RAM e complexidade numa máquina com ~5 GB livres durante o uso normal.
