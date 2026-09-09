from __future__ import annotations

import hashlib
import html
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from olymping.models import (
    CatalogNotice,
    Event,
    EventPreference,
    NotificationReview,
    OpenEventNotice,
    ReviewDelivery,
    ReviewSelection,
    UserProfile,
)
from olymping.services.availability import open_phases
from olymping.services.delivery import DeliveryDeferred
from olymping.services.filters import event_is_enabled
from olymping.services.importer import format_calendar_value
from olymping.services.users import require_admin_profile

logger = logging.getLogger(__name__)
SendMessage = Callable[[int, str], Awaitable[None]]
Notice = CatalogNotice | OpenEventNotice


class StaleReviewError(ValueError):
    pass


async def refresh_review(session: AsyncSession, *, batch_id: int, actor_id: int) -> bool:
    await require_admin_profile(session, actor_id)
    claimed = await session.scalar(
        update(NotificationReview)
        .where(
            NotificationReview.id == batch_id,
            NotificationReview.status == "pending",
        )
        .values(status="pending")
        .returning(NotificationReview.id)
    )
    if claimed is None:
        return False
    selections = list(
        await session.scalars(
            select(ReviewSelection).where(
                ReviewSelection.review_batch_id == batch_id,
            )
        )
    )
    for item in selections:
        event = await session.scalar(
            select(Event)
            .options(selectinload(Event.milestones))
            .execution_options(populate_existing=True)
            .where(Event.id == item.event_id)
        )
        if event is None:
            item.selected = False
            continue
        lines = [f"Актуальные сведения. Статус: {format_calendar_value(event.status)}."]
        for stage in event.milestones:
            lines.append(
                f"{stage.title}: {format_calendar_value(stage.starts_at)} "
                f"({format_calendar_value(stage.status)})."
            )
        summary = "\n".join(lines)
        item.summary = summary
        item.snapshot_hash = event_fingerprint(event)
        await session.execute(
            update(CatalogNotice)
            .where(
                CatalogNotice.review_batch_id == batch_id,
                CatalogNotice.event_id == event.id,
                CatalogNotice.kind == "event_updated",
            )
            .values(summary=summary)
        )
    return True


def event_fingerprint(event: Event) -> str:
    def value(item: object) -> object:
        if isinstance(item, datetime):
            return (
                item.replace(tzinfo=UTC) if item.tzinfo is None else item.astimezone(UTC)
            ).isoformat()
        return item

    fields = (
        "title",
        "status",
        "source_kind",
        "tags",
        "min_grade",
        "max_grade",
        "url",
        "source_url",
        "description",
        "format",
        "location",
        "is_online",
    )
    stage_fields = ("id", "title", "kind", "status", "starts_at", "ends_at", "precision")
    payload = {field: value(getattr(event, field)) for field in fields}
    payload["milestones"] = [
        {field: value(getattr(stage, field)) for field in stage_fields}
        for stage in sorted(event.milestones, key=lambda stage: stage.id)
    ]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def human_summary(notice: Notice, event: Event, now: datetime) -> str:
    if isinstance(notice, CatalogNotice):
        if notice.kind == "new_event":
            return "Добавлено в календарь."
        if notice.summary.startswith("Обновлено событие") and " → " not in notice.summary:
            return "Уточнены сведения и расписание. Актуальные данные — в карточке события."
        return notice.summary
    phases = {phase.phase: phase.title for phase in open_phases(event, now)}
    return phases.get(notice.phase, "Ранее обнаружено открытое окно; проверь актуальный график.")


async def collect_review_batch(session: AsyncSession) -> int | None:
    # Serialize collection across startup, manual sync and background sync on SQLite.
    await session.execute(
        update(NotificationReview).where(NotificationReview.id == -1).values(status="pending")
    )
    await _reconcile_duplicate_reviews(session)
    catalogs = list(
        await session.scalars(
            select(CatalogNotice).where(
                CatalogNotice.review_batch_id.is_(None),
                CatalogNotice.sent_at.is_(None),
            )
        )
    )
    opens = list(
        await session.scalars(
            select(OpenEventNotice).where(
                OpenEventNotice.review_batch_id.is_(None),
                OpenEventNotice.status == "pending",
            )
        )
    )
    notices: list[Notice] = [*catalogs, *opens]
    if not notices:
        return None
    batch = NotificationReview()
    session.add(batch)
    await session.flush()
    grouped: dict[str, list[Notice]] = defaultdict(list)
    for notice in notices:
        notice.review_batch_id = batch.id
        grouped[notice.event_id].append(notice)
    for event_id, event_notices in grouped.items():
        event = await session.scalar(
            select(Event)
            .options(selectinload(Event.milestones))
            .execution_options(populate_existing=True)
            .where(Event.id == event_id)
        )
        if event is None:
            continue
        summaries = list(
            dict.fromkeys(human_summary(n, event, datetime.now(UTC)) for n in event_notices)
        )
        session.add(
            ReviewSelection(
                review_batch_id=batch.id,
                event_id=event_id,
                snapshot_hash=event_fingerprint(event),
                summary="\n".join(summaries),
                selected=True,
            )
        )
    await session.flush()
    return batch.id


def _notice_key(notice: Notice, snapshot: str) -> tuple[str, ...]:
    if isinstance(notice, OpenEventNotice):
        return (notice.event_id, snapshot, "open", notice.phase)
    # A title/summary rewrite does not make an existing event new again.
    if notice.kind == "new_event":
        return (notice.event_id, "new_event")
    return (notice.event_id, snapshot, notice.kind, notice.milestone_id or "", notice.summary)


async def _reconcile_duplicate_reviews(session: AsyncSession) -> None:
    """Review facts once across recipients; never auto-approve late duplicates."""
    pending = list(
        await session.scalars(
            select(NotificationReview)
            .where(NotificationReview.status == "pending")
            .order_by(NotificationReview.id)
        )
    )
    pending_ids = {batch.id for batch in pending}
    candidates: list[Notice] = [
        *await session.scalars(
            select(CatalogNotice).where(
                CatalogNotice.sent_at.is_(None),
                CatalogNotice.review_batch_id.is_(None)
                | CatalogNotice.review_batch_id.in_(pending_ids),
            )
        ),
        *await session.scalars(
            select(OpenEventNotice).where(
                OpenEventNotice.status == "pending",
                OpenEventNotice.review_batch_id.is_(None)
                | OpenEventNotice.review_batch_id.in_(pending_ids),
            )
        ),
    ]
    if not candidates:
        return
    event_ids = {notice.event_id for notice in candidates}
    selections = list(
        await session.scalars(
            select(ReviewSelection).where(
                ReviewSelection.event_id.in_(event_ids),
            )
        )
    )
    snapshots = {(s.review_batch_id, s.event_id): s.snapshot_hash for s in selections}
    events = {
        event.id: event
        for event in await session.scalars(
            select(Event)
            .where(Event.id.in_(event_ids))
            .options(selectinload(Event.milestones))
            .execution_options(populate_existing=True)
        )
    }
    history: list[Notice] = [
        *await session.scalars(
            select(CatalogNotice).where(
                CatalogNotice.event_id.in_(event_ids),
                CatalogNotice.review_batch_id.is_not(None),
            )
        ),
        *await session.scalars(
            select(OpenEventNotice).where(
                OpenEventNotice.event_id.in_(event_ids),
                OpenEventNotice.review_batch_id.is_not(None),
            )
        ),
    ]
    # Decided facts take precedence, followed by the oldest pending review.
    known: dict[tuple[str, ...], int] = {}
    for notice in sorted(
        history,
        key=lambda n: (
            n.review_batch_id in pending_ids,
            n.review_batch_id or 0,
        ),
    ):
        batch_id = notice.review_batch_id
        if batch_id is None:
            continue
        snapshot = snapshots.get((batch_id, notice.event_id))
        if snapshot is not None:
            known.setdefault(_notice_key(notice, snapshot), batch_id)
    affected: set[int] = set()
    now = datetime.now(UTC)
    for notice in candidates:
        event = events.get(notice.event_id)
        if event is None:
            continue
        snapshot = (
            snapshots.get((notice.review_batch_id, notice.event_id), event_fingerprint(event))
            if notice.review_batch_id is not None
            else event_fingerprint(event)
        )
        prior = known.get(_notice_key(notice, snapshot))
        if prior is None or prior == notice.review_batch_id:
            continue
        if notice.review_batch_id is not None:
            affected.add(notice.review_batch_id)
        if prior in pending_ids:
            notice.review_batch_id = prior
        elif isinstance(notice, CatalogNotice):
            notice.sent_at = now  # Consumed without a new broadcast.
        else:
            notice.status = "skipped"
    await session.flush()
    for batch in pending:
        if batch.id not in affected:
            continue
        remaining: list[Notice] = [
            *await session.scalars(
                select(CatalogNotice).where(
                    CatalogNotice.review_batch_id == batch.id,
                    CatalogNotice.sent_at.is_(None),
                )
            ),
            *await session.scalars(
                select(OpenEventNotice).where(
                    OpenEventNotice.review_batch_id == batch.id,
                    OpenEventNotice.status == "pending",
                )
            ),
        ]
        for selection in selections:
            if selection.review_batch_id != batch.id:
                continue
            event_notices = [n for n in remaining if n.event_id == selection.event_id]
            if not event_notices:
                await session.delete(selection)
            else:
                selection.summary = "\n".join(
                    dict.fromkeys(human_summary(n, events[n.event_id], now) for n in event_notices)
                )
        if not remaining:
            batch.status = "dismissed"
            batch.decided_at = now
    await session.flush()


async def decide_review(
    session: AsyncSession,
    *,
    batch_id: int,
    actor_id: int,
    approve: bool,
) -> bool:
    await require_admin_profile(session, actor_id)
    await session.execute(
        update(NotificationReview)
        .where(
            NotificationReview.id == batch_id,
            NotificationReview.status == "pending",
        )
        .values(status="pending")
    )
    batch = await session.get(NotificationReview, batch_id)
    if batch is None or batch.status != "pending":
        return False
    selections = list(
        await session.scalars(
            select(ReviewSelection).where(
                ReviewSelection.review_batch_id == batch_id,
            )
        )
    )
    if approve:
        for item in selections:
            if not item.selected:
                continue
            event = await session.scalar(
                select(Event)
                .options(selectinload(Event.milestones))
                .execution_options(populate_existing=True)
                .where(Event.id == item.event_id)
            )
            if event is None or event_fingerprint(event) != item.snapshot_hash:
                raise StaleReviewError(
                    "Данные изменились. Нажми «Обновить сведения», затем проверь пакет ещё раз."
                )
    result = await session.execute(
        update(NotificationReview)
        .where(
            NotificationReview.id == batch_id,
            NotificationReview.status == "pending",
        )
        .values(
            status="approved" if approve else "dismissed",
            decided_by=actor_id,
            decided_at=datetime.now(UTC),
        )
        .returning(NotificationReview.id)
    )
    return result.scalar_one_or_none() is not None


async def toggle_review_event(
    session: AsyncSession,
    *,
    batch_id: int,
    actor_id: int,
    index: int,
) -> bool:
    await require_admin_profile(session, actor_id)
    batch = await session.get(NotificationReview, batch_id)
    if batch is None or batch.status != "pending":
        return False
    selections = list(
        await session.scalars(
            select(ReviewSelection)
            .where(
                ReviewSelection.review_batch_id == batch_id,
            )
            .order_by(ReviewSelection.event_id)
        )
    )
    if not 0 <= index < len(selections):
        return False
    item = selections[index]
    result = await session.execute(
        update(ReviewSelection)
        .where(
            ReviewSelection.review_batch_id == batch_id,
            ReviewSelection.event_id == item.event_id,
            ReviewSelection.review_batch_id.in_(
                select(NotificationReview.id).where(
                    NotificationReview.status == "pending",
                )
            ),
        )
        .values(selected=~ReviewSelection.selected)
        .returning(ReviewSelection.event_id)
    )
    return result.scalar_one_or_none() is not None


def safe_event_block(event: Event, summaries: list[str], *, selected: bool | None = None) -> str:
    prefix = "" if selected is None else ("✅ " if selected else "▫️ ")
    title = html.escape(event.title)
    summary = "\n".join(dict.fromkeys(summaries))
    # Keep HTML and astral Unicode safely within Telegram's message limit.
    clipped = False
    while len(html.escape(summary).encode("utf-16-le")) // 2 > 2000:
        summary = summary[: max(0, len(summary) - 100)]
        clipped = True
    if clipped:
        summary += "\n… Полная карточка — в /all."
    return f"{prefix}<b>{title}</b>\n{html.escape(summary)}"


async def dispatch_reviewed_notices(
    session: AsyncSession,
    *,
    owner_id: int,
    send: SendMessage,
    now: datetime | None = None,
    catalog_only: bool = False,
    open_only: bool = False,
) -> int:
    now = now or datetime.now(UTC)
    profile = await session.get(UserProfile, owner_id)
    if profile is None or profile.access_status != "active" or not profile.onboarding_completed:
        return 0
    batches = list(
        await session.scalars(
            select(NotificationReview)
            .where(
                NotificationReview.status == "approved",
            )
            .order_by(NotificationReview.id)
        )
    )
    sent = 0
    for batch in batches:
        delivery = await session.get(ReviewDelivery, (batch.id, owner_id))
        if delivery is not None:
            retry_at = delivery.next_attempt_at
            if retry_at is not None and retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            if delivery.status == "failed" or (retry_at is not None and retry_at > now):
                continue
        notices: list[Notice] = []
        if not open_only:
            notices.extend(
                await session.scalars(
                    select(CatalogNotice).where(
                        CatalogNotice.review_batch_id == batch.id,
                        CatalogNotice.telegram_user_id == owner_id,
                        CatalogNotice.sent_at.is_(None),
                    )
                )
            )
        if not catalog_only:
            notices.extend(
                await session.scalars(
                    select(OpenEventNotice).where(
                        OpenEventNotice.review_batch_id == batch.id,
                        OpenEventNotice.telegram_user_id == owner_id,
                        OpenEventNotice.status == "pending",
                    )
                )
            )
        grouped: dict[str, list[Notice]] = defaultdict(list)
        for notice in notices:
            grouped[notice.event_id].append(notice)
        blocks: list[tuple[str, list[Notice]]] = []
        for event_id, candidates in grouped.items():
            selection = await session.get(ReviewSelection, (batch.id, event_id))
            event = await session.scalar(
                select(Event)
                .options(selectinload(Event.milestones))
                .execution_options(populate_existing=True)
                .where(Event.id == event_id)
            )
            pref = await session.get(EventPreference, (owner_id, event_id))
            valid = (
                selection is not None
                and selection.selected
                and event is not None
                and event_fingerprint(event) == selection.snapshot_hash
                and event_is_enabled(profile, event)
                and (pref is None or pref.interest != "ignored")
            )
            chosen: list[Notice] = []
            for notice in candidates:
                allowed = valid
                if isinstance(notice, CatalogNotice):
                    enabled = (
                        profile.notify_new_events
                        if notice.kind == "new_event"
                        else profile.notify_open_events
                        if notice.kind == "registration_open_digest"
                        else profile.notify_event_updates
                    )
                    allowed = allowed and enabled
                    if notice.kind == "registration_open_digest":
                        allowed = (
                            allowed
                            and event is not None
                            and any(
                                p.phase.startswith("registration:") for p in open_phases(event, now)
                            )
                            and (pref is None or pref.interest != "registered")
                        )
                else:
                    phases: set[str] = (
                        {p.phase for p in open_phases(event, now)} if event else set()
                    )
                    allowed = (
                        allowed
                        and profile.notify_open_events
                        and notice.phase in phases
                        and not (
                            notice.phase.startswith("registration:")
                            and pref is not None
                            and pref.interest == "registered"
                        )
                    )
                if not allowed:
                    if isinstance(notice, CatalogNotice):
                        notice.sent_at = now
                    else:
                        notice.status = "skipped"
                else:
                    chosen.append(notice)
            if chosen and event is not None:
                blocks.append(
                    (
                        safe_event_block(event, [human_summary(n, event, now) for n in chosen]),
                        chosen,
                    )
                )
        await session.commit()
        packet = "📅 <b>Новости твоего календаря</b>"
        packet_notices: list[Notice] = []
        packets: list[tuple[str, list[Notice]]] = []
        for block, block_notices in blocks:
            if packet_notices and len((packet + "\n\n" + block).encode("utf-16-le")) // 2 > 3900:
                packets.append((packet, packet_notices))
                packet = "📅 <b>Новости твоего календаря — продолжение</b>"
                packet_notices = []
            packet += "\n\n" + block
            packet_notices.extend(block_notices)
        if packet_notices:
            packets.append((packet, packet_notices))
        for text, delivered in packets:
            if delivery is None:
                delivery = ReviewDelivery(
                    review_batch_id=batch.id,
                    telegram_user_id=owner_id,
                    attempts=0,
                    status="pending",
                )
                session.add(delivery)
            delivery.attempts += 1
            try:
                await send(owner_id, text)
            except DeliveryDeferred as exc:
                delivery.attempts -= 1
                delivery.next_attempt_at = datetime.now(UTC) + timedelta(seconds=exc.retry_after)
                await session.commit()
                raise
            except Exception as exc:
                logger.warning("Review batch %s delivery failed (%s)", batch.id, type(exc).__name__)
                delivery.next_attempt_at = now + timedelta(minutes=min(60, 2**delivery.attempts))
                if delivery.attempts >= 5:
                    delivery.status = "failed"
                await session.commit()
                return sent
            for notice in delivered:
                notice.sent_at = now
                if isinstance(notice, OpenEventNotice):
                    notice.status = "sent"
            delivery.attempts = 0
            delivery.next_attempt_at = None
            await session.commit()
            sent += len(delivered)
    return sent
