from datetime import UTC, datetime

import pytest
from conftest import approve_pending_reviews
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import AccessStatus, Event, Milestone, OpenEventNotice
from olymping.services.reminders import dispatch_registration_digest
from olymping.services.reviews import dispatch_reviewed_notices
from olymping.services.users import ensure_user_profile


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
        assert await dispatch_registration_digest(session, owner_id=42, send=fail, now=due) == 1
        assert not sent
        assert await dispatch_registration_digest(session, owner_id=42, send=send, now=due) == 0
        await approve_pending_reviews(session)
        assert await dispatch_reviewed_notices(session, owner_id=42, send=send, now=due) == 1
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
        await approve_pending_reviews(session)
        assert (
            await dispatch_reviewed_notices(session, owner_id=42, send=send, now=due.replace(day=7))
            == 1
        )
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
