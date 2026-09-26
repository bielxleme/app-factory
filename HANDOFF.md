# HANDOFF.md — Ponto de parada

**Atualizado em:** 2026-09-26 · **Por:** Claude (Cowork)

## Situação
Fase 0 **NÃO concluída ainda.** Estrutura criada e verificada; falta o usuário executar commit e push no WSL.

## Onde parei
1. Arquivos de estado, `.gitignore`, `.gitattributes`, `.appfactory/job.json` e `.appfactory/checkpoints/.gitkeep` criados.
2. `git init -b main` e `origin` configurados. Nenhum commit ainda.
3. Remote verificado para leitura (existe e está vazio).

## Próxima ação (usuário, no WSL)
```bash
cd /mnt/d/Claude/app-factory
git add . && git commit -m "chore: initialize App Factory"
git push -u origin main
git status && git log --oneline -1
```

## Depois disso (próxima IA)
- Conferir o push (`git ls-remote origin` deve mostrar `refs/heads/main` com o hash do commit).
- Criar `.appfactory/checkpoints/CP-0001-fase0.json`, atualizar este arquivo, `PROJECT_STATE.md`, `TASK_QUEUE.md`, `TEST_STATUS.md`, `job.json`, e commitar (`chore: add Phase 0 checkpoint`).
- **Não iniciar a Fase 1** sem nova instrução do usuário.
