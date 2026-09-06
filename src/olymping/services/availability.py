from __future__ import annotations

import html
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from olymping.models import (
    AccessStatus,
    CatalogNotice,
    Event,
    EventInterest,
    EventPreference,
    Milestone,
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
    openings = [stage for stage in stages if stage.kind == "registration_open"]
    deadlines = [stage for stage in stages if stage.kind == "registration_deadline"]
    future_deadlines = sorted(
        [
            stage
            for stage in deadlines
            if stage.starts_at is not None and registration_deadline(stage) > now
        ],
        key=registration_deadline,
    )
    result: list[OpenPhase] = []
    # A future confirmed deadline without an opening follows /register semantics.
    if future_deadlines:
        deadline = future_deadlines[0]
        matching = [
            stage
            for stage in openings
            if stage.starts_at is not None
            and _utc(stage.starts_at) < registration_deadline(deadline)
        ]
        latest = max(matching, key=lambda stage: _utc(stage.starts_at or now), default=None)
        if not openings or (latest is not None and _utc(latest.starts_at or now) <= now):
            key = latest.id if latest else deadline.id
            result.append(OpenPhase(f"registration:{key}", deadline.id, "Открыта регистрация"))
    elif openings and not deadlines:
        latest = max(openings, key=lambda stage: _utc(stage.starts_at or now))
        final_ends = [
            stage.ends_at for stage in stages if stage.kind == "final" and stage.ends_at is not None
        ]
        if _utc(latest.starts_at or now) <= now and (
            not final_ends or max(_utc(value) for value in final_ends) > now
        ):
            result.append(OpenPhase(f"registration:{latest.id}", latest.id, "Открыта регистрация"))
    for stage in stages:
        if stage.kind not in {"qualifier", "team_stage", "final", "competition"}:
            continue
        assert stage.starts_at is not None
        # Without a confirmed end we cannot assert that participation is still open.
        if stage.ends_at is not None and _utc(stage.starts_at) <= now < _utc(stage.ends_at):
            result.append(OpenPhase(f"stage:{stage.id}", stage.id, f"Идёт этап: {stage.title}"))
    return result


def _allowed(profile: UserProfile, event: Event, interest: str | None, phase: str) -> bool:
    return (
        profile.access_status == AccessStatus.ACTIVE.value
        and profile.onboarding_completed
        and profile.notify_open_events
        and event_is_enabled(profile, event)
        and interest != EventInterest.IGNORED.value
        and not (phase.startswith("registration:") and interest == EventInterest.REGISTERED.value)
    )


async def queue_open_event_notices(session: AsyncSession, *, now: datetime | None = None) -> int:
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
    events = list(await session.scalars(select(Event).options(selectinload(Event.milestones))))
    preferences = {
        (p.telegram_user_id, p.event_id): p.interest
        for p in await session.scalars(select(EventPreference))
    }
    digested = set(
        (
            await session.execute(
                select(
                    CatalogNotice.telegram_user_id,
                    CatalogNotice.event_id,
                ).where(
                    CatalogNotice.kind == "registration_open_digest",
                    CatalogNotice.sent_at.is_not(None),
                )
            )
        ).all()
    )
    queued = 0
    for event in events:
        for phase in open_phases(event, now):
            for profile in profiles:
                user_id = profile.telegram_user_id
                if not _allowed(profile, event, preferences.get((user_id, event.id)), phase.phase):
                    continue
                if phase.phase.startswith("registration:") and (user_id, event.id) in digested:
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
                    .on_conflict_do_nothing(
                        index_elements=["telegram_user_id", "event_id", "phase"],
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
    now = _utc(now or datetime.now(UTC))
    profile = await session.get(UserProfile, owner_id)
    if profile is None or profile.access_status != AccessStatus.ACTIVE.value:
        return 0
    notices = list(
        await session.scalars(
            select(OpenEventNotice)
            .where(
                OpenEventNotice.telegram_user_id == owner_id,
                OpenEventNotice.status == "pending",
                or_(
                    OpenEventNotice.next_attempt_at.is_(None),
                    OpenEventNotice.next_attempt_at <= now,
                ),
            )
            .order_by(OpenEventNotice.id)
            .limit(40)
        )
    )
    pending: list[tuple[OpenEventNotice, str]] = []
    for notice in notices:
        event = await session.scalar(
            select(Event).options(selectinload(Event.milestones)).where(Event.id == notice.event_id)
        )
        pref = await session.get(EventPreference, (owner_id, notice.event_id))
        if event is None or not _allowed(
            profile,
            event,
            pref.interest if pref else None,
            notice.phase,
        ):
            notice.status = "skipped"
            continue
        phase = next((p for p in open_phases(event, now) if p.phase == notice.phase), None)
        if phase is None:
            notice.status = "skipped"
            continue
        link = html.escape(event.url or event.source_url, quote=True)
        # One entry per message: bounded even with long titles and links.
        text = (
            f"🟢 <b>{html.escape(event.title)}</b>\n"
            f"{html.escape(phase.title)}\n"
            f'<a href="{link}">Открыть страницу события</a>'
        )
        pending.append((notice, text))
    await session.commit()
    sent = 0
    for notice, text in pending:
        notice.attempts += 1
        try:
            await send(owner_id, text)
        except Exception as exc:
            logger.warning("Open-event notice %s failed (%s)", notice.id, type(exc).__name__)
            notice.next_attempt_at = now + timedelta(minutes=min(60, 2**notice.attempts))
            if notice.attempts >= 5:
                notice.status = "failed"
        else:
            notice.sent_at = now
            notice.status = "sent"
            sent += 1
        await session.commit()
    return sent
