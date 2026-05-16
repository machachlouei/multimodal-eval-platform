"""Metric interface contract.

A metric is a callable ``fn(predictions, references, **kwargs) -> MetricResult``
or, for per-example metrics, ``fn(pred, ref) -> float``. Aggregation (point
estimate, CI, significance) is delegated to ``melp.stats``.
"""
from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricSpec:
    name: str
    version: str
    package_uri: str
    description: str = ""
    # Signature constraints (§6.5): typed predict/reference shapes.
    predict_type: str = "scalar"   # scalar | text | tokens | image | audio | dist
    reference_type: str = "scalar"
    higher_is_better: bool = True
    needs_judge: bool = False
    deterministic: bool = True


@dataclass
class MetricResult:
    """Outcome of running one metric across (predictions, references).

    Per-example scores enable bootstrap CIs and paired significance tests
    downstream. ``aggregate`` is the canonical scalar.
    """
    aggregate: float
    per_example: list[float] = field(default_factory=list)
    n: int = 0
    extras: dict[str, Any] = field(default_factory=dict)


def load_metric(package_uri: str) -> Callable[..., MetricResult]:
    """Resolve ``python:module:callable`` to a Python callable."""
    if not package_uri.startswith("python:"):
        raise ValueError(f"unsupported package scheme: {package_uri}")
    rest = package_uri.removeprefix("python:")
    if ":" not in rest:
        raise ValueError(f"bad package_uri: {package_uri}")
    module, attr = rest.split(":", 1)
    mod = importlib.import_module(module)
    fn = getattr(mod, attr, None)
    if fn is None:
        raise ImportError(f"metric callable {attr!r} not in {module!r}")
    return fn
