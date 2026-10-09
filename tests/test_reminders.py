from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage
from conftest import approve_pending_reviews
from sqlalchemy import delete, select
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
    OpenEventNotice,
    ReminderMode,
    ReminderRule,
    StageOutcome,
    StageProgress,
)
from olymping.services.delivery import DeliveryDeferred
from olymping.services.importer import import_data_directory, load_calendar_document
from olymping.services.reminders import (
    REMINDER_CUSTOM,
    REMINDER_MUTED,
    REMINDER_NORMAL,
    dispatch_catalog_notices,
    dispatch_due_reminders,
    dispatch_registration_digest,
    event_reminder_state,
    schedule_rule,
    set_event_reminders_muted,
)
from olymping.services.user_state import toggle_event_interest
from olymping.services.users import ensure_user_profile


@pytest.mark.asyncio
@pytest.mark.parametrize("custom", [False, True])
async def test_no_advance_registration_opening_even_for_saved_retry(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]], custom: bool
) -> None:
    _, factory = database
    starts = datetime(2026, 9, 21, tzinfo=UTC)
    due = starts - timedelta(hours=7)  # Previous day, 20:00 Moscow.
    async with factory() as session:
        await ensure_user_profile(session, 99, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:advance",
            title="Advance",
            source_kind="NTO",
            source_url="https://example.org/",
            milestones=[
                Milestone(
                    id=f"test:advance:{kind}",
                    kind=kind,
                    title=kind,
                    starts_at=starts,
                    status="confirmed",
                    precision="exact",
                )
                for kind in ("registration_open", "registration_deadline", "qualifier")
            ],
        )
        session.add(event)
        await session.flush()
        session.add(EventPreference(telegram_user_id=99, event_id=event.id, interest="watching"))
        if custom:
            rule = ReminderRule(
                id="test:advance:custom",
                telegram_user_id=99,
                event_id=event.id,
                mode="offset",
                offset_minutes=420,
            )
            session.add(rule)
        else:
            rule = await session.scalar(
                select(ReminderRule).where(
                    ReminderRule.telegram_user_id == 99,
                    ReminderRule.source_kind == "NTO",
                    ReminderRule.days_before == 1,
                )
            )
            assert rule is not None
        await session.flush()
        session.add(
            NotificationDelivery(
                telegram_user_id=99,
                milestone_id="test:advance:registration_open",
                reminder_rule_id=rule.id,
                scheduled_for=due,
                status="pending",
            )
        )
        await session.commit()
    sent: list[str] = []

    async def send(_user: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        assert await dispatch_due_reminders(session, owner_id=99, send=send, now=due) == 2
        assert all("registration_open" not in text for text in sent)
        assert any("qualifier" in text for text in sent)
        assert any("Завтра заканчивается регистрация" in text for text in sent)
    async with factory() as session:
        # Catch-up after opening must not revive the old advance reminder.
        assert (
            await dispatch_due_reminders(
                session, owner_id=99, send=send, now=starts + timedelta(hours=1)
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("timezone", ["Europe/Moscow", "Asia/Yekaterinburg"])
async def test_same_day_default_opening_rule_waits_until_exact_opening(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]], timezone: str
) -> None:
    _, factory = database
    tz = ZoneInfo(timezone)
    opening = datetime(2026, 9, 21, 10, tzinfo=tz).astimezone(UTC)
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        await ensure_user_profile(session, 99, timezone, onboarding_completed=True)
        event = Event(
            id=f"test:opening-at-start:{timezone}",
            title="Opening at start",
            source_kind="NTO",
            source_url="https://example.org/",
            milestones=[
                Milestone(
                    id=f"test:opening-at-start:{timezone}:open",
                    kind="registration_open",
                    title="Open",
                    starts_at=opening,
                    status="confirmed",
                )
            ],
        )
        session.add(event)
        await session.flush()
        session.add(EventPreference(telegram_user_id=99, event_id=event.id, interest="watching"))
        await session.commit()

        # The default same-day 08:00 local rule is before this 10:00 opening.
        # It must not be lost (or sent before registration actually opens).
        assert await dispatch_due_reminders(session, owner_id=99, send=send, now=opening) == 1
        delivery = await session.scalar(select(NotificationDelivery))
        assert delivery is not None
        assert delivery.scheduled_for.replace(tzinfo=UTC) == opening
    assert len(sent) == 1 and "Opening at start" in sent[0]


@pytest.mark.asyncio
async def test_registration_opening_reminder_and_digest_share_delivery_history(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 99
    opening = datetime(2026, 9, 21, 7, tzinfo=UTC)  # 10:00 Moscow.
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        await ensure_user_profile(session, owner_id, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:opening-dedup",
            title="Opening dedup",
            source_kind="NTO",
            source_url="https://example.org/",
            milestones=[
                Milestone(
                    id="test:opening-dedup:open",
                    kind="registration_open",
                    title="Open",
                    starts_at=opening,
                    status="confirmed",
                )
            ],
        )
        session.add(event)
        await session.flush()
        session.add(
            EventPreference(telegram_user_id=owner_id, event_id=event.id, interest="watching")
        )
        await session.commit()

        assert await dispatch_due_reminders(session, owner_id=owner_id, send=send, now=opening) == 1
        # The 09:00 Moscow catch-up on the next day still sees this opening,
        # but a sent direct opening reminder must suppress its digest duplicate.
        assert (
            await dispatch_registration_digest(
                session, owner_id=owner_id, send=send, now=opening + timedelta(hours=23)
            )
            == 0
        )

        notice = OpenEventNotice(
            telegram_user_id=owner_id,
            event_id=event.id,
            milestone_id="test:opening-dedup:open",
            phase="registration:test:opening-dedup:open",
            status="automatic",
        )
        session.add(notice)
        await session.commit()
        # An older version could leave a failed automatic attempt queued even
        # though a direct reminder had already succeeded.
        assert (
            await dispatch_registration_digest(
                session, owner_id=owner_id, send=send, now=opening + timedelta(hours=23)
            )
            == 0
        )
        assert notice.status == "skipped"

        # Model the opposite order independently: only a digest was delivered,
        # with no direct-reminder delivery record to mask the duplicate.
        await session.execute(delete(NotificationDelivery))
        notice.status = "sent"
        await session.commit()
        # A digest/review opening sent first also suppresses a later direct
        # retry after restart; no second NotificationDelivery is created.
    async with factory() as session:
        assert await dispatch_due_reminders(session, owner_id=owner_id, send=send, now=opening) == 0
        assert await session.scalar(select(NotificationDelivery)) is None
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_failed_reminder_is_not_retried_early_across_sessions_or_after_registration(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 99
    due = datetime(2026, 9, 20, 8, tzinfo=UTC)
    calls = 0

    async def fail(_user_id: int, _text: str) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("network outage")

    async def unexpected(_user_id: int, _text: str) -> None:
        pytest.fail("this reminder is no longer eligible")

    async with factory() as session:
        await ensure_user_profile(session, owner_id, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:retry-eligibility",
            title="Retry eligibility",
            source_kind="NTO",
            source_url="https://example.org/",
            milestones=[
                Milestone(
                    id="test:retry-eligibility:deadline",
                    kind="registration_deadline",
                    title="Deadline",
                    starts_at=due + timedelta(days=2),
                    status="confirmed",
                )
            ],
        )
        session.add(event)
        await session.flush()
        session.add_all(
            [
                EventPreference(telegram_user_id=owner_id, event_id=event.id, interest="watching"),
                ReminderRule(
                    id="test:retry-eligibility:rule",
                    telegram_user_id=owner_id,
                    event_id=event.id,
                    mode=ReminderMode.OFFSET.value,
                    offset_minutes=2880,
                ),
            ]
        )
        await session.commit()
        assert await dispatch_due_reminders(session, owner_id=owner_id, send=fail, now=due) == 0
        assert calls == 1

    async with factory() as session:
        # A fresh session/restart must retain the 2-minute backoff checkpoint.
        assert (
            await dispatch_due_reminders(
                session, owner_id=owner_id, send=unexpected, now=due + timedelta(minutes=1)
            )
            == 0
        )
        await toggle_event_interest(
            session,
            actor_id=owner_id,
            event_id="test:retry-eligibility",
            interest=EventInterest.REGISTERED,
        )
        await session.commit()
        assert (
            await dispatch_due_reminders(
                session, owner_id=owner_id, send=unexpected, now=due + timedelta(minutes=2)
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_first", [False, True])
@pytest.mark.parametrize("lag_hours", [1, 168])
async def test_finished_stage_is_not_replayed_even_inside_configured_grace(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    failed_first: bool,
    lag_hours: int,
) -> None:
    _, factory = database
    due = datetime(2026, 9, 20, 8, tzinfo=UTC)

    async def offline(_user_id: int, _text: str) -> None:
        raise RuntimeError("network unavailable")

    async def unexpected(_user_id: int, _text: str) -> None:
        pytest.fail("a finished tour must not invite participation during catch-up")

    async with factory() as session:
        await ensure_user_profile(session, 99, "Europe/Moscow", onboarding_completed=True)
        session.add(
            Event(
                id="test:finished-stage",
                title="Finished",
                source_kind="NTO",
                source_url="https://example.org/",
                status="confirmed",
                milestones=[
                    Milestone(
                        id="test:finished-stage:entry",
                        kind="qualifier",
                        title="Entry",
                        starts_at=due,
                        ends_at=due + timedelta(minutes=10),
                        status="confirmed",
                        advancement_paths=[],
                    ),
                    Milestone(
                        id="test:finished-stage:next",
                        kind="final",
                        title="Next",
                        starts_at=due + timedelta(days=30),
                        status="confirmed",
                        advancement_paths=[["test:finished-stage:entry"]],
                    ),
                ],
            )
        )
        await session.flush()
        session.add_all(
            [
                EventPreference(
                    telegram_user_id=99, event_id="test:finished-stage", interest="watching"
                ),
                ReminderRule(
                    id="test:finished-stage:rule",
                    telegram_user_id=99,
                    event_id="test:finished-stage",
                    mode=ReminderMode.OFFSET.value,
                    offset_minutes=0,
                ),
            ]
        )
        await session.commit()
        if failed_first:
            assert (
                await dispatch_due_reminders(
                    session, owner_id=99, send=offline, now=due, grace_hours=168
                )
                == 0
            )
    async with factory() as session:
        assert (
            await dispatch_due_reminders(
                session,
                owner_id=99,
                send=unexpected,
                now=due + timedelta(hours=lag_hours),
                grace_hours=168,
            )
            == 0
        )


@pytest.mark.asyncio
async def test_expired_reminder_is_never_sent_after_grace_window(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    due = datetime(2026, 9, 20, 8, tzinfo=UTC)

    async def unexpected(_user_id: int, _text: str) -> None:
        pytest.fail("expired reminders must not be delivered")

    async with factory() as session:
        await ensure_user_profile(session, 99, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:expired-reminder",
            title="Expired",
            source_kind="NTO",
            source_url="https://example.org/",
            milestones=[
                Milestone(
                    id="test:expired-reminder:stage",
                    kind="qualifier",
                    title="Stage",
                    starts_at=due,
                    status="confirmed",
                )
            ],
        )
        session.add(event)
        await session.flush()
        session.add_all(
            [
                EventPreference(telegram_user_id=99, event_id=event.id, interest="watching"),
                ReminderRule(
                    id="test:expired-reminder:rule",
                    telegram_user_id=99,
                    event_id=event.id,
                    mode=ReminderMode.OFFSET.value,
                    offset_minutes=0,
                ),
            ]
        )
        await session.commit()
        assert (
            await dispatch_due_reminders(
                session, owner_id=99, send=unexpected, now=due + timedelta(hours=24, seconds=1)
            )
            == 0
        )


@pytest.mark.asyncio
async def test_reminder_skips_its_own_completed_stage_when_another_path_remains_live(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    due = datetime(2026, 9, 20, 8, tzinfo=UTC)

    async def unexpected(_user_id: int, _text: str) -> None:
        pytest.fail("a completed stage must not be reminded")

    async with factory() as session:
        await ensure_user_profile(session, 99, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:completed-stage",
            title="Completed stage",
            source_kind="NTO",
            source_url="https://example.org/",
            milestones=[
                Milestone(
                    id="test:completed-stage:done",
                    kind="qualifier",
                    title="Completed",
                    starts_at=due,
                    status="confirmed",
                    advancement_paths=[],
                ),
                Milestone(
                    id="test:completed-stage:other-path",
                    kind="qualifier",
                    title="Still available",
                    starts_at=due + timedelta(days=1),
                    status="confirmed",
                    advancement_paths=[],
                ),
            ],
        )
        session.add(event)
        await session.flush()
        session.add_all(
            [
                EventPreference(telegram_user_id=99, event_id=event.id, interest="watching"),
                ReminderRule(
                    id="test:completed-stage:rule",
                    telegram_user_id=99,
                    event_id=event.id,
                    mode=ReminderMode.OFFSET.value,
                    offset_minutes=0,
                ),
                StageProgress(
                    telegram_user_id=99,
                    milestone_id="test:completed-stage:done",
                    outcome=StageOutcome.PASSED.value,
                ),
            ]
        )
        await session.commit()
        assert await dispatch_due_reminders(session, owner_id=99, send=unexpected, now=due) == 0


@pytest.mark.asyncio
async def test_real_dano_calendar_default_registration_reminders(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    messages: list[str] = []

    async def send(_user: int, text: str) -> None:
        messages.append(text)

    async with factory() as session:
        profile = await ensure_user_profile(session, 99, "Europe/Moscow", onboarding_completed=True)
        profile.tag_filters = ["dano"]
        await import_data_directory(session, Path("data/calendar"))
        await session.commit()
        pref = await session.get(EventPreference, (99, "other:dano-2026"))
        assert pref is not None and pref.interest == "watching"
    deadline = _dano_deadline_moscow()
    # Standard rules are three reminders, not just the newly clarified previous-day one.
    for due in [
        (deadline - timedelta(days=3)).replace(hour=20, minute=0),
        (deadline - timedelta(days=1)).replace(hour=20, minute=0),
        deadline.replace(hour=8, minute=0),
    ]:
        async with factory() as session:
            assert (
                await dispatch_due_reminders(
                    session,
                    owner_id=99,
                    send=send,
                    now=due,
                    grace_hours=1,
                )
                == 1
            )
        async with factory() as session:
            assert (
                await dispatch_due_reminders(
                    session,
                    owner_id=99,
                    send=send,
                    now=due,
                    grace_hours=1,
                )
                == 0
            )
    assert len(messages) == 3
    assert "Завтра заканчивается регистрация" in messages[1]
    assert all(deadline.strftime("%d.%m.%Y %H:%M") in message for message in messages)


def _dano_deadline_moscow() -> datetime:
    document = load_calendar_document(Path("data/calendar/09_programming_olympiads.yaml"))
    event = next(event for event in document.events if event.id == "other:dano-2026")
    deadline = next(
        stage for stage in event.milestones if stage.kind.value == "registration_deadline"
    )
    assert deadline.starts_at is not None
    return deadline.starts_at.astimezone(ZoneInfo("Europe/Moscow"))


@pytest.mark.asyncio
async def test_registration_mark_cancels_deferred_deadline_reminder(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    deadline = _dano_deadline_moscow()
    due = (deadline - timedelta(days=1)).replace(hour=20, minute=0)
    sent: list[str] = []

    async def limited(_user: int, _text: str) -> None:
        raise DeliveryDeferred(120)

    async def send(_user: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        profile = await ensure_user_profile(session, 99, "Europe/Moscow", onboarding_completed=True)
        profile.tag_filters = ["dano"]
        await import_data_directory(session, Path("data/calendar"))
        await session.commit()
        with pytest.raises(DeliveryDeferred):
            await dispatch_due_reminders(session, owner_id=99, send=limited, now=due)
    async with factory() as session:
        # Use the same persisted action as the Telegram “registered” button.
        await toggle_event_interest(
            session,
            actor_id=99,
            event_id="other:dano-2026",
            interest=EventInterest.REGISTERED,
        )
        await session.commit()
    async with factory() as session:
        assert (
            await dispatch_due_reminders(
                session,
                owner_id=99,
                send=send,
                now=due + timedelta(minutes=3),
            )
            == 0
        )
        assert (
            await dispatch_due_reminders(
                session,
                owner_id=99,
                send=send,
                now=deadline.replace(hour=8, minute=0),
            )
            == 0
        )
    assert not sent


@pytest.mark.asyncio
async def test_reminder_transient_failures_back_off_and_recover_after_five_attempts(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 99
    due = datetime(2026, 9, 20, 8, tzinfo=UTC)
    attempts = 0
    delivered: list[str] = []

    async def unavailable(_user_id: int, _text: str) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("temporary network outage")

    async def recovered(_user_id: int, text: str) -> None:
        delivered.append(text)

    async with factory() as session:
        await ensure_user_profile(session, owner_id, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:retry-backoff",
            title="Retry backoff",
            source_kind="NTO",
            source_url="https://example.org/",
            milestones=[
                Milestone(
                    id="test:retry-backoff:stage",
                    kind="qualifier",
                    title="Stage",
                    starts_at=due,
                    status="confirmed",
                )
            ],
        )
        session.add(event)
        await session.flush()
        session.add_all(
            [
                EventPreference(
                    telegram_user_id=owner_id,
                    event_id=event.id,
                    interest=EventInterest.WATCHING.value,
                ),
                ReminderRule(
                    id="test:retry-backoff:rule",
                    telegram_user_id=owner_id,
                    event_id=event.id,
                    mode=ReminderMode.OFFSET.value,
                    offset_minutes=0,
                ),
            ]
        )
        await session.commit()

        # Fail at exponentially spaced checkpoints.  Polls between them must
        # not consume retries, and five failures must not abandon the reminder.
        for offset in (0, 2, 6, 14, 30):
            assert (
                await dispatch_due_reminders(
                    session,
                    owner_id=owner_id,
                    send=unavailable,
                    now=due + timedelta(minutes=offset),
                )
                == 0
            )
            assert attempts == (0, 2, 6, 14, 30).index(offset) + 1
            assert (
                await dispatch_due_reminders(
                    session,
                    owner_id=owner_id,
                    send=unavailable,
                    now=due + timedelta(minutes=offset + 1),
                )
                == 0
            )
            assert attempts == (0, 2, 6, 14, 30).index(offset) + 1

        assert (
            await dispatch_due_reminders(
                session,
                owner_id=owner_id,
                send=recovered,
                now=due + timedelta(minutes=62),
            )
            == 1
        )
        delivery = await session.scalar(select(NotificationDelivery))
        assert delivery is not None and delivery.status == "sent" and delivery.attempts == 6
    assert len(delivered) == 1


@pytest.mark.asyncio
async def test_permanent_telegram_failure_is_not_retried_within_grace(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    due = datetime(2026, 9, 20, 8, tzinfo=UTC)
    calls = 0

    async def forbidden(_user_id: int, _text: str) -> None:
        nonlocal calls
        calls += 1
        raise TelegramForbiddenError(SendMessage(chat_id=99, text="notice"), "bot was blocked")

    async def unexpected(_user_id: int, _text: str) -> None:
        pytest.fail("a permanent Telegram failure must not be retried")

    async with factory() as session:
        await ensure_user_profile(session, 99, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:permanent-failure",
            title="Permanent failure",
            source_kind="NTO",
            source_url="https://example.org/",
            milestones=[
                Milestone(
                    id="test:permanent-failure:stage",
                    kind="qualifier",
                    title="Stage",
                    starts_at=due,
                    status="confirmed",
                )
            ],
        )
        session.add(event)
        await session.flush()
        session.add_all(
            [
                EventPreference(telegram_user_id=99, event_id=event.id, interest="watching"),
                ReminderRule(
                    id="test:permanent-failure:rule",
                    telegram_user_id=99,
                    event_id=event.id,
                    mode=ReminderMode.OFFSET.value,
                    offset_minutes=0,
                ),
            ]
        )
        await session.commit()
        assert await dispatch_due_reminders(session, owner_id=99, send=forbidden, now=due) == 0
        assert calls == 1
        assert (
            await dispatch_due_reminders(
                session, owner_id=99, send=unexpected, now=due + timedelta(minutes=2)
            )
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "interest,muted,expected",
    [
        ("watching", False, 1),
        ("registered", False, 0),
        ("ignored", False, 0),
        (None, False, 0),
        ("watching", True, 0),
    ],
)
@pytest.mark.parametrize("timezone", ["Europe/Moscow", "Asia/Yekaterinburg"])
async def test_default_deadline_reminder_on_previous_day_and_after_restart(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    interest: str | None,
    muted: bool,
    expected: int,
    timezone: str,
) -> None:
    _, factory = database
    tz = ZoneInfo(timezone)
    due = datetime(2026, 9, 20, 20, tzinfo=tz).astimezone(UTC)
    sent: list[str] = []

    async def send(_user: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        await ensure_user_profile(session, 99, timezone, onboarding_completed=True)
        event = Event(
            id="test:closing",
            title="Closing",
            source_kind="NTO",
            source_url="https://example.org/",
            status="confirmed",
        )
        event.milestones = [
            Milestone(
                id="test:closing:deadline",
                kind="registration_deadline",
                title="Deadline",
                starts_at=datetime(2026, 9, 21, tzinfo=tz).astimezone(UTC),
                precision="date",
                status="confirmed",
            )
        ]
        session.add(event)
        await session.flush()
        if interest is not None:
            session.add(EventPreference(telegram_user_id=99, event_id=event.id, interest=interest))
        if muted:
            await set_event_reminders_muted(session, user_id=99, event_id=event.id, muted=True)
        await session.commit()
        assert (
            await dispatch_due_reminders(
                session,
                owner_id=99,
                send=send,
                now=due - timedelta(minutes=1),
                grace_hours=1,
            )
            == 0
        )
        assert (
            await dispatch_due_reminders(
                session,
                owner_id=99,
                send=send,
                now=due,
                grace_hours=1,
            )
            == expected
        )
    async with factory() as session:
        assert (
            await dispatch_due_reminders(
                session,
                owner_id=99,
                send=send,
                now=due + timedelta(minutes=1),
                grace_hours=1,
            )
            == 0
        )
        # Do not catch up a missed morning reminder after registration is closed.
        assert (
            await dispatch_due_reminders(
                session,
                owner_id=99,
                send=send,
                now=due + timedelta(hours=29),
            )
            == 0
        )
    assert len(sent) == expected
    if expected:
        assert "Завтра заканчивается регистрация" in sent[0]
        assert "21.09.2026 включительно" in sent[0]


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

        await approve_pending_reviews(session)
        assert await dispatch_catalog_notices(session, owner_id=owner_id, send=send) == 2
        await session.commit()

        assert len(sent) == 1
        assert "New 0" in sent[0] and "New 1" in sent[0]
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
        await approve_pending_reviews(session)
        assert await dispatch_catalog_notices(session, owner_id=42, send=send) == 0
        await session.commit()
        assert all(notice.sent_at is None for notice in notices)

        async def recovered(_user_id: int, text: str) -> None:
            sent.append(text)

        from datetime import timedelta

        from olymping.services.reviews import dispatch_reviewed_notices

        assert (
            await dispatch_reviewed_notices(
                session,
                owner_id=42,
                send=recovered,
                now=datetime.now(UTC) + timedelta(minutes=3),
            )
            == 3
        )
        assert len(sent) == 1
        assert await dispatch_catalog_notices(session, owner_id=42, send=send) == 0


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
        await approve_pending_reviews(session)
        assert await dispatch_catalog_notices(session, owner_id=42, send=send) == 20
        assert len(sent) > 1
