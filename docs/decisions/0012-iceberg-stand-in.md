# ADR-012: JSON-on-object-store as Iceberg stand-in in v1

**Status:** Accepted (known gap — close before result history exceeds ~10M rows)
**Date:** 2026-05-16
**Source:** Divergence from Design-Doc.md §7.3 / [ADR-002](0002-postgres-plus-iceberg.md)

## Context

[ADR-002](0002-postgres-plus-iceberg.md) commits to Iceberg as the analytical
store for per-example result history, with Postgres holding summaries. The
shape of that commitment is correct; the implementation does not yet write
Iceberg.

What ships today (see [`melp/workers/aggregator.py`](../../melp/workers/aggregator.py)):
the aggregator writes a single JSON blob to
`s3://<results-bucket>/runs/<run_id>/aggregate.json`, alongside the
per-run summary in Postgres. There is no time-travel, no partition pruning,
no schema evolution.

Two reasons for the stand-in:
1. The lakehouse-side Iceberg table provisioning is a data-platform-team
   workstream, not a MELP-team workstream (assumption in §2.3). MELP can't
   block on it for the pilot.
2. PyIceberg is added to the optional deps list but not wired into the
   aggregator. The contract is *which file is written and where*; the
   serialiser is swappable.

## Decision

- **v1:** JSON-on-object-store at the documented URI. Postgres holds the
  per-run summary as the authoritative record.
- **v2 (data-platform team owns scheduling):** drop in a PyIceberg writer at
  the aggregator boundary. The result-blob URI moves from
  `runs/<id>/aggregate.json` to an Iceberg table; the Postgres summary row
  is unchanged.
- **Read paths split now to make the migration cheap.** The Run Service and
  the UI read summaries from Postgres only. Nothing in the code reads the
  current JSON blob — it exists for auditability and future Iceberg ingest.
- **Out of scope for v1:** lakehouse time-travel queries from the UI.
  Leaderboards and project pages read Postgres.

## Consequences

- **Pilot can ship without the lakehouse.** The platform team isn't blocked
  on an external dependency that they don't own.
- **History queries are dev-only until the swap.** "Model X over the last
  quarter" works against Postgres at pilot scale; it will not scale past
  Year-2 volumes (§11.1 row 4) and that's the deadline for the swap.
- **No code on the read side will need to change** when Iceberg lands. The
  swap is contained to one writer and one schema-evolution step.

## Alternatives considered

1. **Block the pilot until Iceberg is provisioned.** Couples MELP's launch to
   another team's roadmap. Pilot value comes from ergonomics + comparability,
   not from analytical depth on day one.
2. **Parquet files on object store as a halfway house.** Better than JSON
   for the eventual migration cost, worse than JSON for human inspection in
   the pilot phase. The volume isn't big enough to matter for v1.
3. **Roll our own append-only log in Postgres for the history table.** Cheap
   to write, terrible to scale. Effectively re-implementing Iceberg's worst
   features without its best ones.
