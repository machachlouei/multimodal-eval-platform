"""Built-in metric implementations. See §6.5.

Every metric is a small pure function plus a ``MetricSpec``. The metric registry
service catalogs them by ``package_uri`` (``python:melp.metrics.classic:accuracy``).
At evaluation time the worker imports and calls the function.
"""
from melp.metrics.base import MetricResult, MetricSpec, load_metric  # noqa: F401
