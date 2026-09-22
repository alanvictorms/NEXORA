#!/usr/bin/env sh
set -eu

python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
(cd apps/web && npm install)
cp -n .env.example .env || true
PYTHONPATH=apps/api:apps/worker .venv/bin/alembic upgrade head
printf '%s\n' 'Bootstrap concluído. Use make api, make worker e make web.'
