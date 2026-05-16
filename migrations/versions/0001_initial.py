"""Initial MELP schema — Phase 1 + Phase 2 tables.

Single migration on purpose: this is a greenfield system; the Phase 2 tables
(judge configs, prompts, judgments, webhooks, calibration) are introduced at
launch so DB-level migration risk is contained to one window. Future deltas
will land as separate revisions.

Revision ID: 0001_initial
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "project",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by", sa.String(64), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("quota_storage_gb", sa.Integer, nullable=False, server_default="100"),
        sa.Column("quota_run_concurrency", sa.Integer, nullable=False, server_default="10"),
        sa.Column("quota_judge_tokens_per_day", sa.BigInteger, nullable=False, server_default="10000000"),
    )
    op.create_table(
        "membership",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(64), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "user_id"),
    )

    op.create_table(
        "dataset",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("classification", sa.String(64), nullable=False, server_default="internal"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_table(
        "dataset_version",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dataset_id", sa.String(64), sa.ForeignKey("dataset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("schema_uri", sa.String(512), nullable=False, server_default=""),
        sa.Column("asset_root_uri", sa.String(512), nullable=False),
        sa.Column("record_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("classification", sa.String(64), nullable=False, server_default="internal"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("published_by", sa.String(64), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("dataset_id", "version"),
    )
    op.create_table(
        "slice_def",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("dataset_version_id", sa.String(64), sa.ForeignKey("dataset_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("predicate", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint("dataset_version_id", "name"),
    )

    op.create_table(
        "model",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_table(
        "model_version",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("model_id", sa.String(64), sa.ForeignKey("model.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("uri", sa.String(512), nullable=False),
        sa.Column("backend", sa.String(32), nullable=False, server_default="echo"),
        sa.Column("config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("model_id", "version"),
    )

    op.create_table(
        "metric",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )
    op.create_table(
        "metric_version",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("metric_id", sa.String(64), sa.ForeignKey("metric.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("package_uri", sa.String(512), nullable=False),
        sa.Column("signature", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("tests_passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("metric_id", "version"),
    )

    op.create_table(
        "prompt",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_table(
        "prompt_version",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("prompt_id", sa.String(64), sa.ForeignKey("prompt.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("template", sa.Text, nullable=False),
        sa.Column("output_schema", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("prompt_id", "version"),
    )

    op.create_table(
        "judge_config",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_table(
        "judge_config_version",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("judge_config_id", sa.String(64), sa.ForeignKey("judge_config.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("judge_model", sa.String(255), nullable=False),
        sa.Column("prompt_version_id", sa.String(64), sa.ForeignKey("prompt_version.id"), nullable=False),
        sa.Column("rubric", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("ensembling", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("calibration_set_uri", sa.String(512), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("judge_config_id", "version"),
    )

    op.create_table(
        "run",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("model_version_id", sa.String(64), sa.ForeignKey("model_version.id"), nullable=False),
        sa.Column("dataset_version_id", sa.String(64), sa.ForeignKey("dataset_version.id"), nullable=False),
        sa.Column("slice_set", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("metric_version_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("judge_config_version_id", sa.String(64), sa.ForeignKey("judge_config_version.id"), nullable=True),
        sa.Column("seed", sa.Integer, nullable=False, server_default="42"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("baseline_run_id", sa.String(64), nullable=True),
        sa.Column("parent_run_id", sa.String(64), nullable=True),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("progress", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("submitted_by", sa.String(64), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "request_id", name="uq_run_idempotency"),
    )
    op.create_index("ix_run_project_status", "run", ["project_id", "status"])
    op.create_index("ix_run_project_id", "run", ["project_id"])
    op.create_index("ix_run_status", "run", ["status"])
    op.create_index("ix_run_request_id", "run", ["request_id"])

    op.create_table(
        "run_result",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_version_id", sa.String(64), sa.ForeignKey("metric_version.id"), nullable=False),
        sa.Column("slice_def_id", sa.String(64), sa.ForeignKey("slice_def.id"), nullable=True),
        sa.Column("point_estimate", sa.Float, nullable=False),
        sa.Column("ci_low", sa.Float, nullable=True),
        sa.Column("ci_high", sa.Float, nullable=True),
        sa.Column("ci_method", sa.String(32), nullable=True),
        sa.Column("n_examples", sa.Integer, nullable=False),
        sa.Column("baseline_run_id", sa.String(64), nullable=True),
        sa.Column("p_value", sa.Float, nullable=True),
        sa.Column("effect_size", sa.Float, nullable=True),
        sa.Column("result_blob_uri", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "metric_version_id", "slice_def_id", name="uq_run_metric_slice"),
    )
    op.create_index("ix_run_result_run_id", "run_result", ["run_id"])

    op.create_table(
        "judgment",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("example_id", sa.String(128), nullable=False),
        sa.Column("judge_config_version_id", sa.String(64), sa.ForeignKey("judge_config_version.id"), nullable=False),
        sa.Column("rubric_scores", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("raw_response_uri", sa.String(512), nullable=False, server_default=""),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("token_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_hit", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_judgment_run_id", "judgment", ["run_id"])
    op.create_index("ix_judgment_example_id", "judgment", ["example_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_project_id", "audit_log", ["project_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    op.create_table(
        "webhook_subscription",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("events", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "webhook_delivery",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("subscription_id", sa.String(64), sa.ForeignKey("webhook_subscription.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "calibration_run",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("judge_config_version_id", sa.String(64), sa.ForeignKey("judge_config_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cohen_kappa", sa.Float, nullable=True),
        sa.Column("krippendorff_alpha", sa.Float, nullable=True),
        sa.Column("n_examples", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_calibration_run_created_at", "calibration_run", ["created_at"])


def downgrade() -> None:
    for table in [
        "calibration_run", "webhook_delivery", "webhook_subscription",
        "audit_log", "judgment", "run_result", "run",
        "judge_config_version", "judge_config", "prompt_version", "prompt",
        "metric_version", "metric",
        "model_version", "model",
        "slice_def", "dataset_version", "dataset",
        "membership", "project", "user",
    ]:
        op.drop_table(table)
