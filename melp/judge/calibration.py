"""Judge calibration harness. Implements §6.6 (calibration block) and §14.3.

Periodically runs the judge against a golden set with known human ratings,
computes inter-rater agreement (Cohen's κ, Krippendorff's α), persists a
``calibration_run`` row, and alerts when agreement drops below floor.

Golden set format (JSONL at ``calibration_set_uri``):
  {"id": ..., "input": ..., "human_score": 0.0..1.0}
"""
from __future__ import annotations

import json
from typing import Any

from melp.common import models
from melp.common.db import session_scope
from melp.common.ids import new_id
from melp.common.storage import get_bytes
from melp.common.telemetry import get_logger
from melp.judge.orchestrator import judge_one
from melp.stats.significance import cohen_kappa, krippendorff_alpha

log = get_logger(__name__)
DEFAULT_KAPPA_FLOOR = 0.7  # §13.6 SLO


def _load_golden(uri: str) -> list[dict[str, Any]]:
    if uri.startswith("s3://"):
        bucket, key = uri.removeprefix("s3://").split("/", 1)
        raw = get_bytes(bucket, key)
    else:
        with open(uri, "rb") as f:
            raw = f.read()
    return [json.loads(l) for l in raw.decode().splitlines() if l.strip()]


def _bin(score: float, thresholds: list[float] | None = None) -> int:
    """Discretise a continuous score for Cohen's κ. Default: 3 bins."""
    if thresholds is None:
        thresholds = [0.33, 0.66]
    for i, t in enumerate(thresholds):
        if score < t:
            return i
    return len(thresholds)


def run_calibration(
    judge_config_version_id: str,
    *,
    kappa_floor: float = DEFAULT_KAPPA_FLOOR,
) -> dict[str, Any]:
    with session_scope() as db:
        jcv = db.query(models.JudgeConfigVersion).filter_by(id=judge_config_version_id).one()
        pv = db.query(models.PromptVersion).filter_by(id=jcv.prompt_version_id).one()
        jc = db.query(models.JudgeConfig).filter_by(id=jcv.judge_config_id).one()
        project_id = jc.project_id

    if not jcv.calibration_set_uri:
        raise ValueError("judge config has no calibration set")
    golden = _load_golden(jcv.calibration_set_uri)
    if not golden:
        raise ValueError("golden set empty")

    human, judge = [], []
    for ex in golden:
        try:
            out = judge_one(
                run_id=f"cal_{judge_config_version_id}",
                project_id=project_id,
                judge_config_version=jcv,
                prompt_version=pv,
                example=ex,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("calibration.example_failed", error=str(e))
            continue
        score = out["parsed"].get("score")
        if score is None:
            continue
        judge.append(float(score))
        human.append(float(ex["human_score"]))

    kappa = cohen_kappa([_bin(s) for s in human], [_bin(s) for s in judge]) if human else None
    alpha = krippendorff_alpha([human, judge]) if human else None
    drift = kappa is not None and kappa < kappa_floor

    with session_scope() as db:
        db.add(
            models.CalibrationRun(
                id=new_id("calibration_run"),
                judge_config_version_id=judge_config_version_id,
                cohen_kappa=kappa,
                krippendorff_alpha=alpha,
                n_examples=len(human),
                notes=("drift" if drift else "ok"),
            )
        )
        if drift:
            from melp.common.webhooks import enqueue_event

            enqueue_event(
                db,
                project_id=project_id,
                event="judge.calibration.drift",
                payload={
                    "judge_config_version_id": judge_config_version_id,
                    "kappa": kappa,
                    "alpha": alpha,
                    "floor": kappa_floor,
                },
            )

    return {
        "judge_config_version_id": judge_config_version_id,
        "cohen_kappa": kappa,
        "krippendorff_alpha": alpha,
        "n_examples": len(human),
        "drift": drift,
    }
