from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import Event, Milestone
from olymping.services.calendar import all_olympiads, registration_closes_at
from olymping.services.users import ensure_user_profile


@pytest.mark.asyncio
async def test_all_olympiads_includes_tbd_and_excludes_ctftime(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        profile = await ensure_user_profile(session, 7, "Europe/Moscow")
        session.add_all(
            [
                Event(
                    id="rsosh:tbd-2026",
                    source_kind="RSOSH",
                    title="TBD olympiad",
                    category="informatics",
                    source_url="https://example.edu/olympiad",
                    status="tbd",
                ),
                Event(
                    id="ctftime:999",
                    source_kind="CTF",
                    external_id="999",
                    title="Upcoming CTF",
                    category="cybersecurity",
                    source_url="https://ctftime.org/event/999/",
                    status="confirmed",
                ),
            ]
        )
        await session.commit()

        items = await all_olympiads(session, profile)
        assert [item.id for item in items] == ["rsosh:tbd-2026"]

        profile.category_settings = {**profile.category_settings, "RSOSH": False}
        await session.commit()
        assert await all_olympiads(session, profile) == []


@pytest.mark.asyncio
async def test_catalog_filters_by_grade_and_any_selected_tag(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        profile = await ensure_user_profile(session, 11, "Europe/Moscow")
        profile.school_grade = 10
        profile.tag_filters = ["cybersecurity", "programming"]
        session.add_all(
            [
                Event(
                    id="rsosh:security",
                    source_kind="RSOSH",
                    title="Security",
                    category="cybersecurity",
                    tags=["cybersecurity"],
                    source_url="https://example.edu/security",
                    status="tbd",
                    min_grade=8,
                    max_grade=11,
                ),
                Event(
                    id="mosh:junior-programming",
                    source_kind="MOSH",
                    title="Junior programming",
                    category="informatics",
                    tags=["programming"],
                    source_url="https://example.edu/junior",
                    status="tbd",
                    min_grade=6,
                    max_grade=9,
                ),
                Event(
                    id="rsosh:physics",
                    source_kind="RSOSH",
                    title="Physics",
                    category="physics",
                    tags=["physics"],
                    source_url="https://example.edu/physics",
                    status="tbd",
                    min_grade=7,
                    max_grade=11,
                ),
                Event(
                    id="rsosh:unknown-grades",
                    source_kind="RSOSH",
                    title="Unknown security",
                    category="cybersecurity",
                    tags=["cybersecurity"],
                    source_url="https://example.edu/unknown",
                    status="tbd",
                ),
            ]
        )
        await session.commit()

        items = await all_olympiads(session, profile)

        assert [item.id for item in items] == ["rsosh:security", "rsosh:unknown-grades"]


def test_registration_window_respects_explicit_opening_and_deadline() -> None:
    now = datetime(2026, 9, 2, 12, tzinfo=UTC)
    event = Event(
        id="rsosh:registration",
        source_kind="RSOSH",
        title="Registration",
        category="informatics",
        source_url="https://example.edu/",
        status="confirmed",
    )
    opening = Milestone(
        id="rsosh:registration:open",
        event_id=event.id,
        kind="registration_open",
        title="Open",
        starts_at=now + timedelta(days=1),
        precision="exact",
        status="confirmed",
    )
    deadline = Milestone(
        id="rsosh:registration:deadline",
        event_id=event.id,
        kind="registration_deadline",
        title="Deadline",
        starts_at=now + timedelta(days=10),
        precision="exact",
        status="confirmed",
    )
    event.milestones = [opening, deadline]

    assert registration_closes_at(event, now) is None
    assert registration_closes_at(event, now + timedelta(days=2)) == deadline.starts_at
    assert registration_closes_at(event, now + timedelta(days=11)) is None
