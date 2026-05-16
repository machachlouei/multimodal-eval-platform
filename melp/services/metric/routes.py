"""Metric Registry Service. Implements §6.5.

Catalogs metric versions. Discovery is open to everyone in the platform;
registration is gated by ``platform-admin`` because each new package is code
that runs on workers (§9.6 supply-chain row). Built-ins are seeded at startup.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from melp.common import models
from melp.common.audit import write_audit
from melp.common.auth import PrincipalDep
from melp.common.db import get_db
from melp.common.errors import Conflict, Forbidden, NotFound, ValidationFailed
from melp.common.ids import new_id
from melp.common.schemas import (
    MetricCreate,
    MetricVersionCreate,
    MetricVersionRead,
)
from melp.metrics.base import load_metric

router = APIRouter()


@router.post("", status_code=201)
def create_metric(
    body: MetricCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    if "platform-admin" not in principal.groups:
        raise Forbidden("metric registration is platform-admin only")
    if db.query(models.Metric).filter_by(name=body.name).one_or_none():
        raise Conflict(f"metric {body.name!r} exists")
    mid = new_id("metric")
    db.add(models.Metric(id=mid, name=body.name, description=body.description))
    write_audit(
        db,
        actor_id=principal.user_id,
        action="metric.create",
        resource_type="metric",
        resource_id=mid,
        after=body.model_dump(),
    )
    return {"id": mid, "name": body.name}


@router.get("")
def list_metrics(
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    q = db.query(models.Metric)
    if name:
        q = q.filter_by(name=name)
    return [{"id": r.id, "name": r.name, "description": r.description} for r in q.all()]


@router.post("/{metric_id}/versions", response_model=MetricVersionRead, status_code=201)
def create_version(
    metric_id: str,
    body: MetricVersionCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.MetricVersion:
    if "platform-admin" not in principal.groups:
        raise Forbidden("metric registration is platform-admin only")
    if db.query(models.Metric).filter_by(id=metric_id).one_or_none() is None:
        raise NotFound("metric not found")
    if db.query(models.MetricVersion).filter_by(metric_id=metric_id, version=body.version).one_or_none():
        raise Conflict(f"version {body.version} exists")
    # Validate that the package_uri actually resolves (§6.5 sandboxed loader).
    try:
        load_metric(body.package_uri)
    except Exception as e:
        raise ValidationFailed(f"package_uri invalid: {e}") from e
    mv = models.MetricVersion(
        id=new_id("metric_version"),
        metric_id=metric_id,
        version=body.version,
        package_uri=body.package_uri,
        signature=body.signature,
        tests_passed_at=datetime.now(UTC),
    )
    db.add(mv)
    write_audit(
        db,
        actor_id=principal.user_id,
        action="metric_version.create",
        resource_type="metric_version",
        resource_id=mv.id,
        after=body.model_dump(),
    )
    return mv


@router.get("/{metric_id}/versions", response_model=list[MetricVersionRead])
def list_versions(
    metric_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.MetricVersion]:
    return db.query(models.MetricVersion).filter_by(metric_id=metric_id).all()


@router.get("/versions/{metric_version_id}", response_model=MetricVersionRead)
def get_version(
    metric_version_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> models.MetricVersion:
    mv = db.query(models.MetricVersion).filter_by(id=metric_version_id).one_or_none()
    if mv is None:
        raise NotFound("metric version not found")
    return mv
