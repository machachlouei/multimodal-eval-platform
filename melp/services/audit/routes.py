"""Audit log query routes. Implements §6.12.

Writes happen via ``melp.common.audit.write_audit`` from inside other services;
this surface is read-only.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from melp.common import models
from melp.common.auth import PrincipalDep
from melp.common.db import get_db
from melp.common.errors import Forbidden

router = APIRouter()


@router.get("")
def search(
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
    project_id: Annotated[str | None, Query()] = None,
    resource_type: Annotated[str | None, Query()] = None,
    actor_id: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(le=500)] = 100,
) -> list[dict[str, Any]]:
    if "platform-admin" not in principal.groups and project_id is None:
        raise Forbidden("project_id is required for non-admin queries")
    q = db.query(models.AuditLog)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if resource_type:
        q = q.filter_by(resource_type=resource_type)
    if actor_id:
        q = q.filter_by(actor_id=actor_id)
    if since:
        q = q.filter(models.AuditLog.created_at >= since)
    rows = q.order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "actor_id": r.actor_id,
            "project_id": r.project_id,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "before": r.before,
            "after": r.after,
            "request_id": r.request_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
