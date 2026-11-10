from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_trend_service
from app.api.main import app
from app.gateway.base import ChatResult
from app.studio.trends import (
    TrendService,
    TrendStore,
    parse_custom_content,
    validate_public_url,
)


async def test_weibo_trends_are_normalized_and_cached() -> None:
    calls = 0

    async def fetcher(source: dict[str, str]) -> dict:
        nonlocal calls
        calls += 1
        assert source["name"] == "微博"
        return {
            "data": {
                "realtime": [
                    {"word": "#新品发布#", "num": 12345},
                    {"word": "行业趋势", "num": "9876"},
                ]
            }
        }

    service = TrendService(fetcher=fetcher, ttl_seconds=300)
    first = await service.fetch("weibo", limit=2)
    assert first["source_name"] == "微博"
    assert [item["title"] for item in first["items"]] == ["新品发布", "行业趋势"]
    assert first["items"][0]["hot"] == 12345
    assert first["items"][0]["url"].startswith("https://s.weibo.com/weibo?q=")
    assert first["cached"] is False

    second = await service.fetch("weibo", limit=2)
    assert second["cached"] is True
    assert calls == 1

    forced = await service.fetch("weibo", limit=2, force=True)
    assert forced["cached"] is False
    assert calls == 2


async def test_trend_parsers_support_other_sources() -> None:
    service = TrendService(
        fetcher=lambda _: _resolved(
            {
                "data": [
                    {
                        "target": {
                            "id": 123,
                            "title": "知乎热榜问题",
                            "follower_count": 456,
                        }
                    }
                ]
            }
        )
    )
    result = await service.fetch("zhihu", limit=1)
    assert result["items"][0]["title"] == "知乎热榜问题"
    assert result["items"][0]["url"] == "https://www.zhihu.com/question/123"


async def test_trend_snapshot_survives_restart_and_falls_back(tmp_path) -> None:
    async def fetcher(_: dict[str, str]) -> dict:
        return {"data": {"realtime": [{"word": "每日热点", "num": 100}]}}

    database = tmp_path / "trends.db"
    service = TrendService(fetcher=fetcher, store=TrendStore(database))
    live = await service.fetch("weibo", limit=1, force=True)
    assert live["items"][0]["title"] == "每日热点"
    assert live["stale"] is False

    async def failing(_: dict[str, str]) -> dict:
        raise RuntimeError("source offline")

    restarted = TrendService(
        fetcher=failing,
        store=TrendStore(database),
        ttl_seconds=0,
    )
    stale = await restarted.fetch("weibo", limit=1, force=True)
    assert stale["items"][0]["title"] == "每日热点"
    assert stale["stale"] is True


async def test_small_request_does_not_shrink_daily_snapshot(tmp_path) -> None:
    async def fetcher(_: dict[str, str]) -> dict:
        return {
            "data": {
                "realtime": [
                    {"word": f"热点 {index}", "num": 100 - index}
                    for index in range(10)
                ]
            }
        }

    store = TrendStore(tmp_path / "trends.db")
    service = TrendService(fetcher=fetcher, store=store)
    small = await service.fetch("weibo", limit=2, force=True)
    assert len(small["items"]) == 2
    assert len(store.latest("weibo")["items"]) == 10

    full = await service.fetch("weibo", limit=10)
    assert len(full["items"]) == 10


async def test_related_trends_rank_dedupe_and_match_keywords(tmp_path) -> None:
    store = TrendStore(tmp_path / "trends.db")
    today = datetime.now().astimezone().date().isoformat()
    common = {
        "rank": 1,
        "hot": 100,
        "url": "https://example.com/a",
        "source": "weibo",
        "source_name": "微博",
    }
    store.save(
        "weibo",
        "微博",
        today,
        f"{today}T08:00:00+00:00",
        [
            {**common, "title": "秋冬美妆新品发布"},
            {**common, "rank": 2, "title": "数码产品年度测评"},
            {**common, "rank": 3, "title": "母婴好物清单"},
        ],
    )
    store.save(
        "bilibili",
        "B站",
        today,
        f"{today}T08:01:00+00:00",
        [
            {
                **common,
                "source": "bilibili",
                "source_name": "B站",
                "title": "秋冬美妆新品发布",
            },
            {
                **common,
                "source": "bilibili",
                "source_name": "B站",
                "rank": 2,
                "title": "美妆护肤新手教程",
            },
        ],
    )

    service = TrendService(store=store)
    result = await service.related("美妆护肤", limit=10)
    titles = [item["title"] for item in result["items"]]
    assert "秋冬美妆新品发布" in titles
    assert "美妆护肤新手教程" in titles
    assert "数码产品年度测评" not in titles
    assert "美妆" in result["keywords"]
    duplicate = next(item for item in result["items"] if item["title"] == "秋冬美妆新品发布")
    assert duplicate["also_on"] == ["B站"]


async def test_related_trends_use_ai_direction_expansion(tmp_path) -> None:
    class FakeChat:
        async def chat(self, messages, **options) -> ChatResult:
            assert "燕云十六声" in messages[-1].content
            return ChatResult(
                text=json.dumps(
                    {
                        "keywords": ["武侠", "开放世界", "游戏", "国风"],
                        "topics": [
                            {
                                "title": "为什么武侠开放世界又火了",
                                "angle": "从玩家审美变化解释",
                                "hook": "现在的玩家为什么重新爱上武侠？",
                                "format": "口播",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                model="fake-chat",
                usage={"total_tokens": 42},
            )

    store = TrendStore(tmp_path / "trends.db")
    today = datetime.now().astimezone().date().isoformat()
    store.save(
        "weibo",
        "微博",
        today,
        f"{today}T08:00:00+00:00",
        [
            {
                "rank": 1,
                "title": "国产武侠开放世界游戏新版本上线",
                "hot": 100,
                "url": "https://example.com/game",
                "source": "weibo",
                "source_name": "微博",
            },
            {
                "rank": 2,
                "title": "今日天气",
                "hot": 90,
                "url": "https://example.com/weather",
                "source": "weibo",
                "source_name": "微博",
            },
        ],
    )
    service = TrendService(store=store, chat_model=FakeChat())
    result = await service.related("燕云十六声", limit=10, use_ai=True)
    assert result["ai_expanded"] is True
    assert result["model"] == "fake-chat"
    assert result["usage"]["total_tokens"] == 42
    assert result["items"][0]["title"] == "国产武侠开放世界游戏新版本上线"
    assert result["ai_suggestions"][0]["title"] == "为什么武侠开放世界又火了"
    assert result["ai_suggestions"][0]["format"] == "口播"


async def test_daily_refresh_skips_sources_already_updated_today(tmp_path) -> None:
    async def fetcher(source: dict[str, str]) -> dict:
        if source["name"] == "微博":
            return {"data": {"realtime": [{"word": "每日热点", "num": 100}]}}
        if source["name"] == "知乎":
            return {"data": [{"target": {"id": 1, "title": "知乎热点"}}]}
        if source["name"] == "B站":
            return {"data": {"list": [{"title": "B站热点", "bvid": "BV1"}]}}
        if source["name"] == "百度":
            return {"data": {"cards": [{"content": [{"content": [{"word": "百度热点"}]}]}]}}
        if source["name"] == "抖音":
            return {"data": {"word_list": [{"word": "抖音热点", "hot_value": 100}]}}
        return {"data": [{"Title": "头条热点", "HotValue": 100, "Url": "https://www.toutiao.com/"}]}

    service = TrendService(fetcher=fetcher, store=TrendStore(tmp_path / "trends.db"))
    first = await service.refresh_all_if_stale()
    assert first["refreshed"] == 6
    second = await service.refresh_all_if_stale()
    assert second["refreshed"] == 0


def test_custom_trend_sources_parse_json_rss_and_html() -> None:
    json_items = parse_custom_content(
        '{"data":[{"title":"JSON 热点","url":"/news/1","hot":88}]}',
        "application/json",
        "https://example.com/hot",
        "custom_test",
        "自定义",
    )
    assert json_items[0]["title"] == "JSON 热点"
    assert json_items[0]["url"] == "https://example.com/news/1"

    rss_items = parse_custom_content(
        """<?xml version="1.0"?><rss><channel><item>
        <title>RSS 热点标题</title><link>https://example.com/a</link>
        </item></channel></rss>""",
        "application/rss+xml",
        "https://example.com/",
        "custom_test",
        "自定义",
    )
    assert rss_items[0]["title"] == "RSS 热点标题"
    assert rss_items[0]["url"] == "https://example.com/a"

    html_items = parse_custom_content(
        '<a href="/hot/1">这是一个普通网页热点标题</a><a href="/login">登录</a>',
        "text/html",
        "https://example.com/",
        "custom_test",
        "自定义",
    )
    assert html_items[0]["title"] == "这是一个普通网页热点标题"
    assert html_items[0]["url"] == "https://example.com/hot/1"


def test_custom_trend_source_rejects_private_urls() -> None:
    with pytest.raises(ValueError):
        validate_public_url("http://127.0.0.1/hot")
    with pytest.raises(ValueError):
        validate_public_url("file:///etc/passwd")


def test_custom_trend_source_crud(tmp_path) -> None:
    store = TrendStore(tmp_path / "trends.db")
    with pytest.raises(ValueError):
        store.create_custom_source("本机", "http://localhost/hot")
    source = store.create_custom_source("自定义源", "https://93.184.216.34/hot")
    assert source["name"] == "自定义源"
    assert store.list_custom_sources()[0]["id"] == source["id"]
    assert store.delete_custom_source(str(source["id"])) is True
    assert store.list_custom_sources() == []


def test_custom_trend_source_api(tmp_path) -> None:
    service = TrendService(store=TrendStore(tmp_path / "trends.db"))
    app.dependency_overrides[get_trend_service] = lambda: service
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/trends/custom-sources",
                json={
                    "name": "自定义热榜",
                    "url": "https://93.184.216.34/hot",
                },
            )
            assert created.status_code == 201, created.text
            source = created.json()
            sources = client.get("/api/v1/trends/sources").json()["items"]
            assert any(item["id"] == source["id"] and item["custom"] for item in sources)
            deleted = client.delete(f"/api/v1/trends/custom-sources/{source['id']}")
            assert deleted.status_code == 200
    finally:
        app.dependency_overrides.clear()


async def _resolved(value: dict) -> dict:
    return value


def test_trends_api_uses_service() -> None:
    class FakeTrendService:
        async def fetch(self, source: str, limit: int, force: bool) -> dict:
            return {
                "source": source,
                "source_name": "微博",
                "items": [{"rank": 1, "title": "测试热点"}],
                "updated_at": "2026-11-07T00:00:00+00:00",
                "cached": False,
                "limit": limit,
                "force": force,
            }

        async def related(
            self,
            direction: str,
            limit: int,
            use_ai: bool,
        ) -> dict:
            return {
                "direction": direction,
                "keywords": ["美妆"],
                "ai_keywords": ["美妆"] if use_ai else [],
                "ai_expanded": use_ai,
                "ai_suggestions": [
                    {
                        "title": "美妆选题参考",
                        "angle": "从真实使用场景切入",
                        "hook": "你真的会用吗？",
                        "format": "口播",
                    }
                ] if use_ai else [],
                "items": [{"rank": 1, "title": "美妆关联热点"}],
                "source_count": 3,
            }

    app.dependency_overrides[get_trend_service] = lambda: FakeTrendService()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/trends?source=weibo&limit=100")
            too_many = client.get("/api/v1/trends?source=weibo&limit=201")
            related = client.get("/api/v1/trends/related?direction=美妆&limit=20")
        assert response.status_code == 200
        assert response.json()["items"][0]["title"] == "测试热点"
        assert response.json()["limit"] == 100
        assert too_many.status_code == 422
        assert related.status_code == 200
        assert related.json()["items"][0]["title"] == "美妆关联热点"
    finally:
        app.dependency_overrides.clear()
