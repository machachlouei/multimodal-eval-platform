"""Seed a dev environment: project, user, model, dataset, metric registrations.

Usage::

    python -m melp.scripts.seed_dev
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from melp.common import models
from melp.common.config import get_settings
from melp.common.db import session_scope
from melp.common.ids import new_id
from melp.common.storage import ensure_buckets, put_bytes
from melp.metrics.registry import BUILTINS


def seed() -> None:
    s = get_settings()
    ensure_buckets()

    with session_scope() as db:
        # User.
        user = db.query(models.User).filter_by(email=s.auth_dev_user).one_or_none()
        if user is None:
            user = models.User(id="usr_dev", email=s.auth_dev_user, display_name="dev")
            db.add(user)
            db.flush()

        # Project.
        proj = db.query(models.Project).filter_by(name="captioner-pilot").one_or_none()
        if proj is None:
            proj = models.Project(
                id=new_id("project"),
                name="captioner-pilot",
                description="Pilot project for the captioner team.",
                created_by=user.id,
            )
            db.add(proj)
            db.add(models.Membership(
                id=new_id("membership"), project_id=proj.id, user_id=user.id, role="owner"
            ))
            db.flush()

        # Metrics + versions (built-ins).
        for spec in BUILTINS:
            m = db.query(models.Metric).filter_by(name=spec.name).one_or_none()
            if m is None:
                m = models.Metric(id=new_id("metric"), name=spec.name, description=spec.description)
                db.add(m)
                db.flush()
            mv = (
                db.query(models.MetricVersion)
                .filter_by(metric_id=m.id, version=spec.version)
                .one_or_none()
            )
            if mv is None:
                db.add(models.MetricVersion(
                    id=new_id("metric_version"),
                    metric_id=m.id,
                    version=spec.version,
                    package_uri=spec.package_uri,
                    signature={
                        "predict_type": spec.predict_type,
                        "reference_type": spec.reference_type,
                        "higher_is_better": spec.higher_is_better,
                        "needs_judge": spec.needs_judge,
                        "deterministic": spec.deterministic,
                    },
                    tests_passed_at=datetime.now(UTC),
                ))

        # Model + version (echo backend).
        model = db.query(models.Model).filter_by(project_id=proj.id, name="captioner").one_or_none()
        if model is None:
            model = models.Model(id=new_id("model"), project_id=proj.id, name="captioner", description="echo demo")
            db.add(model)
            db.flush()
        mv = db.query(models.ModelVersion).filter_by(model_id=model.id, version="0.1.0").one_or_none()
        if mv is None:
            db.add(models.ModelVersion(
                id=new_id("model_version"),
                model_id=model.id,
                version="0.1.0",
                uri="mr://captioner@0.1.0",
                backend="echo",
            ))

        # Dataset + version.
        ds = db.query(models.Dataset).filter_by(project_id=proj.id, name="caption-toy").one_or_none()
        if ds is None:
            ds = models.Dataset(id=new_id("dataset"), project_id=proj.id, name="caption-toy", description="toy")
            db.add(ds)
            db.flush()

        # Upload toy dataset assets.
        examples = [
            {"id": "ex_1", "input": "a cat on a mat", "reference": "a cat on a mat", "len": 4},
            {"id": "ex_2", "input": "a quick brown fox jumps", "reference": "a quick brown fox jumps over", "len": 5},
            {"id": "ex_3", "input": "hello world", "reference": "hello world", "len": 2},
            {"id": "ex_4", "input": "this is a long video frame description that is detailed", "reference": "this is a long video frame description", "len": 9},
        ]
        blob = ("\n".join(json.dumps(e) for e in examples) + "\n").encode()
        put_bytes(s.s3_bucket_datasets, "caption-toy/v0.1.0/data.jsonl", blob, "application/x-ndjson")

        dv = db.query(models.DatasetVersion).filter_by(dataset_id=ds.id, version="0.1.0").one_or_none()
        if dv is None:
            dv = models.DatasetVersion(
                id=new_id("dataset_version"),
                dataset_id=ds.id,
                version="0.1.0",
                content_hash="seed",
                asset_root_uri=f"s3://{s.s3_bucket_datasets}/caption-toy/v0.1.0/",
                record_count=len(examples),
                classification="internal",
                status="PUBLISHED",
                published_by=user.id,
                published_at=datetime.now(UTC),
            )
            db.add(dv)
            db.flush()
            # Slice: long examples.
            db.add(models.SliceDef(
                id=new_id("slice_def"),
                dataset_version_id=dv.id,
                name="long",
                predicate="example.get('len', 0) >= 5",
                description="Examples with >=5 tokens",
            ))

    print("Seeded captioner-pilot project, captioner model, caption-toy dataset, and metric registry.", file=sys.stderr)


if __name__ == "__main__":
    seed()
