"""SQLAlchemy ORM models. Mirrors §7.2 logical data model.

Tables present (Phase 1 + Phase 2):
  project, user, membership, audit_log,
  dataset, dataset_version, slice_def,
  model, model_version,
  metric, metric_version,
  judge_config, judge_config_version, prompt, prompt_version,
  run, run_result, judgment,
  webhook_subscription, webhook_delivery,
  calibration_run.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


# ---------- Identity & projects ----------
class User(Base):
    __tablename__ = "user"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "project"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64), ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    quota_storage_gb: Mapped[int] = mapped_column(Integer, default=100)
    quota_run_concurrency: Mapped[int] = mapped_column(Integer, default=10)
    quota_judge_tokens_per_day: Mapped[int] = mapped_column(BigInteger, default=10_000_000)


class Membership(Base):
    __tablename__ = "membership"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("project.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("user.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(32))  # viewer / contributor / maintainer / owner
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)


# ---------- Datasets ----------
class Dataset(Base):
    __tablename__ = "dataset"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[str] = mapped_column(String(64), default="internal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("project_id", "name"),)


class DatasetVersion(Base):
    __tablename__ = "dataset_version"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), ForeignKey("dataset.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(64))  # semver
    content_hash: Mapped[str] = mapped_column(String(128))
    schema_uri: Mapped[str] = mapped_column(String(512), default="")
    asset_root_uri: Mapped[str] = mapped_column(String(512))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    classification: Mapped[str] = mapped_column(String(64), default="internal")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")  # DRAFT | PUBLISHED
    published_by: Mapped[str | None] = mapped_column(String(64), ForeignKey("user.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("dataset_id", "version"),)


class SliceDef(Base):
    __tablename__ = "slice_def"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("dataset_version.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    predicate: Mapped[str] = mapped_column(Text)  # python expression on example dict
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("dataset_version_id", "name"),)


# ---------- Models ----------
class Model(Base):
    __tablename__ = "model"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("project_id", "name"),)


class ModelVersion(Base):
    __tablename__ = "model_version"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(64), ForeignKey("model.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(64))
    uri: Mapped[str] = mapped_column(String(512))  # mr://… registry URI
    backend: Mapped[str] = mapped_column(String(32), default="echo")  # echo | http | registry
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("model_id", "version"),)


# ---------- Metrics ----------
class Metric(Base):
    __tablename__ = "metric"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


class MetricVersion(Base):
    __tablename__ = "metric_version"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    metric_id: Mapped[str] = mapped_column(String(64), ForeignKey("metric.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(64))  # semver
    package_uri: Mapped[str] = mapped_column(String(512))  # python:melp.metrics.classic:f1_score
    signature: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tests_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("metric_id", "version"),)


# ---------- Judges ----------
class Prompt(Base):
    __tablename__ = "prompt"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(255))
    __table_args__ = (UniqueConstraint("project_id", "name"),)


class PromptVersion(Base):
    __tablename__ = "prompt_version"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String(64), ForeignKey("prompt.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(64))
    template: Mapped[str] = mapped_column(Text)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("prompt_id", "version"),)


class JudgeConfig(Base):
    __tablename__ = "judge_config"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("project.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("project_id", "name"),)


class JudgeConfigVersion(Base):
    __tablename__ = "judge_config_version"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    judge_config_id: Mapped[str] = mapped_column(String(64), ForeignKey("judge_config.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(64))
    judge_model: Mapped[str] = mapped_column(String(255))   # e.g. "claude-opus-4-7"
    prompt_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("prompt_version.id"))
    rubric: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ensembling: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    calibration_set_uri: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("judge_config_id", "version"),)


# ---------- Runs ----------
class Run(Base):
    __tablename__ = "run"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("project.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    model_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("model_version.id"))
    dataset_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("dataset_version.id"))
    slice_set: Mapped[list[str]] = mapped_column(JSON, default=list)
    metric_version_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    judge_config_version_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("judge_config_version.id"), nullable=True
    )
    seed: Mapped[int] = mapped_column(Integer, default=42)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    baseline_run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("run.id"), nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("run.id"), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[str] = mapped_column(String(64), ForeignKey("user.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index("ix_run_project_status", "project_id", "status"),
        UniqueConstraint("project_id", "request_id", name="uq_run_idempotency"),
    )


class RunResult(Base):
    __tablename__ = "run_result"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("run.id", ondelete="CASCADE"), index=True)
    metric_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("metric_version.id"))
    slice_def_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("slice_def.id"), nullable=True)
    point_estimate: Mapped[float] = mapped_column()
    ci_low: Mapped[float | None] = mapped_column(nullable=True)
    ci_high: Mapped[float | None] = mapped_column(nullable=True)
    ci_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    n_examples: Mapped[int] = mapped_column(Integer)
    baseline_run_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("run.id"), nullable=True)
    p_value: Mapped[float | None] = mapped_column(nullable=True)
    effect_size: Mapped[float | None] = mapped_column(nullable=True)
    result_blob_uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("run_id", "metric_version_id", "slice_def_id", name="uq_run_metric_slice"),
    )


class Judgment(Base):
    __tablename__ = "judgment"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("run.id", ondelete="CASCADE"), index=True)
    example_id: Mapped[str] = mapped_column(String(128), index=True)
    judge_config_version_id: Mapped[str] = mapped_column(String(64), ForeignKey("judge_config_version.id"))
    rubric_scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_response_uri: Mapped[str] = mapped_column(String(512), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    token_in: Mapped[int] = mapped_column(Integer, default=0)
    token_out: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Audit & webhooks ----------
class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscription"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("project.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(512))
    secret: Mapped[str] = mapped_column(String(128))  # HMAC signing key
    events: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebhookDelivery(Base):
    __tablename__ = "webhook_delivery"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subscription_id: Mapped[str] = mapped_column(String(64), ForeignKey("webhook_subscription.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- Calibration ----------
class CalibrationRun(Base):
    __tablename__ = "calibration_run"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    judge_config_version_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("judge_config_version.id", ondelete="CASCADE")
    )
    cohen_kappa: Mapped[float | None] = mapped_column(nullable=True)
    krippendorff_alpha: Mapped[float | None] = mapped_column(nullable=True)
    n_examples: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
