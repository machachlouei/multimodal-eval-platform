# Performance & soak tests

Three test types, increasing in duration:

| Test | Tool | Duration | Cadence | What it validates |
|---|---|---|---|---|
| Smoke | k6 | 60 s | Every PR (CI) | Submit + read paths return 2xx under light load |
| Load | k6 | 15 min | Weekly | P50 / P99 latency targets from Design-Doc §11.6 |
| Soak | k6 | 24 h | Monthly | No memory leak in services; queue depths stay bounded |

## Running locally

```bash
# Smoke
k6 run infra/perf/smoke.js

# Load (15 min)
k6 run -e DURATION=15m infra/perf/load.js

# Soak (24 h) — run on a long-lived host
k6 run -e DURATION=24h infra/perf/soak.js
```

## Targets (Design-Doc §11.6)

- `POST /runs` ack:    P50 ≤ 80 ms, P99 ≤ 500 ms
- `GET /runs/{id}`:    P50 ≤ 50 ms, P99 ≤ 250 ms
- UI page load:        P50 ≤ 600 ms, P99 ≤ 1.5 s

The k6 scripts assert these in their `thresholds` block; the test fails if
any threshold is breached.

## CI wiring

The smoke test is gated in GitHub Actions on every PR (see
`.github/workflows/perf-smoke.yml`). Weekly and monthly cadence is driven by
scheduled cron in the same workflow file.
