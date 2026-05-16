"""Built-in metric catalog. Seeds the Metric Registry service at startup.

Adding a metric:
  1. Implement the function in one of the metric modules.
  2. Add a ``MetricSpec`` here.
  3. Provide a unit test (see ``tests/unit/test_metrics_*``).
"""
from __future__ import annotations

from melp.metrics.base import MetricSpec

BUILTINS: list[MetricSpec] = [
    # ----- Classic (Phase 1) -----
    MetricSpec("accuracy", "1.0.0", "python:melp.metrics.classic:accuracy"),
    MetricSpec("exact_match", "1.0.0", "python:melp.metrics.classic:exact_match", predict_type="text", reference_type="text"),
    MetricSpec("precision_macro", "1.0.0", "python:melp.metrics.classic:precision_macro"),
    MetricSpec("recall_macro", "1.0.0", "python:melp.metrics.classic:recall_macro"),
    MetricSpec("f1_macro", "1.0.0", "python:melp.metrics.classic:f1_macro"),
    MetricSpec("f1_micro", "1.0.0", "python:melp.metrics.classic:f1_micro"),
    MetricSpec("f1_weighted", "1.0.0", "python:melp.metrics.classic:f1_weighted"),
    MetricSpec("mse", "1.0.0", "python:melp.metrics.classic:mse", higher_is_better=False),
    MetricSpec("mae", "1.0.0", "python:melp.metrics.classic:mae", higher_is_better=False),
    # ----- Text (Phase 1 + 2) -----
    MetricSpec("bleu", "1.0.0", "python:melp.metrics.text:bleu", predict_type="text", reference_type="text"),
    MetricSpec("rouge_1", "1.0.0", "python:melp.metrics.text:rouge_1", predict_type="text", reference_type="text"),
    MetricSpec("rouge_2", "1.0.0", "python:melp.metrics.text:rouge_2", predict_type="text", reference_type="text"),
    MetricSpec("rouge_l", "1.0.0", "python:melp.metrics.text:rouge_l", predict_type="text", reference_type="text"),
    MetricSpec("meteor", "1.0.0", "python:melp.metrics.text:meteor", predict_type="text", reference_type="text"),
    MetricSpec("semantic_equivalence", "1.0.0", "python:melp.metrics.text:semantic_equivalence", predict_type="text", reference_type="text", needs_judge=True),
    # ----- Probability / calibration (Phase 2) -----
    MetricSpec("auc_roc", "1.0.0", "python:melp.metrics.probability:auc_roc", predict_type="dist"),
    MetricSpec("auc_pr", "1.0.0", "python:melp.metrics.probability:auc_pr", predict_type="dist"),
    MetricSpec("log_loss", "1.0.0", "python:melp.metrics.probability:log_loss", predict_type="dist", higher_is_better=False),
    MetricSpec("ece", "1.0.0", "python:melp.metrics.probability:expected_calibration_error", predict_type="dist", higher_is_better=False),
    MetricSpec("perplexity", "1.0.0", "python:melp.metrics.probability:perplexity", predict_type="dist", higher_is_better=False),
    # ----- Speech (Phase 2) -----
    MetricSpec("wer", "1.0.0", "python:melp.metrics.speech:wer", predict_type="text", reference_type="text", higher_is_better=False),
    MetricSpec("cer", "1.0.0", "python:melp.metrics.speech:cer", predict_type="text", reference_type="text", higher_is_better=False),
    # ----- Vision / multimodal (Phase 2) -----
    MetricSpec("clip_score", "1.0.0", "python:melp.metrics.vision:clip_score", predict_type="image", reference_type="text"),
    MetricSpec("fid", "1.0.0", "python:melp.metrics.vision:fid", predict_type="image", reference_type="image", higher_is_better=False),
    MetricSpec("inception_score", "1.0.0", "python:melp.metrics.vision:inception_score", predict_type="image"),
    MetricSpec("bert_score", "1.0.0", "python:melp.metrics.vision:bert_score", predict_type="text", reference_type="text"),
]


def get_builtin(name: str) -> MetricSpec | None:
    return next((m for m in BUILTINS if m.name == name), None)
