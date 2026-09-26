# PROJECT_STATE.md — Estado atual

| Campo | Valor |
| --- | --- |
| Projeto | App Factory |
| Inicializado em | 2026-09-26 13:13:26 -03:00 (`git init`) |
| Último commit | `afc1dcc` — `chore: add Phase 0 checkpoint CP-0001` (= `origin/main`) |
| Checkpoints | `CP-0001` (Fase 0, base `5aa9709`) · `CP-0002` (Fase 1, **pendente de commit**) |
| Fase atual | **Fase 1 — Arquitetura** |
| Status da fase | **CONCLUÍDA — aguardando revisão e aprovação do usuário para commit** |
| Arquitetura | **Definida** em `docs/architecture/` (15 documentos). **Nenhum código de produção implementado.** |
| Hardware | **Medido** em 2026-09-26 16:17 -03:00 (ver `RESOURCE_POLICY.md`) |
| Próximo estágio | Fase 2 — Implementação (só com nova instrução do usuário) |
| Última atualização | 2026-09-26 16:35 -03:00 |

## Critérios da Fase 1

- [x] Arquivos de estado e CP-0001 lidos; git verificado
- [x] Ferramentas verificadas (Windows via diagnóstico; VM do Cowork)
- [x] Hardware real medido (CPU, núcleos/threads, RAM total/disponível, GPU, VRAM total/livre, uso atual de CPU/RAM/GPU/VRAM, disco, energia, temperatura)
- [x] 21 componentes definidos, cada um com os 14 campos
- [x] A — fluxo de tarefa · B — jobs · C — paralelismo · D — Resource Manager · E — Provider Router · F — persistência · G — segurança · H — autoevolução · I — diretórios · J — tecnologias · K — 8 diagramas
- [x] L — decisões D-0012 a D-0025 registradas (sem apagar as anteriores)
- [x] M — documentação de estado atualizada
- [ ] N — commit (aguardando aprovação do usuário)

## O que NÃO existe ainda (proposital)

Código dos agentes, Job Manager, Resource Manager, Toolbox, routers, `pyproject.toml`, `config/`. Apenas especificação e o script de diagnóstico.
