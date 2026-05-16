"""S3-compatible object store wrapper. Backed by MinIO in dev, S3 in prod (§7.3)."""
from __future__ import annotations

import hashlib
import io
from functools import lru_cache

import boto3
from botocore.client import Config

from .config import get_settings


@lru_cache(maxsize=1)
def s3():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_buckets() -> None:
    s = get_settings()
    client = s3()
    for bucket in (s.s3_bucket_artifacts, s.s3_bucket_datasets, s.s3_bucket_results):
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            client.create_bucket(Bucket=bucket)


def put_bytes(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload and return the content hash."""
    h = hashlib.sha256(data).hexdigest()
    s3().put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type, Metadata={"sha256": h})
    return h


def get_bytes(bucket: str, key: str) -> bytes:
    return s3().get_object(Bucket=bucket, Key=key)["Body"].read()


def signed_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    return s3().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )


def stream_upload(bucket: str, key: str, stream: io.BufferedReader) -> None:
    s3().upload_fileobj(stream, bucket, key)


def list_keys(bucket: str, prefix: str) -> list[str]:
    paginator = s3().get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            keys.append(obj["Key"])
    return keys
