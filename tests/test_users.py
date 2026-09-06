from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from olymping.models import (
    AccessStatus,
    Event,
    EventInterest,
    EventPreference,
    Invitation,
    Milestone,
    ReminderMode,
    ReminderRule,
    StageOutcome,
    StageProgress,
    UserProfile,
    UserRole,
)
from olymping.services.reminders import set_event_reminders_muted
from olymping.services.user_state import set_stage_outcome, toggle_event_interest
from olymping.services.users import (
    AccessDeniedError,
    active_user_ids,
    create_invitation,
    ensure_admin_profile,
    ensure_user_profile,
    redeem_invitation,
    set_user_access,
)


@pytest.mark.asyncio
async def test_admin_profile_is_bootstrapped_from_settings(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        profile = await ensure_admin_profile(session, 100, "Europe/Moscow")
        await session.commit()

        assert profile.role == UserRole.ADMIN.value
        assert profile.access_status == AccessStatus.ACTIVE.value
        assert profile.onboarding_completed is False
        assert profile.school_grade is None
        assert await active_user_ids(session) == []
        profile.school_grade = 9
        profile.tag_filters = ["informatics"]
        profile.onboarding_completed = True
        await session.commit()
        restored = await ensure_admin_profile(session, 100, "Europe/Moscow")
        assert restored.school_grade == 9
        assert restored.tag_filters == ["informatics"]
        assert restored.onboarding_completed is True


@pytest.mark.asyncio
async def test_invitation_is_single_use_and_starts_personal_onboarding(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await ensure_admin_profile(session, 100, "Europe/Moscow")
        invitation = await create_invitation(
            session,
            created_by=100,
            lifetime=timedelta(days=7),
        )
        token = invitation.token
        await session.commit()

        friend = await redeem_invitation(
            session,
            token=token,
            telegram_user_id=200,
            timezone="Europe/Moscow",
            username="friend",
            display_name="Friend",
        )
        await session.commit()

        assert friend is not None
        assert friend.telegram_user_id == 200
        assert friend.role == UserRole.USER.value
        assert friend.school_grade is None
        assert friend.onboarding_completed is False
        used_invitation = await session.get(Invitation, token)
        assert used_invitation is not None
        await session.refresh(used_invitation)
        assert used_invitation.used_by == 200
        assert used_invitation.used_at is not None

        second_friend = await redeem_invitation(
            session,
            token=token,
            telegram_user_id=201,
            timezone="Europe/Moscow",
            username=None,
            display_name="Second friend",
        )
        assert second_friend is None


@pytest.mark.asyncio
async def test_invitation_can_be_claimed_by_only_one_concurrent_user(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await ensure_admin_profile(session, 100, "Europe/Moscow")
        invitation = await create_invitation(session, created_by=100)
        token = invitation.token
        await session.commit()

    async def redeem(user_id: int) -> UserProfile | None:
        async with factory() as session:
            profile = await redeem_invitation(
                session,
                token=token,
                telegram_user_id=user_id,
                timezone="Europe/Moscow",
                username=None,
                display_name=str(user_id),
            )
            await session.commit()
            return profile

    results = await asyncio.gather(redeem(200), redeem(300))
    winners = [profile for profile in results if profile is not None]
    assert len(winners) == 1

    async with factory() as session:
        claimed = await session.get(Invitation, token)
        profiles = list(
            (
                await session.execute(
                    select(UserProfile).where(UserProfile.telegram_user_id.in_([200, 300]))
                )
            ).scalars()
        )
        assert claimed is not None
        assert claimed.used_by == winners[0].telegram_user_id
        assert [profile.telegram_user_id for profile in profiles] == [winners[0].telegram_user_id]


@pytest.mark.asyncio
async def test_users_have_isolated_preferences_and_blocked_users_are_inactive(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await ensure_admin_profile(session, 100, "Europe/Moscow")
        first_invite = await create_invitation(session, created_by=100)
        second_invite = await create_invitation(session, created_by=100)
        first = await redeem_invitation(
            session,
            token=first_invite.token,
            telegram_user_id=200,
            timezone="Europe/Moscow",
            username="first",
            display_name="First",
        )
        second = await redeem_invitation(
            session,
            token=second_invite.token,
            telegram_user_id=300,
            timezone="Europe/Moscow",
            username="second",
            display_name="Second",
        )
        assert first is not None
        assert second is not None
        first.school_grade = 11
        first.tag_filters = ["cybersecurity"]
        first.onboarding_completed = True
        second.school_grade = 9
        second.tag_filters = ["ecology"]
        second.onboarding_completed = True
        session.add(
            Event(
                id="rsosh:isolation-test",
                source_kind="RSOSH",
                title="Isolation test",
                category="informatics",
                tags=["cybersecurity"],
                source_url="https://example.edu/isolation",
                status="confirmed",
            )
        )
        await session.flush()
        session.add(
            EventPreference(
                telegram_user_id=200,
                event_id="rsosh:isolation-test",
                interest=EventInterest.REGISTERED.value,
            )
        )
        await session.commit()

        preferences = list((await session.execute(select(EventPreference))).scalars())
        assert [(item.telegram_user_id, item.interest) for item in preferences] == [
            (200, EventInterest.REGISTERED.value)
        ]
        assert await active_user_ids(session) == [200, 300]

        second.access_status = AccessStatus.BLOCKED.value
        await session.commit()
        assert await active_user_ids(session) == [200]


@pytest.mark.asyncio
async def test_regular_user_cannot_issue_invites_or_change_another_users_access(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        await ensure_admin_profile(session, 100, "Europe/Moscow")
        await ensure_user_profile(
            session,
            200,
            "Europe/Moscow",
            onboarding_completed=True,
            school_grade=11,
        )
        target = await ensure_user_profile(
            session,
            300,
            "Europe/Moscow",
            onboarding_completed=True,
            school_grade=10,
        )
        await session.commit()

        with pytest.raises(AccessDeniedError):
            await create_invitation(session, created_by=200)
        with pytest.raises(AccessDeniedError):
            await set_user_access(
                session,
                actor_id=200,
                target_id=300,
                status=AccessStatus.BLOCKED,
            )
        assert target.access_status == AccessStatus.ACTIVE.value

        changed = await set_user_access(
            session,
            actor_id=100,
            target_id=300,
            status=AccessStatus.BLOCKED,
        )
        assert changed is target
        assert target.access_status == AccessStatus.BLOCKED.value
        assert (
            await set_user_access(
                session,
                actor_id=100,
                target_id=100,
                status=AccessStatus.BLOCKED,
            )
            is None
        )


@pytest.mark.asyncio
async def test_preferences_progress_settings_and_reminders_are_actor_scoped(
    database: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> None:
    _, factory = database
    async with factory() as session:
        first = await ensure_user_profile(
            session,
            200,
            "Europe/Moscow",
            onboarding_completed=True,
            school_grade=11,
        )
        second = await ensure_user_profile(
            session,
            300,
            "Europe/Moscow",
            onboarding_completed=True,
            school_grade=9,
        )
        event = Event(
            id="rsosh:actor-scope",
            source_kind="RSOSH",
            title="Actor scope",
            category="informatics",
            source_url="https://example.edu/actor-scope",
            status="confirmed",
        )
        milestone = Milestone(
            id="rsosh:actor-scope:final",
            event_id=event.id,
            kind="final",
            title="Final",
            precision="unknown",
            status="tbd",
        )
        session.add_all([event, milestone])
        await session.flush()
        session.add_all(
            [
                EventPreference(
                    telegram_user_id=300,
                    event_id=event.id,
                    interest=EventInterest.IGNORED.value,
                ),
                StageProgress(
                    telegram_user_id=300,
                    milestone_id=milestone.id,
                    outcome=StageOutcome.SKIPPED.value,
                ),
                ReminderRule(
                    id="actor:first",
                    telegram_user_id=200,
                    event_id=event.id,
                    mode=ReminderMode.CALENDAR.value,
                    days_before=1,
                    local_time="20:00",
                ),
                ReminderRule(
                    id="actor:second",
                    telegram_user_id=300,
                    event_id=event.id,
                    mode=ReminderMode.CALENDAR.value,
                    days_before=2,
                    local_time="19:00",
                ),
            ]
        )
        await session.commit()

        first.school_grade = 10
        first.tag_filters = ["cybersecurity"]
        await toggle_event_interest(
            session,
            actor_id=200,
            event_id=event.id,
            interest=EventInterest.WATCHING,
        )
        await set_stage_outcome(
            session,
            actor_id=200,
            milestone_id=milestone.id,
            outcome=StageOutcome.PASSED,
        )
        await set_event_reminders_muted(
            session,
            user_id=200,
            event_id=event.id,
            muted=True,
        )
        await session.commit()

        second_preference = await session.get(EventPreference, (300, event.id))
        second_progress = await session.get(StageProgress, (300, milestone.id))
        second_rule = await session.get(ReminderRule, "actor:second")
        assert second.school_grade == 9
        assert second.tag_filters == []
        assert second_preference is not None
        assert second_preference.interest == EventInterest.IGNORED.value
        assert second_progress is not None
        assert second_progress.outcome == StageOutcome.SKIPPED.value
        assert second_rule is not None
        assert second_rule.enabled is True

        first_preference = await session.get(EventPreference, (200, event.id))
        first_progress = await session.get(StageProgress, (200, milestone.id))
        first_rule = await session.get(ReminderRule, "actor:first")
        assert first.school_grade == 10
        assert first.tag_filters == ["cybersecurity"]
        assert first_preference is not None
        assert first_preference.interest == EventInterest.WATCHING.value
        assert first_progress is not None
        assert first_progress.outcome == StageOutcome.PASSED.value
        assert first_rule is not None
        assert first_rule.enabled is False
