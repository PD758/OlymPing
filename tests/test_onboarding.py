import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import Event, EventPreference
from olymping.services.onboarding import complete_onboarding
from olymping.services.users import AccessDeniedError, ensure_user_profile


@pytest.mark.asyncio
async def test_onboarding_matches_existing_calendar_and_preserves_manual_choices(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        profile = await ensure_user_profile(session, 1, "Europe/Moscow", school_grade=9)
        profile.tag_filters = ["mathematics"]
        profile.auto_subscribe_new_events = False
        for event_id, tags, max_grade, status in [
            ("test:match", ["mathematics"], 11, "tbd"),
            ("test:ignored", ["mathematics"], 11, "confirmed"),
            ("test:registered", ["mathematics"], 11, "confirmed"),
            ("test:younger", ["mathematics"], 8, "confirmed"),
            ("test:subject", ["physics"], 11, "confirmed"),
            ("test:cancelled", ["mathematics"], 11, "cancelled"),
        ]:
            session.add(
                Event(
                    id=event_id,
                    title=event_id,
                    tags=tags,
                    min_grade=5,
                    max_grade=max_grade,
                    status=status,
                    source_kind="RSOSH",
                    source_url="https://example.org/",
                )
            )
        await session.flush()
        session.add_all(
            [
                EventPreference(telegram_user_id=1, event_id="test:ignored", interest="ignored"),
                EventPreference(
                    telegram_user_id=1, event_id="test:registered", interest="registered"
                ),
            ]
        )
        await session.commit()
        result = await complete_onboarding(session, 1)
        await session.commit()
        assert (result.matched, result.subscribed) == (3, 1)
        assert profile.onboarding_completed
        prefs = {p.event_id: p.interest for p in await session.scalars(select(EventPreference))}
        assert prefs == {
            "test:match": "watching",
            "test:ignored": "ignored",
            "test:registered": "registered",
        }
        assert (await complete_onboarding(session, 1)).subscribed == 0


@pytest.mark.asyncio
async def test_onboarding_requires_grade_and_active_access(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        profile = await ensure_user_profile(session, 1, "Europe/Moscow")
        with pytest.raises(ValueError, match="grade"):
            await complete_onboarding(session, 1)
        profile.school_grade = 10
        profile.access_status = "blocked"
        with pytest.raises(AccessDeniedError):
            await complete_onboarding(session, 1)
        profile.access_status = "active"
        result = await complete_onboarding(session, 1)
        assert result.matched == result.subscribed == 0
        assert profile.onboarding_completed
