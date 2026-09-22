# EasyPanel / VPS

Use quatro serviços: `web`, `api`, `worker` e PostgreSQL. Temporal pode ser serviço gerenciado ou o container oficial em rede privada. Compartilhe um volume persistente entre `api` e `worker` apenas para os repositórios Git; em escala, substitua artifacts locais por storage S3-compatible.

1. Crie PostgreSQL e um banco vazio para o control plane.
2. Configure `DATABASE_URL`, `SECRET_ENCRYPTION_KEY`, `TEMPORAL_ADDRESS`, `CORS_ORIGINS` e a URL pública de preview.
3. Faça build do `Dockerfile` raiz para API e worker; altere apenas o comando do worker para `python -m worker.main`.
4. Faça build de `apps/web/Dockerfile` para o frontend.
5. Execute `alembic upgrade head` antes de iniciar a API.
6. Publique somente web/API; mantenha PostgreSQL, Temporal e OpenHands em rede privada.
7. Configure healthcheck HTTP `/api/v1/health`, backup diário e rotação de logs.
8. Fixe todas as imagens por versão/digest e use o cofre de secrets do painel.

O `PlanningOnlyDeploymentProvider` impede publicação comercial acidental. Conecte um provider EasyPanel/VPS explícito antes de habilitar provisionamento externo e mantenha produção derivada de migrations em banco novo.
