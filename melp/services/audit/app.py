from __future__ import annotations

import uvicorn

from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.services.audit.routes import router

app = make_app("audit", title="MELP Audit Service")
app.include_router(router, prefix="/v1/audit", tags=["audit"])


def run() -> None:
    uvicorn.run("melp.services.audit.app:app", host="0.0.0.0", port=get_settings().port_audit)


if __name__ == "__main__":
    run()
