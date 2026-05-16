"""Eval Runner. Implements §6.8.

Two execution modes:
  - **Ray** (prod): activities sharded across Ray workers; each shard processes
    a contiguous example range. Requires ``MELP_USE_RAY=1`` and a Ray cluster.
  - **Local** (dev/tests): single-process loop that polls Postgres for QUEUED
    runs and processes them sequentially.

Activities are split so that Temporal can checkpoint between them (see
``melp.workflows.eval_workflow``). In local mode they are called in sequence.

Model backends:
  - ``echo``: prediction = input. Useful for end-to-end smoke tests.
  - ``http``: POST {"input": ...} to ``ModelVersion.uri``; expect {"prediction": ...}.
  - ``callable``: ``ModelVersion.uri`` is a python:module:fn URI.
  - ``registry``: stub — would call the Model Registry's serving sidecar.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from melp.common import models
from melp.common.config import get_settings
from melp.common.db import session_scope
from melp.common.storage import get_bytes, list_keys, put_bytes
from melp.common.telemetry import configure_logging, get_logger
from melp.common.webhooks import enqueue_event

log = get_logger(__name__)


# ---------- Dataset I/O ----------
def _parse_s3_uri(uri: str) -> tuple[str, str]:
    if uri.startswith("s3://"):
        parts = uri.removeprefix("s3://").split("/", 1)
        return parts[0], parts[1] if len(parts) > 1 else ""
    raise ValueError(f"unsupported uri: {uri}")


def iter_dataset(dv: models.DatasetVersion) -> Iterable[dict[str, Any]]:
    """Yield examples from a dataset version.

    Convention: ``asset_root_uri`` points to one or more JSONL files under an
    S3 prefix. Each line is ``{"id": ..., "input": ..., "reference": ...,
    "context": ..., **other}``. Other modalities (images, audio) reference
    additional S3 URIs in the line; the runner reads them on demand.
    """
    bucket, prefix = _parse_s3_uri(dv.asset_root_uri)
    keys = [k for k in list_keys(bucket, prefix) if k.endswith(".jsonl")]
    if not keys:
        # Fallback: treat the URI as a single key.
        keys = [prefix]
    for key in sorted(keys):
        raw = get_bytes(bucket, key)
        for line in raw.decode("utf-8").splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)


# ---------- Model invocation ----------
def _model_callable(mv: models.ModelVersion) -> Callable[[Any], Any]:
    if mv.backend == "echo":
        return lambda x: x
    if mv.backend == "http":
        client = httpx.Client(timeout=30)

        def call(x: Any) -> Any:
            r = client.post(mv.uri, json={"input": x})
            r.raise_for_status()
            return r.json().get("prediction")

        return call
    if mv.backend == "callable":
        # uri like python:module:fn
        from melp.metrics.base import load_metric  # reuse resolver

        return load_metric(mv.uri)
    if mv.backend == "registry":
        # In prod: call Model Registry's serving sidecar. Stubbed as echo.
        return lambda x: x
    raise ValueError(f"unknown model backend: {mv.backend}")


# ---------- Activities (also reused by Temporal) ----------
def _set_run_status(db: Session, run_id: str, status: str, **fields: Any) -> models.Run:
    r = db.query(models.Run).filter_by(id=run_id).one()
    r.status = status
    for k, v in fields.items():
        setattr(r, k, v)
    return r


def load_dataset_for_run(run_id: str) -> int:
    """Materialise the dataset shard manifest. Returns example count."""
    with session_scope() as db:
        r = db.query(models.Run).filter_by(id=run_id).one()
        dv = db.query(models.DatasetVersion).filter_by(id=r.dataset_version_id).one()
        n = sum(1 for _ in iter_dataset(dv))
        r.progress = {"examples_total": n, "examples_done": 0}
        return n


def run_inference_for_run(run_id: str) -> int:
    """Run the candidate model on every example; write a predictions artifact."""
    s = get_settings()
    with session_scope() as db:
        r = _set_run_status(db, run_id, "RUNNING", started_at=datetime.now(UTC))
        mv = db.query(models.ModelVersion).filter_by(id=r.model_version_id).one()
        dv = db.query(models.DatasetVersion).filter_by(id=r.dataset_version_id).one()
        enqueue_event(db, project_id=r.project_id, event="run.started", payload={"run_id": run_id})
    # Streaming outside the DB session.
    fn = _model_callable(mv)
    out_lines: list[str] = []
    done = 0
    total = 0
    for ex in iter_dataset(dv):
        total += 1
        pred = fn(ex.get("input"))
        out_lines.append(json.dumps({"id": ex.get("id", str(total)), "prediction": pred, "reference": ex.get("reference"), **{k: v for k, v in ex.items() if k not in ("input", "reference")}}))
        done += 1
        if done % 100 == 0:
            with session_scope() as db:
                db.query(models.Run).filter_by(id=run_id).update(
                    {"progress": {"examples_total": total, "examples_done": done}}
                )
    blob = ("\n".join(out_lines) + "\n").encode()
    put_bytes(s.s3_bucket_artifacts, f"runs/{run_id}/predictions.jsonl", blob, "application/x-ndjson")
    with session_scope() as db:
        db.query(models.Run).filter_by(id=run_id).update(
            {"progress": {"examples_total": total, "examples_done": done}}
        )
    return done


# ---------- Top-level orchestration (local mode) ----------
def process_run_locally(run_id: str) -> None:
    """Run all activities in-process. Used in dev and tests."""
    settings = get_settings()
    log.info("run.start", run_id=run_id)
    try:
        load_dataset_for_run(run_id)
        run_inference_for_run(run_id)
        # Optional: judge plane.
        with session_scope() as db:
            r = db.query(models.Run).filter_by(id=run_id).one()
            needs_judge = r.judge_config_version_id is not None
        if needs_judge:
            from melp.judge.orchestrator import judge_run

            preds_raw = get_bytes(settings.s3_bucket_artifacts, f"runs/{run_id}/predictions.jsonl")
            examples = [json.loads(l) for l in preds_raw.decode().splitlines() if l.strip()]
            judge_run(run_id, examples)
        from melp.workers.metric_pool import compute_metrics_for_run

        compute_metrics_for_run(run_id)
        from melp.workers.aggregator import aggregate_run

        aggregate_run(run_id)
        with session_scope() as db:
            r = _set_run_status(db, run_id, "COMPLETED", completed_at=datetime.now(UTC))
            enqueue_event(db, project_id=r.project_id, event="run.completed", payload={"run_id": run_id})
        log.info("run.complete", run_id=run_id)
    except Exception as e:  # noqa: BLE001
        log.error("run.failed", run_id=run_id, error=str(e))
        with session_scope() as db:
            r = _set_run_status(
                db,
                run_id,
                "FAILED",
                error=str(e)[:1000],
                completed_at=datetime.now(UTC),
            )
            enqueue_event(db, project_id=r.project_id, event="run.failed", payload={"run_id": run_id, "error": str(e)[:500]})


def run() -> None:
    """Long-lived poller. Picks up QUEUED runs and processes them."""
    s = get_settings()
    configure_logging("worker", level=s.log_level)
    log.info("worker.start")
    while True:
        with session_scope() as db:
            r = (
                db.query(models.Run)
                .filter(models.Run.status == "QUEUED")
                .order_by(models.Run.submitted_at.asc())
                .first()
            )
            run_id = r.id if r else None
        if run_id:
            process_run_locally(run_id)
        else:
            time.sleep(1)


if __name__ == "__main__":
    run()
