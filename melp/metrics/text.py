"""Text generation metrics. BLEU, ROUGE-{1,2,L}, METEOR, semantic equivalence."""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from melp.metrics.base import MetricResult


def _tokens(s: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", str(s).lower(), re.UNICODE)


# ---------- BLEU (corpus-level, smoothed) ----------
def _modified_precision(refs: list[list[str]], hyp: list[str], n: int) -> tuple[int, int]:
    if len(hyp) < n:
        return 0, 0
    hyp_ngrams = Counter(tuple(hyp[i : i + n]) for i in range(len(hyp) - n + 1))
    max_ref_ngrams: Counter = Counter()
    for ref in refs:
        ref_ngrams = Counter(tuple(ref[i : i + n]) for i in range(len(ref) - n + 1))
        for ng, c in ref_ngrams.items():
            max_ref_ngrams[ng] = max(max_ref_ngrams[ng], c)
    clipped = sum(min(c, max_ref_ngrams[ng]) for ng, c in hyp_ngrams.items())
    total = max(1, sum(hyp_ngrams.values()))
    return clipped, total


def bleu(predictions: Sequence[str], references: Sequence[str | list[str]], **_: object) -> MetricResult:
    """Corpus BLEU-4 with add-1 smoothing. References may be a string or list of strings (multi-ref)."""
    if len(predictions) != len(references):
        raise ValueError("length mismatch")
    per_example: list[float] = []
    weights = [0.25] * 4
    total_clipped = [0] * 4
    total_n = [0] * 4
    hyp_lens, ref_lens = 0, 0
    for pred, ref in zip(predictions, references, strict=True):
        ref_tokens = [_tokens(r) for r in (ref if isinstance(ref, list) else [ref])]
        hyp_tokens = _tokens(pred)
        hyp_lens += len(hyp_tokens)
        ref_lens += min((abs(len(r) - len(hyp_tokens)), len(r)) for r in ref_tokens)[1]
        # Per-example score for bootstrap.
        ex_logs = []
        for n in range(1, 5):
            c, t = _modified_precision(ref_tokens, hyp_tokens, n)
            total_clipped[n - 1] += c
            total_n[n - 1] += t
            ex_logs.append(math.log((c + 1) / (t + 1)))
        ex_bleu = math.exp(sum(w * l for w, l in zip(weights, ex_logs, strict=True)))
        bp = 1.0
        if hyp_tokens:
            ref_len = min(len(r) for r in ref_tokens)
            if len(hyp_tokens) <= ref_len and ref_len > 0:
                bp = math.exp(1 - ref_len / len(hyp_tokens))
        per_example.append(float(ex_bleu * bp))
    # Corpus-level.
    log_p = sum(
        w * math.log((c + 1) / (t + 1)) for w, c, t in zip(weights, total_clipped, total_n, strict=True)
    )
    bp = 1.0 if hyp_lens > ref_lens else (math.exp(1 - ref_lens / max(1, hyp_lens)))
    corpus_bleu = bp * math.exp(log_p)
    return MetricResult(aggregate=float(corpus_bleu), per_example=per_example, n=len(per_example))


# ---------- ROUGE ----------
def _lcs_length(a: list[str], b: list[str]) -> int:
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n]


def _rouge_n(pred: list[str], ref: list[str], n: int) -> float:
    if len(pred) < n or len(ref) < n:
        return 0.0
    p_ng = Counter(tuple(pred[i : i + n]) for i in range(len(pred) - n + 1))
    r_ng = Counter(tuple(ref[i : i + n]) for i in range(len(ref) - n + 1))
    overlap = sum((p_ng & r_ng).values())
    return overlap / max(1, sum(r_ng.values()))


def rouge_1(predictions, references, **_):
    per = [
        _rouge_n(_tokens(p), _tokens(r if isinstance(r, str) else r[0]), 1)
        for p, r in zip(predictions, references, strict=True)
    ]
    return MetricResult(aggregate=float(sum(per) / len(per)) if per else 0.0, per_example=per, n=len(per))


def rouge_2(predictions, references, **_):
    per = [
        _rouge_n(_tokens(p), _tokens(r if isinstance(r, str) else r[0]), 2)
        for p, r in zip(predictions, references, strict=True)
    ]
    return MetricResult(aggregate=float(sum(per) / len(per)) if per else 0.0, per_example=per, n=len(per))


def rouge_l(predictions: Sequence[str], references: Sequence[str | list[str]], **_: object) -> MetricResult:
    per: list[float] = []
    for pred, ref in zip(predictions, references, strict=True):
        ref_s = ref if isinstance(ref, str) else (ref[0] if ref else "")
        p_tok = _tokens(pred)
        r_tok = _tokens(ref_s)
        lcs = _lcs_length(p_tok, r_tok)
        precision = lcs / len(p_tok) if p_tok else 0.0
        recall = lcs / len(r_tok) if r_tok else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per.append(f1)
    return MetricResult(aggregate=float(sum(per) / len(per)) if per else 0.0, per_example=per, n=len(per))


def meteor(predictions, references, **_):
    """Approximate METEOR using unigram overlap with stemming-lite (lowercase only).

    Real METEOR uses WordNet/synonyms; this is a workable approximation suitable
    for a registry default. Teams wanting full METEOR can register their own
    package_uri pointing at a richer implementation.
    """
    per: list[float] = []
    for pred, ref in zip(predictions, references, strict=True):
        ref_s = ref if isinstance(ref, str) else (ref[0] if ref else "")
        p_tok = set(_tokens(pred))
        r_tok = set(_tokens(ref_s))
        if not p_tok or not r_tok:
            per.append(0.0)
            continue
        inter = p_tok & r_tok
        precision = len(inter) / len(p_tok)
        recall = len(inter) / len(r_tok)
        f = 10 * precision * recall / (recall + 9 * precision) if (recall + 9 * precision) else 0.0
        per.append(float(f))
    return MetricResult(aggregate=float(sum(per) / len(per)) if per else 0.0, per_example=per, n=len(per))


def semantic_equivalence(predictions, references, judge_scores=None, **_):
    """Judge-based metric: expects per-example {0,1} or [0,1] from the judge plane.

    This metric is intentionally a thin aggregator. The judge orchestrator is
    responsible for the actual LLM calls and emits ``judge_scores`` alongside.
    """
    if judge_scores is None:
        raise ValueError("semantic_equivalence requires judge_scores from the judge plane")
    per = [float(s) for s in judge_scores]
    return MetricResult(aggregate=float(sum(per) / len(per)) if per else 0.0, per_example=per, n=len(per))
