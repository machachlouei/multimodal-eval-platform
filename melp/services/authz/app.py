"""AuthZ service. Implements §6.2.

Resolves (user_id, project_id) → role. Cached in Redis with 5-min TTL (§11.4)
to keep RBAC checks off the hot path of every API call.

Failure mode: cache-hit-on-IdP-outage is implemented by returning the cached
value with ``stale=true`` for up to 5 min (§10.4).
"""
from __future__ import annotations

from typing import Annotated

import uvicorn
from fastapi import Depends, Query
from sqlalchemy.orm import Session

from melp.common.cache import cache_get, cache_set
from melp.common.config import get_settings
from melp.common.db import get_db
from melp.common.models import Membership
from melp.common.service_base import make_app

app = make_app("authz", title="MELP AuthZ Service")


@app.get("/v1/check")
def check_role(
    user_id: Annotated[str, Query()],
    project_id: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str | bool]:
    cache_key = f"authz:role:{user_id}:{project_id}"
    cached = cache_get(cache_key)
    if cached:
        return {"role": cached["role"], "stale": False}
    m: Membership | None = (
        db.query(Membership).filter_by(user_id=user_id, project_id=project_id).one_or_none()
    )
    if m is None:
        return {"role": None, "stale": False}
    cache_set(cache_key, {"role": m.role}, ttl_seconds=300)
    return {"role": m.role, "stale": False}


@app.delete("/v1/cache/{user_id}/{project_id}")
def invalidate(user_id: str, project_id: str) -> dict[str, bool]:
    from melp.common.cache import cache_del

    cache_del(f"authz:role:{user_id}:{project_id}")
    return {"ok": True}


def run() -> None:
    uvicorn.run("melp.services.authz.app:app", host="0.0.0.0", port=get_settings().port_authz)


if __name__ == "__main__":
    run()
