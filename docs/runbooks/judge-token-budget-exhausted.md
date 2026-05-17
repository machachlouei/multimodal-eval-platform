# Runbook: Judge token budget exhausted

**Symptom** — `melp_judge_budget_throttled_rate > 0` for >10 min on one
project. UI banner shows "judge budget exhausted, runs queued".

**Severity** — SEV-3. Single-project impact; no other tenant affected.

**Acknowledge** — On-call primary, project owner. Do **not** raise the
budget without checking why the spend is high.

**Diagnose**
1. Dashboard `MELP — Per-Project Quotas → Judge tokens`: spending rate
   over the last 24 h.
2. Recent judge-based runs: `melp run list --project X --status COMPLETED |
   head -20`. Big jump in examples per run? Bigger inputs? Cache hit rate
   collapsed (e.g. prompt was version-bumped, invalidating the cache)?
3. `redis-cli GET budget:{project}:{minute}` for the live rate.

**Mitigate** — Short-term: enable off-peak scheduling on the project's
judge configs (`priority=low` runs only fire during 02:00–06:00 UTC).
Don't raise the daily budget yet.

**Resolve** — If demand is genuine:
1. File a budget-raise request with the LLM gateway team (§16.1 R-3).
2. Raise `quota_judge_tokens_per_day` on the project once approved.

If demand is *not* genuine (cache invalidated by accident, prompt
bumped without version intent):
1. Restore the previous prompt version.
2. Run a single canary to validate the cache warms up.

**Verify** — Throttle rate back to 0 within an hour; submissions resume.

**Postmortem** — Only if this caused a release miss. Otherwise note the
spike and move on.
