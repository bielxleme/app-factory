# RESOURCE_POLICY.md — Recursos e limites

Especificação completa: `docs/architecture/05-resource-manager.md`. Este arquivo é o resumo normativo; em caso de divergência, **vale o valor mais restritivo**.

## 1. Hardware medido (2026-09-26 16:17 -03:00)

Fonte: `tools/diagnostics/measure-hardware.ps1` → `.appfactory/runtime/hardware/snapshot-20260926-161709.json` (não versionado).

| Recurso | Valor medido |
| --- | --- |
| Máquina / SO | Acer Nitro ANV15-51 · Windows 11 Home Single Language 10.0.26200 · PowerShell 5.1 · ligado há 187 h |
| CPU | Intel Core i5-13420H · **8 núcleos / 12 threads** · 2100 MHz base · uso no momento: amostras 10/0/25/45/4 % (média **16,8%**) |
| RAM | **24 GB instalados** (16 + 8 GB DDR5-5600, rodando a 5200) · 23,71 GB visíveis · **5,2 GB disponíveis** · 18,51 GB em uso (**78,1%**) · commit livre 17,98 de 56,51 GB |
| GPU | **NVIDIA GeForce RTX 4050 Laptop** · driver 617.14 · CUDA UMD 13.4 · **VRAM 6141 MiB** · usada 105 MiB · **livre 5816 MiB** · uso 0% · 46 °C · P8 · 2,31 W (limite 62 W) · iGPU Intel UHD também presente |
| Processos na GPU | nvcontainer, EpicGamesLauncher, EOSOverlayRenderer (uso de VRAM não reportado) |
| Disco | C: NTFS 475,7 GB · **32,9 GB livres** · D: NTFS 465,7 GB · **177,8 GB livres** · 2 SSDs NVMe |
| Energia | Tem bateria · **na tomada** · 79% · plano "Acer" |
| Temperatura | GPU 46 °C · CPU **indisponível** (ACPI/WMI vazio sem administrador) |
| Usuário | ativo no momento (ocioso 0 s) · maiores consumidores de RAM: Chrome (vários processos, ~0,3–0,5 GB cada), Claude, vmmem, Norton, Word, Explorer |
| Ollama | 0.34.4 · API ok em 127.0.0.1:11434 · **nenhum modelo carregado** · nenhuma variável `OLLAMA_*` definida · 6 modelos (ver `06-provider-model-router.md` §2) |

## 2. Conclusões que orientam a arquitetura

1. **RAM é o gargalo com o usuário ativo** (5,2 GB livres). A fábrica mira no máximo ~2 GB de uso próprio nesse modo.
2. **VRAM de 6 GB = 1 modelo da fábrica por vez**; T2 (8B, 5,2 GB em disco) só com a GPU livre e contexto de 8k.
3. **C: está apertado (32,9 GB)**: a fábrica grava só em D:. Os modelos do Ollama estão no C: por padrão (KI-0008).
4. **Notebook com bateria**: modo BATTERY obrigatório.
5. **A GPU é compartilhada com jogos** (launcher Epic ativo): modo CONTENTION obrigatório.

## 3. Política (resumo)

| Modo | Entrada | Agentes | GPU local | Pesados | keep_alive |
| --- | --- | --- | --- | --- | --- |
| CRITICAL | RAM < 1,5 GB · GPU ≥ 87 °C · D: < 5 GB · `.appfactory/STOP` | 0 novos | nenhuma (descarrega) | 0 | 0 |
| BATTERY | sem tomada | 1 | nenhuma (T0 na CPU) | 0 | 0 |
| CONTENTION | GPU de terceiros > 20% ou VRAM de terceiros > 1,5 GB | 2 | nenhuma | 1 | 0 |
| BACKGROUND | ocioso ≥ 10 min | 4 | T0–T2 | 2 | 10 min |
| FOREGROUND | padrão | 2 | T0–T1 | 1 | 2 min |

- Reservas: RAM 3,0 GB (FG/BAT) e 2,0 GB (BG); VRAM 768 MiB (FG) e 384 MiB (BG).
- Pressão: CPU > 85% → sem novos pesados; RAM < 3 GB → sem novos agentes/modelos; RAM < 2 GB → libera o pesado mais novo; GPU ≥ 80 °C → sem novos jobs de GPU.
- Máximo de 8 processos da fábrica; prioridade BELOW_NORMAL (IDLE na bateria).
- Prioridades P0–P3 com envelhecimento de 30 min; preempção só em fronteira de passo.
- **Nenhuma decisão de recurso gasta dinheiro.** Orçamento pago padrão = 0.

## 4. Recomendações ao usuário (a fábrica não altera o sistema)

- Definir `OLLAMA_MODELS` para uma pasta no D: e mover os modelos (libera espaço no C:).
- Definir `OLLAMA_MAX_LOADED_MODELS=1` e `OLLAMA_NUM_PARALLEL=1`.
- Manter o Docker Desktop desligado quando a fábrica não estiver usando o sandbox S2.
