"""Probabilistic / calibration metrics: AUC-ROC, AUC-PR, log loss, ECE, perplexity."""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from melp.metrics.base import MetricResult


def auc_roc(predictions: Sequence[float], references: Sequence[int], **_: object) -> MetricResult:
    p = np.array(predictions, dtype=float)
    y = np.array(references, dtype=int)
    pos = (y == 1).sum()
    neg = (y == 0).sum()
    if pos == 0 or neg == 0:
        return MetricResult(aggregate=float("nan"), n=len(y))
    order = np.argsort(p)
    ranks = np.empty_like(order, dtype=float)
    # Average tied ranks.
    sorted_p = p[order]
    i = 0
    while i < len(sorted_p):
        j = i
        while j + 1 < len(sorted_p) and sorted_p[j + 1] == sorted_p[i]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-indexed
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    sum_ranks_pos = ranks[y == 1].sum()
    auc = (sum_ranks_pos - pos * (pos + 1) / 2) / (pos * neg)
    return MetricResult(aggregate=float(auc), n=len(y))


def auc_pr(predictions: Sequence[float], references: Sequence[int], **_: object) -> MetricResult:
    p = np.array(predictions, dtype=float)
    y = np.array(references, dtype=int)
    order = np.argsort(-p)
    y_sorted = y[order]
    tp = np.cumsum(y_sorted == 1)
    fp = np.cumsum(y_sorted == 0)
    total_pos = (y == 1).sum()
    if total_pos == 0:
        return MetricResult(aggregate=float("nan"), n=len(y))
    precision = tp / (tp + fp + 1e-12)
    recall = tp / total_pos
    # Average precision: AP = Σ (r_i - r_{i-1}) * p_i  (step interpretation, sklearn-compatible).
    prev_recall = 0.0
    ap = 0.0
    for p_i, r_i in zip(precision, recall, strict=True):
        ap += (r_i - prev_recall) * p_i
        prev_recall = r_i
    return MetricResult(aggregate=float(ap), n=len(y))


def log_loss(predictions: Sequence[float], references: Sequence[int], eps: float = 1e-15, **_: object) -> MetricResult:
    p = np.clip(np.array(predictions, dtype=float), eps, 1 - eps)
    y = np.array(references, dtype=float)
    per = -(y * np.log(p) + (1 - y) * np.log(1 - p))
    return MetricResult(aggregate=float(per.mean()) if per.size else 0.0, per_example=per.tolist(), n=int(per.size))


def expected_calibration_error(
    predictions: Sequence[float],
    references: Sequence[int],
    n_bins: int = 10,
    **_: object,
) -> MetricResult:
    p = np.array(predictions, dtype=float)
    y = np.array(references, dtype=int)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(p)
    for i in range(n_bins):
        mask = (p >= bins[i]) & (p < bins[i + 1] if i < n_bins - 1 else p <= bins[i + 1])
        if mask.sum() == 0:
            continue
        conf = p[mask].mean()
        acc = (y[mask] == 1).mean()
        ece += abs(conf - acc) * mask.sum() / n
    return MetricResult(aggregate=float(ece), n=n)


def perplexity(predictions: Sequence[float], references: Sequence[int] | None = None, **_: object) -> MetricResult:
    """Expects per-token log-probabilities in ``predictions``."""
    logp = np.array(predictions, dtype=float)
    if logp.size == 0:
        return MetricResult(aggregate=float("nan"), n=0)
    avg_logp = logp.mean()
    return MetricResult(aggregate=float(math.exp(-avg_logp)), n=int(logp.size))
