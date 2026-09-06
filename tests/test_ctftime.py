from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import Event, Milestone
from olymping.services.ctftime import sync_ctftime


@pytest.mark.asyncio
async def test_ctftime_sync_maps_and_updates_event(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    payload = [
        {
            "id": 123,
            "title": "Example CTF",
            "description": "A test event",
            "start": "2026-09-10T10:00:00+00:00",
            "finish": "2026-09-11T10:00:00+00:00",
            "ctftime_url": "https://ctftime.org/event/123/",
            "url": "https://ctf.example/",
            "weight": 42.5,
            "format": "Jeopardy",
            "onsite": False,
            "restrictions": "Open",
            "location": "",
            "organizers": [{"id": 1, "name": "Team"}],
            "duration": {"hours": 0, "days": 1},
        }
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["limit"] == "1000"
        return httpx.Response(200, json=payload)

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client,
        factory() as session,
    ):
        summary = await sync_ctftime(
            session,
            base_url="https://ctftime.org/api/v1",
            lookahead_days=30,
            client=client,
            now=datetime(2026, 9, 2, tzinfo=UTC),
        )
        await session.commit()
        assert summary.created_events == 1
        event = await session.get(Event, "ctftime:123")
        assert event is not None
        assert event.weight == 42.5
        milestone = (
            await session.execute(select(Milestone).where(Milestone.event_id == event.id))
        ).scalar_one()
        assert milestone.starts_at is not None
        assert milestone.is_online is True
        assert milestone.format == "Jeopardy"
