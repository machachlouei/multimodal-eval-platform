# Chaos test manifests

Quarterly chaos drills (Design-Doc §10.5, §11.7). Each manifest is a single
fault injected at a time; we never combine them in prod because the
diagnosis becomes intractable.

| Manifest | Failure | Expected behavior |
|---|---|---|
| [postgres-failover.yaml](postgres-failover.yaml) | Kill the Postgres primary pod | <60 s write unavailability; reads continue on replicas; new runs land in PENDING_SUBMISSION and reconcile when writes return (§10.4) |
| [judge-gateway-down.yaml](judge-gateway-down.yaml) | 100% network drop to the LLM gateway namespace | Judge-based runs queue; classic runs unaffected; calibration drift alerts may fire (correctly) (§10.4) |
| [object-store-zone-loss.yaml](object-store-zone-loss.yaml) | Drop a zone of MinIO/S3 | Reads fail over to replica; writes degrade to a durable buffer with limited capacity (§10.4) |
| [run-flood.yaml](run-flood.yaml) | 10x normal submission rate from one project | Rate limits engage; other projects unaffected via fair queueing; SLO holds (§10.6) |

## Tooling

These are written for **Chaos Mesh** (CRDs `NetworkChaos`, `PodChaos`,
`IOChaos`). Apply with:

```bash
kubectl apply -f infra/chaos/<manifest>.yaml
# observe for the documented duration, then:
kubectl delete -f infra/chaos/<manifest>.yaml
```

In CI we run chaos tests quarterly via a scheduled job; results are reviewed
in the operations review and any failed expectation becomes a remediation
ticket.

## Schedule

| Drill | Cadence | Owner |
|---|---|---|
| Postgres failover | Quarterly | On-call lead |
| Judge gateway outage | Quarterly | On-call lead |
| Object-store zone loss | Annually (heavyweight) | Platform lead + data-platform liaison |
| Run flood | Quarterly | On-call lead |
