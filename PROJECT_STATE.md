# PROJECT_STATE.md — Estado atual

| Campo | Valor |
| --- | --- |
| Projeto | App Factory |
| Inicializado em | 2026-09-26 13:13:26 -03:00 (`git init`) |
| Último commit | `b0a80e5` — `chore: validate Phase 2.1 checkpoint` (= `origin/main`) |
| Checkpoints | `CP-0001` (Fase 0) · `CP-0002` (Fase 1, `4082457`) · `CP-0003` (Fase 1.1, `40d4d79`) · `CP-0004` (Fase 2.1, **validado em `4373c65`**) |
| Fase atual | **Fase 2.2 — Guardrails e segurança de execução** |
| Status da fase | **ESPECIFICAÇÃO PRONTA E DECISÕES BLOQUEANTES APLICADAS** (`docs/specs/fase-2.2-guardrails-e-seguranca.md`; D-0048 a D-0054, 2026-09-27) — implementação ainda não iniciada |
| Fase anterior | Fase 2.1 — Fundação: Job Manager — **concluída e validada** (CP-0004) |
| Job Manager | **Implementado e validado** (`src/appfactory/`, somente biblioteca padrão) |
| Testes | **58 testes passaram no Windows** (`uv run pytest`, CPython 3.13.14, pytest 9.1.1 — informado pelo usuário) e 58/58 em Linux (Python 3.10–3.13) |
| Próximo estágio | Commit da documentação da 2.2 (usuário); depois implementação da 2.2 na ordem do §10 da especificação — só com nova instrução. Pendências não bloqueantes: P-04, P-08…P-14 |
| Última atualização | 2026-09-27 00:40 -03:00 |

## Fase 2.1 — critérios

- [x] Identidade, estados (+`STOPPING`/`STOPPED`), transições controladas e registradas
- [x] `COMPLETED` só após validação aprovada
- [x] SQLite como fonte da verdade; fila persistente; checkpoints atômicos; retomada após queda
- [x] STOP de job gracioso e STOP da fábrica persistente
- [x] Recuperação de órfãos; 1 RUNNING por projeto; posse exclusiva com fencing; locks por projeto; histórico por job; CLI mínima
- [x] Cenários de aceite automatizados (queda→recuperação→retomada→COMPLETED; RUNNING→STOPPING→STOPPED)
- [x] `uv run pytest` no Windows: 58 passaram (KI-0018 resolvido)
- [x] Commit `4373c65` sincronizado com `origin/main`; CP-0004 validado

## Pendências que permanecem (documentadas)

- **KI-0019:** sem daemon nem Job Objects — recuperação via `af recover`; processo mudo perde a posse por *fencing*, mas não é encerrado.
- **KI-0020:** escritor único do SQLite ainda transitório (vários processos com `BEGIN IMMEDIATE`, D-0043).

## Fora do escopo da 2.1 (proposital)

Daemon e Job Objects (fatia 2.4), API local e tokens, agentes, sandbox S1h/S2, usuário `afrunner`, Resource Manager, routers/Ollama, navegador, mídia, Evolution. **A App Factory completa não foi implementada.** Nada foi alterado no Ollama, no Windows ou fora do repositório.
