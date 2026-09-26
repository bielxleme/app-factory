# Arquitetura da App Factory — Índice

**Versão:** 1.0 (Fase 1) · **Data:** 2026-09-26 · **Status:** proposta aprovável (normativa após o commit)
**Base:** hardware medido em 2026-09-26 16:17 -03:00 (`tools/diagnostics/measure-hardware.ps1`).

Esta pasta é a **especificação normativa** da App Factory. Qualquer IA que for implementar deve segui-la. Mudanças exigem registro em `DECISIONS.md`.

| Doc | Conteúdo | Item do roteiro |
| --- | --- | --- |
| [00-visao-geral.md](00-visao-geral.md) | Princípios, topologia de processos, baseline de hardware | — |
| [01-componentes.md](01-componentes.md) | Os 21 componentes, cada um com os 14 campos | 1–21 |
| [02-fluxo-de-tarefa.md](02-fluxo-de-tarefa.md) | Caminho Usuário → entrega, com checkpoints, logs, testes, rollback, aprovação, troca de modelo/provedor | A |
| [03-jobs.md](03-jobs.md) | Máquina de estados de jobs e tasks, regras, leases | B |
| [04-execucao-paralela.md](04-execucao-paralela.md) | Paralelismo, locks de arquivo, worktrees, merge, limites | C |
| [05-resource-manager.md](05-resource-manager.md) | Política concreta de recursos (modos, limiares, prioridades) | D |
| [06-provider-model-router.md](06-provider-model-router.md) | Roteamento de modelos e provedores, failover, orçamento zero | E |
| [07-persistencia.md](07-persistencia.md) | O que sobrevive a cada tipo de interrupção | F |
| [08-seguranca.md](08-seguranca.md) | Secrets, permissões, sandbox, aprovação, auditoria, rollback | G |
| [09-autoevolucao.md](09-autoevolucao.md) | Evolution Agent e invariantes protegidas | H |
| [10-diretorios.md](10-diretorios.md) | Estrutura completa de diretórios | I |
| [11-tecnologias.md](11-tecnologias.md) | Tecnologias, alternativas, custos, riscos | J |
| [12-contratos.md](12-contratos.md) | Esquemas de dados, eventos, interfaces entre componentes | — |
| [13-diagramas.md](13-diagramas.md) | Os 8 diagramas ASCII obrigatórios | K |
| [14-plano-fase-2.md](14-plano-fase-2.md) | Proposta de fatiamento da implementação (não executar sem instrução) | — |

Convenções de ID: `JOB-YYYYMMDD-NNNN`, `TASK-<job>-NN`, `CP-NNNN`, `EP-NNNN` (proposta de evolução), `D-NNNN` (decisão), `KI-NNNN` (issue).
