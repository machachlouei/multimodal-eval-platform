"""Centralised config loaded from env. See .env.example for the full surface."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MELP_", env_file=".env", extra="ignore")

    env: str = "dev"
    log_level: str = "INFO"

    db_url: str = "postgresql+psycopg://melp:melp@localhost:5432/melp"
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: str = "melp"
    s3_secret_key: str = "melpmelpmelp"
    s3_bucket_artifacts: str = "melp-artifacts"
    s3_bucket_datasets: str = "melp-datasets"
    s3_bucket_results: str = "melp-results"

    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "melp"

    auth_mode: str = "dev"
    auth_dev_user: str = "dev@example.com"
    auth_oidc_issuer: str = ""
    auth_oidc_client_id: str = ""
    auth_jwt_secret: str = "insecure-dev-secret-change-me"

    llm_gateway_url: str = "http://localhost:9100"
    llm_gateway_token: str = "dev"
    judge_token_budget_per_min: int = 100_000

    port_gateway: int = 8000
    port_authz: int = 8001
    port_run: int = 8010
    port_dataset: int = 8011
    port_model: int = 8012
    port_metric: int = 8013
    port_judge_config: int = 8014
    port_project: int = 8015
    port_audit: int = 8016
    port_aggregator: int = 8017
    port_judge_orch: int = 8018

    # Internal service URLs (override in compose / k8s)
    url_authz: str = Field(default="http://localhost:8001")
    url_run: str = Field(default="http://localhost:8010")
    url_dataset: str = Field(default="http://localhost:8011")
    url_model: str = Field(default="http://localhost:8012")
    url_metric: str = Field(default="http://localhost:8013")
    url_judge_config: str = Field(default="http://localhost:8014")
    url_project: str = Field(default="http://localhost:8015")
    url_audit: str = Field(default="http://localhost:8016")
    url_aggregator: str = Field(default="http://localhost:8017")
    url_judge_orch: str = Field(default="http://localhost:8018")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
