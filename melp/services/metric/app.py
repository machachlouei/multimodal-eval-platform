from __future__ import annotations

import uvicorn

from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.services.metric.routes import router

app = make_app("metric", title="MELP Metric Registry")
app.include_router(router, prefix="/v1/metrics", tags=["metrics"])


def run() -> None:
    uvicorn.run("melp.services.metric.app:app", host="0.0.0.0", port=get_settings().port_metric)


if __name__ == "__main__":
    run()
