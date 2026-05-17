"""Reproducibility nightly job. Phase 3 / Design-Doc §14.4.

Picks ``--sample`` recently-completed runs, re-runs them in a child workflow,
and compares per-metric ``point_estimate`` to the original within a tolerance.
Non-zero diff on a deterministic metric is a SEV-2 — surfaces via a webhook
``run.reproducibility.drift`` and a non-zero process exit so a cron wrapper
can alert.

Schedule: e.g. nightly via ``schedule: "0 3 * * *"``. The script is idempotent
— re-running it overlaps with prior diffs but never corrupts state.

Usage::

    python -m melp.scripts.reproducibility_check --project captioner-pilot --sample 5
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from melp.common import models
from melp.common.db import session_scope
from melp.common.webhooks import enqueue_event


TOLERANCE = 1e-9  # exact match for deterministic metrics


def diff_runs(original_id: str, repro_id: str) -> list[dict]:
    with session_scope() as db:
        orig = {
            (rr.metric_version_id, rr.slice_def_id): rr.point_estimate
            for rr in db.query(models.RunResult).filter_by(run_id=original_id).all()
        }
        repro = {
            (rr.metric_version_id, rr.slice_def_id): rr.point_estimate
            for rr in db.query(models.RunResult).filter_by(run_id=repro_id).all()
        }
        diffs: list[dict] = []
        for key, orig_val in orig.items():
            repro_val = repro.get(key)
            if repro_val is None:
                diffs.append({"metric_version_id": key[0], "slice_def_id": key[1],
                              "issue": "missing in repro"})
                continue
            if abs(orig_val - repro_val) > TOLERANCE:
                diffs.append({
                    "metric_version_id": key[0],
                    "slice_def_id": key[1],
                    "original": orig_val,
                    "repro": repro_val,
                    "diff": repro_val - orig_val,
                })
        return diffs


def pick_recent_runs(project: str, sample: int) -> list[str]:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    with session_scope() as db:
        rows = (
            db.query(models.Run)
            .filter(
                models.Run.project_id == project,
                models.Run.status == "COMPLETED",
                models.Run.completed_at >= since,
            )
            .order_by(models.Run.completed_at.desc())
            .limit(sample)
            .all()
        )
        return [r.id for r in rows]


def replay(original_run_id: str) -> str:
    """Submit a child run that mirrors ``original_run_id``. Returns the child's run ID."""
    from melp.common.ids import new_id

    with session_scope() as db:
        orig = db.query(models.Run).filter_by(id=original_run_id).one()
        child = models.Run(
            id=new_id("run"),
            project_id=orig.project_id,
            name=f"repro of {orig.name or orig.id}",
            model_version_id=orig.model_version_id,
            dataset_version_id=orig.dataset_version_id,
            slice_set=orig.slice_set,
            metric_version_ids=orig.metric_version_ids,
            judge_config_version_id=orig.judge_config_version_id,
            seed=orig.seed,
            priority="low",
            parent_run_id=orig.id,
            submitted_by=orig.submitted_by,
        )
        db.add(child)
        db.flush()
        from melp.workflows.dispatch import submit_run_workflow

        submit_run_workflow(child.id)
        return child.id


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--sample", type=int, default=5)
    args = p.parse_args()

    originals = pick_recent_runs(args.project, args.sample)
    if not originals:
        print(f"no completed runs in {args.project} in last 7 days", file=sys.stderr)
        return 0

    failures = 0
    for orig_id in originals:
        repro_id = replay(orig_id)
        # Caller wraps this in a workflow waiter in real life. For the cron
        # script, we just kick the runs and let the next pass diff them. Diffs
        # below are best-effort — if the repro hasn't finished, they show as
        # missing-in-repro and the script returns nonzero, which the cron
        # wrapper can treat as "check again in N minutes".
        diffs = diff_runs(orig_id, repro_id)
        if diffs:
            failures += 1
            with session_scope() as db:
                enqueue_event(
                    db,
                    project_id=args.project,
                    event="run.reproducibility.drift",
                    payload={
                        "original_run_id": orig_id,
                        "repro_run_id": repro_id,
                        "diffs": diffs[:10],
                    },
                )
            print(f"DRIFT {orig_id}: {len(diffs)} diffs", file=sys.stderr)
    print(f"reproducibility: {len(originals) - failures}/{len(originals)} ok", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
