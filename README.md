# NEXORA Agentic Builder V2

Control plane agêntico que transforma uma conversa em especificações versionadas, DAG de tarefas, execução auditável, validação, preview efêmero e plano de produção. A aplicação foi reconstruída sobre FastAPI, React/Vite, PostgreSQL, SQLAlchemy/Alembic e Temporal, mantendo OpenHands abaixo do orquestrador e atrás de um Provider Registry.

## Fluxo implementado

1. projeto e conversa de discovery;
2. `ProjectSpec` imutável e versionado;
3. gap analysis com perguntas limitadas e recomendações;
4. `DesignSpec` e `ArchitectureSpec` versionados;
5. `TaskGraph` DAG com contexto mínimo, critérios, retry e artifacts esperados;
6. roteamento para executor local, OpenHands nativo, Claude Code ACP ou Codex ACP;
7. repositório Git por projeto e worktree por tarefa;
8. eventos persistidos, artifacts e gates técnicos;
9. preview isolado com quota, inatividade, pausa, retomada e retenção;
10. plano de produção em banco novo e estimativa mensal de créditos.

## Execução local rápida

Requisitos: Python 3.12, Node 24+, npm e Git.

```bash
cp .env.example .env
make bootstrap
make api
```

Em outros terminais:

```bash
make worker   # necessário apenas com WORKFLOW_BACKEND=temporal
make web
```

Abra `http://localhost:5173`. O backend usa SQLite somente no modo local se `DATABASE_URL` não for definido; PostgreSQL é o banco oficial.

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Interface: `http://localhost:5173`; API: `http://localhost:8000/api/v1/health`; Temporal UI: `http://localhost:8080`.

Para usar workflow durável, defina `WORKFLOW_BACKEND=temporal`. Para subir também o Agent Server:

```bash
OPENHANDS_IMAGE=ghcr.io/openhands/agent-server:<versao-fixada> docker compose --profile openhands up --build
```

Fixe uma versão ou digest testado do OpenHands em produção. Sem ele, o executor determinístico local mantém o fluxo ponta a ponta executável para desenvolvimento e CI.

## Qualidade

```bash
make lint
make test
make typecheck
make build
```

O pipeline gerado só cria preview depois dos gates finais de lint, typecheck/compile, testes unitários, integração, build, migrations check, healthcheck e smoke test.

## Migração seletiva do legado

O importador lê o SQLite legado em modo read-only e importa somente briefings, taxonomias, prompts históricos sanitizados e metadata de referências. Credenciais, clientes, financeiro, senhas, tokens e `.env` não são copiados.

```bash
PYTHONPATH=apps/api .venv/bin/python infra/scripts/import_legacy.py /caminho/flowtech_projects.db --dry-run
PYTHONPATH=apps/api .venv/bin/python infra/scripts/import_legacy.py /caminho/flowtech_projects.db
```

## Estrutura

- `apps/api`: domínio, REST/SSE, serviços e integrações;
- `apps/worker`: workflows e activities Temporal;
- `apps/web`: UX de discovery, specs, timeline, tarefas e preview;
- `packages/contracts`: schemas públicos de `ProjectSpec` e `TaskSpec`;
- `migrations`: schema Alembic;
- `infra`: bootstrap e importação segura;
- `docs`: arquitetura, ADRs e operação.

## Segurança

Segredos são criptografados, escopados por tipo de tarefa e nunca retornados em plaintext. O executor recebe referências, não valores. O Agent Server deve ficar em rede privada; coding agents não recebem Docker socket nem acesso irrestrito ao host. Troque `SECRET_ENCRYPTION_KEY` e senhas locais antes de qualquer ambiente compartilhado.
