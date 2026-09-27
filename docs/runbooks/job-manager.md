# Runbook — Job Manager (Fase 2.1)

Fundação executável do Job Manager. **Não** há daemon, agentes, sandbox S1h/S2, Job Objects nem integração com Ollama nesta fase.

## 1. Como executar

Requer Python ≥ 3.10 (alvo: 3.13 via `uv`). Nenhuma dependência de execução.

```powershell
cd D:\Claude\app-factory
# com uv (instala Python 3.13 e pytest no .venv do projeto, ignorado pelo Git)
uv run af --version
uv run pytest
# sem uv
$env:PYTHONPATH = "src"; python -m appfactory --version
$env:PYTHONPATH = "src"; python -m unittest discover -s tests -t .
```

O banco fica em `.appfactory/state/factory.db` (fonte da verdade, ignorado pelo Git). Espelhos operacionais: `.appfactory/runtime/job.json` e `.appfactory/logs/jobs/<job>.jsonl`.

## 2. Comandos

| Comando | Efeito |
| --- | --- |
| `af job create --project P --intent "..." [--payload JSON] [--priority 0-3]` | cria job em `QUEUED` (tipo `demo.steps`) |
| `af job list [--state S]` · `af job queue` | lista jobs · fila reconstruída do SQLite |
| `af job show ID` · `af job status ID` | detalhes (inclui último checkpoint válido) · estado atual |
| `af job run [ID]` | executa um job neste processo (executor em primeiro plano) |
| `af job stop ID` | STOP do job: `RUNNING → STOPPING → STOPPED` (parada graciosa) |
| `af job checkpoint ID [--all]` | último checkpoint válido · todos |
| `af job history ID` | histórico persistente de eventos |
| `af job resume ID` | `STOPPED/PAUSED/BLOCKED/WAITING/FAILED → QUEUED`, retomando do último checkpoint válido |
| `af job cancel ID` | `CANCELLED` (terminal) |
| `af recover` | recuperação após queda/reinício (07 §3) |
| `af stop` · `af resume-factory` · `af status` | STOP da fábrica (kill switch) · liberar (código digitado no console) · situação |
| `af db check` | integridade, schema e triggers do SQLite |

Todos aceitam `--json` e `--root <pasta>` (padrão: `AF_ROOT` ou descoberta a partir do diretório atual).

## 3. Situações comuns

- **Processo morreu no meio de um job:** `af recover` → o job fica `RUNNING` (`state_reason = recovered`) com `resume_from` = último checkpoint válido → `af job run ID` retoma dali.
- **Job em `BLOCKED(needs_human)`:** ler `af job history ID`; depois de resolver, `af job resume ID`.
- **STOP da fábrica ativo:** nada é despachado; jobs executando vão para `PAUSED(factory_stop)`. Apagar `.appfactory/STOP` **não** libera: use `af resume-factory` num terminal interativo.

## 4. Limites conhecidos

Ver `KNOWN_ISSUES.md` (KI-0018 a KI-0020): caminhos Windows ainda não executados em Windows; sem daemon (recuperação sob comando `af recover`); processos mudos perdem a posse por *fencing*, mas não são encerrados (Job Objects na 2.4).
