"""Model Catalog Service routes. Implements §6 (Model Catalog Service entry).

Pass-through to the upstream Model Registry in prod (FR-2). In this repo we
cache known model versions locally so dev can register & evaluate
``backend=echo`` models without a real registry.
"""
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
from melp.common.schemas import ModelCreate, ModelVersionCreate, ModelVersionRead

router = APIRouter()


@router.post("", status_code=201)
async def create_model(
    project: str,
    body: ModelCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    await require_role(project, principal, "contributor")
    if db.query(models.Model).filter_by(project_id=project, name=body.name).one_or_none():
        raise Conflict(f"model {body.name!r} already exists in project")
    mid = new_id("model")
    db.add(models.Model(id=mid, project_id=project, name=body.name, description=body.description))
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="model.create",
        resource_type="model",
        resource_id=mid,
        after=body.model_dump(),
    )
    return {"id": mid, "name": body.name}


@router.get("")
def list_models(
    project: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, str]]:
    rows = db.query(models.Model).filter_by(project_id=project).all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rows]


@router.post("/{model_id}/versions", response_model=ModelVersionRead, status_code=201)
async def create_version(
    project: str,
    model_id: str,
    body: ModelVersionCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.ModelVersion:
    await require_role(project, principal, "contributor")
    if db.query(models.Model).filter_by(id=model_id, project_id=project).one_or_none() is None:
        raise NotFound("model not found")
    if db.query(models.ModelVersion).filter_by(model_id=model_id, version=body.version).one_or_none():
        raise Conflict(f"version {body.version} already exists")
    mv = models.ModelVersion(
        id=new_id("model_version"),
        model_id=model_id,
        version=body.version,
        uri=body.uri,
        backend=body.backend,
        config=body.config,
    )
    db.add(mv)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="model_version.create",
        resource_type="model_version",
        resource_id=mv.id,
        after=body.model_dump(),
    )
    return mv


@router.get("/{model_id}/versions", response_model=list[ModelVersionRead])
def list_versions(
    project: str,
    model_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.ModelVersion]:
    return db.query(models.ModelVersion).filter_by(model_id=model_id).all()


@router.get("/versions/{model_version_id}", response_model=ModelVersionRead)
def get_version(
    project: str,
    model_version_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> models.ModelVersion:
    mv = db.query(models.ModelVersion).filter_by(id=model_version_id).one_or_none()
    if mv is None:
        raise NotFound("model version not found")
    return mv
