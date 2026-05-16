"""Audit logging helpers. See §9.5 — every mutating action records before/after."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import models
from .ids import new_id
from .telemetry import current_request_id


def write_audit(
    db: Session,
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    project_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> models.AuditLog:
    row = models.AuditLog(
        id=new_id("audit"),
        actor_id=actor_id,
        project_id=project_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before,
        after=after,
        request_id=current_request_id(),
    )
    db.add(row)
    return row
