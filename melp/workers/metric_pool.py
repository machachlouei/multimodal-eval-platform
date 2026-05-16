"""Metric Compute Pool. Implements §6.9.

Loads each metric plugin via its ``package_uri``, runs it over the predictions
artifact written by the runner, and serialises per-example scores to S3. The
aggregator then folds these into per-slice point estimates + CIs.

Per-metric isolation: one metric's exception does not stop others (§6.9
failure behavior). For per-example metric exceptions the loaders catch and
count them — total run only fails if error rate exceeds a threshold.
"""
from __future__ import annotations

import json
from typing import Any

from melp.common import models
from melp.common.config import get_settings
from melp.common.db import session_scope
from melp.common.storage import get_bytes, put_bytes
from melp.common.telemetry import get_logger
from melp.metrics.base import MetricResult, load_metric

log = get_logger(__name__)


def _load_predictions(run_id: str) -> list[dict[str, Any]]:
    s = get_settings()
    raw = get_bytes(s.s3_bucket_artifacts, f"runs/{run_id}/predictions.jsonl")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def _evaluate_one(
    metric_version: models.MetricVersion,
    predictions: list,
    references: list,
    judge_scores: list | None,
) -> MetricResult:
    fn = load_metric(metric_version.package_uri)
    kwargs: dict[str, Any] = {}
    if judge_scores is not None:
        kwargs["judge_scores"] = judge_scores
    return fn(predictions, references, **kwargs)


def compute_metrics_for_run(run_id: str) -> int:
    s = get_settings()
    examples = _load_predictions(run_id)
    predictions = [ex.get("prediction") for ex in examples]
    references = [ex.get("reference") for ex in examples]

    # If judge configured, fetch per-example scores from judge orchestrator output.
    judge_scores: list | None = None
    with session_scope() as db:
        r = db.query(models.Run).filter_by(id=run_id).one()
        metric_versions = db.query(models.MetricVersion).filter(
            models.MetricVersion.id.in_(r.metric_version_ids)
        ).all()
        if r.judge_config_version_id:
            from melp.workers.aggregator import judge_scores_for_run

            judge_scores = judge_scores_for_run(run_id)

    summary: list[dict[str, Any]] = []
    for mv in metric_versions:
        try:
            result = _evaluate_one(mv, predictions, references, judge_scores)
            summary.append(
                {
                    "metric_version_id": mv.id,
                    "metric_name": mv.metric_id,
                    "aggregate": result.aggregate,
                    "per_example": result.per_example,
                    "n": result.n,
                }
            )
        except Exception as e:  # noqa: BLE001 — per-metric isolation
            log.error("metric.failed", metric_version_id=mv.id, run_id=run_id, error=str(e))
            summary.append({"metric_version_id": mv.id, "error": str(e)[:500]})
    put_bytes(
        s.s3_bucket_artifacts,
        f"runs/{run_id}/metric_results.json",
        json.dumps(summary).encode(),
        "application/json",
    )
    return len(summary)
