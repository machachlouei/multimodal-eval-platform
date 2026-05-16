"""Run Service. Implements §6.3 + §8.3.

Run states (§17.7):
  QUEUED → RUNNING → AGGREGATING → COMPLETED
                                  → PARTIAL → COMPLETED | FAILED
            → FAILED
            → CANCELLED
  RUNNING → CANCELLED | FAILED

Submission is idempotent via ``Idempotency-Key`` header (§8.4); the same key
within a project returns the original run.

If the workflow engine is unreachable, runs land in PENDING_SUBMISSION; a
reconciler (``melp.workers.run_reconciler``) re-submits them when the workflow
engine recovers (§6.3 failure behavior).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from melp.common import models
from melp.common.audit import write_audit
from melp.common.auth import PrincipalDep, require_role
from melp.common.db import get_db
from melp.common.errors import Conflict, NotFound, ValidationFailed
from melp.common.ids import new_id
from melp.common.schemas import (
    RunCreate,
    RunRead,
    RunResultRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionRead,
)
from melp.common.webhooks import enqueue_event

router = APIRouter()


def _validate_refs(db: Session, body: RunCreate) -> None:
    if not db.query(models.ModelVersion).filter_by(id=body.model_version_id).one_or_none():
        raise ValidationFailed("model_version_id not found")
    dv = db.query(models.DatasetVersion).filter_by(id=body.dataset_version_id).one_or_none()
    if dv is None:
        raise ValidationFailed("dataset_version_id not found")
    if dv.status != "PUBLISHED":
        raise ValidationFailed("dataset version must be PUBLISHED")
    if not body.metric_version_ids:
        raise ValidationFailed("at least one metric_version_id is required")
    for mvid in body.metric_version_ids:
        if not db.query(models.MetricVersion).filter_by(id=mvid).one_or_none():
            raise ValidationFailed(f"metric_version_id {mvid} not found")
    if body.judge_config_version_id and not db.query(models.JudgeConfigVersion).filter_by(
        id=body.judge_config_version_id
    ).one_or_none():
        raise ValidationFailed("judge_config_version_id not found")
    if body.baseline_run_id and not db.query(models.Run).filter_by(id=body.baseline_run_id).one_or_none():
        raise ValidationFailed("baseline_run_id not found")


def _serialize_run(r: models.Run, results: list[models.RunResult] | None = None) -> RunRead:
    return RunRead(
        id=r.id,
        project_id=r.project_id,
        name=r.name,
        model_version_id=r.model_version_id,
        dataset_version_id=r.dataset_version_id,
        metric_version_ids=r.metric_version_ids,
        judge_config_version_id=r.judge_config_version_id,
        seed=r.seed,
        priority=r.priority,
        baseline_run_id=r.baseline_run_id,
        status=r.status,
        progress=r.progress,
        error=r.error,
        submitted_at=r.submitted_at,
        started_at=r.started_at,
        completed_at=r.completed_at,
        results=[RunResultRead.model_validate(x) for x in (results or [])],
    )


@router.post("", response_model=RunRead, status_code=201)
async def create_run(
    project: str,
    body: RunCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> RunRead:
    await require_role(project, principal, "contributor")

    # Idempotency check — same key in same project returns the original.
    if idempotency_key:
        existing = (
            db.query(models.Run).filter_by(project_id=project, request_id=idempotency_key).one_or_none()
        )
        if existing:
            return _serialize_run(existing)

    _validate_refs(db, body)

    # Concurrency quota.
    project_row = db.query(models.Project).filter_by(id=project).one_or_none()
    if project_row is None:
        raise NotFound("project not found")
    running = (
        db.query(models.Run)
        .filter(models.Run.project_id == project, models.Run.status.in_(["QUEUED", "RUNNING", "AGGREGATING"]))
        .count()
    )
    if running >= project_row.quota_run_concurrency:
        raise Conflict(
            f"project run concurrency quota ({project_row.quota_run_concurrency}) reached"
        )

    r = models.Run(
        id=new_id("run"),
        project_id=project,
        name=body.name,
        model_version_id=body.model_version_id,
        dataset_version_id=body.dataset_version_id,
        slice_set=body.slice_set,
        metric_version_ids=body.metric_version_ids,
        judge_config_version_id=body.judge_config_version_id,
        seed=body.seed,
        priority=body.priority,
        baseline_run_id=body.baseline_run_id,
        request_id=idempotency_key,
        status="QUEUED",
        progress={"examples_total": 0, "examples_done": 0},
        submitted_by=principal.user_id,
    )
    db.add(r)
    db.flush()

    # Hand to workflow engine. If Temporal is down, we leave the row at QUEUED
    # and let the reconciler push it; for dev we also support an in-process
    # worker that polls QUEUED rows directly (see melp.workers.runner).
    from melp.workflows.dispatch import submit_run_workflow

    try:
        submit_run_workflow(r.id)
    except Exception as e:  # noqa: BLE001 -- best-effort; reconciler retries
        r.status = "PENDING_SUBMISSION"
        r.error = f"workflow dispatch failed: {e}"

    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="run.create",
        resource_type="run",
        resource_id=r.id,
        after=body.model_dump(),
    )
    enqueue_event(db, project_id=project, event="run.queued", payload={"run_id": r.id})
    return _serialize_run(r)


@router.get("/{run_id}", response_model=RunRead)
def get_run(
    project: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> RunRead:
    r = db.query(models.Run).filter_by(id=run_id, project_id=project).one_or_none()
    if r is None:
        raise NotFound("run not found")
    results = db.query(models.RunResult).filter_by(run_id=run_id).all()
    return _serialize_run(r, results)


@router.get("", response_model=list[RunRead])
def list_runs(
    project: str,
    db: Annotated[Session, Depends(get_db)],
    status: Annotated[str | None, Query()] = None,
    model_version_id: Annotated[str | None, Query()] = None,
    dataset_version_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=200)] = 50,
) -> list[RunRead]:
    q = db.query(models.Run).filter_by(project_id=project)
    if status:
        q = q.filter_by(status=status)
    if model_version_id:
        q = q.filter_by(model_version_id=model_version_id)
    if dataset_version_id:
        q = q.filter_by(dataset_version_id=dataset_version_id)
    rows = q.order_by(models.Run.submitted_at.desc()).limit(limit).all()
    return [_serialize_run(r) for r in rows]


@router.post("/{run_id}/cancel", response_model=RunRead)
async def cancel_run(
    project: str,
    run_id: str,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> RunRead:
    await require_role(project, principal, "contributor")
    r = db.query(models.Run).filter_by(id=run_id, project_id=project).one_or_none()
    if r is None:
        raise NotFound("run not found")
    if r.status in ("COMPLETED", "FAILED", "CANCELLED"):
        raise Conflict(f"cannot cancel run in {r.status} state")
    r.status = "CANCELLED"
    r.completed_at = datetime.now(UTC)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="run.cancel",
        resource_type="run",
        resource_id=run_id,
        after={"status": "CANCELLED"},
    )
    enqueue_event(db, project_id=project, event="run.cancelled", payload={"run_id": run_id})
    return _serialize_run(r)


@router.get("/{run_id}/results", response_model=list[RunResultRead])
def get_results(
    project: str,
    run_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.RunResult]:
    if not db.query(models.Run).filter_by(id=run_id, project_id=project).one_or_none():
        raise NotFound("run not found")
    return db.query(models.RunResult).filter_by(run_id=run_id).all()


@router.get("/leaderboard/{metric_version_id}")
def leaderboard(
    project: str,
    metric_version_id: str,
    db: Annotated[Session, Depends(get_db)],
    dataset_version_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=100)] = 20,
) -> list[dict[str, Any]]:
    """Top-N runs by metric, scoped to project (Phase 2 — §13.4)."""
    q = (
        db.query(models.Run, models.RunResult)
        .join(models.RunResult, models.RunResult.run_id == models.Run.id)
        .filter(models.Run.project_id == project, models.RunResult.metric_version_id == metric_version_id)
    )
    if dataset_version_id:
        q = q.filter(models.Run.dataset_version_id == dataset_version_id)
    q = q.filter(models.RunResult.slice_def_id.is_(None))
    rows = q.order_by(models.RunResult.point_estimate.desc()).limit(limit).all()
    return [
        {
            "run_id": r.id,
            "model_version_id": r.model_version_id,
            "dataset_version_id": r.dataset_version_id,
            "point_estimate": rr.point_estimate,
            "ci_low": rr.ci_low,
            "ci_high": rr.ci_high,
            "submitted_at": r.submitted_at.isoformat(),
        }
        for r, rr in rows
    ]


# ---------- Webhooks (Phase 2 — §8.5) ----------
@router.post("/_webhooks", response_model=WebhookSubscriptionRead, status_code=201)
async def create_webhook(
    project: str,
    body: WebhookSubscriptionCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.WebhookSubscription:
    await require_role(project, principal, "maintainer")
    import secrets

    s = models.WebhookSubscription(
        id=new_id("webhook"),
        project_id=project,
        url=body.url,
        secret=secrets.token_hex(32),
        events=body.events,
        active=True,
    )
    db.add(s)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="webhook.create",
        resource_type="webhook_subscription",
        resource_id=s.id,
        after={"url": body.url, "events": body.events},
    )
    return s


@router.get("/_webhooks", response_model=list[WebhookSubscriptionRead])
def list_webhooks(
    project: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.WebhookSubscription]:
    return db.query(models.WebhookSubscription).filter_by(project_id=project).all()
