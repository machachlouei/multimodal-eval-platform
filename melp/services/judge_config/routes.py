"""Judge Config Service. Implements §6.6 (config-CRUD half).

Handles CRUD for ``Prompt`` / ``PromptVersion`` / ``JudgeConfig`` / ``JudgeConfigVersion``.
The Judge Orchestrator (separate service) consumes these at run time.
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
from melp.common.schemas import (
    JudgeConfigCreate,
    JudgeConfigVersionCreate,
    JudgeConfigVersionRead,
    PromptVersionCreate,
    PromptVersionRead,
)

router = APIRouter()


# ---------- Prompts ----------
@router.post("/_prompts/{name}/versions", response_model=PromptVersionRead, status_code=201)
async def create_prompt_version(
    project: str,
    name: str,
    body: PromptVersionCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.PromptVersion:
    await require_role(project, principal, "maintainer")
    p = db.query(models.Prompt).filter_by(project_id=project, name=name).one_or_none()
    if p is None:
        p = models.Prompt(id=new_id("prompt"), project_id=project, name=name)
        db.add(p)
        db.flush()
    if db.query(models.PromptVersion).filter_by(prompt_id=p.id, version=body.version).one_or_none():
        raise Conflict(f"prompt version {body.version} exists")
    pv = models.PromptVersion(
        id=new_id("prompt_version"),
        prompt_id=p.id,
        version=body.version,
        template=body.template,
        output_schema=body.output_schema,
    )
    db.add(pv)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="prompt_version.create",
        resource_type="prompt_version",
        resource_id=pv.id,
        after=body.model_dump(),
    )
    return pv


@router.get("/_prompts", response_model=list[dict])
def list_prompts(
    project: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    return [
        {"id": p.id, "name": p.name}
        for p in db.query(models.Prompt).filter_by(project_id=project).all()
    ]


@router.get("/_prompts/{name}/versions", response_model=list[PromptVersionRead])
def list_prompt_versions(
    project: str,
    name: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.PromptVersion]:
    p = db.query(models.Prompt).filter_by(project_id=project, name=name).one_or_none()
    if p is None:
        raise NotFound("prompt not found")
    return db.query(models.PromptVersion).filter_by(prompt_id=p.id).all()


# ---------- Judge configs ----------
@router.post("", status_code=201)
async def create_judge_config(
    project: str,
    body: JudgeConfigCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    await require_role(project, principal, "maintainer")
    if db.query(models.JudgeConfig).filter_by(project_id=project, name=body.name).one_or_none():
        raise Conflict("judge config exists")
    jc = models.JudgeConfig(
        id=new_id("judge_config"), project_id=project, name=body.name, description=body.description
    )
    db.add(jc)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="judge_config.create",
        resource_type="judge_config",
        resource_id=jc.id,
        after=body.model_dump(),
    )
    return {"id": jc.id, "name": body.name}


@router.post("/{judge_config_id}/versions", response_model=JudgeConfigVersionRead, status_code=201)
async def create_judge_config_version(
    project: str,
    judge_config_id: str,
    body: JudgeConfigVersionCreate,
    principal: PrincipalDep,
    db: Annotated[Session, Depends(get_db)],
) -> models.JudgeConfigVersion:
    await require_role(project, principal, "maintainer")
    if db.query(models.JudgeConfig).filter_by(id=judge_config_id, project_id=project).one_or_none() is None:
        raise NotFound("judge config not found")
    if db.query(models.PromptVersion).filter_by(id=body.prompt_version_id).one_or_none() is None:
        raise NotFound("prompt version not found")
    if db.query(models.JudgeConfigVersion).filter_by(
        judge_config_id=judge_config_id, version=body.version
    ).one_or_none():
        raise Conflict("judge config version exists")
    jcv = models.JudgeConfigVersion(
        id=new_id("judge_config_version"),
        judge_config_id=judge_config_id,
        version=body.version,
        judge_model=body.judge_model,
        prompt_version_id=body.prompt_version_id,
        rubric=body.rubric,
        ensembling=body.ensembling,
        calibration_set_uri=body.calibration_set_uri,
    )
    db.add(jcv)
    write_audit(
        db,
        actor_id=principal.user_id,
        project_id=project,
        action="judge_config_version.create",
        resource_type="judge_config_version",
        resource_id=jcv.id,
        after=body.model_dump(),
    )
    return jcv


@router.get("", response_model=list[dict])
def list_judge_configs(
    project: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    return [
        {"id": j.id, "name": j.name, "description": j.description}
        for j in db.query(models.JudgeConfig).filter_by(project_id=project).all()
    ]


@router.get("/{judge_config_id}/versions", response_model=list[JudgeConfigVersionRead])
def list_judge_config_versions(
    project: str,
    judge_config_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[models.JudgeConfigVersion]:
    return db.query(models.JudgeConfigVersion).filter_by(judge_config_id=judge_config_id).all()
