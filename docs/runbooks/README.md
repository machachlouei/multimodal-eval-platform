# Runbooks

Every SEV-1 / SEV-2 alert has a linked runbook (Design-Doc §13.5: "alerts
without runbooks are bugs"). Each runbook follows the same shape:

```
Symptom    : What you see (page, dashboard panel, error message).
Severity   : SEV-1 / SEV-2 / SEV-3.
Acknowledge: Touch the page, post in #melp-incident.
Diagnose   : The first three queries / commands to run.
Mitigate   : Stop the bleed (not yet "fix").
Resolve    : Root-cause fix.
Verify     : How you know it's done.
Postmortem : When to schedule, what to include.
```

## Index

| Runbook | Severity | Linked alert |
|---|---|---|
| [Postgres primary failover](postgres-failover.md) | SEV-1 | `melp_db_write_failures_rate > 0.01 for 1m` |
| [Judge gateway outage](judge-gateway-outage.md) | SEV-2 | `melp_judge_call_failures_rate > 0.5 for 5m` |
| [Calibration drift](calibration-drift.md) | SEV-2 | `judge.calibration.drift` webhook |
| [Run flood / one project saturating capacity](run-flood.md) | SEV-2 | `melp_run_queue_depth{project="X"} > 1000 for 5m` |
| [Judge token budget exhausted](judge-token-budget-exhausted.md) | SEV-3 | `melp_judge_budget_throttled_rate > 0 for 10m` |
