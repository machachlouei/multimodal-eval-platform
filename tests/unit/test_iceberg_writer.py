"""Iceberg writer falls back to JSON when PyIceberg is not configured."""
from unittest.mock import patch


def test_fallback_writes_json(monkeypatch):
    # Force the no-Iceberg path.
    monkeypatch.setenv("MELP_ICEBERG", "off")
    seen: dict[str, bytes] = {}

    def fake_put_bytes(bucket, key, data, content_type):  # noqa: ARG001
        seen[key] = data

    with patch("melp.workers.iceberg_writer.put_bytes", side_effect=fake_put_bytes):
        from melp.workers.iceberg_writer import write_run_results

        target = write_run_results("run_test", [{"x": 1}])
    assert target == "json"
    assert any("aggregate.json" in k for k in seen)
