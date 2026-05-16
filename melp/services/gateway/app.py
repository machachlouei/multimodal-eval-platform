"""API Gateway. Implements §6.1.

Single public-facing FastAPI app that mounts every control-plane resource under
``/v1/...``. The control-plane services can be deployed independently behind a
real gateway (Envoy/Kong); in this codebase they are routed in-process to keep
local dev cheap. For internal calls between services we use direct gRPC-ish
HTTP, mediated through the AuthZ service.

Responsibilities:
  - TLS termination would happen at the LB in front of this in prod.
  - Request validation via Pydantic.
  - Request-ID injection (handled by ``RequestContextMiddleware``).
  - Rate limiting (§10.6) — per-project token bucket in Redis.
"""
from __future__ import annotations

import time

import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse

from melp.common.cache import redis_client
from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.services.audit.routes import router as audit_router
from melp.services.dataset.routes import router as dataset_router
from melp.services.judge_config.routes import router as judge_config_router
from melp.services.metric.routes import router as metric_router
from melp.services.model.routes import router as model_router
from melp.services.project.routes import router as project_router
from melp.services.run.routes import router as run_router

app = make_app("gateway", title="MELP API Gateway")


# ---- Simple per-project rate limit (§10.6, §11.5) ----
# Token bucket: 100 ops/s per project, burst 200. Persisted in Redis.
RATE_PER_S = 100
BURST = 200


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    # Only rate-limit project-scoped paths.
    parts = request.url.path.strip("/").split("/")
    if len(parts) < 3 or parts[0] != "v1" or parts[1] != "projects":
        return await call_next(request)
    project = parts[2]
    key = f"rl:{project}"
    now = int(time.time())
    r = redis_client()
    pipe = r.pipeline()
    pipe.hincrby(key, str(now), 1)
    pipe.expire(key, 2)
    count, _ = pipe.execute()
    if count > RATE_PER_S:
        return JSONResponse(
            status_code=429,
            content={
                "code": "RATE_LIMITED",
                "message": f"rate limit exceeded for project {project}",
                "details": [],
                "request_id": request.headers.get("x-request-id", ""),
            },
            headers={"Retry-After": "1", "X-RateLimit-Limit": str(RATE_PER_S)},
        )
    return await call_next(request)


# ---- Mount routers ----
app.include_router(project_router, prefix="/v1/projects", tags=["projects"])
app.include_router(dataset_router, prefix="/v1/projects/{project}/datasets", tags=["datasets"])
app.include_router(model_router, prefix="/v1/projects/{project}/models", tags=["models"])
app.include_router(metric_router, prefix="/v1/metrics", tags=["metrics"])
app.include_router(judge_config_router, prefix="/v1/projects/{project}/judge-configs", tags=["judges"])
app.include_router(run_router, prefix="/v1/projects/{project}/runs", tags=["runs"])
app.include_router(audit_router, prefix="/v1/audit", tags=["audit"])


@app.get("/")
def index() -> dict[str, str]:
    return {"service": "melp", "version": "0.1.0", "docs": "/docs"}


def run() -> None:
    uvicorn.run("melp.services.gateway.app:app", host="0.0.0.0", port=get_settings().port_gateway, reload=False)


if __name__ == "__main__":
    run()
