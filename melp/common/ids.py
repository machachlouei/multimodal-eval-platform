"""ULID-based IDs with type-safe prefixes. See §7.2 — every entity uses ULIDs."""
from __future__ import annotations

from ulid import ULID

_PREFIXES = {
    "project": "prj",
    "user": "usr",
    "membership": "mem",
    "dataset": "ds",
    "dataset_version": "dsv",
    "slice_def": "sld",
    "model": "mdl",
    "model_version": "mdv",
    "metric": "mtc",
    "metric_version": "mtv",
    "judge_config": "jc",
    "judge_config_version": "jcv",
    "prompt": "pmt",
    "prompt_version": "pmv",
    "run": "run",
    "run_result": "rr",
    "judgment": "jmt",
    "audit": "aud",
    "webhook": "wh",
    "calibration_run": "cal",
}


def new_id(kind: str) -> str:
    if kind not in _PREFIXES:
        raise ValueError(f"unknown id kind: {kind}")
    return f"{_PREFIXES[kind]}_{ULID()!s}"


def id_kind(value: str) -> str | None:
    for kind, prefix in _PREFIXES.items():
        if value.startswith(prefix + "_"):
            return kind
    return None
