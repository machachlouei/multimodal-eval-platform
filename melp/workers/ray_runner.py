"""Ray-based eval-shard execution. Phase 3.

Splits the dataset into N shards and runs inference on each in parallel via
``@ray.remote``. Falls back to sequential execution when Ray is unavailable.

Activated by ``MELP_USE_RAY=1`` and a reachable Ray cluster
(``MELP_RAY_ADDRESS``). Sharding granularity is governed by ``shard_size``
(default 250 examples per shard) — chosen empirically to balance Ray task
overhead (≈50 ms / task) against per-shard worker memory.

Implements Design-Doc §6.8 + addresses the §11.3 multimodal bottleneck row
(per-example sharding within metric).
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Iterable

from melp.common.telemetry import get_logger

log = get_logger(__name__)

DEFAULT_SHARD_SIZE = 250


def _chunk(items: list[Any], size: int) -> Iterable[list[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _try_ray():
    if os.environ.get("MELP_USE_RAY", "0") != "1":
        return None
    try:
        import ray  # type: ignore[import-not-found]
    except ImportError:
        log.info("ray.not_installed")
        return None
    if not ray.is_initialized():
        addr = os.environ.get("MELP_RAY_ADDRESS", "auto")
        try:
            ray.init(address=addr, ignore_reinit_error=True, logging_level="WARNING")
        except Exception as e:  # noqa: BLE001
            log.warning("ray.init_failed", error=str(e))
            return None
    return ray


def shard_inference(
    examples: list[dict[str, Any]],
    fn: Callable[[Any], Any],
    *,
    shard_size: int = DEFAULT_SHARD_SIZE,
) -> list[str]:
    """Run ``fn`` over every example, returning prediction JSONL lines.

    Uses Ray when ``MELP_USE_RAY=1``, else falls back to in-process serial
    execution.
    """
    ray = _try_ray()
    if ray is None:
        return [_predict_one(fn, ex) for ex in examples]

    fn_ref = ray.put(fn)

    @ray.remote
    def shard_task(fn_ref, batch):  # noqa: ANN001
        local_fn = ray.get(fn_ref)
        return [_predict_one(local_fn, ex) for ex in batch]

    futures = [shard_task.remote(fn_ref, batch) for batch in _chunk(examples, shard_size)]
    lines: list[str] = []
    for chunk_result in ray.get(futures):
        lines.extend(chunk_result)
    return lines


def _predict_one(fn: Callable[[Any], Any], ex: dict[str, Any]) -> str:
    pred = fn(ex.get("input"))
    return json.dumps(
        {
            "id": ex.get("id"),
            "prediction": pred,
            "reference": ex.get("reference"),
            **{k: v for k, v in ex.items() if k not in ("input", "reference")},
        }
    )
