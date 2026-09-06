from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import (
    CatalogNotice,
    DeliveryStatus,
    Event,
    EventInterest,
    EventPreference,
    NoticeKind,
    NotificationDelivery,
    ReminderMode,
    ReminderRule,
    SourceKind,
    UserProfile,
)
from olymping.schemas import CalendarDocument
from olymping.services.importer import import_document, load_calendar_document
from olymping.services.users import ensure_user_profile


def document_at(when: datetime) -> CalendarDocument:
    return CalendarDocument.model_validate(
        {
            "calendar_version": 1,
            "events": [
                {
                    "id": "rsosh:test-2026",
                    "source_kind": "RSOSH",
                    "title": "Test olympiad",
                    "category": "informatics",
                    "source_url": "https://example.edu/official",
                    "status": "confirmed",
                    "milestones": [
                        {
                            "id": "rsosh:test-2026:final",
                            "kind": "final",
                            "title": "Final",
                            "starts_at": when.isoformat(),
                            "precision": "exact",
                            "status": "confirmed",
                        }
                    ],
                }
            ],
        }
    )


def test_seed_calendar_is_valid() -> None:
    paths = sorted(Path("data/calendar").glob("*.yaml"))
    assert paths
    documents = [load_calendar_document(path) for path in paths]
    events = [event for document in documents for event in document.events]

    assert len(events) >= 70
    assert sum(event.source_kind is SourceKind.VOSH for event in events) == 28
    assert sum(event.source_kind is SourceKind.MOSH for event in events) == 32

    security = next(event for event in events if event.id == "vosh:informatics-security-2026")
    school_stage = next(stage for stage in security.milestones if stage.id.endswith(":schedule"))
    municipal_stage = next(
        stage for stage in security.milestones if stage.id.endswith(":municipal-stage")
    )
    assert school_stage.is_online is True
    assert municipal_stage.is_online is False

    trackable_kinds = {"qualifier", "team_stage", "final", "competition"}
    for event in events:
        assert len(f"evt:{event.id}".encode()) <= 64
        for stage in event.milestones:
            if stage.kind.value in trackable_kinds:
                assert len(f"stage:{stage.id}".encode()) <= 64
                assert len(f"out:p:{stage.id}".encode()) <= 64


def test_grade_range_must_be_complete() -> None:
    with pytest.raises(ValueError, match="min_grade and max_grade"):
        CalendarDocument.model_validate(
            {
                "calendar_version": 1,
                "events": [
                    {
                        "id": "rsosh:invalid-grades",
                        "source_kind": "RSOSH",
                        "title": "Invalid grades",
                        "source_url": "https://example.edu/",
                        "min_grade": 8,
                    }
                ],
            }
        )


@pytest.mark.parametrize("source_kind", [SourceKind.NPK, SourceKind.MOSH])
def test_moscow_source_kinds_are_valid(source_kind: SourceKind) -> None:
    document = CalendarDocument.model_validate(
        {
            "calendar_version": 1,
            "events": [
                {
                    "id": f"{source_kind.value.lower()}:example-2026",
                    "source_kind": source_kind.value,
                    "title": "Engineering conference",
                    "source_url": "https://example.edu/conference",
                }
            ],
        }
    )

    assert document.events[0].source_kind is source_kind


@pytest.mark.asyncio
async def test_existing_profile_receives_defaults_for_new_source_kinds(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 73
    async with factory() as session:
        session.add(
            UserProfile(
                telegram_user_id=owner_id,
                timezone="Europe/Moscow",
                category_settings={"RSOSH": False},
                ctf_filters={},
            )
        )
        await session.commit()

        profile = await ensure_user_profile(session, owner_id, "Europe/Moscow")
        await session.flush()
        npk_rules = (
            (
                await session.execute(
                    select(ReminderRule).where(
                        ReminderRule.telegram_user_id == owner_id,
                        ReminderRule.source_kind == SourceKind.NPK.value,
                    )
                )
            )
            .scalars()
            .all()
        )

        assert profile.category_settings[SourceKind.NPK.value] is True
        assert profile.category_settings[SourceKind.RSOSH.value] is False
        assert len(npk_rules) == 3

        await ensure_user_profile(session, owner_id, "Europe/Moscow", onboarding_completed=True)
        await session.flush()
        npk_rules_after_second_call = (
            (
                await session.execute(
                    select(ReminderRule).where(
                        ReminderRule.telegram_user_id == owner_id,
                        ReminderRule.source_kind == SourceKind.NPK.value,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(npk_rules_after_second_call) == 3


@pytest.mark.asyncio
async def test_import_is_idempotent_and_date_change_supersedes(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 42
    initial = datetime(2026, 10, 10, 12, tzinfo=UTC)
    async with factory() as session:
        await ensure_user_profile(session, owner_id, "Europe/Moscow", onboarding_completed=True)
        first = await import_document(
            session,
            document_at(initial),
            create_new_event_notices=False,
        )
        await session.commit()
        assert first.created_events == 1
        assert first.created_milestones == 1

        second = await import_document(session, document_at(initial))
        await session.commit()
        assert second.updated_events == 0
        assert second.updated_milestones == 0

        rule = ReminderRule(
            id="custom:test",
            telegram_user_id=owner_id,
            event_id="rsosh:test-2026",
            mode=ReminderMode.OFFSET.value,
            offset_minutes=60,
        )
        session.add(rule)
        await session.flush()
        session.add(
            NotificationDelivery(
                telegram_user_id=owner_id,
                milestone_id="rsosh:test-2026:final",
                reminder_rule_id=rule.id,
                scheduled_for=initial - timedelta(hours=1),
            )
        )
        await session.commit()

        changed = await import_document(session, document_at(initial + timedelta(days=1)))
        await session.commit()
        assert changed.updated_milestones == 1
        assert changed.notices == 1
        delivery = (await session.execute(select(NotificationDelivery))).scalar_one()
        assert delivery.status == DeliveryStatus.SUPERSEDED.value
        assert (await session.execute(select(func.count(CatalogNotice.id)))).scalar_one() == 1
        assert await session.get(Event, "rsosh:test-2026") is not None


@pytest.mark.asyncio
async def test_new_event_notification_and_auto_subscription_are_independent(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    owner_id = 314
    async with factory() as session:
        profile = await ensure_user_profile(
            session, owner_id, "Europe/Moscow", onboarding_completed=True
        )
        profile.auto_subscribe_new_events = False
        profile.notify_new_events = True

        summary = await import_document(session, document_at(datetime(2026, 11, 1, tzinfo=UTC)))
        await session.commit()

        preference = await session.get(EventPreference, (owner_id, "rsosh:test-2026"))
        notice = (await session.execute(select(CatalogNotice))).scalar_one()
        assert preference is None
        assert summary.notices == 1
        assert notice.kind == NoticeKind.NEW_EVENT.value

        profile.auto_subscribe_new_events = True
        profile.notify_new_events = False
        second_document = CalendarDocument.model_validate(
            {
                "calendar_version": 1,
                "events": [
                    {
                        "id": "rsosh:second-2026",
                        "source_kind": "RSOSH",
                        "title": "Second olympiad",
                        "source_url": "https://example.edu/second",
                    }
                ],
            }
        )
        second_summary = await import_document(session, second_document)
        await session.commit()

        second_preference = await session.get(
            EventPreference,
            (owner_id, "rsosh:second-2026"),
        )
        assert second_preference is not None
        assert second_preference.interest == EventInterest.WATCHING.value
        assert second_summary.notices == 0
        assert (await session.execute(select(func.count(CatalogNotice.id)))).scalar_one() == 1
