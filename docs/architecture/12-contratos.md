# 12 — Contratos entre componentes

Formatos em JSON (serão modelos Pydantic na Fase 2). Todo objeto tem `schema_version`. Campos marcados `?` são opcionais.

## 1. Envelope de evento (Event Bus / tabela `events`)

```json
{ "schema_version": 1, "seq": 1234, "ts": "2026-09-26T16:20:00-03:00",
  "type": "task.started", "job_id": "JOB-20260926-0001", "task_id": "TASK-JOB-20260926-0001-03",
  "actor": { "kind": "agent|system|user", "id": "coder" },
  "payload": { } }
```

Tipos de evento: `user.message` · `job.{created,state_changed,completed,failed,cancelled}` · `plan.{created,revised,approved}` · `task.{queued,started,heartbeat,step_completed,state_changed,scope_violation,completed,failed}` · `qa.{passed,failed}` · `build.{passed,failed}` · `security.{report,violation}` · `approval.{requested,decided,expired}` · `resource.{sample,mode_changed,admit,deny,preempt,probe_failed}` · `model.{loaded,unloaded,swapped}` · `provider.{call,failed,exhausted,switched,recovered}` · `checkpoint.{created,restored}` · `handoff.written` · `evolution.{proposed,tested,compared,decided}`.

## 2. TaskSpec (Job Manager → agent-runner)

```json
{ "schema_version": 1, "task_id": "...", "job_id": "...", "type": "code",
  "title": "Implementar endpoint /health", "objective": "...",
  "acceptance_criteria": ["GET /health retorna 200 {status: ok}", "teste unitário cobre o caso"],
  "reads": ["src/**"], "writes": ["src/api/health.py", "tests/test_health.py"],
  "depends_on": ["..."], "model_profile": "code.small", "risk_ceiling": "R1",
  "limits": { "max_steps": 30, "step_timeout_s": 600, "max_attempts": 3 },
  "worktree": "D:/Claude/app-factory/workspaces/_worktrees/demo/TASK-...-03",
  "branch": "af/JOB-.../TASK-...-03", "context_pack": ".appfactory/jobs/<job>/context/<task>/pack-0007.json",
  "resume_from?": "step-0006", "approvals?": ["APR-..."] }
```

## 3. TaskResult (agent-runner → Job Manager)

```json
{ "schema_version": 1, "task_id": "...", "attempt_id": "...", "outcome": "success|failure|needs_human|scope_change|interrupted",
  "summary": "...", "files_changed": ["..."], "commits": ["<sha>"], "tests_run?": {"passed": 12, "failed": 0},
  "followups?": [{"title": "...", "reason": "..."}], "blocked_reason?": "...",
  "usage": { "calls": 14, "tokens_in": 52000, "tokens_out": 8000, "providers": {"ollama-local": 14}, "cost_estimate": 0 } }
```

## 4. ContextPack (Memory → Model Router/Provider Router)

```json
{ "schema_version": 1, "pack_id": "pack-0007", "task_id": "...", "target": {"max_tokens": 8192, "reserve_output": 2048},
  "sections": [
    {"kind": "system", "ref": "config/agents/coder.yaml#prompt"},
    {"kind": "task", "text": "..."},
    {"kind": "decisions", "text": "...", "priority": 1},
    {"kind": "file", "path": "src/api/app.py", "range": [1, 120], "priority": 2},
    {"kind": "summary", "text": "Resumo dos passos 1-6", "priority": 1},
    {"kind": "tool_result", "text": "...", "priority": 3}
  ],
  "dropped": [{"kind": "file", "path": "...", "reason": "budget"}], "token_estimate": 6100 }
```

Regra de empacotamento: prioridade 1 sempre; depois 2, 3... até o orçamento; o que sobra é resumido ou vai para `dropped`.

## 5. ModelRequest / ModelResponse

```json
{ "schema_version": 1, "call_id": "...", "task_id": "...", "task_type": "code.small",
  "context_pack": "path", "response_format?": "json", "tools?": [...], "privacy": "local_only|external_ok",
  "max_cost": 0, "priority": 1 }
```
```json
{ "schema_version": 1, "call_id": "...", "provider": "ollama-local", "model": "qwen3.5:4b",
  "content": "...", "tool_calls?": [...], "finish_reason": "stop|length|tool|error",
  "usage": {"tokens_in": 6100, "tokens_out": 900, "latency_ms": 14000, "cost_estimate": 0},
  "fallbacks?": [{"provider": "...", "error": "quota_exhausted"}] }
```

## 6. Interfaces (Python, Fase 2)

```python
class Provider(Protocol):
    id: str
    async def generate(self, req: ModelRequest, pack: RenderedPrompt) -> ModelResponse: ...
    async def stream(self, req, pack) -> AsyncIterator[Chunk]: ...
    async def health(self) -> ProviderHealth: ...
    async def quota(self) -> QuotaStatus | None: ...
    async def list_models(self) -> list[ModelInfo]: ...

class Agent(Protocol):
    name: str
    def capabilities(self) -> CapabilitySet: ...           # validado contra permissions.yaml
    async def step(self, state: AgentState, tools: Toolbox, llm: LLMClient) -> StepOutcome: ...
    # runner: loop de step() com checkpoint entre passos e checagem do cancel token

class ResourceManager(Protocol):
    def snapshot(self) -> ResourceSnapshot: ...
    def admit(self, req: AdmissionRequest) -> Admission: ...        # GRANT | DENY(reason) | WAIT(retry_after)
    def acquire_gpu(self, model: str, est_vram_mib: int, priority: int) -> GpuLease | None: ...

class Sandbox(Protocol):  # S1 subprocess | S2 docker
    async def run(self, cmd: list[str], cwd: Path, env: dict, timeout_s: int, limits: Limits) -> RunResult: ...

class SecretStore(Protocol):
    def get(self, ref: str) -> str: ...     # só Provider Router/Toolbox
    def set(self, ref: str, value: str) -> None: ...   # só via CLI interativa do usuário

class GpuProbe(Protocol): ...
class MediaBackend(Protocol): ...
```

## 7. ResourceSnapshot e admissão

```json
{ "ts": "...", "mode": "FOREGROUND", "cpu_pct_60s": 16.8, "ram_available_gb": 5.2, "ram_total_gb": 23.71,
  "gpu": {"util_pct": 0, "vram_total_mib": 6141, "vram_used_mib": 105, "temp_c": 46, "foreign_util_pct": 0},
  "user_idle_s": 0, "on_ac": true, "battery_pct": 79, "disk_free_gb": {"C": 32.9, "D": 177.8},
  "loaded_models": [], "active": {"agents": 0, "heavy": 0, "gpu_lease": null} }
```
```json
{ "kind": "agent|heavy|gpu", "task_id": "...", "priority": 1, "est_ram_gb": 0.4, "est_vram_mib?": 3900, "model?": "qwen3.5:4b" }
```

## 8. ApprovalRequest

```json
{ "id": "APR-...", "job_id": "...", "task_id?": "...", "risk": "R3", "action": {"kind": "git.push", "target": "origin/main"},
  "justification": "...", "preview": "diff/resumo", "cost_estimate": 0, "reversible": "sim, via revert", "expires_at": "..." }
```

## 9. Journal de ferramenta

```json
{ "idempotency_key": "TASK-..-03:step-0006:git.commit", "tool": "git.commit", "args": {...}, "risk": "R1",
  "intent_at": "...", "result_at?": "...", "result?": {"ok": true, "sha": "..."} }
```

## 10. Checkpoint

```json
{ "schema_version": 1, "checkpoint_id": "...", "level": "step|task|milestone", "job_id?": "...", "task_id?": "...",
  "git": {"repo": "...", "branch": "...", "commit": "<sha>"}, "state_ref": "tabelas/arquivos", "created_at": "...",
  "restorable": true, "notes": "..." }
```
Marcos da fábrica seguem o formato já usado em `CP-0001-fase0.json`.

## 11. API local do daemon (127.0.0.1, header `X-AF-Token`)

| Método | Rota | Uso |
| --- | --- | --- |
| POST | `/jobs` | criar job (Master) |
| GET | `/jobs`, `/jobs/{id}` | status |
| POST | `/jobs/{id}/pause`, `/resume`, `/cancel`, `/priority` | controle |
| GET | `/approvals?state=pending` · POST `/approvals/{id}` | aprovação |
| POST | `/runner/heartbeat`, `/runner/step`, `/runner/result` | agent-runner |
| POST | `/llm/generate` | chamada de modelo (runner → routers) |
| POST | `/tools/{tool}` | chamada de ferramenta (runner → Toolbox + política) |
| GET | `/resources` | snapshot atual |
| POST | `/stop` | kill switch |
