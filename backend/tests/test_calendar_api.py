from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_calendar_service
from app.api.main import app
from app.studio.calendar import CalendarService, CalendarStore


@pytest.fixture
def client(tmp_path):
    service = CalendarService(CalendarStore(tmp_path / "calendar.db"))
    app.dependency_overrides[get_calendar_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_calendar_generate_update_and_delete(client: TestClient) -> None:
    start = date.today().isoformat()
    response = client.post(
        "/api/v1/content-calendar/generate",
        json={
            "direction": "美妆护肤",
            "start_date": start,
            "days": 2,
            "per_day": 2,
            "platforms": ["抖音", "小红书"],
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["count"] == 4
    assert len(payload["items"]) == 4
    assert payload["items"][0]["plan_date"] == start
    assert payload["items"][0]["title"]

    item_id = payload["items"][0]["id"]
    updated = client.patch(
        f"/api/v1/content-calendar/{item_id}",
        json={"status": "in_progress", "notes": "本周优先拍摄"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"

    listed = client.get(
        "/api/v1/content-calendar",
        params={
            "start_date": start,
            "end_date": (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 4

    deleted = client.delete(f"/api/v1/content-calendar/{item_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
