from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.gateway.base import ChatMessage, ChatModel
from app.studio.trends import TrendStore, _direction_keywords

logger = logging.getLogger(__name__)

CALENDAR_SCHEMA = """
CREATE TABLE IF NOT EXISTS content_calendar (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    project_id TEXT,
    plan_date TEXT NOT NULL,
    title TEXT NOT NULL,
    angle TEXT NOT NULL DEFAULT '',
    hook TEXT NOT NULL DEFAULT '',
    format TEXT NOT NULL DEFAULT '口播',
    platform TEXT NOT NULL DEFAULT '抖音',
    status TEXT NOT NULL DEFAULT 'planned',
    source TEXT NOT NULL DEFAULT 'ai',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_content_calendar_date
    ON content_calendar (tenant_id, plan_date, status);
"""

CALENDAR_FIELDS = {
    "project_id",
    "plan_date",
    "title",
    "angle",
    "hook",
    "format",
    "platform",
    "status",
    "source",
    "notes",
}

LOCAL_TOPICS: list[dict[str, str]] = [
    {
        "title": "{direction}新手最容易踩的 3 个坑",
        "angle": "用反常识开头，先讲错误做法，再给正确方法",
        "hook": "如果你刚开始做{direction}，这三个坑千万别踩",
        "format": "口播",
    },
    {
        "title": "一条视频讲清{direction}值不值得做",
        "angle": "从成本、收益、适用人群三个维度做判断",
        "hook": "先说结论：不是所有人都适合做{direction}",
        "format": "测评",
    },
    {
        "title": "{direction}真实体验：优点和缺点都讲",
        "angle": "第一视角记录真实使用过程，保留细节",
        "hook": "用了这么久，我终于敢说它的真实感受",
        "format": "Vlog",
    },
    {
        "title": "{direction}的 5 个隐藏玩法",
        "angle": "清单式盘点，信息密度高",
        "hook": "第 3 个玩法，很多人到现在都不知道",
        "format": "清单",
    },
    {
        "title": "为什么别人做{direction}更容易起量",
        "angle": "拆解选题、开头、节奏和评论区需求",
        "hook": "同样做{direction}，差距可能从第一句话就开始了",
        "format": "教程",
    },
    {
        "title": "用{direction}解决一个真实问题",
        "angle": "从一个具体痛点切入，展示解决前后对比",
        "hook": "这个问题困扰我很久，直到我换了思路",
        "format": "剧情",
    },
    {
        "title": "{direction}本周热点和机会点",
        "angle": "结合热榜、节点和用户讨论做趋势判断",
        "hook": "这周{direction}有一个很明显的变化",
        "format": "盘点",
    },
]


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _extract_json(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    starts = [index for index in (cleaned.find("["), cleaned.find("{")) if index >= 0]
    if not starts:
        return None
    start = min(starts)
    end = max(cleaned.rfind("]"), cleaned.rfind("}"))
    if end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


class CalendarStore:
    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(CALENDAR_SCHEMA)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def list_items(
        self,
        tenant_id: str = "demo",
        start_date: str | None = None,
        end_date: str | None = None,
        status: str | None = None,
        project_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM content_calendar WHERE tenant_id = ?"
        args: list[Any] = [tenant_id]
        if start_date:
            query += " AND plan_date >= ?"
            args.append(start_date)
        if end_date:
            query += " AND plan_date <= ?"
            args.append(end_date)
        if status:
            query += " AND status = ?"
            args.append(status)
        if project_id:
            query += " AND project_id = ?"
            args.append(project_id)
        query += " ORDER BY plan_date, created_at LIMIT ?"
        args.append(max(1, min(int(limit), 1000)))
        with closing(self._connect()) as connection:
            rows = connection.execute(query, args).fetchall()
        return [dict(row) for row in rows]

    def get_item(self, item_id: str, tenant_id: str = "demo") -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM content_calendar WHERE id = ? AND tenant_id = ?",
                (item_id, tenant_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_item(
        self,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any]:
        title = str(values.get("title") or "").strip()
        plan_date = str(values.get("plan_date") or "").strip()
        if not title or not plan_date:
            raise ValueError("选题标题和日期不能为空")
        item_id = uuid.uuid4().hex[:12]
        now = _now()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO content_calendar (
                    id, tenant_id, project_id, plan_date, title, angle, hook,
                    format, platform, status, source, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    tenant_id,
                    values.get("project_id"),
                    plan_date,
                    title,
                    str(values.get("angle") or ""),
                    str(values.get("hook") or ""),
                    str(values.get("format") or "口播"),
                    str(values.get("platform") or "抖音"),
                    str(values.get("status") or "planned"),
                    str(values.get("source") or "ai"),
                    str(values.get("notes") or ""),
                    now,
                    now,
                ),
            )
            connection.commit()
        return self.get_item(item_id, tenant_id) or {}

    def bulk_create(
        self,
        items: list[dict[str, Any]],
        tenant_id: str = "demo",
    ) -> list[dict[str, Any]]:
        return [self.create_item(item, tenant_id) for item in items]

    def update_item(
        self,
        item_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        fields: list[str] = []
        args: list[Any] = []
        for key in CALENDAR_FIELDS:
            if key in values and values[key] is not None:
                fields.append(f"{key} = ?")
                args.append(str(values[key]))
        if not fields:
            return self.get_item(item_id, tenant_id)
        fields.append("updated_at = ?")
        args.append(_now())
        args.extend([item_id, tenant_id])
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                f"UPDATE content_calendar SET {', '.join(fields)} "
                "WHERE id = ? AND tenant_id = ?",
                args,
            )
            connection.commit()
        return self.get_item(item_id, tenant_id) if cursor.rowcount == 1 else None

    def delete_item(self, item_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM content_calendar WHERE id = ? AND tenant_id = ?",
                (item_id, tenant_id),
            )
            connection.commit()
        return cursor.rowcount == 1


class CalendarService:
    def __init__(
        self,
        store: CalendarStore,
        chat_model: ChatModel | None = None,
        trend_store: TrendStore | None = None,
    ) -> None:
        self._store = store
        self._chat_model = chat_model
        self._trend_store = trend_store

    def list_items(
        self,
        tenant_id: str = "demo",
        **filters: object,
    ) -> list[dict[str, Any]]:
        return self._store.list_items(tenant_id, **filters)

    def update_item(
        self,
        item_id: str,
        values: dict[str, Any],
        tenant_id: str = "demo",
    ) -> dict[str, Any] | None:
        return self._store.update_item(item_id, values, tenant_id)

    def delete_item(self, item_id: str, tenant_id: str = "demo") -> bool:
        return self._store.delete_item(item_id, tenant_id)

    def _trend_context(self, direction: str) -> list[str]:
        if self._trend_store is None:
            return []
        titles: list[str] = []
        for source_id in ("weibo", "zhihu", "bilibili", "baidu", "douyin", "toutiao"):
            snapshot = self._trend_store.latest(source_id)
            if snapshot is None:
                continue
            for item in list(snapshot.get("items") or [])[:8]:
                title = str(item.get("title") or "").strip()
                if title:
                    titles.append(title)
        if not titles:
            return []
        keywords = _direction_keywords(direction)
        related = [
            title
            for title in titles
            if any(keyword in title.lower() for keyword in keywords)
        ]
        return related[:12]

    async def generate(
        self,
        direction: str,
        start_date: str,
        days: int,
        per_day: int,
        platforms: list[str],
        project_id: str | None = None,
        tenant_id: str = "demo",
    ) -> list[dict[str, Any]]:
        direction = direction.strip()
        if not direction:
            raise ValueError("内容方向不能为空")
        days = max(1, min(int(days), 90))
        per_day = max(1, min(int(per_day), 5))
        platforms = [item.strip() for item in platforms if item.strip()] or ["抖音"]
        start = date.fromisoformat(start_date)
        total = days * per_day
        trend_context = self._trend_context(direction)

        items: list[dict[str, Any]] = []
        if self._chat_model is not None:
            try:
                items = await self._generate_with_ai(
                    direction,
                    start,
                    days,
                    per_day,
                    platforms,
                    trend_context,
                )
            except Exception:
                logger.warning("calendar AI generation failed", exc_info=True)
        if len(items) < total:
            items.extend(self._local_items(direction, start, days, per_day, platforms))
        items = items[:total]
        for index, item in enumerate(items):
            item["project_id"] = project_id
            item["source"] = item.get("source") or "ai"
            item["platform"] = item.get("platform") or platforms[index % len(platforms)]
            item["plan_date"] = item.get("plan_date") or (
                start + timedelta(days=index // per_day)
            ).isoformat()
        return self._store.bulk_create(items, tenant_id)

    async def _generate_with_ai(
        self,
        direction: str,
        start: date,
        days: int,
        per_day: int,
        platforms: list[str],
        trend_context: list[str],
    ) -> list[dict[str, Any]]:
        assert self._chat_model is not None
        total = days * per_day
        end = start + timedelta(days=days - 1)
        context = "\n".join(f"- {title}" for title in trend_context) or "无"
        result = await self._chat_model.chat(
            [
                ChatMessage(
                    role="system",
                    content=(
                        "你是企业短视频内容策划。只输出 JSON 对象："
                        '{"items":[{"date":"YYYY-MM-DD","title":"",'
                        '"angle":"","hook":"","format":"","platform":""}]}。'
                        "不要输出 Markdown 或解释。"
                    ),
                ),
                ChatMessage(
                    role="user",
                    content=(
                        f"内容方向：{direction}\n"
                        f"日期范围：{start.isoformat()} 至 {end.isoformat()}\n"
                        f"每天 {per_day} 条，共 {total} 条。\n"
                        f"可选平台：{', '.join(platforms)}\n"
                        f"近期热点参考：\n{context}\n"
                        "每条包含具体标题、切入角度、开头钩子、内容形式。"
                        "标题要具体，不要重复，不要空泛。"
                    ),
                ),
            ],
            temperature=0.5,
            max_tokens=2400,
        )
        payload = _extract_json(result.text)
        rows = payload.get("items") if isinstance(payload, dict) else payload
        items: list[dict[str, Any]] = []
        if not isinstance(rows, list):
            return []
        for index, row in enumerate(rows[:total]):
            if not isinstance(row, dict) or not str(row.get("title") or "").strip():
                continue
            try:
                row_date = date.fromisoformat(str(row.get("date") or "")).isoformat()
            except ValueError:
                row_date = (start + timedelta(days=index // per_day)).isoformat()
            items.append(
                {
                    "plan_date": row_date,
                    "title": str(row.get("title") or "").strip()[:180],
                    "angle": str(row.get("angle") or "").strip()[:300],
                    "hook": str(row.get("hook") or "").strip()[:240],
                    "format": str(row.get("format") or "口播").strip()[:40],
                    "platform": str(
                        row.get("platform") or platforms[index % len(platforms)]
                    ).strip(),
                    "source": "ai",
                }
            )
        return items

    @staticmethod
    def _local_items(
        direction: str,
        start: date,
        days: int,
        per_day: int,
        platforms: list[str],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for day_index in range(days):
            for slot in range(per_day):
                template = LOCAL_TOPICS[(day_index * per_day + slot) % len(LOCAL_TOPICS)]
                items.append(
                    {
                        "plan_date": (start + timedelta(days=day_index)).isoformat(),
                        "title": template["title"].format(direction=direction),
                        "angle": template["angle"].format(direction=direction),
                        "hook": template["hook"].format(direction=direction),
                        "format": template["format"],
                        "platform": platforms[(day_index * per_day + slot) % len(platforms)],
                        "source": "template",
                    }
                )
        return items
