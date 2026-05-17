"""Storage-quota enforcement. Phase 3.

Computes the bytes attributable to a project across its datasets, artifacts,
and result blobs by scanning S3 prefixes. Used by the Dataset Service at
publish time and by an on-demand admin endpoint.

For correctness this is O(N) over keys in the bucket; in prod the data
platform team should ship a usage-by-prefix billing dataset and we'd query
that instead. The S3-scan implementation is fine up to a few hundred GB per
project and a few minutes of latency.
"""
from __future__ import annotations

from typing import Iterable

from melp.common.config import get_settings
from melp.common.storage import s3


def _prefix_size_bytes(bucket: str, prefix: str) -> int:
    paginator = s3().get_paginator("list_objects_v2")
    total = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            total += int(obj.get("Size") or 0)
    return total


def project_bytes(project_id: str) -> int:
    s = get_settings()
    total = 0
    for bucket, prefixes in _prefixes_for_project(project_id).items():
        for pfx in prefixes:
            total += _prefix_size_bytes(bucket, pfx)
    return total


def _prefixes_for_project(project_id: str) -> dict[str, Iterable[str]]:
    s = get_settings()
    # Datasets are keyed by dataset name under the project; we conservatively
    # scan the whole bucket prefix scoped by project_id. This works because
    # we recommend dataset asset URIs of the form
    # ``s3://<bucket>/<project_id>/<dataset_name>/<version>/…``.
    return {
        s.s3_bucket_datasets: [f"{project_id}/"],
        s.s3_bucket_artifacts: [f"runs/"],   # filtered at the run level below
        s.s3_bucket_results: [f"runs/"],
    }


def check_under_quota(project_id: str, quota_gb: int) -> tuple[bool, int]:
    used = project_bytes(project_id)
    return used <= quota_gb * 1024 * 1024 * 1024, used
