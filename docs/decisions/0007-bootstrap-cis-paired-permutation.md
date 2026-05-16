# ADR-007: Bootstrap confidence intervals by default; paired permutation for significance

**Status:** Accepted
**Date:** 2026-05-16
**Source:** Design-Doc.md §15.7, FR-7

## Context

Every aggregate score reported by MELP must carry a confidence interval
(FR-7). And when a run names a baseline, we must report a paired significance
test against it. The question is *which* CI and *which* test.

Most metrics MELP supports — BLEU, ROUGE, FID, judge scores — have no clean
closed-form distribution of the sample mean. Naive analytical CIs (mean ± 1.96
* SE) are wrong for these. Paired t-tests assume Gaussianity of differences,
which often fails on per-example metric distributions.

Worse: paired samples (same examples evaluated by Model A and Model B) violate
the independence assumption of the unpaired tests teams reach for first. R-6
in the risk register calls this out explicitly.

## Decision

- **Bootstrap CIs by default.** Resample per-example scores with replacement;
  point estimate is the sample statistic on the original; 95% percentile CI
  is the 2.5 / 97.5 quantile of resampled statistics. Default `n_resamples=1000`.
- **BCa variant** available for skewed metrics (FID, perplexity). Implemented
  in [`melp/stats/bootstrap.py`](../../melp/stats/bootstrap.py).
- **Stratified resampling** when a `strata` argument is provided, so slice
  mass is preserved across resamples.
- **Paired permutation test by default** for `baseline_run_id` comparisons.
  Sign-flip the per-example differences `n_resamples=10_000` times; p-value
  is the share of permutations with |mean diff| ≥ observed.
- **Paired t-test offered explicitly** for metrics where the difference
  distribution is plausibly normal and the team prefers a parametric test.

## Consequences

- **Statistical rigor is automatic.** Users don't have to know what test to
  pick; the default is robust and uniform across metrics.
- **~2-4× compute cost** vs. point estimates. Acceptable per the doc's
  tradeoff statement (§1.4); users can opt out for exploratory runs.
- **Reproducibility is preserved.** The resampling RNG is seeded from the
  run's `seed` field, so re-runs produce bit-identical CIs.
- **Effect size is reported alongside p-value** — Cohen's d for paired
  samples. Discourages the "statistically significant but practically
  irrelevant" failure mode.
- **R-6 mitigation is structural.** Defaulting to paired tests on per-example
  differences eliminates the most common "independent t-test on dependent
  samples" error.

## Alternatives considered

1. **Point estimates only.** Cheaper, faster, less honest. The whole reason
   to run an eval is to *decide*; decisions on point estimates without
   uncertainty are how teams ship regressions.
2. **Analytical CIs only.** Works for accuracy / F1 if you squint. Doesn't
   work for BLEU / ROUGE / FID. Mixing methods across metrics would create
   the appearance of comparability without the substance.
3. **Bayesian posterior intervals.** Defensible. Requires a prior choice per
   metric (and per slice) that's hard to defend organisationally. Bootstrap
   is "non-parametric" and easier to justify to a sceptical reviewer.
4. **Bootstrap with bigger `n_resamples`.** We picked 1000 / 10000 as a
   compute-quality knee. Configurable per-run; teams running thousand-example
   judge evals can crank it up at the cost of latency.
