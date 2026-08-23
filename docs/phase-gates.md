# Phase gate decisions

Required by `IMPLEMENTATION_PLAN.md` §8 item 10: every phase gate records a
documented **go**, **revise**, or **stop** decision with the evidence it rests on.

---

## Phase 0 — Repository rescue and executable foundation

- **Gate commit:** `f199c8c` — Phase 0: executable monorepo foundation
- **Decision:** **GO**
- **Decided by:** StanleyOS (via CI confirmation)
- **Date:** 2026-08-23

### Acceptance criteria

| Criterion (`IMPLEMENTATION_PLAN.md:251`) | Status | Evidence |
|---|---|---|
| Clean clone installs without manually moving files | Pending | Requires a fresh clone + `make install`; not yet exercised |
| Web and API start together through documented commands | Pending | `make dev` not exercised from a clean checkout |
| Docker services become healthy | Pending | `docker compose up` not exercised (Docker engine unavailable locally) |
| Web calls the API readiness endpoint successfully | Pending | Depends on the two rows above |
| CI runs lint, typecheck, unit tests, and production builds | **Met** | GitHub Actions run `32624463701` on `phase-0-foundation` — all 5 jobs (web, contracts, api, worker, openapi drift) green |
| No duplicated `app/app/...` trees remain | **Met** | `git ls-tree -r f199c8c` → 0 paths under `app/app` |
| No unpinned `latest` Docker images | **Met** | `docker-compose.yml` pins `postgres:16.6-alpine`, `redis:7.4.1-alpine`, `minio/minio:RELEASE.2025-01-20T14-49-07Z`; 0 occurrences of `latest` |
| No secret or generated media is committed | **Met** | 0 tracked `.env` / `.pem` / `.key` / video / image files at `f199c8c` |
| A valid test identity can access its organization and receives 403/404 for another organization | **Met** | `tests/test_auth.py` — `test_member_can_read_own_project`, `test_non_member_cannot_read_project` (403), `test_member_cannot_read_other_org_project` (404) |

### Required tests

| Test (`IMPLEMENTATION_PLAN.md:263`) | Status | Location |
|---|---|---|
| API liveness/readiness | Met | `tests/test_health.py` |
| Database migration up/down against an ephemeral database | Met | `tests/test_migrations.py` (Postgres in CI, SQLite locally) |
| Web smoke test | Met | `apps/web/app/page.test.ts` |
| Configuration failure tests | Met | `tests/test_config.py` |
| Object-storage adapter unit tests | Met | `tests/test_storage.py` |
| Authentication validation and cross-tenant authorization tests | Met | `tests/test_auth.py` |

Local suite at the Phase 0 tip: **31 API tests, 1 worker test, ruff clean, mypy strict clean.**

### Open items carried into Phase 1

- Tests build the schema via `Base.metadata.create_all` rather than running
  migrations, so model/migration drift is not caught automatically.
- `require_organization` returns 404 for an unknown organization before the
  membership check, revealing organization existence to any token holder.
- Migration `0002` was edited in place after being pushed. Safe once, because
  nothing is deployed and CI databases are ephemeral. **From this gate onward,
  never edit a merged migration — add a new revision.**

---

## Phase 1 — Paid-demo vertical slice

- **Gate commit:** _not reached_
- **Decision:** _not reached_

Slices landed so far (on `phase-1-products`):

| Commit | Slice |
|---|---|
| `9c12cac` | RFC 9457 problem details + org bootstrap |
| `cb0ed96` | Corrections: DB-backed org resolution, problem schema in OpenAPI, `urn:` problem types |
| `f9a776e` | `products`, `product_assets`, `version` fields (migration `0002`) |
| `4f2d4a1` | Cleanup: unique `(organization_id, sku)`, dependency usage, 422 problem schema |

Remaining Phase 1 scope: signed uploads, references + rights attestation,
campaigns, Runway adapter, generation attempts, reviews, cost events.
