# RESOURCE_POLICY.md — Recursos e limites

## Hardware conhecido

| Recurso | Valor | Fonte |
| --- | --- | --- |
| CPU | Intel Core i5-13420H | Informado pelo usuário; **modelo confirmado** em `/proc/cpuinfo` (2026-09-26) |
| RAM | 24 GB DDR5 | Informado pelo usuário; **não verificado** |
| GPU | NVIDIA RTX 4050 Laptop | Informado pelo usuário; **não verificado** |
| VRAM | 6 GB | Informado pelo usuário; **não verificado** |
| SO | Windows + WSL | Informado pelo usuário; Windows confirmado (`platform: win32`); WSL **não verificado** (ambiente WSL/OpenClaw é separado do projeto — D-0010) |
| Modelos locais | Ollama | Informado pelo usuário; existe `~/.ollama` no perfil do Windows; versão **não verificada** |

## Políticas iniciais (provisórias — revisar na Fase 1)

- Considerar RAM e VRAM os recursos mais escassos.
- Não carregar mais de um modelo local grande ao mesmo tempo na GPU sem avaliação prévia.
- Toda política numérica definitiva (limites de RAM/VRAM por job, concorrência de agentes) será definida na Fase 1, após medições reais.
