.PHONY: up down db-shell redis-shell minio-shell frontend api

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
