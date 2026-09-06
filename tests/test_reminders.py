from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import (
    AccessStatus,
    CatalogNotice,
    Event,
    EventInterest,
    EventPreference,
    Milestone,
    NoticeKind,
    NotificationDelivery,
    ReminderMode,
    ReminderRule,
    StageOutcome,
    StageProgress,
)
from olymping.services.reminders import (
    REMINDER_CUSTOM,
    REMINDER_MUTED,
    REMINDER_NORMAL,
    dispatch_catalog_notices,
    dispatch_due_reminders,
    event_reminder_state,
    schedule_rule,
    set_event_reminders_muted,
)
from olymping.services.users import ensure_user_profile


@pytest.mark.asyncio
async def test_reminder_is_sent_once_and_registration_can_be_suppressed(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 99
    starts_at = datetime(2026, 9, 21, 11, tzinfo=UTC)  # 14:00 Moscow
    sent: list[tuple[int, str]] = []

    async def send(user_id: int, text: str) -> None:
        sent.append((user_id, text))

    async with factory() as session:
        await ensure_user_profile(session, owner_id, "Europe/Moscow")
        event = Event(
            id="rsosh:deadline-2026",
            source_kind="RSOSH",
            title="Deadline <olympiad> & friends",
            category="informatics",
            source_url="https://example.edu/",
            url="https://example.edu/",
            status="confirmed",
        )
        milestone = Milestone(
            id="rsosh:deadline-2026:registration",
            event_id=event.id,
            kind="registration_deadline",
            title="Registration deadline",
            starts_at=starts_at,
            precision="exact",
            status="confirmed",
        )
        preference = EventPreference(
            telegram_user_id=owner_id,
            event_id=event.id,
            interest=EventInterest.WATCHING.value,
        )
        session.add_all([event, milestone, preference])
        await session.flush()
        await session.execute(select(ReminderRule).where(ReminderRule.telegram_user_id == owner_id))
        # Replace inherited rules with one deterministic event override.
        rule = ReminderRule(
            id="custom:registration",
            telegram_user_id=owner_id,
            event_id=event.id,
            milestone_kind="registration_deadline",
            mode=ReminderMode.CALENDAR.value,
            days_before=1,
            local_time="20:00",
        )
        session.add(rule)
        await session.commit()

        due = datetime(2026, 9, 20, 17, tzinfo=UTC)
        assert schedule_rule(rule, milestone, "Europe/Moscow") == due
        assert (
            await dispatch_due_reminders(
                session, owner_id=owner_id, send=send, now=due, grace_hours=1
            )
            == 1
        )
        await session.commit()
        assert (
            await dispatch_due_reminders(
                session, owner_id=owner_id, send=send, now=due, grace_hours=1
            )
            == 0
        )
        assert len(sent) == 1
        assert "Deadline &lt;olympiad&gt; &amp; friends" in sent[0][1]
        assert len((await session.execute(select(NotificationDelivery))).scalars().all()) == 1

        second_registration = Milestone(
            id="rsosh:deadline-2026:registration-2",
            event_id=event.id,
            kind="registration_deadline",
            title="Second registration deadline",
            starts_at=starts_at,
            precision="exact",
            status="confirmed",
        )
        session.add_all(
            [
                second_registration,
                StageProgress(
                    telegram_user_id=owner_id,
                    milestone_id=milestone.id,
                    outcome=StageOutcome.PARTICIPATED.value,
                ),
            ]
        )
        await session.commit()
        progress = await session.get(StageProgress, (owner_id, milestone.id))
        assert progress is not None
        assert progress.outcome == StageOutcome.PARTICIPATED.value
        preference.interest = EventInterest.REGISTERED.value
        await session.commit()
        # Registration status suppresses the new registration milestone entirely.
        assert (
            await dispatch_due_reminders(
                session, owner_id=owner_id, send=send, now=due, grace_hours=1
            )
            == 0
        )
        assert len((await session.execute(select(NotificationDelivery))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_new_catalog_events_are_sent_as_one_digest(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 42
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        await ensure_user_profile(session, owner_id, "Europe/Moscow")
        for index in range(2):
            event_id = f"rsosh:new-{index}"
            session.add(
                Event(
                    id=event_id,
                    source_kind="RSOSH",
                    title=f"New {index}",
                    category="informatics",
                    source_url=f"https://example.edu/{index}",
                    status="tbd",
                )
            )
            await session.flush()
            session.add(
                EventPreference(
                    telegram_user_id=owner_id,
                    event_id=event_id,
                    interest=EventInterest.WATCHING.value,
                )
            )
            session.add(
                CatalogNotice(
                    telegram_user_id=owner_id,
                    event_id=event_id,
                    kind=NoticeKind.NEW_EVENT.value,
                    summary="new",
                )
            )
        await session.commit()

        assert await dispatch_catalog_notices(session, owner_id=owner_id, send=send) == 2
        await session.commit()

        assert len(sent) == 1
        assert "2 новых событий" in sent[0]
        assert sent[0].count("🔔") == 3
        notices = (await session.execute(select(CatalogNotice))).scalars().all()
        assert all(notice.sent_at is not None for notice in notices)


@pytest.mark.asyncio
async def test_reminder_toggle_preserves_custom_rules(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 51
    event_id = "rsosh:toggle"
    async with factory() as session:
        await ensure_user_profile(session, owner_id, "Europe/Moscow")
        session.add(
            Event(
                id=event_id,
                source_kind="RSOSH",
                title="Toggle",
                category="informatics",
                source_url="https://example.edu/",
                status="confirmed",
            )
        )
        await session.flush()

        assert await event_reminder_state(session, owner_id, event_id) == REMINDER_NORMAL
        assert (
            await set_event_reminders_muted(
                session, user_id=owner_id, event_id=event_id, muted=True
            )
            == REMINDER_MUTED
        )
        await session.flush()
        assert await event_reminder_state(session, owner_id, event_id) == REMINDER_MUTED
        assert (
            await set_event_reminders_muted(
                session, user_id=owner_id, event_id=event_id, muted=False
            )
            == REMINDER_NORMAL
        )
        custom = ReminderRule(
            id="custom:toggle",
            telegram_user_id=owner_id,
            event_id=event_id,
            mode=ReminderMode.CALENDAR.value,
            days_before=2,
            local_time="19:00",
        )
        session.add(custom)
        await session.flush()
        assert await event_reminder_state(session, owner_id, event_id) == REMINDER_CUSTOM

        await set_event_reminders_muted(session, user_id=owner_id, event_id=event_id, muted=True)
        await session.flush()
        assert custom.enabled is False
        assert await event_reminder_state(session, owner_id, event_id) == REMINDER_MUTED

        assert (
            await set_event_reminders_muted(
                session, user_id=owner_id, event_id=event_id, muted=False
            )
            == REMINDER_CUSTOM
        )
        await session.flush()
        assert custom.enabled is True


@pytest.mark.asyncio
async def test_catalog_retries_only_failed_messages(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        if "broken" in text:
            raise RuntimeError("delivery unavailable")
        sent.append(text)

    async with factory() as session:
        await ensure_user_profile(session, 42, "Europe/Moscow")
        session.add(
            Event(
                id="rsosh:retry",
                source_kind="RSOSH",
                title="Retry",
                source_url="https://example.edu/",
                status="confirmed",
            )
        )
        await session.flush()
        notices = [
            CatalogNotice(
                telegram_user_id=42,
                event_id="rsosh:retry",
                kind=NoticeKind.EVENT_UPDATED.value,
                summary=summary,
            )
            for summary in ("good", "broken", "also good")
        ]
        session.add_all(notices)
        await session.commit()
        assert await dispatch_catalog_notices(session, owner_id=42, send=send) == 2
        await session.commit()
        assert notices[0].sent_at is not None
        assert notices[1].sent_at is None
        assert notices[2].sent_at is not None
        assert await dispatch_catalog_notices(session, owner_id=42, send=send) == 0
        assert len(sent) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked", [False, True])
async def test_catalog_respects_current_access_and_filters(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    blocked: bool,
) -> None:
    _, factory = database

    async def send(_user_id: int, _text: str) -> None:
        pytest.fail("disabled notifications must not be delivered")

    async with factory() as session:
        profile = await ensure_user_profile(session, 42, "Europe/Moscow")
        session.add(
            Event(
                id="rsosh:disabled",
                source_kind="RSOSH",
                title="Disabled",
                source_url="https://example.edu/",
                status="confirmed",
            )
        )
        await session.flush()
        session.add(
            CatalogNotice(
                telegram_user_id=42,
                event_id="rsosh:disabled",
                kind=NoticeKind.NEW_EVENT.value,
                summary="new",
            )
        )
        if blocked:
            profile.access_status = AccessStatus.BLOCKED.value
        else:
            profile.notify_new_events = False
        await session.commit()
        await dispatch_catalog_notices(session, owner_id=42, send=send)
        assert await dispatch_due_reminders(session, owner_id=42, send=send) == 0


@pytest.mark.asyncio
async def test_large_catalog_digest_is_split(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        assert len(text) < 4096
        sent.append(text)

    async with factory() as session:
        await ensure_user_profile(session, 42, "Europe/Moscow")
        for index in range(20):
            event_id = f"rsosh:long-{index}"
            session.add(
                Event(
                    id=event_id,
                    source_kind="RSOSH",
                    title="A" * 300,
                    source_url="https://example.edu/",
                    status="confirmed",
                )
            )
            await session.flush()
            session.add(
                CatalogNotice(
                    telegram_user_id=42,
                    event_id=event_id,
                    kind=NoticeKind.NEW_EVENT.value,
                    summary="new",
                )
            )
        await session.commit()
        assert await dispatch_catalog_notices(session, owner_id=42, send=send) == 20
        assert len(sent) == 4
