"""Resource Manager (Fase 2.3; 05-resource-manager.md). Biblioteca confiável **somente de leitura e decisão**:
sondas, contabilidade de VRAM do WDDM, modos com histerese por tempo ativo e admissão. Não atua (não pausa
tasks, não descarrega modelos, não altera o sistema) — a atuação é do daemon (2.4) e do Model Router (2.5).
Somente biblioteca padrão (D-0042, D-0058). Módulos protegidos (`src/appfactory/resources/**`)."""
