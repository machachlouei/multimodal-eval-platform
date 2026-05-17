// 24h soak test — surfaces memory leaks, connection-pool exhaustion, and
// monotonically-growing queues. Run on a long-lived host, not in CI.
import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  vus: 20,
  duration: __ENV.DURATION || '24h',
  thresholds: {
    http_req_duration: ['p(99)<800'],
    http_req_failed: ['rate<0.002'],
  },
};

const BASE = __ENV.MELP_BASE_URL || 'http://localhost:8000';

export default function () {
  http.get(`${BASE}/v1/projects/captioner-pilot/runs?limit=10`);
  sleep(1);
}
