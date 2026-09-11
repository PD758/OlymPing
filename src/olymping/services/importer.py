from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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
from olymping.services.subscriptions import reapply_event


@dataclass(slots=True)
class ImportSummary:
    files: int = 0
    created_events: int = 0
    updated_events: int = 0
    created_milestones: int = 0
    updated_milestones: int = 0
    notices: int = 0
    changed_event_ids: set[str] = dataclass_field(default_factory=set[str])

    def merge(self, other: ImportSummary) -> None:
        self.files += other.files
        self.created_events += other.created_events
        self.updated_events += other.updated_events
        self.created_milestones += other.created_milestones
        self.updated_milestones += other.updated_milestones
        self.notices += other.notices
        self.changed_event_ids.update(other.changed_event_ids)

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
        "results_at": seed.results_at.astimezone(UTC) if seed.results_at else None,
        "advancement_paths": seed.advancement_paths,
        "terminal": seed.terminal,
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


def format_calendar_value(value: Any) -> str:
    if value is None:
        return "дата уточняется"
    if isinstance(value, datetime):
        aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
        local = aware.astimezone(ZoneInfo("Europe/Moscow"))
        return local.strftime(
            "%d.%m.%Y" if local.hour == local.minute == 0 else "%d.%m.%Y %H:%M МСК"
        )
    return {
        "confirmed": "подтверждено",
        "tentative": "предварительно",
        "tbd": "уточняется",
        "cancelled": "отменено",
    }.get(str(value), str(value))


def _format_change(title: str, changed: dict[str, tuple[Any, Any]], *, window: bool = False) -> str:
    labels = {
        "starts_at": "Начало",
        "ends_at": "Окончание",
        "status": "Статус",
        "title": "Название",
    }
    lines = [f"{title}:"]
    for field, (old, new) in changed.items():
        if field not in labels:
            continue
        display_old, display_new = old, new
        if window and field == "ends_at":

            def inclusive_day(value: Any) -> Any:
                if isinstance(value, datetime):
                    local = _comparable_value(value).astimezone(ZoneInfo("Europe/Moscow"))
                    if local.hour == local.minute == local.second == 0:
                        return value - timedelta(days=1)
                return value

            display_old, display_new = inclusive_day(old), inclusive_day(new)
        line = (
            f"{labels[field]}: {format_calendar_value(display_old)} → "
            f"{format_calendar_value(display_new)}"
        )
        if isinstance(old, datetime) and isinstance(new, datetime):
            seconds = (_comparable_value(new) - _comparable_value(old)).total_seconds()
            if seconds and seconds % 86400 == 0:
                line += (
                    f" (на {int(abs(seconds) / 86400)} дн. {'позже' if seconds > 0 else 'раньше'})"
                )
        lines.append(line)
    return "\n".join(lines)


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
                    origin="automatic",
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
        preference = await session.get(EventPreference, (profile.telegram_user_id, event.id))
        if not profile.notify_event_updates or not event_is_enabled(
            profile, event, preference=preference
        ):
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
    old_tags = list(event.tags) if event is not None else list(seed.tags)
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
            if create_update_notices and event_existed:
                await session.flush()
                summary.notices += await _create_update_notices(
                    session,
                    event,
                    f"Добавлен этап «{milestone_seed.title}». "
                    f"Начало: {format_calendar_value(milestone_seed.starts_at)}; "
                    f"статус: {format_calendar_value(milestone_seed.status.value)}.",
                    milestone_id=milestone_seed.id,
                )
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
                _format_change(milestone.title, changed, window=milestone.precision == "window"),
                milestone_id=milestone.id,
            )
    if event_existed:
        summary.notices += await reapply_event(session, event, old_tags=old_tags)
    if any(
        (
            summary.created_events,
            summary.updated_events,
            summary.created_milestones,
            summary.updated_milestones,
        )
    ):
        summary.changed_event_ids.add(seed.id)
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
        validate_progression(seed)
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


def validate_progression(seed: EventSeed) -> None:
    stages = {s.id: s for s in seed.milestones}
    visited: set[str] = set()

    def visit(stage_id: str, path: set[str]) -> None:
        if stage_id in path:
            raise CalendarImportError(f"cyclic advancement path in {seed.id}: {stage_id}")
        if stage_id in visited:
            return
        for alternative in stages[stage_id].advancement_paths or []:
            for parent in alternative:
                if parent not in stages:
                    raise CalendarImportError(f"unknown prerequisite in {seed.id}: {parent}")
                if stages[parent].terminal:
                    raise CalendarImportError(
                        f"terminal milestone cannot have successors: {parent}"
                    )
                visit(parent, path | {stage_id})
        visited.add(stage_id)

    for stage_id in stages:
        visit(stage_id, set())


async def import_data_directory(
    session: AsyncSession,
    data_dir: Path,
    *,
    create_new_event_notices: bool = True,
) -> ImportSummary:
    paths = calendar_paths(data_dir)
    # Resolve patches first: notify about the final result, never intermediate flips.
    seeds: dict[str, EventSeed] = {}
    for path in paths:
        document = load_calendar_document(path)
        for seed in document.events:
            if seed.id in seeds:
                milestones = {stage.id: stage for stage in seeds[seed.id].milestones}
                milestones.update({stage.id: stage for stage in seed.milestones})
                seed = seed.model_copy(update={"milestones": list(milestones.values())})
            seeds[seed.id] = seed
    total = await import_document(
        session,
        CalendarDocument(calendar_version=1, events=list(seeds.values())),
        create_new_event_notices=create_new_event_notices,
    )
    total.files = len(paths)
    return total
