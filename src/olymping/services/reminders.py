from __future__ import annotations

import html
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from olymping.models import (
    AccessStatus,
    CatalogNotice,
    DeliveryStatus,
    Event,
    EventInterest,
    EventPreference,
    Milestone,
    MilestoneKind,
    NotificationDelivery,
    OpenEventNotice,
    RecordStatus,
    ReminderMode,
    ReminderRule,
    UserProfile,
)
from olymping.presentation import telegram_time
from olymping.services.availability import registration_deadline
from olymping.services.delivery import DeliveryDeferred
from olymping.services.filters import event_is_enabled

logger = logging.getLogger(__name__)
SendMessage = Callable[[int, str], Awaitable[None]]

REMINDER_NORMAL = "normal"
REMINDER_CUSTOM = "custom"
REMINDER_MUTED = "muted"
REGISTRATION_DIGEST = "registration_open_digest"


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def schedule_rule(rule: ReminderRule, milestone: Milestone, timezone: str) -> datetime | None:
    if milestone.starts_at is None:
        return None
    starts_at = aware_utc(milestone.starts_at)
    if rule.mode == ReminderMode.OFFSET.value and rule.offset_minutes is not None:
        return starts_at - timedelta(minutes=rule.offset_minutes)
    if (
        rule.mode == ReminderMode.CALENDAR.value
        and rule.days_before is not None
        and rule.local_time
    ):
        tz = ZoneInfo(timezone)
        event_date = starts_at.astimezone(tz).date()
        target_date: date = event_date - timedelta(days=rule.days_before)
        hour, minute = (int(part) for part in rule.local_time.split(":", maxsplit=1))
        return datetime.combine(target_date, time(hour, minute), tzinfo=tz).astimezone(UTC)
    return None


def reminder_state(rules: list[ReminderRule]) -> str:
    if not rules:
        return REMINDER_NORMAL
    if any(rule.enabled for rule in rules):
        return REMINDER_CUSTOM
    return REMINDER_MUTED


async def event_reminder_state(session: AsyncSession, user_id: int, event_id: str) -> str:
    result = await session.execute(
        select(ReminderRule).where(
            ReminderRule.telegram_user_id == user_id,
            ReminderRule.event_id == event_id,
        )
    )
    return reminder_state(list(result.scalars()))


def _rule_has_schedule(rule: ReminderRule) -> bool:
    return rule.offset_minutes is not None or (
        rule.days_before is not None and rule.local_time is not None
    )


async def set_event_reminders_muted(
    session: AsyncSession,
    *,
    user_id: int,
    event_id: str,
    muted: bool,
) -> str:
    result = await session.execute(
        select(ReminderRule).where(
            ReminderRule.telegram_user_id == user_id,
            ReminderRule.event_id == event_id,
        )
    )
    rules = list(result.scalars())
    if muted:
        if rules:
            for rule in rules:
                rule.enabled = False
        else:
            session.add(
                ReminderRule(
                    id=f"mute:{uuid4().hex}",
                    telegram_user_id=user_id,
                    event_id=event_id,
                    mode=ReminderMode.CALENDAR.value,
                    enabled=False,
                )
            )
        return REMINDER_MUTED
    scheduled_rules = [rule for rule in rules if _rule_has_schedule(rule)]
    for rule in rules:
        if rule in scheduled_rules:
            rule.enabled = True
        else:
            await session.delete(rule)
    return REMINDER_CUSTOM if scheduled_rules else REMINDER_NORMAL


async def _rules_for_event(
    session: AsyncSession, user_id: int, event: Event, milestone: Milestone
) -> list[ReminderRule]:
    event_rules_result = await session.execute(
        select(ReminderRule).where(
            ReminderRule.telegram_user_id == user_id,
            ReminderRule.event_id == event.id,
        )
    )
    event_rules = list(event_rules_result.scalars())
    candidates = event_rules
    if not event_rules:
        category_result = await session.execute(
            select(ReminderRule).where(
                ReminderRule.telegram_user_id == user_id,
                ReminderRule.event_id.is_(None),
                ReminderRule.source_kind == event.source_kind,
            )
        )
        candidates = list(category_result.scalars())
    return [
        rule
        for rule in candidates
        if rule.enabled and (rule.milestone_kind is None or rule.milestone_kind == milestone.kind)
    ]


def _reminder_text(event: Event, milestone: Milestone, profile: UserProfile, now: datetime) -> str:
    assert milestone.starts_at is not None
    when = telegram_time(milestone.starts_at, profile.timezone)
    label = html.escape(milestone.title)
    if milestone.kind == MilestoneKind.REGISTRATION_DEADLINE.value:
        tz = ZoneInfo(profile.timezone)
        deadline_date = aware_utc(milestone.starts_at).astimezone(tz).date()
        tomorrow = now.astimezone(tz).date() + timedelta(days=1)
        label = (
            "Завтра заканчивается регистрация"
            if deadline_date == tomorrow
            else "Регистрация заканчивается"
        )
        if milestone.precision == "date":
            when = deadline_date.strftime("%d.%m.%Y") + " включительно"
    link = html.escape(event.url or event.source_url, quote=True)
    return (
        f"⏰ <b>{html.escape(event.title)}</b>\n"
        f"{label}: <b>{when}</b> ({profile.timezone})\n"
        f'<a href="{link}">Открыть источник</a>'
    )


async def dispatch_due_reminders(
    session: AsyncSession,
    *,
    owner_id: int,
    send: SendMessage,
    now: datetime | None = None,
    grace_hours: int = 24,
) -> int:
    now = aware_utc(now or datetime.now(UTC))
    profile = await session.get(UserProfile, owner_id)
    if profile is None or profile.access_status != AccessStatus.ACTIVE.value:
        return 0
    milestone_result = await session.execute(
        select(Milestone)
        .options(selectinload(Milestone.event))
        .where(
            Milestone.status == RecordStatus.CONFIRMED.value,
            Milestone.starts_at.is_not(None),
        )
    )
    preference_result = await session.execute(
        select(EventPreference).where(EventPreference.telegram_user_id == owner_id)
    )
    preferences = {item.event_id: item.interest for item in preference_result.scalars()}
    sent = 0
    for milestone in milestone_result.scalars():
        event = milestone.event
        interest = preferences.get(event.id)
        if event.status == RecordStatus.CANCELLED.value or not event_is_enabled(profile, event):
            continue
        if interest not in {
            EventInterest.WATCHING.value,
            EventInterest.REGISTERED.value,
        }:
            continue
        if interest == EventInterest.REGISTERED.value and milestone.kind in {
            MilestoneKind.REGISTRATION_OPEN.value,
            MilestoneKind.REGISTRATION_DEADLINE.value,
        }:
            continue
        if (
            milestone.kind == MilestoneKind.REGISTRATION_DEADLINE.value
            and registration_deadline(milestone) <= now
        ):
            continue
        rules = await _rules_for_event(session, owner_id, event, milestone)
        for rule in rules:
            scheduled = schedule_rule(rule, milestone, profile.timezone)
            if scheduled is None or not (now - timedelta(hours=grace_hours) <= scheduled <= now):
                continue
            existing_result = await session.execute(
                select(NotificationDelivery).where(
                    NotificationDelivery.telegram_user_id == owner_id,
                    NotificationDelivery.milestone_id == milestone.id,
                    NotificationDelivery.reminder_rule_id == rule.id,
                    NotificationDelivery.scheduled_for == scheduled,
                )
            )
            delivery = existing_result.scalar_one_or_none()
            if delivery is not None and delivery.status in {
                DeliveryStatus.SENT.value,
                DeliveryStatus.SUPERSEDED.value,
            }:
                continue
            if delivery is None:
                delivery = NotificationDelivery(
                    telegram_user_id=owner_id,
                    milestone_id=milestone.id,
                    reminder_rule_id=rule.id,
                    scheduled_for=scheduled,
                )
                session.add(delivery)
                await session.flush()
            if delivery.attempts >= 5:
                continue
            delivery.attempts += 1
            try:
                await send(owner_id, _reminder_text(event, milestone, profile, now))
                delivery.status = DeliveryStatus.SENT.value
                delivery.sent_at = now
                delivery.error = None
                sent += 1
            except DeliveryDeferred:
                delivery.attempts -= 1
                delivery.status = DeliveryStatus.PENDING.value
                delivery.error = None
                await session.commit()
                raise
            except Exception as exc:
                delivery.status = DeliveryStatus.FAILED.value
                delivery.error = f"{type(exc).__name__}: {exc}"[:2000]
                logger.exception("Failed to send reminder %s", delivery.id)
            # Persist each outcome before pacing or attempting the next message.
            await session.commit()
    return sent


async def dispatch_catalog_notices(
    session: AsyncSession,
    *,
    owner_id: int,
    send: SendMessage,
    limit: int = 20,
) -> int:
    from olymping.services.reviews import dispatch_reviewed_notices

    return await dispatch_reviewed_notices(session, owner_id=owner_id, send=send, catalog_only=True)


async def dispatch_registration_digest(
    session: AsyncSession,
    *,
    owner_id: int,
    send: SendMessage,
    now: datetime | None = None,
) -> int:
    now = aware_utc(now or datetime.now(UTC))
    local_now = now.astimezone(ZoneInfo("Europe/Moscow"))
    cutoff = local_now.replace(hour=9, minute=0, second=0, microsecond=0)
    if local_now < cutoff:
        return 0
    profile = await session.get(UserProfile, owner_id)
    if (
        profile is None
        or profile.access_status != AccessStatus.ACTIVE.value
        or not profile.onboarding_completed
        or not profile.notify_open_events
    ):
        return 0
    openings = await session.scalars(
        select(Milestone)
        .options(selectinload(Milestone.event).selectinload(Event.milestones))
        .where(
            Milestone.kind == MilestoneKind.REGISTRATION_OPEN.value,
            Milestone.status == RecordStatus.CONFIRMED.value,
            Milestone.starts_at > cutoff.astimezone(UTC) - timedelta(days=1),
            Milestone.starts_at <= cutoff.astimezone(UTC),
        )
        .order_by(Milestone.starts_at, Milestone.id)
    )
    notified = set(
        await session.scalars(
            select(CatalogNotice.event_id).where(
                CatalogNotice.telegram_user_id == owner_id,
                CatalogNotice.kind == REGISTRATION_DIGEST,
            )
        )
    )
    notified.update(
        await session.scalars(
            select(OpenEventNotice.event_id).where(
                OpenEventNotice.telegram_user_id == owner_id,
                OpenEventNotice.phase.like("registration:%"),
            )
        )
    )
    events: list[Event] = []
    for opening in openings:
        assert opening.starts_at is not None
        event = opening.event
        if event.id in notified or event.status == RecordStatus.CANCELLED.value:
            continue
        if not event_is_enabled(profile, event):
            continue
        preference = await session.get(EventPreference, (owner_id, event.id))
        if preference is not None and preference.interest in {
            EventInterest.IGNORED.value,
            EventInterest.REGISTERED.value,
        }:
            continue
        deadlines = [
            registration_deadline(stage)
            for stage in event.milestones
            if stage.kind == MilestoneKind.REGISTRATION_DEADLINE.value
            and stage.status == RecordStatus.CONFIRMED.value
            and stage.starts_at is not None
            and aware_utc(stage.starts_at) >= aware_utc(opening.starts_at)
        ]
        if deadlines and min(deadlines) <= now:
            continue
        events.append(event)
        notified.add(event.id)
    for event in events:
        session.add(
            CatalogNotice(
                telegram_user_id=owner_id,
                event_id=event.id,
                kind=REGISTRATION_DIGEST,
                summary="Открылась регистрация за последние сутки.",
            )
        )
    await session.commit()
    return len(events)


async def run_notification_cycle(
    factory: async_sessionmaker[AsyncSession],
    *,
    owner_id: int,
    send: SendMessage,
    grace_hours: int,
    registration_digest: bool = False,
) -> tuple[int, int]:
    async with factory() as session:
        reminders = await dispatch_due_reminders(
            session, owner_id=owner_id, send=send, grace_hours=grace_hours
        )
        await session.commit()
        if registration_digest:
            await dispatch_registration_digest(session, owner_id=owner_id, send=send)
        from olymping.services.reviews import collect_review_batch, dispatch_reviewed_notices

        await collect_review_batch(session)
        await session.commit()
        changes = await dispatch_reviewed_notices(session, owner_id=owner_id, send=send)
        return reminders, changes
