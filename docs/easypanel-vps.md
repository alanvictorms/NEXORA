# EasyPanel / VPS

O deploy de produção/validação usa **`docker-compose.easypanel.yml`** (o `docker-compose.yml`
da raiz continua sendo o compose de desenvolvimento local). Ele sobe cinco serviços:
`postgres`, `temporal`, `api`, `worker` e `web`.

## Topologia

```
USUÁRIO → web (público, :80) → api:8000 → temporal → worker → OpenHands Agent Server
```

O **Agent Server não faz parte deste compose**. Ele roda como um serviço EasyPanel próprio
(`nexora-agent-server`) e é alcançado pela rede externa `easypanel`:

```
OPENHANDS_BASE_URL=http://claw3d_nexora-agent-server:8000
```

Por isso `api`, `worker` e `web` participam da rede `easypanel` além da rede interna do Compose.
`postgres` e `temporal` ficam apenas na rede interna.

## Regras de exposição

- Nenhum serviço publica porta no host (`ports:` não é usado); o roteamento é do EasyPanel.
- Somente `web` recebe domínio público, na porta interna **80**. O nginx do `web` já faz
  proxy de `/api` para `api:8000`, então a API não precisa de domínio próprio.

## Variáveis obrigatórias (secrets do EasyPanel)

| Variável | Observação |
| --- | --- |
| `POSTGRES_PASSWORD` | Entra na `DATABASE_URL`; use apenas caracteres seguros para URL (hex). |
| `SECRET_ENCRYPTION_KEY` | Obrigatória com `APP_ENV=production` (`SecretStore` recusa iniciar sem ela). |
| `OPENHANDS_API_KEY` | **Mesmo valor** do `SESSION_API_KEY` do serviço `nexora-agent-server`. |
| `PREVIEW_BASE_URL` | URL pública de preview. |
| `CORS_ORIGINS` | Origens do frontend. |

Fixas no compose: `APP_ENV=production`, `AUTO_CREATE_SCHEMA=false`,
`WORKFLOW_BACKEND=temporal`, `TEMPORAL_ADDRESS=temporal:7233`.

## Deploy

1. Crie um serviço **Compose** apontando para o repositório Git, branch `main`, build path `/`,
   e `docker-compose.easypanel.yml` como arquivo de compose.
2. Preencha os secrets acima em *Environment*.
3. Crie o domínio público apenas para `web:80`.
4. Deploy. A API roda `alembic upgrade head` antes do `uvicorn` (o schema vem de migrations,
   nunca de `create_all`).

## Persistência

- `postgres_data` → `/var/lib/postgresql/data`
- `project_data` → `/app/data` em `api` **e** `worker` (repositórios Git e artifacts são
  compartilhados entre os dois; não separe esse volume)

Em escala, troque artifacts locais por storage S3-compatible.

## Validação pós-deploy

- `GET /api/v1/health` pelo domínio público (via proxy do nginx).
- `pg_isready` no `postgres` e porta 7233 respondendo no `temporal`.
- Log do `worker` com o worker Temporal registrado na task queue `nexora-control-plane`.

Healthcheck HTTP `/api/v1/health`, backup diário e rotação de logs continuam recomendados,
assim como fixar imagens por versão/digest.

O `PlanningOnlyDeploymentProvider` impede publicação comercial acidental. Conecte um provider
EasyPanel/VPS explícito antes de habilitar provisionamento externo e mantenha produção derivada
de migrations em banco novo.
