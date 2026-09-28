# Runbook — Resource Manager (Fase 2.3)

Especificação: `docs/specs/fase-2.3-resource-manager.md` · Decisões: D-0058 a D-0073 · Normativo: `docs/architecture/05-resource-manager.md` (fonte canônica dos limiares) e `RESOURCE_POLICY.md` (tetos).

## O que existe nesta fase

- **Biblioteca somente de leitura e decisão** (`src/appfactory/resources/`, protegida): não pausa tasks, não descarrega modelos, não altera Windows, drivers, energia nem o Ollama. A atuação é do daemon (2.4) e do Model Router (2.5).
- **Política** `config/resources.yaml` (subconjunto JSON, protegida): esquema fechado (chave desconhecida é recusada; `mode_confirmations` não existe — D-0070), tetos do `RESOURCE_POLICY.md` e limiares nunca mais permissivos que os canônicos (D-0064; reserva de RAM de CONTENTION 3,0 GB — D-0072). Guardrail `I4.resources_config_within_ceilings` ativo.
- **Sondas** (somente biblioteca padrão, D-0058): Windows via `ctypes` (RAM/commit por `GlobalMemoryStatusEx` — D-0068); NVIDIA pela NVML (`nvml.dll` via `ctypes`), com `nvidia-smi` só como fallback isolado em `probes/nvidia.py`; Ollama só `GET /api/ps` (todo modelo conta como de terceiros até a 2.5 — D-0059); Linux mínima só para desenvolvimento (D-0067). Sonda que falha = **pior caso**.
- **Modos** com histerese por **tempo ativo contínuo de 10 s** (D-0069): lacuna > 5 s, troca de boot ou sono reiniciam a contagem. Ociosidade é leitura instantânea (D-0071). Saída de CRITICAL exige 60 s dentro dos limites **e** o STOP da fábrica liberado por `af resume-factory` (D-0062).
- **Admissão** (`GRANT`/`DENY`/`WAIT`) só como biblioteca e CLI (D-0060); lê **somente** o histórico do `watch` (D-0063).
- **Persistência só por eventos** na tabela `events` (D-0061): `resource.snapshot`, `resource.mode_changed`, `resource.admission_denied`, `resource.probe_failed`. Append-only, **sem retenção nem limpeza nesta fase** (cerca de 1 evento por segundo enquanto o `watch` roda).

## Comandos

Todos aceitam `--root <raiz>`; `--json` (antes de `resources`) muda a saída do `watch` para JSON por linha. Códigos: `0` ok · `3` negado/fora da tolerância · `2` erro.

| Comando | Para quê |
| --- | --- |
| `uv run af resources snapshot [--samples N]` | `ResourceSnapshot` (12 §7). Faz N leituras (padrão 2). Não grava nada. Médias de janela só aparecem se houver histórico do `watch`. |
| `uv run af resources watch [--interval S] [--count N]` | Amostra em primeiro plano (padrão 1 s = `sampling.interval_s`) e grava o histórico. Ctrl+C para parar. |
| `uv run af resources mode` | Modo pelo histórico do `watch` (com histerese). Sem histórico: modo instantâneo, avisado. |
| `uv run af resources admit --kind agent\|heavy\|gpu\|s2 [--tier T0\|T1\|T2 --est-vram-mib N --priority P]` | **Simulação**: nada é reservado. Sem histórico suficiente do `watch` responde `WAIT` ("janela incompleta"). |
| `uv run af resources compare --hardware-snapshot <arquivo>` | Compara com um snapshot de `tools/diagnostics/measure-hardware.ps1` (AC23-07). |

Para `admit` avaliar, deixe um `watch` rodando em outro terminal por pelo menos 60 s (janela de CPU) sem interrupção.

## Validação no Windows (AC23-01, AC23-02, AC23-07)

```powershell
cd D:\Claude\app-factory
uv run pytest
uv run python -m pytest -c tests/guardrails/pytest.ini --noconftest -p no:cacheprovider tests/guardrails
powershell -ExecutionPolicy Bypass -File tools\diagnostics\measure-hardware.ps1
uv run af resources compare --hardware-snapshot (Get-ChildItem .appfactory\runtime\hardware\snapshot-*.json | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
git diff --check
```

Esperado: `uv run pytest` sem falhas (7 pulados: 6 guardrails `pending` + a sonda Linux); guardrails sem falhas com 6 pulados; `compare` com código 0.

## Matriz KI-0017 (M1–M4; M5 na 2.5 — D-0066)

Em cada cenário, num terminal:

```powershell
uv run af --json resources watch --count 180 | Out-File -Encoding utf8 .appfactory\runtime\ki0017-M1.jsonl
```

(troque `M1` por `M2`, `M3`, `M4`). Em outro terminal, perto do fim: `uv run af resources mode` e `uv run af resources snapshot`.

| Cenário | O que fazer durante os 3 min | Modo esperado |
| --- | --- | --- |
| **M1** ocioso | não usar o computador (tomada ligada, nada em tela cheia) | FOREGROUND; BACKGROUND só após 10 min ocioso + 10 s |
| **M2** vídeo no navegador | vídeo tocando em janela normal; depois em tela cheia | janela normal: FOREGROUND (salvo uso alheio da GPU > 20%); tela cheia: CONTENTION após 10 s |
| **M3** jogo abrindo | abrir um jogo (launcher sozinho não conta) | CONTENTION (tela cheia/D3D, VRAM de terceiros > 1536 MiB ou +512 MiB em 30 s) |
| **M4** Ollama usado por outra ferramenta | gerar texto pelo OpenClaw (a fábrica não carrega modelos) | `vram_ollama_foreign_mib` > 0; CONTENTION se VRAM de terceiros > 1536 MiB |

Registrar em `TEST_STATUS.md`, para cada cenário: modo esperado × observado, `vram_foreign_mib`, `gpu.util_pct`, falhas de sonda e a calibração proposta de `vram_base` (hoje 105 MiB), `overhead_contexto` e `margem_medicao`. Mudar qualquer calibração exige decisão registrada (valores protegidos pelo I4).

## Observações da 1ª execução no Windows (2026-09-27)

- Com RAM disponível abaixo de 1,5 GB o modo é **CRITICAL**, que tem precedência sobre CONTENTION (05 §2); para sair é preciso RAM ≥ 2,5 GB por 60 s. Nessa execução M2–M4 ficaram em CRITICAL por RAM (0,19–1,66 GB disponíveis), e o modo esperado dos cenários não pôde ser observado. Para repetir M2–M4, comece com **pelo menos 3 GB de RAM disponível** (confira com `uv run af resources snapshot`), sem mudar nenhum critério.
- Em M4 o `/api/ps` não listou nenhum modelo nos 180 s (sem falha de sonda). Antes de repetir, confirme com `ollama ps`, durante a geração, que o OpenClaw usa um modelo **local** (não `*-cloud`, KI-0009).

## Limitações desta fase

- Sem daemon: nada é amostrado se o `watch` não estiver rodando; o limite "1 admissão por minuto" e os contadores de agentes/pesados/lease de GPU existem só na memória do processo (entre processos, na 2.4).
- Admissão não é consultada pelo Job Manager (integração na 2.4, D-0060); tabelas `resource_samples`/`resource_decisions` na 2.4 (D-0061).
- Sem registro de posse de modelos (2.5): todo modelo do Ollama é de terceiros.
- Na VM Linux, GPU/energia/tela cheia não existem: o modo é sempre CRITICAL (pior caso) — esperado.
