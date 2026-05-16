from __future__ import annotations

import uvicorn

from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.services.model.routes import router

app = make_app("model", title="MELP Model Catalog Service")
app.include_router(router, prefix="/v1/projects/{project}/models", tags=["models"])


def run() -> None:
    uvicorn.run("melp.services.model.app:app", host="0.0.0.0", port=get_settings().port_model)


if __name__ == "__main__":
    run()
