"""Results Aggregator. Implements §6.10.

Reads per-example metric outputs, computes:
  - Per-slice point estimates,
  - Bootstrap 95% CIs,
  - Paired significance vs. ``baseline_run_id`` when supplied,
and writes ``run_result`` rows + a results blob to S3 (§7.3 Iceberg target;
JSONL stand-in in dev). Idempotent on ``(run_id, metric_version_id, slice_def_id)``.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from melp.common import models
from melp.common.config import get_settings
from melp.common.db import session_scope
from melp.common.ids import new_id
from melp.common.storage import get_bytes, put_bytes
from melp.common.telemetry import get_logger
from melp.stats import bootstrap_ci, paired_permutation_test

log = get_logger(__name__)


def _load_examples(run_id: str) -> list[dict[str, Any]]:
    s = get_settings()
    raw = get_bytes(s.s3_bucket_artifacts, f"runs/{run_id}/predictions.jsonl")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def _load_metric_results(run_id: str) -> list[dict[str, Any]]:
    s = get_settings()
    raw = get_bytes(s.s3_bucket_artifacts, f"runs/{run_id}/metric_results.json")
    return json.loads(raw)


def judge_scores_for_run(run_id: str) -> list[float]:
    """Look up per-example judgments for ``run_id`` in order."""
    with session_scope() as db:
        judgments = (
            db.query(models.Judgment)
            .filter_by(run_id=run_id)
            .order_by(models.Judgment.created_at.asc())
            .all()
        )
    # rubric_scores is a dict; use 'score' if present else average values
    out: list[float] = []
    for j in judgments:
        rs = j.rubric_scores or {}
        if "score" in rs:
            out.append(float(rs["score"]))
        elif rs:
            out.append(float(sum(rs.values()) / len(rs)))
        else:
            out.append(0.0)
    return out


def _evaluate_slice(
    examples: list[dict[str, Any]],
    per_example: list[float],
    predicate: str,
) -> tuple[list[float], list[int]]:
    """Apply ``predicate`` (Python expression on ``example`` dict) and return
    (filtered_scores, indices_kept)."""
    scope: dict[str, Any] = {}
    keep: list[int] = []
    for i, ex in enumerate(examples):
        try:
            scope["example"] = ex
            if bool(eval(predicate, {"__builtins__": {}}, scope)):  # noqa: S307 dev sandbox
                keep.append(i)
        except Exception:  # noqa: BLE001 — predicate problems are slice-bugs
            continue
    return [per_example[i] for i in keep], keep


def _baseline_per_example(
    db: Session, baseline_run_id: str, metric_version_id: str
) -> list[float] | None:
    s = get_settings()
    raw = get_bytes(s.s3_bucket_artifacts, f"runs/{baseline_run_id}/metric_results.json")
    for item in json.loads(raw):
        if item.get("metric_version_id") == metric_version_id and "per_example" in item:
            return list(item["per_example"])
    return None


def aggregate_run(run_id: str) -> None:
    examples = _load_examples(run_id)
    metric_results = _load_metric_results(run_id)
    with session_scope() as db:
        r = db.query(models.Run).filter_by(id=run_id).one()
        slices = (
            db.query(models.SliceDef).filter_by(dataset_version_id=r.dataset_version_id).all()
        )
        r.status = "AGGREGATING"

        result_summary: list[dict[str, Any]] = []
        for item in metric_results:
            if "error" in item:
                continue
            mvid = item["metric_version_id"]
            per_example: list[float] = list(item.get("per_example") or [])
            if not per_example:
                # Single-value metric: persist as point estimate, no CI.
                rr = models.RunResult(
                    id=new_id("run_result"),
                    run_id=run_id,
                    metric_version_id=mvid,
                    slice_def_id=None,
                    point_estimate=float(item["aggregate"]),
                    n_examples=int(item.get("n", 0)),
                )
                db.merge(rr)
                continue

            # Overall slice (slice_def_id NULL).
            ci = bootstrap_ci(per_example, n_resamples=500, seed=r.seed)
            p_val: float | None = None
            effect: float | None = None
            if r.baseline_run_id:
                b = _baseline_per_example(db, r.baseline_run_id, mvid)
                if b and len(b) == len(per_example):
                    sig = paired_permutation_test(per_example, b, n_resamples=2_000, seed=r.seed)
                    p_val, effect = sig.p_value, sig.effect_size

            rr = models.RunResult(
                id=new_id("run_result"),
                run_id=run_id,
                metric_version_id=mvid,
                slice_def_id=None,
                point_estimate=ci.point_estimate,
                ci_low=ci.ci_low,
                ci_high=ci.ci_high,
                ci_method=ci.method,
                n_examples=len(per_example),
                baseline_run_id=r.baseline_run_id,
                p_value=p_val,
                effect_size=effect,
            )
            db.merge(rr)
            result_summary.append(
                {
                    "metric_version_id": mvid,
                    "slice": "overall",
                    "point": ci.point_estimate,
                    "ci": [ci.ci_low, ci.ci_high],
                    "n": len(per_example),
                }
            )

            # Per-slice.
            for sd in slices:
                if r.slice_set and sd.id not in r.slice_set and sd.name not in r.slice_set:
                    continue
                vals, _ = _evaluate_slice(examples, per_example, sd.predicate)
                if not vals:
                    continue
                sci = bootstrap_ci(vals, n_resamples=500, seed=r.seed)
                rr_s = models.RunResult(
                    id=new_id("run_result"),
                    run_id=run_id,
                    metric_version_id=mvid,
                    slice_def_id=sd.id,
                    point_estimate=sci.point_estimate,
                    ci_low=sci.ci_low,
                    ci_high=sci.ci_high,
                    ci_method=sci.method,
                    n_examples=len(vals),
                )
                db.merge(rr_s)
                result_summary.append(
                    {
                        "metric_version_id": mvid,
                        "slice": sd.name,
                        "point": sci.point_estimate,
                        "ci": [sci.ci_low, sci.ci_high],
                        "n": len(vals),
                    }
                )
        # Persist a results blob (Iceberg target in prod, JSON stand-in here).
        s = get_settings()
        put_bytes(
            s.s3_bucket_results,
            f"runs/{run_id}/aggregate.json",
            json.dumps(result_summary).encode(),
            "application/json",
        )
        r.completed_at = datetime.now(UTC)
