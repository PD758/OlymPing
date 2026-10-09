from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import EventPreference
from olymping.schemas import CalendarDocument
from olymping.services.importer import import_document, load_calendar_document
from olymping.services.onboarding import complete_onboarding
from olymping.services.reminders import dispatch_due_reminders, dispatch_registration_digest
from olymping.services.users import ensure_user_profile


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subject",
    [
        "biology",
        "french",
        "ecology",
        "mathematics",
        "law",
        "chemistry",
        "chinese",
        "informatics-programming",
        "informatics-security",
        "economics",
        "informatics-ai",
    ],
)
@pytest.mark.parametrize("registered", [False, True])
async def test_vosh_school_calendar_delivers_opening_and_stage_reminders(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    subject: str,
    registered: bool,
) -> None:
    """Exercise the real seed and questionnaire, not a synthetic confirmed milestone."""
    _, factory = database
    document = load_calendar_document(Path("data/calendar/01_vosh_2026.yaml"))
    seed = next(event for event in document.events if event.id == f"vosh:{subject}-2026")
    opening = next(stage for stage in seed.milestones if stage.kind.value == "registration_open")
    school = next(stage for stage in seed.milestones if stage.advancement_paths == [])
    assert opening.starts_at is not None
    assert school.starts_at is not None
    async with factory() as session:
        await import_document(session, CalendarDocument(calendar_version=1, events=[seed]))
        profile = await ensure_user_profile(session, 42, "Europe/Moscow", school_grade=10)
        profile.tag_filters = ["group:vosh"]
        result = await complete_onboarding(session, 42)
        assert result.subscribed == 1
        if registered:
            preference = await session.get(EventPreference, (42, seed.id))
            assert preference is not None
            preference.interest = "registered"
        await session.commit()

    sent: list[str] = []

    async def send(_user: int, text: str) -> None:
        sent.append(text)

    # The default opening reminder is on the day itself, not a day in advance.
    async with factory() as session:
        assert (
            await dispatch_due_reminders(
                session,
                owner_id=42,
                send=send,
                now=opening.starts_at - timedelta(hours=4),
                grace_hours=1,
            )
            == 0
        )
    async with factory() as session:
        assert await dispatch_due_reminders(
            session,
            owner_id=42,
            send=send,
            now=opening.starts_at.replace(hour=8),
            grace_hours=1,
        ) == (0 if registered else 1)
    async with factory() as session:
        assert (
            await dispatch_registration_digest(
                session, owner_id=42, send=send, now=opening.starts_at.replace(hour=9)
            )
            == 0
        )
    for due in (
        (school.starts_at - timedelta(days=1)).replace(hour=20),
        school.starts_at.replace(hour=8),
    ):
        async with factory() as session:
            assert (
                await dispatch_due_reminders(
                    session, owner_id=42, send=send, now=due, grace_hours=1
                )
                == 1
            )
        # A new session/process must not repeat the same occurrence.
        async with factory() as session:
            assert (
                await dispatch_due_reminders(
                    session, owner_id=42, send=send, now=due, grace_hours=1
                )
                == 0
            )
    assert len(sent) == (2 if registered else 3)
    assert sum(school.title in text for text in sent) == 2
