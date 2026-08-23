.PHONY: install dev lint typecheck test build db-migrate db-upgrade db-downgrade generate-client docker-up docker-down

# --- Install ---
install:
	npm install
	cd services/api && pip install -e ".[dev]"
	cd services/worker && pip install -e ".[dev]"

# --- Dev ---
dev:
	npm run dev

# --- Lint ---
lint:
	npm run lint
	cd services/api && ruff check .
	cd services/worker && ruff check .

# --- Typecheck ---
typecheck:
	npm run typecheck
	cd services/api && mypy src

# --- Test ---
test:
	npm run test
	cd services/api && pytest
	cd services/worker && pytest

# --- Build ---
build:
	npm run build

# --- Database ---
db-migrate:
	cd services/api && alembic upgrade head

db-upgrade:
	cd services/api && alembic upgrade head

db-downgrade:
	cd services/api && alembic downgrade base

# --- Client generation ---
generate-client:
	cd services/api && avd-export-openapi
	npm run generate:client

# --- Docker ---
docker-up:
	docker compose up -d

docker-down:
	docker compose down
