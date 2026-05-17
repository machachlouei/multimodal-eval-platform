// MELP load test. 15 min sustained at 200 RPS to validate §11.6 latency targets.
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    sustained: {
      executor: 'constant-arrival-rate',
      rate: 200,
      timeUnit: '1s',
      duration: __ENV.DURATION || '15m',
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    http_req_duration: ['p(50)<80', 'p(99)<500'],
    http_req_failed: ['rate<0.001'],
  },
};

const BASE = __ENV.MELP_BASE_URL || 'http://localhost:8000';

export default function () {
  http.get(`${BASE}/v1/projects/captioner-pilot/runs?limit=20`);
  sleep(0.05);
}
