# Runbook: Judge gateway outage

**Symptom** — `melp_judge_call_failures_rate > 0.5` for >5 min; judge-based
runs stall in `RUNNING`; PR comments "MELP gate failed: judge timeout".

**Severity** — SEV-2 (degrades judge-based runs only; classic runs unaffected
by design — §10.4).

**Acknowledge** — On-call primary; post in `#melp-incident` and `#llm-gateway`
(the upstream owner). Do **not** restart the judge orchestrator — that
clears the in-flight retry counters and produces a thundering herd.

**Diagnose**
1. `curl -fsS https://llm-gateway.internal/healthz` — is the gateway itself
   up?
2. Dashboard `MELP — Judge Plane → Latency`: P99 vs. baseline. Sudden
   doubling = backend slow. Spike to ∞ = circuit breaker open.
3. `redis-cli LLEN melp:judge:dlq:*` — how many examples have already
   dead-lettered?

**Mitigate**
- If the upstream is partially up, **let circuit breakers do their job**.
  The orchestrator's 3-tier retry (in-call → in-orch → DLQ) handles this.
  Page rate of DLQ growth is the right signal of severity.
- If the upstream is fully down for >15 min, post a notice in
  `#melp-users`: "judge-based runs are queued; classic runs unaffected".

**Resolve** — When the gateway returns:
1. Confirm `melp_judge_call_failures_rate < 0.05` for 5 min.
2. Run the DLQ replay command for each affected run:
   ```bash
   python -m melp.scripts.dlq_replay --run-id <run_id>
   ```
3. Resume any runs paused by the workflow engine (Temporal: `signal-with-start`
   a "resume" signal on the workflow).

**Verify**
- DLQ keys are empty: `redis-cli KEYS 'melp:judge:dlq:*'` returns nothing.
- Sampling 5 recent judge-based runs: all reach COMPLETED.

**Postmortem** — Within 5 business days. Especially if this is a
recurring upstream incident, file the action item to **negotiate a higher
fallback token budget or a secondary gateway** (R-3 in the risk register).
