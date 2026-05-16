"""Pydantic v2 schemas — request/response types for every public endpoint.

Names mirror the SQL model where they overlap; nested schemas suffix ``Read`` for
output, ``Create`` for inputs, ``Update`` for partial updates.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- shared ----------
class ProblemDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = []
    request_id: str = ""


class PageInfo(BaseModel):
    next_page_token: str | None = None


# ---------- projects ----------
class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    quota_storage_gb: int = 100
    quota_run_concurrency: int = 10
    quota_judge_tokens_per_day: int = 10_000_000


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    quota_storage_gb: int
    quota_run_concurrency: int
    quota_judge_tokens_per_day: int
    created_at: datetime


class MembershipCreate(BaseModel):
    user_email: str
    role: Literal["viewer", "contributor", "maintainer", "owner"]


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    user_id: str
    role: str


# ---------- datasets ----------
class SliceDefCreate(BaseModel):
    name: str
    predicate: str
    description: str = ""


class SliceDefRead(SliceDefCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dataset_version_id: str


class DatasetCreate(BaseModel):
    name: str
    description: str = ""
    classification: str = "internal"


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    name: str
    description: str
    classification: str


class DatasetVersionCreate(BaseModel):
    version: str
    asset_root_uri: str
    schema_uri: str = ""
    record_count: int = 0
    classification: str | None = None
    slices: list[SliceDefCreate] = []


class DatasetVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dataset_id: str
    version: str
    content_hash: str
    schema_uri: str
    asset_root_uri: str
    record_count: int
    classification: str
    status: str
    published_at: datetime | None


# ---------- models ----------
class ModelCreate(BaseModel):
    name: str
    description: str = ""


class ModelVersionCreate(BaseModel):
    version: str
    uri: str
    backend: Literal["echo", "http", "registry"] = "echo"
    config: dict[str, Any] = {}


class ModelVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    model_id: str
    version: str
    uri: str
    backend: str


# ---------- metrics ----------
class MetricCreate(BaseModel):
    name: str
    description: str = ""


class MetricVersionCreate(BaseModel):
    version: str
    package_uri: str  # python:module.submodule:callable
    signature: dict[str, Any] = {}


class MetricVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    metric_id: str
    version: str
    package_uri: str
    signature: dict[str, Any]
    tests_passed_at: datetime | None


# ---------- judges ----------
class PromptVersionCreate(BaseModel):
    template: str
    version: str
    output_schema: dict[str, Any] = {}


class PromptVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    prompt_id: str
    version: str
    template: str
    output_schema: dict[str, Any]


class JudgeConfigCreate(BaseModel):
    name: str
    description: str = ""


class JudgeConfigVersionCreate(BaseModel):
    version: str
    judge_model: str
    prompt_version_id: str
    rubric: dict[str, Any] = {}
    ensembling: dict[str, Any] = {}
    calibration_set_uri: str = ""


class JudgeConfigVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    judge_config_id: str
    version: str
    judge_model: str
    prompt_version_id: str
    rubric: dict[str, Any]
    ensembling: dict[str, Any]


# ---------- runs ----------
class RunCreate(BaseModel):
    name: str = ""
    model_version_id: str
    dataset_version_id: str
    metric_version_ids: list[str]
    judge_config_version_id: str | None = None
    slice_set: list[str] = []
    seed: int = 42
    priority: Literal["low", "normal", "high"] = "normal"
    baseline_run_id: str | None = None


class RunResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    metric_version_id: str
    slice_def_id: str | None
    point_estimate: float
    ci_low: float | None
    ci_high: float | None
    ci_method: str | None
    n_examples: int
    p_value: float | None
    effect_size: float | None


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    name: str
    model_version_id: str
    dataset_version_id: str
    metric_version_ids: list[str]
    judge_config_version_id: str | None
    seed: int
    priority: str
    baseline_run_id: str | None
    status: str
    progress: dict[str, Any]
    error: str | None
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    results: list[RunResultRead] = []


# ---------- webhooks ----------
class WebhookSubscriptionCreate(BaseModel):
    url: str
    events: list[str] = Field(
        default_factory=lambda: ["run.queued", "run.started", "run.completed", "run.failed"]
    )


class WebhookSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    url: str
    events: list[str]
    active: bool
    secret: str  # returned only on create
