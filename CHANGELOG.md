# Changelog técnico

## 0.1.0 — 2026-09-21

- reconstrução em monólito modular FastAPI e React/Vite, com worker Temporal separado;
- contratos versionados para ProjectSpec, DesignSpec, ArchitectureSpec e TaskGraph;
- Provider Registry com executor local e adapters OpenHands/ACP;
- Git por projeto, worktrees por tarefa, artifacts, eventos, auditoria e secret store criptografado;
- oito gates finais antes de preview, lifecycle com pausa/retomada/retenção e Production Plan;
- importador sanitizado do legado, Docker Compose, migrations e instruções EasyPanel/VPS;
- correção arquitetural: integração OpenHands encapsulada no contrato REST canônico do Agent Server; SDK não foi acoplado ao domínio para evitar dependência instável;
- correção operacional: modo local explícito para CI/desenvolvimento e Temporal obrigatório quando `WORKFLOW_BACKEND=temporal`.
