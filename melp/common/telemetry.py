"""Structured logging + OTel + Prometheus + request IDs. See §13."""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from fastapi import FastAPI, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

_REQUEST_ID: ContextVar[str] = ContextVar("request_id", default="")

REQUEST_COUNT = Counter(
    "melp_http_requests_total", "Total HTTP requests", ["service", "method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "melp_http_request_seconds", "HTTP request latency", ["service", "method", "path"]
)


def configure_logging(service: str, level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
    )
    structlog.contextvars.bind_contextvars(service=service)


def get_logger(name: str | None = None) -> Any:
    return structlog.get_logger(name)


def current_request_id() -> str:
    return _REQUEST_ID.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, service: str):
        super().__init__(app)
        self.service = service

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:16]}"
        token = _REQUEST_ID.set(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)
        import time

        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed = time.perf_counter() - t0
            path = request.url.path
            REQUEST_LATENCY.labels(self.service, request.method, path).observe(elapsed)
            _REQUEST_ID.reset(token)
        response.headers["x-request-id"] = rid
        REQUEST_COUNT.labels(self.service, request.method, request.url.path, response.status_code).inc()
        return response


def metrics_endpoint() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
