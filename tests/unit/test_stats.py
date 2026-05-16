import numpy as np

from melp.stats.bootstrap import bootstrap_ci, paired_bootstrap_diff
from melp.stats.significance import (
    cohen_kappa,
    krippendorff_alpha,
    paired_permutation_test,
    paired_t_test,
)


def test_bootstrap_ci_contains_point_estimate():
    rng = np.random.default_rng(0)
    x = rng.normal(loc=2.0, scale=0.5, size=200).tolist()
    r = bootstrap_ci(x, n_resamples=500, seed=0)
    assert r.ci_low <= r.point_estimate <= r.ci_high
    assert r.method == "percentile"


def test_paired_bootstrap_diff_zero_when_equal():
    r = paired_bootstrap_diff([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert abs(r.point_estimate) < 1e-9


def test_paired_permutation_detects_lift():
    rng = np.random.default_rng(1)
    a = (rng.normal(1.0, 0.1, 100)).tolist()
    b = (rng.normal(0.5, 0.1, 100)).tolist()
    r = paired_permutation_test(a, b, n_resamples=2_000, seed=1)
    assert r.p_value < 0.05
    assert r.effect_size > 0


def test_paired_t_basic():
    r = paired_t_test([1, 2, 3, 4, 5], [1, 2, 3, 4, 6])
    assert r.method == "paired_t"


def test_cohen_kappa_perfect():
    assert abs(cohen_kappa([0, 1, 2, 1], [0, 1, 2, 1]) - 1.0) < 1e-9


def test_krippendorff_alpha_perfect():
    val = krippendorff_alpha([[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]])
    assert val > 0.99
