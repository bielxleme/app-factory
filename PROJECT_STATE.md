# PROJECT_STATE.md — Estado atual

| Campo | Valor |
| --- | --- |
| Projeto | App Factory |
| Inicializado em | 2026-09-26 13:13:26 -03:00 (`git init`) |
| Último commit | `4082457` — `docs: define App Factory architecture (Phase 1)` (= `origin/main`) |
| Checkpoints | `CP-0001` (Fase 0, `5aa9709`) · `CP-0002` (Fase 1, **validado em `4082457`**) · `CP-0003` (Fase 1.1, **pendente de commit**) |
| Fase 1 | **CONCLUÍDA e validada** (`4082457`) |
| Fase atual | **Fase 1.1 — Revisão e correção documental da arquitetura** |
| Status da fase | **CONCLUÍDA — aguardando revisão e commit do usuário** |
| Arquitetura | Especificação v1.1 em `docs/architecture/` (16 documentos). **Nenhum código de produção implementado.** |
| Hardware | Medido em 2026-09-26 16:17 -03:00 (`RESOURCE_POLICY.md`) |
| Próximo estágio | Fase 2 — Implementação, fatia 2.1 (só com nova instrução do usuário) |
| Última atualização | 2026-09-26 18:15 -03:00 |

## Fase 1.1 — achados da revisão técnica corrigidos

- [x] N1 — Segurança do código não confiável (S1h, usuário dedicado, Job Object, tokens, STOP, aprovações, npm/pip, S2)
- [x] N2 — Infraestrutura protegida ampliada + rejeição automática
- [x] N3 — Ciclo de vida do daemon (`15-daemon.md`)
- [x] N4 — GPU no Windows/WDDM
- [x] N5 — Classificação e posse de modelos do Ollama
- [x] N6 — Estado versionado × operacional
- [x] N7 — Contradições resolvidas (CPU, BATTERY, SQLite, `writes`, locks, integração)
- [x] N8 — Fechamento da Fase 1 (CP-0002 validado, decisões confirmadas, CP-0003)
- [ ] Commit da Fase 1.1 (usuário)

## O que NÃO existe ainda (proposital)

Código dos agentes, daemon, Job Manager, Resource Manager, Toolbox, routers, `pyproject.toml`, `config/`. Usuário `afrunner`, ACLs, tarefa de logon e mudanças no Ollama: **não feitos** (serão ações do usuário na Fase 2).
