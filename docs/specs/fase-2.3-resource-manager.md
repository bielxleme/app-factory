# Fase 2.3 — Resource Manager · Especificação executável

**Status:** **implementada (D-0073) e validada parcialmente no Windows em 2026-09-27 — PENDENTE.** Windows: `uv run pytest` 210 passed/7 skipped, guardrails 22/6, G23-27 ok, `af resources compare` ok. Pendências: repetir a suíte no Windows após a correção D-0074 (uso da GPU pela média de 30 s) e repetir M2–M4, que não demonstraram o critério de cada cenário (ver `TEST_STATUS.md`). Linux: 218 testes OK (Python 3.10–3.13). Histórico (antes da implementação): decisões P23-01 a P23-10 em D-0058 a D-0067; fechamento documental com D-0058 ajustada, D-0063 complementada, D-0068 e D-0069; conflitos do plano em D-0070 a D-0072.
**Base:** commit `f44ac72` (Fase 2.2 validada, CP-0005 em `6fb983c`). **Data:** 2026-09-27.
**Fontes normativas:** `AGENTS.md`, `RESOURCE_POLICY.md` (tetos), `docs/architecture/05-resource-manager.md` (**fonte canônica dos limiares**, D-0038), `01` §4, `04` §7–8, `06` §2–2.1, `08` §4.4, `10`, `11`, `12` §6–7, `13` §4, `14` (fatia 2.3), `15` §6; decisões D-0017, D-0018, D-0019, D-0024, D-0032, D-0033, D-0036, D-0037, D-0038, D-0042, D-0043, D-0048, D-0049, D-0051, D-0052, D-0056, **D-0058 a D-0072** (decisões desta fase); KIs KI-0007, KI-0008, KI-0010, KI-0011, KI-0017, KI-0019, KI-0020.

Convenções: **[ARQ]** exigido pela arquitetura aprovada · **[2.1]/[2.2]** já existe no código · **[PROP]** proposta desta especificação · **P23-NN** pendência da §9, **decidida** (D-0058 a D-0067).

---

## 1. Escopo exato

### 1.1 Princípio

A 2.3 implementa o Resource Manager como **biblioteca confiável somente de leitura e decisão**: sondas do sistema, contabilidade de VRAM no WDDM, avaliação de modo com histerese, limiares de pressão e **resposta de admissão** (`GRANT`/`DENY`/`WAIT`), mais a CLI `af resources`. **Não atua**: não pausa tasks, não descarrega modelos, não altera Windows, drivers, planos de energia nem a instalação do Ollama (01 §4 Permissões). A atuação contínua é do daemon (2.4) e o descarregamento de modelos depende do registro de posse (2.5).

Critério de pronto da fatia (14): **valores batem com `measure-hardware.ps1`** e **matriz de validação da GPU executada** (KI-0017).

### 1.2 Dentro do escopo

| # | Entrega | Base |
| --- | --- | --- |
| E1 | `config/resources.yaml` (subconjunto JSON, protegido) com o conteúdo normativo de 05 §9: **sem `mode_confirmations`**, `sampling.interval_s: 1` (D-0070), `reserves.ram_gb.CONTENTION: 3.0` (D-0072) | [ARQ] 05 §9; D-0049, D-0052, D-0070, D-0072 |
| E2 | Carregador/validador da política com checagem contra os **tetos** do `RESOURCE_POLICY.md` (guardrail I4) | [ARQ] RESOURCE_POLICY; 09 I4 |
| E3 | Sondas: Windows (RAM, commit, CPU, energia/bateria, disco, ociosidade, tela cheia/D3D, processos), NVIDIA (GPU/VRAM **totais**, temperatura, potência, processos na GPU), runtime local (Ollama `/api/ps`, **somente leitura**), Linux (desenvolvimento/VM) | [ARQ] 05 §1; 10 (`resources/probes/`); somente biblioteca padrão + `ctypes`/`nvml.dll` (D-0058); `/api/ps` com todo modelo de terceiros (D-0059); Linux mínima (D-0067) |
| E4 | Contabilidade de VRAM do WDDM (05 §1.1) | [ARQ] D-0032 |
| E5 | Modos CRITICAL > BATTERY > CONTENTION > BACKGROUND > FOREGROUND, histerese, janela de observação da GPU | [ARQ] 05 §1.1–§3; D-0018, D-0038 |
| E6 | Limiares de pressão (05 §4) e fórmula de admissão (04 §8); `admit()` e lease de GPU **em memória** | [ARQ] 12 §6–7; 04 §8 |
| E7 | `ResourceSnapshot` (12 §7) e eventos `resource.*` | [ARQ] 01 §4, 12 §7 |
| E8 | Persistência **somente por eventos** `resource.*` na tabela `events`; tabelas `resource_samples` / `resource_decisions` ficam para a 2.4 | [ARQ] 01 §4; **D-0061** |
| E9 | CLI `af resources snapshot|mode|admit|watch|compare` | [ARQ] 14 (`af resources`); subcomandos [PROP] |
| E10 | Guardrail `I4.resources_config_within_ceilings` passa de `pending` a `active` (D-0048: o módulo `appfactory.resources.manager` passa a existir) | [ARQ] D-0048 |
| E11 | Procedimento e registro da matriz de validação da GPU (KI-0017) e da comparação com `measure-hardware.ps1` | [ARQ] 05 §1.1, 14 |

### 1.3 Fora do escopo (proibido nesta fase)

Daemon e laço contínuo de amostragem/atuação (2.4) · pausar tasks ou mudar estados de job por decisão de recurso (2.4) · descarregar/carregar modelos, registro de posse de modelos, Model Router, `keep_alive` (2.5) · alterar Ollama, suas variáveis ou modelos (D-0034) · Docker/S2 real (2.6) · alterar configuração do Windows, drivers ou energia · executar código não confiável · dependências novas (D-0058: nenhuma) · integração da admissão ao despacho de jobs e novas transições de estado (2.4, D-0060) · migração de schema e tabelas `resource_*` (2.4, D-0061) · seção `sandbox` no `resources.yaml` (D-0065) · cenário M5 da KI-0017 (2.5, D-0066) · agentes, Evolution, API local.

### 1.4 Invariantes que não mudam

STOP (D-0028, D-0054): o Resource Manager **lê** `factory_stop` (fonte da verdade) e nunca o libera; **a saída de CRITICAL exige o STOP da fábrica liberado** e apagar `.appfactory/STOP` nunca libera (D-0062). Guardrails da 2.2 intactos (D-0048…D-0057). Falha de sonda ⇒ **pior caso** daquele recurso (05 §1) — nunca um valor otimista.

---

## 2. Componentes

| Componente | Arquivo (10 — todos em `resources/**`, protegidos) | Responsabilidade |
| --- | --- | --- |
| Política | `src/appfactory/resources/policy.py` | carregar `config/resources.yaml` (JSON, D-0049), validar esquema e tetos (I4) |
| Sondas Windows | `src/appfactory/resources/probes/windows.py` | RAM/commit, CPU, energia, disco, ociosidade, tela cheia/D3D, lista de processos |
| Sondas NVIDIA | `src/appfactory/resources/probes/nvidia.py` | uso/VRAM totais, temperatura, potência, PIDs na GPU (sem VRAM por processo) |
| Runtime local | `src/appfactory/resources/probes/runtime_local.py` | `GET http://127.0.0.1:11434/api/ps` (somente leitura) |
| Sondas Linux | `src/appfactory/resources/probes/linux.py` | `/proc/meminfo`, `/proc/stat`, `statvfs`; o que não existir ⇒ pior caso |
| Contabilidade de GPU | `src/appfactory/resources/gpu_accounting.py` | fórmulas de 05 §1.1 |
| Modos | `src/appfactory/resources/modes.py` | ordem de avaliação, histerese, janela de observação |
| Gerente | `src/appfactory/resources/manager.py` | `snapshot()`, `admit()`, `acquire_gpu()`/`release_gpu()` (em memória), eventos, persistência |
| CLI | `src/appfactory/cli/main.py` (protegido; aditivo) | `af resources …` |
| Guardrail | `tests/guardrails/test_resource_limits.py` + `MANIFEST.json` (protegidos) | ativar `I4.resources_config_within_ceilings` |

### 2.1 Sondas — fonte, frequência e pior caso

| Métrica | Fonte proposta (Windows) | Frequência (05 §1) | Pior caso se falhar |
| --- | --- | --- | --- |
| CPU % total | `GetSystemTimes` (ctypes; D-0058) | 5 s; média 60 s | 100% |
| RAM disponível/total | `GlobalMemoryStatusEx` (fonte oficial, D-0068) | 5 s; mínimo 30 s | 0 GB disponível |
| Commit livre | `GlobalMemoryStatusEx.ullAvailPageFile` (equivale a WMI `FreeVirtualMemory`) | 30 s | 0 |
| GPU %, VRAM usada/livre total, temperatura, potência | NVML (`nvml.dll` via ctypes — caminho principal, D-0058); fallback `nvidia-smi --query-gpu` só em `probes/nvidia.py` | 5 s (1 s na janela de observação); média 30 s | VRAM disponível 0; temperatura ≥ 87 °C ⇒ tratar como crítica |
| Processos na GPU (PIDs/nomes) | NVML `…RunningProcesses` + `QueryFullProcessImageNameW` | 15 s | lista desconhecida ⇒ não dispara sozinha |
| Tela cheia / D3D / apresentação | `SHQueryUserNotificationState` | 5 s | assume tela cheia (CONTENTION) |
| Modelos carregados | Ollama `/api/ps` | 15 s | todos desconhecidos; VRAM já entra em `vram_outros` pelo total |
| Ociosidade | `GetLastInputInfo` + `GetTickCount64` — **leitura instantânea**, sem histórico (D-0071) | 5 s | ativo (0 s) |
| Energia / bateria | `GetSystemPowerStatus` | 30 s | na bateria, 0% |
| Disco livre C:/D: | `GetDiskFreeSpaceExW` | 60 s | 0 GB |
| Temperatura da CPU | **indisponível** (KI-0010) | — | não usada |

Toda falha registra `resource.probe_failed` (05 §1).

### 2.2 Modos, histerese e observação (05 §2–§3)

- Avaliação em ordem: **CRITICAL → BATTERY → CONTENTION → BACKGROUND → FOREGROUND**; o primeiro que casar vence.
- Mudança de modo só após a condição do novo modo ficar satisfeita de forma **contínua por ≥ 10 s de tempo decorrido** (regra fixa de 05 §2, **não configurável** — D-0070; **não** "2 avaliações a cada 5 s"), **exceto** entrada em CRITICAL e volta do usuário (imediatas). Medição (**D-0069**): tempo ativo monotônico (`core/clock.py`, 15 §4); a contagem começa na primeira amostra com a condição e a mudança vale na primeira amostra com `agora − início ≥ 10 s`; amostra sem a condição, lacuna maior que a frequência da métrica em 05 §1, troca de `boot_id` ou retorno do sono reiniciam a contagem; o número de amostras não conta. As saídas com janela própria (60 s, 60 s, 120 s) usam a mesma medição. A coleta de 1 s do `watch` não encurta nenhuma janela (D-0063); cada `resource.snapshot` registra tempo ativo e `boot_id`.
- Saídas com histerese: CRITICAL (RAM ≥ 2,5 GB **e** GPU ≤ 80 °C **e** disco ≥ 10 GB por 60 s **e STOP da fábrica liberado** — `factory_stop` inativo, liberado só por `af resume-factory`; apagar `.appfactory/STOP` não libera — **D-0062**, 05 §2 corrigido); BATTERY (tomada por 60 s); CONTENTION (condição ausente por 120 s).
- Uso alheio da GPU (> 20%) só avaliado em amostras **sem chamada da fábrica em andamento**; janela de observação de 2 s entre chamadas em FOREGROUND/CONTENTION; > 60 s de inferência contínua ⇒ só critérios de VRAM e heurísticas.
- BACKGROUND/FOREGROUND usam o **valor atual** da ociosidade (ocioso ≥ 10 min ⇒ condição de BACKGROUND, sujeita à histerese; entrada do usuário ⇒ FOREGROUND imediato) — **D-0071**.
- Heurísticas de CONTENTION: tela cheia/D3D; processo em `gpu.contention_processes` (launchers em `gpu.benign_processes` não disparam sozinhos); `vram_terceiros` > 1536 MiB; crescimento > 512 MiB em 30 s.

### 2.3 Admissão (04 §8; 05 §3–§4)

`admit(AdmissionRequest{kind: agent|heavy|gpu|s2, priority, est_ram_gb, est_vram_mib?, model?})` ⇒ `GRANT` | `DENY(reason)` | `WAIT(retry_after)`:
- STOP da fábrica ativo ou modo CRITICAL ⇒ nenhuma admissão nova;
- CPU 60 s > 85% ⇒ nenhuma nova; > 70% ⇒ no máximo 1 por minuto;
- RAM < 3,0 GB ⇒ nenhum agente nem load de modelo; `slots_ram = floor((ram_disp − reserva[modo]) / 0,4)`, com `reserva[modo]` = FG 3,0 · BG 2,0 · BATTERY 3,0 · **CONTENTION 3,0** GB (D-0072); `max_agentes = min(limite_modo, slots_ram)`;
- pesado: `ativos < limite[modo]` **e** `ram_disp ≥ reserva + 1,0`; BATTERY: 0 pesados;
- GPU: tier permitido no modo, lease livre (1 por vez; T0 coabitando se `allow_t0_colocation` e couber), `vram_estimada ≤ vram_disponivel_fabrica` (05 §1.1), temperatura < 80 °C;
- S2/Docker: `ram_disp ≥ reserva[modo] + 3,0 GB` (08 §4.4) — alimenta futuramente o parâmetro `s2_admitted` do Toolbox [2.2];
- partida: **2 amostras** antes de qualquer admissão (01 §4); histórico insuficiente para a janela ⇒ `WAIT` e "janela incompleta" na CLI; `watch` acumula histórico em primeiro plano (**D-0063**).
- **fonte do histórico:** `admit` lê o histórico acumulado pelo `watch` (eventos `resource.snapshot`, D-0061); **não** coleta amostras nem espera 60 s. Janelas exigidas = **somente** as métricas com janela explícita na política: CPU 60 s, RAM 30 s, GPU 30 s, crescimento de `vram_terceiros` em 30 s e saídas de modo por tempo — a ociosidade **não** exige histórico (D-0071). Histórico suficiente = amostras cobrindo cada janela exigida inteira até o instante da consulta, sem lacuna entre amostras consecutivas e sem amostra mais recente mais antiga que a frequência da métrica em 05 §1, com no mínimo 2 amostras; caso contrário ⇒ `WAIT` (**D-0063, complemento**).
- a admissão é **biblioteca + CLI** nesta fase; o Job Manager não consulta a admissão e nenhum estado de job muda (**D-0060**; integração ao despacho na 2.4).

Cada `DENY`/`WAIT` é registrado como evento `resource.admission_denied` na tabela `events` (**D-0061**; `resource_decisions` fica para a 2.4).

### 2.4 Contabilidade de VRAM (05 §1.1)

`vram_factory` = Σ `size_vram` dos modelos com posse da fábrica + `overhead_contexto`; **na 2.3 não existe registro de posse (2.5)**, portanto `vram_factory = 0` e todo modelo visto no `/api/ps` conta como `vram_ollama_terceiros` (direção segura) — **D-0059**. `vram_outros = max(0, total_usada − factory − ollama_terceiros − vram_base)`; `vram_terceiros = ollama_terceiros + outros`; `vram_disponivel_fabrica = vram_total − vram_usada_total − reserva_vram[modo] − margem_medicao` (margem ≥ 256 MiB).

---

## 3. Dependências

| Dependência | Situação |
| --- | --- |
| Fase 2.2 (`security/paths.load_policy_file`, guardrails, manifesto) | pronta (CP-0005) |
| Job Manager 2.1 (`factory_stop`, eventos, SQLite) | pronto; **não é alterado** — integração de admissão na 2.4 (D-0060); eventos na tabela existente (D-0061) |
| Bibliotecas: psutil, nvidia-ml-py (citadas originalmente em 01 §4, 05 §1, 11 e 13 §4; referências atualizadas no fechamento documental) | **não usadas** (D-0058): somente biblioteca padrão + `ctypes` + `nvml.dll` |
| `nvidia-smi` (fallback) | presente no Windows; fallback **implementado e permitido**, isolado **exclusivamente** em `resources/probes/nvidia.py`, só quando a NVML falhar; sujeito ao AC-06 (lista ampliada só com esse arquivo); proibido em qualquer outro módulo (G23-30) — D-0058 |
| Ollama 0.34.4 em 127.0.0.1:11434 | presente; **somente leitura** do `/api/ps`; nada é alterado |
| Registro de posse de modelos | **2.5** (06 §2.1) |
| Daemon (laço contínuo, atuação, carência pós-sono) | **2.4** |
| Usuário (Windows) | executar a matriz KI-0017 e a comparação com `measure-hardware.ps1` |

---

## 4. Arquivos a criar / modificar

### 4.1 Criar
`config/resources.yaml` · `src/appfactory/resources/{__init__,policy,modes,gpu_accounting,manager}.py` · `src/appfactory/resources/probes/{__init__,windows,nvidia,runtime_local,linux}.py` · `tests/unit/test_resource_policy.py`, `test_resource_modes.py`, `test_gpu_accounting.py`, `test_admission.py`, `test_probes.py` · `tests/integration/test_cli_resources.py` · `tests/fakes/probes.py` (sondas falsas, só em testes) · `docs/runbooks/recursos.md` (inclui o procedimento KI-0017).

### 4.2 Modificar (aditivo; arquivos protegidos ⇒ sessão dirigida pelo usuário, registrar em `DECISIONS.md`)
`src/appfactory/cli/main.py` (`af resources`) · `tests/guardrails/test_resource_limits.py` e `tests/guardrails/MANIFEST.json` (ativar I4.resources) · `tests/unit/test_repo_hygiene.py` (lista do AC-06 ampliada **só** com `resources/probes/nvidia.py`; verificação de que nenhum outro módulo cita/invoca `nvidia-smi` — D-0058, G23-30). **Não** se altera `src/appfactory/jobs/store.py` (D-0061) nem o restante do Job Manager (D-0060). A correção de `docs/architecture/05-resource-manager.md` §2 (D-0062) **já foi aplicada** na sessão de decisões.

---

## 5. APIs e interfaces

```python
# resources/policy.py
@dataclass(frozen=True)
class ResourcePolicy: sampling; idle_threshold_min; reserves; limits; gpu; thresholds; max_processes
def load_policy(root) -> ResourcePolicy          # D-0049; inválido => erro (fail-closed)
def check_ceilings(policy) -> list[str]          # violações dos tetos (I4); vazio = ok

# resources/probes/*
class Probe(Protocol):
    def sample(self) -> RawSample                 # campos ausentes = None => pior caso na decisão

# resources/modes.py
class ModeTracker:
    def update(self, sample: RawSample, now_active_ms: int, factory_stop: bool, factory_call_active: bool) -> ModeState

# resources/manager.py  (12 §6)
class ResourceManager:
    def __init__(self, root, probes, clock, policy=None, persist=None): ...
    def snapshot(self) -> ResourceSnapshot        # 12 §7
    def admit(self, req: AdmissionRequest) -> Admission    # GRANT | DENY(reason) | WAIT(retry_after_s)
    def acquire_gpu(self, model: str, est_vram_mib: int, priority: int) -> GpuLease | None   # em memória
    def release_gpu(self, lease: GpuLease) -> None
```

CLI (códigos: 0 ok · 3 negado/fora da tolerância · 2 erro): `af resources snapshot [--json] [--samples N]` · `af resources mode` · `af resources admit --kind agent|heavy|gpu|s2 [--model M --est-vram-mib N]` (simulação, nada é reservado; **lê o histórico do `watch`, não coleta amostras**; histórico insuficiente ⇒ `WAIT` — D-0063) · `af resources watch [--interval S]` (primeiro plano; **intervalo padrão 1 s** = `sampling.interval_s` (D-0070), substituível por `--interval` naquela execução; cada amostra ⇒ evento `resource.snapshot` — D-0063) · `af resources compare --hardware-snapshot <arquivo>` (comparação com `measure-hardware.ps1`).

Eventos: `resource.snapshot` (só no `watch`; **append-only** nesta fase, sem retenção nem limpeza automática — D-0061, D-0063), `resource.mode_changed`, `resource.admission_denied`, `resource.probe_failed`.

---

## 6. Matriz de testes

| ID | Objetivo | Pré-condições | Ação | Resultado esperado |
| --- | --- | --- | --- | --- |
| G23-01 | Política válida | `config/resources.yaml` real | `load_policy` | carrega; `check_ceilings` vazio |
| G23-02 | Formato D-0049 | arquivo com comentário/sintaxe YAML | `load_policy` | erro (fail-closed) |
| G23-03 | Tetos (I4) | agentes FG 3, BG 5, `max_factory_models_loaded` 2, `max_concurrent_local_calls` 2, margem 128 MiB, `reserves.ram_gb.CONTENTION` 2,9; arquivo com `mode_confirmations` | `check_ceilings`/`load_policy` | cada violação listada; política recusada; `mode_confirmations` rejeitada (chave não prevista — D-0070) |
| G23-04 | Ordem dos modos | sondas falsas combinando RAM baixa + bateria + tela cheia + ocioso | `update` | CRITICAL > BATTERY > CONTENTION > BACKGROUND > FOREGROUND |
| G23-05 | Histerese por tempo (D-0069) | relógio falso; coleta a 1 s | condição nova por 9 s; por 10 s; interrompida aos 6 s; lacuna > frequência; troca de `boot_id` | 9 s não muda; 10 s muda; interrupção, lacuna e `boot_id` reiniciam a contagem; 2 amostras em 2 s não mudam; CRITICAL e volta do usuário imediatas |
| G23-06 | Saídas | CONTENTION 119 s × 120 s; BATTERY 59 s × 60 s; CRITICAL com RAM 2,5 GB por 60 s | `update` | saídas só nos tempos de 05 §2 |
| G23-07 | STOP e CRITICAL | `factory_stop` ativo; arquivo `STOP` apagado; RAM/GPU/disco já dentro das condições de saída por 60 s | `update`/`admit` | CRITICAL mantido até `factory_stop` liberado (D-0062); nenhuma admissão |
| G23-08 | Limiares de CPU | média 60 s = 71% e 86% | 2 `admit` em 60 s | 1 por minuto; nenhuma |
| G23-09 | Limiares de RAM | 2,9 GB; 1,9 GB; 1,4 GB | `admit(agent)`; `update` | nega agente; ação recomendada de liberar pesado; CRITICAL |
| G23-10 | Fórmula de admissão | 5,2 GB disponíveis, FG | `admit(agent)` ×3 | 2 concedidos, 3º `WAIT` (04 §8) |
| G23-11 | Pesados e BATTERY | FG com 1 pesado; BATTERY | `admit(heavy)` | `WAIT`; BATTERY sempre `WAIT` |
| G23-12 | S2 e reserva de CONTENTION | RAM = reserva + 2,9 GB e + 3,0 GB (FG e CONTENTION, reserva 3,0) | `admit(s2)`; `admit(agent)`/`admit(heavy)` em CONTENTION | `WAIT` e `GRANT`; em CONTENTION as fórmulas usam reserva 3,0 GB (D-0072) |
| G23-13 | GPU por modo | FG pedindo T2; BATTERY pedindo T0 | `admit(gpu)` | negado; negado (T0 só na CPU) |
| G23-14 | Lease de GPU | lease ativo | 2º `acquire_gpu`; T0 coabitando | `None`; concedido só se couber e `allow_t0_colocation` |
| G23-15 | Contabilidade WDDM | total 4000, `/api/ps` 2500, base 105 | cálculo | `vram_factory = 0` (sem posse, 2.5); terceiros = 3895; disponível conforme fórmula |
| G23-16 | Janela de observação | chamada da fábrica em andamento com uso 90% | `update` | uso não dispara CONTENTION; após > 60 s só VRAM/heurísticas |
| G23-17 | Heurísticas | tela cheia; jogo na lista; só launcher; +600 MiB em 30 s | `update` | CONTENTION; CONTENTION; nada; CONTENTION |
| G23-18 | Temperatura | GPU 80 °C e 87 °C | `admit(gpu)`; `update` | negado; CRITICAL |
| G23-19 | Disco | D: 19 GB; D: 4,9 GB; C: 14 GB | `admit(heavy build)`; `update` | `WAIT(disk)`; CRITICAL; alerta de C: |
| G23-20 | Pior caso | cada sonda lançando erro | `snapshot`/`admit` | valor de pior caso; evento `resource.probe_failed`; nunca `GRANT` otimista |
| G23-21 | Partida e janela | 0 e 1 amostra; histórico < janela de 60 s; usuário ocioso há 12 min com 90 s de histórico | `admit` | `WAIT` até 2 amostras (01 §4); `WAIT` com "janela incompleta" enquanto a janela de CPU não estiver completa (D-0063); ociosidade não exige histórico — avaliada pelo valor atual (D-0071) |
| G23-22 | Somente leitura | sondas reais/falsas | executar tudo | nenhuma chamada de escrita ao Ollama (só `GET /api/ps`), nenhum subprocesso fora do aprovado, nenhuma alteração de job |
| G23-23 | Snapshot 12 §7 | sondas falsas | `snapshot` | todos os campos de 12 §7 presentes e tipados |
| G23-24 | Persistência | D-0061 | `admit` negado; `watch` | evento `resource.admission_denied` (e `resource.snapshot` no `watch`) na tabela `events`; nenhuma tabela nova; schema inalterado |
| G23-25 | CLI | raiz temporária | `af resources snapshot/mode/admit/compare` | JSON válido; códigos 0/3/2 |
| G23-26 | Guardrail I4 | manifesto atualizado | comando fixo dos guardrails | `I4.resources_config_within_ceilings` **active** e passando; teste de controle do manifesto verde |
| G23-27 | Sondas Windows reais | Windows | `test_probes` (só Windows) | valores plausíveis (RAM total 23,71 GB ± 0,05; 12 CPUs lógicas; VRAM 6141 MiB) |
| G23-28 | Comparação com `measure-hardware.ps1` | snapshot novo do usuário | `af resources compare` | estáticos idênticos (tolerâncias §7); dinâmicos só informativos |
| G23-29 | Regressão | — | suíte completa | 157/21 da 2.2 continuam passando |
| G23-30 | `nvidia-smi` isolado | árvore `src/` | teste AST/texto (AC-06) | subprocesso `nvidia-smi` só em `resources/probes/nvidia.py` e só após falha da NVML (sonda falsa); nenhum outro módulo cita/invoca `nvidia-smi`; sem `shell=True` (D-0058) |
| G23-31 | `admit` lê o histórico do `watch` | eventos `resource.snapshot`: nenhum; completos até agora; antigos; com lacuna | `admit` | nenhum/antigos/com lacuna ⇒ `WAIT` ("janela incompleta"); completos ⇒ avalia; `admit` não coleta amostras nem espera (sem `sleep`; relógio falso) (D-0063) |
| G23-32 | Frequência e eventos do `watch` | relógio falso | `watch` sem `--interval`; com `--interval 5` | coleta a cada 1 s por padrão; `--interval` respeitado; cada amostra ⇒ `resource.snapshot`; UPDATE/DELETE em `events` rejeitados pelos triggers; nenhuma limpeza (D-0063) |

Matriz manual KI-0017 (Windows, usuário; registrada em `TEST_STATUS.md`): **M1** ocioso · **M2** vídeo no navegador · **M3** jogo abrindo · **M4** Ollama usado por outra ferramenta (OpenClaw) · **M5** inferência da fábrica + jogo (**na 2.5** — D-0066). Para cada cenário: modo esperado × observado, `vram_terceiros`, uso da GPU, e calibração proposta de `vram_base`, `overhead_contexto`, `margem_medicao`.

---

## 7. Critérios de aceite

| # | Critério | Verificação |
| --- | --- | --- |
| AC23-01 | Suíte completa sem falhas no Windows | `uv run pytest` → 0 failed |
| AC23-02 | Guardrails pelo comando fixo | 0 failed; `I4.resources_config_within_ceilings` ativo (pulados = 6) |
| AC23-03 | Linux sem pytest | `unittest` OK (VM) |
| AC23-04 | Tetos | G23-03; `config/resources.yaml` real sem violação |
| AC23-05 | Somente leitura | G23-22 + teste AST: nenhuma escrita no Ollama, nenhuma mudança de estado de job pelo Resource Manager |
| AC23-06 | Pior caso | G23-20 |
| AC23-07 | Valores × `measure-hardware.ps1` | `af resources compare` código 0: CPUs lógicas iguais; RAM total ± 0,05 GB; VRAM total igual; tamanho de C:/D: ± 0,5 GB; presença de bateria igual |
| AC23-08 | Matriz KI-0017 | M1–M4 executados e registrados; M5 marcado como pendente da 2.5 (D-0066) |
| AC23-09 | Sem dependências novas; `nvidia-smi` isolado | `pyproject.toml` sem dependências novas (D-0058); psutil/nvidia-ml-py ausentes; `nvidia-smi` só em `probes/nvidia.py` (G23-30) |
| AC23-10 | Higiene | `git diff --check`; sem segredos; runtime fora do Git |

---

## 8. KIs relacionados

KI-0007 (RAM livre baixa: FG limitado a 2 agentes) · KI-0008 (C: com pouco espaço; alerta C: < 15 GB) · KI-0010 (sem temperatura da CPU) · KI-0011 (Docker a confirmar: admissão S2 só calcula) · **KI-0017 (validação da GPU — alvo desta fatia)** · KI-0019/KI-0020 (sem daemon: sem laço contínuo nem atuação; escritor transitório).

**Limitação aceita nesta fase (D-0063):** os eventos `resource.snapshot` são append-only e não há retenção nem limpeza automática; enquanto o `watch` roda, a tabela `events` cresce cerca de um evento por segundo no intervalo padrão.

---

## 9. Contradições e decisões (todas decididas — D-0058 a D-0067)

| ID | Contradição / lacuna | Onde | Opções | Recomendação |
| --- | --- | --- | --- | --- |
| P23-01 | 05 §1 e 11 citam **psutil** e **nvidia-ml-py**; D-0042 proíbe dependências sem decisão e o PyPI está bloqueado na VM de verificação. O fallback `nvidia-smi` exige subprocesso, e o AC-06 da 2.2 só permite subprocesso em `diff_guard.py` e `cli/main.py` | 05 §1, 11 × D-0042, AC-06 | (a) adicionar psutil + nvidia-ml-py (decisão, `uv.lock`; testes na VM com importação opcional); (b) somente biblioteca padrão: Win32 via `ctypes` e NVML via `nvml.dll` do driver por `ctypes`; `nvidia-smi` como fallback aprovado em `resources/probes/nvidia.py` (lista do AC-06 ampliada por decisão); (c) (b) sem fallback | (b) |
| P23-02 | Contabilidade de VRAM exige o registro de posse (06 §2.1, fatia 2.5) | 05 §1.1 × 14 | (a) ler `/api/ps` na 2.3 e tratar **todo** modelo como de terceiros até a 2.5 (direção segura); (b) não ler o Ollama na 2.3 (VRAM só pelo total) | (a) |
| P23-03 | A admissão deveria segurar jobs, mas `QUEUED → WAITING` não existe na máquina de estados, e o despacho contínuo é do daemon (2.4) | 03 × 04 §8 × 14 | (a) 2.3 entrega só a biblioteca e a CLI; integração no despacho na 2.4; (b) `claim` consulta a admissão e deixa o job em `QUEUED` com `state_reason` (muda o Job Manager protegido); (c) nova transição `QUEUED → WAITING` | (a) |
| P23-04 | 01 §4 prevê tabelas `resource_samples` e `resource_decisions`, mas não há daemon para amostragem contínua e o `store.py` é protegido | 01 §4 × D-0037/D-0043 | (a) migração de schema 2 agora (tabelas criadas; escritas por `admit`/`watch`); (b) só eventos `resource.*` na tabela `events` na 2.3, tabelas na 2.4 | (b) — sem migração nesta fatia |
| P23-05 | **Contradição real:** 05 §2 diz que CRITICAL sai com "kill switch removido", mas D-0028 diz que apagar `.appfactory/STOP` nunca libera | 05 §2 × D-0028, 08 §9 | (a) saída de CRITICAL exige `factory_stop.active = 0` (liberado por `af resume-factory`) e corrigir o texto de 05 §2; (b) manter o texto | (a) |
| P23-06 | Janelas de 60 s/30 s/120 s e ociosidade de 10 min pressupõem amostragem contínua (daemon, 2.4) | 05 §1–§2 × 14 | (a) sem histórico suficiente, `admit` responde `WAIT` (fail-closed) e a CLI mostra "janela incompleta"; `watch` acumula histórico em primeiro plano; (b) janelas reduzidas na 2.3 | (a) |
| P23-07 | O `RESOURCE_POLICY.md` lista tetos explícitos (modelos na GPU, chamadas locais, agentes FG/BG, memória/CPU do S1h, RUNNING por projeto); os demais limiares de 05 §4 não têm "direção segura" formal | RESOURCE_POLICY × 05 §4 × I4 | (a) I4 verifica só a tabela de tetos + margem ≥ 256 MiB (D-0032); (b) I4 também impede afrouxar qualquer limiar de 05 §4 (reservas não menores, limiares de RAM/CPU/temperatura não mais permissivos) | (b) |
| P23-08 | P-09 (aberta): limites configuráveis do S1h sem lugar no `resources.yaml` | 08 §4.2 × 05 §9 | (a) seção `sandbox` no `resources.yaml` (≤ tetos); (b) manter as constantes da 2.2 até a 2.6 | (b) — P-09 continua aberta |
| P23-09 | O cenário "inferência da fábrica + jogo" (KI-0017) exige o Model Router (2.5) | 05 §1.1 × 14 | (a) M1–M4 na 2.3, M5 na 2.5; (b) exigir M5 na 2.3 | (a) |
| P23-10 | 10 lista `probes/linux.py`; o alvo é Windows | 10 × D-0013 | (a) sonda Linux mínima só para desenvolvimento/VM; (b) só sondas falsas fora do Windows | (a) |

**Decisões do usuário (2026-09-27):** todas as recomendações acima foram aprovadas.

| ID | Decisão | Registro |
| --- | --- | --- |
| P23-01 | (b) somente biblioteca padrão + `ctypes` + `nvml.dll` no caminho principal; sem psutil, nvidia-ml-py nem subprocesso `nvidia-smi` no caminho principal; `nvidia-smi` como fallback **implementado e permitido**, isolado em `probes/nvidia.py`, sujeito ao AC-06 | D-0058 |
| P23-02 | (a) ler `/api/ps` (somente leitura); todo modelo de terceiros até a 2.5 | D-0059 |
| P23-03 | (a) biblioteca + CLI; integração ao despacho de jobs na 2.4 | D-0060 |
| P23-04 | (b) eventos `resource.*`; tabelas estruturadas na 2.4 | D-0061 |
| P23-05 | (a) saída de CRITICAL exige STOP da fábrica liberado; 05 §2 corrigido | D-0062 |
| P23-06 | (a) histórico insuficiente ⇒ `WAIT`; `watch` acumula histórico; complemento: `admit` lê o histórico do `watch` (não coleta), `watch` a cada 1 s, `resource.snapshot` append-only sem retenção | D-0063 |
| P23-07 | (b) I4 também impede afrouxar limiares de 05 §4 | D-0064 |
| P23-08 | (b) constantes da 2.2 até a 2.6; P-09 continua aberta | D-0065 |
| P23-09 | (a) M1–M4 na 2.3; M5 na 2.5 | D-0066 |
| P23-10 | (a) sonda Linux mínima só para desenvolvimento/VM | D-0067 |
| — | Fonte oficial de RAM: `GlobalMemoryStatusEx` (WMI/CIM não é fonte do Resource Manager) | D-0068 |
| — | Histerese: tempo decorrido contínuo de 10 s em tempo ativo, independente do número de amostras | D-0069 |
| — | `sampling` sem `mode_confirmations`; histerese fixa e não configurável; `sampling.interval_s: 1` é o padrão do `watch` | D-0070 |
| — | Ociosidade é leitura instantânea; histórico só para métricas com janela explícita | D-0071 |
| — | Reserva de RAM de CONTENTION = 3,0 GB | D-0072 |

**Consequência de P23-05 (D-0062):** o modo CRITICAL só termina quando RAM ≥ 2,5 GB **e** GPU ≤ 80 °C **e** disco ≥ 10 GB por 60 s **e** o STOP da fábrica estiver liberado (`factory_stop` inativo, só por `af resume-factory` com confirmação do usuário). Apagar `.appfactory/STOP` **nunca** faz sair de CRITICAL; o Resource Manager lê `factory_stop` e nunca o libera. `05-resource-manager.md` §2 foi corrigido (revisão 1.2) e a contradição com D-0028 deixou de existir. Coberto por G23-07.

Nenhuma decisão bloqueante pendente. As pendências P-04, P-09, P-10, P-12, P-13 e P-14 da Fase 2.2 são independentes e continuam abertas.

---

## 10. Ordem recomendada de implementação

1. ~~Decisões (§9) registradas em `DECISIONS.md`; correção de 05 §2~~ — **feito** (D-0058 a D-0067; 05 §2 revisão 1.2).
2. `config/resources.yaml` + `policy.py` + guardrail I4 (G23-01…03, G23-26).
3. Sondas falsas + `gpu_accounting.py` + `modes.py` com histerese por tempo (D-0069) (G23-04…07, G23-15…18).
4. `manager.py`: snapshot, admissão, lease em memória (G23-08…14, G23-19…21, G23-23).
5. Sondas reais: Windows, NVIDIA (NVML + fallback isolado), runtime local (somente leitura), Linux mínima (G23-22, G23-27, G23-30).
6. CLI `af resources` incl. `compare`, `admit` sobre o histórico do `watch` e `watch` a 1 s (G23-25, G23-28, G23-31, G23-32).
7. Persistência por eventos, conforme D-0061 (G23-24).
8. Regressão Linux; Windows: `uv run pytest`, guardrails, `af resources compare` com `measure-hardware.ps1` novo, matriz KI-0017 (M1–M4) com o usuário.
9. Estado, `docs/runbooks/recursos.md`, CP-0006.
