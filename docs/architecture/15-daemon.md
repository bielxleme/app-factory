# 15 — Ciclo de vida do daemon, leases e runners (N3)

**Criado na revisão 1.1 (2026-09-26).** Decisões: D-0030 e D-0031 (prazos de parada: D-0054). Diagrama: `13-diagramas.md` §10. Nada disto está implementado.

## 1. Instância única

- **Mutex nomeado** `Local\AppFactory-afd-<hash-do-caminho-do-repo>` (sessão do usuário) + **arquivo de trava** `.appfactory/runtime/afd.lock` com `{pid, process_create_time, started_at, repo_path, version}`.
- Segunda instância: não consegue o mutex → informa o PID da instância ativa e sai com código ≠ 0.
- Trava órfã (daemon morreu): o mutex é liberado pelo sistema quando o processo morre; o arquivo é considerado velho se o PID não existir **ou** se o horário de criação do processo com aquele PID for diferente do gravado (reuso de PID). Nesse caso é sobrescrito.
- Somente a instância que detém o mutex abre o SQLite para escrita (D-0037).

## 2. Comandos

| Comando | Efeito |
| --- | --- |
| `af daemon start` | Se não houver instância: cria processo destacado (`DETACHED_PROCESS`, `CREATE_NEW_PROCESS_GROUP`, prioridade BELOW_NORMAL, sem janela), espera `GET /health` por até 20 s, informa PID e porta. Se houver: informa e sai com sucesso. |
| `af daemon stop` | Pausa cooperativa de todos os runners (`terminate` ≤ T0 + 30 s, encerramento total ≤ T0 + 40 s, com T0 = instante persistido do pedido; D-0054), grava estado, remove a trava, encerra. |
| `af daemon status` | PID, versão, modo de recursos, jobs ativos, STOP, horário do último heartbeat de cada runner. |
| `af daemon restart` | `stop` + `start`. |
| `af daemon install-autostart` / `uninstall-autostart` | Cria/remove a tarefa de logon (§3). **R3**: exige confirmação interativa do usuário. Implementação só na Fase 2. |

## 3. Inicialização no login do Windows

- Mecanismo: **Agendador de Tarefas**, tarefa `AppFactory-afd`, gatilho "Ao fazer logon" **do usuário atual**, opção "**Executar somente quando o usuário estiver conectado**", sem "privilégios mais altos", sem armazenar senha.
- Ação: `af daemon start --autostart` (atraso de 60 s após o logon para não competir com a inicialização do Windows).
- **Não é um serviço do Windows** nesta fase (D-0030). Motivo: o daemon precisa da sessão interativa para `GetLastInputInfo`, notificações e o cofre do usuário.
- A fábrica nunca cria a tarefa sozinha; é o usuário quem roda `af daemon install-autostart` (com confirmação).

## 4. Relógios

| Uso | Relógio |
| --- | --- |
| Leases, heartbeats, timeouts de passo | **tempo ativo do sistema** — `QueryUnbiasedInterruptTime` (exclui suspensão/hibernação) |
| Detecção de retorno do sono | diferença entre `time.monotonic()` (inclui suspensão no Windows) e o tempo ativo, ou evento de energia `PBT_APMRESUMEAUTOMATIC` |
| Registros para humanos (`created_at`, logs) | relógio de parede com fuso |

Leases nunca são comparados com relógio de parede.

## 5. Leases e verificação de vida

| Parâmetro | Valor |
| --- | --- |
| Heartbeat do runner | a cada 15 s (tempo ativo) |
| Lease | 60 s de tempo ativo |
| Ao vencer | **antes** de declarar a tentativa `interrupted`, o daemon verifica o processo: PID existe **e** `process_create_time` igual ao registrado **e** pertence ao Job Object da task |
| Processo vivo, sem heartbeat | pede status pela API; sem resposta em mais 2 leases (120 s) → encerra o Job Object da task → `interrupted` |
| Processo morto | `interrupted` imediatamente; `resume_from` = último checkpoint de passo completo |
| Passo com efeito colateral sem resultado no journal | `BLOCKED(needs_human)` (07 §4) |

Nunca existem duas tentativas vivas da mesma task: a nova só é criada depois que o Job Object da anterior foi encerrado e confirmado vazio.

## 6. Retorno do sono / hibernação

1. Detectado o retorno (§4): o daemon entra em **carência de 120 s**.
2. Durante a carência: nenhum lease vence, nenhuma admissão nova, o Resource Manager faz 2 amostras novas, a rede é sondada.
3. Runners vivos voltam a mandar heartbeat normalmente; os que não voltarem seguem §5.
4. Chamadas a provedores interrompidas pelo sono são tratadas como erro transitório (06 §5).
5. Evento `system.resumed` com a duração da suspensão.

## 7. Job Objects

```
Job raiz "AppFactory-afd" (criado pelo daemon; KILL_ON_JOB_CLOSE)
 |-- job do runner da task A (usuário principal, código confiável da fábrica)
 |-- job S1h da task A (processos como afrunner; limites de 08 §4.2)
 |-- job do runner da task B ...
 `-- processos pesados confiáveis (git, ferramentas do Toolbox)
```

- Todo processo filho é criado **suspenso**, atribuído ao job e só então retomado (não há janela sem controle).
- `KILL_ON_JOB_CLOSE` no job raiz: se o daemon morrer (crash, kill), o sistema fecha o handle e **mata todos os runners e sandboxes** — não sobram órfãos trabalhando.
- O Docker/S2 é controlado por `docker` com `--rm` e rótulo `appfactory.task=<id>`; na recuperação, containers com o rótulo e sem task viva são parados.

## 8. Runners órfãos e daemon ausente

- Com o Job Object raiz, órfãos não sobrevivem ao daemon. Por defesa em profundidade, o runner também tem **dead-man switch**: se 3 heartbeats seguidos falharem (45 s) ou o PID do daemon (com o `process_create_time` registrado) sumir, ele termina a operação atômica em curso, grava checkpoint de passo e sai.
- Na partida (07 §3), o daemon ainda procura processos da fábrica listados em `.appfactory/runtime/pids/` e só os encerra se PID **e** horário de criação **e** usuário coincidirem.

## 9. Sequência de parada normal

1. Parar despacho → 2. pedir pausa cooperativa a todos os runners → 3. esperar até T0 + 30 s (`terminate`) e T0 + 40 s (kill), com T0 persistido antes do passo 1 (D-0054) → 4. encerrar Job Objects restantes → 5. descarregar só os modelos da fábrica → 6. gravar estado e handoff operacional → 7. liberar mutex e remover a trava.

## 10. Validação futura (Fase 2)

Prova de conceito obrigatória antes de usar S1h de verdade: (a) logon secundário + atribuição a Job Object aninhado + `KILL_ON_JOB_CLOSE`; (b) `QueryUnbiasedInterruptTime` antes/depois de suspender o notebook; (c) matar o daemon à força e confirmar que nenhum processo sobrevive. Resultado registrado em `TEST_STATUS.md` (KI-0014).
