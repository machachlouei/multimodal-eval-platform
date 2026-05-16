"""Judge Orchestrator service entry. Wraps ``melp.judge.orchestrator`` and the
calibration harness behind a small HTTP surface (used by the data plane and by
the calibration scheduler).
"""
from __future__ import annotations

import uvicorn
from fastapi import Body

from melp.common.config import get_settings
from melp.common.service_base import make_app
from melp.judge.calibration import run_calibration
from melp.judge.orchestrator import judge_run

app = make_app("judge_orch", title="MELP Judge Orchestrator")


@app.post("/v1/judge/run/{run_id}")
def trigger_judge_for_run(run_id: str, examples: list[dict] = Body(...)) -> dict[str, int]:
    n = judge_run(run_id, examples)
    return {"judged": n}


@app.post("/v1/judge/calibrate/{judge_config_version_id}")
def trigger_calibration(judge_config_version_id: str) -> dict:
    return run_calibration(judge_config_version_id)


def run() -> None:
    uvicorn.run("melp.services.judge_orch.app:app", host="0.0.0.0", port=get_settings().port_judge_orch)


if __name__ == "__main__":
    run()
