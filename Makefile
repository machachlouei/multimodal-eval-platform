.PHONY: help install fmt lint test up down db-up db-down seed run-gateway run-worker run-all

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

install: ## install python deps (uv preferred)
	uv sync --extra dev --extra ray --extra temporal --extra judge \
	  --extra metrics-text --extra metrics-vision --extra metrics-speech \
	  || pip install -e ".[dev,ray,temporal,judge,metrics-text,metrics-vision,metrics-speech]"

fmt:
	ruff format melp tests

lint:
	ruff check melp tests

test:
	pytest -q

up: ## bring up infra (postgres, redis, minio, temporal)
	docker-compose up -d postgres redis minio minio-init temporal llm-gateway-stub
	@echo "Waiting for postgres..." && sleep 3

down:
	docker-compose down

db-up: ## run alembic migrations
	alembic upgrade head

db-down:
	alembic downgrade base

seed: ## seed dev project + sample metric registrations
	python -m melp.scripts.seed_dev

run-gateway:
	uvicorn melp.services.gateway.app:app --reload --port 8000

run-worker:
	python -m melp.workers.runner

run-all: ## run gateway + every backing service in one process (dev only)
	python -m melp.scripts.run_all
