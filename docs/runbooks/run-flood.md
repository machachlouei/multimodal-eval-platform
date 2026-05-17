# Runbook: Run flood (one project saturating capacity)

**Symptom** — `melp_run_queue_depth{project="X"} > 1000` for >5 min; other
projects start seeing rising P99; rate-limit headers return `X-RateLimit-
Remaining: 0` for project X.

**Severity** — SEV-2.

**Acknowledge** — On-call primary; the offender project's owner.

**Diagnose**
1. Dashboard `MELP — Per-Project Quotas`: is this CI gone rogue, or a
   human user submitting in a tight loop?
2. `melp run list --project X --status QUEUED | wc -l` — confirms queue
   depth.
3. Recent audit log entries for `run.create` on this project — pattern of
   submitter (one CI bot? many?), same idempotency keys (then it's a
   misconfigured retry loop)?

**Mitigate**
- **If it's a runaway CI loop:** revoke the CI's project-scoped token via
  the project owner panel. The fair-queueing pre-emption in the gateway
  starts shedding their requests immediately.
- **If it's a human:** call them. Then cancel queued runs in bulk:
  ```bash
  melp run list --project X --status QUEUED | xargs -n1 melp run cancel --project X
  ```

**Resolve** — Identify the source, fix the workflow that caused it. If
this happens twice from the same team in a quarter, file a ticket to
lower their concurrency quota by half until they explain it.

**Verify**
- Queue depth back to normal for project X.
- Other projects' P99 returns to baseline.

**Postmortem** — Only if this exceeds 30 min or if it harms another
project's SLO. Otherwise log it and move on.
