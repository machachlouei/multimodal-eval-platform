from melp.metrics.base import load_metric
from melp.metrics.registry import BUILTINS, get_builtin


def test_all_builtins_resolve():
    for spec in BUILTINS:
        fn = load_metric(spec.package_uri)
        assert callable(fn), f"{spec.name} did not load"


def test_get_builtin_lookup():
    assert get_builtin("bleu") is not None
    assert get_builtin("nope") is None
