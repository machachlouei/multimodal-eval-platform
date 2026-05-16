import pytest

from melp.common.ids import id_kind, new_id


def test_new_id_uses_prefix():
    rid = new_id("run")
    assert rid.startswith("run_")
    assert id_kind(rid) == "run"


def test_unknown_kind():
    with pytest.raises(ValueError):
        new_id("nope")
