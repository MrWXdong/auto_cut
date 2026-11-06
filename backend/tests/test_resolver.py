from __future__ import annotations

import pytest

from app.core.workflow.resolver import ReferenceError, build_scope, resolve


def make_scope() -> dict:
    return build_scope(
        inputs={"source": "in.mp4", "max_clips": 5},
        variables={"language": "zh"},
        node_outputs={
            "transcript": {
                "segments": [{"start": 1.0, "text": "hello"}],
                "count": 3,
            }
        },
        env={"MODEL": "deepseek-chat"},
        loop={"index": 0, "item": {"start": 1.0}},
    )


def test_full_reference_preserves_type() -> None:
    scope = make_scope()
    assert resolve("{{inputs.max_clips}}", scope) == 5
    assert resolve("{{transcript.segments}}", scope) == [{"start": 1.0, "text": "hello"}]


def test_embedded_reference_interpolates() -> None:
    scope = make_scope()
    assert resolve("clip-{{loop.index}}.mp4", scope) == "clip-0.mp4"
    assert resolve("{{transcript.count}} segments", scope) == "3 segments"


def test_nested_lookup() -> None:
    scope = make_scope()
    assert resolve("{{transcript.segments.0.text}}", scope) == "hello"
    assert resolve("{{loop.item.start}}", scope) == 1.0
    assert resolve("{{env.MODEL}}", scope) == "deepseek-chat"


def test_resolves_inside_containers() -> None:
    scope = make_scope()
    value = {
        "source": "{{inputs.source}}",
        "options": ["{{vars.language}}", 1],
    }
    assert resolve(value, scope) == {"source": "in.mp4", "options": ["zh", 1]}


def test_missing_reference_raises() -> None:
    scope = make_scope()
    with pytest.raises(ReferenceError):
        resolve("{{inputs.missing}}", scope)
    with pytest.raises(ReferenceError):
        resolve("{{unknown.value}}", scope)


def test_boolean_and_none_are_stringified() -> None:
    scope = build_scope(inputs={"enabled": True, "empty": None})
    assert resolve("enabled={{inputs.enabled}}", scope) == "enabled=true"
    assert resolve("value={{inputs.empty}}", scope) == "value="
