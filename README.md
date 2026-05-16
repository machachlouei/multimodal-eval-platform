# MELP — Multimodal Evaluation & Learning Platform

Reference implementation of the system described in [Design-Doc.md](Design-Doc.md).

This repo covers **Phase 1** (foundations + pilot MVP) and **Phase 2** (judge plane,
statistics, multi-team) of the rollout plan. Phase 3 (production gating,
multimodal at scale, DR drills) is not implemented.

- 11 FastAPI services across three planes (control / data / judge)
- 25+ built-in metrics with bootstrap CIs and paired significance
- LLM-as-Judge orchestrator with calibration harness
- Python SDK, CLI, HTMX UI
- 43 unit tests, all green

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
# 1. Bring up Postgres, Redis, MinIO, Temporal, and the stub LLM gateway
docker-compose up -d

# 2. Install Python deps
uv sync                                 # or: pip install -e ".[dev]"

# 3. Run migrations + seed the captioner-pilot project + metric registry
make db-up
make seed

# 4. Start the API gateway + a worker
make run-gateway                        # http://localhost:8000
make run-worker                         # in another terminal

# 5. Edit examples/captioner_classic.yaml to fill in the IDs printed by seed,
#    then submit a run
melp run submit examples/captioner_classic.yaml
```

See [docs/getting-started.md](docs/getting-started.md) for the full walk-through
(including registering a judge config + calibration).

## Repo layout

```
melp/
  common/        Shared: db models, auth, errors, schemas, telemetry, IDs, storage
  services/      One subpackage per service (FastAPI apps + HTMX UI)
  workers/       Eval runner, metric pool, aggregator
  workflows/     Temporal workflow definitions + dispatch
  metrics/       Built-in metric plugins (classic, text, probability, speech, vision)
  stats/         Bootstrap CIs, paired permutation / t-tests, κ, α
  judge/         Judge orchestrator, prompt rendering, cache, calibration
  sdk/           Python SDK (wraps REST)
  cli/           Command-line tool
  scripts/       Dev helpers: seed_dev, run_all
migrations/      Alembic migrations (one revision: 0001_initial)
infra/           Dockerfile, k8s skeleton, deterministic LLM stub
docs/            decisions/ (ADRs), tech-stack.md, getting-started.md
tests/           Unit tests (43, all green)
examples/        Sample run-spec YAMLs
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

✅ = implemented and tested · ⚠️ = implemented with a documented gap · ✗ = not implemented.

| Capability | Phase | Status |
|---|---|---|
| Run lifecycle (FR-1) | 1 | ✅ |
| Model registry integration (FR-2) | 1 | ⚠️ pass-through stub; echo / http / callable / registry backends |
| Dataset versioning + immutability (FR-3) | 1 | ✅ two-phase publish, content-hashed |
| Metric registry (FR-4) | 1 | ✅ 25+ built-ins |
| LLM-as-Judge (FR-5) | 2 | ⚠️ orchestrator, cache, calibration ✅ · ensembling schema-only, DLQ has no consumer |
| Multimodal eval (FR-6) | 2 | ⚠️ schema + vision metrics over pre-computed features; production sharding is Phase 3 |
| Statistical rigor (FR-7) | 2 | ✅ bootstrap (percentile + BCa), paired permutation, paired t |
| Slicing & failure analysis (FR-8) | 2 | ✅ slice predicates as code; per-slice CIs |
| Dashboards & leaderboards (FR-9) | 2 | ⚠️ leaderboard API ✅ · dedicated UI page ✗ |
| APIs + SDK + CLI (FR-10) | 1 | ⚠️ REST + SDK + CLI ✅ · gRPC deferred ([ADR-008](docs/decisions/0008-rest-first-grpc-deferred.md)) |
| Webhooks / CI hooks (FR-11) | 2 | ⚠️ webhooks ✅ · CI gating endpoint ✗ (Phase 3) |
| Reproducibility (FR-12) | 1 | ✅ run rerun-by-ID; seeded RNG for CIs |
| RBAC (FR-13) | 2 | ✅ Viewer / Contributor / Maintainer / Owner |
| Audit log (FR-14) | 1 | ✅ before/after on every mutating action |

### Known gaps (have ADRs)

- [ADR-011](docs/decisions/0011-metric-loader-sandbox-gap.md) — metric loader
  runs in-process today; subprocess sandbox is required before Phase 3.
- [ADR-012](docs/decisions/0012-iceberg-stand-in.md) — result history is a
  JSON blob in object storage; real Iceberg writer lands with the lakehouse.
- See [tech-stack.md §5](docs/tech-stack.md#5-open-questions--known-gaps) for
  the smaller items (no OTel exporter wired, no service mesh, 8 unused deps).

For a side-by-side of what's done vs. what's left across both phases, the
ADRs and `tech-stack.md` are authoritative; ask in PR review if anything in
the table above is unclear.
