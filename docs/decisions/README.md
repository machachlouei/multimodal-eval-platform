# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for MELP. ADRs
capture decisions that are hard to reverse, that shape the system's properties,
or that future readers will want to understand the reasoning behind.

We use a lightweight format adapted from Michael Nygard's classic template:

```
Status    : Accepted | Superseded by ADR-NNN | Deprecated
Context   : What forces are at play. What's the problem.
Decision  : What we chose.
Consequences : What we accept by choosing this — good and bad.
Alternatives : What we considered and why we didn't pick them.
```

## Numbering

| #   | Title                                                                          | Source                            |
|-----|--------------------------------------------------------------------------------|-----------------------------------|
| 001 | [Three-plane separation: control / data / judge](0001-three-plane-separation.md)    | mirrors Design-Doc.md §15.1       |
| 002 | [Postgres for OLTP, Iceberg for analytical history](0002-postgres-plus-iceberg.md)  | mirrors Design-Doc.md §15.2       |
| 003 | [LLM-as-Judge with provider abstraction](0003-llm-as-judge-provider-abstraction.md) | mirrors Design-Doc.md §15.3       |
| 004 | [Versioned, sandboxed metric plugins](0004-versioned-sandboxed-metrics.md)          | mirrors Design-Doc.md §15.4       |
| 005 | [Immutable, content-addressed datasets](0005-immutable-content-addressed-datasets.md) | mirrors Design-Doc.md §15.5     |
| 006 | [Temporal as the workflow engine](0006-temporal-workflow-engine.md)                 | refines Design-Doc.md §15.6       |
| 007 | [Bootstrap CIs by default; paired permutation for significance](0007-bootstrap-cis-paired-permutation.md) | mirrors Design-Doc.md §15.7 |
| 008 | [REST/FastAPI first, gRPC deferred](0008-rest-first-grpc-deferred.md)               | implementation choice             |
| 009 | [HTMX UI in v1 rather than React](0009-htmx-ui.md)                                  | implementation choice             |
| 010 | [Single launch migration for Phase 1 + Phase 2 schemas](0010-single-launch-migration.md) | divergence from plan          |
| 011 | [In-process metric loader is a known gap; subprocess sandbox is required for prod](0011-metric-loader-sandbox-gap.md) | known gap |
| 012 | [JSON blob as Iceberg stand-in in v1](0012-iceberg-stand-in.md)                     | known gap                         |

## Status conventions

- **Accepted** — the decision is in force.
- **Superseded by ADR-NNN** — a later ADR replaces this one. Keep the original for the historical record.
- **Deprecated** — the decision still describes today's code but we want to move off it; the replacement isn't planned yet.

## When to write a new ADR

- A choice that's hard to reverse (storage shape, identity model, public API contract).
- A choice that locks in dependencies (workflow engine, judge provider, message broker).
- A choice that materially shapes the system's failure modes or operability.
- A divergence from `Design-Doc.md` — readers comparing the code to the spec need to know.

Do **not** write ADRs for routine code organisation, formatter choice, or library
swaps that are easily reversed.

## Process

1. Branch, write the ADR file using the next sequential number.
2. Status starts at `Proposed`; flip to `Accepted` when merged.
3. ADRs are immutable once `Accepted` — supersede via a new ADR rather than editing.
