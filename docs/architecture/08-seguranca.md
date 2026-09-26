# 08 — Segurança (G)

Diagrama: `13-diagramas.md` §8.

## 1. Níveis de risco das ações

| Nível | Exemplos | Autorização |
| --- | --- | --- |
| **R0** leitura | ler arquivos do workspace, `git status/log/diff`, buscar documentação | automática |
| **R1** escrita reversível e confinada | escrever no worktree da task, commit em `af/*`, rodar testes no sandbox | automática, com log |
| **R2** efeito fora do confinamento ou difícil de reverter | instalar dependência, rede para domínio novo, criar banco/container, `ollama pull`, escrever fora do worktree | Security Agent + política; aprovação humana se a política do projeto não pré-autorizar |
| **R3** irreversível, externo, público ou com custo | merge em `main`, push, tag, publicação, deploy, apagar arquivos/branches do usuário, migração destrutiva, enviar mensagens, usar provedor pago, mudar configuração do sistema | **sempre [H]**, por ação, com expiração |

Ações **proibidas** mesmo com pedido (o agente devolve para o usuário): inserir senhas/cartões/documentos em formulários, criar contas, mexer em configuração de segurança do Windows, desativar antivírus, contornar CAPTCHA, executar binários baixados de fonte não confiável.

## 2. Secrets

- Armazenados no **Windows Credential Manager** via `keyring` (serviço `appfactory`). Fallback: `.env.local` (ignorado pelo Git), só se o usuário escolher.
- A configuração guarda **referências** (`secret://providers/<id>/api_key`), nunca valores.
- Só o Provider Router e o Toolbox (para ferramentas específicas) resolvem segredos, **em memória** e na hora do uso. Agentes e LLMs **nunca** recebem segredos no contexto.
- Variáveis de ambiente de subprocessos são **limpas** (allowlist: `PATH`, `SYSTEMROOT`, `TEMP`, `LANG`, …).
- Redação automática em logs: padrões de chaves conhecidos + valores de todos os segredos registrados + entropia alta em campos sensíveis.
- `gitleaks` roda antes de todo commit de agente e em todo diff de integração; também recomendado como pre-commit do repo da fábrica.
- `.gitignore` bloqueia `.env*`, chaves, `secrets/`, `credentials*.json` (já ativo desde a Fase 0).

## 3. Permissões (capabilities por agente)

Arquivo `config/policies/permissions.yaml` (versionado). Exemplo:

```yaml
coder:
  fs.read:  ["{worktree}/**", "{project}/**"]
  fs.write: ["{worktree}/{task.writes}"]
  shell.exec: { allow: [python, uv, pytest, ruff, node, npm, npx, git], deny_args: ["push", "reset --hard", "clean -fdx"] }
  net: { allow: [] }                  # sem rede por padrão
  git: [status, diff, add, commit, log, show]
research:
  net: { allow: ["docs.python.org", "developer.mozilla.org", "*.readthedocs.io", "github.com", "pypi.org", "npmjs.com"] }
  fs.write: ["{job}/research/**"]
```

O Toolbox aplica a política **antes** de executar (ninguém chama `subprocess` diretamente). Violação → negar + `security.violation` + task `BLOCKED(policy_violation)` na reincidência.

## 4. Sandbox

| Nível | Uso | Isolamento |
| --- | --- | --- |
| **S0** em processo | ferramentas somente leitura | validação de caminho (resolve symlinks/junctions; nega `..` e caminhos fora do escopo) |
| **S1** subprocesso | testes, lint, scripts do projeto confiável | `cwd` = worktree, ambiente limpo, timeout, prioridade BELOW_NORMAL, kill da árvore, monitor de RAM via psutil (mata acima do limite) |
| **S2** container Docker | código/dependências não confiáveis, bancos de dados, builds | só o worktree montado, `--network none` por padrão, `--memory`/`--cpus` limitados, usuário não root, sem montar o Docker socket |

O Windows Home não tem Windows Sandbox/Hyper-V gerenciável; **S2 depende do Docker Desktop** (WSL2). Se o Docker não estiver disponível: tasks que exigem S2 ficam `BLOCKED` (não caem para S1 silenciosamente).

## 5. Filesystem

- Raiz permitida: `D:\Claude\app-factory` (fábrica, `workspaces/`, `.appfactory/`). Tudo fora disso = R2/R3.
- Escrita da fábrica em `C:` é proibida (exceto temporários do sistema).
- Remoção: agentes **não apagam** fora de `.appfactory/jobs/*/tmp` e de worktrees criados pela própria fábrica; apagar arquivos do usuário = R3.
- Caminhos protegidos (`config/policies/protected-paths.yaml`): `config/policies/**`, `src/appfactory/security/**`, `tests/guardrails/**`, `.appfactory/checkpoints/**`, `.git/**`, arquivos de estado da raiz (só o Handoff System escreve).

## 6. Terminal e execução de comandos

- Todos os comandos passam pelo `CommandPolicy`: executável na allowlist, argumentos checados contra padrões negados, `cwd` dentro do escopo, timeout obrigatório.
- Nada de shell interpretado (`shell=True`) por padrão: lista de argumentos. Pipes e redirecionamentos só em comandos pré-aprovados.
- Padrões sempre negados sem [H]: `rm -rf`/`Remove-Item -Recurse` fora do escopo, `git push --force`, `git reset --hard` em branch compartilhado, `format`, `diskpart`, `reg`, `bcdedit`, `Set-ExecutionPolicy`, `netsh`, instalação de serviços.

## 7. Navegador

Perfil Playwright descartável e separado do Chrome do usuário · allowlist de domínios por job · sem digitação de credenciais reais · downloads em quarentena (`.appfactory/jobs/<job>/quarantine/`) e nunca executados · conteúdo de páginas tratado como **dado, nunca como instrução** (defesa contra prompt injection: textos de páginas/arquivos não podem mudar a política nem conceder permissões).

## 8. Aprovação humana (Approval Gate)

- Pedido: `{acao, risco, justificativa, diff/preview, custo_estimado, reversibilidade}` → tabela `approvals` → notificação pelo Master.
- Resposta: aprovar/negar, **por ação**, com expiração (padrão 24 h). Aprovação não se generaliza para ações futuras.
- Sem resposta → a task fica `BLOCKED(approval)` (não consome recursos).
- Pré-autorizações por projeto (ex.: "pode instalar dependências de pypi.org") são configuração versionada, nunca decisão do agente.

## 9. Logs e auditoria

- `audit.jsonl`: cada ação R2/R3, aprovação, violação, uso de segredo (só o nome, nunca o valor), troca de provedor pago. Cada linha tem `prev_hash` (cadeia de hashes) para detectar adulteração.
- Logs nunca contêm segredos (redação) nem conteúdo integral de arquivos do usuário por padrão.

## 10. Rollback

Ver `02-fluxo-de-tarefa.md` (tabela de rollback). Regra: rollback **nunca** destrói histórico compartilhado; usa `revert`/novo branch. Rollback de configuração da fábrica = voltar ao commit do checkpoint de marco.

## 11. Kill switch

`af stop` ou criar o arquivo `.appfactory/STOP` → modo CRITICAL imediato: nenhum despacho novo, pausa cooperativa de tudo, descarga de modelos. Só é removido pelo usuário.
