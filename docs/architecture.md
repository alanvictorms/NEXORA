# Arquitetura da V2

## Forma do sistema

NEXORA é um control plane de engenharia de software. A primeira base é um monólito modular FastAPI com frontend React e worker Temporal separado. PostgreSQL persiste a fonte da verdade; OpenHands é uma camada de execução substituível.

```text
React/Vite -> FastAPI control plane -> PostgreSQL
                     |-> Temporal workflows/workers
                     |-> Provider Registry -> OpenHands Agent Server -> ACP/OpenHands
                     |-> Git repositories/worktrees
                     |-> Validation Engine
                     |-> Preview/Deployment providers
```

## Fontes de verdade

- conversa: evidência;
- `ProjectSpecVersion`: intenção compilada e versionada;
- `ArchitectureSpecVersion`: decisões técnicas justificadas;
- `TaskGraph`: DAG executável versionada;
- `Execution`/`ExecutionEvent`: estado e timeline reais;
- Git: linhagem do código;
- `Artifact`: arquivos e relatórios;
- `PreviewSession` e `ProductionPlan`: ambientes e custo técnico.

## Modos de execução

- `local`: workflow determinístico para desenvolvimento, CI e demonstração sem infraestrutura externa;
- `temporal`: workflows duráveis reais, timers e activities;
- executor `local_mock`: produz commits/artifacts de demonstração e permite E2E offline;
- executor `openhands`: integração REST encapsulada com Agent Server;
- presets ACP são configuração por execução (`claude_code_acp`, `codex_acp`), não estado global.

## Limites de segurança

Segredos são criptografados no Secret Store e o banco recebe metadata/referência. Eventos são classificados em `PUBLIC_PROGRESS`, `TECHNICAL_LOG`, `DEBUG` e `SECRET`; o último nunca é entregue ao browser. Coding agents recebem apenas `TaskSpec`, manifesto mínimo e secret refs autorizados.

## Preview

O contrato possui estados `BUILDING`, `STARTING`, `ACTIVE`, `IDLE`, `PAUSED`, `RESUMING`, `ARCHIVED`, `RESTORING`, `FAILED` e `DELETED`. O provider local serve um artifact pela API e exercita pausa/retomada. O provider Docker/PostgreSQL isolado é a evolução operacional, mantendo a mesma interface. Preview nunca é banco de produção.

## Correções em relação ao pacote arquitetural

1. A integração OpenHands usa um adapter HTTP próprio e versionado por contrato, mas recomenda o SDK oficial quando a versão do Agent Server for fixada. Isso evita inventar dependência Python instável no núcleo.
2. O modo local não simula Temporal em produção; ele existe como implementação explícita da interface para CI e onboarding. `WORKFLOW_BACKEND=temporal` é o caminho durável.
3. A versão inicial não entrega Docker socket a agents. Git/worktrees e execução local ficam limitados a diretórios de projeto; o runtime comercial deverá usar `AgentRuntimeFactory` isolada.

