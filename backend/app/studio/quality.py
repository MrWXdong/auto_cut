from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

QUALITY_PRESETS: dict[str, dict[str, Any]] = {
    "draft": {
        "label": "草稿",
        "image_size": (720, 1280),
        "candidates": 1,
        "scene_count": 3,
        "min_score": 50,
    },
    "standard": {
        "label": "标准",
        "image_size": (1080, 1920),
        "candidates": 2,
        "scene_count": 5,
        "min_score": 65,
    },
    "high": {
        "label": "高质量",
        "image_size": (1440, 2560),
        "candidates": 3,
        "scene_count": 7,
        "min_score": 75,
    },
}


def preset(name: str | None) -> dict[str, Any]:
    return QUALITY_PRESETS.get(name or "standard", QUALITY_PRESETS["standard"])


@dataclass
class QualityReport:
    score: int
    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "checks": self.checks,
        }


def check_text(
    content: str,
    required_keywords: list[str] | None = None,
    banned_words: list[str] | None = None,
    min_chars: int = 10,
) -> QualityReport:
    checks: list[dict[str, Any]] = []
    score = 100

    length = len(content.strip())
    length_ok = length >= min_chars
    checks.append(
        {
            "name": "length",
            "ok": length_ok,
            "detail": f"{length} 字符，最低 {min_chars}",
        }
    )
    if not length_ok:
        score -= 40

    for word in banned_words or []:
        if word and word in content:
            score -= 25
            checks.append(
                {"name": "banned_word", "ok": False, "detail": f"包含禁用词：{word}"}
            )

    missing = [
        word for word in (required_keywords or []) if word and word not in content
    ]
    if missing:
        score -= min(30, len(missing) * 10)
        checks.append(
            {
                "name": "required_keywords",
                "ok": False,
                "detail": "缺少：" + "、".join(missing),
            }
        )

    score = max(0, score)
    return QualityReport(score=score, passed=score >= 60, checks=checks)


def _svg_size(text: str) -> tuple[int, int]:
    width = re.search(r'width="(\d+)"', text)
    height = re.search(r'height="(\d+)"', text)
    return (
        int(width.group(1)) if width else 0,
        int(height.group(1)) if height else 0,
    )


def check_asset(
    path: Path,
    kind: str,
    required_keywords: list[str] | None = None,
    banned_words: list[str] | None = None,
) -> QualityReport:
    if not path.is_file():
        return QualityReport(0, False, [{"name": "file", "ok": False, "detail": "文件不存在"}])

    size = path.stat().st_size
    if kind == "image" and path.suffix.lower() == ".svg":
        text = path.read_text(encoding="utf-8", errors="ignore")
        width, height = _svg_size(text)
        min_side = min(width, height)
        checks = [
            {
                "name": "dimensions",
                "ok": min_side >= 720,
                "detail": f"{width}x{height}",
            },
            {"name": "file_size", "ok": size > 0, "detail": f"{size} bytes"},
        ]
        score = 40
        if min_side >= 720:
            score += 20
        if min_side >= 1080:
            score += 15
        if min_side >= 1440:
            score += 15
        if size > 0:
            score += 10
        return QualityReport(score=min(100, score), passed=score >= 60, checks=checks)

    if kind in {"file", "image"} and size < 500_000:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = ""
        if text:
            return check_text(text, required_keywords, banned_words)

    checks = [{"name": "file_size", "ok": size > 0, "detail": f"{size} bytes"}]
    score = 70 if size > 0 else 0
    if size > 1_000_000:
        score = 90
    return QualityReport(score=score, passed=score >= 60, checks=checks)
