# Relatório de validação — 2026-09-21

| Gate | Evidência | Resultado |
|---|---|---|
| Python lint | `ruff check apps tests infra/scripts` | aprovado |
| Python types | `mypy apps/api/app apps/worker/worker` | 35 arquivos, sem issues |
| Unit/integration/E2E | `pytest -q` | 5 aprovados |
| Frontend typecheck/build | `npm run build` | 17 módulos, bundle produzido |
| Migration | `alembic upgrade head` + `alembic current` em SQLite vazio | `0001 (head)` |
| Temporal definitions | validação das definições `BuildWorkflow` e `PreviewLifecycleWorkflow` | aprovado |
| Importador legado | dry-run e import em DB temporário | 6 projetos, 5 prompts, 8 referências |
| Compose | parse YAML e presença de serviços/volumes | aprovado estruturalmente |
| Container runtime | `docker compose` | não executado: Docker indisponível no ambiente de trabalho |

O teste E2E cria projeto, responde gaps, produz versões de specs, executa quatro tarefas em worktrees, consolida commits, registra cinco validation runs, cria preview, pausa por inatividade, retoma e gera Production Plan/créditos.

Há dois warnings de depreciação no `TestClient` de FastAPI/Starlette, provenientes da combinação atual com httpx. Eles não afetam o resultado e devem ser reavaliados quando o ecossistema concluir a transição para httpx2.
