# AI Video Director

Furniture campaign operating system. Phase 0 establishes a clean, reproducible
monorepo foundation: Next.js web app, FastAPI API, Celery worker, PostgreSQL,
Redis, MinIO, migrations, health checks, tests, CI, and an object-storage
abstraction.

## Repository layout

```text
ai-video-director/
  apps/web/                # Next.js 15, TypeScript
  services/api/            # FastAPI, REST/OpenAPI
  services/worker/         # Celery job consumers
  packages/contracts/      # Generated TypeScript client and shared schemas
  infrastructure/docker/   # (compose lives at repo root)
  tests/                   # (future)
  docs/
```

## Prerequisites

- Node.js >= 22
- Python >= 3.12
- Docker + Docker Compose (for PostgreSQL, Redis, MinIO)

## Setup

```bash
# 1. Install dependencies
npm install
cd services/api && pip install -e ".[dev]"
cd services/worker && pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env

# 3. Start infrastructure (PostgreSQL, Redis, MinIO)
docker compose up -d

# 4. Run database migrations
cd services/api && alembic upgrade head
```

## Commands

| Command        | Description                                            |
| -------------- | ------------------------------------------------------ |
| `npm run dev`  | Start the Next.js web app (http://localhost:3000)      |
| `npm run lint` | Lint all JS/TS workspaces                              |
| `npm run typecheck` | Typecheck all JS/TS workspaces                   |
| `npm run test` | Run all JS/TS tests                                    |
| `npm run build`| Production build of the web app                        |
| `npm run generate:client` | Regenerate TS client from OpenAPI          |
| `cd services/api && uvicorn avd_api.main:app --reload` | Run the API |
| `cd services/api && pytest` | Run API tests                              |
| `cd services/api && alembic upgrade head` | Apply migrations              |
| `cd services/worker && celery -A avd_worker.celery_app worker --loglevel=info` | Run worker |

## Health checks

- API liveness: `GET /health/live`
- API readiness: `GET /health/ready`
- Worker health task: `avd.health`

## Configuration boundaries

| Environment | Notes |
| ----------- | ----- |
| `development` | Local defaults; local storage allowed; test identity provider |
| `test` | Used by automated tests; ephemeral DB, local storage |
| `staging` | S3 storage, real OIDC issuer expected |
| `production` | Requires S3 credentials and a real (non-localhost) JWKS issuer |

See `.env.example` for all variables. Never commit `.env`.
