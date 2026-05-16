"""Project / RBAC routes. Implements §6.11."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from melp.common import models
from melp.common.audit import write_audit
from melp.common.auth import PrincipalDep, require_role
from melp.common.db import get_db
from melp.common.errors import Conflict, NotFound
from melp.common.ids import new_id
from melp.common.schemas import (
    MembershipCreate,
    MembershipRead,
    ProjectCreate,
    ProjectRead,
)

router = APIRouter()


def _ensure_user(db: Session, *, user_id: str, email: str) -> models.User:
    user = db.query(models.User).filter_by(id=user_id).one_or_none()
    if user is None:
        user = models.User(id=user_id, email=email, display_name=email.split("@")[0])
        db.add(user)
        db.flush()
    return user


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(
    body: ProjectCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.Project:
    if db.query(models.Project).filter_by(name=body.name).one_or_none():
        raise Conflict(f"project {body.name!r} already exists")
    user = _ensure_user(db, user_id=principal.user_id, email=principal.email)
    pid = new_id("project")
    p = models.Project(
        id=pid,
        name=body.name,
        description=body.description,
        created_by=user.id,
        quota_storage_gb=body.quota_storage_gb,
        quota_run_concurrency=body.quota_run_concurrency,
        quota_judge_tokens_per_day=body.quota_judge_tokens_per_day,
    )
    db.add(p)
    # Creator is owner.
    db.add(
        models.Membership(
            id=new_id("membership"), project_id=pid, user_id=user.id, role="owner"
        )
    )
    write_audit(
        db,
        actor_id=user.id,
        project_id=pid,
        action="project.create",
        resource_type="project",
        resource_id=pid,
        after=body.model_dump(),
    )
    return p


@router.get("", response_model=list[ProjectRead])
def list_projects(
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.Project]:
    # Platform admins see everything; others see projects they're a member of.
    if "platform-admin" in principal.groups:
        return db.query(models.Project).all()
    return (
        db.query(models.Project)
        .join(models.Membership, models.Membership.project_id == models.Project.id)
        .filter(models.Membership.user_id == principal.user_id)
        .all()
    )


@router.get("/{project}", response_model=ProjectRead)
def get_project(
    project: str,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.Project:
    p = db.query(models.Project).filter_by(id=project).one_or_none()
    if p is None:
        raise NotFound(f"project {project} not found")
    return p


@router.post("/{project}/members", response_model=MembershipRead, status_code=201)
async def add_member(
    project: str,
    body: MembershipCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.Membership:
    await require_role(project, principal, "owner")
    user = db.query(models.User).filter_by(email=body.user_email).one_or_none()
    if user is None:
        user = models.User(id=new_id("user"), email=body.user_email, display_name=body.user_email.split("@")[0])
        db.add(user)
        db.flush()
    if db.query(models.Membership).filter_by(project_id=project, user_id=user.id).one_or_none():
        raise Conflict("user already a member")
    m = models.Membership(
        id=new_id("membership"), project_id=project, user_id=user.id, role=body.role
    )
    db.add(m)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="member.add",
        resource_type="membership",
        resource_id=m.id,
        after={"user_email": body.user_email, "role": body.role},
    )
    return m


@router.get("/{project}/members", response_model=list[MembershipRead])
def list_members(
    project: str,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.Membership]:
    return db.query(models.Membership).filter_by(project_id=project).all()
