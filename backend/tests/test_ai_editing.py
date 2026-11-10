from __future__ import annotations

from app.config import Settings, get_settings
from app.gateway.asr import CloudASR
from app.gateway.base import ChatResult
from app.nodes.ai import (
    SelectSegmentsNode,
    _build_prompt,
    _fallback_segments,
    _parse_segments,
)
from app.studio.edit import choose_workflow, edit_capabilities


def test_cloud_asr_sentence_timeline() -> None:
    segments = CloudASR._split_sentences(
        "第一句介绍产品。第二句讲使用体验！第三句给出建议？",
        0,
        12,
    )
    assert len(segments) == 3
    assert segments[0]["start"] == 0
    assert segments[-1]["end"] == 12
    assert segments[0]["text"] == "第一句介绍产品。"


def test_rule_fallback_keeps_short_video_whole() -> None:
    picks = _fallback_segments(
        [{"start": 0, "end": 6, "text": "短视频内容"}],
        duration=6,
        max_clips=3,
        min_seconds=15,
        max_seconds=60,
    )
    assert len(picks) == 1
    assert picks[0]["start"] == 0
    assert picks[0]["end"] == 6


def test_rule_fallback_honors_requested_clip_count() -> None:
    picks = _fallback_segments(
        [],
        duration=37.5,
        max_clips=3,
        min_seconds=15,
        max_seconds=60,
    )
    assert len(picks) == 3
    assert picks[0]["start"] == 0
    assert picks[-1]["end"] == 37.5
    assert all(item["end"] > item["start"] for item in picks)


def test_rule_fallback_uses_sentence_boundaries_and_keeps_short_clip() -> None:
    picks = _fallback_segments(
        [
            {"start": 0, "end": 10, "text": "开场介绍"},
            {"start": 10, "end": 13, "text": "三秒高光"},
            {"start": 13, "end": 30, "text": "后续内容"},
        ],
        duration=30,
        max_clips=3,
        min_seconds=1,
        max_seconds=0,
    )
    assert [(item["start"], item["end"]) for item in picks] == [
        (0.0, 10.0),
        (10.0, 13.0),
        (13.0, 30.0),
    ]


def test_rule_fallback_has_no_fixed_upper_limit() -> None:
    picks = _fallback_segments(
        [],
        duration=200,
        max_clips=2,
        min_seconds=1,
        max_seconds=0,
    )
    assert len(picks) == 2
    assert all(item["end"] - item["start"] > 60 for item in picks)


def test_rule_fallback_respects_optional_custom_upper_limit() -> None:
    picks = _fallback_segments(
        [],
        duration=200,
        max_clips=2,
        min_seconds=1,
        max_seconds=60,
    )
    assert len(picks) == 4
    assert all(item["end"] - item["start"] <= 60 for item in picks)


def test_ai_prompt_and_parser_allow_short_highlights_without_fixed_max() -> None:
    prompt = _build_prompt(
        [{"start": 10, "end": 13, "text": "三秒高光"}],
        duration=30,
        max_clips=3,
        min_seconds=1,
        max_seconds=0,
    )
    assert "不设固定单段上限" in prompt
    picks = _parse_segments(
        '[{"start": 10, "end": 13, "title": "三秒高光", "score": 0.9}]',
        duration=30,
        min_seconds=1,
        max_seconds=0,
    )
    assert len(picks) == 1
    assert picks[0]["end"] - picks[0]["start"] == 3


def test_edit_capabilities_uses_cloud_asr_and_llm() -> None:
    current = get_settings()
    settings = Settings(
        _env_file=None,
        llm_api_key="test-key",
        llm_base_url="https://open.bigmodel.cn/api/paas/v4",
        ffmpeg_bin=current.ffmpeg_bin,
        asr_provider="cloud",
        asr_api_key="",
    )
    capabilities = edit_capabilities(settings)
    assert capabilities["ai_ready"] is True
    assert capabilities["asr"] is True
    assert capabilities["llm"] is True
    assert choose_workflow(settings) == ("clip", "ai")


async def test_select_segments_falls_back_when_video_has_no_speech() -> None:
    result = await SelectSegmentsNode().run(
        None,
        {
            "data": {"duration": 169.0, "segments": []},
            "params": {
                "max_clips": 3,
                "min_seconds": 15,
                "max_seconds": 60,
                "model_ref": "",
            },
        },
    )
    assert len(result["segments"]) >= 1
    assert result["warning"] == "未识别到可用人声，已自动使用规则选段"
    assert result["segments"][0]["end"] > result["segments"][0]["start"]


async def test_select_segments_passes_user_brief_to_model(monkeypatch) -> None:
    captured = {}

    class FakeChat:
        async def chat(self, messages, **options):
            captured["prompt"] = messages[-1].content
            return ChatResult(
                text=(
                    '[{"start":0,"end":20,"title":"打斗高光",'
                    '"reason":"符合用户要求","score":0.9}]'
                ),
                model="fake-model",
            )

    monkeypatch.setattr(
        "app.nodes.ai.build_chat_model",
        lambda _model_ref=None: FakeChat(),
    )
    result = await SelectSegmentsNode().run(
        None,
        {
            "data": {
                "duration": 60.0,
                "segments": [{"start": 0, "end": 20, "text": "一段打斗内容"}],
            },
            "params": {
                "max_clips": 3,
                "min_seconds": 15,
                "max_seconds": 60,
            },
            "job_params": {
                "brief": "优先保留打斗高光，避开片头",
            },
        },
    )
    assert "优先保留打斗高光，避开片头" in captured["prompt"]
    assert result["segments"][0]["start"] == 0.0
