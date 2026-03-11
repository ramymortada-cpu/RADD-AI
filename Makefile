.PHONY: up down migrate seed api web worker test lint typecheck build help

# ─────────────────────────────────────────────
# RADD — Developer Commands
# ─────────────────────────────────────────────

help:
	@echo ""
	@echo "  make up        — Start all Docker services (postgres, redis, qdrant, minio)"
	@echo "  make down      — Stop all Docker services"
	@echo "  make migrate   — Run Alembic database migrations"
	@echo "  make seed      — Seed development data (1 workspace, 2 users, 1 channel)"
	@echo "  make api       — Start FastAPI development server on :8000"
	@echo "  make worker    — Start message worker (Redis Streams consumer)"
	@echo "  make web       — Start Next.js development server on :3000"
	@echo "  make test      — Run all tests (pytest + vitest)"
	@echo "  make test-api  — Run backend tests only"
	@echo "  make test-web  — Run frontend tests only"
	@echo "  make lint      — Lint backend (ruff) + frontend (eslint)"
	@echo "  make typecheck — Type-check backend (mypy) + frontend (tsc)"
	@echo "  make build     — Build production Docker images"
	@echo ""

up:
	docker compose -f infrastructure/docker-compose.yml up -d
	@echo "✓ Services started: postgres:5432, redis:6379, qdrant:6333, minio:9000"
	@echo "  MinIO console: http://localhost:9001"
	@echo "  Qdrant dashboard: http://localhost:6333/dashboard"

down:
	docker compose -f infrastructure/docker-compose.yml down

migrate:
	cd apps/api && uv run alembic upgrade head

migrate-down:
	cd apps/api && uv run alembic downgrade -1

migrate-create:
	@read -p "Migration name: " name; cd apps/api && uv run alembic revision --autogenerate -m "$$name"

seed:
	cd apps/api && uv run python scripts/seed.py

api:
	cd apps/api && uv run uvicorn radd.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd apps/api && uv run python -m workers.message_worker

web:
	cd apps/web && pnpm dev

test: test-api test-web

test-api:
	cd apps/api && uv run pytest tests/ -v --tb=short

test-web:
	cd apps/web && pnpm test

lint:
	cd apps/api && uv run ruff check radd/ workers/ scripts/
	cd apps/web && pnpm lint

lint-fix:
	cd apps/api && uv run ruff check --fix radd/ workers/ scripts/

typecheck:
	cd apps/api && uv run mypy radd/
	cd apps/web && pnpm typecheck

build:
	docker build -f infrastructure/docker/Dockerfile.api -t radd-api:latest .
	docker build -f infrastructure/docker/Dockerfile.worker -t radd-worker:latest .
	docker build -f infrastructure/docker/Dockerfile.web -t radd-web:latest .

install:
	cd apps/api && uv sync
	cd apps/web && pnpm install

benchmark:
	cd apps/api && uv run python scripts/benchmark.py
