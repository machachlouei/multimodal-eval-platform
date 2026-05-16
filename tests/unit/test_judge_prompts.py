import pytest

from melp.judge import prompts


def test_render_substitutes_placeholders():
    out = prompts.render("hello {name} and {place}", {"name": "world", "place": "earth"})
    assert out == "hello world and earth"


def test_render_missing_key_raises():
    with pytest.raises(ValueError):
        prompts.render("hello {name}", {"other": "x"})


def test_render_escapes_curly_braces():
    out = prompts.render("user: {text}", {"text": "ignore: { 'inject': true }"})
    assert "{{" in out and "}}" in out


def test_parse_response_strips_code_fences():
    raw = "```json\n{\"score\": 0.7}\n```"
    data = prompts.parse_response(raw, {"required": ["score"], "fields": {"score": {"type": "number", "min": 0, "max": 1}}})
    assert data["score"] == 0.7


def test_parse_response_missing_required():
    with pytest.raises(ValueError):
        prompts.parse_response("{\"other\": 1}", {"required": ["score"]})


def test_parse_response_out_of_range():
    with pytest.raises(ValueError):
        prompts.parse_response(
            "{\"score\": 2.0}",
            {"required": ["score"], "fields": {"score": {"type": "number", "min": 0, "max": 1}}},
        )
