# Runbook: Judge calibration drift

**Symptom** — `judge.calibration.drift` webhook fired; `Judge Health`
dashboard shows κ below 0.7 for one judge-config-version.

**Severity** — SEV-2. Judge scores are still being produced; we just no
longer trust them against the published rubric.

**Acknowledge** — On-call primary + the team that owns the judge config
(field `judge_config.owner_team`).

**Diagnose**
1. Look at the last calibration_run row:
   ```sql
   select * from calibration_run
   where judge_config_version_id = '<id>' order by created_at desc limit 1;
   ```
2. Compare to the previous 5 calibration_runs: gradual decline (model
   upgrade upstream) or sudden cliff (prompt was changed without a
   version bump — bug)?
3. Sample 10 of the most-recent judgments. Read them.  Are they obviously
   wrong, or just drifting in average?

**Mitigate**
- **Stop using this judge config version for gating decisions.** Mark it
  `inactive=true` so the gating endpoint refuses to honour it; existing
  runs still record their judgments but downstream tooling will see the
  flag.
- Notify the affected projects in `#melp-users` (filter by which projects
  reference this judge config).

**Resolve**
1. Determine whether the issue is the prompt, the rubric, or the
   underlying model. Don't fix a model drift with a prompt change —
   re-version the prompt instead.
2. Publish a new `judge_config_version` with the fix.
3. Run calibration on the new version: agreement must be **non-inferior**
   to the last known-good version (§14.3).
4. Re-run any in-flight production gating runs that depended on this judge.

**Verify**
- `select cohen_kappa from calibration_run where judge_config_version_id = '<new>' order by created_at desc limit 1;` ≥ 0.7.
- A canary judge-based run on the golden set produces sane outputs.

**Postmortem** — Always. Required: was this catchable earlier? Should the
κ floor be different per-rubric? Action items into the calibration
roadmap.
