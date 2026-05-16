"""Dev entry: spawn every service + worker in one process.

Only use this for local dev / demos. In prod each service is a separate
Kubernetes deployment.
"""
from __future__ import annotations

import multiprocessing as mp
import signal
import sys
import time

from melp.common.telemetry import configure_logging, get_logger


def _start(target_name: str) -> mp.Process:
    def _target():
        import importlib

        mod = importlib.import_module(f"melp.services.{target_name}.app")
        mod.run()

    p = mp.Process(target=_target, name=target_name)
    p.start()
    return p


def main() -> None:
    configure_logging("run_all")
    log = get_logger(__name__)
    services = [
        "gateway", "authz", "run", "dataset", "model",
        "metric", "judge_config", "project", "audit",
        "aggregator", "judge_orch",
    ]
    procs = [_start(s) for s in services]

    def _worker():
        from melp.workers.runner import run as worker_run

        worker_run()

    wp = mp.Process(target=_worker, name="worker")
    wp.start()
    procs.append(wp)

    def _bye(*_):
        for p in procs:
            p.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, _bye)
    signal.signal(signal.SIGTERM, _bye)
    log.info("all_services_started", services=services + ["worker"])
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
