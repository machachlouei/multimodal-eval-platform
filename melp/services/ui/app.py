"""Minimal HTMX UI. Phase 1: list runs, run detail. Phase 2: comparison + leaderboard.

This is intentionally tiny — three pages, no React. The doc identifies the UI
as a Phase 1 deliverable but states "no dedicated frontend headcount in Y1"
(see ``Design-Doc.pdf`` and the implementation plan). HTMX is enough to get
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


def run() -> None:
    uvicorn.run("melp.services.ui.app:app", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    run()
