"""Smoke test for the gateway: it imports and /healthz responds.

Real integration tests need Postgres + Redis up; covered in tests/integration.
"""
from fastapi.testclient import TestClient

from melp.services.gateway.app import app


def test_healthz_ok():
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.text == "ok"


def test_root_returns_service_info():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "melp"


def test_openapi_documents_routes():
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    paths = set(spec["paths"].keys())
    assert any(p.startswith("/v1/projects") for p in paths)
    assert any("/runs" in p for p in paths)
    assert "/v1/metrics" in paths
