"""Classic ML metrics (Phase 1)."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from melp.metrics.base import MetricResult


def _binarise(y: Sequence[int | float | str]) -> np.ndarray:
    return np.array(list(y))


def accuracy(predictions: Sequence, references: Sequence, **_: object) -> MetricResult:
    p = _binarise(predictions)
    r = _binarise(references)
    if len(p) != len(r):
        raise ValueError("predictions and references must be same length")
    correct = (p == r).astype(float)
    return MetricResult(aggregate=float(correct.mean()) if len(correct) else 0.0, per_example=correct.tolist(), n=len(correct))


def exact_match(predictions: Sequence[str], references: Sequence[str], **_: object) -> MetricResult:
    p = [str(x).strip() for x in predictions]
    r = [str(x).strip() for x in references]
    if len(p) != len(r):
        raise ValueError("length mismatch")
    per = [float(a == b) for a, b in zip(p, r, strict=True)]
    return MetricResult(aggregate=float(np.mean(per)) if per else 0.0, per_example=per, n=len(per))


def _confusion(p: np.ndarray, r: np.ndarray, classes: np.ndarray) -> dict[str, np.ndarray]:
    tp = np.array([np.sum((p == c) & (r == c)) for c in classes], dtype=float)
    fp = np.array([np.sum((p == c) & (r != c)) for c in classes], dtype=float)
    fn = np.array([np.sum((p != c) & (r == c)) for c in classes], dtype=float)
    return {"tp": tp, "fp": fp, "fn": fn}


def _prf(p: np.ndarray, r: np.ndarray, average: str = "macro") -> dict[str, float]:
    classes = np.unique(np.concatenate([p, r]))
    cm = _confusion(p, r, classes)
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]
    with np.errstate(divide="ignore", invalid="ignore"):
        prec = np.where(tp + fp > 0, tp / (tp + fp), 0.0)
        rec = np.where(tp + fn > 0, tp / (tp + fn), 0.0)
        f1 = np.where(prec + rec > 0, 2 * prec * rec / (prec + rec), 0.0)
    if average == "micro":
        TP, FP, FN = tp.sum(), fp.sum(), fn.sum()
        P = TP / (TP + FP) if (TP + FP) else 0.0
        R = TP / (TP + FN) if (TP + FN) else 0.0
        F = 2 * P * R / (P + R) if (P + R) else 0.0
        return {"precision": float(P), "recall": float(R), "f1": float(F)}
    if average == "weighted":
        support = np.array([np.sum(r == c) for c in classes], dtype=float)
        w = support / support.sum() if support.sum() else np.zeros_like(support)
        return {
            "precision": float((prec * w).sum()),
            "recall": float((rec * w).sum()),
            "f1": float((f1 * w).sum()),
        }
    # macro
    return {"precision": float(prec.mean()), "recall": float(rec.mean()), "f1": float(f1.mean())}


def precision_macro(predictions, references, **_):
    return MetricResult(aggregate=_prf(_binarise(predictions), _binarise(references), "macro")["precision"], n=len(predictions))


def recall_macro(predictions, references, **_):
    return MetricResult(aggregate=_prf(_binarise(predictions), _binarise(references), "macro")["recall"], n=len(predictions))


def f1_macro(predictions, references, **_):
    return MetricResult(aggregate=_prf(_binarise(predictions), _binarise(references), "macro")["f1"], n=len(predictions))


def f1_micro(predictions, references, **_):
    return MetricResult(aggregate=_prf(_binarise(predictions), _binarise(references), "micro")["f1"], n=len(predictions))


def f1_weighted(predictions, references, **_):
    return MetricResult(aggregate=_prf(_binarise(predictions), _binarise(references), "weighted")["f1"], n=len(predictions))


def mse(predictions: Sequence[float], references: Sequence[float], **_: object) -> MetricResult:
    p = np.array(predictions, dtype=float)
    r = np.array(references, dtype=float)
    per = (p - r) ** 2
    return MetricResult(aggregate=float(per.mean()) if per.size else 0.0, per_example=per.tolist(), n=int(per.size))


def mae(predictions: Sequence[float], references: Sequence[float], **_: object) -> MetricResult:
    p = np.array(predictions, dtype=float)
    r = np.array(references, dtype=float)
    per = np.abs(p - r)
    return MetricResult(aggregate=float(per.mean()) if per.size else 0.0, per_example=per.tolist(), n=int(per.size))
