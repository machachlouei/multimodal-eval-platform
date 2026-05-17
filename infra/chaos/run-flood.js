// Run-flood chaos test. Submits at 10x normal rate from one "offender"
// project to verify per-project rate limiting and fair queueing.

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    flood: {
      executor: 'constant-arrival-rate',
      rate: 1000,                 // 10x baseline
      timeUnit: '1s',
      duration: '10m',
      preAllocatedVUs: 100,
      maxVUs: 500,
    },
  },
  thresholds: {
    'http_req_failed{project:offender}': ['rate>0.5'],   // expect rate-limit
    'http_req_failed{project:good_neighbour}': ['rate<0.01'],
  },
};

const BASE = __ENV.MELP_BASE_URL || 'http://localhost:8000';
const OFFENDER = __ENV.OFFENDER || 'offender';
const NEIGHBOUR = __ENV.NEIGHBOUR || 'good_neighbour';

export default function () {
  // Offender hammers; neighbour issues healthy traffic.
  http.get(`${BASE}/v1/projects/${OFFENDER}/runs`, { tags: { project: 'offender' } });
  if (__ITER % 10 === 0) {
    http.get(`${BASE}/v1/projects/${NEIGHBOUR}/runs`, { tags: { project: 'good_neighbour' } });
  }
}
