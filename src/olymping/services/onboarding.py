from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from olymping.models import AccessStatus, Event, EventPreference, UserProfile
from olymping.services.filters import event_is_enabled
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
    existing = set(
        await session.scalars(
            select(EventPreference.event_id).where(
                EventPreference.telegram_user_id == user_id,
            )
        )
    )
    events = list(await session.scalars(select(Event).where(Event.status != "cancelled")))
    matched = subscribed = 0
    for event in events:
        if not event_is_enabled(profile, event):
            continue
        matched += 1
        if event.id not in existing:
            session.add(
                EventPreference(
                    telegram_user_id=user_id,
                    event_id=event.id,
                    interest="watching",
                )
            )
            subscribed += 1
    profile.onboarding_completed = True
    await session.flush()
    return OnboardingResult(matched, subscribed)
