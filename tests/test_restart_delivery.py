import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.bot import prepare_database
from olymping.config import Settings
from olymping.db import create_engine, create_session_factory, upgrade_schema
from olymping.models import (
    Event,
    EventPreference,
    Milestone,
    NotificationDelivery,
    NotificationReview,
    ReminderRule,
)
from olymping.services.delivery import DeliveryDeferred
from olymping.services.reminders import dispatch_due_reminders, run_notification_cycle
from olymping.services.reviews import decide_review
from olymping.services.users import ensure_admin_profile, ensure_user_profile


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["pending", "dismissed", "approved"])
async def test_restart_and_calendar_deploy_never_approve_broadcasts(
    tmp_path: Path, decision: str
) -> None:
    now = datetime.now(UTC)
    calendar_dir = tmp_path / "calendar"
    calendar_dir.mkdir()
    data: dict[str, Any] = {
        "calendar_version": 1,
        "events": [
            {
                "id": "test:open",
                "title": "Open registration",
                "source_kind": "RSOSH",
                "source_url": "https://example.org/",
                "status": "confirmed",
                "milestones": [
                    {
                        "id": "test:open:start",
                        "kind": "registration_open",
                        "title": "Open",
                        "starts_at": (now - timedelta(days=3)).isoformat(),
                        "status": "confirmed",
                    },
                    {
                        "id": "test:open:end",
                        "kind": "registration_deadline",
                        "title": "Deadline",
                        "starts_at": (now + timedelta(days=10)).isoformat(),
                        "status": "confirmed",
                    },
                ],
            }
        ],
    }
    path = calendar_dir / "calendar.yaml"
    path.write_text(yaml.safe_dump(data))
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'restart.db'}",
        data_dir=calendar_dir,
        owner_telegram_id=1,
    )
    await upgrade_schema(settings.database_url)
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    sent: list[str] = []

    async def send(_user: int, text: str) -> None:
        sent.append(text)

    async def cycle() -> None:
        await run_notification_cycle(
            factory, owner_id=1, send=send, grace_hours=24, registration_digest=True
        )

    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        admin.auto_subscribe_new_events = False
        await session.commit()
    try:
        await prepare_database(engine, factory, settings)
        await cycle()
        assert not sent
        async with factory() as session:
            batch = await session.scalar(select(NotificationReview))
            assert batch is not None and batch.status == "pending"
            if decision != "pending":
                await decide_review(
                    session, batch_id=batch.id, actor_id=1, approve=decision == "approved"
                )
                await session.commit()
        await engine.dispose()
        engine = create_engine(settings.database_url)
        factory = create_session_factory(engine)
        await prepare_database(engine, factory, settings)
        await cycle()
        expected = int(decision == "approved")
        assert len(sent) == expected
        await prepare_database(engine, factory, settings)
        await cycle()
        assert len(sent) == expected
        # A deployment can add data, but cannot turn that data into an approved broadcast.
        data["events"].append(
            {
                "id": "test:new",
                "title": "New event",
                "source_kind": "NTO",
                "source_url": "https://example.org/",
            }
        )
        path.write_text(yaml.safe_dump(data))
        await prepare_database(engine, factory, settings)
        await cycle()
        assert len(sent) == expected
        async with factory() as session:
            assert (
                await session.scalar(
                    select(NotificationReview.id).where(NotificationReview.status == "pending")
                )
                is not None
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["cancelled", "flood"])
async def test_reminders_checkpoint_each_send_before_interruption(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    interruption: str,
) -> None:
    _, factory = database
    now = datetime.now(UTC)
    async with factory() as session:
        await ensure_user_profile(session, 1, "Europe/Moscow", onboarding_completed=True)
        event = Event(
            id="test:reminders",
            title="Event",
            source_kind="RSOSH",
            source_url="https://example.org/",
            status="confirmed",
        )
        session.add(event)
        await session.flush()
        for index in range(2):
            session.add(
                Milestone(
                    id=f"test:reminders:{index}",
                    event_id=event.id,
                    title=f"Stage {index}",
                    kind="qualifier",
                    starts_at=now,
                    precision="exact",
                    status="confirmed",
                )
            )
        session.add_all(
            [
                EventPreference(telegram_user_id=1, event_id=event.id, interest="watching"),
                ReminderRule(
                    id="test:rule",
                    telegram_user_id=1,
                    event_id=event.id,
                    mode="offset",
                    offset_minutes=0,
                    enabled=True,
                ),
            ]
        )
        await session.commit()
    messages: list[str] = []

    async def interrupted_send(_user: int, text: str) -> None:
        if messages:
            if interruption == "flood":
                raise DeliveryDeferred(120)
            raise asyncio.CancelledError
        messages.append(text)

    async with factory() as session:
        with pytest.raises(DeliveryDeferred if interruption == "flood" else asyncio.CancelledError):
            await dispatch_due_reminders(session, owner_id=1, send=interrupted_send, now=now)
    async with factory() as session:
        rows = list(await session.scalars(select(NotificationDelivery)))
        assert sum(row.status == "sent" for row in rows) == 1
        assert all(row.attempts == 0 for row in rows if row.status == "pending")

        async def recovered(_user: int, text: str) -> None:
            messages.append(text)

        assert await dispatch_due_reminders(session, owner_id=1, send=recovered, now=now) == 1
        assert len(messages) == 2 and len(set(messages)) == 2
        assert await dispatch_due_reminders(session, owner_id=1, send=recovered, now=now) == 0
