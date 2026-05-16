"""Bootstrap confidence intervals. Default for every aggregate (§15.7 / FR-7).

Stratified resampling is supported via the ``strata`` argument; when present,
samples are drawn independently within each stratum (preserves slice mass).

The default 2.5 / 97.5 percentile interval is fine for symmetric distributions;
``method="bca"`` selects the bias-corrected and accelerated variant for skewed
metrics (FID, perplexity).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats as sps


@dataclass
class CIResult:
    point_estimate: float
    ci_low: float
    ci_high: float
    method: str
    n_resamples: int


def bootstrap_ci(
    per_example: Sequence[float],
    *,
    statistic: Callable[[np.ndarray], float] = np.mean,
    n_resamples: int = 1000,
    alpha: float = 0.05,
    method: str = "percentile",
    strata: Sequence[int] | None = None,
    seed: int = 42,
) -> CIResult:
    x = np.asarray(per_example, dtype=float)
    if x.size == 0:
        return CIResult(0.0, 0.0, 0.0, method, 0)
    rng = np.random.default_rng(seed)
    if strata is None:
        idx = rng.integers(0, x.size, size=(n_resamples, x.size))
        samples = statistic_axis(x[idx], statistic)
    else:
        s = np.asarray(strata)
        samples = np.empty(n_resamples)
        unique = np.unique(s)
        for r in range(n_resamples):
            picks = []
            for u in unique:
                mask = np.where(s == u)[0]
                picks.append(mask[rng.integers(0, mask.size, size=mask.size)])
            idx = np.concatenate(picks)
            samples[r] = statistic(x[idx])
    point = float(statistic(x))
    if method == "percentile":
        lo, hi = np.percentile(samples, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    elif method == "bca":
        z0 = sps.norm.ppf((samples < point).mean() or 1 / (n_resamples + 1))
        jackknife = np.array([statistic(np.delete(x, i)) for i in range(x.size)])
        jack_mean = jackknife.mean()
        num = ((jack_mean - jackknife) ** 3).sum()
        den = 6 * (((jack_mean - jackknife) ** 2).sum() ** 1.5 + 1e-12)
        a = num / den
        z_a = sps.norm.ppf(alpha / 2)
        z_1a = sps.norm.ppf(1 - alpha / 2)
        a1 = sps.norm.cdf(z0 + (z0 + z_a) / (1 - a * (z0 + z_a)))
        a2 = sps.norm.cdf(z0 + (z0 + z_1a) / (1 - a * (z0 + z_1a)))
        lo, hi = np.percentile(samples, [100 * a1, 100 * a2])
    else:
        raise ValueError(f"unknown CI method: {method}")
    return CIResult(point, float(lo), float(hi), method, n_resamples)


def statistic_axis(arr: np.ndarray, fn: Callable[[np.ndarray], float]) -> np.ndarray:
    """Apply ``fn`` to each row of ``arr``."""
    if fn is np.mean:
        return arr.mean(axis=1)
    if fn is np.median:
        return np.median(arr, axis=1)
    return np.array([fn(row) for row in arr])


def paired_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> CIResult:
    """CI on the *paired* difference (a_i - b_i). Implements §15.7's paired bootstrap."""
    x = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    return bootstrap_ci(x.tolist(), n_resamples=n_resamples, alpha=alpha, seed=seed)
