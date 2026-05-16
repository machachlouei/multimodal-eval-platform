"""Workflow-engine adapter. See ADR pre-flight decision (Temporal default).

In production this would talk to a Temporal cluster. For dev we tolerate the
absence of Temporal by leaving the run QUEUED and letting the in-process
``melp.workers.runner`` pick it up. The Run Service treats a dispatch failure
as ``PENDING_SUBMISSION`` and runs a reconciler (§6.3).
"""
from __future__ import annotations

import os

from melp.common.cache import redis_client
from melp.common.telemetry import get_logger

log = get_logger(__name__)


def submit_run_workflow(run_id: str) -> None:
    """Best-effort: push to Temporal if configured, else publish to a Redis stream
    so the local poller can pick it up immediately.
    """
    use_temporal = os.environ.get("MELP_USE_TEMPORAL", "0") == "1"
    if use_temporal:
        try:
            from melp.workflows.eval_workflow import start as start_temporal  # local import

            start_temporal(run_id)
            return
        except Exception as e:  # noqa: BLE001
            log.warning("temporal_dispatch_failed", error=str(e), run_id=run_id)
            raise
    # Local mode: nudge the worker via a Redis pub/sub channel; the worker also
    # polls the DB so missing the nudge is fine.
    try:
        redis_client().publish("melp:runs:new", run_id)
    except Exception as e:  # noqa: BLE001
        log.warning("redis_publish_failed", error=str(e))
