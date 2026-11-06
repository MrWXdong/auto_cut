from __future__ import annotations

from app.nodes.subtitle import format_timestamp


def test_formats_srt_timestamp() -> None:
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(61.5) == "00:01:01,500"
    assert format_timestamp(3661.25) == "01:01:01,250"


def test_clamps_negative_values() -> None:
    assert format_timestamp(-3) == "00:00:00,000"
