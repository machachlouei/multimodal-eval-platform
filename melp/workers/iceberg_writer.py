"""Iceberg writer for aggregated run results. Closes ADR-012.

The aggregator writes per-(run_id, metric_version_id, slice_def_id) rows to a
single Iceberg table ``melp.run_result_history`` partitioned by
``submitted_at_day``. Rows are append-only; corrections happen by writing a
new run (immutable result history).

Falls back to the JSON-blob stand-in when PyIceberg is not installed or the
catalog isn't reachable — keeps local dev cheap.

See Design-Doc.md §7.3 row 3, and ADR-002 / ADR-012.
"""
from __future__ import annotations

import json
import os
from typing import Any

from melp.common.config import get_settings
from melp.common.storage import put_bytes
from melp.common.telemetry import get_logger

log = get_logger(__name__)

ICEBERG_TABLE = "melp.run_result_history"
SCHEMA_FIELDS = [
    ("run_id", "string"),
    ("project_id", "string"),
    ("model_version_id", "string"),
    ("dataset_version_id", "string"),
    ("metric_version_id", "string"),
    ("slice_name", "string"),
    ("point_estimate", "double"),
    ("ci_low", "double"),
    ("ci_high", "double"),
    ("ci_method", "string"),
    ("n_examples", "long"),
    ("p_value", "double"),
    ("effect_size", "double"),
    ("submitted_at_day", "date"),
]


def _try_iceberg_append(rows: list[dict[str, Any]]) -> bool:
    """Best-effort append to Iceberg via PyIceberg. Returns True on success."""
    if os.environ.get("MELP_ICEBERG", "auto") == "off":
        return False
    try:
        # Lazy imports — PyIceberg + a catalog client are heavy.
        from pyiceberg.catalog import load_catalog  # type: ignore[import-not-found]
        import pyarrow as pa  # type: ignore[import-not-found]
    except ImportError:
        return False

    catalog_uri = os.environ.get("MELP_ICEBERG_CATALOG", "")
    if not catalog_uri:
        return False

    try:
        catalog = load_catalog("default", **{"uri": catalog_uri})
        if not catalog.table_exists(ICEBERG_TABLE):
            log.warning("iceberg.table_missing", table=ICEBERG_TABLE)
            return False
        tbl = catalog.load_table(ICEBERG_TABLE)
        arrow_table = pa.Table.from_pylist(rows)
        tbl.append(arrow_table)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("iceberg.append_failed", error=str(e))
        return False


def _json_fallback(run_id: str, rows: list[dict[str, Any]]) -> None:
    s = get_settings()
    put_bytes(
        s.s3_bucket_results,
        f"runs/{run_id}/aggregate.json",
        json.dumps(rows).encode(),
        "application/json",
    )


def write_run_results(run_id: str, rows: list[dict[str, Any]]) -> str:
    """Persist aggregated rows. Returns ``"iceberg"`` or ``"json"``."""
    if rows and _try_iceberg_append(rows):
        log.info("results.persisted", run_id=run_id, target="iceberg", n=len(rows))
        return "iceberg"
    _json_fallback(run_id, rows)
    log.info("results.persisted", run_id=run_id, target="json", n=len(rows))
    return "json"
