# 05 — Resource Manager (D)

**Revisão 1.1 (2026-09-26):** medição de GPU corrigida para Windows/WDDM (§1.1, N4), limiares de CPU e BATTERY unificados (§3–§4, N7), modelos de terceiros no Ollama (§5, N5). Decisões D-0032, D-0033, D-0038. **Este documento é a fonte canônica dos limiares**; os demais apenas o referenciam.

**Revisão 1.2 (2026-09-27):** fontes das sondas (§1) alinhadas a D-0058 e D-0068 — somente biblioteca padrão (`ctypes`), NVML via `nvml.dll` no caminho principal, `nvidia-smi` só como fallback isolado em `resources/probes/nvidia.py`; saída do modo CRITICAL corrigida (§2) — exige o STOP da fábrica liberado; apagar o arquivo `.appfactory/STOP` nunca libera (D-0028, D-0062); histerese de 10 s contínuos por tempo ativo (§2; D-0069, D-0070); ociosidade instantânea (D-0071); `sampling.interval_s: 1` e reserva de RAM de CONTENTION 3,0 GB no exemplo de §9 (D-0070, D-0072).

Diagrama: `13-diagramas.md` §4. Valores de referência do hardware medido: RAM 23,71 GB (5,2 GB livres no uso normal), VRAM 6141 MiB, 12 threads, C: 32,9 GB livres, D: 177,8 GB livres.

## 1. Sondas e frequência

| Métrica | Fonte | Frequência | Janela de decisão |
| --- | --- | --- | --- |
| CPU % total | Win32 `GetSystemTimes` (`ctypes`) | 5 s | média de 60 s |
| RAM disponível | Win32 `GlobalMemoryStatusEx` (`ctypes`) | 5 s | mínimo de 30 s |
| Commit livre | Win32 `GlobalMemoryStatusEx` (`ullAvailPageFile`, `ctypes`; D-0068) | 30 s | valor atual |
| GPU % total, VRAM usada/livre **total**, temperatura, potência | NVML via `nvml.dll` + `ctypes` (caminho principal); fallback `nvidia-smi --query-gpu` **somente** em `resources/probes/nvidia.py` (D-0058) | 5 s (1 s nas janelas de observação, §1.1) | média de 30 s |
| Processos na GPU (nomes/PIDs; **sem VRAM por processo**) | NVML (processos de computação/gráficos) | 15 s | valor atual |
| Tela cheia / modo apresentação / D3D exclusivo | Win32 `SHQueryUserNotificationState` | 5 s | valor atual |
| Modelos carregados | Ollama `/api/ps` | 15 s e após load/unload | valor atual |
| Ociosidade do usuário | Win32 `GetLastInputInfo` | 5 s | valor atual |
| Energia / bateria | Win32 `GetSystemPowerStatus` (`ctypes`) | 30 s | valor atual |
| Disco livre (C:, D:) | Win32 `GetDiskFreeSpaceExW` (`ctypes`) | 60 s | valor atual |
| Temperatura da CPU | **Indisponível** (WMI exige administrador; medido: vazio) | — | — |

Falha de uma sonda → assume o **pior caso** daquele recurso e registra `resource.probe_failed`.

## 1.1 GPU no Windows (WDDM) — como medir sem VRAM por processo

**Fato medido (2026-09-26):** `nvidia-smi --query-compute-apps` devolveu `used_memory = [N/A]` para todos os processos. No modo WDDM o driver **não** informa VRAM por processo. A arquitetura não pode depender disso.

| Grandeza | Definição |
| --- | --- |
| `vram_used_total` | VRAM usada no total (NVML) |
| `vram_factory` | soma de `size_vram` (runtime local, ex.: Ollama `/api/ps`) dos modelos **carregados pela fábrica** segundo o registro de posse (06 §2.1) + `overhead_contexto` por modelo (inicial 300 MiB, calibrar) |
| `vram_ollama_terceiros` | soma de `size_vram` dos modelos presentes no `/api/ps` que **não** são da fábrica (carregados por outras ferramentas, ex.: OpenClaw) |
| `vram_base` | consumo do sistema com tudo ocioso (medido: 105 MiB); recalibrado quando a GPU estiver ociosa |
| `vram_outros` | `max(0, vram_used_total − vram_factory − vram_ollama_terceiros − vram_base)` |
| **`vram_terceiros`** | `vram_ollama_terceiros + vram_outros` |
| **`margem_medicao`** | 512 MiB (erro de estimativa + contexto CUDA não contabilizado); calibrável, nunca abaixo de 256 MiB |
| **VRAM disponível para a fábrica** | `vram_total − vram_used_total − reserva_vram[modo] − margem_medicao` |

**Uso da GPU por terceiros durante inferência da fábrica:** enquanto a fábrica tem chamada em andamento, o `% de uso` total é dela e não pode ser atribuído a ninguém. Regras:

1. O critério de **uso** (`> 20%`) só é avaliado em amostras **sem chamada da fábrica em andamento**.
2. Em FOREGROUND e CONTENTION, o lease de GPU tem **janela de observação** de 2 s entre chamadas consecutivas (amostras de 1 s) para medir o uso alheio.
3. Se a fábrica ficar mais de 60 s em inferência contínua, valem só os critérios de VRAM e as heurísticas abaixo até a próxima janela.

**Heurísticas de jogos/apps gráficos** (qualquer uma dispara CONTENTION):

- `SHQueryUserNotificationState` = D3D em tela cheia exclusiva, modo apresentação ou "ocupado" (tela cheia);
- processo em execução presente em `gpu.contention_processes` (lista configurável; ex.: executáveis de jogos) — launchers (Epic, Steam) ficam em `gpu.benign_processes` e **não** disparam sozinhos;
- `vram_terceiros` > 1536 MiB;
- crescimento de `vram_terceiros` > 512 MiB em 30 s.

**Validação futura (fatia 2.3, KI-0017):** matriz de testes — ocioso; vídeo no navegador; jogo abrindo; Ollama usado pelo OpenClaw; inferência da fábrica + jogo. Verificar se NVML expõe utilização por processo nesta máquina; calibrar `overhead_contexto`, `vram_base` e `margem_medicao`.

## 2. Modos (avaliados em ordem; o primeiro que casar vence)

| Ordem | Modo | Condição de entrada | Condição de saída (histerese) |
| --- | --- | --- | --- |
| 1 | **CRITICAL** | RAM disponível < 1,5 GB **ou** temp. GPU ≥ 87 °C **ou** disco de trabalho (D:) < 5 GB **ou** kill switch `.appfactory/STOP` | RAM ≥ 2,5 GB **e** GPU ≤ 80 °C **e** disco ≥ 10 GB por 60 s **e** STOP da fábrica liberado (`factory_stop` inativo, só por `af resume-factory` — D-0028, D-0062); apagar `.appfactory/STOP` **não** faz sair de CRITICAL |
| 2 | **BATTERY** | Sem energia da tomada | Tomada por 60 s |
| 3 | **CONTENTION** | Qualquer critério de §1.1: uso alheio > 20% (só em amostras sem inferência da fábrica) **ou** `vram_terceiros` > 1536 MiB **ou** crescimento rápido de `vram_terceiros` **ou** tela cheia/D3D exclusivo **ou** processo em `contention_processes` | Condição ausente por 120 s |
| 4 | **BACKGROUND** | Usuário ocioso ≥ 10 min | Qualquer entrada do usuário → FOREGROUND imediato |
| 5 | **FOREGROUND** | Padrão (usuário ativo) | — |

Mudança de modo só vale após a condição do novo modo ficar satisfeita de forma **contínua por 10 s** de tempo ativo (regra fixa, não configurável; D-0069, D-0070), exceto: entrada em CRITICAL e volta do usuário (imediatas). A ociosidade é leitura instantânea (§1; D-0071).

## 3. Política por modo

| Aspecto | FOREGROUND | BACKGROUND | BATTERY | CONTENTION | CRITICAL |
| --- | --- | --- | --- | --- | --- |
| Agentes simultâneos | 2 | 4 | 1 | 2 | 0 novos; pausa os pesados |
| Tiers locais permitidos na GPU | T0, T1 | T0, T1, T2 | nenhum (T0 na CPU permitido) | nenhum | nenhum (descarrega **os modelos da fábrica**) |
| `keep_alive` dos modelos | 2 min | 10 min | 0 | 0 (descarrega) | 0 |
| Offload de modelo para a CPU (camadas fora da GPU) | **proibido** | permitido até 4 GB de RAM | proibido | proibido | proibido |
| Processos pesados | 1 | 2 | 0 (ficam em WAITING) | 1 (sem GPU) | 0 |
| Prioridade de processo | BELOW_NORMAL | BELOW_NORMAL | IDLE | BELOW_NORMAL | — |
| Provedores externos gratuitos já consentidos | sim | sim | sim | sim (preferidos) | não |
| Jobs P3 (evolução/manutenção) | não | sim | não | não | não |
| Bateria < 30% (dentro de BATTERY) | — | — | pausa tudo exceto P0 (com checkpoint) | — | — |
| Tasks em execução ao entrar no modo | continuam | continuam | **continuam** dentro do limite de 1 agente (as excedentes vão para `WAITING(resources)` em fronteira de passo); **só vão para `PAUSED` se a bateria < 30%** | GPU liberada; tasks locais de GPU → `WAITING(resources)` ou EXT permitido | pesados pausados; demais → `PAUSED` |

## 4. Limiares de pressão (valem em qualquer modo)

| Sinal | Ação |
| --- | --- |
| CPU média 60 s > 70% | No máximo **1 nova admissão por minuto** (agente ou pesado) |
| CPU média 60 s > 85% | **Nenhuma nova admissão** (nem agente, nem pesado); o que já roda continua |
| RAM disponível < 3,0 GB | Nenhum novo agente; nenhum novo load de modelo |
| RAM disponível < 2,0 GB | Pausa cooperativa do processo pesado mais novo; descarrega o modelo ocioso |
| RAM disponível < 1,5 GB | → CRITICAL |
| VRAM disponível para a fábrica (§1.1) < estimativa do modelo | Load negado → `WAITING(resources)` ou EXT (se permitido) |
| Critérios de §1.1 | → CONTENTION (descarrega **somente** modelos da fábrica) |
| Temp. GPU ≥ 80 °C | Nenhum novo job de GPU; `keep_alive` = 0 |
| Temp. GPU ≥ 87 °C | → CRITICAL |
| Disco D: < 20 GB | Build/mídia → `WAITING(disk)` |
| Disco C: < 15 GB | Alerta ao usuário (a fábrica não grava em C:; o Ollama sim, veja KI-0008) |
| Subir Docker/S2 | Admissão própria: RAM disponível ≥ reserva do modo + 3,0 GB; senão `WAITING(resources)` |

## 5. Modelos carregados

- **Máximo 1 modelo da fábrica na GPU** por vez (`gpu.max_factory_models_loaded: 1`, configurável, teto em `RESOURCE_POLICY.md`); exceção: T0 (≤1 GB) junto com T1 se `gpu.allow_t0_colocation` e a soma couber na VRAM disponível (§1.1).
- A fábrica **só descarrega modelos que ela mesma carregou** (registro de posse, 06 §2.1). Modelos carregados por outras ferramentas nunca são descarregados pela fábrica; contam como `vram_terceiros`.
- Estimativa de VRAM = `tamanho_em_disco × 1,15 + kv_cache(ctx)`; calibrada com medições reais de `/api/ps` (`size_vram`) gravadas em `model_profiles`.
- Contextos padrão locais: T0 4k · T1 8k · T2 8k (16k só em BACKGROUND e se couber).
- Fila única de GPU (lease), com prioridade P0 > P1 > P2 > P3; um lease dura no máximo 1 chamada de modelo (as chamadas se intercalam entre agentes).
- O Model Router descarrega (`keep_alive: 0`) **os modelos da fábrica** ao trocar de modelo e quando o modo muda.
- Configuração do Ollama recomendada (**decisão do usuário, a fábrica não altera o sistema**): `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=2m`, `OLLAMA_MODELS=D:\...` (tirar os modelos do C:).

## 6. Limite de processos

- Total de **slots de processo** da fábrica: daemon + até 4 runners + até 2 pesados + 1 navegador = **8 no máximo**. Cada slot pode ter processos filhos, limitados pelo seu Job Object (S1h: até 32 processos, memória e CPU conforme 08 §4.2); o limite de 8 conta slots, não processos filhos.
- Timeouts: passo de agente 10 min; suíte de testes 15 min; build 30 min; comando de shell 5 min (padrão, configurável por comando).
- Árvores de processos rastreadas por PID; kill da árvore no cancelamento.

## 7. Prioridade dos jobs

| Classe | Uso | Preempção |
| --- | --- | --- |
| P0 | Usuário esperando resposta curta (perguntas, status, correções pequenas) | Pode preemptar P2/P3 em fronteira de passo |
| P1 | Jobs normais do usuário | Não preempta |
| P2 | Jobs em lote/segundo plano pedidos pelo usuário | Pode ser preemptado |
| P3 | Evolução, reindexação, manutenção | Só em BACKGROUND; sempre preemptável |

Envelhecimento: +1 nível a cada 30 min na fila (limite P1).

## 8. Dinheiro

O Resource Manager **não conhece preços**. Custo é política do Provider Router: orçamento padrão **R$ 0 / US$ 0**; nenhuma decisão automática gasta dinheiro (ver `06`).

## 9. Configuração (`config/resources.yaml`, a criar na Fase 2)

Exemplo **ilustrativo** (conteúdo normativo, sintaxe não): o arquivo real é escrito no subconjunto JSON do YAML 1.2, sem comentários, e é protegido (`config/**`) — D-0049, D-0052.

```yaml
sampling: { interval_s: 1, cpu_window_s: 60, gpu_window_s: 30 }   # histerese de 10 s fixa, não configurável (D-0069, D-0070)
idle_threshold_min: 10
reserves: { ram_gb: { FOREGROUND: 3.0, BACKGROUND: 2.0, BATTERY: 3.0, CONTENTION: 3.0 }, vram_mib: { FOREGROUND: 768, BACKGROUND: 384 } }
limits:
  FOREGROUND: { agents: 2, heavy: 1, gpu_tiers: [T0, T1], keep_alive: 2m, cpu_offload_gb: 0 }
  BACKGROUND: { agents: 4, heavy: 2, gpu_tiers: [T0, T1, T2], keep_alive: 10m, cpu_offload_gb: 4 }
  BATTERY:    { agents: 1, heavy: 0, gpu_tiers: [], keep_alive: 0, cpu_offload_gb: 0, pause_below_pct: 30 }
  CONTENTION: { agents: 2, heavy: 1, gpu_tiers: [], keep_alive: 0 }
  CRITICAL:   { agents: 0, heavy: 0, gpu_tiers: [] }
gpu:
  max_factory_models_loaded: 1        # teto; só humano aumenta (guardrail I4)
  max_concurrent_local_calls: 1
  allow_t0_colocation: true
  measurement_margin_mib: 512         # >= 256
  context_overhead_mib: 300           # calibrar
  observation_window_s: 2
  contention_processes: []            # executáveis de jogos/apps 3D (configurável)
  benign_processes: [EpicGamesLauncher.exe, steam.exe, nvcontainer.exe, explorer.exe, chrome.exe]
thresholds:
  ram_gb: { no_new_agents: 3.0, shed_heavy: 2.0, critical: 1.5, critical_exit: 2.5 }
  cpu_pct: { one_admission_per_min: 70, no_new_admission: 85 }
  gpu: { contention_util_pct: 20, contention_vram_mib: 1536, contention_vram_growth_mib_30s: 512, temp_throttle_c: 80, temp_critical_c: 87 }
  docker_vm_admission_ram_gb: 3.0     # S2 exige RAM própria além da reserva
  disk_gb: { work_drive: D, build_min: 20, critical: 5, system_drive_warn: 15 }
max_processes: 8
```
