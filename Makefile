.PHONY: bootstrap dev api worker web test lint typecheck build check compose

bootstrap:
	python3.12 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
	cd apps/web && npm install

api:
	PYTHONPATH=apps/api:apps/worker .venv/bin/uvicorn app.main:app --reload

worker:
	PYTHONPATH=apps/api:apps/worker .venv/bin/python -m worker.main

web:
	cd apps/web && npm run dev

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check apps tests

typecheck:
	.venv/bin/mypy apps/api/app apps/worker/worker

build:
	cd apps/web && npm run build

check: lint test build

compose:
	docker compose up --build
