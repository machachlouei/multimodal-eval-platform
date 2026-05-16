"""Paired significance tests. See FR-7 and §15.7.

Paired permutation is the default (assumption-light); paired t is offered for
metrics where examples are independent and distribution-of-means is plausibly
normal. Both report p-value and effect size (Cohen's d for paired samples).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as sps


@dataclass
class SignificanceResult:
    p_value: float
    effect_size: float
    statistic: float
    method: str


def paired_permutation_test(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_resamples: int = 10_000,
    seed: int = 42,
) -> SignificanceResult:
    """Two-sided paired permutation test on the mean difference."""
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.shape != y.shape:
        raise ValueError("paired samples must be same shape")
    diffs = x - y
    obs = float(diffs.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n_resamples, diffs.size))
    null = (signs * np.abs(diffs)).mean(axis=1)
    p = float((np.abs(null) >= abs(obs)).mean())
    d = float(obs / (diffs.std(ddof=1) + 1e-12))
    return SignificanceResult(p_value=p, effect_size=d, statistic=obs, method="permutation")


def paired_t_test(a: Sequence[float], b: Sequence[float]) -> SignificanceResult:
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    t, p = sps.ttest_rel(x, y)
    d = float((x - y).mean() / ((x - y).std(ddof=1) + 1e-12))
    return SignificanceResult(p_value=float(p), effect_size=d, statistic=float(t), method="paired_t")


def cohen_kappa(a: Sequence[int], b: Sequence[int]) -> float:
    """Cohen's κ for two raters with equal categories. See §6.6 calibration."""
    x = np.asarray(a)
    y = np.asarray(b)
    cats = np.unique(np.concatenate([x, y]))
    po = float((x == y).mean())
    pe = float(sum((x == c).mean() * (y == c).mean() for c in cats))
    return (po - pe) / (1 - pe + 1e-12)


def krippendorff_alpha(ratings: list[list[float]]) -> float:
    """Krippendorff's α for interval data; ``ratings`` is one list per rater.

    All raters must have rated the same items (no missing). For missing values,
    fill the unrated cells with ``np.nan`` (handled by ignoring those pairs).
    """
    a = np.array(ratings, dtype=float)
    n_raters, n_items = a.shape
    pair_diffs: list[float] = []
    for i in range(n_items):
        col = a[:, i]
        valid = col[~np.isnan(col)]
        if len(valid) < 2:
            continue
        for j in range(len(valid)):
            for k in range(j + 1, len(valid)):
                pair_diffs.append((valid[j] - valid[k]) ** 2)
    do = float(np.mean(pair_diffs)) if pair_diffs else 0.0
    flat = a[~np.isnan(a)]
    de = float(((flat[:, None] - flat[None, :]) ** 2).mean()) if flat.size else 0.0
    if de == 0:
        return 1.0
    return 1.0 - do / de
