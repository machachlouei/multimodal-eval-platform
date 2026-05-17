"""Judge DLQ replay command. Phase 3.

Drains failed-judgment entries from the Redis dead-letter queue for a given
run and resubmits them through the judge orchestrator. Designed to be run
manually by on-call after a transient judge-gateway outage (§6.6 retry
strategy, dead-letter tier).

Usage::

    python -m melp.scripts.dlq_replay --run-id run_01HKY... [--dry-run]
"""
from __future__ import annotations

import argparse
import ast
import sys

from melp.common import models
from melp.common.cache import redis_client
from melp.common.db import session_scope


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    r = redis_client()
    key = f"melp:judge:dlq:{args.run_id}"
    raw = r.lrange(key, 0, -1)
    if not raw:
        print(f"DLQ empty for run {args.run_id}", file=sys.stderr)
        return 0

    failed = [ast.literal_eval(item) if isinstance(item, str) else item for item in raw]
    print(f"DLQ has {len(failed)} entries for {args.run_id}", file=sys.stderr)
    if args.dry_run:
        for f in failed[:10]:
            print(f"  - {f}", file=sys.stderr)
        return 0

    # Reload predictions JSONL to find the original example payloads.
    from melp.common.config import get_settings
    from melp.common.storage import get_bytes
    import json

    s = get_settings()
    preds_raw = get_bytes(s.s3_bucket_artifacts, f"runs/{args.run_id}/predictions.jsonl")
    by_id = {
        str(json.loads(line)["id"]): json.loads(line)
        for line in preds_raw.decode().splitlines()
        if line.strip()
    }

    to_replay = [by_id[entry["example_id"]] for entry in failed if entry["example_id"] in by_id]
    if not to_replay:
        print("no matching examples found in predictions artifact", file=sys.stderr)
        return 1

    from melp.judge.orchestrator import judge_run

    with session_scope() as db:
        run = db.query(models.Run).filter_by(id=args.run_id).one_or_none()
        if run is None:
            print(f"run {args.run_id} not found", file=sys.stderr)
            return 1

    n = judge_run(args.run_id, to_replay)
    if n == len(to_replay):
        r.delete(key)
        print(f"replayed {n}/{len(to_replay)} entries; DLQ cleared", file=sys.stderr)
        return 0
    print(f"replayed {n}/{len(to_replay)}; DLQ still has entries", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
