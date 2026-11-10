from __future__ import annotations

from app.nodes.subtitle import build_clip_timed_text, format_short_timestamp, format_timestamp


def test_formats_srt_timestamp() -> None:
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(61.5) == "00:01:01,500"
    assert format_timestamp(3661.25) == "01:01:01,250"


def test_clamps_negative_values() -> None:
    assert format_timestamp(-3) == "00:00:00,000"


def test_formats_short_timestamp() -> None:
    assert format_short_timestamp(0) == "00:00"
    assert format_short_timestamp(61.5) == "01:02"
    assert format_short_timestamp(3661.25) == "01:01:01"


def test_groups_subtitles_by_clip_time_range() -> None:
    clips = [
        {"start": 0, "end": 12.597, "title": "第一段"},
        {"start": 12.597, "end": 24.399, "title": "第二段"},
    ]
    transcript = [
        {"start": 0, "end": 5, "text": "第一句"},
        {"start": 5, "end": 12.597, "text": "第二句"},
        {"start": 12.597, "end": 18, "text": "第三句"},
    ]
    assert build_clip_timed_text(clips, transcript).splitlines() == [
        "[00:00 --> 00:13] 第一句 第二句",
        "[00:13 --> 00:24] 第三句",
    ]
