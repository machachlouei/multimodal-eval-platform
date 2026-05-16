# ADR-010: Single launch migration for Phase 1 + Phase 2 schemas

**Status:** Accepted
**Date:** 2026-05-16
**Source:** Divergence from the implementation plan (Phase 1 / Phase 2 split)

## Context

The implementation plan splits schema work between Phase 1 (run, dataset,
metric, audit) and Phase 2 (judge_config, prompt_version, judgment, webhook,
calibration_run). This is a reasonable phasing for a real rollout: minimise
DB-level risk during the pilot.

We're shipping a greenfield system. Nobody is on the platform yet. There is
no "production" to migrate.

## Decision

- **One Alembic migration at version `0001_initial`** contains every table
  from Phase 1 and Phase 2.
- **Indexes are created up-front**, not added later — they're cheap on an
  empty table and avoid a follow-up migration with locks.
- **Subsequent schema changes land as new revisions**, never by editing
  `0001_initial`.

## Consequences

- **One DB schema bring-up step** for the pilot team — they don't migrate
  through Phase 2's add-judge-tables window.
- **Smaller migration test surface.** A single migration is easier to verify
  end-to-end (especially the rollback path) than two interleaved ones.
- **Slightly heavier "first migration"** at deploy time. Acceptable: the
  whole schema bring-up runs in well under a second on Postgres 16.
- **Divergence from the plan is explicit.** A reader comparing the
  implementation to the plan will notice and could be confused. This ADR is
  the breadcrumb that explains it.
- **Real production migrations later still follow the plan's pattern**:
  expand-contract, blue/green for risky changes, shadow reads on schema
  rewrites. That's an operational discipline, not a launch-day concern.

## Alternatives considered

1. **Honour the plan and ship two migrations.** No technical benefit on a
   greenfield. Would have created an artificial "Phase 2 migration window"
   in CI and the docs.
2. **Skip Alembic entirely; use SQLAlchemy `create_all`.** Convenient for
   tests, terrible for production. Operations need versioned migrations
   regardless of whether there's one or many of them.
