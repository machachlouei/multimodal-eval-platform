// MELP control-plane smoke test. Light load, gated in CI on every PR.
// Validates that submission ack stays under 500 ms P99 and reads under 250 ms.

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 5,
  duration: '60s',
  thresholds: {
    http_req_duration{type:submit}: ['p(99)<500'],
    http_req_duration{type:read}: ['p(99)<250'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE = __ENV.MELP_BASE_URL || 'http://localhost:8000';
const PROJECT = __ENV.MELP_PROJECT || 'captioner-pilot';
const MODEL_VERSION = __ENV.MELP_MODEL_VERSION || '';
const DATASET_VERSION = __ENV.MELP_DATASET_VERSION || '';
const METRIC_VERSION = __ENV.MELP_METRIC_VERSION || '';

export default function () {
  // GET path
  const get = http.get(`${BASE}/v1/projects/${PROJECT}/runs?status=COMPLETED&limit=10`, {
    tags: { type: 'read' },
  });
  check(get, { 'list runs ok': (r) => r.status === 200 });

  // Submit (idempotent, so retry-safe across iterations)
  if (MODEL_VERSION && DATASET_VERSION && METRIC_VERSION) {
    const body = JSON.stringify({
      model_version_id: MODEL_VERSION,
      dataset_version_id: DATASET_VERSION,
      metric_version_ids: [METRIC_VERSION],
      seed: 42,
      priority: 'low',
    });
    const submit = http.post(`${BASE}/v1/projects/${PROJECT}/runs`, body, {
      headers: { 'Content-Type': 'application/json', 'Idempotency-Key': `k6-${__VU}-${__ITER}` },
      tags: { type: 'submit' },
    });
    check(submit, { 'submit 201': (r) => r.status === 201 });
  }

  sleep(0.2);
}
