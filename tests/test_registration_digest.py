from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import AccessStatus, Event, Milestone, OpenEventNotice
from olymping.services.availability import queue_open_event_notices
from olymping.services.delivery import DeliveryDeferred
from olymping.services.reminders import dispatch_registration_digest
from olymping.services.reviews import collect_review_batch
from olymping.services.users import ensure_user_profile


@pytest.mark.asyncio
@pytest.mark.parametrize("review_change", [False, True])
async def test_automatic_opening_deferred_delivery_and_sync_review(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    review_change: bool,
) -> None:
    _, factory = database
    due = datetime(2026, 9, 11, 6, tzinfo=UTC)
    async with factory() as session:
        await ensure_user_profile(session, 42, "Europe/Moscow", onboarding_completed=True)
        session.add(
            Event(
                id="test:deferred",
                title="Deferred",
                source_kind="NTO",
                source_url="https://example.org/",
                milestones=[
                    Milestone(
                        id="test:deferred:open",
                        kind="registration_open",
                        title="Open",
                        starts_at=due - timedelta(hours=1),
                        status="confirmed",
                    )
                ],
            )
        )
        await session.commit()

        async def deferred(_user: int, _text: str) -> None:
            raise DeliveryDeferred(120)

        with pytest.raises(DeliveryDeferred):
            await dispatch_registration_digest(session, owner_id=42, send=deferred, now=due)
    sent: list[str] = []

    async def send(_user: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        if review_change:
            # A changed imported event claims its previously unsent automatic notice for review.
            assert (
                await queue_open_event_notices(session, event_ids={"test:deferred"}, now=due) == 1
            )
            assert await collect_review_batch(session) is not None
            await session.commit()
        else:
            assert await collect_review_batch(session) is None
        assert await dispatch_registration_digest(session, owner_id=42, send=send, now=due) == 0
        assert await dispatch_registration_digest(
            session, owner_id=42, send=send, now=due + timedelta(minutes=2)
        ) == (0 if review_change else 1)
        assert (
            await dispatch_registration_digest(
                session, owner_id=42, send=send, now=due + timedelta(days=1)
            )
            == 0
        )
    assert len(sent) == (0 if review_change else 1)


@pytest.mark.asyncio
async def test_digest_does_not_reannounce_skipped_registration(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    due = datetime(2026, 9, 9, 6, tzinfo=UTC)

    async def send(_user: int, _text: str) -> None:
        pytest.fail("A skipped fact must not generate another broadcast")

    async with factory() as session:
        await ensure_user_profile(session, 42, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:skipped", title="Skipped", source_kind="NTO", source_url="https://example.org/"
        )
        event.milestones = [
            Milestone(
                id="test:skipped:open",
                kind="registration_open",
                title="Open",
                starts_at=due.replace(hour=5),
                status="confirmed",
            )
        ]
        session.add(event)
        await session.flush()
        session.add(
            OpenEventNotice(
                telegram_user_id=42,
                event_id=event.id,
                milestone_id="test:skipped:open",
                phase="registration:test:skipped:open",
                status="skipped",
            )
        )
        await session.commit()
    async with factory() as session:
        assert (
            await dispatch_registration_digest(
                session,
                owner_id=42,
                send=send,
                now=due,
            )
            == 0
        )


@pytest.mark.asyncio
async def test_digest_window_filters_retry_and_restart(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        sent.append(text)

    async def fail(_user_id: int, _text: str) -> None:
        raise RuntimeError("offline")

    due = datetime(2026, 9, 6, 6, tzinfo=UTC)
    async with factory() as session:
        profile = await ensure_user_profile(
            session,
            42,
            "Europe/Moscow",
            onboarding_completed=True,
        )
        profile.tag_filters = ["informatics"]
        for index, (hour, status, tags) in enumerate(
            [
                (5, "confirmed", ["informatics"]),
                (7, "confirmed", ["informatics"]),
                (5, "tentative", ["informatics"]),
                (5, "confirmed", ["physics"]),
            ]
        ):
            event = Event(
                id=f"test:event-{index}",
                title=f"Event <{index}>",
                source_kind="RSOSH",
                source_url="https://example.org/",
                tags=tags,
            )
            session.add(event)
            await session.flush()
            session.add(
                Milestone(
                    id=f"test:opening-{index}",
                    event_id=event.id,
                    kind="registration_open",
                    title="Open",
                    status=status,
                    starts_at=due.replace(hour=hour),
                )
            )
        await session.commit()
        assert (
            await dispatch_registration_digest(
                session,
                owner_id=42,
                send=send,
                now=due.replace(hour=5),
            )
            == 0
        )
        profile.access_status = AccessStatus.BLOCKED.value
        await session.commit()
        assert await dispatch_registration_digest(session, owner_id=42, send=send, now=due) == 0
        profile.access_status = AccessStatus.ACTIVE.value
        await session.commit()
        assert await dispatch_registration_digest(session, owner_id=42, send=fail, now=due) == 0
        assert not sent
        assert await dispatch_registration_digest(session, owner_id=42, send=send, now=due) == 0
        assert await collect_review_batch(session) is None
        assert (
            await dispatch_registration_digest(
                session, owner_id=42, send=send, now=due + timedelta(minutes=2)
            )
            == 1
        )
        assert "Event &lt;0&gt;" in sent[0]
    async with factory() as session:
        assert await dispatch_registration_digest(session, owner_id=42, send=send, now=due) == 0
        assert (
            await dispatch_registration_digest(
                session,
                owner_id=42,
                send=send,
                now=due.replace(day=7),
            )
            == 1
        )
        assert await collect_review_batch(session) is None
        assert "Event &lt;1&gt;" in sent[1]
        assert (
            await dispatch_registration_digest(
                session,
                owner_id=42,
                send=send,
                now=due.replace(day=8),
            )
            == 0
        )


@pytest.mark.asyncio
async def test_automatic_opening_failure_does_not_starve_later_openings(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    now = datetime(2026, 9, 10, 6, tzinfo=UTC)  # 09:00 Moscow digest.
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        if "Broken" in text:
            raise RuntimeError("recipient temporarily unavailable")
        sent.append(text)

    async with factory() as session:
        await ensure_user_profile(session, 42, "Europe/Moscow", onboarding_completed=True)
        for event_id, title in (("test:broken", "Broken"), ("test:healthy", "Healthy")):
            session.add(
                Event(
                    id=event_id,
                    title=title,
                    source_kind="NTO",
                    source_url="https://example.org/",
                    milestones=[
                        Milestone(
                            id=f"{event_id}:open",
                            kind="registration_open",
                            title="Open",
                            starts_at=now - timedelta(hours=1),
                            status="confirmed",
                        )
                    ],
                )
            )
        await session.commit()

        assert await dispatch_registration_digest(session, owner_id=42, send=send, now=now) == 1
        assert len(sent) == 1 and "Healthy" in sent[0]
        broken = await session.scalar(
            select(OpenEventNotice).where(OpenEventNotice.event_id == "test:broken")
        )
        healthy = await session.scalar(
            select(OpenEventNotice).where(OpenEventNotice.event_id == "test:healthy")
        )
        assert broken is not None and broken.status == "automatic" and broken.attempts == 1
        assert broken.next_attempt_at is not None
        assert broken.next_attempt_at.replace(tzinfo=UTC) == now + timedelta(minutes=2)
        assert healthy is not None and healthy.status == "sent"


@pytest.mark.asyncio
async def test_automatic_opening_recovers_after_more_than_five_transient_failures(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    now = datetime(2026, 9, 10, 6, tzinfo=UTC)
    failures = 0
    sent: list[str] = []

    async def unavailable(_user_id: int, _text: str) -> None:
        nonlocal failures
        failures += 1
        raise RuntimeError("network outage")

    async def recovered(_user_id: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        await ensure_user_profile(session, 42, "Europe/Moscow", onboarding_completed=True)
        session.add(
            Event(
                id="test:automatic-retry",
                title="Automatic retry",
                source_kind="NTO",
                source_url="https://example.org/",
                milestones=[
                    Milestone(
                        id="test:automatic-retry:open",
                        kind="registration_open",
                        title="Open",
                        starts_at=now - timedelta(hours=1),
                        status="confirmed",
                    )
                ],
            )
        )
        await session.commit()
        for offset in (0, 2, 6, 14, 30):
            assert (
                await dispatch_registration_digest(
                    session, owner_id=42, send=unavailable, now=now + timedelta(minutes=offset)
                )
                == 0
            )
        assert failures == 5
        assert (
            await dispatch_registration_digest(
                session, owner_id=42, send=recovered, now=now + timedelta(minutes=62)
            )
            == 1
        )
        notice = await session.scalar(select(OpenEventNotice))
        assert notice is not None and notice.status == "sent" and notice.attempts == 6
    assert len(sent) == 1
