# HANDOFF.md — Ponto de parada

**Atualizado em:** 2026-09-26 18:15 -03:00 · **Por:** Claude (Cowork)

## Situação
**Fase 1.1 concluída na documentação e aguardando o commit do usuário.** A Fase 1 está fechada (CP-0002 validado em `4082457`). Nenhum código de produção foi escrito.

## Onde parei
- Achados N1–N8 da revisão técnica corrigidos em `docs/architecture/` (versão 1.1; novo `15-daemon.md`).
- Decisões D-0026 a D-0039 registradas; D-0005 e D-0012 a D-0025 com status atualizado (textos originais preservados).
- `CP-0003-fase1-1.json` criado com `validated_commit: null`.
- Alterações **não commitadas** (ver `git status`).

## Próxima ação (usuário, PowerShell em `D:\Claude\app-factory`), após revisar
```powershell
git status
git add .
git commit -m "docs: revise architecture after Phase 1 review (Phase 1.1)"
git push
git log --oneline -3
```
Depois: a próxima IA preenche `validated_commit` no CP-0003 (commit `chore: finalize Phase 1.1 checkpoint CP-0003`).

## Regras para a próxima IA
- Ler `AGENTS.md` (regras 13–15 novas: código não confiável, estado versionado × operacional, escopo dos caminhos protegidos).
- Git oficial: PowerShell/Git para Windows (D-0010). WSL/OpenClaw é separado e não deve ser usado.
- Não criar usuário Windows, ACLs, tarefas agendadas nem mexer no Ollama sem pedido explícito do usuário.
- **Não iniciar a Fase 2** sem nova instrução do usuário.

## Próximo passo
FASE 2 — Implementação, fatia 2.1 (Fundação), conforme `docs/architecture/14-plano-fase-2.md` (revisão 1.1).
