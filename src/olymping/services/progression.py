from __future__ import annotations

import html
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from olymping.models import (
    Event,
    EventPreference,
    Milestone,
    ReminderRule,
    StageProgress,
    UserProfile,
    WorkflowNotice,
)
from olymping.services.delivery import DeliveryDeferred
from olymping.services.filters import event_is_enabled

TRACKABLE = {"qualifier", "team_stage", "final", "competition"}
logger = logging.getLogger(__name__)
SendWorkflow = Callable[[int, str, str, str], Awaitable[None]]


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def stage_access(
    stage: Milestone,
    stages: dict[str, Milestone],
    outcomes: dict[str, str],
    visiting: frozenset[str] = frozenset(),
) -> str:
    """Unknown eligibility remains visible; only exhausted explicit paths are blocked."""
    if stage.id in visiting:
        return "unknown"
    if not stage.advancement_paths:
        return "eligible" if stage.advancement_paths == [] else "unknown"
    states: list[str] = []
    for path in stage.advancement_paths:
        requirements: list[str] = []
        for parent_id in path:
            parent = stages.get(parent_id)
            result = outcomes.get(parent_id)
            if result == "passed":
                requirements.append("eligible")
            elif result in {"not_passed", "skipped"}:
                requirements.append("blocked")
            elif parent is None:
                requirements.append("unknown")
            else:
                access = stage_access(parent, stages, outcomes, visiting | {stage.id})
                requirements.append("blocked" if access == "blocked" else "unknown")
        states.append(
            "blocked"
            if "blocked" in requirements
            else "eligible"
            if all(s == "eligible" for s in requirements)
            else "unknown"
        )
    return "eligible" if "eligible" in states else "unknown" if "unknown" in states else "blocked"


async def user_outcomes(session: AsyncSession, user_id: int) -> dict[str, str]:
    return {
        row.milestone_id: row.outcome
        for row in await session.scalars(
            select(StageProgress).where(StageProgress.telegram_user_id == user_id)
        )
    }


def completed_for_user(event: Event, outcomes: dict[str, str], now: datetime) -> bool:
    stages = {stage.id: stage for stage in event.milestones}
    upcoming: list[Milestone] = []
    for stage in stages.values():
        end = finished_at(stage)
        if (
            stage.kind in TRACKABLE
            and stage.status != "cancelled"
            and outcomes.get(stage.id) not in {"passed", "not_passed", "skipped"}
            and (end is None or end > now)
        ):
            upcoming.append(stage)
    if not upcoming:
        return any(s.id in outcomes for s in stages.values() if s.kind in TRACKABLE)
    return all(stage_access(s, stages, outcomes) == "blocked" for s in upcoming)


def finished_at(stage: Milestone) -> datetime | None:
    if stage.ends_at is not None:
        return utc(stage.ends_at)
    if stage.starts_at is not None and stage.precision in {"date", "exact"}:
        return utc(stage.starts_at) + timedelta(days=1)
    return None


def successors(stage: Milestone, event: Event) -> list[Milestone]:
    return [
        candidate
        for candidate in event.milestones
        if candidate.status != "cancelled"
        and any(stage.id in path for path in candidate.advancement_paths or [])
    ]


async def reported_finished_stages(session: AsyncSession) -> set[str]:
    return set(
        await session.scalars(
            select(StageProgress.milestone_id).where(
                StageProgress.outcome.in_(
                    ["passed", "not_passed", "participated", "awaiting_results"]
                )
            )
        )
    )


def missing_schedule(
    stage: Milestone, event: Event, now: datetime, *, reported_finished: bool = False
) -> bool:
    end = finished_at(stage)
    if (
        stage.kind not in TRACKABLE
        or stage.status == "cancelled"
        or stage.terminal is True
        or (stage.status != "confirmed" and not reported_finished)
    ):
        return False
    if not reported_finished and (end is None or end > now):
        return False
    following = successors(stage, event)
    return not following or any(s.starts_at is None or s.status != "confirmed" for s in following)


def result_request_time(
    stage: Milestone, event: Event, timezone: str
) -> tuple[datetime | None, datetime | None]:
    following = successors(stage, event)
    starts = [
        utc(s.starts_at) for s in following if s.starts_at is not None and s.status == "confirmed"
    ]
    cutoff = min(starts) if starts else None
    if stage.results_at is not None:
        return max(utc(stage.results_at), finished_at(stage) or utc(stage.results_at)), cutoff
    if cutoff is None:
        return None, None
    local = cutoff.astimezone(ZoneInfo(timezone)) - timedelta(days=3)
    due = local.replace(hour=20, minute=0, second=0, microsecond=0).astimezone(UTC)
    return max(due, finished_at(stage) or due), cutoff


async def dispatch_workflow_notices(
    session: AsyncSession,
    *,
    user_id: int,
    admin_id: int,
    send: SendWorkflow,
    now: datetime | None = None,
) -> int:
    now = utc(now or datetime.now(UTC))
    profile = await session.get(UserProfile, user_id)
    if profile is None or profile.access_status != "active" or not profile.onboarding_completed:
        return 0
    preferences = {
        p.event_id: p
        for p in await session.scalars(
            select(EventPreference).where(EventPreference.telegram_user_id == user_id)
        )
    }
    outcomes = await user_outcomes(session, user_id)
    reported: set[str] = await reported_finished_stages(session) if user_id == admin_id else set()
    event_rules: dict[str, list[bool]] = {}
    for rule in await session.scalars(
        select(ReminderRule).where(
            ReminderRule.telegram_user_id == user_id,
            ReminderRule.event_id.is_not(None),
        )
    ):
        if rule.event_id is not None:
            event_rules.setdefault(rule.event_id, []).append(rule.enabled)
    muted = {event_id for event_id, enabled in event_rules.items() if not any(enabled)}
    events = list(
        await session.scalars(
            select(Event).where(Event.status != "cancelled").options(selectinload(Event.milestones))
        )
    )
    sent = 0
    notices = {
        n.key: n
        for n in await session.scalars(
            select(WorkflowNotice).where(WorkflowNotice.telegram_user_id == user_id)
        )
    }
    for event in events:
        stages = {s.id: s for s in event.milestones}
        pref = preferences.get(event.id)
        for stage in stages.values():
            for kind in ("result", "gap"):
                key = f"{kind}:{user_id}:{stage.id}"
                notice = notices.get(key)
                due, cutoff = result_request_time(stage, event, profile.timezone)
                if kind == "gap":
                    allowed = user_id == admin_id and missing_schedule(
                        stage,
                        event,
                        now,
                        reported_finished=stage.id in reported,
                    )
                    due = now
                else:
                    following = successors(stage, event)
                    needed = not following or any(
                        stage_access(s, stages, outcomes) == "unknown" for s in following
                    )
                    allowed = (
                        stage.kind in TRACKABLE
                        and stage.status == "confirmed"
                        and stage.terminal is not True
                        and pref is not None
                        and pref.interest in {"watching", "registered"}
                        and event_is_enabled(profile, event, preference=pref)
                        and outcomes.get(stage.id) not in {"passed", "not_passed", "skipped"}
                        and stage_access(stage, stages, outcomes) != "blocked"
                        and (cutoff is None or now < cutoff)
                        and due is not None
                        and needed
                        and event.id not in muted
                    )
                if not allowed:
                    if notice is not None:
                        notice.status = "resolved"
                    continue
                if due is None or due > now:
                    continue
                if notice is None:
                    notice = WorkflowNotice(
                        key=key,
                        telegram_user_id=user_id,
                        milestone_id=stage.id,
                        kind=kind,
                        scheduled_for=due,
                        status="pending",
                        attempts=0,
                    )
                    session.add(notice)
                elif notice.status == "resolved":
                    notice.status = "pending"
                    notice.scheduled_for = due
                    notice.next_attempt_at = None
                    notice.attempts = 0
                if notice.status != "pending" or utc(notice.scheduled_for) > now:
                    continue
                if notice.attempts >= 5 or (
                    notice.next_attempt_at and utc(notice.next_attempt_at) > now
                ):
                    continue
                text = f"📋 <b>{html.escape(event.title)}</b>\n{html.escape(stage.title)}\n" + (
                    "Нужно уточнить продолжение: не внесены связи этапов "
                    "или подтверждённая дата следующего этапа. /gaps"
                    if kind == "gap"
                    else "Прошёл на следующий этап? Пока нет ответа, "
                    "этапы и напоминания остаются в календаре."
                )
                notice.attempts += 1
                try:
                    await send(user_id, text, stage.id, kind)
                except DeliveryDeferred as exc:
                    notice.attempts -= 1
                    notice.next_attempt_at = now + timedelta(seconds=exc.retry_after)
                    await session.commit()
                    raise
                except Exception as exc:
                    logger.warning("Workflow delivery failed (%s)", type(exc).__name__)
                    notice.next_attempt_at = now + timedelta(minutes=min(60, 2**notice.attempts))
                else:
                    notice.status = "sent"
                    notice.sent_at = now
                    sent += 1
                await session.commit()
    await session.commit()
    return sent
