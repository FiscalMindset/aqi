# Dhuan Detective — developer entry points.
# Run `make help` for the full list.

SHELL := /bin/bash
DC := docker compose
COMPOSE := $(DC) -f docker/docker-compose.yml
COMPOSE_TEST := $(DC) -f docker/docker-compose.test.yml
BACKEND := backend

.DEFAULT_GOAL := help
.PHONY: help dev up down logs test lint format types check-backend \
        train evaluate seed-sources api frontend-dev docs docs-serve \
        openapi smoke teardown clean verify release

## help: show this help
help:
	@echo "Dhuan Detective — targets:"
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## /  /'

## dev: start full stack (OpenSearch, LocalStack, backend, frontend)
dev: up
	@echo "Stack starting: API http://localhost:8000  web http://localhost:5173"

## up: start docker services in background
up:
	$(COMPOSE) up -d --wait --wait-timeout 180

## down: stop docker services
down:
	$(COMPOSE) down -v

## logs: tail service logs
logs:
	$(COMPOSE) logs -f --tail=100

## test: run all test layers locally (docker-backed)
test: test-backend test-frontend

## test-backend: unit + integration + model + agent evals (containers)
test-backend:
	$(COMPOSE_TEST) up -d --wait --wait-timeout 180
	cd $(BACKEND) && uv run pytest tests/unit tests/model -q --cov=src/dhuan --cov-report=term-missing
	cd $(BACKEND) && uv run pytest tests/integration tests/contract tests/agent_evals -q
	$(COMPOSE_TEST) down -v

## test-frontend: vitest unit tests
test-frontend:
	cd frontend && npm ci && npm run test:unit

## lint: ruff + eslint + format check
lint:
	cd $(BACKEND) && uv run ruff check src tests && uv run ruff format --check src tests
	cd frontend && npm run lint

## format: auto-format
format:
	cd $(BACKEND) && uv run ruff format src tests && uv run ruff check --fix src tests
	cd frontend && npm run lint:fix

## types: mypy --strict + tsc
types:
	cd $(BACKEND) && uv run mypy --strict src
	cd frontend && npm run typecheck

## check-backend: lint + types + backend unit tests
check-backend:
	$(MAKE) lint
	cd $(BACKEND) && uv run mypy --strict src
	cd $(BACKEND) && uv run pytest tests/unit -q

## train: reproducible model training (snapshot hashes recorded)
train:
	cd $(BACKEND) && uv run python -m dhuan.model.train

## evaluate: regenerate model card from evaluation metrics
evaluate:
	cd $(BACKEND) && uv run python -m dhuan.model.evaluate

## seed-sources: Overpass -> OpenSearch source seeding
seed-sources:
	cd $(BACKEND) && uv run python -m dhuan.ingest.osm --seed

## api: run FastAPI locally with reload
api:
	cd $(BACKEND) && uv run uvicorn dhuan.api.app:app --reload --port 8000

## frontend-dev: vite dev server
frontend-dev:
	cd frontend && npm run dev

## docs: build mkdocs site strictly
docs:
	uv run --with mkdocs-material --with mkdocs-mermaid2-plugin --with pymdown-extensions \
		mkdocs build --strict -f docs/mkdocs.yml

## docs-serve: serve docs locally
docs-serve:
	uv run --with mkdocs-material --with mkdocs-mermaid2-plugin --with pymdown-extensions \
		mkdocs serve -f docs/mkdocs.yml

## openapi: regenerate openapi.yaml from the FastAPI app
openapi:
	cd $(BACKEND) && uv run python -m dhuan.api.openapi_gen

## smoke: run smoke checks against DEPLOYED endpoints (set BASE_URL)
smoke:
	uv run --with httpx python scripts/smoke.py

## teardown: delete all deployed AWS resources for this project
teardown:
	bash scripts/teardown.sh

## clean: remove caches and build artifacts
clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null; true
	rm -rf .pytest_cache .mypy_cache .ruff_cache backend/.venv
	rm -rf frontend/dist frontend/node_modules site
	docker compose -f docker/docker-compose.yml down -v 2>/dev/null; true

## verify: full local verification (lint, types, tests, docs)
verify:
	$(MAKE) lint
	$(MAKE) types
	$(MAKE) check-backend
	$(MAKE) docs
	@echo "verify: GREEN (see TASKS.md for layer status)"

## release: walk the release checklist (docs/RELEASE.md)
release:
	@bash scripts/release_checklist.sh
