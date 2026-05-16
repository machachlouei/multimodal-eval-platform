"""Deterministic stub LLM gateway for local dev / CI.

Implements the same surface MELP expects from the internal LLM gateway:
  POST /v1/judge {model, prompt} -> {output, usage}

The output is JSON with a deterministic score derived from the prompt hash so
that tests are stable. Production swaps this URL for the real gateway.
"""
from __future__ import annotations

import hashlib
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, {"error": "bad json"})
        if self.path != "/v1/judge":
            return self._send(404, {"error": "not found"})
        prompt = payload.get("prompt", "")
        h = hashlib.sha256(prompt.encode()).digest()
        # Deterministic score in [0, 1].
        score = (h[0] / 255.0)
        out = json.dumps({"score": round(score, 3), "rationale": "stub deterministic judge"})
        return self._send(200, {
            "output": out,
            "usage": {"input_tokens": max(1, len(prompt) // 4), "output_tokens": 32},
        })

    def log_message(self, *_):  # silence
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9100), Handler).serve_forever()
