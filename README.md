# MELP — Multimodal Evaluation & Learning Platform

Reference implementation of the system described in [Design-Doc.pdf](Design-Doc.pdf).

This repo covers **Phase 1** (foundations + pilot MVP) and **Phase 2** (judge plane,
statistics, multi-team) of the rollout plan. Phase 3 hooks (gating, multimodal at
scale, DR drills) are not implemented.

## What's in here

| Plane | Components |
|---|---|
| Control | `api-gateway`, `authz`, `run`, `dataset`, `model`, `metric`, `judge-config`, `project`, `audit` |
| Data | Temporal workflow, Ray eval runners, metric pool, results aggregator |
| Judge | Orchestrator, prompt registry, response cache, calibration harness |
| Clients | Python SDK, CLI, HTMX UI |

All services are FastAPI apps in the `melp/services/` tree. They share one
SQLAlchemy schema (Postgres) and one Pydantic schema package. Each can be deployed
as its own container — see `infra/docker/`.

## Quick start

```bash
# 1. Bring up Postgres, Redis, MinIO, Temporal
docker-compose up -d

# 2. Install Python deps
uv sync   # or: pip install -e ".[dev]"

# 3. Run migrations + seed
make db-up
make seed

# 4. Start the API gateway + a sample worker
make run-gateway       # http://localhost:8000
make run-worker        # in another terminal

# 5. Submit a run via the CLI
melp run submit examples/captioner_classic.yaml
```

See [docs/getting-started.md](docs/getting-started.md) for details.

## Repo layout

```
melp/
  common/        Shared: db models, auth, errors, schemas, telemetry, IDs, storage
  services/      One subpackage per control-plane service (FastAPI apps)
  workers/       Ray runner, metric pool, calibration worker
  workflows/     Temporal workflow definitions
  metrics/       Built-in metric plugins (registry + implementations)
  stats/         Bootstrap CIs, paired significance tests
  judge/         Judge orchestrator, prompt registry, cache, calibration
  sdk/           Python SDK (wraps REST)
  cli/           Command-line tool
migrations/      Alembic migrations
ui/              HTMX templates + static assets
infra/           Dockerfiles, k8s manifests, terraform stubs
tests/           unit / integration / e2e
examples/        Sample run specs and judge configs
```

## Design references

Every component file header references the section of `Design-Doc.md` it
implements (e.g. `# Implements §6.3 Run Service`).

- [`docs/decisions/`](docs/decisions/) — Architecture Decision Records (one
  per major design choice, including divergences from the doc).
- [`docs/tech-stack.md`](docs/tech-stack.md) — every external dependency
  mapped to the ADR / architectural decision it serves, with alternatives
  and swap cost.
- [`docs/getting-started.md`](docs/getting-started.md) — local dev setup.

## Status

| Capability | Phase | Status |
|---|---|---|
| Run lifecycle (FR-1) | 1 | ✅ |
| Model registry integration (FR-2) | 1 | ✅ stub |
| Dataset versioning + immutability (FR-3) | 1 | ✅ |
| Metric registry + 5 built-ins (FR-4) | 1 | ✅ |
| LLM-as-Judge (FR-5) | 2 | ✅ |
| Multimodal eval (FR-6) | 2 | ✅ schema; vision metrics implemented |
| Statistical rigor (FR-7) | 2 | ✅ |
| Slicing & failure analysis (FR-8) | 2 | ✅ |
| Dashboards & leaderboards (FR-9) | 2 | ✅ basic |
| APIs + SDK + CLI (FR-10) | 1 | ✅ REST + SDK + CLI (gRPC deferred) |
| Webhooks / CI hooks (FR-11) | 2 | ✅ |
| Reproducibility (FR-12) | 1 | ✅ |
| RBAC (FR-13) | 2 | ✅ |
| Audit log (FR-14) | 1 | ✅ |
