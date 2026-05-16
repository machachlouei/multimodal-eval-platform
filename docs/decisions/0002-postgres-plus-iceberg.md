# ADR-002: Postgres for OLTP metadata, Iceberg for analytical history

**Status:** Accepted (Iceberg currently a JSON stand-in — see [ADR-012](0012-iceberg-stand-in.md))
**Date:** 2026-05-16
**Source:** Design-Doc.md §7.2, §7.3, §15.2

## Context

MELP has two storage shapes with conflicting requirements:

1. **OLTP metadata** — `run`, `dataset_version`, `metric_version`, audit log.
   Hundreds of writes per minute; foreign keys across half a dozen tables;
   requires transactional integrity (a run must never appear `COMPLETED`
   without its results visible); read-your-writes required for submitters.
2. **Analytical result history** — `run_result` rows accumulate into the tens
   of millions over time. "How did model X score on dataset Y last quarter?"
   is a column-scan over time-partitioned data — exactly what an analytical
   store does well and exactly what Postgres does poorly past ~50M rows.

## Decision

- **Postgres** as the single source of truth for all metadata, including a
  *summary* of each `run_result`. Indexed for the lookup patterns the Run
  Service uses: `(project_id, status)`, `(project_id, request_id)`,
  `(run_id, metric_version_id, slice_def_id)`.
- **Iceberg** tables on the lakehouse for the full per-example, per-slice
  result history, written by the aggregator. Iceberg gives us time-travel
  queries, partition-aware reads, and a schema that survives version bumps.
- **Redis** for hot, recomputable state: judge response cache (§11.4), AuthZ
  role cache (5-min TTL).

Different consistency contracts apply (§7.5): Postgres writes are strongly
consistent; the lakehouse roll-up is eventually consistent (< 5 min stale,
acceptable because leaderboards are advisory, not gating).

## Consequences

- **The right tool per shape.** Per-run reads use Postgres at ~50 ms P50;
  quarterly analytics use Iceberg without taxing the OLTP store.
- **Two systems to operate.** Reconciled by the aggregator: Postgres holds the
  summary row, Iceberg holds the per-example detail. The aggregator writes
  both before flipping the run to `COMPLETED`.
- **Bulk-load to Iceberg keeps Postgres small.** Per-example judgments would
  add ~50M rows/day at Year-1 scale; only summaries go to Postgres (§11.3).
- **Lag tolerance is explicit.** The leaderboard endpoint is documented as
  advisory; production gating reads from Postgres, never from the lakehouse.

## Alternatives considered

1. **Postgres only.** Works to ~10M `run_result` rows; falls apart at Year-3
   scale (500M example-evaluations/day). The history query "model trajectory
   over last quarter" becomes a multi-minute table scan with locking
   implications.
2. **Iceberg only.** Loses transactional integrity on runs; loses sub-second
   reads for the Run Service. Iceberg's commit cadence (seconds, not
   milliseconds) makes it the wrong tool for the request path.
3. **A document DB (e.g., DynamoDB / MongoDB).** Loses relational integrity
   across `run`, `dataset_version`, `metric_version`, `judge_config_version`.
   The platform's whole value proposition rests on those references being
   referentially intact — a per-document store invites silent drift.
4. **Time-series DB (e.g., InfluxDB).** Wrong cardinality model. Metric
   results are *high-cardinality structured rows*, not time-stamped points.
