# 04 — Execução paralela (C)

Diagrama: `13-diagramas.md` §7.

## 1. Quando paralelizar

- Tasks do DAG **sem dependência entre si** e com conjuntos `writes` **disjuntos**.
- Trabalho I/O-bound: Research, chamadas a provedores externos, leitura/indexação.
- Suítes de teste independentes (limitadas por slots de processo pesado).
- Agentes que usam **modelos externos** (não disputam a GPU).

## 2. Quando executar em sequência

- Tasks que escrevem nos mesmos arquivos/módulos.
- **Hot files** (sempre serializados por uma task de integração): `package.json`, lockfiles (`uv.lock`, `package-lock.json`), `pyproject.toml`, pasta de migrações, configurações de raiz, arquivos de rotas centrais.
- Instalação de dependências, migrações de banco, build/release, merges.
- **Qualquer inferência na GPU local:** 1 lease de GPU. Vários agentes podem estar "rodando", mas as chamadas locais entram numa fila única.
- Evolution Agent (sempre sozinho).

## 3. Evitar dois agentes no mesmo arquivo

1. O Planner declara `writes` (globs) por task. Task sem `writes` = somente leitura.
2. Antes de iniciar, o Job Manager adquire **locks de glob** na tabela `locks` (transação SQLite). Há conflito quando dois globs se sobrepõem (verificado com correspondência de caminhos normalizados, sem diferenciar maiúsculas de minúsculas no Windows).
3. Conflito → a segunda task fica `WAITING(lock)`.
4. O Toolbox **impõe** o `writes`: escrita fora do conjunto é negada e gera `task.scope_violation` (o agente pede replanejamento).
5. Locks têm lease atrelado ao da task: se o runner morrer, o lock é liberado quando o lease vence.

## 4. Branches e worktrees

```
workspaces/<projeto>/                 repo do projeto (branch main)
  branch af/<job>/integration         criado a partir de main no início do job
workspaces/_worktrees/<projeto>/<task>/
  branch af/<job>/<task>              criado a partir de af/<job>/integration
```

- 1 worktree por task de escrita; tasks somente leitura usam o worktree de integração em modo leitura.
- Worktrees são removidos após o merge da task; branches ficam até o job terminar (e mais 7 dias).
- Commits de agentes: autor `App Factory Agent <agent@appfactory.local>` + trailer `AF-Task: <task-id>`; o usuário continua autor dos commits que ele mesmo fizer.

## 5. Merge

1. Task `COMPLETED` (QA ok) → fila de integração.
2. O **Integrador** (função do Job Manager) faz merge das tasks **uma de cada vez**, na ordem topológica do DAG, com `--no-ff` (rastreável e revertível).
3. Após cada merge: QA de integração rápido (lint + testes afetados). Falhou → `git revert` do merge + task volta para Debug.
4. Fim do job: QA completo + Security + Build no branch de integração → apresentação ao usuário → merge em `main` **somente com [H]**.

## 6. Conflitos

| Situação | Ação |
| --- | --- |
| Conflito textual no merge | Coder "resolvedor" recebe os dois lados + intenção das tasks; 1 tentativa; QA obrigatório depois. |
| Falhou a resolução | `BLOCKED(conflict)` com o diff para o usuário. |
| Conflito semântico (testes quebram após merge limpo) | Revert do merge + Debug na task mais recente. |
| Colisão de hot file | Não deveria acontecer (serialização); se acontecer, registrar KI e replanejar. |

## 7. Limites de concorrência

| Recurso | FOREGROUND (usuário ativo) | BACKGROUND (ocioso) | BATTERY | CONTENTION | CRITICAL |
| --- | --- | --- | --- | --- | --- |
| Agentes simultâneos (runners) | 2 | 4 | 1 | 2 | 0 novos |
| Lease de GPU local | 1 (só T0/T1) | 1 (até T2) | 0 (T0 na CPU) | 0 | 0 |
| Processos pesados (build/teste/navegador/container) | 1 | 2 | 0 | 1 | 0 |
| Navegadores Playwright | 1 | 1 | 0 | 1 | 0 |
| Chamadas externas concorrentes | 2 | 4 | 1 | 2 | 0 |

## 8. Fórmula de admissão (limite baseado em CPU/RAM/VRAM)

```
slots_ram   = floor( (ram_disponivel_gb - reserva_ram_gb[modo]) / 0.4 )   # ~0,4 GB por runner + ferramentas
slots_cpu   = 0 se cpu_media_60s > 85%  senão  (1 se > 70%  senão  ilimitado)
max_agentes = min( limite_modo[modo], slots_ram, slots_cpu )
admitir_GPU = lease_livre E vram_livre_mib - vram_estimada(modelo, ctx) >= reserva_vram_mib[modo]
admitir_pesado = pesados_ativos < limite_pesado[modo] E ram_disponivel_gb >= reserva_ram_gb[modo] + 1.0
```

`reserva_ram_gb`: FOREGROUND 3,0 · BACKGROUND 2,0 · BATTERY 3,0. `reserva_vram_mib`: FOREGROUND 768 · BACKGROUND 384.
**Com o baseline medido (5,2 GB disponíveis, usuário ativo):** `slots_ram = floor((5,2−3,0)/0,4) = 5` → limitado pelo modo a **2 agentes**.
