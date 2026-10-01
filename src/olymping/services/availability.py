from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from olymping.models import (
    AccessStatus,
    CatalogNotice,
    DeliveryStatus,
    Event,
    EventInterest,
    EventPreference,
    Milestone,
    NotificationDelivery,
    OpenEventNotice,
    RecordStatus,
    UserProfile,
)
from olymping.services.filters import event_is_enabled

logger = logging.getLogger(__name__)
SendMessage = Callable[[int, str], Awaitable[None]]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def registration_deadline(stage: Milestone) -> datetime:
    """A date-only deadline includes its stated calendar day."""
    assert stage.starts_at is not None
    value = _utc(stage.starts_at)
    if stage.precision == "date":
        value += timedelta(days=1)
    return value


@dataclass(frozen=True)
class OpenPhase:
    phase: str
    milestone_id: str
    title: str


def open_phases(event: Event, now: datetime) -> list[OpenPhase]:
    """Only confirmed, currently available registration or participation windows."""
    now = _utc(now)
    if event.status == RecordStatus.CANCELLED.value:
        return []
    stages = [
        stage
        for stage in event.milestones
        if stage.status == RecordStatus.CONFIRMED.value and stage.starts_at is not None
    ]
    openings = sorted(
        (stage for stage in stages if stage.kind == "registration_open"),
        key=lambda stage: _utc(stage.starts_at or now),
    )
    deadlines = sorted(
        (stage for stage in stages if stage.kind == "registration_deadline"),
        key=registration_deadline,
    )
    result: list[OpenPhase] = []
    started = [stage for stage in openings if _utc(stage.starts_at or now) <= now]
    latest = started[-1] if started else None
    closed_deadlines = [stage for stage in deadlines if registration_deadline(stage) <= now]
    last_closed = registration_deadline(closed_deadlines[-1]) if closed_deadlines else None
    if latest is not None and (last_closed is None or _utc(latest.starts_at or now) >= last_closed):
        # A later opening begins a new wave.  Do not attach the current wave
        # to a deadline after that later opening: it may have its own deadline
        # (or deliberately have none).
        next_opening = next(
            (
                stage
                for stage in openings
                if _utc(stage.starts_at or now) > _utc(latest.starts_at or now)
            ),
            None,
        )
        deadline = next(
            (
                stage
                for stage in deadlines
                if registration_deadline(stage) > now
                and registration_deadline(stage) > _utc(latest.starts_at or now)
                and (
                    next_opening is None
                    or registration_deadline(stage) <= _utc(next_opening.starts_at or now)
                )
            ),
            None,
        )
        if deadline is not None:
            result.append(
                OpenPhase(f"registration:{latest.id}", deadline.id, "Открыта регистрация")
            )
        else:
            final_ends = [
                _utc(stage.ends_at)
                for stage in stages
                if stage.kind == "final" and stage.ends_at is not None
            ]
            if not final_ends or max(final_ends) > now:
                result.append(
                    OpenPhase(f"registration:{latest.id}", latest.id, "Открыта регистрация")
                )
    elif not openings:
        # Historical calendars can publish only a future deadline.  Preserve
        # that contract, but never infer a new wave from an old, closed one.
        deadline = next((stage for stage in deadlines if registration_deadline(stage) > now), None)
        if deadline is not None:
            result.append(
                OpenPhase(f"registration:{deadline.id}", deadline.id, "Открыта регистрация")
            )
    for stage in stages:
        if stage.kind not in {"qualifier", "team_stage", "final", "competition"}:
            continue
        assert stage.starts_at is not None
        # Without a confirmed end we cannot assert that participation is still open.
        if stage.ends_at is not None and _utc(stage.starts_at) <= now < _utc(stage.ends_at):
            result.append(OpenPhase(f"stage:{stage.id}", stage.id, f"Идёт этап: {stage.title}"))
    return result


def _allowed(
    profile: UserProfile, event: Event, preference: EventPreference | None, phase: str
) -> bool:
    interest = preference.interest if preference else None
    return (
        profile.access_status == AccessStatus.ACTIVE.value
        and profile.onboarding_completed
        and profile.notify_open_events
        and event_is_enabled(profile, event, preference=preference)
        and interest not in {EventInterest.IGNORED.value, "unsubscribed"}
        and not (phase.startswith("registration:") and interest == EventInterest.REGISTERED.value)
    )


async def queue_open_event_notices(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    event_ids: set[str] | None = None,
) -> int:
    if event_ids == set():
        return 0
    now = _utc(now or datetime.now(UTC))
    profiles = list(
        await session.scalars(
            select(UserProfile).where(
                UserProfile.access_status == AccessStatus.ACTIVE.value,
                UserProfile.onboarding_completed.is_(True),
                UserProfile.notify_open_events.is_(True),
            )
        )
    )
    query = (
        select(Event)
        .options(selectinload(Event.milestones))
        .execution_options(populate_existing=True)
    )
    if event_ids is not None:
        query = query.where(Event.id.in_(event_ids))
    events = list(await session.scalars(query))
    preferences = {
        (p.telegram_user_id, p.event_id): p for p in await session.scalars(select(EventPreference))
    }
    digested = set(
        (
            await session.execute(
                select(
                    CatalogNotice.telegram_user_id,
                    CatalogNotice.event_id,
                ).where(
                    CatalogNotice.kind == "registration_open_digest",
                )
            )
        ).all()
    )
    sent_registration_openings = set(
        (
            await session.execute(
                select(
                    NotificationDelivery.telegram_user_id,
                    NotificationDelivery.milestone_id,
                ).where(NotificationDelivery.status == DeliveryStatus.SENT.value)
            )
        ).all()
    )
    queued = 0
    from olymping.services.progression import stage_access, user_outcomes

    outcomes = {
        p.telegram_user_id: await user_outcomes(session, p.telegram_user_id) for p in profiles
    }
    for event in events:
        for phase in open_phases(event, now):
            for profile in profiles:
                user_id = profile.telegram_user_id
                stage = next(s for s in event.milestones if s.id == phase.milestone_id)
                if phase.phase.startswith("stage:") and outcomes[user_id].get(stage.id) in {
                    "passed",
                    "not_passed",
                    "skipped",
                }:
                    continue
                if (
                    stage_access(stage, {s.id: s for s in event.milestones}, outcomes[user_id])
                    == "blocked"
                ):
                    continue
                if not _allowed(profile, event, preferences.get((user_id, event.id)), phase.phase):
                    continue
                if phase.phase.startswith("registration:") and (user_id, event.id) in digested:
                    continue
                if (
                    phase.phase.startswith("registration:")
                    and (user_id, phase.phase.removeprefix("registration:"))
                    in sent_registration_openings
                ):
                    continue
                statement = (
                    insert(OpenEventNotice)
                    .values(
                        telegram_user_id=user_id,
                        event_id=event.id,
                        milestone_id=phase.milestone_id,
                        phase=phase.phase,
                        status="pending",
                        attempts=0,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_update(
                        index_elements=["telegram_user_id", "event_id", "phase"],
                        set_={"status": "pending", "next_attempt_at": None, "attempts": 0},
                        where=OpenEventNotice.status == "automatic",
                    )
                    .returning(OpenEventNotice.id)
                )
                if (await session.execute(statement)).scalar_one_or_none() is not None:
                    queued += 1
    return queued


async def dispatch_open_event_notices(
    session: AsyncSession,
    *,
    owner_id: int,
    send: SendMessage,
    now: datetime | None = None,
) -> int:
    from olymping.services.reviews import dispatch_reviewed_notices

    return await dispatch_reviewed_notices(
        session,
        owner_id=owner_id,
        send=send,
        now=now,
        open_only=True,
    )
