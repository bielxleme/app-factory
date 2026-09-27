# HANDOFF.md — Ponto de parada

**Atualizado em:** 2026-09-27 00:40 -03:00 · **Por:** Claude (Cowork)

## Situação
Fase 2.1 validada e commitada (`b0a80e5`, sincronizado com `origin/main`). **Fase 2.2 (Guardrails e segurança de execução): especificação pronta e as 7 decisões bloqueantes aprovadas pelo usuário e aplicadas à documentação (D-0048 a D-0054).** Nenhum código de produção, teste, configuração, usuário Windows, ACL, Job Object ou Docker foi criado ou alterado; o Job Manager da 2.1 e seus testes estão intactos.

## Decisões aplicadas (2026-09-27)
- D-0048: guardrails sem componente ficam `pending` no manifesto protegido; **`pending` nunca é aprovação**; Evolution só com I1–I7 `active`.
- D-0049: arquivos `.yaml` no subconjunto JSON, lidos com `json` (sem dependência nova).
- D-0050: Toolbox mínimo (`fs.py`, `shell.py`) na 2.2; restante na 2.8.
- D-0051: núcleo do Job Manager (`store`, `manager`, `executor`, `states`, `handlers`), `core/paths|clock|procinfo`, `cli/main.py` e futuros `state_machine`, `jobobjects`, `core/api` protegidos.
- D-0052: `config/**` inteiro protegido.
- D-0053: lista completa só no repositório da fábrica; projetos gerados com regras próprias; tipo de repositório decidido por código confiável (na dúvida, fábrica).
- D-0054: STOP com `terminate` ≤ T0 + 30 s e encerramento total ≤ T0 + 40 s, T0 persistido no SQLite.

## Arquivos alterados (não commitados)
`DECISIONS.md`, `AGENTS.md`, `CHANGELOG.md`, `PROJECT_STATE.md`, `TASK_QUEUE.md`, `HANDOFF.md`, `TEST_STATUS.md`, `docs/architecture/{README,01-componentes,05-resource-manager,08-seguranca,09-autoevolucao,10-diretorios,11-tecnologias,14-plano-fase-2,15-daemon}.md`, `docs/specs/fase-2.2-guardrails-e-seguranca.md` (novo).

## Pendências
- Não bloqueantes da 2.2: P-04, P-08, P-09, P-10, P-11, P-12, P-13, P-14 (especificação §9).
- KI-0019/KI-0020 (2.4); KI-0014/KI-0016 (2.6).

## Regras para a próxima IA
- Ler `AGENTS.md`, `DECISIONS.md` (D-0048 a D-0054) e a especificação da 2.2.
- Os arquivos do núcleo do Job Manager e a CLI agora são protegidos (D-0051): só sessões dirigidas pelo usuário os alteram, com registro.
- **Não implementar a 2.2** sem nova instrução do usuário.

## Próxima ação (usuário, PowerShell em `D:\Claude\app-factory`)
```powershell
git status
git add .
git commit -m "docs: approve Phase 2.2 blocking decisions"
git push
```
