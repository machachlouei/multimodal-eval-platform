"""Webhook dispatch with HMAC signing and exponential backoff. See §8.5."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from melp.common import models
from melp.common.ids import new_id


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def enqueue_event(
    db: Session,
    *,
    project_id: str,
    event: str,
    payload: dict[str, Any],
) -> int:
    """Insert one WebhookDelivery row per active subscription that wants ``event``."""
    subs = (
        db.query(models.WebhookSubscription)
        .filter_by(project_id=project_id, active=True)
        .all()
    )
    n = 0
    for s in subs:
        if event not in s.events:
            continue
        db.add(
            models.WebhookDelivery(
                id=new_id("webhook"),
                subscription_id=s.id,
                event=event,
                payload=payload,
                next_attempt_at=datetime.now(UTC),
            )
        )
        n += 1
    return n


def deliver_pending(db: Session, *, max_batch: int = 50, max_attempts: int = 8) -> int:
    """Background-loop entry point. Returns number of deliveries attempted."""
    now = datetime.now(UTC)
    rows = (
        db.query(models.WebhookDelivery)
        .filter(models.WebhookDelivery.status == "PENDING")
        .filter(models.WebhookDelivery.next_attempt_at <= now)
        .limit(max_batch)
        .all()
    )
    for d in rows:
        sub = db.query(models.WebhookSubscription).filter_by(id=d.subscription_id).one()
        body = json.dumps({"event": d.event, "delivery_id": d.id, "data": d.payload}).encode()
        try:
            with httpx.Client(timeout=10) as c:
                r = c.post(
                    sub.url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-MELP-Signature": sign(body, sub.secret),
                        "X-MELP-Event": d.event,
                        "X-MELP-Delivery-Id": d.id,
                    },
                )
            if 200 <= r.status_code < 300:
                d.status = "DELIVERED"
            else:
                d.attempts += 1
                d.last_error = f"HTTP {r.status_code}: {r.text[:200]}"
                if d.attempts >= max_attempts:
                    d.status = "FAILED"
                else:
                    backoff = min(2 ** d.attempts, 600)
                    d.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
        except Exception as e:  # noqa: BLE001
            d.attempts += 1
            d.last_error = str(e)[:200]
            if d.attempts >= max_attempts:
                d.status = "FAILED"
            else:
                backoff = min(2 ** d.attempts, 600)
                d.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff)
    return len(rows)


def run_delivery_loop(interval_s: int = 5) -> None:
    """Long-lived helper used by ``melp.workers.webhook_dispatcher``."""
    from melp.common.db import session_scope

    while True:
        with session_scope() as db:
            deliver_pending(db)
        time.sleep(interval_s)
