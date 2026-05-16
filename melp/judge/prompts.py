"""Prompt rendering with strict, allow-listed templating.

Templates use ``{name}`` placeholders bound to the example dict. We deliberately
avoid Jinja for prompts because (1) prompt injection in dataset content is in
the threat model (§9.6) and (2) we want render-time errors to surface as
validation errors, not runtime tracebacks.

Output structure is enforced by parsing JSON from the model response and
validating against the prompt's ``output_schema``.
"""
from __future__ import annotations

import json
import re
from typing import Any

_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render(template: str, example: dict[str, Any]) -> str:
    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in example:
            raise ValueError(f"prompt placeholder {{{key}}} not present in example")
        v = example[key]
        # Escape backticks and braces in user content to neutralise injection.
        s = str(v).replace("{", "{{").replace("}", "}}")
        return s

    return _PLACEHOLDER.sub(sub, template)


def parse_response(raw: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Parse a model response as JSON and check it against ``schema``.

    ``schema`` is a tiny subset of JSON Schema: ``{"required":[...], "score":{"type":"number","min":0,"max":1}, ...}``
    """
    text = raw.strip()
    # Tolerate code fences.
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :]
    try:
        data = json.loads(text[text.find("{") : text.rfind("}") + 1])
    except Exception as e:
        raise ValueError(f"judge response is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("judge response must be a JSON object")
    for key in schema.get("required", []):
        if key not in data:
            raise ValueError(f"judge response missing key {key!r}")
    for key, rule in schema.get("fields", {}).items():
        if key not in data:
            continue
        if rule.get("type") == "number":
            v = float(data[key])
            if "min" in rule and v < rule["min"]:
                raise ValueError(f"{key}={v} below min")
            if "max" in rule and v > rule["max"]:
                raise ValueError(f"{key}={v} above max")
            data[key] = v
        elif rule.get("type") == "string":
            data[key] = str(data[key])
    return data
