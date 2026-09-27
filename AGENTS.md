# AGENTS.md — Regras permanentes para qualquer IA

Este arquivo vale para **qualquer IA ou agente** (Claude, Codex, Cursor, modelos locais via Ollama etc.) que trabalhar neste repositório.

## 1. Localização e repositório

- Diretório oficial: `D:\Claude\app-factory` (Windows) = `/mnt/d/Claude/app-factory` (WSL).
- Nunca crie o projeto em outro lugar (ex.: `~/app-factory`).
- Remote oficial: `https://github.com/bielxleme/app-factory` (branch `main`).

## 2. Ordem de leitura ao iniciar uma sessão

1. `AGENTS.md` (este arquivo)
2. `HANDOFF.md` — ponto exato de parada
3. `PROJECT_STATE.md` — fase e progresso
4. `TASK_QUEUE.md` — próximas tarefas
5. `KNOWN_ISSUES.md` e `TEST_STATUS.md`
6. `DECISIONS.md` e `RESOURCE_POLICY.md` antes de decisões técnicas
7. `.appfactory/job.json` e o checkpoint mais recente em `.appfactory/checkpoints/`
8. `docs/architecture/README.md` — especificação **normativa** da arquitetura (antes de implementar qualquer coisa), em especial `08-seguranca.md` e `15-daemon.md`

## 3. Regras de trabalho

1. Não avance de fase sem que a fase atual esteja validada e registrada.
2. Não invente resultados de comandos. Registre saídas reais ou declare explicitamente que algo não foi verificado.
3. Não marque tarefa como concluída sem verificação.
4. Não apague arquivos sem autorização explícita do usuário.
5. Não faça alterações destrutivas (reset --hard, force push, rebase de histórico publicado) sem confirmação.
6. Nunca coloque credenciais, tokens, chaves ou `.env` reais no Git.
7. Não altere arquivos fora do projeto sem necessidade e sem registrar.
8. Registre comandos relevantes em `COMMAND_LOG.md`.
9. Se algo falhar, registre em `KNOWN_ISSUES.md` e informe — não esconda erros.
10. Respeite `RESOURCE_POLICY.md` (medido: RAM 23,7 GB com ~5 GB livres no uso normal; VRAM 6141 MiB; C: com pouco espaço — grave só em D:).
11. Não mude a arquitetura sem registrar a revisão em `DECISIONS.md` e atualizar `docs/architecture/`.
12. Nunca gaste dinheiro (provedores pagos) sem aprovação explícita do usuário.
13. Código gerado por agentes é **não confiável**: nunca o execute como o usuário principal (ver `docs/architecture/08-seguranca.md` §0).
14. **Estado versionado × operacional:** os arquivos desta pasta raiz, `DECISIONS.md` etc. são o estado **versionado** do desenvolvimento da fábrica e são mantidos pelas sessões de desenvolvimento dirigidas pelo usuário. O estado **operacional** da execução de jobs fica em `.appfactory/runtime/**` e `.appfactory/state/**` (ignorados pelo Git) e nunca deve ser commitado.
15. Os caminhos protegidos (`08-seguranca.md` §5.1) valem para os agentes em execução da App Factory e para o Evolution Agent; sessões de desenvolvimento dirigidas pelo usuário podem alterá-los, sempre registrando em `DECISIONS.md`.

## 4. Atualização dos arquivos de estado (ao fim de cada sessão/tarefa)

| Arquivo | Quando atualizar |
| --- | --- |
| `PROJECT_STATE.md` | Mudança de fase, progresso ou situação |
| `TASK_QUEUE.md` | Tarefa criada, iniciada, concluída ou bloqueada |
| `DECISIONS.md` | Toda decisão arquitetural/operacional, com motivo |
| `CHANGELOG.md` | Toda alteração versionada |
| `HANDOFF.md` | **Sempre** ao encerrar a sessão |
| `KNOWN_ISSUES.md` | Bug, limitação ou problema encontrado/resolvido |
| `TEST_STATUS.md` | Todo teste/verificação executado, com resultado real |
| `COMMAND_LOG.md` | Comandos relevantes executados |
| `.appfactory/job.json` | **Somente em marcos** (fim de fase/revisão). O espelho de cada transição de job fica em `.appfactory/runtime/job.json` (ignorado) |
| `.appfactory/checkpoints/` | Ao validar um marco (fim de fase, entrega relevante) |

## 5. Convenções

- Idioma da documentação: português do Brasil.
- Commits: Conventional Commits (`chore:`, `feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
- Checkpoints: `.appfactory/checkpoints/CP-NNNN-<slug>.json` (numeração sequencial).
- Datas: ISO 8601 com fuso (`America/Sao_Paulo`, UTC-3).
- Finais de linha: LF (ver `.gitattributes`).
- Testes: `uv run pytest` (ou `python -m unittest discover -s tests -t .` com `PYTHONPATH=src`). Nenhuma fase é concluída com teste crítico falhando.
- Código Python: sem dependências novas sem decisão registrada (D-0042); configuração do pytest só em `pytest.ini`.
