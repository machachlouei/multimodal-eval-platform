"""Dataset Service. Implements §6.4 with two-phase publish.

Lifecycle:
  1. POST /v1/projects/{p}/datasets                          → Dataset
  2. POST /v1/projects/{p}/datasets/{d}/versions             → DatasetVersion (DRAFT)
  3. PUT  /v1/projects/{p}/datasets/{d}/versions/{v}/publish → DRAFT → PUBLISHED

A DRAFT version may still be modified (slices added, asset_root pointing to
``s3://.../pending/...``); a PUBLISHED version is immutable. Content hash is
computed from the asset_root URI + version metadata.

Slices are declared at publish time and cannot be added afterward.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from melp.common import models
from melp.common.audit import write_audit
from melp.common.auth import PrincipalDep, require_role
from melp.common.db import get_db
from melp.common.errors import Conflict, NotFound, ValidationFailed
from melp.common.ids import new_id
from melp.common.schemas import (
    DatasetCreate,
    DatasetRead,
    DatasetVersionCreate,
    DatasetVersionRead,
    SliceDefRead,
)

router = APIRouter()


@router.post("", response_model=DatasetRead, status_code=201)
async def create_dataset(
    project: str,
    body: DatasetCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.Dataset:
    await require_role(project, principal, "contributor")
    if db.query(models.Dataset).filter_by(project_id=project, name=body.name).one_or_none():
        raise Conflict(f"dataset {body.name!r} exists")
    d = models.Dataset(
        id=new_id("dataset"),
        project_id=project,
        name=body.name,
        description=body.description,
        classification=body.classification,
    )
    db.add(d)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="dataset.create",
        resource_type="dataset",
        resource_id=d.id,
        after=body.model_dump(),
    )
    return d


@router.get("", response_model=list[DatasetRead])
def list_datasets(
    project: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.Dataset]:
    return db.query(models.Dataset).filter_by(project_id=project).all()


@router.post("/{dataset_id}/versions", response_model=DatasetVersionRead, status_code=201)
async def create_version(
    project: str,
    dataset_id: str,
    body: DatasetVersionCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.DatasetVersion:
    await require_role(project, principal, "contributor")
    d = db.query(models.Dataset).filter_by(id=dataset_id, project_id=project).one_or_none()
    if d is None:
        raise NotFound("dataset not found")
    if db.query(models.DatasetVersion).filter_by(dataset_id=dataset_id, version=body.version).one_or_none():
        raise Conflict(f"version {body.version} exists")
    h = hashlib.sha256(f"{dataset_id}@{body.version}:{body.asset_root_uri}".encode()).hexdigest()
    dv = models.DatasetVersion(
        id=new_id("dataset_version"),
        dataset_id=dataset_id,
        version=body.version,
        content_hash=h,
        schema_uri=body.schema_uri,
        asset_root_uri=body.asset_root_uri,
        record_count=body.record_count,
        classification=body.classification or d.classification,
        status="DRAFT",
    )
    db.add(dv)
    db.flush()
    for s in body.slices:
        db.add(
            models.SliceDef(
                id=new_id("slice_def"),
                dataset_version_id=dv.id,
                name=s.name,
                predicate=s.predicate,
                description=s.description,
            )
        )
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="dataset_version.create",
        resource_type="dataset_version",
        resource_id=dv.id,
        after=body.model_dump(),
    )
    return dv


@router.put("/{dataset_id}/versions/{version_id}/publish", response_model=DatasetVersionRead)
async def publish_version(
    project: str,
    dataset_id: str,
    version_id: str,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.DatasetVersion:
    await require_role(project, principal, "maintainer")
    dv = db.query(models.DatasetVersion).filter_by(id=version_id, dataset_id=dataset_id).one_or_none()
    if dv is None:
        raise NotFound("dataset version not found")
    if dv.status != "DRAFT":
        raise ValidationFailed(f"can only publish from DRAFT, current status: {dv.status}")
    dv.status = "PUBLISHED"
    dv.published_by = principal.user_id
    dv.published_at = datetime.now(UTC)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="dataset_version.publish",
        resource_type="dataset_version",
        resource_id=dv.id,
        after={"status": "PUBLISHED"},
    )
    return dv


@router.get("/{dataset_id}/versions", response_model=list[DatasetVersionRead])
def list_versions(
    project: str,
    dataset_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.DatasetVersion]:
    return db.query(models.DatasetVersion).filter_by(dataset_id=dataset_id).all()


@router.get("/{dataset_id}/versions/{version_id}", response_model=DatasetVersionRead)
def get_version(
    project: str,
    dataset_id: str,
    version_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> models.DatasetVersion:
    dv = db.query(models.DatasetVersion).filter_by(id=version_id, dataset_id=dataset_id).one_or_none()
    if dv is None:
        raise NotFound("dataset version not found")
    return dv


@router.get("/{dataset_id}/versions/{version_id}/slices", response_model=list[SliceDefRead])
def list_slices(
    project: str,
    dataset_id: str,
    version_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.SliceDef]:
    return db.query(models.SliceDef).filter_by(dataset_version_id=version_id).all()
