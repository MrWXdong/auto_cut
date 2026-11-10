from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.gateway.base import ChatMessage
from app.gateway.factory import build_chat_model
from app.studio.store import StudioStore

SYSTEM_PROMPT = (
    "你是短视频分镜导演。把口播稿拆成可执行的镜头清单。"
    "只输出 JSON，不要 Markdown、解释或代码块。"
)


def _fallback_scenes(script_body: str) -> list[dict[str, Any]]:
    parts = [
        part.strip()
        for part in re.split(r"(?<=[。！？!?])|[\r\n]+", script_body)
        if part.strip()
    ]
    parts = parts or [script_body.strip() or "开场镜头"]
    parts = parts[:7]
    shots = ["全景", "中景", "特写"]
    cameras = ["缓慢推进", "平稳横移", "固定机位", "轻微拉远"]
    transitions = ["淡入", "直接切换", "叠化", "淡出"]
    return [
        {
            "index": index + 1,
            "duration": 3 if index < 3 else 4,
            "shot": shots[index % len(shots)],
            "camera": cameras[index % len(cameras)],
            "voiceover": text,
            "visual_prompt": f"与口播内容匹配的画面：{text}",
            "transition": transitions[index % len(transitions)],
        }
        for index, text in enumerate(parts)
    ]


def _parse_scenes(text: str) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    payload = json.loads(cleaned)
    raw_scenes = payload.get("scenes") if isinstance(payload, dict) else None
    if not isinstance(raw_scenes, list):
        raise ValueError("storyboard response has no scenes")

    scenes = []
    for index, scene in enumerate(raw_scenes[:10], start=1):
        if not isinstance(scene, dict):
            continue
        duration = float(scene.get("duration") or 3)
        scenes.append(
            {
                "index": int(scene.get("index") or index),
                "duration": max(1.0, min(duration, 15.0)),
                "shot": str(scene.get("shot") or "中景"),
                "camera": str(scene.get("camera") or "固定机位"),
                "voiceover": str(scene.get("voiceover") or ""),
                "visual_prompt": str(scene.get("visual_prompt") or ""),
                "transition": str(scene.get("transition") or "直接切换"),
            }
        )
    if not scenes:
        raise ValueError("storyboard response is empty")
    return scenes


async def build_storyboard(
    studio: StudioStore,
    project_id: str,
    script_id: str,
    script_body: str,
) -> dict[str, Any]:
    model = build_chat_model()
    provider = "local"
    model_name = ""
    scenes: list[dict[str, Any]]
    if model is None:
        scenes = _fallback_scenes(script_body)
    else:
        result = await model.chat(
            [
                ChatMessage(role="system", content=SYSTEM_PROMPT),
                ChatMessage(
                    role="user",
                    content=(
                        "根据下面的口播稿生成 3-7 个镜头，字段必须为：\n"
                        '{"scenes":[{"index":1,"duration":3,"shot":"中景",'
                        '"camera":"缓慢推进","voiceover":"该镜头配音",'
                        '"visual_prompt":"该镜头画面提示词","transition":"淡入"}]}\n\n'
                        f"口播稿：\n{script_body}"
                    ),
                ),
            ],
            temperature=0.3,
        )
        provider = model.endpoint.provider
        model_name = result.model
        try:
            scenes = _parse_scenes(result.text)
        except (ValueError, json.JSONDecodeError):
            scenes = _fallback_scenes(script_body)
            provider = f"{provider}:fallback"

    payload = {
        "script_id": script_id,
        "provider": provider,
        "model": model_name,
        "scenes": scenes,
    }
    filename = f"storyboard-{uuid.uuid4().hex[:10]}.json"
    storage_key = f"projects/{project_id}/assets/{filename}"
    root = studio.work_root.resolve()
    target = (root / storage_key).resolve()
    if not target.is_relative_to(root):
        raise ValueError("invalid storyboard storage path")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    target.write_text(text, encoding="utf-8")
    asset = studio.add_asset(
        project_id,
        filename,
        storage_key,
        len(text.encode("utf-8")),
        {
            "provider": provider,
            "model": model_name,
            "script_id": script_id,
            "scene_count": len(scenes),
        },
    )
    return {
        "asset_id": asset["id"],
        "filename": filename,
        "script_id": script_id,
        "provider": provider,
        "model": model_name,
        "scenes": scenes,
    }
