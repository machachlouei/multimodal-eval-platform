from __future__ import annotations

import uvicorn

from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.services.judge_config.routes import router

app = make_app("judge_config", title="MELP Judge Config Service")
app.include_router(router, prefix="/v1/projects/{project}/judge-configs", tags=["judges"])


def run() -> None:
    uvicorn.run("melp.services.judge_config.app:app", host="0.0.0.0", port=get_settings().port_judge_config)


if __name__ == "__main__":
    run()
