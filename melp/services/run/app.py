from __future__ import annotations

import uvicorn

from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.services.run.routes import router

app = make_app("run", title="MELP Run Service")
app.include_router(router, prefix="/v1/projects/{project}/runs", tags=["runs"])


def run() -> None:
    uvicorn.run("melp.services.run.app:app", host="0.0.0.0", port=get_settings().port_run)


if __name__ == "__main__":
    run()
