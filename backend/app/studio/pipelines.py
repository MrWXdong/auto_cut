from __future__ import annotations

PIPELINE_TEMPLATES: list[dict[str, object]] = [
    {
        "id": "copy_to_video",
        "name": "文案到成片",
        "description": "脚本 -> 分镜 -> 生图 -> 音频 -> 渲染",
        "steps": [
            {"module": "copywriting", "mode": "script", "prompt": "生成口播脚本"},
            {"module": "storyboard", "mode": "auto", "prompt": "根据脚本拆分镜"},
            {"module": "image", "mode": "text2img", "prompt": "为每个镜头生成画面"},
            {"module": "audio", "mode": "tts", "prompt": "生成配音和字幕"},
            {"module": "render", "mode": "render", "prompt": "按分镜合成成片"},
        ],
    },
    {
        "id": "asset_to_video",
        "name": "素材到成片",
        "description": "素材 -> 字幕 -> 渲染",
        "steps": [
            {"module": "audio", "mode": "asr", "prompt": "识别素材语音"},
            {"module": "copywriting", "mode": "titles", "prompt": "根据内容生成标题和标签"},
            {"module": "render", "mode": "render", "prompt": "套用模板并导出"},
        ],
    },
    {
        "id": "cover_pack",
        "name": "封面与包装",
        "description": "文案 -> 生图 -> 封面",
        "steps": [
            {"module": "copywriting", "mode": "script", "prompt": "生成封面文案"},
            {"module": "image", "mode": "cover", "prompt": "生成封面图"},
        ],
    },
]

PIPELINE_TEMPLATE_BY_ID = {str(item["id"]): item for item in PIPELINE_TEMPLATES}
