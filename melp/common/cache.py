"""Redis cache helpers. See §11.4."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import redis

from .config import get_settings


@lru_cache(maxsize=1)
def redis_client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def cache_get(key: str) -> Any | None:
    raw = redis_client().get(key)
    return json.loads(raw) if raw else None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    redis_client().set(key, json.dumps(value), ex=ttl_seconds)


def cache_del(key: str) -> None:
    redis_client().delete(key)
