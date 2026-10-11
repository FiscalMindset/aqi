import http from "k6/http";
import { check, sleep } from "k6";

// Launch with real targets again:
//   k6 run --vus 10 --duration 2m load/estimate.js

export const options = {
  stages: [
    { duration: "30s", target: 5 },
    { duration: "1m", target: 20 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1500"],
    "http_req_duration{route:explain}": ["p(95)<8000"],
  },
};

const BASE = __ENV.API_BASE || "http://localhost:8000";

export default function () {
  const estimate = http.get(`${BASE}/v1/estimate?lat=28.6139&lon=77.2090`, {
    tags: { route: "estimate" },
  });
  check(estimate, {
    "estimate 200": (r) => r.status === 200,
    "estimate has interval": (r) => r.json("pm25_low") <= r.json("pm25_mid"),
  });

  sleep(1);

  const explain = http.post(
    `${BASE}/v1/explain`,
    JSON.stringify({ lat: 28.6139, lon: 77.209 }),
    {
      headers: { "Content-Type": "application/json" },
      tags: { route: "explain" },
    },
  );
  check(explain, {
    "explain 200": (r) => r.status === 200,
    "explain cites evidence": (r) => r.json("attribution.evidence.length") >= 1,
  });

  sleep(2);
}
