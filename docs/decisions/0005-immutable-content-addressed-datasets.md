# ADR-005: Immutable, content-addressed dataset versions

**Status:** Accepted
**Date:** 2026-05-16
**Source:** Design-Doc.md §6.4, §7, §15.5

## Context

Reproducibility (FR-12) is the platform's highest-value property. A run is a
function of `(model_version, dataset_version, metric_version, judge_config_version, seed)`.
If any of those inputs can mutate after the fact, the function is no longer a
function — yesterday's "0.71 BLEU on dataset Y v1.0" might not reproduce
tomorrow.

The dataset axis is the tricky one. Models and metrics are versioned by code
release; teams already understand "v1.2.3". Datasets are a fuzzier idea —
people add a few examples, fix some labels, reshuffle splits.

## Decision

- **DRAFT → PUBLISHED, one-way.** A `dataset_version` row starts as `DRAFT`
  and becomes `PUBLISHED` via an explicit, audited transition. Published
  versions are **immutable**: no edits, ever.
- **New content = new version.** Even a one-example fix produces a new
  `dataset_version_id`. New versions are cheap (content dedup at the object
  store handles near-duplicates).
- **Content hashing.** Each version carries `content_hash` over its assets +
  manifest. If two versions hash the same, that's a bug in the publisher,
  not in MELP — surface it.
- **Two-phase publish.** Assets land at a `pending/` prefix in the object
  store; the publish step atomically renames + writes the metadata row. If
  the metadata write fails, the version stays `DRAFT` and the assets are
  garbage-collected (§6.4 failure behavior).
- **Slices declared at publish time.** Slice predicates live with the dataset
  version, not the run, so the slice "long videos" means the same thing for
  every run against that version.

## Consequences

- **A run from a year ago re-runs deterministically** as long as the model
  binary still exists. We never lose the ability to bisect a regression.
- **Storage cost for near-duplicates.** Mitigated by object-store dedup; in
  practice dataset-level dedup buys us most of the savings.
- **Cultural friction.** Teams that are used to "I just appended to the
  dataset" have to internalise the version bump. We accept this — it's the
  price of comparability.
- **DRAFT is a real lifecycle stage.** Workers refuse to evaluate DRAFT
  versions; the Run Service rejects them at submission time (FR-3).

## Alternatives considered

1. **Mutable datasets with version tags.** "We'll just be careful." History
   shows this never works: someone fixes a typo and silently invalidates
   every prior evaluation against that dataset.
2. **Copy-on-write at run submission time** (snapshot the dataset into the
   run). Solves reproducibility but explodes storage and breaks dataset-level
   reasoning ("show me every run against caption-toy v0.1.0" becomes
   intractable).
3. **Git-style refs over content-addressed blobs.** Closest to chosen — we
   essentially do this, with the metadata service as the ref store and object
   storage as the blob store. The ADR is just naming it explicitly.
