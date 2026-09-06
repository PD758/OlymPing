from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.db import create_engine, create_schema, create_session_factory


@pytest.fixture
async def database(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    await create_schema(engine)
    factory = create_session_factory(engine)
    yield engine, factory
    await engine.dispose()


async def approve_pending_reviews(session: AsyncSession) -> None:
    """Exercise the real admin approval path for legacy delivery regression tests."""
    from sqlalchemy import select

    from olymping.models import NotificationReview, UserProfile
    from olymping.services.reviews import collect_review_batch, decide_review

    profile = await session.scalar(
        select(UserProfile).order_by(UserProfile.telegram_user_id).limit(1)
    )
    assert profile is not None
    profile.role = "admin"
    profile.onboarding_completed = True
    await session.flush()
    await collect_review_batch(session)
    await session.commit()
    batch_ids = list(
        await session.scalars(
            select(NotificationReview.id).where(
                NotificationReview.status == "pending",
            )
        )
    )
    for batch_id in batch_ids:
        await decide_review(
            session, batch_id=batch_id, actor_id=profile.telegram_user_id, approve=True
        )
    await session.commit()
