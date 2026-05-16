"""Vision metrics: CLIPScore, FID, Inception Score, BERTScore.

These wrap heavy models in real life (§6.5). In this reference codebase they
are implemented as stable, deterministic stubs that consume pre-computed
features in the input dict; teams running real evals would substitute a
package_uri pointing at the actual model wrapper.

Input convention:
  predictions: list of dicts ``{"image_features": np.ndarray, "text": str?}``
  references : list of dicts ``{"image_features": np.ndarray, "text": str?}``
  (For BERTScore: ``{"embedding": np.ndarray}`` per item.)
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from melp.metrics.base import MetricResult


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def clip_score(predictions: Sequence[dict], references: Sequence[dict] | None = None, **_: object) -> MetricResult:
    """Mean cosine similarity between image_features and text_features.

    Real CLIPScore would call a CLIP model to embed the text; here we assume
    upstream has produced ``text_features`` alongside ``image_features``.
    """
    per: list[float] = []
    for item in predictions:
        img = np.asarray(item["image_features"], dtype=float)
        txt = np.asarray(item["text_features"], dtype=float)
        per.append(max(0.0, _cos(img, txt)))
    return MetricResult(aggregate=float(np.mean(per)) if per else 0.0, per_example=per, n=len(per))


def fid(predictions: Sequence[dict], references: Sequence[dict], **_: object) -> MetricResult:
    """Approximate Fréchet distance between two feature distributions.

    The doc-grade FID uses Inception-v3 pool features; we accept arbitrary
    pre-computed features in ``image_features`` and compute Fréchet on them.
    """
    P = np.array([item["image_features"] for item in predictions], dtype=float)
    R = np.array([item["image_features"] for item in references], dtype=float)
    if P.size == 0 or R.size == 0:
        return MetricResult(aggregate=float("nan"), n=0)
    mu_p, mu_r = P.mean(axis=0), R.mean(axis=0)
    cov_p = np.cov(P, rowvar=False) + 1e-6 * np.eye(P.shape[1])
    cov_r = np.cov(R, rowvar=False) + 1e-6 * np.eye(R.shape[1])
    diff = mu_p - mu_r
    # Approximation: trace(C_p + C_r - 2 (C_p C_r)^{1/2})
    eigvals = np.linalg.eigvals(cov_p @ cov_r).real.clip(min=0)
    fid_val = float(diff @ diff + np.trace(cov_p + cov_r) - 2 * np.sum(np.sqrt(eigvals)))
    return MetricResult(aggregate=float(max(0.0, fid_val)), n=len(P))


def inception_score(predictions: Sequence[dict], references: Sequence[dict] | None = None, **_: object) -> MetricResult:
    """Inception Score given per-example class-probability distributions.

    Expects predictions[i]["probs"] -- a class distribution (sums to 1).
    """
    P = np.array([item["probs"] for item in predictions], dtype=float)
    if P.size == 0:
        return MetricResult(aggregate=float("nan"), n=0)
    py = P.mean(axis=0, keepdims=True)
    kl = (P * (np.log(P + 1e-12) - np.log(py + 1e-12))).sum(axis=1)
    return MetricResult(aggregate=float(np.exp(kl.mean())), per_example=kl.tolist(), n=len(P))


def bert_score(predictions: Sequence[dict], references: Sequence[dict], **_: object) -> MetricResult:
    """Cosine similarity between provided sentence embeddings.

    Real BERTScore is token-level; this is a sentence-level approximation that
    works whenever the upstream pipeline produces ``embedding`` vectors.
    """
    per: list[float] = []
    for p, r in zip(predictions, references, strict=True):
        per.append(_cos(np.asarray(p["embedding"], dtype=float), np.asarray(r["embedding"], dtype=float)))
    return MetricResult(aggregate=float(np.mean(per)) if per else 0.0, per_example=per, n=len(per))
