# PROJECT_STATE.md — Estado atual

| Campo | Valor |
| --- | --- |
| Projeto | App Factory |
| Inicializado em | 2026-09-26 13:13:26 -03:00 (`git init`) |
| Último commit | `683b9e2` — `docs: approve Phase 2.2 blocking decisions` (= `origin/main`); implementação da 2.2 **não commitada** |
| Checkpoints | `CP-0001` (Fase 0) · `CP-0002` (Fase 1, `4082457`) · `CP-0003` (Fase 1.1, `40d4d79`) · `CP-0004` (Fase 2.1, **validado em `4373c65`**) · `CP-0005` (Fase 2.2, **pronta para commit** — `phase_2_2_ready_for_commit`; validação pós-commit pendente) |
| Fase atual | **Fase 2.2 — Guardrails e segurança de execução** |
| Status da fase | **IMPLEMENTADA, VALIDADA NO WINDOWS E PRONTA PARA COMMIT** (D-0048 a D-0057) sobre a base `683b9e2`. Falta: revisão, commit/push e validação pós-commit do CP-0005 (D-0011) |
| Fase anterior | Fase 2.1 — Fundação: Job Manager — **concluída e validada** (CP-0004) |
| Job Manager | **Implementado e validado** (`src/appfactory/`, somente biblioteca padrão) |
| Testes | 2.1: 58 no Windows (validados). **2.2: 164 testes (58 da 2.1 + 106 novos) OK em Linux, Python 3.10–3.13 (`unittest`; 10 pulados: 7 guardrails `pending`, 2 que exigem pytest, 1 só-Windows). **Windows real (CPython 3.13.14): `uv run pytest` 157 passed, 7 skipped, 0 failed; guardrails 21 passed, 7 skipped** (correção 8.3 validada).** |
| Próximo estágio | Revisão → commit/push (usuário) → validação pós-commit (CP-0005 `validated_commit`). P-11 e P-08 decididas (D-0056, D-0057); pendências não bloqueantes P-04, P-09, P-10, P-12, P-13, P-14 seguem abertas (escolhas provisórias em D-0055) |
| Última atualização | 2026-09-27 04:45 -03:00 |

## Fase 2.2 — implementação

- [x] Caminhos protegidos (`config/policies/protected-paths.yaml`) e política de arquivos (`security/paths.py`)
- [x] Verificador de diff com distinção fábrica × projeto (`security/diff_guard.py`, D-0053)
- [x] CommandPolicy + ambiente limpo (`security/command_policy.py`, `config/policies/commands.yaml`)
- [x] Contrato de sandbox, seleção S1h/S2 sem rebaixamento, S1h/S2 **falhando fechados** (`security/sandbox/`)
- [x] Auditoria `audit.jsonl` com cadeia de hashes (`logs/audit.py`); STOP auditado
- [x] Integração com o Job Manager (`hold_attempt`, `record_violation`, STOP da fábrica no `should_stop`; D-0055)
- [x] STOP conforme D-0054 (T0 persistido; `terminate` ≤ T0 + 30 s; fim ≤ T0 + 40 s; sondagem ≤ 1 s)
- [x] Toolbox mínimo `fs.py`/`shell.py` (D-0050); autorização em memória (`core/auth.py`)
- [x] CLI `af guard`, `af audit`, `af guardrails`; manifesto protegido dos guardrails (D-0048)
- [x] Testes G22-01…G22-54 e critérios AC em Linux (3.10–3.13)
- [x] **Usuário:** `uv run pytest` (157 passed, 7 skipped, 0 failed) e o comando fixo dos guardrails (21 passed, 7 skipped) no Windows, CPython 3.13.14
- [ ] **Usuário:** commit e push

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
