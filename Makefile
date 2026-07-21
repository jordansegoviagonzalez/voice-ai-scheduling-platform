SHELL := /bin/bash

.PHONY: setup dev seed test lint build up down logs migrate

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e "./backend[dev]"
	cd frontend && npm ci

dev:
	docker compose up --build db backend frontend

migrate:
	. .venv/bin/activate && cd backend && alembic upgrade head

seed:
	. .venv/bin/activate && cd backend && flask --app app:create_app seed

test:
	docker compose exec -T backend pytest -q
	docker compose exec -T frontend npm test -- --run

lint:
	docker compose exec -T backend ruff check .
	docker compose exec -T backend ruff format --check .
	docker compose exec -T backend mypy app
	docker compose exec -T frontend npm run lint

build:
	docker compose exec -T frontend npm run build

docker-build:
	docker compose -f docker-compose.prod.yml build

up:
	docker compose -f docker-compose.prod.yml up -d --build

down:
	docker compose -f docker-compose.prod.yml down

logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=200
