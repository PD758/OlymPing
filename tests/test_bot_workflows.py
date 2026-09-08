from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.bot import create_router
from olymping.config import Settings
from olymping.models import CatalogNotice, Event, EventPreference, NotificationReview, UserProfile
from olymping.services.reviews import collect_review_batch
from olymping.services.users import ensure_admin_profile, ensure_user_profile


def callback_update(user_id: int, data: str, update_id: int) -> Update:
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=str(update_id),
            from_user=User(id=user_id, is_bot=False, first_name="Tester"),
            chat_instance="test",
            data=data,
            message=Message(
                message_id=77,
                date=datetime.now(UTC),
                chat=Chat(id=user_id, type="private"),
                text="Questionnaire",
            ),
        ),
    )


@pytest.mark.parametrize(
    ("selection", "source", "tags"),
    [
        ("mathematics", "RSOSH", ["mathematics"]),
        ("group:vosh", "VOSH", ["literature"]),
        ("group:mosh", "MOSH", []),
    ],
)
@pytest.mark.asyncio
async def test_real_onboarding_callbacks_populate_existing_subscriptions(
    selection: str,
    source: str,
    tags: list[str],
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await ensure_user_profile(session, 2, "Europe/Moscow")
        session.add(
            Event(
                id="test:math",
                title="Math",
                tags=tags,
                source_kind=source,
                source_url="https://example.org/",
                max_grade=11,
            )
        )
        await session.commit()
    bot = Bot(token="123456:test-token")
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(factory, Settings(owner_telegram_id=1)))
    response = Message(message_id=77, date=datetime.now(UTC), chat=Chat(id=2, type="private"))
    transport = AsyncMock(return_value=response)
    try:
        with patch.object(Bot, "__call__", new=transport):
            for index, data in enumerate(
                ("onboard:grade:9", f"onboard:tag:0:{selection}", "onboard:done")
            ):
                await dispatcher.feed_update(bot, callback_update(2, data, index + 1))
        async with factory() as session:
            profile = await session.get(UserProfile, 2)
            preference = await session.get(EventPreference, (2, "test:math"))
            assert profile is not None and profile.onboarding_completed
            assert profile.school_grade == 9 and profile.tag_filters == [selection]
            assert preference is not None and preference.interest == "watching"
        assert transport.await_count >= 3
    finally:
        await bot.session.close()


@pytest.mark.asyncio
async def test_review_buttons_enforce_admin_and_are_idempotent(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        session.add(
            Event(
                id="test:math", title="Math", source_kind="RSOSH", source_url="https://example.org/"
            )
        )
        await session.flush()
        session.add(
            CatalogNotice(telegram_user_id=2, event_id="test:math", kind="new_event", summary="new")
        )
        batch_id = await collect_review_batch(session)
        assert batch_id is not None
        await session.commit()
    bot = Bot(token="123456:test-token")
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(factory, Settings(owner_telegram_id=1)))
    response = Message(message_id=77, date=datetime.now(UTC), chat=Chat(id=1, type="private"))
    try:
        with patch.object(Bot, "__call__", new=AsyncMock(return_value=response)):
            await dispatcher.feed_update(bot, callback_update(2, f"review:approve:{batch_id}", 1))
            async with factory() as session:
                batch = await session.get(NotificationReview, batch_id)
                assert batch is not None and batch.status == "pending"
            await dispatcher.feed_update(bot, callback_update(1, f"review:approve:{batch_id}", 2))
            await dispatcher.feed_update(bot, callback_update(1, f"review:approve:{batch_id}", 3))
        async with factory() as session:
            batch = await session.get(NotificationReview, batch_id)
            assert batch is not None and batch.status == "approved" and batch.decided_by == 1
    finally:
        await bot.session.close()
