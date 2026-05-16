# ADR-003: LLM-as-Judge with a provider abstraction, not a bespoke judge model

**Status:** Accepted
**Date:** 2026-05-16
**Source:** Design-Doc.md §6.6, §15.3

## Context

Open-ended outputs (summarisation, captioning, reasoning) cannot be reliably
scored with reference-based metrics like BLEU. "LLM-as-Judge" is the current
state-of-the-art workaround: another model rates the output against a rubric.

But judges are not free or stable. Three risks dominate:

1. **Drift.** Foundation-model updates change behavior overnight; yesterday's
   judge scores are not directly comparable to today's.
2. **Bias.** Length bias, position bias, self-preference bias are
   well-documented in the literature.
3. **Cost.** Token spend is a real budget item and is rate-limited by the
   provider.

We have to commit to a strategy: train our own judge, use one external model,
or wrap several behind an abstraction.

## Decision

- **No internally-trained judge model.** Foundation models evolve faster than
  we can re-train a judge; switching cost matters more than peak performance.
- **Provider abstraction.** `JudgeConfigVersion` carries a `judge_model` field
  that the orchestrator hands to the LLM gateway. Swapping providers is a
  config change, not a code change.
- **Calibration harness as a hard gate.** Every judge config version has a
  golden set; promotion requires non-inferiority of Cohen's κ vs. the current
  prod version (§14.3). Drift below the κ floor (0.7) triggers a
  `judge.calibration.drift` webhook and a re-calibration runbook (§13.5).
- **Cache keyed by (model, prompt, rubric, input).** Any version bump produces
  a new key; we never invalidate in place. This guarantees reproducibility
  against a frozen cache (§11.4).
- **Per-project per-minute token budget** enforced at the orchestrator, not
  the worker, so concurrent workers can't blow through it (§6.6 scaling).

## Consequences

- **Engineering effort goes to calibration, prompt versioning, and bias
  measurement** — not judge training.
- **Judge quality is bounded by third-party model quality.** Mitigated by
  the calibration harness, prompt versioning, and (deferred) ensembling.
- **Token spend is now an operational dimension.** Quotas, budgets, and
  off-peak scheduling become real workstreams. We accept this cost.
- **Reproducibility is preserved across judge upgrades** because old runs
  reference a pinned `judge_config_version_id`; replaying writes new judgments
  at the new version without disturbing the old.

## Alternatives considered

1. **Train an internal judge model.** Probably gives best peak agreement on
   one rubric. Loses on every other axis: training cost, model maintenance,
   rubric flexibility, time-to-evaluate-a-new-task.
2. **Use a single external judge model with no abstraction.** Equivalent to
   the chosen approach if you guess right on the model. Locks you in.
3. **Ensemble of judges at launch.** Better expected calibration; doubles
   token cost and makes prompt iteration harder. Deferred to v2 (§16.2 #3).
4. **No judge at all; require human ratings.** Doesn't scale to 10k-example
   runs in <60 min (§10.1 SLO).
