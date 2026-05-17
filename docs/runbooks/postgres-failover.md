# Runbook: Postgres primary failover

**Symptom** — `melp_db_write_failures_rate > 1%` for >1 min; UI shows 5xx on
mutating endpoints; new runs sit in `PENDING_SUBMISSION`.

**Severity** — SEV-1.

**Acknowledge** — Page on-call primary; secondary backs up; post in
`#melp-incident` ("PG primary failover, ack'd by @<oncall>").

**Diagnose**
1. Dashboard `MELP — Platform Health → Database`: which node is primary,
   replica lag, connection count.
2. `kubectl get pods -n melp-data | grep postgres` — is the primary alive
   but slow, or gone?
3. `psql -h melp-postgres-primary -c '\x' -c 'select * from pg_stat_replication;'`
   on the replica to see if replication is still flowing.

**Mitigate** — If the primary is unreachable for >60 s, trigger replica
promotion:

```bash
kubectl exec -n melp-data melp-postgres-replica-0 -- \
  patronictl failover --master melp-postgres-primary --candidate melp-postgres-replica-0
```

Reads continue uninterrupted because read replicas keep serving. New writes
land in `PENDING_SUBMISSION` and the Run-Service reconciler re-submits when
the new primary is up (§6.3 failure behavior).

**Resolve** — Investigate the original primary (disk, OOM, network). If
unrecoverable, replace with a fresh node and let WAL streaming catch it up.

**Verify**
- `melp_db_write_failures_rate < 0.001` for 5 min.
- `melp_run_pending_submission_count` returns to 0.
- A canary `POST /v1/projects/{p}/runs` returns 201.

**Postmortem** — Schedule within 5 business days. Required sections:
timeline, root cause, contributing factors, action items, blast radius
(how many runs landed in PENDING_SUBMISSION and how long they waited).
