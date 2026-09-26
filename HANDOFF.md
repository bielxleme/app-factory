# HANDOFF.md — Ponto de parada

**Atualizado em:** 2026-09-26 16:35 -03:00 · **Por:** Claude (Cowork)

## Situação
**Fase 1 (Arquitetura) concluída e aguardando aprovação do usuário para commit.** Nenhum código de produção foi escrito.

## Onde parei
- Especificação completa em `docs/architecture/` (comece por `README.md`).
- Hardware medido e política de recursos em `RESOURCE_POLICY.md`.
- Decisões D-0012 a D-0025 (status "proposta" até o commit).
- `CP-0002-fase1.json` criado com `validated_commit: null`.
- Alterações **não commitadas** (ver `git status`).

## Próxima ação (usuário, PowerShell em `D:\Claude\app-factory`), após revisar
```powershell
git status
git add .
git commit -m "docs: define App Factory architecture (Phase 1)"
git push
git log --oneline -3
```
Depois: a próxima IA preenche `validated_commit` no CP-0002 e muda as decisões D-0012…D-0025 para "ativa" (commit `chore: finalize Phase 1 checkpoint CP-0002`).

## Regras para a próxima IA
- Ler `AGENTS.md` (agora inclui a leitura de `docs/architecture/`).
- Git oficial: PowerShell/Git para Windows (D-0010). WSL/OpenClaw é separado e não deve ser usado.
- Não reinicializar o Git nem criar uma segunda cópia do projeto.
- **Não iniciar a Fase 2** sem nova instrução do usuário.

## Próximo passo
FASE 2 — Implementação, fatia 2.1 (Fundação), conforme `docs/architecture/14-plano-fase-2.md`.
