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


@pytest.mark.asyncio
async def test_personal_views_hide_ignored_and_nonmatching_events(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    from olymping.models import EventPreference
    from olymping.services.calendar import open_registration_events, upcoming_events

    _, factory = database
    now = datetime(2026, 9, 8, tzinfo=UTC)
    async with factory() as session:
        first = await ensure_user_profile(session, 1, "Europe/Moscow")
        second = await ensure_user_profile(session, 2, "Europe/Moscow")
        for profile in (first, second):
            profile.school_grade = 9
            profile.tag_filters = ["law"]
            profile.category_settings = {**profile.category_settings, "NTO": False}
        for key, source, tags, max_grade, status in [
            ("match", "RSOSH", ["law"], 11, "confirmed"),
            ("ignored", "RSOSH", ["law"], 11, "confirmed"),
            ("topic", "RSOSH", ["physics"], 11, "confirmed"),
            ("group", "VOSH", ["physics"], 11, "confirmed"),
            ("young", "RSOSH", ["law"], 8, "confirmed"),
            ("source", "NTO", ["law"], 11, "confirmed"),
            ("cancelled", "RSOSH", ["law"], 11, "cancelled"),
        ]:
            event = Event(
                id=f"test:{key}",
                title=key,
                source_kind=source,
                tags=tags,
                min_grade=5,
                max_grade=max_grade,
                status=status,
                source_url="https://example.org/",
            )
            event.milestones = [
                Milestone(
                    id=f"test:{key}:deadline",
                    kind="registration_deadline",
                    title="Deadline",
                    starts_at=now + timedelta(hours=12),
                    precision="exact",
                    status="confirmed",
                )
            ]
            session.add(event)
        await session.flush()
        session.add_all(
            [
                EventPreference(telegram_user_id=1, event_id="test:ignored", interest="ignored"),
                EventPreference(telegram_user_id=2, event_id="test:match", interest="ignored"),
            ]
        )
        await session.commit()
        for days in (1, 7, 30):
            events = await upcoming_events(
                session, first, starts_at=now, ends_at=now + timedelta(days=days)
            )
            assert [event.id for event, _ in events] == ["test:match"]
        assert [event.id for event in await open_registration_events(session, first, now=now)] == [
            "test:match"
        ]
        assert [event.id for event in await open_registration_events(session, second, now=now)] == [
            "test:ignored"
        ]
        assert "test:ignored" in [event.id for event in await all_olympiads(session, first)]
        first.tag_filters = ["law", "group:vosh"]
        await session.commit()
        assert {event.id for event in await open_registration_events(session, first, now=now)} == {
            "test:match",
            "test:group",
        }
        ignored = await session.get(EventPreference, (1, "test:ignored"))
        assert ignored is not None
        ignored.interest = "watching"
        await session.commit()
        assert "test:ignored" in [
            event.id for event in await open_registration_events(session, first, now=now)
        ]


@pytest.mark.asyncio
async def test_personal_limits_apply_after_filtering_and_deadline_sort(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    from olymping.services.calendar import open_registration_events, upcoming_events

    _, factory = database
    now = datetime(2026, 9, 8, tzinfo=UTC)
    async with factory() as session:
        profile = await ensure_user_profile(session, 1, "Europe/Moscow")
        profile.tag_filters = ["law"]
        for index in range(10):
            event = Event(
                id=f"test:{index}",
                title=f"{index}",
                source_kind="RSOSH",
                tags=["physics"],
                status="confirmed",
                source_url="https://example.org/",
            )
            event.milestones = [
                Milestone(
                    id=f"test:{index}:stage",
                    kind="qualifier",
                    title="Stage",
                    starts_at=now,
                    precision="exact",
                    status="confirmed",
                )
            ]
            session.add(event)
        for key, days in [("a-later", 2), ("z-sooner", 1)]:
            event = Event(
                id=f"test:{key}",
                title=key,
                source_kind="RSOSH",
                tags=["law"],
                status="confirmed",
                source_url="https://example.org/",
            )
            event.milestones = [
                Milestone(
                    id=f"test:{key}:deadline",
                    kind="registration_deadline",
                    title="Deadline",
                    starts_at=now + timedelta(days=days),
                    precision="exact",
                    status="confirmed",
                )
            ]
            session.add(event)
        await session.commit()
        upcoming = await upcoming_events(
            session, profile, starts_at=now, ends_at=now + timedelta(days=7), limit=1
        )
        assert [event.id for event, _ in upcoming] == ["test:z-sooner"]
        registrations = await open_registration_events(session, profile, now=now, limit=1)
        assert [event.id for event in registrations] == ["test:z-sooner"]
