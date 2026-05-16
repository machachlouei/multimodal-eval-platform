"""Project service standalone entry point (§6.11)."""
from __future__ import annotations

import uvicorn

from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.services.project.routes import router

app = make_app("project", title="MELP Project Service")
app.include_router(router, prefix="/v1/projects", tags=["projects"])


def run() -> None:
    uvicorn.run("melp.services.project.app:app", host="0.0.0.0", port=get_settings().port_project)


if __name__ == "__main__":
    run()
