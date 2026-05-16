"""Python SDK. Wraps the REST API behind ergonomic helpers (FR-10).

Example::

    from melp.sdk import MELPClient
    c = MELPClient("http://localhost:8000")
    project = c.create_project("vision-quality")
    run = c.submit_run(
        project="vision-quality",
        model_version_id="mdv_...",
        dataset_version_id="dsv_...",
        metric_version_ids=["mtv_..."],
    )
    print(c.wait_for_run(project, run["id"]))
"""
from __future__ import annotations

import os
import time
from typing import Any
from uuid import uuid4

import httpx


class MELPClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("MELP_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.token = token or os.environ.get("MELP_TOKEN")
        self.http = httpx.Client(timeout=timeout)

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if idempotency_key:
            h["Idempotency-Key"] = idempotency_key
        return h

    def _request(self, method: str, path: str, **kw: Any) -> Any:
        r = self.http.request(method, f"{self.base_url}{path}", **kw)
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise RuntimeError(f"{r.status_code} {method} {path}: {detail}")
        if r.status_code == 204 or not r.content:
            return None
        return r.json()

    # ---------- projects ----------
    def create_project(self, name: str, description: str = "") -> dict:
        return self._request(
            "POST", "/v1/projects", json={"name": name, "description": description}, headers=self._headers()
        )

    def list_projects(self) -> list[dict]:
        return self._request("GET", "/v1/projects", headers=self._headers())

    # ---------- datasets ----------
    def create_dataset(self, project: str, name: str, classification: str = "internal") -> dict:
        return self._request(
            "POST", f"/v1/projects/{project}/datasets",
            json={"name": name, "classification": classification},
            headers=self._headers(),
        )

    def create_dataset_version(
        self,
        project: str,
        dataset_id: str,
        *,
        version: str,
        asset_root_uri: str,
        record_count: int = 0,
        slices: list[dict] | None = None,
    ) -> dict:
        return self._request(
            "POST", f"/v1/projects/{project}/datasets/{dataset_id}/versions",
            json={
                "version": version,
                "asset_root_uri": asset_root_uri,
                "record_count": record_count,
                "slices": slices or [],
            },
            headers=self._headers(),
        )

    def publish_dataset_version(self, project: str, dataset_id: str, version_id: str) -> dict:
        return self._request(
            "PUT", f"/v1/projects/{project}/datasets/{dataset_id}/versions/{version_id}/publish",
            headers=self._headers(),
        )

    # ---------- models ----------
    def register_model(self, project: str, name: str) -> dict:
        return self._request(
            "POST", f"/v1/projects/{project}/models", json={"name": name}, headers=self._headers()
        )

    def register_model_version(
        self,
        project: str,
        model_id: str,
        *,
        version: str,
        uri: str,
        backend: str = "echo",
        config: dict | None = None,
    ) -> dict:
        return self._request(
            "POST", f"/v1/projects/{project}/models/{model_id}/versions",
            json={"version": version, "uri": uri, "backend": backend, "config": config or {}},
            headers=self._headers(),
        )

    # ---------- metrics ----------
    def list_metrics(self) -> list[dict]:
        return self._request("GET", "/v1/metrics", headers=self._headers())

    # ---------- runs ----------
    def submit_run(
        self,
        project: str,
        *,
        model_version_id: str,
        dataset_version_id: str,
        metric_version_ids: list[str],
        judge_config_version_id: str | None = None,
        slice_set: list[str] | None = None,
        baseline_run_id: str | None = None,
        seed: int = 42,
        priority: str = "normal",
        name: str = "",
        idempotency_key: str | None = None,
    ) -> dict:
        key = idempotency_key or f"sdk-{uuid4().hex}"
        return self._request(
            "POST", f"/v1/projects/{project}/runs",
            json={
                "name": name,
                "model_version_id": model_version_id,
                "dataset_version_id": dataset_version_id,
                "metric_version_ids": metric_version_ids,
                "judge_config_version_id": judge_config_version_id,
                "slice_set": slice_set or [],
                "baseline_run_id": baseline_run_id,
                "seed": seed,
                "priority": priority,
            },
            headers=self._headers(idempotency_key=key),
        )

    def get_run(self, project: str, run_id: str) -> dict:
        return self._request("GET", f"/v1/projects/{project}/runs/{run_id}", headers=self._headers())

    def list_runs(self, project: str, status: str | None = None) -> list[dict]:
        params = {"status": status} if status else None
        return self._request(
            "GET", f"/v1/projects/{project}/runs", params=params, headers=self._headers()
        )

    def cancel_run(self, project: str, run_id: str) -> dict:
        return self._request(
            "POST", f"/v1/projects/{project}/runs/{run_id}/cancel", headers=self._headers()
        )

    def wait_for_run(
        self,
        project: str,
        run_id: str,
        *,
        terminal: tuple[str, ...] = ("COMPLETED", "FAILED", "CANCELLED", "PARTIAL"),
        poll_interval_s: float = 2.0,
        timeout_s: float = 600.0,
    ) -> dict:
        t0 = time.time()
        while True:
            r = self.get_run(project, run_id)
            if r["status"] in terminal:
                return r
            if time.time() - t0 > timeout_s:
                raise TimeoutError(f"run {run_id} did not finish within {timeout_s}s")
            time.sleep(poll_interval_s)

    def leaderboard(self, project: str, metric_version_id: str, limit: int = 20) -> list[dict]:
        return self._request(
            "GET", f"/v1/projects/{project}/runs/leaderboard/{metric_version_id}",
            params={"limit": limit}, headers=self._headers(),
        )
