# ADR-011: Metric loader runs in-process today; subprocess sandbox is a Phase-3 gap

**Status:** Accepted (known gap — must close before Phase 3)
**Date:** 2026-05-16
**Source:** Divergence from Design-Doc.md §6.5 / §9.6 supply-chain row

## Context

Design-Doc §6.5 specifies: "Metric packages run in sandboxed subprocesses
with CPU/memory limits." This is the §9.6 STRIDE table's supply-chain
mitigation — a malicious or buggy metric plugin must not be able to read the
worker's secrets, kill the host, or exhaust shared resources.

The current implementation in [`melp/metrics/base.py`](../../melp/metrics/base.py)
uses `importlib.import_module` and calls the resolved function in-process. It
provides per-metric exception isolation (a failing metric doesn't take down
the rest of the run, §6.9) but **not** address-space isolation.

For an internally-trusted, code-reviewed, signed-package supply chain on a
pilot team, this is acceptable. For a system that publishes a metric-
registration endpoint and accepts community plugins, it is not.

## Decision

- **Status quo for v1:** in-process metric execution. Per-metric error
  catch + count; CPU/memory limits enforced at the pod level only.
- **Required before Phase 3:** wrap each metric invocation in a subprocess
  with `seccomp` / `AppArmor` profiles, cgroup CPU + memory caps, and a
  hard wall-clock timeout. The subprocess gets a serialised inputs blob on
  stdin and writes a serialised `MetricResult` to stdout.
- **Registration is gated on platform-admin** for the duration of this gap
  (§9.6 implementation). The gate carries the security review until the
  subprocess sandbox lands.
- **The seam is preserved.** `MetricResult` is already a small,
  JSON-serialisable dataclass; the call site `load_metric(uri)(args)` will
  swap to `run_in_sandbox(uri, args) -> MetricResult` without touching the
  metric implementations.

## Consequences

- **Real, named gap.** Anyone reading the code or running a security review
  finds this ADR and understands the posture.
- **Limited blast radius for v1** because registration is platform-admin-
  only — a casual team member cannot inject code. The threat is an insider
  with platform-admin or a compromised admin account.
- **No metric author has to change their implementation** when the sandbox
  lands — the contract is already a pure function.

## Alternatives considered

1. **Ship the subprocess sandbox in v1.** Right answer for a public-facing
   platform; overkill for a pilot with platform-admin-only registration and
   one trusted team. The plan budget didn't include the time to do this
   carefully.
2. **Containerised metric execution (one container per metric call).** Best
   isolation, worst latency. ~100 ms of container-startup overhead per call
   would dominate runtime for fast metrics on small datasets.
3. **WASM sandbox.** Cleaner story than subprocesses for a polyglot future.
   Adds a metric-author constraint (no arbitrary native deps) that doesn't
   fit Python ML libraries today.
