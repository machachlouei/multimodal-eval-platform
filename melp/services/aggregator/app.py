"""Results Aggregator service entry. Wraps ``melp.workers.aggregator`` (§6.10)."""
from __future__ import annotations

import uvicorn
from fastapi import HTTPException

from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.workers.aggregator import aggregate_run

app = make_app("aggregator", title="MELP Results Aggregator")


@app.post("/v1/aggregate/{run_id}")
def trigger_aggregate(run_id: str) -> dict[str, str]:
    try:
        aggregate_run(run_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"run_id": run_id, "status": "AGGREGATED"}


def run() -> None:
    uvicorn.run("melp.services.aggregator.app:app", host="0.0.0.0", port=get_settings().port_aggregator)


if __name__ == "__main__":
    run()
