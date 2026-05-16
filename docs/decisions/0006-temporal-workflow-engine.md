# ADR-006: Temporal as the workflow engine for run orchestration

**Status:** Accepted (refines Design-Doc.md §16.2 #2)
**Date:** 2026-05-16
**Source:** Design-Doc.md §6.7, §15.6, §16.2

## Context

A run pipeline is `load_dataset → run_inference → compute_metrics → run_judge
→ aggregate → write_results → notify`. Each stage:

- Can take minutes to hours.
- Can fail transiently (worker OOM, transient gateway 5xx) and must retry.
- Must be checkpoint-able — losing a 45-minute inference stage to a worker
  crash is a Bad Day.
- Must support cancellation mid-flight (FR-1).
- Must be exactly-once at the result-write boundary.

This is a workflow problem, not a job-queue problem.

Design-Doc §16.2 leaves the final choice open between "an existing internal
engine" and "adopting a new one." This ADR records the choice for the
open-source reference implementation.

## Decision

**Temporal** for production. The Python SDK (`temporalio`) integrates cleanly
with Ray activities; the engine handles durable orchestration, retries,
heartbeats, and cancellation.

**Local in-process runner as a fallback** for dev and tests
(`melp.workers.runner.process_run_locally`), gated by `MELP_USE_TEMPORAL=0`.
The local runner reads QUEUED rows from Postgres and executes the same
activities sequentially, so tests don't need a Temporal cluster.

Workflow definition lives in `melp/workflows/eval_workflow.py`; activities
delegate to plain Python functions in `melp/workers/`. The split means
activities can be tested without Temporal in the loop.

## Consequences

- **Durable orchestration is free.** Activity-level retry with exponential
  backoff, heartbeats, and exactly-once at the activity boundary are all
  inherited from Temporal.
- **Cancellation works correctly** — Temporal propagates a cancel signal
  through pending activities.
- **Local dev is cheap.** New engineers don't need a Temporal cluster; tests
  run against the in-process runner.
- **One more system to operate in prod.** Temporal needs Postgres (or
  Cassandra), its own deployment, and observability. Acceptable given the
  alternative is building a worse Temporal in-house.

## Alternatives considered

1. **Airflow.** Built for scheduled batch DAGs. The retry/timeout model is
   weaker; mid-workflow state mutation is awkward; the operator pattern is
   heavier than activity-based workflows. Best at "scheduled ETL," worst at
   "long-running stateful pipeline."
2. **A state machine in Postgres.** Tempting at small scale. Rapidly grows
   into a worse Temporal: you re-invent durable retries, timers, cancellation,
   heartbeats, exactly-once. The doc warns against this in §15.6 and we
   agree.
3. **Argo Workflows.** K8s-native, good for batch. Activities are
   container-per-step which is high overhead for our many small steps; not
   ergonomic for stateful workflow code.
4. **An internal/existing workflow engine.** Open issue in the doc (§16.2 #2);
   resolution depends on what's available in the deploying org. The reference
   implementation picks Temporal because it's open-source and well-supported.
