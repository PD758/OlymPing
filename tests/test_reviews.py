from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from aiogram.exceptions import TelegramForbiddenError
from aiogram.methods import SendMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import (
    CatalogNotice,
    Event,
    EventPreference,
    Milestone,
    NotificationReview,
    OpenEventNotice,
    ReviewDelivery,
    ReviewSelection,
    StageProgress,
    UserProfile,
)
from olymping.review_ui import review_page
from olymping.schemas import CalendarDocument
from olymping.services.delivery import DeliveryDeferred
from olymping.services.importer import import_data_directory, import_document
from olymping.services.reviews import (
    StaleReviewError,
    collect_review_batch,
    decide_review,
    dispatch_reviewed_notices,
    event_fingerprint,
    legacy_event_fingerprint,
    refresh_review,
    toggle_review_event,
)
from olymping.services.users import AccessDeniedError, ensure_admin_profile, ensure_user_profile


@pytest.mark.asyncio
@pytest.mark.parametrize("approve", [True, False])
async def test_reviewed_facts_do_not_return_for_new_recipient_or_old_duplicate_batch(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    approve: bool,
) -> None:
    _, factory = database
    async with factory() as session:
        original = await seed_review(session)
        event = await session.get(Event, "test:math")
        assert event is not None
        duplicate = NotificationReview()
        session.add(duplicate)
        await session.flush()
        duplicate_id = duplicate.id
        session.add(
            ReviewSelection(
                review_batch_id=duplicate_id,
                event_id=event.id,
                snapshot_hash=event_fingerprint(event),
                summary="Добавлено в календарь.",
            )
        )
        session.add(
            CatalogNotice(
                telegram_user_id=1,
                event_id=event.id,
                kind="new_event",
                summary="old duplicate",
                review_batch_id=duplicate_id,
            )
        )
        await decide_review(session, batch_id=original, actor_id=1, approve=approve)
        original_selection = await session.get(ReviewSelection, (original, event.id))
        assert original_selection is not None
        # Simulate a package persisted by the release before full stage fields.
        original_selection.snapshot_hash = legacy_event_fingerprint(event)
        await session.commit()
    async with factory() as session:
        await ensure_user_profile(session, 3, "Europe/Moscow", onboarding_completed=True)
        late = CatalogNotice(
            telegram_user_id=3,
            event_id="test:math",
            kind="new_event",
            summary="new wording",
        )
        session.add(late)
        await session.flush()
        assert await collect_review_batch(session) is None
        assert late.sent_at is not None
        batch = await session.get(NotificationReview, duplicate_id)
        assert batch is not None and batch.status == "dismissed"
        await session.commit()
    async with factory() as session:
        assert await collect_review_batch(session) is None
        # A real change still requires a fresh decision.
        event = await session.get(Event, "test:math")
        assert event is not None
        event.title = "New title"
        session.add(
            CatalogNotice(
                telegram_user_id=1,
                event_id=event.id,
                kind="event_updated",
                summary="Название: Mathematics → New title",
            )
        )
        await session.flush()
        assert await collect_review_batch(session) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("approve", [False, True])
async def test_legacy_event_update_deduplicates_for_later_recipient(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    approve: bool,
) -> None:
    _, factory = database
    summary = "Уточнено место проведения."
    async with factory() as session:
        batch_id = await seed_review(session)
        event = await session.get(Event, "test:math")
        selection = await session.get(ReviewSelection, (batch_id, "test:math"))
        assert event is not None and selection is not None
        session.add(
            CatalogNotice(
                telegram_user_id=1,
                event_id=event.id,
                kind="event_updated",
                summary=summary,
                review_batch_id=batch_id,
            )
        )
        selection.snapshot_hash = legacy_event_fingerprint(event)
        if approve:
            assert await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
            # Simulate an approved package persisted before the new hash existed.
            selection.snapshot_hash = legacy_event_fingerprint(event)
        await session.commit()

    async with factory() as session:
        await ensure_user_profile(session, 3, "Europe/Moscow", onboarding_completed=True)
        late = CatalogNotice(
            telegram_user_id=3,
            event_id="test:math",
            kind="event_updated",
            summary=summary,
        )
        session.add(late)
        await session.flush()
        assert await collect_review_batch(session) is None
        if approve:
            assert late.sent_at is not None
        else:
            assert late.review_batch_id == batch_id


@pytest.mark.asyncio
@pytest.mark.parametrize("decided", [False, True])
async def test_open_registration_review_is_shared_across_recipients(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    decided: bool,
) -> None:
    from olymping.services.availability import queue_open_event_notices

    _, factory = database
    now = datetime.now(UTC)
    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        event = Event(
            id="nto:review", title="NTO", source_kind="NTO", source_url="https://example.org/"
        )
        event.milestones = [
            Milestone(
                id="nto:review:open",
                kind="registration_open",
                title="Open",
                starts_at=now - timedelta(hours=1),
                status="confirmed",
            )
        ]
        session.add(event)
        await session.commit()
        assert await queue_open_event_notices(session, now=now) == 1
        original = await collect_review_batch(session)
        assert original is not None
        if decided:
            await decide_review(session, batch_id=original, actor_id=1, approve=False)
        await session.commit()
    async with factory() as session:
        await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        await session.commit()
        assert await queue_open_event_notices(session, now=now + timedelta(days=1)) == 1
        assert await collect_review_batch(session) is None
        notice = await session.scalar(
            select(OpenEventNotice).where(
                OpenEventNotice.telegram_user_id == 2,
            )
        )
        assert notice is not None
        if decided:
            assert notice.status == "skipped"
        else:
            assert notice.review_batch_id == original
        await session.commit()


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
async def test_flood_wait_keeps_approved_notices_and_attempt_budget(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    from olymping.models import ReviewDelivery

    _, factory = database

    async def limited(_user: int, _text: str) -> None:
        raise DeliveryDeferred(120)

    async with factory() as session:
        batch = await seed_review(session)
        await decide_review(session, batch_id=batch, actor_id=1, approve=True)
        await session.commit()
        with pytest.raises(DeliveryDeferred):
            await dispatch_reviewed_notices(session, owner_id=1, send=limited)
    sent: list[str] = []

    async def recovered(_user: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        delivery = await session.get(ReviewDelivery, (batch, 1))
        assert delivery is not None and delivery.attempts == 0
        assert delivery.next_attempt_at is not None
        assert await dispatch_reviewed_notices(session, owner_id=1, send=recovered) == 0
        assert not sent
        assert (
            await dispatch_reviewed_notices(
                session, owner_id=1, send=recovered, now=datetime.now(UTC) + timedelta(seconds=121)
            )
            == 2
        )
        assert len(sent) == 1


@pytest.mark.asyncio
async def test_review_delivery_retries_transient_failures_but_stops_permanent_ones(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    start = datetime.now(UTC)

    async def unavailable(_user_id: int, _text: str) -> None:
        raise RuntimeError("temporary network outage")

    async with factory() as session:
        batch_id = await seed_review(session)
        assert await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
        await session.commit()

    for attempt in range(6):
        async with factory() as session:
            assert (
                await dispatch_reviewed_notices(
                    session,
                    owner_id=1,
                    send=unavailable,
                    now=start + timedelta(hours=2 * attempt),
                )
                == 0
            )
            delivery = await session.get(ReviewDelivery, (batch_id, 1))
            assert delivery is not None
            assert delivery.status == "pending" and delivery.attempts == attempt + 1

    sent: list[str] = []

    async def recovered(_user_id: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        assert (
            await dispatch_reviewed_notices(
                session,
                owner_id=1,
                send=recovered,
                now=start + timedelta(hours=13),
            )
            == 2
        )
        assert sent

        session.add(
            CatalogNotice(
                telegram_user_id=1,
                event_id="test:math",
                kind="event_updated",
                summary="Постоянно отклоняемое сообщение.",
            )
        )
        await session.flush()
        permanent_batch = await collect_review_batch(session)
        assert permanent_batch is not None
        assert await decide_review(session, batch_id=permanent_batch, actor_id=1, approve=True)
        await session.commit()

        async def forbidden(_user_id: int, _text: str) -> None:
            raise TelegramForbiddenError(SendMessage(chat_id=1, text="review"), "bot was blocked")

        assert (
            await dispatch_reviewed_notices(
                session,
                owner_id=1,
                send=forbidden,
                now=start + timedelta(hours=14),
            )
            == 0
        )
        delivery = await session.get(ReviewDelivery, (permanent_batch, 1))
        assert delivery is not None and delivery.status == "failed"

        async def must_not_retry(_user_id: int, _text: str) -> None:
            pytest.fail("permanent review delivery failure must not retry")

        assert (
            await dispatch_reviewed_notices(
                session,
                owner_id=1,
                send=must_not_retry,
                now=start + timedelta(days=1),
            )
            == 0
        )


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
async def test_silent_review_decisions_consume_their_queue_rows(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        batch_id = await seed_review(session)
        assert await decide_review(session, batch_id=batch_id, actor_id=1, approve=False)
        await session.commit()
        dismissed = list(
            await session.scalars(
                select(CatalogNotice).where(CatalogNotice.review_batch_id == batch_id)
            )
        )
        assert dismissed and all(notice.sent_at is not None for notice in dismissed)

        session.add(
            CatalogNotice(
                telegram_user_id=1,
                event_id="test:math",
                kind="event_updated",
                summary="Уточнено расписание.",
            )
        )
        await session.flush()
        next_batch = await collect_review_batch(session)
        assert next_batch is not None
        assert await toggle_review_event(session, batch_id=next_batch, actor_id=1, index=0)
        assert await decide_review(session, batch_id=next_batch, actor_id=1, approve=True)
        await session.commit()
        excluded = list(
            await session.scalars(
                select(CatalogNotice).where(
                    CatalogNotice.review_batch_id == next_batch,
                    CatalogNotice.event_id == "test:math",
                )
            )
        )
        assert excluded and all(notice.sent_at is not None for notice in excluded)


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
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("location", "Новая площадка"),
        ("format", "очный"),
        ("is_online", True),
        ("source_url", "https://example.org/new-stage"),
    ],
)
async def test_review_is_stale_when_full_stage_metadata_changes(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    field: str,
    value: str | bool,
) -> None:
    _, factory = database
    async with factory() as session:
        batch_id = await seed_review(session)
        stage = Milestone(
            id="test:math:round",
            event_id="test:math",
            kind="round",
            title="Отборочный этап",
            status="confirmed",
        )
        session.add(stage)
        await session.flush()
        assert await refresh_review(session, batch_id=batch_id, actor_id=1)
        setattr(stage, field, value)
        await session.flush()

        with pytest.raises(StaleReviewError):
            await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage_changes_after_failure", [False, True])
async def test_legacy_approved_review_upgrades_before_retry(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
    stage_changes_after_failure: bool,
) -> None:
    _, factory = database
    delivered: list[str] = []
    start = datetime.now(UTC)

    async def unavailable(_user_id: int, _text: str) -> None:
        raise RuntimeError("temporary network outage")

    async def send(_user_id: int, text: str) -> None:
        delivered.append(text)

    async with factory() as session:
        batch_id = await seed_review(session)
        selection = await session.get(ReviewSelection, (batch_id, "test:math"))
        event = await session.get(Event, "test:math")
        batch = await session.get(NotificationReview, batch_id)
        assert selection is not None and event is not None and batch is not None
        stage = Milestone(
            id="test:math:legacy-stage",
            event_id=event.id,
            kind="round",
            title="Отборочный этап",
            status="confirmed",
        )
        session.add(stage)
        await session.flush()
        await session.refresh(event, attribute_names=["milestones"])
        selection.snapshot_hash = legacy_event_fingerprint(event)
        full_snapshot = event_fingerprint(event)
        batch.status = "approved"
        for notice in await session.scalars(
            select(CatalogNotice).where(
                CatalogNotice.review_batch_id == batch_id,
                CatalogNotice.event_id != event.id,
            )
        ):
            notice.sent_at = start
        await session.commit()

        assert (
            await dispatch_reviewed_notices(session, owner_id=1, send=unavailable, now=start) == 0
        )
        assert selection.snapshot_hash == full_snapshot
        if stage_changes_after_failure:
            stage.location = "Новая площадка"
        await session.commit()

        assert await dispatch_reviewed_notices(
            session, owner_id=1, send=send, now=start + timedelta(minutes=2)
        ) == (0 if stage_changes_after_failure else 1)
        assert bool(delivered) is not stage_changes_after_failure


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
async def test_delivery_rechecks_unsubscribe_and_registered_registration_updates(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    sent: list[str] = []

    async def send(_user_id: int, text: str) -> None:
        sent.append(text)

    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        event = Event(
            id="test:delivery-guard",
            title="Delivery guard",
            source_kind="NTO",
            source_url="https://example.org/",
        )
        event.milestones = [
            Milestone(
                id="test:delivery-guard:open",
                kind="registration_open",
                title="Registration",
            ),
            Milestone(
                id="test:delivery-guard:qualifier",
                kind="qualifier",
                title="Qualifier",
            ),
        ]
        session.add(event)
        await session.flush()
        registration = CatalogNotice(
            telegram_user_id=1,
            event_id=event.id,
            milestone_id="test:delivery-guard:open",
            kind="event_updated",
            summary="Изменилась регистрация.",
        )
        ordinary = CatalogNotice(
            telegram_user_id=1,
            event_id=event.id,
            milestone_id="test:delivery-guard:qualifier",
            kind="event_updated",
            summary="Изменился отборочный этап.",
        )
        session.add_all([registration, ordinary])
        await session.flush()
        batch_id = await collect_review_batch(session)
        assert batch_id is not None
        assert await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
        session.add(
            EventPreference(
                telegram_user_id=1,
                event_id=event.id,
                interest="registered",
            )
        )
        await session.commit()

        assert await dispatch_reviewed_notices(session, owner_id=1, send=send) == 1
        assert len(sent) == 1 and "отборочный этап" in sent[0]
        assert registration.sent_at is not None
        assert ordinary.sent_at is not None

        unsubscribed = CatalogNotice(
            telegram_user_id=1,
            event_id=event.id,
            kind="event_updated",
            summary="Эта новость не должна прийти.",
        )
        session.add(unsubscribed)
        await session.flush()
        next_batch = await collect_review_batch(session)
        assert next_batch is not None
        assert await decide_review(session, batch_id=next_batch, actor_id=1, approve=True)
        preference = await session.get(EventPreference, (1, event.id))
        assert preference is not None
        preference.interest = "unsubscribed"
        await session.commit()

        assert await dispatch_reviewed_notices(session, owner_id=1, send=send) == 0
        assert unsubscribed.sent_at is not None


@pytest.mark.asyncio
async def test_reviewed_stage_opening_is_skipped_after_own_final_outcome(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database

    async def send(_user_id: int, _text: str) -> None:
        pytest.fail("finished stage must not be announced")

    now = datetime.now(UTC)
    async with factory() as session:
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        event = Event(
            id="test:reviewed-outcome",
            title="Reviewed outcome",
            source_kind="NTO",
            source_url="https://example.org/",
        )
        event.milestones = [
            Milestone(
                id="test:reviewed-outcome:stage",
                kind="qualifier",
                title="Qualifier",
                status="confirmed",
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(hours=1),
            )
        ]
        session.add(event)
        await session.flush()
        notice = OpenEventNotice(
            telegram_user_id=1,
            event_id=event.id,
            milestone_id="test:reviewed-outcome:stage",
            phase="stage:test:reviewed-outcome:stage",
        )
        session.add(notice)
        await session.flush()
        batch_id = await collect_review_batch(session)
        assert batch_id is not None
        assert await decide_review(session, batch_id=batch_id, actor_id=1, approve=True)
        session.add(
            StageProgress(
                telegram_user_id=1,
                milestone_id="test:reviewed-outcome:stage",
                outcome="passed",
            )
        )
        await session.commit()

        assert await dispatch_reviewed_notices(session, owner_id=1, send=send, now=now) == 0
        assert notice.status == "skipped"


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
