# 00 — Visão geral

## 1. Princípios (em ordem de prioridade)

1. **Segurança e reversibilidade antes de velocidade.** Toda ação com efeito colateral é registrada, autorizada conforme risco e reversível sempre que possível.
2. **O computador é do usuário.** A App Factory trabalha em segundo plano e cede recursos quando o usuário está ativo.
3. **Nada se perde.** Estado durável em disco (SQLite + arquivos). Qualquer processo pode morrer a qualquer momento.
4. **Zero gasto automático.** Nenhum provedor pago é usado sem configuração explícita **e** aprovação humana.
5. **Local primeiro, externo por escolha.** Ollama é o provedor padrão; externos são plugáveis e substituíveis.
6. **Sem dependência de um fornecedor.** Todo modelo/provedor/ferramenta fica atrás de uma interface.
7. **Continuidade entre IAs.** O estado é legível por humanos (Markdown/JSON) para que outra IA retome o trabalho.
8. **Simplicidade operacional.** Um único processo supervisor, SQLite em vez de servidores de fila, sem serviços extras obrigatórios.

## 2. Baseline de hardware (medido em 2026-09-26 16:17 -03:00)

| Recurso | Valor medido | Implicação arquitetural |
| --- | --- | --- |
| Máquina | Acer Nitro ANV15-51, Windows 11 Home 26200 | Execução nativa no Windows; sem recursos de Windows Pro (Hyper-V/Sandbox) |
| CPU | i5-13420H — 8 núcleos (4P+4E), 12 threads, uso médio 16,8% | Agentes são I/O-bound; limite por slots, não por núcleos |
| RAM | 23,71 GB visíveis; **5,2 GB disponíveis** (78% em uso com Chrome/Word/Norton) | **RAM é o gargalo principal** com o usuário ativo |
| GPU | RTX 4050 Laptop, 6141 MiB; 105 MiB usados; 0%; 46 °C; P8; limite 62 W | **1 modelo local por vez** na GPU; contexto limitado |
| Disco | C: 32,9 GB livres de 475,7 · D: 177,8 GB livres de 465,7 (ambos NVMe) | Todos os dados da fábrica em D:; C: é crítico |
| Energia | Com bateria; na tomada (79%) | Modo BATTERY obrigatório |
| Temperatura | GPU via `nvidia-smi`; CPU **indisponível** sem administrador | Política térmica só para GPU |
| Ollama | 0.34.4, API em 127.0.0.1:11434, nenhum modelo carregado, sem variáveis `OLLAMA_*` | Provedor local padrão |
| Docker | Docker Desktop 29.8.0 (engine respondeu) | Sandbox forte opcional, sob demanda |
| WSL2 | OpenClawGateway (padrão), Ubuntu, docker-desktop — todos Stopped | **Não usado** pela fábrica (D-0010) |

## 3. Topologia de processos

```
Windows (host)
 |
 +-- afd  (App Factory Daemon, Python, 1 processo, prioridade BELOW_NORMAL)
 |     |- API local  127.0.0.1:<porta>  (token local)      <- CLI "af" / UI futura
 |     |- Job Manager + Scheduler
 |     |- Resource Manager (amostragem 5 s)
 |     |- Model Router + Provider Router
 |     |- Event Bus (em memória) + Event Store (SQLite)
 |     |- Checkpoint / Logging / Handoff services
 |     `- Approval Gate
 |
 +-- agent-runner (subprocesso por task; 0..N conforme política)
 |     `- executa UM agente (Coder, QA, ...) com TaskSpec + ContextPack
 |
 +-- heavy processes (builds, testes, Playwright, containers) — lançados via Toolbox
 |
 +-- Ollama (serviço existente do usuário) — gerido só via API
 `-- Docker Desktop (opcional, iniciado sob demanda para sandbox S2)
```

Todo acesso a modelos, ferramentas perigosas e recursos passa pelo **daemon**. Agentes nunca chamam provedores diretamente: pedem ao daemon (que mede, limita, registra e aplica política).

## 4. Modelo de dados em uma frase

**SQLite (`.appfactory/state/factory.db`, WAL) é a fonte da verdade**; arquivos em `.appfactory/jobs/<job>/` guardam artefatos, contextos e checkpoints de task; os Markdown da raiz (`PROJECT_STATE.md`, `HANDOFF.md` etc.) são **visões humanas** geradas/atualizadas pelo Handoff System.

## 5. Fábrica x projetos gerados

- **Repositório da fábrica:** `D:\Claude\app-factory` (este repo).
- **Projetos gerados:** `D:\Claude\app-factory\workspaces\<projeto>\` — cada um é **um repositório Git próprio**, ignorado pelo Git da fábrica.
- **Worktrees de agentes:** `D:\Claude\app-factory\workspaces\_worktrees\<projeto>\<task>\`.
