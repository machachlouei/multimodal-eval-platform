"""Subprocess sandbox for metric plugins. Closes ADR-011.

Each metric invocation runs in a forked subprocess with:
  - CPU time limit  (RLIMIT_CPU)
  - Address-space cap (RLIMIT_AS)
  - File-descriptor cap (RLIMIT_NOFILE)
  - Wall-clock timeout via subprocess.communicate(timeout=…)

Inputs and outputs cross the boundary as pickled payloads. We pickle the
`MetricResult` dataclass (small, fully-controlled) — not arbitrary user objects.

The sandbox is **not** a full security boundary on its own; production must
also drop seccomp profile (`infra/seccomp/metric.json`) and run the pod with
NET_NONE network policy. Both are infra concerns; this module is what makes
the per-call CPU/RAM caps work today.

Fallback: when ``MELP_METRIC_SANDBOX=0`` we call the metric in-process. This
is intended for unit tests where the subprocess startup tax is wasteful.
"""
from __future__ import annotations

import os
import pickle
import subprocess
import sys
from dataclasses import asdict
from typing import Any, Sequence

from melp.common.telemetry import get_logger
from melp.metrics.base import MetricResult, load_metric

log = get_logger(__name__)

# Defaults are intentionally generous; tune per metric in MetricVersion.signature.
DEFAULT_CPU_SECONDS = 60
DEFAULT_MEMORY_MB = 2048
DEFAULT_WALL_SECONDS = 120


def _set_limit(resource_module: Any, limit: int, soft: int, hard: int | None = None) -> None:
    """Set an rlimit without exceeding the platform's existing hard cap."""
    target_hard = soft if hard is None else hard
    _, current_hard = resource_module.getrlimit(limit)
    if current_hard != resource_module.RLIM_INFINITY:
        soft = min(soft, current_hard)
        target_hard = min(target_hard, current_hard)
    try:
        resource_module.setrlimit(limit, (soft, target_hard))
    except (OSError, ValueError):
        # Some platforms expose an rlimit but reject lowering it in child
        # processes. Keep the sandbox usable and rely on the other limits.
        return


def _runner_main() -> None:
    """Entry point for the subprocess. Reads pickled call from stdin, writes
    pickled result to stdout. No code path here should import or call anything
    outside the metric plugin."""
    import resource

    payload = pickle.loads(sys.stdin.buffer.read())  # noqa: S301 — trusted parent
    pkg_uri = payload["package_uri"]
    predictions = payload["predictions"]
    references = payload["references"]
    kwargs = payload.get("kwargs", {})
    cpu = int(payload.get("cpu_seconds", DEFAULT_CPU_SECONDS))
    mem_mb = int(payload.get("memory_mb", DEFAULT_MEMORY_MB))

    # Apply rlimits inside the child.
    _set_limit(resource, resource.RLIMIT_CPU, cpu)
    _set_limit(resource, resource.RLIMIT_AS, mem_mb * 1024 * 1024)
    _set_limit(resource, resource.RLIMIT_NOFILE, 256)

    try:
        fn = load_metric(pkg_uri)
        result: MetricResult = fn(predictions, references, **kwargs)
        out = {"ok": True, "result": asdict(result)}
    except Exception as e:  # noqa: BLE001
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    sys.stdout.buffer.write(pickle.dumps(out))


def run_metric_in_sandbox(
    package_uri: str,
    predictions: Sequence[Any],
    references: Sequence[Any],
    *,
    kwargs: dict[str, Any] | None = None,
    cpu_seconds: int = DEFAULT_CPU_SECONDS,
    memory_mb: int = DEFAULT_MEMORY_MB,
    wall_seconds: int = DEFAULT_WALL_SECONDS,
) -> MetricResult:
    if os.environ.get("MELP_METRIC_SANDBOX", "1") == "0":
        fn = load_metric(package_uri)
        return fn(predictions, references, **(kwargs or {}))

    payload = pickle.dumps(
        {
            "package_uri": package_uri,
            "predictions": list(predictions),
            "references": list(references),
            "kwargs": kwargs or {},
            "cpu_seconds": cpu_seconds,
            "memory_mb": memory_mb,
        }
    )

    proc = subprocess.Popen(
        [sys.executable, "-m", "melp.metrics.sandbox", "_runner"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        out, err = proc.communicate(payload, timeout=wall_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise TimeoutError(f"metric {package_uri} exceeded wall-clock {wall_seconds}s")
    if proc.returncode != 0:
        raise RuntimeError(
            f"metric {package_uri} subprocess exited {proc.returncode}: {err.decode()[:500]}"
        )
    parsed = pickle.loads(out)  # noqa: S301 — trusted child
    if not parsed.get("ok"):
        raise RuntimeError(parsed.get("error", "unknown sandbox error"))
    d = parsed["result"]
    return MetricResult(
        aggregate=d["aggregate"],
        per_example=d.get("per_example", []),
        n=d.get("n", 0),
        extras=d.get("extras", {}),
    )


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "_runner":
    _runner_main()
