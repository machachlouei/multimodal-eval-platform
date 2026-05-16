# ADR-001: Three-plane separation — control / data / judge

**Status:** Accepted
**Date:** 2026-05-16
**Source:** Design-Doc.md §5, §15.1

## Context

A model-evaluation platform has three workloads that look superficially similar
but have fundamentally different operating characteristics:

| Workload   | Bound by         | Failure profile                    | Egress posture            |
|------------|------------------|------------------------------------|---------------------------|
| Metadata API | request rate     | Postgres availability              | None (internal-only)      |
| Eval compute | CPU/GPU minutes  | Worker crashes, OOM kills          | None                      |
| Judge calls  | external token budget | Third-party rate limits, model drift | Egress to LLM gateway |

Treating them as one monolith means a judge-token outage degrades the metadata
API; a runaway run drains all judge tokens; a CVE in any single library forces
a redeploy of the entire system.

## Decision

Three deployment planes, each with its own node pool and network policy:

- **Control plane** — stateless FastAPI services for metadata, RBAC, audit, and
  run lifecycle. Behind an internal load balancer.
- **Data plane** — Ray-based eval runners and metric compute pool. No egress.
- **Judge plane** — judge orchestrator, prompt registry, response cache,
  calibration harness. **Only plane permitted egress to the LLM gateway**
  (enforced by NetworkPolicy).

Services within a plane communicate via mTLS-authenticated internal calls.

## Consequences

- **Blast-radius isolation.** A judge gateway outage queues new judge-based
  runs but doesn't degrade the metadata API or classic-metric runs.
- **Independent scaling.** Run-throughput spikes auto-scale the runner pool
  without touching control-plane replicas.
- **Egress security is structurally enforced.** Even a compromised data-plane
  worker cannot exfiltrate to the LLM gateway — the network policy denies it.
- **Operational cost:** more services to operate. Mitigated by shared FastAPI
  scaffolding (`melp/common/service_base.py`), shared telemetry middleware, and
  one runbook template.
- **Deployment cost:** three node pools must be provisioned even at low scale.
  Acceptable: the control plane can run with 2 replicas; the data and judge
  pools scale to zero when idle.

## Alternatives considered

1. **Monolith.** Lower operational overhead, but you'd give up the blast-radius
   and egress-isolation properties. The judge plane's external dependency makes
   this especially painful: any LLM-gateway flap would impact the metadata API.
2. **Two planes (control + combined data/judge).** Better than monolith but
   couples the egress-permitted code path with the compute-heavy code path,
   meaning every metric plugin runs in the same network zone as the judge —
   defeating the §9.6 supply-chain mitigation.
3. **Per-team isolated deployments.** Tried by some shops. Trades comparability
   (a key MELP requirement) for isolation; we'd lose the "two teams running the
   same eval must get the same number" property (§1.2 business goal #2).
