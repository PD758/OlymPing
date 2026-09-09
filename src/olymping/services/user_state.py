from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from olymping.models import (
    Event,
    EventInterest,
    EventPreference,
    Milestone,
    StageOutcome,
    StageProgress,
    WorkflowNotice,
)


class StateTargetNotFoundError(LookupError):
    """Raised when forged or stale callback data points at an unknown object."""


async def toggle_event_interest(
    session: AsyncSession,
    *,
    actor_id: int,
    event_id: str,
    interest: EventInterest,
) -> str | None:
    if await session.get(Event, event_id) is None:
        raise StateTargetNotFoundError(event_id)
    record = await session.get(EventPreference, (actor_id, event_id))
    if record is None:
        session.add(
            EventPreference(
                telegram_user_id=actor_id,
                event_id=event_id,
                interest=interest.value,
            )
        )
        return interest.value
    if record.interest == interest.value:
        record.interest = "unsubscribed"
        record.origin = "manual"
        return None
    record.interest = interest.value
    record.origin = "manual"
    return interest.value


async def set_stage_outcome(
    session: AsyncSession,
    *,
    actor_id: int,
    milestone_id: str,
    outcome: StageOutcome | None,
    now: datetime | None = None,
) -> str | None:
    if await session.get(Milestone, milestone_id) is None:
        raise StateTargetNotFoundError(milestone_id)
    now = now or datetime.now(UTC)
    notice = await session.get(WorkflowNotice, f"result:{actor_id}:{milestone_id}")
    if notice is None and outcome == StageOutcome.AWAITING_RESULTS:
        notice = WorkflowNotice(
            key=f"result:{actor_id}:{milestone_id}",
            telegram_user_id=actor_id,
            milestone_id=milestone_id,
            kind="result",
            status="pending",
            scheduled_for=now,
        )
        session.add(notice)
    if notice is not None:
        if outcome == StageOutcome.AWAITING_RESULTS:
            notice.status = "pending"
            notice.scheduled_for = now + timedelta(days=1)
            notice.next_attempt_at = None
            notice.attempts = 0
        elif outcome in {StageOutcome.PASSED, StageOutcome.NOT_PASSED, StageOutcome.SKIPPED}:
            notice.status = "resolved"
        elif outcome is None:
            notice.status = "pending"
            notice.next_attempt_at = None
            notice.attempts = 0
    record = await session.get(StageProgress, (actor_id, milestone_id))
    if outcome is None:
        if record is not None:
            await session.delete(record)
        return None
    if record is None:
        session.add(
            StageProgress(
                telegram_user_id=actor_id,
                milestone_id=milestone_id,
                outcome=outcome.value,
            )
        )
    else:
        record.outcome = outcome.value
    return outcome.value
