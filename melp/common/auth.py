"""Authentication primitives. See §9.1.

Two modes:
  - dev: every request authenticated as ``MELP_AUTH_DEV_USER``.
  - oidc: validate bearer JWTs against the configured issuer (stubbed; in prod
    this would verify against the corporate IdP's JWKS).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, Header
from jose import JWTError, jwt

from .config import get_settings
from .errors import Forbidden, Unauthenticated


@dataclass
class Principal:
    """The authenticated caller."""
    user_id: str
    email: str
    groups: list[str]
    is_service: bool = False


async def authenticate(
    authorization: Annotated[str | None, Header()] = None,
    x_request_id: Annotated[str | None, Header()] = None,
) -> Principal:
    s = get_settings()
    if s.auth_mode == "dev":
        return Principal(user_id="usr_dev", email=s.auth_dev_user, groups=["platform-admin"])

    if not authorization or not authorization.startswith("Bearer "):
        raise Unauthenticated("missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        # In real life: fetch JWKS from issuer and validate with the kid'd key.
        claims = jwt.decode(token, s.auth_jwt_secret, algorithms=["HS256"], options={"verify_aud": False})
    except JWTError as e:
        raise Unauthenticated(f"invalid token: {e}") from e
    return Principal(
        user_id=claims.get("sub", ""),
        email=claims.get("email", ""),
        groups=claims.get("groups", []),
        is_service=claims.get("svc", False),
    )


PrincipalDep = Annotated[Principal, Depends(authenticate)]


# ---------- Authorization ----------
# Project-scoped RBAC roles (§9.2). Higher roles include lower.
ROLES = ["viewer", "contributor", "maintainer", "owner"]


def role_at_least(actual: str, required: str) -> bool:
    return ROLES.index(actual) >= ROLES.index(required)


async def require_role(project_id: str, principal: Principal, required: str) -> None:
    """Resolves the principal's role within ``project_id`` and enforces ``required``.

    Calls AuthZ service. Platform admins bypass.
    """
    if "platform-admin" in principal.groups:
        return
    s = get_settings()
    async with httpx.AsyncClient(timeout=5) as c:
        resp = await c.get(
            f"{s.url_authz}/v1/check",
            params={"user_id": principal.user_id, "project_id": project_id},
        )
    if resp.status_code != 200:
        raise Forbidden("authz check failed")
    role = resp.json().get("role")
    if role is None or not role_at_least(role, required):
        raise Forbidden(f"requires role {required}; have {role!r}")
