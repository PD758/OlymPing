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
from olymping.services.importer import ImportSummary, load_calendar_document
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


def test_registration_waves_do_not_join_across_closed_or_future_openings() -> None:
    now = datetime(2026, 9, 10, 12, tzinfo=UTC)
    event = Event(id="test:waves", source_kind="NTO", title="Waves", status="confirmed")
    event.milestones = [
        Milestone(
            id="test:waves:first-open",
            kind="registration_open",
            title="First open",
            starts_at=now - timedelta(days=10),
            status="confirmed",
        ),
        Milestone(
            id="test:waves:first-deadline",
            kind="registration_deadline",
            title="First deadline",
            starts_at=now - timedelta(days=5),
            status="confirmed",
        ),
        Milestone(
            id="test:waves:second-open",
            kind="registration_open",
            title="Second open",
            starts_at=now - timedelta(hours=1),
            status="confirmed",
        ),
        Milestone(
            id="test:waves:future-open",
            kind="registration_open",
            title="Future open",
            starts_at=now + timedelta(days=2),
            status="confirmed",
        ),
        Milestone(
            id="test:waves:future-deadline",
            kind="registration_deadline",
            title="Future deadline",
            starts_at=now + timedelta(days=5),
            status="confirmed",
        ),
    ]

    # The second wave is open with no published deadline.  The future opening
    # owns the future deadline, so it must not close or hide this wave.
    assert [(phase.phase, phase.milestone_id) for phase in open_phases(event, now)] == [
        ("registration:test:waves:second-open", "test:waves:second-open")
    ]


def test_real_vosh_registration_is_not_open_a_week_after_school_tours() -> None:
    document = load_calendar_document(Path("data/calendar/01_vosh_2026.yaml"))
    assert len(document.events) == 28
    for seed in document.events:
        event = Event(id=seed.id, title=seed.title, status=seed.status.value)
        event.milestones = [
            Milestone(
                id=stage.id,
                kind=stage.kind.value,
                title=stage.title,
                starts_at=stage.starts_at,
                ends_at=stage.ends_at,
                status=stage.status.value,
                advancement_paths=stage.advancement_paths,
            )
            for stage in seed.milestones
        ]
        school = next(stage for stage in event.milestones if stage.advancement_paths == [])
        assert school.starts_at is not None
        entry_ends = [
            stage.ends_at
            for stage in event.milestones
            if stage.kind == "qualifier" and not stage.advancement_paths
        ]
        assert entry_ends and all(end is not None for end in entry_ends)
        last_end = max(end for end in entry_ends if end is not None)
        assert any(
            p.phase.startswith("registration:")
            for p in open_phases(event, school.starts_at - timedelta(days=1))
        ), seed.id
        assert not any(
            p.phase.startswith("registration:")
            for p in open_phases(event, last_end + timedelta(days=7))
        ), seed.id


@pytest.mark.parametrize("second_status, second_end", [("confirmed", True), ("tbd", False)])
def test_undated_registration_keeps_remaining_independent_entry_rounds(
    second_status: str, second_end: bool
) -> None:
    event = Event(id="test:rounds", title="Rounds", status="confirmed")
    event.milestones = [
        Milestone(
            id="test:rounds:open",
            kind="registration_open",
            title="Open",
            starts_at=NOW - timedelta(days=10),
            status="confirmed",
        ),
        Milestone(
            id="test:rounds:first",
            kind="qualifier",
            title="First",
            starts_at=NOW - timedelta(days=2),
            ends_at=NOW - timedelta(days=1),
            status="confirmed",
            advancement_paths=[],
        ),
        Milestone(
            id="test:rounds:second",
            kind="qualifier",
            title="Second",
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=2) if second_end else None,
            status=second_status,
            advancement_paths=[],
        ),
    ]
    assert any(p.phase.startswith("registration:") for p in open_phases(event, NOW))
    if second_end:
        assert not open_phases(event, NOW + timedelta(days=2))
    else:
        # Missing dates cannot be promoted to a claimed closed window.
        assert open_phases(event, NOW + timedelta(days=7))


def test_published_registration_deadline_overrides_entry_window_bound() -> None:
    event = Event(id="test:deadline", title="Deadline", status="confirmed")
    event.milestones = [
        Milestone(
            id="test:deadline:open",
            kind="registration_open",
            title="Open",
            starts_at=NOW - timedelta(days=10),
            status="confirmed",
        ),
        Milestone(
            id="test:deadline:entry",
            kind="qualifier",
            title="Entry",
            starts_at=NOW - timedelta(days=2),
            ends_at=NOW - timedelta(days=1),
            status="confirmed",
            advancement_paths=[],
        ),
        Milestone(
            id="test:deadline:close",
            kind="registration_deadline",
            title="Close",
            starts_at=NOW + timedelta(days=1),
            status="confirmed",
        ),
    ]
    assert any(p.phase.startswith("registration:") for p in open_phases(event, NOW))
    assert not open_phases(event, NOW + timedelta(days=2))


def test_unknown_final_does_not_extend_initial_registration_after_qualifier() -> None:
    event = Event(id="test:unknown-final", title="Unknown final", status="confirmed")
    event.milestones = [
        Milestone(
            id="test:unknown-final:open",
            kind="registration_open",
            title="Open",
            starts_at=NOW - timedelta(days=10),
            status="confirmed",
        ),
        Milestone(
            id="test:unknown-final:qualifier",
            kind="qualifier",
            title="Qualifier",
            starts_at=NOW - timedelta(days=2),
            ends_at=NOW - timedelta(days=1),
            status="confirmed",
        ),
        Milestone(
            id="test:unknown-final:final",
            kind="final",
            title="Final",
            starts_at=NOW + timedelta(days=30),
            status="tentative",
        ),
    ]
    assert not open_phases(event, NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_first", [False, True])
async def test_approved_registration_without_deadline_expires_before_late_send(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]], failed_first: bool
) -> None:
    _, factory = database
    async with factory() as session:
        await ensure_user_profile(session, 1, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:late-review",
            title="Late review",
            source_kind="VOSH",
            source_url="https://example.org/",
            status="confirmed",
            milestones=[
                Milestone(
                    id="test:late-review:open",
                    kind="registration_open",
                    title="Open",
                    starts_at=NOW,
                    status="confirmed",
                ),
                Milestone(
                    id="test:late-review:school",
                    kind="qualifier",
                    title="School",
                    starts_at=NOW + timedelta(days=1),
                    ends_at=NOW + timedelta(days=2),
                    status="confirmed",
                    advancement_paths=[],
                ),
                Milestone(
                    id="test:late-review:regional",
                    kind="qualifier",
                    title="Regional",
                    starts_at=NOW + timedelta(days=30),
                    ends_at=NOW + timedelta(days=31),
                    status="confirmed",
                    advancement_paths=[["test:late-review:school"]],
                ),
            ],
        )
        session.add(event)
        await session.commit()
        assert await queue_open_event_notices(session, now=NOW) == 1
        await approve_pending_reviews(session)
        if failed_first:
            send = AsyncMock(side_effect=RuntimeError("network unavailable"))
            assert await dispatch_open_event_notices(session, owner_id=1, send=send, now=NOW) == 0
            send.assert_awaited_once()

    # Approved before the outage: restart/retry must still check availability.
    async with factory() as session:
        send = AsyncMock()
        late = NOW + timedelta(days=9)
        assert await dispatch_open_event_notices(session, owner_id=1, send=send, now=late) == 0
        send.assert_not_awaited()
        notice = await session.scalar(select(OpenEventNotice))
        assert notice is not None and notice.status == "skipped"
        assert await queue_open_event_notices(session, now=late) == 0
        await session.commit()


@pytest.mark.asyncio
async def test_automatic_registration_retry_expires_after_entry_tour(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    due = NOW.replace(hour=6)  # 09:00 Moscow: within the opening digest window.
    async with factory() as session:
        await ensure_user_profile(session, 1, "Europe/Moscow", onboarding_completed=True)
        session.add(
            Event(
                id="test:late-digest",
                title="Late digest",
                source_kind="VOSH",
                source_url="https://example.org/",
                status="confirmed",
                milestones=[
                    Milestone(
                        id="test:late-digest:open",
                        kind="registration_open",
                        title="Open",
                        starts_at=due - timedelta(hours=1),
                        status="confirmed",
                    ),
                    Milestone(
                        id="test:late-digest:entry",
                        kind="qualifier",
                        title="Entry",
                        starts_at=due + timedelta(hours=1),
                        ends_at=due + timedelta(hours=2),
                        status="confirmed",
                        advancement_paths=[],
                    ),
                ],
            )
        )
        await session.commit()
        send = AsyncMock(side_effect=RuntimeError("network unavailable"))
        assert await dispatch_registration_digest(session, owner_id=1, send=send, now=due) == 0
        send.assert_awaited_once()
    async with factory() as session:
        send = AsyncMock()
        assert (
            await dispatch_registration_digest(
                session, owner_id=1, send=send, now=due + timedelta(days=7)
            )
            == 0
        )
        send.assert_not_awaited()
        notice = await session.scalar(select(OpenEventNotice))
        assert notice is not None and notice.status == "skipped"


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
