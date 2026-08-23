# AI Video Director V2 — Phase-Gated Implementation Plan

Status: implementation handoff
Plan date: 2026-08-23
Primary customer: furniture and interior-product brand creative teams
Initial promise: turn product assets plus an authorized creative reference into product-faithful, reviewable short-form campaign videos

## 1. Product decision

Do not build a generic "multi-agent AI video generator." Generation providers already expose much of the original concept:

- Runway Product Ad turns product images, style references, and creative direction into a short ad.
- Runway Product Swap preserves the reference video's motion, framing, lighting, and composition while replacing a product.
- Adobe Firefly accepts reference videos for composition and camera-motion transfer.

Therefore, provider orchestration is infrastructure, not the moat.

Build a **furniture campaign operating system** whose defensible assets are:

1. A structured product truth record for every SKU.
2. Automated product-fidelity and temporal-consistency evaluation.
3. A reusable, rights-aware vocabulary of shots and campaign structures.
4. Brand rules, approvals, version history, and provenance.
5. Catalog-scale batch creation and localization.
6. Cost/quality-aware provider routing.
7. A feedback loop connecting creative attributes to real campaign outcomes.

## 2. Narrow initial use case

### User

A creative or e-commerce manager at a furniture, lighting, homeware, or interior-product brand.

### Job to be done

> Given 3-10 clean product images, product facts, and a customer-owned or licensed reference clip/template, create several 5-15 second social-ready videos that preserve the product's identity and comply with the brand's rules.

### Initial output

- One product per generation.
- MP4, 720p or 1080p.
- 9:16 first; 1:1 and 16:9 variants later.
- A visible job history with cost, provider, prompt/recipe version, and approval state.
- Human approval before export or publication.

### Business validation gate

Before expanding the platform, complete at least 20 real campaign jobs across 3 design partners and achieve:

- At least 30% of generations approved after no more than two retries.
- Median operator time below 20 minutes per approved asset.
- Generation cost captured for 100% of jobs.
- At least 2 of the 3 partners willing to pay for another campaign.

If these conditions fail, improve or change the use case before adding more agents or providers.

## 3. Genius ideas, prioritized

### Build into the core product

#### A. Product Truth Passport

A versioned record containing source images, masks, dimensions, materials, colors, logos, copy, optional 3D models, and approved visual examples. Every output is evaluated against it. This converts "looks good" into auditable product fidelity.

#### B. Shot DNA instead of copying a reference

Extract an abstract shot grammar—duration, framing, camera path, subject placement, lighting, pacing, and transition—rather than treating another video as pixels to imitate. Store source rights and create a new plan from the grammar. This is more reusable and reduces copying risk.

#### C. Self-healing generation

The system identifies why a result failed—wrong geometry, logo corruption, color drift, flicker, or unsafe claim—and changes only the relevant control, provider, or reference set before retrying. Every retry must have a recorded reason.

#### D. Director controls

Expose business-friendly controls instead of raw prompts: product prominence, camera energy, luxury level, realism, lighting warmth, scene complexity, and reference adherence. Compile these controls into provider-specific inputs.

#### E. SKU Swarm

Take one approved campaign structure and generate controlled variations across a product collection. Preserve the same creative grammar while adapting dimensions, colors, claims, and product views per SKU.

#### F. Creative Genome

Represent every asset as structured creative attributes. Later connect these attributes to spend, view-through, click, and conversion data. Generate mutations of winners while changing one dimension at a time.

#### G. Rights and provenance ledger

Record ownership/license attestations for references and source assets, provider/model versions, transformations, and approvals. Add C2PA Content Credentials at export when feasible.

### Build after repeat usage is proven

#### H. Product Capture Coach

A guided phone capture flow tells the user which missing angles, lighting conditions, or close-ups are needed to improve fidelity. The output is a provider-ready reference sheet.

#### I. 3D rescue lane

When generative video repeatedly distorts a product, use a supplied GLB/USDZ model to render controlled keyframes, depth, normals, and masks, then condition generation on those assets. Use this selectively, not as the default pipeline.

#### J. Rights-cleared motion template library

Brands and agencies can save approved motion/composition templates for reuse. A marketplace is possible only after internal template reuse is demonstrated.

#### K. Creative preflight

Before expensive video generation, produce a cheap storyboard and predict risks: insufficient product angles, impossible interaction, dimension mismatch, unsupported duration, unsafe claim, or reference/product shape mismatch.

### Explicitly defer

- Training a foundation video model.
- A full nonlinear video editor.
- A public template marketplace.
- Automated ad buying or fully autonomous publishing.
- Broad support for unrelated industries.
- A complex LangGraph of many agents before approval/retry loops exist.
- Scraping or downloading third-party reference videos without documented rights.

## 4. Target architecture

### Repository layout

```text
ai-video-director/
  apps/web/                # Next.js 15, TypeScript
  services/api/            # FastAPI, REST/OpenAPI
  services/worker/         # Celery job consumers
  packages/contracts/      # Generated TypeScript client and shared schemas
  workflows/schemas/       # Versioned shot-plan and brand-rule JSON schemas
  workflows/prompts/       # Versioned prompt/recipe templates
  infrastructure/docker/
  tests/fixtures/          # Small licensed/synthetic assets
  tests/golden/            # Expected analysis/evaluation outputs
  docs/
```

### Core services

- **Web:** project, product, campaign, generation, comparison, review, and export UI.
- **API:** authentication, tenancy, metadata, validation, signed uploads, and job commands.
- **Worker:** FFmpeg, scene analysis, provider submission/polling, evaluation, retry, and export.
- **PostgreSQL:** authoritative metadata and workflow state.
- **S3/MinIO:** original uploads, frames, masks, provider outputs, proxies, and exports.
- **Redis:** Celery broker, short-lived locks, and rate limits; never the source of truth.
- **Provider adapters:** Runway first; provider payloads remain behind a typed interface.
- **Observability:** structured logs, traces, timings, provider errors, and cost ledger.

### Workflow rule

Use a deterministic state machine first:

```text
DRAFT -> ASSETS_READY -> PREFLIGHTED -> QUEUED -> GENERATING
      -> EVALUATING -> NEEDS_REVIEW -> APPROVED -> EXPORTED
                                |-> REJECTED -> QUEUED
                                |-> FAILED
```

Introduce LangGraph only when Phase 4 needs durable human interrupts, conditional critique/retry loops, or parallel specialist analysis. LangGraph's persisted state must not replace PostgreSQL application records.

### Minimum data model

- `organizations`, `users`, `memberships`, `projects`
- `products`, `product_assets`, `product_truth_versions`
- `references`, `reference_rights_attestations`
- `shot_plans`, `shot_plan_versions`, `shots`
- `brand_kits`, `brand_rule_versions`
- `campaigns`, `campaign_variants`
- `generation_jobs`, `generation_attempts`, `provider_tasks`
- `evaluations`, `evaluation_findings`
- `reviews`, `comments`, `approvals`
- `exports`, `provenance_records`, `cost_events`
- Later: `channel_connections`, `performance_observations`, `creative_genomes`

Every tenant-owned table must include `organization_id`. Every mutable creative object must be versioned rather than overwritten.

### Tenant isolation model

- Use a shared PostgreSQL schema with mandatory `organization_id` scoping in the service/repository layer.
- Store objects under immutable `org/{organization_id}/...` prefixes and verify the prefix before signing any URL.
- Include `organization_id` in every job payload and namespace Redis keys by organization.
- Never trust an organization ID supplied by the browser; derive membership from the authenticated principal.
- Start with shared queues and enforce per-organization concurrency/quotas. Separate queues are an operational option, not the security boundary.
- Add cross-tenant negative tests for every new resource type.

### Media asset lifecycle

```text
upload intent -> quarantine -> magic-byte/size/checksum validation -> malware scan
-> private immutable original -> normalized proxy/frames -> provider transfer
-> private result -> watermarked review proxy -> approved export -> retention/deletion
```

Preserve originals privately when required for fidelity or provenance. Strip EXIF and other unnecessary metadata from derivatives. Temporary frames and provider-transfer objects need explicit expiry policies.

### Provider contract

Each adapter implements:

```text
capabilities()
estimate(request)
validate(request)
submit(request, idempotency_key)
status(provider_task_id)
cancel(provider_task_id)
normalize_result(provider_response)
```

The normalized result includes provider, model/version, duration, resolution, request hash, provider task ID, timestamps, output assets, moderation outcome, and estimated/actual cost.

## 5. Phase-by-phase implementation

Only one phase is active at a time. The coding agent must finish tests, acceptance evidence, migration notes, and operator documentation before beginning the next phase.

---

## Phase 0 — Repository rescue and executable foundation

**Estimated effort:** 5-8 engineering days
**Objective:** turn the current blueprint into a clean, reproducible monorepo that builds and tests.

### Deliverables

1. Move usable Next.js code into `apps/web` and delete duplicated generated/nested app paths.
2. Create a root workspace with pinned Node and Python versions.
3. Create `services/api` with FastAPI and `GET /health/live`, `GET /health/ready`.
4. Create `services/worker` with a Celery health task.
5. Add PostgreSQL, Redis, and MinIO to Docker Compose with health checks and pinned images.
6. Add Alembic and the first migration for organizations, users, memberships, projects, and generation jobs.
7. Add `.env.example`; validate required variables at startup.
8. Add formatting, linting, unit tests, production builds, and CI.
9. Add an OpenAPI-to-TypeScript client generation script.
10. Replace production local-file writes with an object-storage abstraction; local filesystem is allowed only in tests.
11. Define the authentication contract: OIDC-compatible identity, API validation of issuer/audience/JWKS, and a deterministic local/test identity provider or fixture.
12. Add a centralized authorization/membership check used by all tenant-owned resources.
13. Document `development`, `test`, `staging`, and `production` configuration boundaries; Phase 0 only needs automated local/test deployment.

### Required commands

Document equivalents for:

```text
install
dev
lint
typecheck
test
build
db:migrate
```

### Acceptance criteria

- Clean clone installs without manually moving files.
- Web and API start together through documented commands.
- Docker services become healthy.
- Web calls the API readiness endpoint successfully.
- CI runs lint, typecheck, unit tests, and production builds.
- No duplicated `app/app/...` trees remain.
- No unpinned `latest` Docker images.
- No secret or generated media is committed.
- A valid test identity can access its organization and receives 403/404 for another organization.

### Tests

- API liveness/readiness.
- Database migration up/down against an ephemeral database.
- Web smoke test.
- Configuration failure tests.
- Object-storage adapter unit tests.
- Authentication validation and cross-tenant authorization tests.

### Non-goals

No AI analysis, generation call, authentication UI, LangGraph, or polished dashboard.

### Phase gate

Do not start Phase 1 until `build` and every automated test pass from a clean checkout.

---

## Phase 1 — Paid-demo vertical slice

**Estimated effort:** 10-15 engineering days
**Objective:** produce and approve one real product video through an end-to-end observable workflow.

### User flow

1. Create a project and product.
2. Add 3-10 product images and product facts.
3. Add an optional authorized reference video/style images.
4. Attest that the references may be used.
5. Choose `Product Ad` or `Product Swap`.
6. Enter a brief, submit, and observe progress.
7. Preview, approve, reject with a reason, or retry.
8. Download the approved MP4.

### Backend deliverables

- Direct-to-object-storage signed uploads and finalized asset records.
- Product, reference, campaign, job, attempt, review, and cost tables.
- MIME sniffing, limits, display-name sanitization, checksums, and antivirus hook interface.
- Reference rights fields for ownership/license type, source, permitted channels/territories, expiry, and reviewer notes; expired or unapproved rights block submission.
- Runway adapter implementing Product Ad and Product Swap.
- Async submit/poll/download with timeouts, bounded backoff, idempotency, cancellation, and restart recovery.
- A stuck-job sweeper and dead-letter/manual-recovery path; no job may remain indefinitely in a transient state.
- Job status via server-sent events or polling; choose one and test reconnection.
- Persist normalized provider requests/responses with secrets removed.
- Record estimated and actual credits/cost whenever available.
- Watermarked preview proxies; originals remain private.
- Temporary-frame cleanup and object lifecycle rules; derivatives strip unnecessary EXIF/metadata.
- Structured service metrics for queue delay, provider latency, success/failure, retry count, bytes stored, and cost.

### API surface

```text
POST   /v1/projects
GET    /v1/projects/{project_id}
POST   /v1/products
POST   /v1/assets/upload-intents
POST   /v1/assets/{asset_id}/complete
POST   /v1/references
POST   /v1/campaigns
POST   /v1/generations
GET    /v1/generations/{generation_id}
POST   /v1/generations/{generation_id}/cancel
POST   /v1/generations/{generation_id}/retry
POST   /v1/generations/{generation_id}/reviews
POST   /v1/generations/{generation_id}/approve
GET    /v1/assets/{asset_id}/download
```

### Acceptance criteria

- A real Runway job completes without copying URLs manually.
- A worker restart does not lose or duplicate a submitted provider task.
- The same idempotency key never creates a second chargeable attempt.
- Every attempt records provider/model, request hash, outcome, latency, and cost.
- Users cannot access another organization's assets or jobs.
- Failed jobs display an actionable normalized error.
- Approved outputs download through short-lived signed URLs.
- Expired or unapproved references cannot enter a paid provider request.
- Provider-independent system overhead is measured separately from generation latency; job state becomes visible to the UI within 10 seconds under normal operation.

### Tests

- Provider contract tests using recorded, redacted fixtures.
- Job transition and retry tests.
- Tenant isolation.
- Upload validation and path traversal.
- Timeout, 429, malformed response, and duplicate callback.
- Stuck-job recovery, dead-letter handling, reference expiry, and temporary-asset cleanup.
- One opt-in live-provider smoke test excluded from default CI.

### Business gate

Run 20 real jobs for 3 design partners. If nobody will review and pay for the result, revisit the use case before adding infrastructure.

---

## Phase 2 — Reference intelligence and Shot DNA

**Estimated effort:** 2 weeks
**Objective:** convert references into editable, provider-neutral creative plans instead of opaque prompts.

### Deliverables

- FFprobe metadata and FFmpeg proxy/frame extraction.
- PySceneDetect scene boundaries with manual split/merge.
- Versioned `ShotPlan` JSON Schema.
- Multimodal analysis behind a typed `VisionAnalyzer` interface.
- Per-shot fields: duration, shot size/angle, product placement/scale, camera motion/intensity, focal-length class, composition, depth layers, lighting, material/environment, action, transition, pacing, confidence, and evidence frame IDs.
- Timeline/storyboard UI with editable fields.
- Deterministic compiler from Shot DNA + product truth + brand rules to provider inputs.
- Creative preflight that catches incompatible plans before paid generation.
- Rights status visible in every derivative campaign.

### Schema rule

Analysis output is schema-validated structured JSON. Downstream generation must never depend on parsing free-form prose.

### Acceptance criteria

- Scene boundaries are correctable without re-uploading.
- Re-analysis creates a new version and preserves the old plan.
- Every asserted attribute has confidence and evidence.
- Same plan/compiler version produces identical compiled input.
- Users can borrow selected abstract attributes without carrying source frames forward.
- At least 80% of tested references produce schema-valid plans without manual JSON repair.

### Tests

- Golden video fixtures for boundaries and metadata.
- JSON Schema compatibility/migration.
- Prompt snapshots.
- Malformed multimodal response recovery.
- Rights propagation.

### Phase gate

At least five users must reuse or edit a Shot DNA plan. Otherwise keep reference analysis internal and do not build a marketplace.

---

## Phase 3 — Product Truth Passport and Fidelity Gate

**Estimated effort:** 3-4 weeks
**Objective:** reject or repair attractive outputs that misrepresent the product.

### Deliverables

- Truth editor for SKU, dimensions, proportions, materials, colors, logos, required details, prohibited changes, claims, and optional GLB/USDZ.
- Automatic product masks with manual correction.
- Reference-sheet generator from approved views.
- Frame-sampling evaluation pipeline with findings for product presence, masked similarity, silhouette/proportion drift, color difference, OCR corruption, material mismatch, temporal identity drift, flicker, object permanence, and shape compatibility.
- Versioned composite score with `PASS`, `REVIEW`, and `FAIL` thresholds.
- Evidence UI showing exact frames and rules.
- Retry recommendations; autonomous retries remain disabled until validated.

### Suggested technical path

- SAM 3 or equivalent for segmentation/tracking.
- CoTracker for point and geometry stability where useful.
- Video Depth Anything only when depth changes a decision.
- OCR and deterministic color/proportion checks before expensive VLM judging.
- Human ratings as calibration truth; an embedding score alone never proves fidelity.

### Acceptance criteria

- Benchmark includes at least 200 labeled findings across 50 generated clips.
- Severe geometry, logo, and wrong-color defects have below 10% false accepts.
- Composite score has at least 0.6 rank correlation with blinded human fidelity ratings; otherwise expose findings without claiming a reliable composite.
- Every failure includes evidence frames.
- Evaluation adds less than 20% to median generation cost.
- Reviewers spend at least 40% less time finding defects.

### Tests

- Deterministic evaluator unit tests.
- Golden masks/crops and corrupted logo/color fixtures.
- Versioned threshold calibration report.
- Regression test preventing scoring changes from silently altering old evaluations.

### Phase gate

No autonomous paid retries until offline tests show improved pass rate within the configured cost budget.

---

## Phase 4 — Brand OS and Campaign Factory

**Estimated effort:** 2-3 weeks
**Objective:** turn one successful generation into a governed, repeatable campaign.

### Deliverables

- Versioned brand kit: color, type, logos, tone, visual rules, product prominence, required/banned phrases, claims, disclaimers, music, and locale rules.
- Rule engine with deterministic checks before model judges.
- Campaign matrix: SKU x concept x aspect ratio x locale x channel.
- Batch generation with concurrency, quota, and spend caps.
- Review inbox, frame/time comments, attempt comparison, approval history, and role-based approval.
- Export presets for 9:16, 1:1, and 16:9 with captions, safe zones, thumbnails, and metadata.
- On-screen copy/subtitle localization; voice/dubbing optional.
- Durable pause/resume. Introduce LangGraph only if it simplifies real approval/repair loops.
- Self-healing retry in shadow mode, then opt-in after validation.

### Acceptance criteria

- One approved plan applies to at least 10 SKUs.
- Spend caps prevent further paid submissions.
- Partial batch failures retry without rerunning successes.
- Brand rules detect required, banned, and incorrect text in sampled frames.
- Every approval records actor, version, time, and comments.
- A 10-SKU campaign is reviewable/exportable without database manipulation.

### Tests

- Batch idempotency, partial failure, cancellation, and quotas.
- Brand rule valid/invalid fixtures.
- Approval authorization/audit history.
- Export safe zones and subtitle renders.

### Business gate

At least two customers must run a second campaign from saved products, brand kits, or plans. Repeat usage is the gate.

---

## Phase 5 — Provider router and cost/quality optimizer

**Estimated effort:** 2 weeks
**Objective:** make providers replaceable and reduce cost without reducing approval rate.

### Deliverables

- Capability registry for modes, duration, ratios, references, audio, pricing, limits, moderation, and version date.
- A second hosted adapter selected from actual customer needs; re-verify current terms/capabilities first.
- ComfyUI adapter for controlled/private workflows when justified.
- Policy router using hard constraints before historical quality, latency, and cost.
- Circuit breakers, concurrency controls, provider health, and bounded fallback.
- Budget estimator/reservation before submission.
- Model/version pinning and reproducibility metadata.
- Shadow routing and evaluation dashboard by provider, recipe, product category, and Shot DNA.

### Routing rule

Start with explicit rules. No bandit/learned router until comparable outcomes exist. Reviewer and option-exposure bias must be recorded.

### Acceptance criteria

- Contract tests pass for every adapter.
- Outages do not corrupt jobs or trigger unlimited fallback charges.
- Estimated cost appears before submission and hard budgets work.
- Decisions are explainable and replayable.
- Fixed benchmark shows at least 20% lower cost per approved output without meaningful approval-rate loss.

---

## Phase 6 — Creative Genome and performance learning

**Estimated effort:** 3-4 weeks
**Objective:** learn which controlled creative choices work for each brand and channel.

### Deliverables

- `CreativeGenome` from Shot DNA, brand settings, format, hook, pace, product prominence, text density, and audio style.
- Import performance observations from CSV first.
- Add read-only Meta/TikTok connections later only if customers request them and API approval is practical.
- Map platform creative IDs to immutable export IDs.
- Normalize spend, impressions, views, clicks, conversions, dates, audience, placement, and attribution settings.
- Experiment designer that changes one or a few dimensions.
- Winner mutation suggestions with supporting evidence.
- Guardrails against low samples, low spend, incompatible attribution, and audience changes.

### Acceptance criteria

- Every performance row traces to one immutable creative version.
- UI distinguishes correlation from causal evidence.
- Recommendations are suppressed below configurable thresholds.
- At least one customer runs a controlled second-generation experiment.
- First release requires no channel write/publish permission.

### Phase gate

No autonomous optimization or publishing until repeated controlled experiments show useful uplift and customers request it.

---

## Phase 7 — Enterprise trust and integrations

**Estimated effort:** 3-5 weeks
**Objective:** deploy within serious brand and agency workflows.

### Deliverables

- SSO/OIDC or SAML, granular RBAC, audit export, and service accounts.
- Configurable retention, legal holds, deletion workflows, and regional storage options.
- Customer-managed provider keys where required.
- Rights ledger and immutable asset lineage.
- C2PA Content Credentials for exported AI media where supported.
- Shopify catalog import for product facts, images, video, and 3D references.
- Webhooks/API for DAM, PIM, and agency workflows.
- Threat model, dependency/container scanning, backup/restore drill, and incident runbook.

### Acceptance criteria

- Cross-tenant tests find no unauthorized asset or metadata access.
- Audit log covers login, upload, generation, review, approval, export, and deletion.
- Restore drill meets documented recovery objectives.
- Rights/source lineage is visible from every exported asset.
- Shopify sync is incremental/idempotent and never overwrites curated truth without review.

## 6. Cross-phase engineering rules

### Security

- Private buckets and short-lived signed URLs.
- Verify magic bytes, not filename or browser MIME alone.
- Scan uploads before analysis.
- Encrypt secrets and redact provider payloads in logs.
- Enforce and test tenant scope.
- Require rights attestation for external references.
- Never execute uploaded workflow/model files as code.

### Reliability

- Every external call has timeout, bounded retry, idempotency, and a persisted task ID.
- Workers are at-least-once; handlers are idempotent.
- PostgreSQL is the workflow source of truth.
- Asset records use checksums and immutable object keys.
- Cancellation is best-effort and recorded.

### Cost control

- Record cost events for analysis, generation, evaluation, storage, and export.
- Reserve estimated spend before submission.
- Support organization, campaign, and job budgets.
- Never perform an autonomous paid retry without policy and remaining budget.

### AI quality

- Version prompts, schemas, evaluators, thresholds, models, and recipes.
- Maintain a licensed/synthetic golden dataset.
- Require schema-validated structured outputs.
- Store evidence for findings.
- Prefer deterministic checks over model judges.
- Track human overrides and disagreement.

### Observability

Each generation trace must answer who requested it; which product/reference/brand/plan versions were used; which provider/model/recipe ran; its cost and stage timings; why it passed, failed, retried, or needed review; and which output was approved/exported.

## 7. API and event conventions

- REST under `/v1`; OpenAPI is authoritative.
- UUIDv7 identifiers and UTC timestamps.
- Cursor pagination.
- RFC 9457 problem details.
- `Idempotency-Key` on chargeable commands.
- Optimistic concurrency/version fields on creative objects.
- Outbox pattern for durable job/event dispatch.
- Past-tense events such as `asset.uploaded`, `generation.submitted`, `generation.completed`, `evaluation.failed`, `review.requested`, `generation.approved`, and `export.created`.

## 8. Definition of done for every phase

A phase is done only when:

1. Scope and non-goals were respected.
2. Migrations and rollback notes exist.
3. Unit, integration, and required end-to-end tests pass.
4. Security/tenant tests pass for touched paths.
5. API and operator documentation are updated.
6. Metrics and cost events are visible.
7. Failure and restart behavior were exercised.
8. Acceptance evidence exists.
9. No secrets or customer media entered the repository.
10. The phase gate has a documented go, revise, or stop decision.

## 9. First coding-agent assignment

Give the coding agent only Phase 0 initially:

> Implement Phase 0 from `IMPLEMENTATION_PLAN.md`. Do not begin Phase 1. First inspect the repository and propose the exact moves/deletions, dependency versions, workspace layout, and commands. Preserve useful code but remove duplicated generated trees. Build a reproducible Next.js + FastAPI + Celery monorepo with PostgreSQL, Redis, MinIO, migrations, health checks, tests, CI, and an object-storage abstraction. Do not add generation providers, LangGraph, or AI analysis. Finish by running every documented install/lint/typecheck/test/build/migration command from a clean state and report evidence against each Phase 0 acceptance criterion.

After Phase 0 is accepted, issue a new task containing only Phase 1. Do not ask one agent to implement all phases in one pass.

## 10. Research anchors

These references are not endorsements. Re-verify pricing, availability, terms, and model names when implementing an adapter.

- [Runway Product Ad](https://docs.dev.runwayml.com/recipes/product-ad/)
- [Runway Product Swap](https://docs.dev.runwayml.com/recipes/product-swap/)
- [Runway API](https://docs.dev.runwayml.com/api/)
- [Adobe composition reference](https://helpx.adobe.com/uk/firefly/web/work-with-audio-and-video/work-with-video/use-video-as-composition-reference.html)
- [Adobe camera-motion reference](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-video/match-camera-motion-to-reference-video.html)
- [Adobe Style Kits](https://helpx.adobe.com/firefly/web/work-with-enterprise-features/collaborate-using-style-kits/style-kits-overview.html)
- [LangGraph human-in-the-loop](https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/breakpoints/)
- [ComfyUI Cloud API](https://docs.comfy.org/api-reference/cloud/overview)
- [SAM 3](https://ai.meta.com/sam3/)
- [CoTracker](https://github.com/facebookresearch/co-tracker)
- [Depth Anything](https://github.com/DepthAnything)
- [Shopify product media](https://shopify.dev/docs/api/storefront/latest/interfaces/media)
- [Google Merchant Center 3D models](https://support.google.com/merchants/answer/13675100)
- [C2PA specification](https://spec.c2pa.org/specifications/specifications/2.4/index.html)
