from __future__ import annotations

MODULE_COSTS: dict[str, dict[str, int]] = {
    "copywriting": {"script": 2, "titles": 1, "tags": 1, "default": 2},
    "image": {
        "text2img": 10,
        "img2img": 10,
        "controlnet": 15,
        "inpaint": 15,
        "outpaint": 15,
        "cover": 10,
        "default": 10,
    },
    "storyboard": {"auto": 5, "manual": 3, "default": 5},
    "audio": {"asr": 5, "tts": 8, "bgm": 3, "denoise": 3, "default": 5},
    "lora": {"train": 500, "style": 300, "default": 300},
    "render": {"render": 20, "export": 5, "default": 20},
    "batch": {"batch": 50, "default": 50},
}


def module_cost(module: str, mode: str, quality: str = "standard") -> int:
    table = MODULE_COSTS.get(module, {"default": 5})
    base = table.get(mode, table.get("default", 5))
    multiplier = {"draft": 0.5, "standard": 1.0, "high": 1.5}.get(quality, 1.0)
    return max(1, round(base * multiplier))


def workflow_cost(workflow: str, params: dict[str, object]) -> int:
    if workflow == "quick_cut":
        count = int(params.get("count") or 3)
        return 10 + max(1, count) * 20
    if workflow == "clip":
        clips = int(params.get("max_clips") or 5)
        return 20 + max(1, clips) * 30
    return 20
