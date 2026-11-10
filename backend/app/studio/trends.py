from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import re
import socket
import sqlite3
import time
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

from app.gateway.base import ChatMessage, ChatModel

logger = logging.getLogger(__name__)

TREND_SOURCES: dict[str, dict[str, str]] = {
    "weibo": {
        "name": "微博",
        "url": "https://weibo.com/ajax/side/hotSearch",
        "referer": "https://weibo.com/",
    },
    "zhihu": {
        "name": "知乎",
        "url": "https://api.zhihu.com/topstory/hot-list?limit=50",
        "referer": "https://www.zhihu.com/hot",
    },
    "bilibili": {
        "name": "B站",
        "url": "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all",
        "referer": "https://www.bilibili.com/",
    },
    "baidu": {
        "name": "百度",
        "url": "https://top.baidu.com/api/board?platform=wise&tab=realtime",
        "referer": "https://top.baidu.com/",
    },
    "douyin": {
        "name": "抖音",
        "url": "https://www.douyin.com/aweme/v1/web/hot/search/list/",
        "referer": "https://www.douyin.com/",
    },
    "toutiao": {
        "name": "今日头条",
        "url": "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
        "referer": "https://www.toutiao.com/",
    },
}

Fetcher = Callable[[dict[str, str]], Awaitable[Any]]

TREND_SCHEMA = """
CREATE TABLE IF NOT EXISTS trend_snapshots (
    source TEXT NOT NULL,
    source_name TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    items_json TEXT NOT NULL,
    PRIMARY KEY (source, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_trend_snapshot_latest
    ON trend_snapshots (source, updated_at DESC);

CREATE TABLE IF NOT EXISTS custom_trend_sources (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'demo',
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS idx_custom_trend_tenant
    ON custom_trend_sources (tenant_id, created_at);
"""


def _text(value: Any) -> str:
    return str(value or "").strip().strip("#")


def _number(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _item(
    source: str,
    rank: int,
    title: str,
    hot: Any,
    url: str,
) -> dict[str, object]:
    return {
        "rank": rank,
        "title": title,
        "hot": _number(hot),
        "url": url,
        "source": source,
        "source_name": TREND_SOURCES[source]["name"],
    }


def parse_weibo(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows = payload.get("data", {}).get("realtime", [])
    items = []
    for row in rows:
        title = _text(row.get("word") or row.get("note"))
        if not title:
            continue
        items.append(
            _item(
                "weibo",
                len(items) + 1,
                title,
                row.get("num") or row.get("raw_hot"),
                f"https://s.weibo.com/weibo?q=%23{quote(title)}%23",
            )
        )
    return items


def parse_zhihu(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows = payload.get("data", [])
    items = []
    for row in rows:
        target = row.get("target") or {}
        title = _text(target.get("title"))
        if not title:
            continue
        question_id = target.get("id")
        url = (
            f"https://www.zhihu.com/question/{question_id}"
            if question_id
            else "https://www.zhihu.com/hot"
        )
        items.append(
            _item(
                "zhihu",
                len(items) + 1,
                title,
                row.get("detail_text") or target.get("follower_count"),
                url,
            )
        )
    return items


def parse_bilibili(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows = payload.get("data", {}).get("list", [])
    items = []
    for row in rows:
        title = _text(row.get("title"))
        if not title:
            continue
        bvid = row.get("bvid") or ""
        items.append(
            _item(
                "bilibili",
                len(items) + 1,
                title,
                (row.get("stat") or {}).get("view"),
                f"https://www.bilibili.com/video/{bvid}" if bvid else "https://www.bilibili.com/",
            )
        )
    return items


def parse_baidu(payload: dict[str, Any]) -> list[dict[str, object]]:
    cards = payload.get("data", {}).get("cards", [])
    rows: list[dict[str, Any]] = []
    for card in cards:
        for entry in card.get("content") or []:
            nested = entry.get("content")
            if isinstance(nested, list):
                rows.extend(nested)
            else:
                rows.append(entry)
    items = []
    for row in rows:
        title = _text(row.get("word") or row.get("query"))
        if not title:
            continue
        items.append(
            _item(
                "baidu",
                len(items) + 1,
                title,
                row.get("hotScore"),
                str(row.get("url") or "https://top.baidu.com/board?tab=realtime"),
            )
        )
    return items


def parse_douyin(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows = (payload.get("data") or {}).get("word_list") or []
    items = []
    for row in rows:
        title = _text(row.get("word"))
        if not title:
            continue
        items.append(
            _item(
                "douyin",
                len(items) + 1,
                title,
                row.get("hot_value"),
                f"https://www.douyin.com/search/{quote(title)}",
            )
        )
    return items


def parse_toutiao(payload: dict[str, Any]) -> list[dict[str, object]]:
    rows = payload.get("data") or []
    items = []
    for row in rows:
        title = _text(row.get("Title"))
        if not title:
            continue
        items.append(
            _item(
                "toutiao",
                len(items) + 1,
                title,
                row.get("HotValue"),
                str(row.get("Url") or "https://www.toutiao.com/"),
            )
        )
    return items


PARSERS: dict[str, Callable[[dict[str, Any]], list[dict[str, object]]]] = {
    "weibo": parse_weibo,
    "zhihu": parse_zhihu,
    "bilibili": parse_bilibili,
    "baidu": parse_baidu,
    "douyin": parse_douyin,
    "toutiao": parse_toutiao,
}


class TrendFetchError(RuntimeError):
    pass


TITLE_KEYS = ("title", "name", "word", "keyword", "headline", "Title")
URL_KEYS = ("url", "link", "Url", "href")
HOT_KEYS = ("hot", "hot_value", "hotScore", "hotValue", "score", "view")
NAV_WORDS = (
    "首页",
    "登录",
    "注册",
    "下载",
    "客户端",
    "关于我们",
    "帮助",
    "隐私",
    "协议",
    "广告",
    "更多",
)

DIRECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "美妆": ("美妆", "护肤", "化妆", "彩妆", "面膜", "口红", "防晒", "成分", "抗老", "皮肤"),
    "母婴": ("母婴", "宝宝", "育儿", "婴儿", "奶粉", "儿童", "早教", "亲子", "幼儿园"),
    "数码": ("数码", "手机", "电脑", "相机", "耳机", "芯片", "AI", "科技", "测评"),
    "美食": ("美食", "餐厅", "探店", "做饭", "菜谱", "小吃", "咖啡", "奶茶", "火锅"),
    "职场": ("职场", "工作", "招聘", "面试", "打工人", "老板", "离职", "副业", "上班"),
    "教育": ("教育", "学习", "考试", "高考", "考研", "学校", "老师", "学生", "课程"),
    "健康": ("健康", "养生", "医院", "医生", "睡眠", "减脂", "健身", "疾病", "饮食"),
    "汽车": ("汽车", "新能源", "电车", "车型", "驾驶", "车主", "智驾", "车展"),
    "家居": ("家居", "装修", "家具", "收纳", "家电", "租房", "房子", "改造"),
    "游戏": ("游戏", "手游", "电竞", "玩家", "版本", "主机", "Steam", "赛事"),
    "影视": ("电影", "电视剧", "综艺", "演员", "导演", "票房", "热播", "剧情"),
    "旅游": ("旅游", "旅行", "景点", "酒店", "攻略", "机票", "自驾", "出游"),
    "财经": ("财经", "股票", "基金", "经济", "消费", "公司", "市场", "投资"),
    "穿搭": ("穿搭", "服装", "时尚", "衣服", "鞋", "包", "配饰", "秋冬"),
    "宠物": ("宠物", "猫", "狗", "铲屎官", "猫咪", "狗狗", "养宠"),
}

DIRECTION_STOPWORDS = {"内容", "视频", "热点", "方向", "账号", "平台", "运营", "自媒体"}


def _direction_keywords(direction: str) -> list[str]:
    normalized = re.sub(r"\s+", "", direction.strip().lower())
    if not normalized:
        return []
    keywords = {normalized}
    for key, values in DIRECTION_KEYWORDS.items():
        if key in normalized or normalized in key:
            keywords.add(key)
            keywords.update(values)
    for part in re.split(r"[,，、/|+;；]+", normalized):
        if len(part) >= 2:
            keywords.add(part)
    for chunk in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if 2 <= len(chunk) <= 8:
            keywords.add(chunk)
        for index in range(max(0, len(chunk) - 1)):
            keywords.add(chunk[index : index + 2])
    for word in re.findall(r"[a-z0-9]{2,}", normalized):
        keywords.add(word)
    keywords.difference_update(DIRECTION_STOPWORDS)
    return sorted(
        (word for word in keywords if len(word) >= 2),
        key=lambda word: (-len(word), word),
    )[:30]


def _parse_ai_keywords(text: str) -> list[str]:
    keywords: list[str] = []
    for token in re.split(r"[\n,，、;；|]+", text):
        token = re.sub(r"^[\s\d.\-*•、]+", "", token)
        token = token.strip(" \t\"'“”‘’：:")
        if not (2 <= len(token) <= 24):
            continue
        if token in DIRECTION_STOPWORDS or token in keywords:
            continue
        keywords.append(token)
    return keywords[:24]


def _parse_ai_expansion(text: str) -> tuple[list[str], list[dict[str, str]]]:
    payload: dict[str, Any] | None = None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = None
    if payload is None:
        return _parse_ai_keywords(text), []

    raw_keywords = payload.get("keywords") or []
    if isinstance(raw_keywords, str):
        keywords = _parse_ai_keywords(raw_keywords)
    elif isinstance(raw_keywords, list):
        keywords = _parse_ai_keywords(
            "、".join(str(item) for item in raw_keywords if item)
        )
    else:
        keywords = []

    suggestions: list[dict[str, str]] = []
    raw_topics = payload.get("topics") or []
    if isinstance(raw_topics, list):
        for item in raw_topics[:10]:
            if not isinstance(item, dict):
                continue
            title = _text(item.get("title"))
            if not title:
                continue
            suggestions.append(
                {
                    "title": title[:120],
                    "angle": _text(item.get("angle"))[:240],
                    "hook": _text(item.get("hook"))[:160],
                    "format": _text(item.get("format"))[:40],
                }
            )
    return keywords, suggestions


def validate_public_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("热点源只支持 http/https 链接")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("热点源链接缺少域名")
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("不允许使用本机或内网地址")

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    try:
        addresses.append(ipaddress.ip_address(hostname))
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, None)
        except socket.gaierror as exc:
            raise ValueError("热点源域名无法解析") from exc
        for info in infos:
            try:
                addresses.append(ipaddress.ip_address(info[4][0]))
            except ValueError as exc:
                raise ValueError("热点源域名解析结果无效") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("不允许访问内网、本机或保留地址")
    return url.strip()


def _custom_records_to_items(
    records: list[dict[str, Any]],
    source_id: str,
    source_name: str,
    fallback_url: str = "",
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen: set[str] = set()
    for record in records:
        title = ""
        for key in TITLE_KEYS:
            title = _text(record.get(key))
            if title:
                break
        if not title or title in seen:
            continue
        seen.add(title)
        url = ""
        for key in URL_KEYS:
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                url = value.strip()
                break
        if url and fallback_url:
            url = urljoin(fallback_url, url)
        hot = 0
        for key in HOT_KEYS:
            hot = _number(record.get(key))
            if hot:
                break
        items.append(
            {
                "rank": len(items) + 1,
                "title": title,
                "hot": hot,
                "url": url or fallback_url or TREND_SOURCES.get(source_id, {}).get("url", ""),
                "source": source_id,
                "source_name": source_name,
            }
        )
    return items


def parse_custom_json(
    payload: Any,
    source_id: str,
    source_name: str,
    fallback_url: str = "",
) -> list[dict[str, object]]:
    best: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        nonlocal best
        if isinstance(value, list):
            records = [item for item in value if isinstance(item, dict)]
            if records and any(any(key in item for key in TITLE_KEYS) for item in records):
                if len(records) > len(best):
                    best = records
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(payload)
    return _custom_records_to_items(best, source_id, source_name, fallback_url)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_custom_rss(
    xml_text: str,
    source_id: str,
    source_name: str,
    fallback_url: str = "",
) -> list[dict[str, object]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError("RSS/XML 内容解析失败") from exc
    records: list[dict[str, Any]] = []
    for entry in root.iter():
        if _local_name(entry.tag) not in {"item", "entry"}:
            continue
        title = ""
        link = ""
        for child in entry:
            name = _local_name(child.tag)
            if name == "title":
                title = _text(child.text)
            elif name == "link":
                link = _text(child.text) or child.attrib.get("href", "")
        if title:
            records.append({"title": title, "url": link})
    return _custom_records_to_items(records, source_id, source_name, fallback_url)


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href") or ""
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        text = " ".join("".join(self._text).split())
        if text:
            self.links.append({"title": text, "url": self._href})
        self._href = ""
        self._text = []


def parse_custom_html(
    html_text: str,
    base_url: str,
    source_id: str,
    source_name: str,
) -> list[dict[str, object]]:
    parser = _AnchorParser()
    parser.feed(html_text)
    records = []
    for link in parser.links:
        title = link["title"]
        href = link["url"]
        if not (6 <= len(title) <= 120):
            continue
        if href.startswith(("#", "javascript:", "mailto:")):
            continue
        if any(word in title for word in NAV_WORDS):
            continue
        records.append({"title": title, "url": urljoin(base_url, href)})
    return _custom_records_to_items(records, source_id, source_name, base_url)


def parse_custom_content(
    content: str,
    content_type: str,
    base_url: str,
    source_id: str,
    source_name: str,
) -> list[dict[str, object]]:
    stripped = content.lstrip()
    if "json" in content_type or stripped.startswith(("{", "[")):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("JSON 内容解析失败") from exc
        return parse_custom_json(payload, source_id, source_name, base_url)
    lowered = stripped[:300].lower()
    if "xml" in content_type or "<rss" in lowered or "<feed" in lowered:
        return parse_custom_rss(content, source_id, source_name, base_url)
    return parse_custom_html(content, base_url, source_id, source_name)


class TrendStore:
    def __init__(self, database_path: Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(TREND_SCHEMA)
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def save(
        self,
        source: str,
        source_name: str,
        snapshot_date: str,
        updated_at: str,
        items: list[dict[str, object]],
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO trend_snapshots
                    (source, source_name, snapshot_date, updated_at, items_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (source, snapshot_date)
                DO UPDATE SET
                    source_name = excluded.source_name,
                    updated_at = excluded.updated_at,
                    items_json = excluded.items_json
                """,
                (
                    source,
                    source_name,
                    snapshot_date,
                    updated_at,
                    json.dumps(items, ensure_ascii=False),
                ),
            )
            connection.commit()

    def latest(self, source: str) -> dict[str, object] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT * FROM trend_snapshots
                WHERE source = ?
                ORDER BY snapshot_date DESC, updated_at DESC
                LIMIT 1
                """,
                (source,),
            ).fetchone()
        return self._snapshot_dict(row) if row is not None else None

    def latest_all(self) -> list[dict[str, object]]:
        return [
            snapshot
            for source in TREND_SOURCES
            if (snapshot := self.latest(source)) is not None
        ]

    def prune(self, retention_days: int = 90) -> None:
        if retention_days <= 0:
            return
        cutoff = (datetime.now().astimezone().date() - timedelta(days=retention_days)).isoformat()
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM trend_snapshots WHERE snapshot_date < ?",
                (cutoff,),
            )
            connection.commit()

    def list_custom_sources(
        self,
        tenant_id: str = "demo",
        include_disabled: bool = False,
    ) -> list[dict[str, object]]:
        query = "SELECT * FROM custom_trend_sources WHERE tenant_id = ?"
        if not include_disabled:
            query += " AND enabled = 1"
        query += " ORDER BY created_at"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, (tenant_id,)).fetchall()
        return [self._custom_source_dict(row) for row in rows]

    def get_custom_source(
        self,
        source_id: str,
        tenant_id: str = "demo",
    ) -> dict[str, object] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM custom_trend_sources WHERE id = ? AND tenant_id = ?",
                (source_id, tenant_id),
            ).fetchone()
        return self._custom_source_dict(row) if row is not None else None

    def create_custom_source(
        self,
        name: str,
        url: str,
        tenant_id: str = "demo",
    ) -> dict[str, object]:
        name = name.strip()
        if not name:
            raise ValueError("平台名称不能为空")
        url = validate_public_url(url)
        source_id = "custom_" + uuid.uuid4().hex[:10]
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO custom_trend_sources
                        (id, tenant_id, name, url, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (source_id, tenant_id, name, url, now, now),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ValueError("这个平台名称已经存在") from exc
        return self.get_custom_source(source_id, tenant_id) or {}

    def delete_custom_source(self, source_id: str, tenant_id: str = "demo") -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM custom_trend_sources WHERE id = ? AND tenant_id = ?",
                (source_id, tenant_id),
            )
            if cursor.rowcount == 1:
                connection.execute(
                    "DELETE FROM trend_snapshots WHERE source = ?",
                    (source_id,),
                )
            connection.commit()
        return cursor.rowcount == 1

    @staticmethod
    def _custom_source_dict(row: sqlite3.Row) -> dict[str, object]:
        return {
            "id": row["id"],
            "name": row["name"],
            "url": row["url"],
            "enabled": bool(row["enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _snapshot_dict(row: sqlite3.Row) -> dict[str, object]:
        return {
            "source": row["source"],
            "source_name": row["source_name"],
            "snapshot_date": row["snapshot_date"],
            "updated_at": row["updated_at"],
            "items": json.loads(row["items_json"]),
        }


class TrendService:
    def __init__(
        self,
        fetcher: Fetcher | None = None,
        ttl_seconds: int = 300,
        store: TrendStore | None = None,
        retention_days: int = 90,
        chat_model: ChatModel | None = None,
    ) -> None:
        self._fetcher = fetcher or self._fetch_http
        self._ttl_seconds = ttl_seconds
        self._store = store
        self._retention_days = retention_days
        self._chat_model = chat_model
        self._cache: dict[tuple[str, int], tuple[float, dict[str, object]]] = {}

    @staticmethod
    async def _fetch_http(source: dict[str, str]) -> Any:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": source["referer"],
            "X-Requested-With": "fetch",
        }
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            response = await client.get(source["url"], headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def sources() -> list[dict[str, str]]:
        return [
            {"id": source_id, "name": source["name"]}
            for source_id, source in TREND_SOURCES.items()
        ]

    def list_sources(self, tenant_id: str = "demo") -> list[dict[str, object]]:
        items: list[dict[str, object]] = [
            {"id": source_id, "name": source["name"], "custom": False}
            for source_id, source in TREND_SOURCES.items()
        ]
        if self._store:
            items.extend(
                {
                    "id": source["id"],
                    "name": source["name"],
                    "custom": True,
                }
                for source in self._store.list_custom_sources(tenant_id)
            )
        return items

    def add_custom_source(
        self,
        name: str,
        url: str,
        tenant_id: str = "demo",
    ) -> dict[str, object]:
        if self._store is None:
            raise ValueError("custom trend sources are unavailable")
        return self._store.create_custom_source(name, url, tenant_id)

    def delete_custom_source(self, source_id: str, tenant_id: str = "demo") -> bool:
        if self._store is None:
            return False
        return self._store.delete_custom_source(source_id, tenant_id)

    def _resolve_source(self, source_id: str, tenant_id: str = "demo") -> dict[str, object]:
        if source_id in TREND_SOURCES:
            source = TREND_SOURCES[source_id]
            return {
                "id": source_id,
                "name": source["name"],
                "url": source["url"],
                "referer": source["referer"],
                "custom": False,
            }
        if self._store and source_id.startswith("custom_"):
            source = self._store.get_custom_source(source_id, tenant_id)
            if source and source["enabled"]:
                parsed = urlparse(str(source["url"]))
                return {
                    **source,
                    "referer": f"{parsed.scheme}://{parsed.netloc}/",
                    "custom": True,
                }
        raise ValueError("unsupported trend source")

    async def _fetch_custom(self, source: dict[str, object]) -> list[dict[str, object]]:
        url = validate_public_url(str(source["url"]))
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json, application/rss+xml, text/html, */*",
            "Referer": str(source.get("referer") or url),
            "X-Requested-With": "fetch",
        }
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                current_url = url
                response = None
                for _ in range(4):
                    response = await client.get(current_url, headers=headers)
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        break
                    location = response.headers.get("location")
                    if not location:
                        break
                    current_url = validate_public_url(urljoin(current_url, location))
                if response is None:
                    raise TrendFetchError("自定义热点源没有响应")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TrendFetchError(f"自定义热点源请求失败：{exc}") from exc
        if len(response.content) > 5 * 1024 * 1024:
            raise TrendFetchError("自定义热点源内容超过 5MB")
        content_type = response.headers.get("content-type", "")
        try:
            items = parse_custom_content(
                response.text,
                content_type,
                str(response.url),
                str(source["id"]),
                str(source["name"]),
            )
        except ValueError as exc:
            raise TrendFetchError(f"自定义热点源解析失败：{exc}") from exc
        if not items:
            raise TrendFetchError("自定义热点源没有解析到可用标题")
        return items

    @staticmethod
    def _snapshot_payload(
        snapshot: dict[str, object],
        limit: int,
        cached: bool,
        stale: bool = False,
    ) -> dict[str, object]:
        return {
            "source": snapshot["source"],
            "source_name": snapshot["source_name"],
            "items": list(snapshot.get("items") or [])[:limit],
            "updated_at": snapshot["updated_at"],
            "snapshot_date": snapshot["snapshot_date"],
            "cached": cached,
            "stale": stale,
        }

    async def fetch(
        self,
        source_id: str,
        limit: int = 30,
        force: bool = False,
        tenant_id: str = "demo",
    ) -> dict[str, object]:
        source = self._resolve_source(source_id, tenant_id)
        limit = max(1, min(int(limit), 200))
        cache_key = (source_id, limit)
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and not force and cached[0] > now:
            return {**cached[1], "cached": True}

        snapshot = self._store.latest(source_id) if self._store else None
        today = datetime.now().astimezone().date().isoformat()
        if snapshot and not force and snapshot["snapshot_date"] == today:
            result = self._snapshot_payload(snapshot, limit, cached=True)
            self._cache[cache_key] = (now + self._ttl_seconds, result)
            return result

        try:
            if source["custom"]:
                all_items = (await self._fetch_custom(source))[:200]
            else:
                payload = await self._fetcher(
                    {
                        "name": str(source["name"]),
                        "url": str(source["url"]),
                        "referer": str(source["referer"]),
                    }
                )
                if not isinstance(payload, dict):
                    raise ValueError("trend source returned invalid data")
                all_items = PARSERS[source_id](payload)[:200]
            if not all_items:
                raise ValueError("trend source returned no items")
        except Exception as exc:
            if snapshot:
                return self._snapshot_payload(snapshot, limit, cached=True, stale=True)
            if isinstance(exc, (httpx.HTTPError, TrendFetchError)):
                raise
            raise TrendFetchError(str(exc)) from exc

        updated_at = datetime.now(UTC).isoformat(timespec="seconds")
        result: dict[str, object] = {
            "source": source_id,
            "source_name": source["name"],
            "items": all_items[:limit],
            "updated_at": updated_at,
            "snapshot_date": datetime.now().astimezone().date().isoformat(),
            "cached": False,
            "stale": False,
        }
        if self._store:
            self._store.save(
                source_id,
                str(source["name"]),
                str(result["snapshot_date"]),
                updated_at,
                all_items,
            )
            self._store.prune(self._retention_days)
        self._cache[cache_key] = (now + self._ttl_seconds, result)
        return result

    async def _expand_direction_with_ai(
        self,
        direction: str,
    ) -> tuple[list[str], list[dict[str, str]], str | None, dict[str, int]]:
        if self._chat_model is None:
            return [], [], None, {}
        try:
            result = await self._chat_model.chat(
                [
                    ChatMessage(
                        role="system",
                        content=(
                            "你是短视频选题策划和中文热榜检索助手。只输出一个 JSON 对象，"
                            "格式为："
                            '{"keywords":["关键词"],"topics":['
                            '{"title":"选题","angle":"切入角度",'
                            '"hook":"开头钩子","format":"内容形式"}]}。'
                            "不要输出 Markdown，不要解释。"
                        ),
                    ),
                    ChatMessage(
                        role="user",
                        content=(
                            f"内容方向：{direction}\n"
                            "要求：\n"
                            "1. keywords 输出 10-24 个，覆盖作品/品牌名、人物名、"
                            "所属品类、核心玩法或使用场景、用户关注点、常见同义词。\n"
                            "2. topics 输出 6-10 个创作者可以直接使用的选题。\n"
                            "3. 选题不要求是当天真实热点，但必须与方向高度相关，"
                            "要具体、有信息量，不要空泛口号。\n"
                            "4. format 从口播、剧情、测评、清单、对比、访谈、"
                            "教程、盘点、探店、Vlog 中选择。"
                        ),
                    ),
                ],
                temperature=0.2,
                max_tokens=900,
            )
        except Exception:
            logger.warning("AI trend topic expansion failed", exc_info=True)
            return [], [], None, {}
        keywords, suggestions = _parse_ai_expansion(result.text)
        return keywords, suggestions, result.model, result.usage

    async def related(
        self,
        direction: str,
        limit: int = 50,
        tenant_id: str = "demo",
        use_ai: bool = True,
    ) -> dict[str, object]:
        direction = direction.strip()
        keywords = _direction_keywords(direction)
        if not keywords:
            raise ValueError("内容方向不能为空")
        ai_keywords: list[str] = []
        ai_suggestions: list[dict[str, str]] = []
        model_name: str | None = None
        usage: dict[str, int] = {}
        if use_ai:
            ai_keywords, ai_suggestions, model_name, usage = (
                await self._expand_direction_with_ai(direction)
            )
            for keyword in ai_keywords:
                if keyword not in keywords:
                    keywords.append(keyword)
        limit = max(1, min(int(limit), 200))
        if self._store is None:
            return {
                "direction": direction,
                "keywords": keywords[:12],
                "ai_keywords": ai_keywords,
                "ai_suggestions": ai_suggestions,
                "ai_expanded": bool(ai_keywords),
                "model": model_name,
                "usage": usage,
                "items": [],
                "source_count": 0,
                "snapshot_date": datetime.now().astimezone().date().isoformat(),
            }

        source_ids = list(TREND_SOURCES)
        source_ids.extend(
            str(source["id"])
            for source in self._store.list_custom_sources(tenant_id)
        )
        merged: dict[str, dict[str, object]] = {}
        source_count = 0
        for source_id in source_ids:
            snapshot = self._store.latest(source_id)
            if snapshot is None:
                continue
            source_count += 1
            source_name = str(snapshot["source_name"])
            for raw in list(snapshot.get("items") or [])[:200]:
                if not isinstance(raw, dict):
                    continue
                title = _text(raw.get("title"))
                if not title:
                    continue
                lowered = title.lower()
                matched = [keyword for keyword in keywords if keyword in lowered]
                if not matched:
                    continue
                relevance = sum(
                    len(keyword) * 3 + (12 if keyword == direction.lower() else 0)
                    for keyword in matched
                )
                dedupe_key = re.sub(r"[^\w\u4e00-\u9fff]+", "", lowered)
                existing = merged.get(dedupe_key)
                if existing is None:
                    item = dict(raw)
                    item["matched_keywords"] = matched
                    item["relevance"] = relevance
                    item["also_on"] = []
                    merged[dedupe_key] = item
                    continue
                existing["relevance"] = max(int(existing["relevance"]), relevance)
                existing["matched_keywords"] = sorted(
                    set(existing["matched_keywords"]) | set(matched)
                )
                if source_name != existing.get("source_name"):
                    also_on = set(existing.get("also_on") or [])
                    also_on.add(source_name)
                    existing["also_on"] = sorted(also_on)

        items = sorted(
            merged.values(),
            key=lambda item: (
                -int(item.get("relevance") or 0),
                -int(item.get("hot") or 0),
            ),
        )[:limit]
        return {
            "direction": direction,
            "keywords": keywords[:12],
            "ai_keywords": ai_keywords,
            "ai_suggestions": ai_suggestions,
            "ai_expanded": bool(ai_keywords),
            "model": model_name,
            "usage": usage,
            "items": items,
            "source_count": source_count,
            "snapshot_date": datetime.now().astimezone().date().isoformat(),
        }

    async def refresh_all_if_stale(self) -> dict[str, int]:
        today = datetime.now().astimezone().date().isoformat()
        refreshed = 0
        failed = 0
        source_ids = list(TREND_SOURCES)
        if self._store:
            source_ids.extend(
                str(source["id"])
                for source in self._store.list_custom_sources()
            )
        for source_id in source_ids:
            snapshot = self._store.latest(source_id) if self._store else None
            if snapshot and snapshot["snapshot_date"] == today:
                continue
            try:
                await self.fetch(source_id, limit=50, force=True)
                refreshed += 1
            except Exception:
                failed += 1
                logger.warning("trend refresh failed for %s", source_id, exc_info=True)
        return {"refreshed": refreshed, "failed": failed}


async def trend_refresh_loop(
    service: TrendService,
    interval_seconds: int = 3600,
) -> None:
    await asyncio.sleep(3)
    while True:
        try:
            await service.refresh_all_if_stale()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("trend refresh loop failed")
        await asyncio.sleep(max(60, interval_seconds))
