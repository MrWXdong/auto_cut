from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.commands import CommandError, run_command
from app.studio.store import StudioStore

COMPLIANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS compliance_reports (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT,
    asset_id TEXT,
    platform TEXT NOT NULL DEFAULT '抖音',
    content_type TEXT NOT NULL DEFAULT 'text',
    score INTEGER NOT NULL DEFAULT 100,
    level TEXT NOT NULL DEFAULT 'pass',
    summary TEXT NOT NULL DEFAULT '',
    issues_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_compliance_reports_tenant
    ON compliance_reports (tenant_id, created_at DESC);
"""

RULES: list[dict[str, Any]] = [
    {
        "code": "ad_absolute",
        "category": "广告法",
        "severity": "critical",
        "words": ("国家级", "最高级", "最佳", "第一品牌", "绝无仅有", "万能", "唯一"),
        "message": "使用了广告法高风险绝对化用语",
        "suggestion": "改成可证明、有限定条件的表达，例如“目前使用体验较好”。",
    },
    {
        "code": "medical_claim",
        "category": "医疗功效",
        "severity": "critical",
        "words": ("治疗", "治愈", "根治", "消炎", "抗癌", "降血压", "包治"),
        "message": "出现医疗功效或疾病治疗承诺",
        "suggestion": "删除治疗、治愈类表述，改为护肤或使用感受描述。",
    },
    {
        "code": "financial_claim",
        "category": "金融承诺",
        "severity": "critical",
        "words": ("稳赚不赔", "保本保收益", "零风险", "高收益", "暴利"),
        "message": "出现收益保证或无风险承诺",
        "suggestion": "删除保本、稳赚和高收益承诺，补充风险提示。",
    },
    {
        "code": "exaggeration",
        "category": "夸大宣传",
        "severity": "high",
        "words": ("100%", "绝对", "全网最低", "销量第一", "顶级", "史无前例"),
        "message": "出现难以证明的夸大宣传",
        "suggestion": "补充数据来源和适用范围，或改成更克制的描述。",
    },
    {
        "code": "traffic_diversion",
        "category": "平台引流",
        "severity": "medium",
        "words": ("加微信", "加V", "私信领", "扫码", "二维码"),
        "message": "可能触发平台站外引流审核",
        "suggestion": "改成平台内合规的互动或主页引导。",
    },
]

SEVERITY_WEIGHTS = {"critical": 25, "high": 15, "medium": 8, "low": 3}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _issue(
    code: str,
    category: str,
    severity: str,
    message: str,
    suggestion: str,
    evidence: str = "",
) -> dict[str, str]:
    return {
        "code": code,
        "category": category,
        "severity": severity,
        "message": message,
        "suggestion": suggestion,
        "evidence": evidence,
    }


def _score(issues: list[dict[str, str]]) -> int:
    score = 100
    for item in issues:
        score -= SEVERITY_WEIGHTS.get(item.get("severity", "low"), 3)
    return max(0, score)


def _level(score: int, issues: list[dict[str, str]]) -> str:
    if any(item.get("severity") == "critical" for item in issues) or score < 60:
        return "fail"
    if issues:
        return "warn"
    return "pass"


def _normalize_text(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class ComplianceStore:
    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(COMPLIANCE_SCHEMA)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def save_report(
        self,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        report_id = uuid.uuid4().hex[:12]
        now = _now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO compliance_reports (
                    id, tenant_id, project_id, asset_id, platform,
                    content_type, score, level, summary, issues_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    tenant_id,
                    values.get("project_id"),
                    values.get("asset_id"),
                    str(values.get("platform") or "抖音"),
                    str(values.get("content_type") or "text"),
                    int(values.get("score") or 0),
                    str(values.get("level") or "pass"),
                    str(values.get("summary") or ""),
                    json.dumps(values.get("issues") or [], ensure_ascii=False),
                    now,
                ),
            )
            connection.commit()
        return self.get_report(report_id, tenant_id) or {}

    def get_report(self, report_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM compliance_reports WHERE id = ? AND tenant_id = ?",
                (report_id, tenant_id),
            ).fetchone()
        return self._report_dict(row) if row is not None else None

    def list_reports(
        self,
        tenant_id: str = "demo",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM compliance_reports
                WHERE tenant_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (tenant_id, max(1, min(limit, 200))),
            ).fetchall()
        return [self._report_dict(row) for row in rows]

    def delete_report(self, report_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM compliance_reports WHERE id = ? AND tenant_id = ?",
                (report_id, tenant_id),
            )
            connection.commit()
        return cursor.rowcount == 1

    @staticmethod
    def _report_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["issues"] = json.loads(data.pop("issues_json") or "[]")
        return data


class ComplianceService:
    def __init__(self, store: ComplianceStore) -> None:
        self._store = store

    def list_reports(self, tenant_id: str = "demo", limit: int = 50) -> list[dict[str, Any]]:
        return self._store.list_reports(tenant_id, limit)

    def delete_report(self, report_id: str, tenant_id: str = "demo") -> bool:
        return self._store.delete_report(report_id, tenant_id)

    async def check(
        self,
        studio: StudioStore,
        *,
        platform: str,
        project_id: str | None = None,
        asset_id: str | None = None,
        text: str = "",
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        text = text.strip()
        probe: dict[str, Any] | None = None
        file_hash = ""

        if text:
            issues.extend(self._check_text_rules(text))
            brand = studio.get_brand_kit(tenant_id)
            if brand.get("configured") and brand.get("brand_name"):
                if str(brand["brand_name"]) not in text:
                    issues.append(
                        _issue(
                            "brand_missing",
                            "品牌规范",
                            "low",
                            "文案中没有出现配置的品牌名称",
                            "确认是否需要在开头或结尾补充品牌露出。",
                            str(brand["brand_name"]),
                        )
                    )
            if project_id:
                issues.extend(self._check_duplicate(studio, project_id, text, tenant_id))

        if asset_id:
            asset = studio.get_asset(asset_id, tenant_id)
            if asset is None or (project_id and asset["project_id"] != project_id):
                raise ValueError("素材不存在")
            if asset["kind"] != "video":
                raise ValueError("当前成片质检仅支持视频素材")
            path = (studio.work_root / asset["storage_key"]).resolve()
            if not path.is_relative_to(studio.work_root.resolve()) or not path.is_file():
                raise ValueError("素材文件不存在")
            file_hash = _file_sha256(path)
            probe = await self._probe_video(path)
            issues.extend(self._check_video_rules(probe, platform))
            if not project_id:
                project_id = str(asset["project_id"])

        score = _score(issues)
        level = _level(score, issues)
        content_type = "mixed" if text and asset_id else ("video" if asset_id else "text")
        summary = {
            "pass": "质检通过，未发现明显风险。",
            "warn": "发现一些可优化项，建议修改后再发布。",
            "fail": "发现高风险问题，建议修改后重新质检。",
        }[level]
        report = self._store.save_report(
            {
                "project_id": project_id,
                "asset_id": asset_id,
                "platform": platform,
                "content_type": content_type,
                "score": score,
                "level": level,
                "summary": summary,
                "issues": issues,
                "file_hash": file_hash,
                "media": probe,
            },
            tenant_id,
        )
        report["file_hash"] = file_hash
        report["media"] = probe
        return report

    def _check_text_rules(self, text: str) -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        lowered = text.lower()
        for rule in RULES:
            for word in rule["words"]:
                if str(word).lower() in lowered:
                    issues.append(
                        _issue(
                            str(rule["code"]),
                            str(rule["category"]),
                            str(rule["severity"]),
                            str(rule["message"]),
                            str(rule["suggestion"]),
                            str(word),
                        )
                    )
        return issues

    def _check_duplicate(
        self,
        studio: StudioStore,
        project_id: str,
        text: str,
        tenant_id: str,
    ) -> list[dict[str, str]]:
        normalized = _normalize_text(text)
        if len(normalized) < 20:
            return []
        for script in studio.list_scripts(project_id, tenant_id)[:200]:
            other = _normalize_text(str(script.get("body") or ""))
            if not other:
                continue
            ratio = SequenceMatcher(None, normalized, other).ratio()
            if ratio >= 0.85:
                return [
                    _issue(
                        "duplicate_text",
                        "重复内容",
                        "medium",
                        "文案与已有脚本高度相似",
                        "调整开头、案例或表达方式，避免平台判定重复内容。",
                        str(script.get("title") or script.get("id") or ""),
                    )
                ]
        return []

    async def _probe_video(self, path: Path) -> dict[str, Any]:
        settings = get_settings()
        try:
            raw = await run_command(
                [
                    settings.ffprobe_bin,
                    "-v",
                    "error",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    str(path),
                ],
                timeout=60,
            )
            payload = json.loads(raw)
        except (OSError, CommandError, json.JSONDecodeError):
            return await self._probe_video_with_ffmpeg(path)
        streams = payload.get("streams") or []
        video = next((item for item in streams if item.get("codec_type") == "video"), None)
        audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
        if video is None:
            raise ValueError("视频文件没有视频流")
        container = payload.get("format") or {}
        return {
            "duration": float(container.get("duration") or 0),
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "video_codec": str(video.get("codec_name") or ""),
            "has_audio": audio is not None,
            "audio_codec": str(audio.get("codec_name") or "") if audio else "",
            "size_bytes": int(container.get("size") or path.stat().st_size),
        }

    async def _probe_video_with_ffmpeg(self, path: Path) -> dict[str, Any]:
        settings = get_settings()
        try:
            await run_command(
                [settings.ffmpeg_bin, "-hide_banner", "-i", str(path)],
                timeout=60,
            )
            text = ""
        except CommandError as exc:
            text = exc.stderr
        except OSError as exc:
            raise ValueError("视频信息读取失败，请确认 FFmpeg 可用") from exc
        duration = 0.0
        duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
        if duration_match:
            hours, minutes, seconds = duration_match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        video_line = next((line for line in text.splitlines() if "Video:" in line), "")
        size_match = re.search(r"(\d{2,5})x(\d{2,5})", video_line)
        if not size_match:
            raise ValueError("视频信息读取失败，未检测到视频流")
        width, height = size_match.groups()
        codec_match = re.search(r"Video:\s*([^\s,]+)", video_line)
        return {
            "duration": duration,
            "width": int(width),
            "height": int(height),
            "video_codec": codec_match.group(1) if codec_match else "",
            "has_audio": "Audio:" in text,
            "audio_codec": "",
            "size_bytes": path.stat().st_size,
        }

    def _check_video_rules(
        self,
        probe: dict[str, Any],
        platform: str,
    ) -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        duration = float(probe.get("duration") or 0)
        width = int(probe.get("width") or 0)
        height = int(probe.get("height") or 0)
        if duration <= 0:
            issues.append(
                _issue(
                    "video_duration_invalid",
                    "视频规格",
                    "critical",
                    "视频时长无效",
                    "重新导出并确认文件可以正常播放。",
                )
            )
        elif duration < 5:
            issues.append(
                _issue(
                    "video_too_short",
                    "视频规格",
                    "high",
                    "视频时长过短",
                    "短视频建议至少 10 秒，保留完整开头和结尾。",
                    f"{duration:.1f}s",
                )
            )
        elif duration > 180:
            issues.append(
                _issue(
                    "video_too_long",
                    "视频规格",
                    "medium",
                    "视频时长较长",
                    "根据发布平台考虑拆分或压缩节奏。",
                    f"{duration:.1f}s",
                )
            )
        if not probe.get("has_audio"):
            issues.append(
                _issue(
                    "video_no_audio",
                    "音轨",
                    "high",
                    "视频没有音轨",
                    "确认是否需要配音、字幕或背景音乐。",
                )
            )
        if width < 480 or height < 480:
            issues.append(
                _issue(
                    "video_low_resolution",
                    "视频规格",
                    "high",
                    "视频分辨率过低",
                    "建议至少导出 720p，竖屏推荐 1080x1920。",
                    f"{width}x{height}",
                )
            )
        vertical_platforms = {"抖音", "视频号", "小红书", "快手", "TikTok"}
        if platform in vertical_platforms and height <= width:
            issues.append(
                _issue(
                    "video_aspect_ratio",
                    "画幅",
                    "medium",
                    f"{platform}更适合竖屏内容",
                    "建议导出 9:16 画幅，或确认横屏是否为有意设计。",
                    f"{width}x{height}",
                )
            )
        return issues
