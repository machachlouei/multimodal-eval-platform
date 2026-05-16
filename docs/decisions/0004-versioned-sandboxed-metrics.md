# ADR-004: Versioned, sandboxed metric plugins

**Status:** Accepted (sandbox is currently in-process; subprocess sandbox is a
known gap — see [ADR-011](0011-metric-loader-sandbox-gap.md))
**Date:** 2026-05-16
**Source:** Design-Doc.md §6.5, §15.4

## Context

"BLEU" should mean the same thing in every team's run. The single biggest
cause of incomparable evals across teams is small variations in metric
implementation: tokenisation differences, smoothing differences, brevity-penalty
differences. Without a single registry, "we got 0.42" and "we got 0.41" are
not comparable.

At the same time, ML teams need to register custom metrics. The platform
cannot ship every metric a team will ever want.

These two requirements pull in opposite directions: opinionated uniformity vs.
team extensibility. The wrong resolution makes the platform either useless or
unsafe.

## Decision

- **One registry, versioned.** Each metric is `(metric_id, version)` —
  e.g., `bleu@1.0.0`. A run references `metric_version_id`, not "BLEU".
- **Plugins are code.** Each metric resolves a `package_uri`
  (`python:melp.metrics.text:bleu`) at evaluation time. Implementations live
  in the `melp/metrics/` tree (built-ins) or in team-owned packages.
- **Registration is gated.** New metric versions require platform-admin role
  (§9.6 supply-chain threat-model row). The registration endpoint validates
  that the `package_uri` resolves before accepting.
- **Per-metric isolation at execution time.** A failing metric does not stop
  others (§6.9); per-example exceptions are counted, not fatal.
- **Tests are part of the contract.** Every metric ships with type-signature
  tests, reference-value tests against a canonical implementation, edge-case
  tests, and a determinism test (§14.2). The registry records
  `tests_passed_at`.

## Consequences

- **Comparability across teams is enforced by code.** Two teams running
  `mtv_bleu_1_0_0` get the same number bit-for-bit (on deterministic metrics).
- **Teams can bring their own metrics** without forking the platform.
- **Audit trail is automatic.** Every run records exactly which metric version
  it used; reproducing the run reuses the same plugin.
- **A bad plugin is a real risk.** Untrusted code runs on shared workers.
  Mitigated by code review (registration gate), signed packages, and the
  subprocess sandbox roadmapped in [ADR-011](0011-metric-loader-sandbox-gap.md).
- **Metric churn is friction for users.** A metric author has to write tests
  and get a review. We accept this — it's the price of comparability.

## Alternatives considered

1. **Built-in metrics only.** Maximally safe and uniform, but blocks every
   team that needs a custom metric. They'd write notebook one-offs instead
   and the comparability problem returns through the back door.
2. **Arbitrary user code in workers, no registry.** Maximally flexible and
   maximally unsafe. Lost: comparability, audit trail, supply-chain control.
3. **Metric implementations as remote services (HTTP).** Cleaner isolation
   than in-process. Adds per-metric latency on the hot path; harder to ensure
   determinism. Could be added later for heavyweight metrics (FID, BERTScore)
   without changing the contract.
