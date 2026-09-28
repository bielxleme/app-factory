# PROJECT_STATE.md — Estado atual

| Campo | Valor |
| --- | --- |
| Projeto | App Factory |
| Inicializado em | 2026-09-26 13:13:26 -03:00 (`git init`) |
| Último commit | `f44ac72` — `chore: validate Phase 2.2 checkpoint` (= `origin/main`); implementação da 2.2 em `6fb983c` |
| Checkpoints | `CP-0001` (Fase 0) · `CP-0002` (Fase 1, `4082457`) · `CP-0003` (Fase 1.1, `40d4d79`) · `CP-0004` (Fase 2.1, **validado em `4373c65`**) · `CP-0005` (Fase 2.2, **validado em `6fb983c`**) |
| Fase atual | **Fase 2.3 — Resource Manager — validação no Windows PENDENTE** (D-0058 a D-0074) |
| Status da fase | 2.3: **PENDENTE**. Rodada 2.3b no Windows: 211 passed/7 skipped, guardrails 22/6, M1 e M2 PASS, M3 e M4 não conclusivos (CRITICAL por RAM). Correção D-0075 (Ollama a cada 15 s em segundo plano; `watch` a 1 s) — Linux 223 OK; falta repetir a suíte no Windows e M3/M4 em condições controladas. CP-0006 não gerado; nada commitado. 2.2: concluída e validada (CP-0005) |
| Fase anterior | Fase 2.2 — Guardrails e segurança de execução — **concluída e validada** (CP-0005, `6fb983c`; consolidação `f44ac72`) |
| Job Manager | **Implementado e validado** (`src/appfactory/`, somente biblioteca padrão) |
| Testes | **2.3: Windows 210 passed, 7 skipped (antes de D-0074); guardrails 22/6; Linux 218 OK (10 pulados) em 3.10–3.13 após D-0074.** 2.1: 58 no Windows (validados). **2.2: 164 testes (58 da 2.1 + 106 novos) OK em Linux, Python 3.10–3.13 (`unittest`; 10 pulados: 7 guardrails `pending`, 2 que exigem pytest, 1 só-Windows). **Windows real (CPython 3.13.14): `uv run pytest` 157 passed, 7 skipped, 0 failed; guardrails 21 passed, 7 skipped** (correção 8.3 validada).** |
| Próximo estágio | **Usuário (Windows):** `powershell -ExecutionPolicy Bypass -File .appfactory
untimealidate-2.3c.ps1` (suíte e guardrails após D-0075; M3 e M4 com portão de RAM ≥ 3,0 GB e `qwen3:8b` confirmado). Depois: análise; CP-0006 e commit só se AC23-01 e AC23-08 fecharem |
| Última atualização | 2026-09-27 19:27 -03:00 |

## Fase 2.3 — Resource Manager

- [x] Estado lido (HEAD `f44ac72`, limpo); fontes: `05-resource-manager.md`, 01 §4, 04 §7–8, 06 §2, 12 §6–7, 13 §4, 15 §6, D-0018/D-0028/D-0032/D-0038, `RESOURCE_POLICY.md`, `measure-hardware.ps1` (só leitura)
- [x] Especificação `docs/specs/fase-2.3-resource-manager.md`: escopo E1–E11, componentes, APIs, matriz G23-01…32 + M1–M4, critérios AC23-01…10, pendências P23-01…P23-10, ordem de implementação
- [x] **Usuário:** P23-01…P23-10 decididas (2026-09-27) → D-0058 a D-0067; `05-resource-manager.md` §2 corrigido (D-0062, revisão 1.2)
- [x] Fechamento documental (2026-09-27): fallback `nvidia-smi` explícito e isolado (D-0058); `admit` lê o histórico do `watch`, `watch` a 1 s, `resource.snapshot` append-only (complemento de D-0063); referências a psutil/nvidia-ml-py alinhadas em 01 §4, 05 §1, 11 e 13 §4; `14-plano-fase-2.md` e `CHANGELOG.md` atualizados
- [x] Conflitos do plano resolvidos (D-0070 a D-0072)
- [x] Implementação E1–E10 (D-0073): `config/resources.yaml`, `src/appfactory/resources/**`, CLI `af resources`, guardrail I4 ativo
- [x] Testes em Linux: 217 OK (10 pulados) em Python 3.10, 3.11, 3.12, 3.13; guardrails 22 OK, 6 pulados; `git diff --check` sem erro
- [x] **Usuário (Windows, 2026-09-27):** `uv run pytest` 210 passed/7 skipped; guardrails 22/6; G23-27 ok; `af resources compare` ok; `git diff --check` ok
- [x] **Usuário (Windows):** M1–M4 executados (0 falhas de sonda) — M1 conforme; M2/M3 em CRITICAL por RAM (detecção de CONTENTION ok nas razões); M4 sem modelo no `/api/ps`
- [x] Defeito encontrado e corrigido: uso alheio da GPU pela média de 30 s (D-0074); Linux 218 OK
- [ ] **Usuário (Windows):** repetir `uv run pytest` e guardrails após D-0074 (AC23-01)
- [ ] **Usuário (Windows):** repetir M2–M4 com ≥ 3 GB de RAM disponível; M4 com modelo local confirmado (AC23-08)
- [ ] CP-0006 — só depois disso

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
- [x] **Usuário:** commit e push — `6fb983c` (validado pós-commit; CP-0005)

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
