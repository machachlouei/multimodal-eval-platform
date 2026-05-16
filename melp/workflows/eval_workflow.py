"""Temporal workflow definition for the classic eval pipeline.

Lazy-imports temporalio so the rest of the system works without it.
Stages mirror §17.4:
    load_dataset → run_inference → compute_metrics → (optional) run_judge
        → aggregate → write_results → notify.

Each stage is an idempotent activity. On worker crash, Temporal replays from
the last committed event (§6.7).
"""
from __future__ import annotations

from datetime import timedelta

from melp.common.config import get_settings


def start(run_id: str) -> None:
    """Start (fire-and-forget) the Temporal workflow for ``run_id``."""
    import asyncio

    from temporalio.client import Client  # type: ignore[import-not-found]

    s = get_settings()

    async def _run() -> None:
        client = await Client.connect(s.temporal_host, namespace=s.temporal_namespace)
        await client.start_workflow(
            "eval_workflow",
            run_id,
            id=f"melp-eval-{run_id}",
            task_queue="melp-eval",
            execution_timeout=timedelta(hours=6),
        )

    asyncio.get_event_loop().run_until_complete(_run())


# ---------- Workflow definition (only loaded when Temporal is in use) ----------
try:  # pragma: no cover
    from temporalio import activity, workflow

    @activity.defn
    async def load_dataset(run_id: str) -> int:
        from melp.workers.runner import load_dataset_for_run

        return load_dataset_for_run(run_id)

    @activity.defn
    async def run_inference(run_id: str) -> int:
        from melp.workers.runner import run_inference_for_run

        return run_inference_for_run(run_id)

    @activity.defn
    async def compute_metrics(run_id: str) -> int:
        from melp.workers.metric_pool import compute_metrics_for_run

        return compute_metrics_for_run(run_id)

    @activity.defn
    async def aggregate(run_id: str) -> None:
        from melp.workers.aggregator import aggregate_run

        aggregate_run(run_id)

    @workflow.defn(name="eval_workflow")
    class EvalWorkflow:
        @workflow.run
        async def run(self, run_id: str) -> None:
            await workflow.execute_activity(load_dataset, run_id, start_to_close_timeout=timedelta(minutes=30))
            await workflow.execute_activity(run_inference, run_id, start_to_close_timeout=timedelta(hours=2))
            await workflow.execute_activity(compute_metrics, run_id, start_to_close_timeout=timedelta(hours=1))
            await workflow.execute_activity(aggregate, run_id, start_to_close_timeout=timedelta(minutes=30))

except ImportError:
    EvalWorkflow = None  # type: ignore[assignment]
