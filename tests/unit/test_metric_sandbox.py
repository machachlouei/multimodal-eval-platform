"""Sandbox round-trip — same answer as in-process call (closes ADR-011)."""
import os

import pytest

from melp.metrics.sandbox import run_metric_in_sandbox


def test_sandbox_roundtrip_accuracy():
    out = run_metric_in_sandbox(
        "python:melp.metrics.classic:accuracy",
        [1, 0, 1, 1],
        [1, 1, 1, 0],
    )
    assert out.aggregate == 0.5
    assert out.n == 4


def test_sandbox_bleu_per_example_preserved():
    out = run_metric_in_sandbox(
        "python:melp.metrics.text:bleu",
        ["the cat sat on the mat"],
        ["the cat sat on the mat"],
    )
    assert out.aggregate > 0.99
    assert len(out.per_example) == 1


def test_sandbox_fallback_in_process(monkeypatch):
    monkeypatch.setenv("MELP_METRIC_SANDBOX", "0")
    out = run_metric_in_sandbox(
        "python:melp.metrics.classic:accuracy",
        [1, 1],
        [1, 0],
    )
    assert out.aggregate == 0.5


def test_sandbox_propagates_metric_error():
    with pytest.raises(RuntimeError):
        run_metric_in_sandbox(
            "python:melp.metrics.classic:accuracy",
            [1, 0],
            [1, 0, 1],  # length mismatch → raises in child
        )
