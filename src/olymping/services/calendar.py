from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from olymping.models import (
    Event,
    EventInterest,
    EventPreference,
    Milestone,
    RecordStatus,
    SourceKind,
    UserProfile,
)
from olymping.services.availability import registration_deadline
from olymping.services.filters import event_is_enabled
from olymping.services.progression import completed_for_user, stage_access, user_outcomes
from olymping.services.reminders import aware_utc


async def upcoming_events(
    session: AsyncSession,
    profile: UserProfile,
    *,
    starts_at: datetime,
    ends_at: datetime,
    limit: int = 30,
) -> list[tuple[Event, Milestone]]:
    if limit <= 0:
        return []
    start_utc = aware_utc(starts_at).astimezone(UTC)
    end_utc = aware_utc(ends_at).astimezone(UTC)
    result = await session.execute(
        select(Milestone)
        .options(selectinload(Milestone.event).selectinload(Event.milestones))
        .where(
            Milestone.status == RecordStatus.CONFIRMED.value,
            Milestone.starts_at >= start_utc,
            Milestone.starts_at < end_utc,
            Milestone.event_id.not_in(
                select(EventPreference.event_id).where(
                    EventPreference.telegram_user_id == profile.telegram_user_id,
                    EventPreference.interest == EventInterest.IGNORED.value,
                )
            ),
        )
        .order_by(Milestone.starts_at, Milestone.id)
    )
    items: list[tuple[Event, Milestone]] = []
    preferences = {
        p.event_id: p
        for p in await session.scalars(
            select(EventPreference).where(
                EventPreference.telegram_user_id == profile.telegram_user_id
            )
        )
    }
    outcomes = await user_outcomes(session, profile.telegram_user_id)
    for milestone in result.scalars():
        if (
            stage_access(milestone, {s.id: s for s in milestone.event.milestones}, outcomes)
            == "blocked"
        ):
            continue
        if milestone.event.status != RecordStatus.CANCELLED.value and event_is_enabled(
            profile, milestone.event, preference=preferences.get(milestone.event_id)
        ):
            items.append((milestone.event, milestone))
        if len(items) >= limit:
            break
    return items


async def get_event(session: AsyncSession, event_id: str) -> Event | None:
    result = await session.execute(
        select(Event).options(selectinload(Event.milestones)).where(Event.id == event_id)
    )
    return result.scalar_one_or_none()


async def all_olympiads(
    session: AsyncSession, profile: UserProfile, *, limit: int = 500
) -> list[Event]:
    result = await session.execute(
        select(Event)
        .options(selectinload(Event.milestones))
        .where(Event.source_kind != SourceKind.CTF.value)
        .order_by(Event.source_kind, Event.title)
        .limit(limit * 2)
    )
    preferences = {
        p.event_id: p
        for p in await session.scalars(
            select(EventPreference).where(
                EventPreference.telegram_user_id == profile.telegram_user_id
            )
        )
    }
    return [
        event
        for event in result.scalars()
        if event_is_enabled(profile, event, preference=preferences.get(event.id))
    ][:limit]


def registration_closes_at(event: Event, now: datetime) -> datetime | None:
    """Return the active registration deadline, or None when registration is closed."""
    now_utc = aware_utc(now)
    dated_openings = [
        aware_utc(milestone.starts_at)
        for milestone in event.milestones
        if milestone.kind == "registration_open"
        and milestone.status == RecordStatus.CONFIRMED.value
        and milestone.starts_at is not None
    ]
    if dated_openings and min(dated_openings) > now_utc:
        return None
    future_deadlines = [
        aware_utc(milestone.starts_at)
        for milestone in event.milestones
        if milestone.kind == "registration_deadline"
        and milestone.status == RecordStatus.CONFIRMED.value
        and milestone.starts_at is not None
        and registration_deadline(milestone) > now_utc
    ]
    if future_deadlines:
        return min(future_deadlines)
    return None


async def open_registration_events(
    session: AsyncSession,
    profile: UserProfile,
    *,
    now: datetime,
    limit: int = 500,
) -> list[Event]:
    if limit <= 0:
        return []
    events = await session.scalars(
        select(Event)
        .options(selectinload(Event.milestones))
        .where(
            Event.source_kind != SourceKind.CTF.value,
            Event.status != RecordStatus.CANCELLED.value,
            Event.id.not_in(
                select(EventPreference.event_id).where(
                    EventPreference.telegram_user_id == profile.telegram_user_id,
                    EventPreference.interest == EventInterest.IGNORED.value,
                )
            ),
        )
    )
    preferences = {
        p.event_id: p
        for p in await session.scalars(
            select(EventPreference).where(
                EventPreference.telegram_user_id == profile.telegram_user_id
            )
        )
    }
    outcomes = await user_outcomes(session, profile.telegram_user_id)
    active = [
        event
        for event in events
        if event_is_enabled(profile, event, preference=preferences.get(event.id))
        and not completed_for_user(event, outcomes, aware_utc(now))
        and registration_closes_at(event, now) is not None
    ]
    return sorted(
        active,
        key=lambda event: (
            registration_closes_at(event, now) or datetime.max.replace(tzinfo=UTC),
            event.title,
        ),
    )[:limit]
