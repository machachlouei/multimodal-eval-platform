# Getting started

## 1. Bring up infrastructure

```bash
docker-compose up -d
```

This starts Postgres, Redis, MinIO (with bucket init), Temporal, and the
stubbed LLM gateway.

## 2. Install Python deps

```bash
uv sync --extra dev --extra metrics-text --extra metrics-speech
# or:
pip install -e ".[dev,metrics-text,metrics-speech]"
```

## 3. Run migrations + seed

```bash
make db-up
make seed
```

`make seed` creates:
- a dev user (`dev@example.com`)
- a project (`captioner-pilot`) with an owner membership
- the full built-in metric registry (~25 metrics across classic / text / probability / speech / vision)
- a toy `captioner` model (echo backend)
- a toy `caption-toy` dataset version (4 examples)
- one slice (`long`) for examples with ≥5 tokens.

## 4. Start the gateway + worker

In one terminal:

```bash
make run-gateway      # http://localhost:8000
```

In another:

```bash
make run-worker
```

## 5. Submit your first run

```bash
melp project list
melp metric list
melp run list --project captioner-pilot
```

Find the IDs you need, edit `examples/captioner_classic.yaml`, then:

```bash
melp run submit examples/captioner_classic.yaml
melp run watch <run_id> --project captioner-pilot
```

## 6. Browse the UI

```bash
python -m melp.services.ui.app
```

Visit <http://localhost:8080>.

## 7. Phase 2: judge plane

Register a prompt + judge config (via SDK):

```python
from melp.sdk import MELPClient
c = MELPClient("http://localhost:8000")
c.http.post(
    "http://localhost:8000/v1/projects/captioner-pilot/judge-configs/_prompts/caption-quality/versions",
    json={
        "version": "1.0.0",
        "template": "Rate caption quality for input={input}\nPrediction: {prediction}\n\nRespond as JSON {\"score\": 0..1, \"rationale\": string}.",
        "output_schema": {"required": ["score"], "fields": {"score": {"type": "number", "min": 0, "max": 1}}},
    },
)
```

Then create a judge config and a judge config version pointing at that prompt.
Submit a run with the `judge_config_version_id` and a metric like
`semantic_equivalence` to use it.
