FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 nexora
COPY pyproject.toml alembic.ini ./
COPY apps ./apps
COPY migrations ./migrations
RUN pip install --no-cache-dir . && pip install --no-cache-dir pytest
RUN mkdir -p /app/data && chown -R nexora:nexora /app
USER nexora
ENV PYTHONPATH=/app/apps/api:/app/apps/worker
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
