.PHONY: up down db-shell redis-shell minio-shell frontend api test test-api test-web

up:
	docker-compose up -d

down:
	docker-compose down

db-shell:
	docker-compose exec db psql -U postgres -d sentinel_deformation

redis-shell:
	docker-compose exec redis redis-cli

api:
	cd apps/api && uvicorn app.main:app --reload --port 8000

frontend:
	cd apps/web && npm run dev

test: test-api test-web

test-api:
	cd apps/api && ../../venv/bin/python -m pytest tests/ -v

test-web:
	cd apps/web && npx vitest run
