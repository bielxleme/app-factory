# 06 — Provider Router e Model Router (E)

**Revisão 1.1 (2026-09-26):** classificação explícita de modelos, registro de posse e regra de custo *fail-closed* (N5). Decisões D-0033 e D-0034.

Diagrama: `13-diagramas.md` §5.

## 1. Separação de responsabilidades

- **Model Router:** *o que* usar. Tipo de tarefa → perfil (tier, janela de contexto, capacidades) → lista ordenada de modelos candidatos, filtrada pelo modo de recursos.
- **Provider Router:** *onde e se pode* usar. Para cada candidato, escolhe o provedor/endpoint permitido pela política (custo, privacidade, cotas, saúde), executa e faz failover.

## 2. Classes de modelo

| Classe | Critério | Uso pela fábrica |
| --- | --- | --- |
| **LOCAL_VERIFICADO** | Está em `config/models.yaml → local_allowlist` com registro de verificação: nome, *digest*, data, método (`ollama show <modelo>` sem origem remota **e** `/api/ps` mostrando execução local em GPU/CPU) | Único tipo que pode ser tratado como local (`privacy: local`, `cost_class: local`) |
| **CLOUD** | Nome termina em `-cloud`, ou metadados indicam origem remota, ou tem o mesmo *digest* de um modelo cloud | Externo: provedor `ollama-cloud` (`privacy: external`, desligado por padrão) |
| **DESCONHECIDO** | Qualquer outro modelo descoberto (`/api/tags`) sem verificação | **Não usado.** Tratado como externo + desligado até ser verificado por um humano |
| **DE TERCEIROS (carregado)** | Modelo presente no `/api/ps` que **não** consta no registro de posse da fábrica | Nunca descarregado pela fábrica; sua VRAM conta como `vram_terceiros` (05 §1.1) |

A classificação é **por verificação real**, nunca por suposição de nome ou tamanho. Nenhum modelo está verificado ainda: a verificação acontece na fatia 2.5, com o usuário.

### 2.1 Registro de posse (ownership)

Tabela `model_loads(model, digest, loaded_at, loaded_by_factory, last_call_at, expected_expires_at)`:

- A fábrica registra cada modelo que **ela** carregou. Só esses podem ser descarregados por ela (`keep_alive: 0`).
- Se o `expires_at` visto no `/api/ps` passar do esperado pela fábrica, outra ferramenta usou o modelo: ele vira **compartilhado** e a fábrica não o descarrega (só deixa de usá-lo). Heurística a validar na 2.5.
- Em nenhum modo (inclusive CRITICAL e STOP) a fábrica descarrega modelos de terceiros.

## 2.2 Catálogo observado (`ollama list`, 2026-09-26) — situação de verificação

| Modelo | Tamanho em disco | Tier pretendido | Uso sugerido | Classe atual |
| --- | --- | --- | --- | --- |
| `qwen3.5:0.8b` | 1,0 GB | T0 | classificação de intenção, roteamento, resumos curtos, commit messages | DESCONHECIDO (verificar) |
| `qwen3.5:2b` | 2,7 GB | T1 | Master Agent, resumos, triagem de falhas | DESCONHECIDO (verificar) |
| `qwen3.5:4b` | 3,4 GB | T1 | código simples, testes, documentação | DESCONHECIDO (verificar) |
| `qwen3:8b` | 5,2 GB | T2 | planejamento local, raciocínio, código (GPU exclusiva; ctx 8k) | DESCONHECIDO (verificar) |
| `qwen3-coder:latest` | 5,2 GB (listado) | — | código | **CLOUD até prova em contrário**: mesmo ID do `:480b-cloud` (KI-0009); só muda de classe após verificação real |
| `qwen3-coder:480b-cloud` | — | EXT | código de alta qualidade | **CLOUD** (externo, cota, desligado) |

Tamanho em disco ≠ VRAM em uso. A VRAM real (pesos + KV cache) será medida na Fase 2 e gravada em `model_profiles`.

## 3. Perfis de tarefa (`config/models.yaml`)

Os candidatos abaixo são **pretendidos**: só entram em uso depois de estarem em `local_allowlist` (LOCAL_VERIFICADO). Enquanto um candidato não estiver verificado, ele é ignorado e o próximo é tentado; sem nenhum → `WAITING(resources)` ou EXT permitido.

| `task_type` | Perfil | Candidatos (ordem) |
| --- | --- | --- |
| `intent.classify`, `route` | T0, ctx 4k, JSON | qwen3.5:0.8b |
| `chat.master`, `summarize` | T1, ctx 8k | qwen3.5:2b → qwen3.5:4b → EXT(se permitido) |
| `plan.create`, `architect` | alto, ctx ≥ 16k | EXT(se permitido) → qwen3:8b (ctx 8k, plano fatiado) |
| `code.small` | T1/T2 | qwen3.5:4b → qwen3:8b → (modelo de código local, se algum for verificado) |
| `code.medium` | T2/EXT | (modelo de código local verificado) → qwen3:8b → EXT(se permitido) |
| `debug.escalate` | escalonado | T1 → T2 → EXT |
| `review.security` | T2 + scanners | qwen3:8b + ferramentas determinísticas |
| `embed` (futuro) | T0 embeddings | a definir (nenhum instalado) |

## 4. Registro de provedores (`config/providers.yaml`, sem chaves)

```yaml
- id: ollama-local
  kind: ollama
  base_url: http://127.0.0.1:11434
  cost_class: local        # local | free | free_tier | paid
  privacy: local           # local | external
  concurrency: 1           # GPU única
  models: allowlist        # SOMENTE config/models.yaml -> local_allowlist (nunca "auto")
- id: ollama-cloud
  kind: ollama
  base_url: http://127.0.0.1:11434
  model_filter: "*-cloud"   # + modelos com digest de modelo cloud
  cost_class: paid         # até o usuário confirmar o plano (fail-closed)
  privacy: external
  enabled: false           # só com consentimento explícito
- id: <externo-exemplo>
  kind: openai_compatible
  base_url: <url>
  secret_ref: secret://providers/<id>/api_key
  cost_class: paid
  privacy: external
  enabled: false
  budget: { monthly_limit: 0, per_job_limit: 0, currency: USD }
```

## 5. Algoritmo de roteamento

1. **Filtrar** candidatos: classe do modelo (só LOCAL_VERIFICADO vai para `ollama-local`; CLOUD/DESCONHECIDO nunca são tratados como locais) · capacidade exigida (tools/JSON/visão/janela) · `enabled` · política de privacidade do job (`local_only` é o padrão para código do usuário) · custo (`paid` só se o orçamento > 0 **e** houver aprovação [H] válida para o job) · saúde (não `exhausted`/`down`) · admissão de GPU (se local).
2. **Pontuar:** adequação ao tier (peso 0,4) + custo (local/free melhor, 0,25) + latência histórica (0,15) + cota restante (0,1) + carga local atual (0,1).
3. **Executar** com timeout (padrão 120 s local, 90 s externo) e streaming salvo em arquivo parcial.
4. **Classificar erro e reagir:**

| Erro | Ação | Estado |
| --- | --- | --- |
| Transitório (5xx, timeout, conexão) | Retry 3× com backoff exponencial (2, 8, 30 s) + jitter | mantém |
| Limite de taxa (429) com `retry-after` curto (≤ 60 s) | espera e repete | mantém |
| Cota esgotada / limite diário | provedor → `exhausted` até `reset_at`; tenta próximo candidato compatível **e permitido**; se nenhum → task `WAITING(provider_quota, retry_at=reset_at)` | registra motivo |
| Autenticação/autorização | provedor → `down(auth)` | `BLOCKED(credentials)` |
| Contexto excede a janela | reempacota com resumo (Memory) → modelo de janela maior → senão falha a task com motivo | — |
| Recusa de conteúdo / política | registra; tenta outro provedor **só** se a política permitir; senão `BLOCKED(needs_human)` | — |
| Resposta inválida (JSON quebrado) | 1 reparo automático → 1 retry → escalonamento de tier | — |
| GPU preemptada (CONTENTION/CRITICAL) | libera o lease; `WAITING(resources)` ou EXT se permitido (`PAUSED` só em CRITICAL/STOP, 05 §3) | — |

## 6. Preservação de contexto e trabalho

- Toda chamada parte de um **`ContextPack` persistido** (arquivo) → trocar de provedor = renderizar o mesmo pack no formato do novo provedor.
- Respostas em streaming são gravadas incrementalmente (`responses/<call-id>.partial`).
- Checkpoint **antes** de cada troca de provedor/modelo; evento `provider.switched` com motivo.
- O `HANDOFF` do job registra qual provedor/modelo produziu cada artefato (proveniência).

## 7. Regras de custo (inegociáveis)

1. Orçamento padrão = **0**. Provedores `paid` vêm `enabled: false`.
2. Habilitar um provedor pago exige: o usuário editar a configuração **e** aprovar por job ([H]) com estimativa de custo.
3. O router **nunca** troca automaticamente de um provedor gratuito para um pago, nem quando o gratuito esgota: nesse caso a task vai para `WAITING`.
4. Uso é contabilizado por chamada (`provider_usage`: tokens, custo estimado, job).
5. Limite atingido → bloqueia novas chamadas pagas imediatamente.
6. **Fail-closed:** provedor **ou ferramenta** sem `cost_class`, ou com valor desconhecido, é tratado como `paid` + `enabled: false`. O mesmo vale para `privacy` ausente (= `external`).
7. Modelos CLOUD ou DESCONHECIDOS nunca são usados sob política `local_only`.

## 8. Ferramentas gratuitas e novos provedores

- Ferramentas (busca web, APIs públicas) usam a mesma interface `Provider` com `kind: tool`, com `cost_class` e `privacy` **obrigatórios** (ausente = pago/externo/desligado).
- Novo provedor = novo adaptador implementando `Provider.generate/stream/embed/health/quota` + entrada no YAML. Nenhuma outra parte do sistema muda.

## 9. Instalação do Ollama (decisão adiada)

- A fábrica **não altera** a instalação do Ollama, suas variáveis nem a pasta de modelos.
- Migrar os modelos para `D:` (`OLLAMA_MODELS`) é uma **decisão futura do usuário** (D-0034, KI-0008).
- Recomendações de `OLLAMA_MAX_LOADED_MODELS`/`OLLAMA_NUM_PARALLEL` continuam só como recomendação (afetam outras ferramentas do usuário).
