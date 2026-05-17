"""Minimal HTMX UI. Phase 1: list runs, run detail. Phase 2: comparison + leaderboard.

This is intentionally tiny — three pages, no React. The doc identifies the UI
as a Phase 1 deliverable but states "no dedicated frontend headcount in Y1"
(see ``Design-Doc.md`` and the implementation plan). HTMX is enough to get
ML engineers off curl and into a browser without a real frontend team.
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.requests import Request

from melp.common import models
from melp.common.db import get_db
from melp.common.service_base import make_app

BASE_DIR = Path(__file__).parent
TPL_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = make_app("ui", title="MELP UI")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TPL_DIR))


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Annotated[Session, Depends(get_db)]):
    projects = db.query(models.Project).order_by(models.Project.created_at.desc()).all()
    return templates.TemplateResponse("home.html", {"request": request, "projects": projects})


@app.get("/p/{project_id}", response_class=HTMLResponse)
def project_page(project_id: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    p = db.query(models.Project).filter_by(id=project_id).one_or_none()
    if not p:
        return HTMLResponse("project not found", status_code=404)
    runs = (
        db.query(models.Run)
        .filter_by(project_id=project_id)
        .order_by(models.Run.submitted_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "project.html", {"request": request, "project": p, "runs": runs}
    )


@app.get("/r/{run_id}", response_class=HTMLResponse)
def run_page(run_id: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    r = db.query(models.Run).filter_by(id=run_id).one_or_none()
    if not r:
        return HTMLResponse("run not found", status_code=404)
    rrs = db.query(models.RunResult).filter_by(run_id=run_id).all()
    # Pull metric names for display.
    mv_ids = list({rr.metric_version_id for rr in rrs})
    mv_map = {
        mv.id: mv
        for mv in db.query(models.MetricVersion).filter(models.MetricVersion.id.in_(mv_ids)).all()
    } if mv_ids else {}
    slice_map = {
        s.id: s
        for s in db.query(models.SliceDef).filter_by(dataset_version_id=r.dataset_version_id).all()
    }
    return templates.TemplateResponse(
        "run.html",
        {"request": request, "run": r, "results": rrs, "mv_map": mv_map, "slice_map": slice_map},
    )


# ---------- Phase 3 carry-overs ----------
@app.get("/p/{project_id}/leaderboard/{metric_version_id}", response_class=HTMLResponse)
def leaderboard_page(
    project_id: str, metric_version_id: str, request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    rows = (
        db.query(models.Run, models.RunResult)
        .join(models.RunResult, models.RunResult.run_id == models.Run.id)
        .filter(
            models.Run.project_id == project_id,
            models.RunResult.metric_version_id == metric_version_id,
            models.RunResult.slice_def_id.is_(None),
        )
        .order_by(models.RunResult.point_estimate.desc())
        .limit(50)
        .all()
    )
    mv = db.query(models.MetricVersion).filter_by(id=metric_version_id).one_or_none()
    return templates.TemplateResponse(
        "leaderboard.html",
        {"request": request, "project_id": project_id, "metric_version": mv, "rows": rows},
    )


@app.get("/compare/{run_a}/{run_b}", response_class=HTMLResponse)
def compare_runs(
    run_a: str, run_b: str, request: Request, db: Annotated[Session, Depends(get_db)],
):
    rA = db.query(models.Run).filter_by(id=run_a).one_or_none()
    rB = db.query(models.Run).filter_by(id=run_b).one_or_none()
    if not rA or not rB:
        return HTMLResponse("run not found", status_code=404)
    rrA = {(rr.metric_version_id, rr.slice_def_id): rr for rr in db.query(models.RunResult).filter_by(run_id=run_a).all()}
    rrB = {(rr.metric_version_id, rr.slice_def_id): rr for rr in db.query(models.RunResult).filter_by(run_id=run_b).all()}
    keys = sorted(set(rrA.keys()) | set(rrB.keys()), key=lambda k: (k[0] or "", k[1] or ""))
    mv_map = {
        mv.id: mv for mv in db.query(models.MetricVersion).filter(
            models.MetricVersion.id.in_({k[0] for k in keys})
        ).all()
    }
    slice_map = {
        s.id: s for s in db.query(models.SliceDef).filter(
            models.SliceDef.id.in_({k[1] for k in keys if k[1]})
        ).all()
    } if any(k[1] for k in keys) else {}
    return templates.TemplateResponse(
        "compare.html",
        {"request": request, "a": rA, "b": rB, "keys": keys, "rrA": rrA, "rrB": rrB,
         "mv_map": mv_map, "slice_map": slice_map},
    )


@app.get("/audit", response_class=HTMLResponse)
def audit_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    project_id: str | None = None,
    resource_type: str | None = None,
    actor_id: str | None = None,
    limit: int = 100,
):
    q = db.query(models.AuditLog)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if resource_type:
        q = q.filter_by(resource_type=resource_type)
    if actor_id:
        q = q.filter_by(actor_id=actor_id)
    rows = q.order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    return templates.TemplateResponse(
        "audit.html",
        {"request": request, "rows": rows, "filters": {
            "project_id": project_id, "resource_type": resource_type, "actor_id": actor_id,
        }},
    )


@app.get("/p/{project_id}/slices/{dataset_version_id}", response_class=HTMLResponse)
def slice_browser(
    project_id: str, dataset_version_id: str, request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    slices = db.query(models.SliceDef).filter_by(dataset_version_id=dataset_version_id).all()
    rows = []
    for sd in slices:
        worst = (
            db.query(models.Run, models.RunResult)
            .join(models.RunResult, models.RunResult.run_id == models.Run.id)
            .filter(
                models.Run.project_id == project_id,
                models.RunResult.slice_def_id == sd.id,
            )
            .order_by(models.RunResult.point_estimate.asc())
            .limit(5)
            .all()
        )
        rows.append((sd, worst))
    return templates.TemplateResponse(
        "slices.html", {"request": request, "rows": rows, "project_id": project_id},
    )


def run() -> None:
    uvicorn.run("melp.services.ui.app:app", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    run()
