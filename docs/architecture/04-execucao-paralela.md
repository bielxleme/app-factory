# 04 — Execução paralela (C)

**Revisão 1.1 (2026-09-26):** regra de `writes`, locks por projeto, 1 job RUNNING por projeto e worktree de integração definidos (N7, D-0036); limiares de CPU passam a vir só de `05-resource-manager.md` (D-0038).

Diagrama: `13-diagramas.md` §7.

## 0. Regra de concorrência entre jobs (Fase 2)

- **No máximo 1 job `RUNNING` por projeto** (`workspaces/<p>`). Outros jobs do mesmo projeto ficam `QUEUED` (motivo `project_busy`).
- **Jobs de projetos diferentes podem rodar em paralelo**, dentro dos limites do Resource Manager.
- Preparação para o futuro: locks e worktrees já são **por projeto** (§3); liberar mais de um job por projeto exigirá apenas mudar `max_running_jobs_per_project` (hoje 1, protegido) depois de uma decisão registrada e de testes de conflito entre jobs.

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

1. O Planner declara `writes` por task usando **somente** duas formas: (a) **arquivo explícito** (`src/api/health.py`) ou (b) **prefixo de pasta** `dir/**` (`src/ui/**`). Curingas arbitrários (`*.py`, `src/**/test_*.py`, `?`) são **proibidos**. Task sem `writes` = somente leitura.
2. Normalização: caminho relativo à raiz do projeto, separador `/`, sem `.`/`..`, **sem diferenciar maiúsculas de minúsculas** (Windows); symlinks/junctions resolvidos e recusados se saírem do projeto.
3. Sobreposição (decidível por comparação de prefixo): arquivo×arquivo = iguais; arquivo×`d/**` = o arquivo começa com `d/`; `d1/**`×`d2/**` = um prefixo contém o outro.
4. Locks são **por projeto**: tabela `locks(project, path_spec, task_id, acquired_at)`. Antes de iniciar, o Job Manager adquire **todos** os `writes` da task numa única transação (tudo ou nada → sem deadlock).
5. Conflito → a task fica `WAITING(lock)`.
6. O Toolbox **impõe** o `writes`: escrita fora do conjunto é negada e gera `task.scope_violation` (o agente pede replanejamento). Em S1h, a ACL só concede escrita no worktree da própria task (08 §4.2).
7. Locks seguem a vida da task: são liberados quando a tentativa termina ou é declarada `interrupted` após a verificação de vida (15 §5) — nunca apenas porque um relógio passou.

## 4. Branches e worktrees

```
workspaces/<projeto>/                 repo do projeto (branch main)
  branch af/<job>/integration         criado a partir de main no início do job
workspaces/_worktrees/<projeto>/_integration-<job>/
  branch af/<job>/integration         worktree de integração (merges, QA de integração, Security, Build)
workspaces/_worktrees/<projeto>/<task>/
  branch af/<job>/<task>              criado a partir de af/<job>/integration
```

- O checkout principal `workspaces/<projeto>/` permanece em `main` e **não** é usado para trabalho de agentes.
- 1 worktree por task de escrita; tasks somente leitura leem o worktree de integração (sem permissão de escrita).
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
# CPU: limiares canônicos em 05 §4 (> 85%: nenhuma nova admissão; > 70%: no máx. 1 admissão por minuto)
max_agentes = min( limite_modo[modo], slots_ram )     # e respeitando a regra de CPU acima
admitir_GPU = lease_livre E vram_estimada(modelo, ctx) <= vram_disponivel_fabrica   # definida em 05 §1.1 (já desconta reserva e margem)
admitir_pesado = pesados_ativos < limite_pesado[modo] E ram_disponivel_gb >= reserva_ram_gb[modo] + 1.0
```

`reserva_ram_gb`: FOREGROUND 3,0 · BACKGROUND 2,0 · BATTERY 3,0 · CONTENTION 3,0 (D-0072). `reserva_vram_mib`: FOREGROUND 768 · BACKGROUND 384.
**Com o baseline medido (5,2 GB disponíveis, usuário ativo):** `slots_ram = floor((5,2−3,0)/0,4) = 5` → limitado pelo modo a **2 agentes**.
