"""Judge response cache. See §6.6 / §11.4.

Cache key includes ``judge_model``, ``prompt_version``, ``rubric_version``, and
``sha256(input)``. We never invalidate in place — any version bump produces a
new key. This guarantees reproducibility against a frozen cache.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from melp.common.cache import redis_client


def make_key(
    *,
    judge_model: str,
    prompt_version_id: str,
    rubric_hash: str,
    example: dict[str, Any],
) -> str:
    payload = json.dumps(example, sort_keys=True, default=str).encode()
    h = hashlib.sha256(payload).hexdigest()
    return f"judge:{judge_model}:{prompt_version_id}:{rubric_hash}:{h}"


def get(key: str) -> dict | None:
    raw = redis_client().get(key)
    return json.loads(raw) if raw else None


def put(key: str, value: dict, ttl_seconds: int = 30 * 24 * 3600) -> None:
    redis_client().set(key, json.dumps(value), ex=ttl_seconds)


def rubric_hash(rubric: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(rubric, sort_keys=True).encode()).hexdigest()[:16]
