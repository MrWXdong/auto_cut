from __future__ import annotations

MODULES: list[dict[str, object]] = [
    {
        "id": "copywriting",
        "name": "文案脚本",
        "group": "创作",
        "description": "脚本、标题、标签、分镜旁白",
        "modes": ["script", "titles", "tags"],
        "status": "ready",
    },
    {
        "id": "image",
        "name": "生图中台",
        "group": "创作",
        "description": "文生图、图生图、ControlNet、局部重绘、扩图、封面生成",
        "modes": ["text2img", "img2img", "controlnet", "inpaint", "outpaint", "cover"],
        "status": "shell",
    },
    {
        "id": "storyboard",
        "name": "分镜编排",
        "group": "创作",
        "description": "自动分镜、可视化编辑、镜头唤起生图",
        "modes": ["auto", "manual"],
        "status": "shell",
    },
    {
        "id": "audio",
        "name": "音频字幕",
        "group": "创作",
        "description": "ASR、TTS、BGM 卡点、降噪",
        "modes": ["asr", "tts", "bgm", "denoise"],
        "status": "shell",
    },
    {
        "id": "lora",
        "name": "LoRA 训练",
        "group": "创作",
        "description": "图集上传、训练任务、LoRA 库管理",
        "modes": ["train", "style"],
        "status": "shell",
    },
    {
        "id": "render",
        "name": "渲染导出",
        "group": "生产",
        "description": "FFmpeg 异步渲染、多规格导出",
        "modes": ["render", "export"],
        "status": "ready",
    },
    {
        "id": "batch",
        "name": "矩阵批量",
        "group": "生产",
        "description": "批量创作、矩阵分发、多项目并行",
        "modes": ["batch"],
        "status": "shell",
    },
]

MODULE_BY_ID = {str(item["id"]): item for item in MODULES}
