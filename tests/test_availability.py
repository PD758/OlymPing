from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from conftest import approve_pending_reviews
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.config import Settings
from olymping.models import (
    AccessStatus,
    Event,
    EventPreference,
    Milestone,
    OpenEventNotice,
    StageProgress,
    SyncRun,
)
from olymping.services.availability import (
    dispatch_open_event_notices,
    open_phases,
    queue_open_event_notices,
)
from olymping.services.calendar import registration_closes_at
from olymping.services.importer import ImportSummary
from olymping.services.reminders import dispatch_registration_digest
from olymping.services.synchronization import synchronize_calendar
from olymping.services.users import ensure_user_profile

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)


@pytest.mark.asyncio
async def test_unchanged_sync_does_not_review_clock_opening(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]], tmp_path: Path
) -> None:
    _, factory = database
    due = datetime(2026, 9, 11, 6, tzinfo=UTC)
    async with factory() as session:
        profile = await ensure_user_profile(session, 42, "Europe/Moscow", onboarding_completed=True)
        profile.notify_new_events = False
        profile.auto_subscribe_new_events = False
        await session.commit()
    calendar = tmp_path / "calendar.yaml"
    calendar.write_text("""calendar_version: 1
events:
  - id: test:clock
    source_kind: NTO
    title: Clock opening
    source_url: https://example.org/
    status: confirmed
    milestones:
      - id: test:clock:open
        kind: registration_open
        title: Open
        starts_at: '2026-09-11T00:00:00+03:00'
        status: confirmed
      - id: test:clock:deadline
        kind: registration_deadline
        title: Deadline
        starts_at: '2026-09-20T00:00:00+03:00'
        status: confirmed
""")
    settings = Settings(data_dir=tmp_path)
    with (
        patch(
            "olymping.services.synchronization.sync_ctftime",
            new=AsyncMock(return_value=ImportSummary()),
        ),
        patch("olymping.services.availability.datetime", wraps=datetime) as clock,
    ):
        clock.now.return_value = due - timedelta(days=1)
        first = await synchronize_calendar(factory, settings)
        assert first.imported.changed_event_ids == {"test:clock"}
        assert first.open_notices == 0 and first.review_batch_id is None
        clock.now.return_value = due
        second = await synchronize_calendar(factory, settings)
        assert second.imported.changed_event_ids == set()
        assert second.open_notices == 0 and second.review_batch_id is None
        send = AsyncMock()
        async with factory() as session:
            assert await dispatch_registration_digest(session, owner_id=42, send=send, now=due) == 1
        send.assert_awaited_once()
        calendar.write_text(calendar.read_text().replace("2026-09-20", "2026-09-21"))
        changed = await synchronize_calendar(factory, settings)
        assert changed.imported.changed_event_ids == {"test:clock"}
        assert changed.review_batch_id is not None
        again = await synchronize_calendar(factory, settings)
        assert again.open_notices == 0 and again.review_batch_id is None


async def seed(session: AsyncSession) -> Event:
    for user_id in range(1, 6):
        profile = await ensure_user_profile(
            session, user_id, "Europe/Moscow", onboarding_completed=True
        )
        if user_id == 3:
            profile.access_status = AccessStatus.BLOCKED.value
        if user_id == 4:
            profile.tag_filters = ["physics"]
        if user_id == 5:
            profile.notify_open_events = False
    event = Event(
        id="nto:test",
        title="Test <NTO>",
        source_kind="NTO",
        source_url="https://example.org/",
        tags=["informatics"],
        status="confirmed",
    )
    event.milestones = [
        Milestone(
            id="nto:test:open",
            kind="registration_open",
            title="Open",
            status="confirmed",
            starts_at=NOW - timedelta(days=10),
        ),
        Milestone(
            id="nto:test:deadline",
            kind="registration_deadline",
            title="Deadline",
            status="confirmed",
            starts_at=NOW + timedelta(days=10),
        ),
        Milestone(
            id="nto:test:stage",
            kind="qualifier",
            title="Qualifying",
            status="confirmed",
            starts_at=NOW - timedelta(days=1),
            ends_at=NOW + timedelta(days=1),
        ),
    ]
    session.add(event)
    await session.commit()
    return event


@pytest.mark.asyncio
async def test_sync_queues_old_openings_per_user_without_duplicates(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[tuple[int, str]] = []

    async def send(user_id: int, text: str) -> None:
        sent.append((user_id, text))

    async with factory() as session:
        await seed(session)
        assert await queue_open_event_notices(session, now=NOW) == 4
        await session.commit()
        assert await queue_open_event_notices(session, now=NOW) == 0
        await approve_pending_reviews(session)
        assert await dispatch_open_event_notices(session, owner_id=1, send=send, now=NOW) == 2
        assert await dispatch_open_event_notices(session, owner_id=2, send=send, now=NOW) == 2
        assert all("&lt;NTO&gt;" in text for _, text in sent)
    async with factory() as session:
        assert await queue_open_event_notices(session, now=NOW) == 0
        assert await dispatch_open_event_notices(session, owner_id=1, send=send, now=NOW) == 0
        assert len(sent) == 2


@pytest.mark.asyncio
async def test_delivery_retry_and_changed_preferences(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        sent.append(text)

    async def fail(_user_id: int, _text: str) -> None:
        raise RuntimeError("network down")

    async with factory() as session:
        await seed(session)
        assert await queue_open_event_notices(session, now=NOW) == 4
        await session.commit()
        await approve_pending_reviews(session)
        assert await dispatch_open_event_notices(session, owner_id=1, send=fail, now=NOW) == 0
        assert await dispatch_open_event_notices(session, owner_id=1, send=send, now=NOW) == 0
        assert (
            await dispatch_open_event_notices(
                session,
                owner_id=1,
                send=send,
                now=NOW + timedelta(minutes=3),
            )
            == 2
        )
        session.add(EventPreference(telegram_user_id=2, event_id="nto:test", interest="ignored"))
        await session.commit()
        assert await dispatch_open_event_notices(session, owner_id=2, send=send, now=NOW) == 0
        notices = list(
            await session.scalars(
                select(OpenEventNotice).where(
                    OpenEventNotice.telegram_user_id == 2,
                )
            )
        )
        assert all(notice.status == "skipped" for notice in notices)


@pytest.mark.asyncio
async def test_closed_or_unconfirmed_windows_not_announced(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        event = await seed(session)
        assert len(open_phases(event, NOW)) == 2
        assert open_phases(event, NOW + timedelta(days=20)) == []
        for stage in event.milestones:
            stage.status = "tentative"
        assert open_phases(event, NOW) == []


@pytest.mark.asyncio
async def test_sync_keeps_yaml_if_ctftime_fails(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    tmp_path: Path,
) -> None:
    _, factory = database
    async with factory() as session:
        await ensure_user_profile(session, 1, "Europe/Moscow", onboarding_completed=True)
        await session.commit()
    calendar = tmp_path / "calendar"
    calendar.mkdir()
    (calendar / "events.yaml").write_text("""calendar_version: 1
events:
  - id: nto:imported
    source_kind: NTO
    title: Imported
    source_url: https://example.org/
    status: confirmed
    milestones:
      - id: nto:imported:deadline
        kind: registration_deadline
        title: Deadline
        starts_at: '2099-10-22T00:00:00+03:00'
        status: confirmed
""")
    settings = Settings(data_dir=calendar)
    with patch(
        "olymping.services.synchronization.sync_ctftime",
        new=AsyncMock(side_effect=RuntimeError("remote down")),
    ):
        result = await synchronize_calendar(factory, settings)
    assert result.ctftime is None
    assert result.imported.created_events == 1
    assert result.open_notices == 1
    async with factory() as session:
        assert await session.get(Event, "nto:imported") is not None
        failures = list(await session.scalars(select(SyncRun).where(SyncRun.success.is_(False))))
        assert len(failures) == 1


@pytest.mark.asyncio
async def test_date_only_deadline_includes_announced_day(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        event = await seed(session)
        deadline = next(s for s in event.milestones if s.kind == "registration_deadline")
        deadline.starts_at = NOW.replace(hour=0)
        deadline.precision = "date"
        assert any(p.phase.startswith("registration:") for p in open_phases(event, NOW))
        assert registration_closes_at(event, NOW) == deadline.starts_at
        assert not any(
            p.phase.startswith("registration:") for p in open_phases(event, NOW + timedelta(days=1))
        )


@pytest.mark.asyncio
async def test_registered_user_only_receives_participation(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await seed(session)
        session.add(EventPreference(telegram_user_id=1, event_id="nto:test", interest="registered"))
        await session.commit()
        assert await queue_open_event_notices(session, now=NOW) == 3
        notices = list(
            await session.scalars(
                select(OpenEventNotice).where(
                    OpenEventNotice.telegram_user_id == 1,
                )
            )
        )
        assert [notice.phase for notice in notices] == ["stage:nto:test:stage"]


@pytest.mark.asyncio
async def test_finished_stage_and_unsubscribed_user_are_not_queued(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await seed(session)
        session.add(
            StageProgress(
                telegram_user_id=1,
                milestone_id="nto:test:stage",
                outcome="not_passed",
            )
        )
        session.add(
            EventPreference(
                telegram_user_id=2,
                event_id="nto:test",
                interest="unsubscribed",
            )
        )
        await session.commit()

        assert await queue_open_event_notices(session, now=NOW) == 1
        notices = list(await session.scalars(select(OpenEventNotice)))
        assert [(notice.telegram_user_id, notice.phase) for notice in notices] == [
            (1, "registration:nto:test:open")
        ]
