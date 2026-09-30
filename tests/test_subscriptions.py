import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import CatalogNotice, Event, EventInterest, EventPreference
from olymping.schemas import CalendarDocument
from olymping.services.filters import event_is_enabled
from olymping.services.importer import import_document
from olymping.services.reviews import collect_review_batch, decide_review, dispatch_reviewed_notices
from olymping.services.subscriptions import reapply_profile
from olymping.services.user_state import toggle_event_interest
from olymping.services.users import ensure_admin_profile, ensure_user_profile


def document(tags: list[str]) -> CalendarDocument:
    return CalendarDocument.model_validate(
        {
            "calendar_version": 1,
            "events": [
                {
                    "id": "test:reapply",
                    "title": "Reapply",
                    "source_kind": "NTO",
                    "source_url": "https://example.org/",
                    "tags": tags,
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_reapply_preserves_explicit_choices_and_reviews_personal_removal(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    packets: list[tuple[int, str, list[str]]] = []

    async def send(_user: int, _text: str) -> None:
        pytest.fail("Personal changes must carry action buttons")

    async def actions(user: int, text: str, events: list[str]) -> None:
        packets.append((user, text, events))

    async with factory() as session:
        await import_document(session, document(["mathematics"]))
        admin = await ensure_admin_profile(session, 1, "Europe/Moscow")
        admin.onboarding_completed = True
        admin.auto_subscribe_new_events = False
        for user, origin, interest in [
            (2, "automatic", "watching"),
            (3, "manual", "watching"),
            (4, "automatic", "registered"),
            (5, "manual", "ignored"),
        ]:
            profile = await ensure_user_profile(
                session, user, "Europe/Moscow", onboarding_completed=True
            )
            profile.tag_filters = ["mathematics"]
            session.add(
                EventPreference(
                    telegram_user_id=user, event_id="test:reapply", origin=origin, interest=interest
                )
            )
        newcomer = await ensure_user_profile(session, 6, "Europe/Moscow", onboarding_completed=True)
        newcomer.tag_filters = ["biology"]
        await session.commit()
        result = await import_document(session, document(["biology"]))
        assert result.notices == 2
        await session.commit()
        assert await session.get(EventPreference, (2, "test:reapply")) is None
        for user in (3, 4, 5):
            assert await session.get(EventPreference, (user, "test:reapply")) is not None
        added = await session.get(EventPreference, (6, "test:reapply"))
        assert added is not None and added.origin == "automatic"
        assert (await import_document(session, document(["biology"]))).notices == 0
        batch = await collect_review_batch(session)
        assert batch is not None
        await session.commit()
        assert (
            await dispatch_reviewed_notices(
                session, owner_id=2, send=send, send_with_actions=actions
            )
            == 0
        )
        await decide_review(session, batch_id=batch, actor_id=1, approve=True)
        await session.commit()
        assert (
            await dispatch_reviewed_notices(
                session, owner_id=2, send=send, send_with_actions=actions
            )
            == 1
        )
        assert (
            await dispatch_reviewed_notices(
                session, owner_id=6, send=send, send_with_actions=actions
            )
            == 1
        )
    async with factory() as session:
        assert await collect_review_batch(session) is None
        assert (
            await dispatch_reviewed_notices(
                session, owner_id=2, send=send, send_with_actions=actions
            )
            == 0
        )
        # A later reverse transition is a new personal change, not a duplicate global fact.
        assert (await import_document(session, document(["mathematics"]))).notices == 2
        assert await collect_review_batch(session) is not None
    assert len(packets) == 2
    assert "Автоподписка снята".lower() in packets[0][1].lower()
    assert "Математика → Биология" in packets[0][1]
    assert packets[0][2] == ["test:reapply"]


@pytest.mark.asyncio
async def test_manual_subscription_overrides_only_topics_and_unsubscribe_is_preserved(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await import_document(session, document(["biology"]))
        profile = await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        profile.tag_filters = ["mathematics"]
        event = await session.get(Event, "test:reapply")
        assert event is not None
        assert not event_is_enabled(profile, event)
        await toggle_event_interest(
            session, actor_id=2, event_id=event.id, interest=EventInterest.WATCHING
        )
        await session.flush()
        pref = await session.get(EventPreference, (2, event.id))
        assert pref is not None and pref.origin == "manual"
        assert event_is_enabled(profile, event, preference=pref)
        profile.category_settings = {"NTO": False}
        assert not event_is_enabled(profile, event, preference=pref)
        profile.category_settings = {"NTO": True}
        profile.school_grade = 11
        event.max_grade = 9
        assert not event_is_enabled(profile, event, preference=pref)
        await toggle_event_interest(
            session, actor_id=2, event_id=event.id, interest=EventInterest.WATCHING
        )
        await session.commit()
        assert (await import_document(session, document(["mathematics"]))).notices == 0
        pref = await session.get(EventPreference, (2, event.id))
        assert pref is not None and pref.interest == "unsubscribed"
        assert not list(await session.scalars(select(CatalogNotice)))


def test_registration_overrides_topic_filter_but_auto_subscription_does_not() -> None:
    from olymping.models import UserProfile

    profile = UserProfile(telegram_user_id=1, tag_filters=["mathematics"])
    event = Event(id="test:bio", tags=["biology"], source_kind="NTO")
    pref = EventPreference(
        telegram_user_id=1, event_id=event.id, origin="automatic", interest="watching"
    )
    assert not event_is_enabled(profile, event, preference=pref)
    pref.interest = "registered"
    assert event_is_enabled(profile, event, preference=pref)


@pytest.mark.asyncio
async def test_reapply_profile_reconciles_only_automatic_watching_preferences(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        profile = await ensure_user_profile(session, 2, "Europe/Moscow", onboarding_completed=True)
        profile.school_grade = 9
        profile.tag_filters = ["mathematics"]
        session.add_all(
            [
                Event(
                    id="test:old-auto",
                    title="Old automatic",
                    source_kind="NTO",
                    tags=["mathematics"],
                    min_grade=5,
                    max_grade=11,
                    source_url="https://example.org/old-auto",
                ),
                Event(
                    id="test:new-auto",
                    title="New automatic",
                    source_kind="NTO",
                    tags=["biology"],
                    min_grade=5,
                    max_grade=11,
                    source_url="https://example.org/new-auto",
                ),
                Event(
                    id="test:manual-watch",
                    title="Manual watch",
                    source_kind="NTO",
                    tags=["mathematics"],
                    min_grade=5,
                    max_grade=11,
                    source_url="https://example.org/manual-watch",
                ),
                Event(
                    id="test:manual-ignored",
                    title="Manual ignored",
                    source_kind="NTO",
                    tags=["mathematics"],
                    min_grade=5,
                    max_grade=11,
                    source_url="https://example.org/manual-ignored",
                ),
                Event(
                    id="test:manual-registered",
                    title="Manual registered",
                    source_kind="NTO",
                    tags=["mathematics"],
                    min_grade=5,
                    max_grade=11,
                    source_url="https://example.org/manual-registered",
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                EventPreference(
                    telegram_user_id=2,
                    event_id="test:old-auto",
                    interest="watching",
                    origin="automatic",
                ),
                EventPreference(
                    telegram_user_id=2,
                    event_id="test:manual-watch",
                    interest="watching",
                    origin="manual",
                ),
                EventPreference(
                    telegram_user_id=2,
                    event_id="test:manual-ignored",
                    interest="ignored",
                    origin="manual",
                ),
                EventPreference(
                    telegram_user_id=2,
                    event_id="test:manual-registered",
                    interest="registered",
                    origin="manual",
                ),
            ]
        )
        await session.commit()

        profile.tag_filters = ["biology"]
        added, removed = await reapply_profile(session, profile)
        await session.commit()

        assert (added, removed) == (1, 1)
        preferences = {
            preference.event_id: (preference.interest, preference.origin)
            for preference in await session.scalars(
                select(EventPreference).where(EventPreference.telegram_user_id == 2)
            )
        }
        assert preferences == {
            "test:new-auto": ("watching", "automatic"),
            "test:manual-watch": ("watching", "manual"),
            "test:manual-ignored": ("ignored", "manual"),
            "test:manual-registered": ("registered", "manual"),
        }
