import math

from melp.metrics.probability import (
    auc_pr,
    auc_roc,
    expected_calibration_error,
    log_loss,
    perplexity,
)


def test_auc_roc_perfect():
    r = auc_roc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])
    assert r.aggregate == 1.0


def test_auc_roc_random():
    r = auc_roc([0.5] * 4, [0, 1, 0, 1])
    assert abs(r.aggregate - 0.5) < 1e-6


def test_auc_pr_nondecreasing():
    r = auc_pr([0.1, 0.5, 0.9, 0.95], [0, 0, 1, 1])
    assert r.aggregate > 0.5


def test_log_loss_perfect():
    r = log_loss([0.99, 0.01], [1, 0])
    assert r.aggregate < 0.05


def test_ece_perfectly_calibrated():
    r = expected_calibration_error([0.1, 0.9], [0, 1])
    assert r.aggregate < 0.2


def test_perplexity_uniform():
    # log p = log 0.5 → perplexity = 2
    r = perplexity([math.log(0.5)] * 8)
    assert abs(r.aggregate - 2.0) < 1e-6
