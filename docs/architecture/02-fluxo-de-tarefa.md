# 02 — Fluxo de uma tarefa (A)

Legenda dos marcadores: **[CP]** checkpoint · **[LOG]** log/evento · **[TEST]** teste · **[RB]** ponto de rollback · **[H]** aprovação humana · **[MS]** troca de modelo · **[PS]** troca de provedor.
Diagrama resumido: `13-diagramas.md` §2 e §3.

## Caminho completo

| # | Etapa | O que acontece | Marcadores |
| --- | --- | --- | --- |
| 1 | **Usuário** | Envia pedido pela CLI (`af ask "..."`) ou UI. | [LOG] `user.message` |
| 2 | **Master Agent** | Classifica a intenção (T0). Se ambíguo, pergunta. Cria `JobRequest` com objetivo, restrições, prazo e orçamento (padrão: custo 0, somente local). | [LOG] `job.created` · [H] esclarecimentos |
| 3 | **Job Manager** | Registra o job em `QUEUED`, prioridade P1 (P0 se o usuário estiver esperando uma resposta curta). | [CP] estado inicial · [LOG] |
| 4 | **Resource Manager** | Admite o planejamento: precisa de 1 slot de agente + modelo de planejamento (EXT permitido ou T2 com lease de GPU). Senão → `WAITING(resources)`. | [LOG] `resource.admit` · [MS] escolhe tier conforme modo |
| 5 | **Planner** | Job → `PLANNING`. Gera `spec.md` + `plan.json` (DAG, `writes`, critérios de aceite, riscos, pontos [H]). Pode criar tasks de Research. | [CP] `plan.v1` · [LOG] `plan.created` |
| 6 | **Aprovação do plano** | Se o plano contém ações R2/R3, novas dependências, custo > 0 ou mais de N tasks (padrão 15), o job fica `BLOCKED(approval)` até o usuário aprovar. | [H] |
| 7 | **Job Manager** | Job → `RUNNING`. Cria o branch `af/<job>/integration` no repo do projeto. Para cada task pronta (dependências ok): pede admissão, obtém lock dos `writes`, cria o worktree `af/<job>/<task>` e lança o `agent-runner`. | [RB] branch base registrado · [CP] · [LOG] `task.started` |
| 8 | **Agentes especializados** | Coder/DB/UI executam em passos. A cada passo: `ContextPack` → Model Router → Provider Router → resposta → ferramenta (via Toolbox + política) → journal → commit/checkpoint. | [CP] por passo · [LOG] por chamada · [MS]/[PS] conforme abaixo |
| 9 | **QA** | Ao terminar a task: lint + testes no sandbox. Aprovado → task `COMPLETED`. Reprovado → evento `qa.failed`. | [TEST] · [LOG] `qa.*` |
| 10 | **Debug** | Em `qa.failed`: até 3 tentativas com tier crescente (T1→T2→EXT se permitido). Cada tentativa é um checkpoint. Esgotou → task `BLOCKED(needs_human)` ou replanejamento. | [CP] · [RB] volta ao commit anterior à tentativa · [MS] · [TEST] |
| 11 | **Integração** | Job Manager faz merge das tasks concluídas no branch de integração (em ordem do DAG). Após cada merge: QA de integração. Conflito → Coder tenta 1 vez → senão `BLOCKED`. | [RB] merge revertível · [TEST] · [CP] |
| 12 | **Security** | Portão sobre o diff total da integração: segredos, dependências, análise estática. Bloqueante → volta para Debug/Coder. | [TEST] · [LOG] auditoria |
| 13 | **Build** | Build reproduzível no sandbox. Falha → Debug. | [TEST] · [CP] hash dos artefatos |
| 14 | **Entrega** | Master apresenta o resumo, diff, relatório de QA/Security e artefatos. **Merge em `main`, push, tag, publicação ou deploy exigem [H].** | [H] · [CP] marco `CP-NNNN` · [LOG] |
| 15 | **Handoff** | Atualiza `handoff.md` do projeto e os arquivos de estado; o job vira `COMPLETED`. Worktrees são removidos (branches ficam). | [CP] · [LOG] `job.completed` |

## Onde entram trocas de modelo [MS]

- **Etapa 4/8:** o Model Router escolhe o tier conforme o modo do Resource Manager (ex.: FOREGROUND limita a T1 local).
- **Etapa 10:** escalonamento de tier a cada tentativa do Debug.
- **Contexto grande demais** para o modelo atual → reempacotamento com resumo; se ainda não couber → modelo com janela maior.
- **Preempção de GPU** (usuário começou a jogar/usar a GPU) → o modelo é descarregado; a task vai para `PAUSED` ou é redirecionada para EXT (se permitido).
- Toda troca gera **[CP]** antes e evento `model.swapped`.

## Onde entram trocas de provedor [PS]

- Provedor com cota esgotada/limite de taxa → marcado `exhausted` até `reset_at`; o router tenta outro **compatível e permitido**; se não houver → task em `WAITING(provider_quota)` com retomada agendada.
- Falha de autenticação → `BLOCKED(credentials)` ([H]).
- Queda de rede → retries com backoff (3×); depois `WAITING(network)`, com sonda a cada 60 s.
- Toda troca: **[CP]** + `provider.switched` + contexto preservado no `ContextPack`.

## Onde entra o rollback [RB]

| Nível | Mecanismo |
| --- | --- |
| Passo | Descartar alterações não commitadas no worktree da task → voltar ao último commit do passo. |
| Task | Remover worktree/branch da task; recriar a partir do branch de integração. |
| Integração | `git revert` do merge (nunca reescrever histórico compartilhado). |
| Job | Branch de integração descartado; `main` intacto porque só recebe merge com [H]. |
| Fábrica | Checkpoint de marco `CP-NNNN`: commit + snapshot do banco (`VACUUM INTO`). |
