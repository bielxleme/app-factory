# 05 — Resource Manager (D)

Diagrama: `13-diagramas.md` §4. Valores de referência do hardware medido: RAM 23,71 GB (5,2 GB livres no uso normal), VRAM 6141 MiB, 12 threads, C: 32,9 GB livres, D: 177,8 GB livres.

## 1. Sondas e frequência

| Métrica | Fonte | Frequência | Janela de decisão |
| --- | --- | --- | --- |
| CPU % total | psutil (`cpu_percent`) | 5 s | média de 60 s |
| RAM disponível | psutil (`virtual_memory().available`) | 5 s | mínimo de 30 s |
| Commit livre | WMI `FreeVirtualMemory` | 30 s | valor atual |
| GPU %, VRAM usada/livre, temperatura, potência | NVML (nvidia-ml-py); fallback `nvidia-smi --query-gpu` | 5 s | média de 30 s |
| Processos usando a GPU | NVML (processos de computação/gráficos) | 15 s | valor atual |
| Modelos carregados | Ollama `/api/ps` | 15 s e após load/unload | valor atual |
| Ociosidade do usuário | Win32 `GetLastInputInfo` | 5 s | valor atual |
| Energia / bateria | psutil `sensors_battery()` | 30 s | valor atual |
| Disco livre (C:, D:) | psutil `disk_usage` | 60 s | valor atual |
| Temperatura da CPU | **Indisponível** (WMI exige administrador; medido: vazio) | — | — |

Falha de uma sonda → assume o **pior caso** daquele recurso e registra `resource.probe_failed`.

## 2. Modos (avaliados em ordem; o primeiro que casar vence)

| Ordem | Modo | Condição de entrada | Condição de saída (histerese) |
| --- | --- | --- | --- |
| 1 | **CRITICAL** | RAM disponível < 1,5 GB **ou** temp. GPU ≥ 87 °C **ou** disco de trabalho (D:) < 5 GB **ou** kill switch `.appfactory/STOP` | RAM ≥ 2,5 GB **e** GPU ≤ 80 °C **e** disco ≥ 10 GB por 60 s (e kill switch removido) |
| 2 | **BATTERY** | Sem energia da tomada | Tomada por 60 s |
| 3 | **CONTENTION** | Processo que não é da fábrica usando GPU > 20% (média 30 s) **ou** VRAM de terceiros > 1,5 GB **ou** app em tela cheia | Condição ausente por 120 s |
| 4 | **BACKGROUND** | Usuário ocioso ≥ 10 min | Qualquer entrada do usuário → FOREGROUND imediato |
| 5 | **FOREGROUND** | Padrão (usuário ativo) | — |

Mudança de modo só vale após **2 avaliações consecutivas** (10 s), exceto: entrada em CRITICAL e volta do usuário (imediatas).

## 3. Política por modo

| Aspecto | FOREGROUND | BACKGROUND | BATTERY | CONTENTION | CRITICAL |
| --- | --- | --- | --- | --- | --- |
| Agentes simultâneos | 2 | 4 | 1 | 2 | 0 novos; pausa os pesados |
| Tiers locais permitidos na GPU | T0, T1 | T0, T1, T2 | nenhum (T0 na CPU permitido) | nenhum | nenhum (descarrega tudo) |
| `keep_alive` dos modelos | 2 min | 10 min | 0 | 0 (descarrega) | 0 |
| Offload de modelo para a CPU (camadas fora da GPU) | **proibido** | permitido até 4 GB de RAM | proibido | proibido | proibido |
| Processos pesados | 1 | 2 | 0 (ficam em WAITING) | 1 (sem GPU) | 0 |
| Prioridade de processo | BELOW_NORMAL | BELOW_NORMAL | IDLE | BELOW_NORMAL | — |
| Provedores externos gratuitos já consentidos | sim | sim | sim | sim (preferidos) | não |
| Jobs P3 (evolução/manutenção) | não | sim | não | não | não |
| Bateria < 30% (dentro de BATTERY) | — | — | pausa tudo exceto P0 (com checkpoint) | — | — |

## 4. Limiares de pressão (valem em qualquer modo)

| Sinal | Ação |
| --- | --- |
| CPU média 60 s > 70% | No máximo 1 nova admissão por minuto |
| CPU média 60 s > 85% | Nenhum novo processo pesado; agentes continuam |
| RAM disponível < 3,0 GB | Nenhum novo agente; nenhum novo load de modelo |
| RAM disponível < 2,0 GB | Pausa cooperativa do processo pesado mais novo; descarrega o modelo ocioso |
| RAM disponível < 1,5 GB | → CRITICAL |
| VRAM livre < reserva + estimativa | Load negado → `WAITING(resources)` ou EXT (se permitido) |
| GPU de terceiros > 20% | → CONTENTION (descarrega modelos da fábrica) |
| Temp. GPU ≥ 80 °C | Nenhum novo job de GPU; `keep_alive` = 0 |
| Temp. GPU ≥ 87 °C | → CRITICAL |
| Disco D: < 20 GB | Build/mídia → `WAITING(disk)` |
| Disco C: < 15 GB | Alerta ao usuário (a fábrica não grava em C:; o Ollama sim, veja KI-0008) |

## 5. Modelos carregados

- **Máximo 1 modelo da fábrica na GPU** por vez; exceção: T0 (≤1 GB) junto com T1 se a soma couber na VRAM livre menos a reserva.
- Estimativa de VRAM = `tamanho_em_disco × 1,15 + kv_cache(ctx)`; calibrada com medições reais de `/api/ps` (`size_vram`) gravadas em `model_profiles`.
- Contextos padrão locais: T0 4k · T1 8k · T2 8k (16k só em BACKGROUND e se couber).
- Fila única de GPU (lease), com prioridade P0 > P1 > P2 > P3; um lease dura no máximo 1 chamada de modelo (as chamadas se intercalam entre agentes).
- O Model Router descarrega (`keep_alive: 0`) ao trocar de modelo e quando o modo muda.
- Configuração do Ollama recomendada (**decisão do usuário, a fábrica não altera o sistema**): `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=2m`, `OLLAMA_MODELS=D:\...` (tirar os modelos do C:).

## 6. Limite de processos

- Total de processos da fábrica: daemon + até 4 runners + até 2 pesados + 1 navegador = **8 no máximo**.
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

```yaml
sampling: { interval_s: 5, cpu_window_s: 60, gpu_window_s: 30, mode_confirmations: 2 }
idle_threshold_min: 10
reserves: { ram_gb: { FOREGROUND: 3.0, BACKGROUND: 2.0, BATTERY: 3.0 }, vram_mib: { FOREGROUND: 768, BACKGROUND: 384 } }
limits:
  FOREGROUND: { agents: 2, heavy: 1, gpu_tiers: [T0, T1], keep_alive: 2m, cpu_offload_gb: 0 }
  BACKGROUND: { agents: 4, heavy: 2, gpu_tiers: [T0, T1, T2], keep_alive: 10m, cpu_offload_gb: 4 }
  BATTERY:    { agents: 1, heavy: 0, gpu_tiers: [], keep_alive: 0, cpu_offload_gb: 0, pause_below_pct: 30 }
  CONTENTION: { agents: 2, heavy: 1, gpu_tiers: [], keep_alive: 0 }
  CRITICAL:   { agents: 0, heavy: 0, gpu_tiers: [] }
thresholds:
  ram_gb: { no_new_agents: 3.0, shed_heavy: 2.0, critical: 1.5, critical_exit: 2.5 }
  cpu_pct: { slow_admission: 70, no_heavy: 85 }
  gpu: { contention_util_pct: 20, contention_vram_mib: 1536, temp_throttle_c: 80, temp_critical_c: 87 }
  disk_gb: { work_drive: D, build_min: 20, critical: 5, system_drive_warn: 15 }
max_processes: 8
```
