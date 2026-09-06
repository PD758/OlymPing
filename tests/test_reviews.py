from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import CatalogNotice, Event, NotificationReview, UserProfile
from olymping.review_ui import review_page
from olymping.schemas import CalendarDocument
from olymping.services.importer import import_data_directory, import_document
from olymping.services.reviews import (
    StaleReviewError,
    collect_review_batch,
    decide_review,
    dispatch_reviewed_notices,
    refresh_review,
    toggle_review_event,
)
from olymping.services.users import AccessDeniedError, ensure_admin_profile, ensure_user_profile


def calendar() -> CalendarDocument:
    return CalendarDocument.model_validate(
        {
            "calendar_version": 1,
            "events": [
                {
                    "id": "test:math",
                    "title": "Mathematics",
                    "source_kind": "RSOSH",
                    "source_url": "https://example.org/math",
                    "tags": ["mathematics"],
                },
                {
                    "id": "test:physics",
                    "title": "Physics",
                    "source_kind": "RSOSH",
                    "source_url": "https://example.org/physics",
                    "tags": ["physics"],
                },
            ],
        }
    )


async def seed_review(session: AsyncSession) -> int:
    admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
    admin.onboarding_completed = True
    friend = await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
    friend.tag_filters = ["mathematics"]
    await session.flush()
    await import_document(session, calendar())
    batch_id = await collect_review_batch(session)
    assert batch_id is not None
    await session.commit()
    return batch_id


@pytest.mark.asyncio
async def test_no_broadcast_until_approval_then_one_personalized_packet(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[tuple[int, str]] = []

    async def send(user_id: int, text: str) -> None:
        sent.append((user_id, text))

    async with factory() as session:
        batch_id = await seed_review(session)
        assert await dispatch_reviewed_notices(session, owner_id=1, send=send) == 0
        assert await dispatch_reviewed_notices(session, owner_id=2, send=send) == 0
        assert not sent
        assert await collect_review_batch(session) is None
        text, keyboard = await review_page(session, batch_id)
        assert "Mathematics" in text and "Physics" in text
        assert any(
            button.callback_data == f"review:approve:{batch_id}"
            for row in keyboard.inline_keyboard
            for button in row
        )
        assert await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
        await session.commit()
        assert not await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
        assert await dispatch_reviewed_notices(session, owner_id=1, send=send) == 2
        assert await dispatch_reviewed_notices(session, owner_id=2, send=send) == 1
        assert len(sent) == 2
        assert "Physics" in sent[0][1]
        assert "Mathematics" in sent[1][1] and "Physics" not in sent[1][1]
    async with factory() as session:
        assert await dispatch_reviewed_notices(session, owner_id=1, send=send) == 0
        assert len(sent) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("approve", [True, False])
async def test_deselection_or_dismissal_prevents_broadcast(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    approve: bool,
) -> None:
    _, factory = database
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        batch_id = await seed_review(session)
        assert await toggle_review_event(session, batch_id=batch_id, actor_id=1, index=0)
        await session.commit()
        assert await decide_review(session, batch_id=batch_id, actor_id=1, approve=approve)
        await session.commit()
        assert not await toggle_review_event(session, batch_id=batch_id, actor_id=1, index=1)
        assert await dispatch_reviewed_notices(session, owner_id=2, send=send) == 0
        assert await dispatch_reviewed_notices(session, owner_id=1, send=send) == int(approve)
        if approve:
            assert "Mathematics" not in sent[0]
        else:
            assert not sent


@pytest.mark.asyncio
async def test_only_admin_can_decide_and_stale_review_is_rejected(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        batch_id = await seed_review(session)
        with pytest.raises(AccessDeniedError):
            await decide_review(session, batch_id=batch_id, actor_id=2, approve=True)
        with pytest.raises(AccessDeniedError):
            await toggle_review_event(session, batch_id=batch_id, actor_id=2, index=0)
        event = await session.get(Event, "test:math")
        assert event is not None
        event.title = "Updated mathematics"
        await session.commit()
        with pytest.raises(StaleReviewError):
            await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
        await session.rollback()
        batch = await session.get(NotificationReview, batch_id)
        assert batch is not None and batch.status == "pending"
        assert await refresh_review(session, batch_id=batch_id, actor_id=1)
        await session.commit()
        assert await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)


@pytest.mark.asyncio
async def test_current_filters_are_rechecked_after_approval(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database

    async def send(_user_id: int, _text: str) -> None:
        pytest.fail("filtered or blocked recipient must not receive a packet")

    async with factory() as session:
        batch_id = await seed_review(session)
        await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
        profile = await session.get(UserProfile, 2)
        assert profile is not None
        profile.tag_filters = ["biology"]
        await session.commit()
        assert await dispatch_reviewed_notices(session, owner_id=2, send=send) == 0


@pytest.mark.asyncio
async def test_import_reports_actual_delta_and_resolves_patch_noise(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    tmp_path: Path,
) -> None:
    _, factory = database
    start = datetime(2026, 9, 17, tzinfo=UTC)
    raw = {
        "calendar_version": 1,
        "events": [
            {
                "id": "test:dated",
                "title": "Olympiad",
                "source_kind": "NTO",
                "status": "confirmed",
                "source_url": "https://example.org/",
                "milestones": [
                    {
                        "id": "test:dated:qualifier",
                        "title": "Отбор",
                        "kind": "qualifier",
                        "status": "confirmed",
                        "starts_at": start.isoformat(),
                    }
                ],
            }
        ],
    }
    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        await import_document(
            session, CalendarDocument.model_validate(raw), create_new_event_notices=False
        )
        await session.commit()
        tentative = CalendarDocument.model_validate(raw).model_dump(mode="json")
        tentative["events"][0]["status"] = "tentative"
        (tmp_path / "01.yaml").write_text(yaml.safe_dump(tentative))
        (tmp_path / "02.yaml").write_text(yaml.safe_dump(raw))
        summary = await import_data_directory(session, tmp_path)
        assert summary.updated_events == 0 and summary.notices == 0
        changed = CalendarDocument.model_validate(raw)
        changed.events[0].milestones[0].starts_at = start + timedelta(days=3)
        await import_document(session, changed)
        await session.commit()
        notice = await session.scalar(select(CatalogNotice))
        assert notice is not None
        assert "17.09.2026" in notice.summary and "20.09.2026" in notice.summary
        assert "на 3 дн. позже" in notice.summary
        assert "starts_at" not in notice.summary


@pytest.mark.asyncio
async def test_review_pagination_and_packets_fit_telegram_limit(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    packets: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        assert len(text.encode("utf-16-le")) // 2 <= 4096
        packets.append(text)

    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        for index in range(20):
            event = Event(
                id=f"test:long-{index}",
                title="<&🎉" * 100,
                source_kind="RSOSH",
                source_url="https://example.org/",
            )
            session.add(event)
            await session.flush()
            session.add(
                CatalogNotice(
                    telegram_user_id=1,
                    event_id=event.id,
                    kind="event_updated",
                    summary="Дата сдвинулась 🎉 & " * 100,
                )
            )
        batch_id = await collect_review_batch(session)
        assert batch_id is not None
        await session.commit()
        text, keyboard = await review_page(session, batch_id)
        assert len(text.encode("utf-16-le")) // 2 <= 4096
        assert any(button.text == "→" for row in keyboard.inline_keyboard for button in row)
        await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
        await session.commit()
        assert await dispatch_reviewed_notices(session, owner_id=1, send=send) == 20
        assert len(packets) > 1
