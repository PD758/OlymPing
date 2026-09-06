from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from olymping.models import (
    AccessStatus,
    CatalogNotice,
    DeliveryStatus,
    Event,
    EventInterest,
    EventPreference,
    Milestone,
    NoticeKind,
    NotificationDelivery,
    UserProfile,
)
from olymping.schemas import CalendarDocument, EventSeed, MilestoneSeed
from olymping.services.filters import event_is_enabled


@dataclass(slots=True)
class ImportSummary:
    files: int = 0
    created_events: int = 0
    updated_events: int = 0
    created_milestones: int = 0
    updated_milestones: int = 0
    notices: int = 0

    def merge(self, other: ImportSummary) -> None:
        self.files += other.files
        self.created_events += other.created_events
        self.updated_events += other.updated_events
        self.created_milestones += other.created_milestones
        self.updated_milestones += other.updated_milestones
        self.notices += other.notices

    def __str__(self) -> str:
        return (
            f"files={self.files}, events +{self.created_events}/~{self.updated_events}, "
            f"milestones +{self.created_milestones}/~{self.updated_milestones}, "
            f"notices={self.notices}"
        )


class CalendarImportError(ValueError):
    pass


def load_calendar_document(path: Path) -> CalendarDocument:
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        return CalendarDocument.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise CalendarImportError(f"invalid calendar file {path}: {exc}") from exc


def _event_values(seed: EventSeed, checked_at: datetime) -> dict[str, Any]:
    return {
        "source_kind": seed.source_kind.value,
        "external_id": seed.external_id,
        "title": seed.title,
        "description": seed.description,
        "category": seed.category,
        "tags": seed.tags,
        "url": str(seed.url) if seed.url else None,
        "source_url": str(seed.source_url),
        "source_checked_at": checked_at,
        "status": seed.status.value,
        "format": seed.format,
        "location": seed.location,
        "is_online": seed.is_online,
        "restrictions": seed.restrictions,
        "min_grade": seed.min_grade,
        "max_grade": seed.max_grade,
        "weight": seed.weight,
    }


def _milestone_values(seed: MilestoneSeed, event_id: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "kind": seed.kind.value,
        "title": seed.title,
        "starts_at": seed.starts_at.astimezone(UTC) if seed.starts_at else None,
        "ends_at": seed.ends_at.astimezone(UTC) if seed.ends_at else None,
        "precision": seed.precision.value,
        "status": seed.status.value,
        "format": seed.format,
        "location": seed.location,
        "is_online": seed.is_online,
        "source_url": str(seed.source_url) if seed.source_url else None,
    }


def _changed_fields(instance: object, values: dict[str, Any]) -> dict[str, tuple[Any, Any]]:
    changed: dict[str, tuple[Any, Any]] = {}
    for field, new_value in values.items():
        if field == "source_checked_at":
            continue
        old_value = getattr(instance, field)
        old_comparable = _comparable_value(old_value)
        new_comparable = _comparable_value(new_value)
        if old_comparable != new_comparable:
            changed[field] = (old_value, new_value)
    return changed


def _comparable_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return value


def _format_change(title: str, changed: dict[str, tuple[Any, Any]]) -> str:
    important = {"starts_at", "ends_at", "status", "title"}
    fields = [name for name in changed if name in important]
    details = ", ".join(fields) if fields else "данные источника"
    return f"Обновлено событие «{title}»: {details}."


async def _profiles(session: AsyncSession) -> list[UserProfile]:
    result = await session.execute(
        select(UserProfile).where(
            UserProfile.access_status == AccessStatus.ACTIVE.value,
            UserProfile.onboarding_completed.is_(True),
        )
    )
    return list(result.scalars())


async def _handle_new_event(
    session: AsyncSession,
    event: Event,
    *,
    create_notice: bool,
) -> int:
    notices = 0
    for profile in await _profiles(session):
        if not event_is_enabled(profile, event):
            continue
        if profile.auto_subscribe_new_events:
            session.add(
                EventPreference(
                    telegram_user_id=profile.telegram_user_id,
                    event_id=event.id,
                    interest=EventInterest.WATCHING.value,
                )
            )
        if create_notice and profile.notify_new_events:
            session.add(
                CatalogNotice(
                    telegram_user_id=profile.telegram_user_id,
                    event_id=event.id,
                    kind=NoticeKind.NEW_EVENT.value,
                    summary=f"Добавлена новая олимпиада «{event.title}».",
                )
            )
            notices += 1
    return notices


async def _create_update_notices(
    session: AsyncSession,
    event: Event,
    summary: str,
    *,
    milestone_id: str | None = None,
) -> int:
    notices = 0
    for profile in await _profiles(session):
        if not profile.notify_event_updates or not event_is_enabled(profile, event):
            continue
        session.add(
            CatalogNotice(
                telegram_user_id=profile.telegram_user_id,
                event_id=event.id,
                milestone_id=milestone_id,
                kind=NoticeKind.EVENT_UPDATED.value,
                summary=summary,
            )
        )
        notices += 1
    return notices


async def upsert_event(
    session: AsyncSession,
    seed: EventSeed,
    *,
    checked_at: datetime,
    create_update_notices: bool = True,
    create_new_event_notices: bool = True,
) -> ImportSummary:
    summary = ImportSummary()
    event = await session.get(Event, seed.id)
    values = _event_values(seed, checked_at)
    event_existed = event is not None
    if event is None:
        event = Event(id=seed.id, **values)
        session.add(event)
        summary.created_events += 1
        await session.flush()
        summary.notices += await _handle_new_event(
            session,
            event,
            create_notice=create_new_event_notices,
        )
    else:
        changed = _changed_fields(event, values)
        for field, value in values.items():
            setattr(event, field, value)
        if changed:
            summary.updated_events += 1
            if create_update_notices and {"status", "title"}.intersection(changed):
                summary.notices += await _create_update_notices(
                    session,
                    event,
                    _format_change(event.title, changed),
                )

    existing_result = await session.execute(select(Milestone).where(Milestone.event_id == seed.id))
    existing = {item.id: item for item in existing_result.scalars()}
    for milestone_seed in seed.milestones:
        values_m = _milestone_values(milestone_seed, seed.id)
        milestone = existing.get(milestone_seed.id)
        if milestone is None:
            session.add(Milestone(id=milestone_seed.id, **values_m))
            summary.created_milestones += 1
            continue
        changed = _changed_fields(milestone, values_m)
        for field, value in values_m.items():
            setattr(milestone, field, value)
        if not changed:
            continue
        summary.updated_milestones += 1
        schedule_changed = {"starts_at", "ends_at", "status"}.intersection(changed)
        if schedule_changed:
            await session.execute(
                update(NotificationDelivery)
                .where(
                    NotificationDelivery.milestone_id == milestone.id,
                    NotificationDelivery.status.in_(
                        [DeliveryStatus.PENDING.value, DeliveryStatus.FAILED.value]
                    ),
                )
                .values(status=DeliveryStatus.SUPERSEDED.value)
            )
        if create_update_notices and event_existed and schedule_changed:
            summary.notices += await _create_update_notices(
                session,
                event,
                _format_change(event.title, changed),
                milestone_id=milestone.id,
            )
    return summary


async def import_document(
    session: AsyncSession,
    document: CalendarDocument,
    *,
    checked_at: datetime | None = None,
    create_new_event_notices: bool = True,
) -> ImportSummary:
    checked_at = checked_at or datetime.now(UTC)
    summary = ImportSummary()
    for seed in document.events:
        summary.merge(
            await upsert_event(
                session,
                seed,
                checked_at=checked_at,
                create_new_event_notices=create_new_event_notices,
            )
        )
    return summary


def calendar_paths(data_dir: Path) -> list[Path]:
    if not data_dir.is_dir():
        raise CalendarImportError(f"calendar data directory does not exist: {data_dir}")
    paths = sorted({*data_dir.rglob("*.yaml"), *data_dir.rglob("*.yml")})
    if not paths:
        raise CalendarImportError(f"no YAML calendar files found in {data_dir}")
    return paths


async def import_data_directory(
    session: AsyncSession,
    data_dir: Path,
    *,
    create_new_event_notices: bool = True,
) -> ImportSummary:
    paths = calendar_paths(data_dir)
    total = ImportSummary()
    for path in paths:
        document = load_calendar_document(path)
        result = await import_document(
            session,
            document,
            create_new_event_notices=create_new_event_notices,
        )
        result.files = 1
        total.merge(result)
    return total
