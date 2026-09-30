from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from olymping.models import AccessStatus, Event, UserProfile
from olymping.services.filters import event_is_enabled
from olymping.services.subscriptions import reapply_profile
from olymping.services.users import AccessDeniedError


@dataclass(frozen=True)
class OnboardingResult:
    matched: int
    subscribed: int


async def complete_onboarding(session: AsyncSession, user_id: int) -> OnboardingResult:
    profile = await session.get(UserProfile, user_id)
    if profile is None or profile.access_status != AccessStatus.ACTIVE.value:
        raise AccessDeniedError("active profile required")
    if profile.school_grade is None:
        raise ValueError("choose a school grade first")
    events = list(await session.scalars(select(Event).where(Event.status != "cancelled")))
    matched = sum(event_is_enabled(profile, event) for event in events)
    subscribed, _ = await reapply_profile(session, profile, subscribe_matches=True)
    profile.onboarding_completed = True
    await session.flush()
    return OnboardingResult(matched, subscribed)
