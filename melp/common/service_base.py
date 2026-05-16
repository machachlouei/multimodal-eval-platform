"""Common FastAPI app factory — wires telemetry, errors, healthchecks, metrics."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from .config import get_settings
from .errors import MELPError, generic_error_handler, melp_error_handler
from .telemetry import RequestContextMiddleware, configure_logging, metrics_endpoint


def make_app(service: str, title: str | None = None) -> FastAPI:
    s = get_settings()
    configure_logging(service, level=s.log_level)
    app = FastAPI(title=title or service, version="0.1.0")
    app.add_middleware(RequestContextMiddleware, service=service)
    app.add_exception_handler(MELPError, melp_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    @app.get("/healthz", response_class=PlainTextResponse)
    def healthz() -> str:
        return "ok"

    @app.get("/readyz", response_class=PlainTextResponse)
    def readyz() -> str:
        return "ok"

    @app.get("/metrics")
    def metrics():
        return metrics_endpoint()

    return app
