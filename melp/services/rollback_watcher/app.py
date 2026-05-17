"""Auto-rollback SLO watcher. Phase 3 / Design-Doc §12.5.

Polls Prometheus for the control-plane API error rate and the run-completion
latency SLI. When the SLO is breached for ``--window`` seconds, the watcher
emits a ``platform.rollback.requested`` webhook with the offending service
and metric. The real rollback executor (Argo Rollouts, Flagger, or
deployment-specific tooling) is downstream of this — we only emit the signal.

This service is intentionally tiny. It owns no state, only signals.

Env:
  MELP_PROMETHEUS_URL  default http://prometheus:9090
  MELP_ROLLBACK_WINDOW_S  default 600
  MELP_ROLLBACK_ERROR_RATE  default 0.01      (1% over the window)
  MELP_ROLLBACK_P99_LATENCY default 1.5       (seconds)
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from melp.common.config import get_settings
from melp.common.db import session_scope
from melp.common.service_base import make_app
from melp.common.telemetry import get_logger
from melp.common.webhooks import enqueue_event

log = get_logger(__name__)
app = make_app("rollback_watcher", title="MELP Rollback Watcher")


def _query(url: str, expr: str) -> float | None:
    try:
        with httpx.Client(timeout=5) as c:
            r = c.get(f"{url}/api/v1/query", params={"query": expr})
            r.raise_for_status()
            data = r.json()
            v = data["data"]["result"]
            return float(v[0]["value"][1]) if v else None
    except Exception as e:  # noqa: BLE001
        log.warning("prom.query_failed", expr=expr, error=str(e))
        return None


def evaluate_once() -> dict[str, Any]:
    prom = os.environ.get("MELP_PROMETHEUS_URL", "http://prometheus:9090")
    window = int(os.environ.get("MELP_ROLLBACK_WINDOW_S", "600"))
    err_floor = float(os.environ.get("MELP_ROLLBACK_ERROR_RATE", "0.01"))
    p99_floor = float(os.environ.get("MELP_ROLLBACK_P99_LATENCY", "1.5"))

    error_rate_expr = (
        f"sum(rate(melp_http_requests_total{{status=~\"5..\"}}[{window}s]))"
        f" / sum(rate(melp_http_requests_total[{window}s]))"
    )
    p99_expr = (
        f"histogram_quantile(0.99, sum(rate(melp_http_request_seconds_bucket[{window}s])) by (le))"
    )

    err = _query(prom, error_rate_expr)
    p99 = _query(prom, p99_expr)

    breaches: list[str] = []
    if err is not None and err > err_floor:
        breaches.append(f"error_rate={err:.4f} > {err_floor}")
    if p99 is not None and p99 > p99_floor:
        breaches.append(f"p99_latency={p99:.3f}s > {p99_floor}s")

    if breaches:
        with session_scope() as db:
            # Emit to every project's webhook subscribers — platform-level event.
            # In practice, downstream rollback executors subscribe themselves.
            from melp.common import models

            for proj in db.query(models.Project).all():
                enqueue_event(
                    db,
                    project_id=proj.id,
                    event="platform.rollback.requested",
                    payload={
                        "window_seconds": window,
                        "error_rate": err,
                        "p99_latency_seconds": p99,
                        "breaches": breaches,
                    },
                )
        log.warning("rollback.requested", breaches=breaches)
    return {"error_rate": err, "p99_latency": p99, "breaches": breaches}


@app.post("/v1/evaluate")
def evaluate() -> dict[str, Any]:
    return evaluate_once()


def run() -> None:
    import uvicorn

    s = get_settings()
    # Background loop is started by the service's own crontab in prod (every
    # 60 s) — running it inside this process keeps dev simple.
    import threading

    def loop():
        while True:
            evaluate_once()
            time.sleep(60)

    threading.Thread(target=loop, daemon=True).start()
    uvicorn.run("melp.services.rollback_watcher.app:app", host="0.0.0.0", port=s.port_aggregator + 10)


if __name__ == "__main__":
    run()
