from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.gateway.base import ChatMessage
from app.gateway.factory import build_chat_model
from app.rag.service import RagService
from app.rag.store import RagStore
from app.service import JobService
from app.skills import PromptSkill
from app.studio.executors import execute_module
from app.studio.importer import import_asset as import_asset_from_url
from app.studio.importer import preview_asset
from app.studio.store import StudioStore


@dataclass
class ToolOutcome:
    tool: str
    reply: str
    data: dict[str, Any] = field(default_factory=dict)
    files: list[dict[str, Any]] = field(default_factory=list)
    ok: bool = True


def route_tool(message: str) -> str:
    if "http://" in message or "https://" in message:
        if any(keyword in message for keyword in ("下载", "导入", "扒", "保存")):
            return "import_material"
        return "preview_material"
    if any(keyword in message for keyword in ("知识库", "资料", "文档里", "根据文档")):
        return "search_knowledge"
    if any(keyword in message for keyword in ("分镜", "镜头")):
        return "generate_storyboard"
    if any(keyword in message for keyword in ("封面", "图片", "海报", "生图")):
        return "generate_image"
    if any(keyword in message for keyword in ("配音", "音频", "朗读", "tts")):
        return "generate_audio"
    if any(keyword in message for keyword in ("脚本", "文案", "口播", "提示词")):
        return "generate_script"
    if any(
        keyword in message
        for keyword in ("字幕", "srt", "文件", "导出", "markdown", "md", "json", "csv", "表格")
    ):
        return "write_file"
    if any(keyword in message for keyword in ("剪辑", "切片", "成片", "视频")):
        return "create_edit_job"
    return "chat"


def _file_entry(project_id: str, asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": asset["filename"],
        "asset_id": asset["id"],
        "url": f"/api/v1/projects/{project_id}/assets/{asset['id']}/file",
    }


def _save_text_file(
    studio: StudioStore,
    project_id: str,
    filename: str,
    content: str,
) -> dict[str, Any]:
    token = uuid.uuid4().hex[:10]
    suffix = Path(filename).suffix or ".md"
    storage_key = f"projects/{project_id}/assets/{token}{suffix}"
    path = studio.work_root / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return studio.add_asset(
        project_id,
        filename,
        storage_key,
        len(content.encode("utf-8")),
        {"provider": "agent", "kind": "generated"},
    )


def _file_extension(message: str) -> str:
    lower = message.lower()
    if "srt" in lower or "字幕" in message:
        return ".srt"
    if "json" in lower:
        return ".json"
    if "csv" in lower or "表格" in message:
        return ".csv"
    if "txt" in lower or "纯文本" in message:
        return ".txt"
    return ".md"


async def _llm_text(model_ref: str | None, system: str, user: str) -> str | None:
    model = build_chat_model(model_ref)
    if model is None:
        return None
    result = await model.chat(
        [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
        temperature=0.4,
    )
    return result.text.strip() or None


async def execute_tool(
    studio: StudioStore,
    rag: RagStore,
    job_service: JobService,
    tool: str,
    message: str,
    project_id: str | None,
    knowledge_base_id: str | None,
    model_ref: str | None,
) -> ToolOutcome:
    quality = (
        "high"
        if any(keyword in message for keyword in ("高质量", "高清", "精细"))
        else "standard"
    )

    if tool == "search_knowledge":
        kb_id = knowledge_base_id
        if not kb_id:
            kbs = rag.list_kbs()
            kb_id = kbs[0]["id"] if kbs else None
        if not kb_id:
            return ToolOutcome(tool, "还没有知识库，先在知识库页上传文档。")
        result = RagService(rag).search(kb_id, message, requested_top_k=6)
        if not result.hits:
            return ToolOutcome(tool, "知识库里没有找到相关内容。", {"hits": []})
        return ToolOutcome(
            tool,
            "根据知识库：\n" + result.context,
            {
                "hits": result.hits,
                "context": result.context,
                "tokens": result.tokens,
                "top_k": result.top_k,
            },
        )

    if tool == "generate_script":
        platform = next(
            (item for item in ("抖音", "小红书", "视频号", "淘宝") if item in message),
            "抖音",
        )
        style = "测评" if "测评" in message else "口播"
        style_profile = studio.effective_style(project_id)
        if style_profile:
            if style_profile.get("prompt"):
                style += f"；风格要求：{style_profile['prompt']}"
            if style_profile.get("shot_rhythm"):
                style += f"；节奏：{style_profile['shot_rhythm']}"
        result = await PromptSkill(build_chat_model(model_ref)).run(
            {},
            {
                "product": message,
                "platform": platform,
                "style": style,
                "quality": quality,
                "task": "script",
            },
        )
        body = str(result.get("prompt") or "").strip()
        script = studio.create_script(message[:40] or "对话脚本", body, project_id, ["chat"])
        files = []
        if project_id:
            asset = _save_text_file(studio, project_id, "script.md", body)
            files.append(_file_entry(project_id, asset))
        return ToolOutcome(
            tool,
            body,
            {"script_id": script["id"], "shell": bool(result.get("shell"))},
            files,
        )

    if tool in {"generate_storyboard", "generate_image", "generate_audio"}:
        if not project_id:
            return ToolOutcome(
                tool,
                "先在项目页创建或选择一个项目，再让我生成文件。",
            )
        module = {
            "generate_storyboard": ("storyboard", "auto"),
            "generate_image": ("image", "cover"),
            "generate_audio": ("audio", "tts"),
        }[tool]
        outcome = await execute_module(
            studio,
            module[0],
            module[1],
            message,
            {"quality": quality},
            project_id,
        )
        result = outcome.get("result") or {}
        asset_id = result.get("asset_id")
        files = []
        if asset_id:
            asset = studio.get_asset(asset_id)
            if asset is not None:
                files.append(_file_entry(project_id, asset))
        reply = result.get("note") or "已生成。"
        return ToolOutcome(tool, reply, result, files, outcome["status"] != "failed")

    if tool == "write_file":
        if not project_id:
            return ToolOutcome(tool, "先在项目页创建或选择一个项目，再生成文件。")
        extension = _file_extension(message)
        generated = await _llm_text(
            model_ref,
            "你是内容生产助手，只输出可直接保存的文件内容，不要解释。",
            f"用户要求：{message}\n目标格式：{extension}",
        )
        content = generated or (
            f"# 云流影生成文件\n\n用户需求：{message}\n\n"
            "接入模型后会输出完整内容。\n"
        )
        asset = _save_text_file(studio, project_id, f"yunliuying{extension}", content)
        return ToolOutcome(
            tool,
            f"已生成 {asset['filename']}，可以直接下载。",
            {"asset_id": asset["id"], "format": extension},
            [_file_entry(project_id, asset)],
        )

    if tool == "create_edit_job":
        if not project_id:
            return ToolOutcome(tool, "先在项目页创建或选择一个项目，再创建剪辑任务。")
        assets = studio.list_assets(project_id)
        video = next((item for item in assets if item["kind"] == "video"), None)
        if video is None:
            return ToolOutcome(tool, "项目里还没有视频素材，先在素材页上传一个视频。")
        path = (studio.work_root / video["storage_key"]).resolve()
        job = job_service.create_job(
            workflow="quick_cut",
            input_path=path,
            params={
                "project_id": project_id,
                "asset_id": video["id"],
                "mode": "rule",
                "count": 3,
                "aspects": ["9:16"],
            },
        )
        return ToolOutcome(
            tool,
            f"剪辑任务已创建：{job.id}，到任务页查看进度。",
            {"job_id": job.id},
        )

    if tool == "import_material":
        if not project_id:
            return ToolOutcome(tool, "先在项目页创建或选择一个项目，再导入素材。")
        match = re.search(r"https?://\S+", message)
        if match is None:
            return ToolOutcome(tool, "没有识别到有效链接。")
        url = match.group(0).rstrip("，。！？)")
        try:
            asset = await import_asset_from_url(studio, project_id, url)
        except Exception as exc:
            return ToolOutcome(tool, f"素材导入失败：{exc}", ok=False)
        return ToolOutcome(
            tool,
            f"已导入素材 {asset['filename']}，可以直接下载或用于剪辑。",
            {"asset_id": asset["id"], "url": url},
            [_file_entry(project_id, asset)],
        )

    if tool == "preview_material":
        if not project_id:
            return ToolOutcome(tool, "先在项目页创建或选择一个项目，再解析素材。")
        match = re.search(r"https?://\S+", message)
        if match is None:
            return ToolOutcome(tool, "没有识别到有效链接。")
        url = match.group(0).rstrip("，。！？)")
        try:
            preview = await preview_asset(studio, project_id, url)
        except Exception as exc:
            return ToolOutcome(tool, f"素材解析失败：{exc}", ok=False)
        size = int(preview.get("size_bytes") or 0)
        duration = float(preview.get("duration") or 0)
        size_text = f"{max(1, round(size / 1024))} KB" if size else "未知大小"
        duration_text = f"{round(duration)} 秒" if duration else "未知时长"
        return ToolOutcome(
            tool,
            f"解析到：{preview.get('title')}（{preview.get('kind')}，"
            f"{size_text}，{duration_text}）。到素材页确认是否下载。",
            preview,
        )

    reply = await _llm_text(
        model_ref,
        "你是云流影的内容生产助手，回答简洁。"
        "必要时告诉用户可以生成脚本、分镜、封面、配音、字幕或创建剪辑任务。",
        message,
    )
    if reply is None:
        reply = (
            "我可以帮你生成脚本、分镜、封面、配音、字幕文件，或创建剪辑任务。"
            "先在项目页选择项目，再告诉我具体需求。"
        )
    return ToolOutcome("chat", reply)
