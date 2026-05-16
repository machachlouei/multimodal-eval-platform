"""Speech metrics: WER, CER. Implements Levenshtein-based scoring."""
from __future__ import annotations

import re
from collections.abc import Sequence

from melp.metrics.base import MetricResult


def _edit_distance(a: list[str], b: list[str]) -> int:
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            cur = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j - 1], dp[j])
            prev = cur
    return dp[n]


def _words(s: str) -> list[str]:
    return re.findall(r"\S+", str(s).lower())


def wer(predictions: Sequence[str], references: Sequence[str], **_: object) -> MetricResult:
    per: list[float] = []
    for pred, ref in zip(predictions, references, strict=True):
        rw = _words(ref)
        pw = _words(pred)
        if not rw:
            per.append(0.0 if not pw else 1.0)
            continue
        per.append(_edit_distance(rw, pw) / len(rw))
    return MetricResult(aggregate=float(sum(per) / len(per)) if per else 0.0, per_example=per, n=len(per))


def cer(predictions: Sequence[str], references: Sequence[str], **_: object) -> MetricResult:
    per: list[float] = []
    for pred, ref in zip(predictions, references, strict=True):
        rc = list(str(ref))
        pc = list(str(pred))
        if not rc:
            per.append(0.0 if not pc else 1.0)
            continue
        per.append(_edit_distance(rc, pc) / len(rc))
    return MetricResult(aggregate=float(sum(per) / len(per)) if per else 0.0, per_example=per, n=len(per))
