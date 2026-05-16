"""Judge Orchestrator. Implements §6.6 / §17.3.

For each example: render prompt → cache lookup → call LLM gateway → parse →
persist Judgment row. Failures route through a 3-tier retry (in-call, in-
orchestrator, dead-letter). Per-project token budgets are enforced here.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
import tenacity

from melp.common import models
from melp.common.cache import redis_client
from melp.common.config import get_settings
from melp.common.db import session_scope
from melp.common.ids import new_id
from melp.common.storage import put_bytes
from melp.common.telemetry import get_logger
from melp.judge import cache as jcache
from melp.judge import prompts

log = get_logger(__name__)


# ---------- Token budget ----------
def _budget_check_and_consume(project_id: str, tokens: int) -> bool:
    """Per-project per-minute budget. Returns True if the spend is allowed.

    The full per-project per-day budget is checked at job admission; this is
    the in-flight rate limiter (§11.3).
    """
    s = get_settings()
    bucket = f"budget:{project_id}:{int(time.time()) // 60}"
    r = redis_client()
    used = int(r.incrby(bucket, tokens) or 0)
    r.expire(bucket, 120)
    return used <= s.judge_token_budget_per_min


# ---------- LLM gateway call ----------
@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential_jitter(initial=0.5, max=8),
    retry=tenacity.retry_if_exception_type((httpx.HTTPError, ValueError)),
    reraise=True,
)
def _call_llm(judge_model: str, prompt: str) -> dict[str, Any]:
    s = get_settings()
    with httpx.Client(timeout=60) as c:
        r = c.post(
            f"{s.llm_gateway_url}/v1/judge",
            json={"model": judge_model, "prompt": prompt},
            headers={"Authorization": f"Bearer {s.llm_gateway_token}"},
        )
        r.raise_for_status()
        return r.json()


# ---------- Judge a single example ----------
def judge_one(
    *,
    run_id: str,
    project_id: str,
    judge_config_version: models.JudgeConfigVersion,
    prompt_version: models.PromptVersion,
    example: dict[str, Any],
) -> dict[str, Any]:
    key = jcache.make_key(
        judge_model=judge_config_version.judge_model,
        prompt_version_id=prompt_version.id,
        rubric_hash=jcache.rubric_hash(judge_config_version.rubric),
        example=example,
    )
    cached = jcache.get(key)
    if cached:
        return {"raw": cached["raw"], "parsed": cached["parsed"], "cache_hit": True, "latency_ms": 0,
                "token_in": 0, "token_out": 0}

    rendered = prompts.render(prompt_version.template, example)
    # Budget gate.
    est_tokens_in = max(1, len(rendered) // 4)
    if not _budget_check_and_consume(project_id, est_tokens_in):
        raise RuntimeError("judge token budget exhausted for this minute")
    t0 = time.perf_counter()
    resp = _call_llm(judge_config_version.judge_model, rendered)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    raw = resp.get("output", "")
    parsed = prompts.parse_response(raw, prompt_version.output_schema or {})
    out = {
        "raw": raw,
        "parsed": parsed,
        "cache_hit": False,
        "latency_ms": elapsed_ms,
        "token_in": resp.get("usage", {}).get("input_tokens", est_tokens_in),
        "token_out": resp.get("usage", {}).get("output_tokens", 0),
    }
    jcache.put(key, {"raw": raw, "parsed": parsed})
    return out


# ---------- Judge a whole run ----------
def judge_run(run_id: str, examples: list[dict[str, Any]]) -> int:
    """Drive the judge over every example and persist Judgment rows.

    Failed examples land in a Redis-backed dead-letter list with the original
    ``example_id`` so a runbook can replay them (§6.6 failure behavior).
    """
    s = get_settings()
    with session_scope() as db:
        r = db.query(models.Run).filter_by(id=run_id).one()
        if not r.judge_config_version_id:
            return 0
        jcv = db.query(models.JudgeConfigVersion).filter_by(id=r.judge_config_version_id).one()
        pv = db.query(models.PromptVersion).filter_by(id=jcv.prompt_version_id).one()
        project_id = r.project_id

    judged = 0
    failed: list[dict] = []
    for ex in examples:
        example_id = str(ex.get("id", judged))
        try:
            result = judge_one(
                run_id=run_id,
                project_id=project_id,
                judge_config_version=jcv,
                prompt_version=pv,
                example=ex,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("judge.example_failed", run_id=run_id, example_id=example_id, error=str(e))
            failed.append({"example_id": example_id, "error": str(e)[:300]})
            continue
        # Persist raw response.
        raw_uri_key = f"runs/{run_id}/judge/{example_id}.txt"
        if not result["cache_hit"]:
            put_bytes(s.s3_bucket_artifacts, raw_uri_key, result["raw"].encode(), "text/plain")
        with session_scope() as db:
            db.add(
                models.Judgment(
                    id=new_id("judgment"),
                    run_id=run_id,
                    example_id=example_id,
                    judge_config_version_id=jcv.id,
                    rubric_scores=result["parsed"],
                    raw_response_uri=f"s3://{s.s3_bucket_artifacts}/{raw_uri_key}" if not result["cache_hit"] else "",
                    latency_ms=result["latency_ms"],
                    token_in=result["token_in"],
                    token_out=result["token_out"],
                    cache_hit=result["cache_hit"],
                )
            )
        judged += 1
    if failed:
        r_ = redis_client()
        r_.rpush(f"melp:judge:dlq:{run_id}", *[str(f) for f in failed])
    return judged
