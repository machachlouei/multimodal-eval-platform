# Tech Stack

This document maps every external technology in the codebase to the
architectural decision it implements, the alternatives we considered, and how
hard it would be to swap out later.

The table is the artifact. The narrative sections are signposts.

## Conventions

- **Architectural decision** — ADR file in [`docs/decisions/`](decisions/),
  or "—" for routine choices that don't merit an ADR.
- **Swap cost** — how disruptive a future replacement would be:
  - *Trivial* — one file, no contract change (e.g., logger library).
  - *Localised* — confined to one subsystem; public surface unchanged.
  - *Pervasive* — touches the public API, the data model, or every service.
- **Status: unused** — dependency listed in `pyproject.toml` but never
  imported. Candidates for removal; documented here to keep us honest.

---

## 1. Runtime dependencies (control plane + judge plane)

### Web framework / API

| Tech | Used for | Architectural decision | Alternatives & why not | Swap cost |
|---|---|---|---|---|
| **FastAPI** | Every service is a FastAPI app | [ADR-001](decisions/0001-three-plane-separation.md) (plane-shaped services), [ADR-008](decisions/0008-rest-first-grpc-deferred.md) (REST-first) | Django REST: heavier, ORM tightly coupled · Starlette alone: lacks request validation & OpenAPI · Tornado/aiohttp: less ergonomic for typed schemas | **Pervasive** — public API contract |
| **uvicorn** | ASGI server | [ADR-008](decisions/0008-rest-first-grpc-deferred.md) | Hypercorn: comparable, less battle-tested · gunicorn (sync): wrong concurrency model | Trivial |
| **Pydantic v2** | All request/response models + config | [ADR-008](decisions/0008-rest-first-grpc-deferred.md) (REST contract), [ADR-004](decisions/0004-versioned-sandboxed-metrics.md) (metric signatures) | Marshmallow: pre-typed-era, slower · attrs+cattrs: no schema export · dataclasses: no validation | Pervasive |
| **pydantic-settings** | Env-var-loaded config in `melp/common/config.py` | — | python-dotenv alone: no typing · dynaconf: heavier | Trivial |

### Persistence

| Tech | Used for | Architectural decision | Alternatives & why not | Swap cost |
|---|---|---|---|---|
| **PostgreSQL 16** | OLTP metadata for every entity | [ADR-002](decisions/0002-postgres-plus-iceberg.md) | MySQL: weaker JSON / array support · CockroachDB: cost vs. need · DynamoDB: loses relational integrity (see ADR-002) | Pervasive |
| **SQLAlchemy 2.0** | ORM + query builder | [ADR-002](decisions/0002-postgres-plus-iceberg.md) | Raw SQL via asyncpg: fast but loses migrations integration · SQLModel: wraps SQLA, adds a layer we don't need · Tortoise: smaller ecosystem | Pervasive (data access layer) |
| **psycopg 3 (binary)** | Postgres driver | [ADR-002](decisions/0002-postgres-plus-iceberg.md) | psycopg2: legacy, no async · asyncpg: async-only, doesn't pair with SQLA sync sessions cleanly | Trivial |
| **Alembic** | Schema migrations | [ADR-010](decisions/0010-single-launch-migration.md) | yoyo-migrations: smaller, no SQLA integration · raw SQL files: no rollback metadata | Localised |
| **Redis 7** | Judge response cache · AuthZ role cache · per-project rate-limit bucket · judge token-budget bucket · judge DLQ list | [ADR-003](decisions/0003-llm-as-judge-provider-abstraction.md) (cache), [ADR-001](decisions/0001-three-plane-separation.md) (cross-plane shared state) | Memcached: no list/stream primitives · in-process LRU: doesn't share across pods · Postgres as cache: wrong tool | Localised |
| **MinIO / S3-compatible object store** | Datasets · prediction artifacts · raw judge responses · aggregate result blobs | [ADR-005](decisions/0005-immutable-content-addressed-datasets.md), [ADR-012](decisions/0012-iceberg-stand-in.md) | Local filesystem: no multi-worker access · NFS: ops burden · GCS/S3 directly: works (boto3 is S3-compatible); MinIO is the dev surrogate | Localised |
| **boto3** | S3 client wrapper in `melp/common/storage.py` | [ADR-005](decisions/0005-immutable-content-addressed-datasets.md) | s3fs: filesystem-like but slower · aioboto3: async; not needed at current load | Trivial |
| **Iceberg (via PyIceberg)** | Analytical history of `run_result` rows | [ADR-002](decisions/0002-postgres-plus-iceberg.md), [ADR-012](decisions/0012-iceberg-stand-in.md) — **currently a JSON-blob stand-in** | Delta Lake: similar; choice depends on lakehouse · Parquet without table format: loses time-travel · ClickHouse: different cost model | Localised (writer-only seam) |

### Orchestration & compute

| Tech | Used for | Architectural decision | Alternatives & why not | Swap cost |
|---|---|---|---|---|
| **Temporal (`temporalio`)** | Durable workflow engine for run pipelines | [ADR-006](decisions/0006-temporal-workflow-engine.md) | Airflow: scheduled-DAG-shaped, weak retries · Argo: K8s-native, container-per-step overhead · state machine in Postgres: rebuilds Temporal badly | Localised (workflow-defn boundary) |
| **Ray** | Distributed eval runner pool (data plane) | [ADR-001](decisions/0001-three-plane-separation.md), Design-Doc §6.8 | Dask: smaller GPU support · Spark: heavy JVM, wrong shape · plain multiprocessing: no autoscaling | Localised |

### Identity, auth, transport

| Tech | Used for | Architectural decision | Alternatives & why not | Swap cost |
|---|---|---|---|---|
| **python-jose** | JWT decode for OIDC tokens | Design-Doc §9.1 | PyJWT: equivalent · authlib: heavier, more than we need | Trivial |
| **httpx** | Inter-service calls + LLM gateway calls | [ADR-001](decisions/0001-three-plane-separation.md), [ADR-003](decisions/0003-llm-as-judge-provider-abstraction.md) | requests: no async, no HTTP/2 · aiohttp: less ergonomic in sync code | Trivial |
| **tenacity** | 3-tier retry in judge orchestrator | [ADR-003](decisions/0003-llm-as-judge-provider-abstraction.md) | backoff: simpler but less expressive · rolling our own: tedious | Trivial |

### Statistics & math

| Tech | Used for | Architectural decision | Alternatives & why not | Swap cost |
|---|---|---|---|---|
| **NumPy** | All metric implementations + bootstrap resampling | [ADR-007](decisions/0007-bootstrap-cis-paired-permutation.md) | Pure Python: ~50× slower on bootstrap · PyTorch tensors: heavier dep | Pervasive (metric code) |
| **SciPy** | Paired t-test, BCa quantiles | [ADR-007](decisions/0007-bootstrap-cis-paired-permutation.md) | rolling our own normal/CDF: error-prone | Trivial |

### Observability & ops

| Tech | Used for | Architectural decision | Alternatives & why not | Swap cost |
|---|---|---|---|---|
| **structlog** | Structured JSON logs across every service | Design-Doc §13.1 | stdlib logging w/ JSON formatter: works but boilerplate-heavy · loguru: less interop with OTel | Trivial |
| **OpenTelemetry (api/sdk/instrumentation-fastapi)** | Tracing scaffolding; spans propagated via request-ID | Design-Doc §13.3 — **exporter not yet wired** | Vendor-specific SDKs: lock-in · Zipkin: legacy | Localised |
| **prometheus-client** | `/metrics` endpoint per service | Design-Doc §13.2 | OTel metrics: still maturing · push-based StatsD: doesn't fit pull-based Prometheus | Trivial |

### Clients & UI

| Tech | Used for | Architectural decision | Alternatives & why not | Swap cost |
|---|---|---|---|---|
| **click** | CLI framework (`melp` entry point) | [ADR-008](decisions/0008-rest-first-grpc-deferred.md) (CLI wraps SDK) | argparse: works but ugly groups · Typer: thin wrapper over click, adds Pydantic coupling we don't need | Trivial |
| **rich** | CLI tables + colorised output | — | tabulate: simpler, less polish · plain print: dev quality | Trivial |
| **pyyaml** | Run spec YAML parser (matches Design-Doc Appendix D) | — | ruamel.yaml: round-tripping; we don't need it · TOML: doc shows YAML | Trivial |
| **Jinja2** | HTMX UI templates only | [ADR-009](decisions/0009-htmx-ui.md) — **deliberately NOT used for judge prompts** ([`melp/judge/prompts.py`](../melp/judge/prompts.py)) | Mako: similar · server-rendered React: blocked by no-frontend-team constraint | Localised (UI-only) |
| **HTMX (CDN, no Python package)** | Server-driven interactivity in UI | [ADR-009](decisions/0009-htmx-ui.md) | React/Vite SPA: no headcount; see ADR | Localised (UI-only) |
| **python-ulid** | Type-prefixed IDs (`run_…`, `dsv_…`, …) | Design-Doc §7.2 | UUIDv7: similar sortable property; no Python stdlib generator yet · UUID4: not sortable by time | Pervasive (every primary key) |

### Listed but unused (recommend removal)

The following are declared in `pyproject.toml` but not imported anywhere in
`melp/` or `tests/`. They were placeholders for features I'd planned to use
external libraries for (and then implemented from scratch instead).

| Tech | Originally for | Actual code path | Status |
|---|---|---|---|
| **scikit-learn** | Reference AUC/log-loss/etc. | All re-implemented in `melp/metrics/probability.py` | **Unused** — remove |
| **sacrebleu** | Reference BLEU | `melp/metrics/text.py` re-implements (smoothed corpus BLEU) | **Unused** — keep as optional extra so teams can register a `package_uri` pointing at sacrebleu for fidelity |
| **rouge-score** | Reference ROUGE | `melp/metrics/text.py` re-implements ROUGE-{1,2,L} | **Unused** — same note as sacrebleu |
| **jiwer** | WER / CER | `melp/metrics/speech.py` re-implements Levenshtein-based WER/CER | **Unused** — same note |
| **Pillow** | Image processing for vision metrics | Vision metrics consume pre-computed features, not raw images | **Unused** — needed if real CLIPScore/FID land |
| **tiktoken** | Token counting for budget gate | Budget gate uses `len(prompt)//4` approximation | **Unused** — replace approximation before scale matters |
| **passlib** | Password hashing | We don't hash any passwords (OIDC only) | **Unused** — remove |
| **factory-boy** | Test fixtures | Tests use inline data | **Unused** — remove |

---

## 2. Infrastructure (docker-compose / k8s)

| Tech | Used for | Architectural decision | Alternatives & why not |
|---|---|---|---|
| **PostgreSQL 16** | Metadata + Temporal backend | [ADR-002](decisions/0002-postgres-plus-iceberg.md) | (see runtime row) |
| **Redis 7** | Cache + budget + DLQ | [ADR-003](decisions/0003-llm-as-judge-provider-abstraction.md) | (see runtime row) |
| **MinIO** | Local S3-compatible object store | [ADR-005](decisions/0005-immutable-content-addressed-datasets.md) | LocalStack: heavier, more services we don't need · seaweedfs: less S3-API parity |
| **Temporal auto-setup** | Workflow engine in dev | [ADR-006](decisions/0006-temporal-workflow-engine.md) | Same answer as runtime row |
| **Stub LLM gateway** (`infra/llm-stub/server.py`) | Deterministic judge responses in dev/CI | [ADR-003](decisions/0003-llm-as-judge-provider-abstraction.md) | Recording fixtures: harder to maintain · Mocking inside Python: doesn't exercise HTTP path |
| **Kubernetes** (production target) | Service runtime; node-pool isolation | [ADR-001](decisions/0001-three-plane-separation.md) | Nomad: less ML-team familiarity · plain VMs: no autoscaling story |
| **Single Dockerfile parameterised by `MELP_SERVICE`** | One image, many services | — | Per-service Dockerfile: more files, more drift; ours is small enough to share |

---

## 3. Build, dev, test tooling

| Tech | Used for | Why this and not the alternatives |
|---|---|---|
| **Python 3.11** | Runtime for everything | 3.11 perf, structural pattern match, ExceptionGroup; 3.12 added little we need; 3.10 lacks `Self` and StrEnum ergonomics. |
| **uv** (preferred) / pip | Dependency install | uv: 10–100× faster solver; pip works as fallback (`pip install -e ".[dev]"`). |
| **hatchling** | Build backend | Default for `uv`; minimal config; no setuptools legacy. |
| **pytest + pytest-asyncio** | Tests | unittest: noisier syntax; nose: deprecated. |
| **httpx.TestClient (via FastAPI)** | Service smoke tests | Same library as the SDK; no separate test transport. |
| **ruff** | Lint + format | flake8 + black + isort: 3 tools, slower; ruff is one binary that does all of it. |
| **mypy** | Static typing | pyright: faster, less ecosystem support; both are fine. |

---

## 4. How to use this map

- **Reviewing a PR that adds a dependency?** Add a row here. If you can't,
  the dep probably shouldn't land.
- **Considering a swap?** Read the *Swap cost* column. *Pervasive* means a
  proper migration plan; *Localised* means a single PR; *Trivial* means
  just do it.
- **Cleaning up tech debt?** Section 1's "Listed but unused" subtable is the
  shortlist. Removing those eight deps would cut the install footprint
  substantially (sklearn alone is ~30 MB).

---

## 5. Open questions / known gaps

- **gRPC is in Design-Doc.md §8.1 but absent from this stack.** Deferred per
  [ADR-008](decisions/0008-rest-first-grpc-deferred.md); re-evaluate at the
  end of Phase 2 if a hot path needs it.
- **OpenTelemetry exporter is not wired** — the SDK is present and request-ID
  middleware is in place, but no collector endpoint is configured. Counted
  against §13.3 in the "what's left" audit.
- **PyIceberg is not in deps yet** even though [ADR-012](decisions/0012-iceberg-stand-in.md)
  names it as the v2 target. Will land when the lakehouse target is real.
- **No service mesh** (Linstio/Linkerd) is wired in. The doc (§12.2) assumes
  one; for local dev we rely on plain HTTP + Docker DNS. Production
  deployment would add mTLS via the mesh, not the app.
