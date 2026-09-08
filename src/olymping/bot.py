from __future__ import annotations

import asyncio
import contextlib
import html
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    BotCommandScopeChat,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from olymping.config import Settings
from olymping.db import create_engine, create_session_factory, upgrade_schema
from olymping.models import (
    AccessStatus,
    Event,
    EventInterest,
    EventPreference,
    Milestone,
    MilestoneKind,
    ReminderMode,
    ReminderRule,
    SourceKind,
    StageOutcome,
    StageProgress,
    UserProfile,
    UserRole,
)
from olymping.presentation import telegram_time
from olymping.review_ui import notify_pending_review, register_review_handlers
from olymping.services.availability import queue_open_event_notices
from olymping.services.calendar import (
    all_olympiads,
    get_event,
    open_registration_events,
    registration_closes_at,
    upcoming_events,
)
from olymping.services.ctftime import sync_ctftime
from olymping.services.importer import CalendarImportError, import_data_directory
from olymping.services.onboarding import complete_onboarding
from olymping.services.reminders import (
    REMINDER_CUSTOM,
    REMINDER_MUTED,
    REMINDER_NORMAL,
    aware_utc,
    event_reminder_state,
    run_notification_cycle,
    set_event_reminders_muted,
)
from olymping.services.runtime_health import clear_heartbeats, record_heartbeat, supervise_runtime
from olymping.services.synchronization import synchronize_calendar
from olymping.services.user_state import (
    StateTargetNotFoundError,
    set_stage_outcome,
    toggle_event_interest,
)
from olymping.services.users import (
    AccessDeniedError,
    active_user_ids,
    create_invitation,
    ensure_admin_profile,
    ensure_user_profile,
    redeem_invitation,
    set_user_access,
)

logger = logging.getLogger(__name__)


class PollingHeartbeatMiddleware(BaseRequestMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self, make_request: NextRequestMiddlewareType[Any], bot: Bot, method: Any
    ) -> Any:
        response = await make_request(bot, method)
        if method.__class__.__name__ == "GetUpdates":
            record_heartbeat(self.settings, "telegram-api")
            record_heartbeat(self.settings, "polling")
        return response


CATALOG_PAGE_SIZE = 8
TAG_PAGE_SIZE = 8
FILTERABLE_TAGS: tuple[tuple[str, str], ...] = (
    ("group:vosh", "Вся группа ВсОШ"),
    ("group:mosh", "Вся группа МОШ"),
    ("cybersecurity", "Информационная безопасность"),
    ("informatics", "Информатика"),
    ("programming", "Программирование"),
    ("algorithms", "Алгоритмы"),
    ("ai", "Искусственный интеллект"),
    ("mathematics", "Математика"),
    ("engineering", "Инженерия"),
    ("robotics", "Робототехника"),
    ("technology", "Технология"),
    ("physics", "Физика"),
    ("ecology", "Экология"),
    ("law", "Право"),
    ("obzr", "ОБЗР"),
    ("social-science", "Обществознание"),
    ("economics", "Экономика"),
    ("financial-literacy", "Финграмотность"),
    ("biology", "Биология"),
    ("chemistry", "Химия"),
    ("geography", "География"),
    ("astronomy", "Астрономия"),
    ("history", "История"),
    ("literature", "Литература"),
    ("linguistics", "Лингвистика"),
    ("english", "Английский язык"),
    ("art", "Искусство"),
    ("research", "Исследования"),
    ("preprofessional", "Предпрофиль"),
    ("team", "Командные"),
)
TAG_LABELS: dict[str, str] = dict(FILTERABLE_TAGS)


@dataclass(frozen=True, slots=True)
class CatalogContext:
    mode: str
    index: int
    total: int

    @property
    def page(self) -> int:
        return self.index // CATALOG_PAGE_SIZE


class AccessMiddleware(BaseMiddleware):
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return None
        async with self.factory() as session:
            profile = await session.get(UserProfile, user.id)
        invite_start = isinstance(event, Message) and (event.text or "").startswith(
            "/start invite_"
        )
        if profile is None or profile.access_status != AccessStatus.ACTIVE.value:
            if invite_start:
                return await handler(event, data)
            if isinstance(event, CallbackQuery):
                await event.answer("Нужно приглашение администратора.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Бот доступен по приглашению администратора.")
            return None
        if not profile.onboarding_completed:
            onboarding_action = (
                isinstance(event, Message)
                and (event.text or "").startswith(("/start", "/onboarding"))
            ) or (isinstance(event, CallbackQuery) and (event.data or "").startswith("onboard:"))
            if not onboarding_action:
                if isinstance(event, CallbackQuery):
                    await event.answer("Сначала заверши настройку профиля.", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer("Сначала заверши настройку через /start.")
                return None
        return await handler(event, data)


def actor_id(event: Message | CallbackQuery) -> int:
    user = event.from_user
    if user is None:
        raise RuntimeError("Telegram user is missing")
    return user.id


def home_keyboard(*, is_admin: bool = False) -> InlineKeyboardMarkup:
    final_row = [InlineKeyboardButton(text="Настройки", callback_data="settings", style="primary")]
    if is_admin:
        final_row.append(InlineKeyboardButton(text="Синхронизировать", callback_data="sync"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="list:today"),
                InlineKeyboardButton(text="7 дней", callback_data="list:week", style="primary"),
                InlineKeyboardButton(text="30 дней", callback_data="list:month"),
            ],
            [
                InlineKeyboardButton(
                    text="Мои олимпиады", callback_data="list:mine", style="success"
                ),
                InlineKeyboardButton(text="Весь каталог", callback_data="list:all"),
            ],
            [
                InlineKeyboardButton(
                    text="🟢 Сейчас можно зарегистрироваться",
                    callback_data="list:registration",
                    style="success",
                )
            ],
            final_row,
        ]
    )


TRACKABLE_MILESTONE_KINDS = {
    MilestoneKind.QUALIFIER.value,
    MilestoneKind.TEAM_STAGE.value,
    MilestoneKind.FINAL.value,
    MilestoneKind.COMPETITION.value,
}
OUTCOME_LABELS = {
    StageOutcome.PARTICIPATED.value: "📝 Участвовал",
    StageOutcome.PASSED.value: "✅ Прошёл",
    StageOutcome.NOT_PASSED.value: "❌ Не прошёл",
    StageOutcome.SKIPPED.value: "⏭ Пропускаю",
}
OUTCOME_ICONS = {
    StageOutcome.PARTICIPATED.value: "📝",
    StageOutcome.PASSED.value: "✅",
    StageOutcome.NOT_PASSED.value: "❌",
    StageOutcome.SKIPPED.value: "⏭",
}


def _context_callback(prefix: str, context: CatalogContext | None, event_id: str) -> str:
    if context is None:
        return f"{prefix}:{event_id}"
    value = f"{prefix}:{context.mode}:{context.index}:{event_id}"
    return value if len(value.encode()) <= 64 else f"{prefix}:{event_id}"


def event_keyboard(
    event: Event,
    interest: str | None,
    context: CatalogContext | None = None,
    reminder_status: str = REMINDER_NORMAL,
) -> InlineKeyboardMarkup:
    watching_label = "🔔 Подписан" if interest == EventInterest.WATCHING.value else "Подписаться"
    registered_label = (
        "✅ Зарегистрирован" if interest == EventInterest.REGISTERED.value else "Регистрация ✅"
    )
    ignored_label = "🚫 Не интересно" if interest == EventInterest.IGNORED.value else "Не интересно"
    reminder_labels = {
        REMINDER_NORMAL: "🔔 Напоминания: обычные",
        REMINDER_CUSTOM: "⚙️ Напоминания: свои",
        REMINDER_MUTED: "🔕 Напоминания: выключены",
    }
    reminder_action = "d" if reminder_status == REMINDER_MUTED else "m"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=watching_label,
                    callback_data=_context_callback("pref:w", context, event.id),
                    style="success" if interest == EventInterest.WATCHING.value else "primary",
                ),
                InlineKeyboardButton(
                    text=registered_label,
                    callback_data=_context_callback("pref:r", context, event.id),
                    style="success" if interest == EventInterest.REGISTERED.value else None,
                ),
            ],
            [
                InlineKeyboardButton(
                    text=ignored_label,
                    callback_data=_context_callback("pref:i", context, event.id),
                    style="danger" if interest == EventInterest.IGNORED.value else None,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Этапы и результаты",
                    callback_data=_context_callback("progress", context, event.id),
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text=reminder_labels.get(reminder_status, reminder_labels[REMINDER_NORMAL]),
                    callback_data=_context_callback(f"r:{reminder_action}", context, event.id),
                    style="danger" if reminder_status == REMINDER_MUTED else "success",
                )
            ],
        ]
    )
    if context is None:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="Главное меню", callback_data="home")]
        )
        return keyboard
    previous = f"ce:{context.mode}:{context.index - 1}" if context.index > 0 else "noop"
    following = (
        f"ce:{context.mode}:{context.index + 1}" if context.index + 1 < context.total else "noop"
    )
    keyboard.inline_keyboard.extend(
        [
            [
                InlineKeyboardButton(text="←", callback_data=previous),
                InlineKeyboardButton(
                    text=f"{context.index + 1}/{context.total}", callback_data="noop"
                ),
                InlineKeyboardButton(text="→", callback_data=following),
            ],
            [
                InlineKeyboardButton(
                    text="К списку", callback_data=f"cat:{context.mode}:{context.page}"
                )
            ],
        ]
    )
    return keyboard


def format_event(
    event: Event,
    timezone: str,
    progress: dict[str, str] | None = None,
) -> str:
    status_icons = {"confirmed": "✅", "tentative": "⚠️", "tbd": "❔", "cancelled": "🚫"}
    lines = [f"<b>{html.escape(event.title)}</b>", f"Источник: {html.escape(event.source_kind)}"]
    if event.format:
        lines.append(f"Формат: {html.escape(event.format)}")
    if event.location:
        lines.append(f"Место: {html.escape(event.location)}")
    if event.min_grade is not None or event.max_grade is not None:
        grade_from = event.min_grade or 1
        grade_to = event.max_grade or 11
        grade_text = str(grade_from) if grade_from == grade_to else f"{grade_from}–{grade_to}"
        lines.append(f"Классы: {grade_text}")
    elif event.restrictions:
        lines.append(f"Классы/ограничения: {html.escape(event.restrictions)}")
    else:
        lines.append("Классы: уточняются")
    if event.tags:
        labels = [TAG_LABELS[tag] for tag in event.tags if tag in TAG_LABELS]
        if labels:
            lines.append("Темы: " + html.escape(", ".join(labels)))
    milestones = sorted(
        event.milestones,
        key=lambda item: (
            item.starts_at is None,
            aware_utc(item.starts_at).timestamp() if item.starts_at else float("inf"),
        ),
    )
    for milestone in milestones:
        icon = status_icons.get(milestone.status, "•")
        if milestone.starts_at:
            value = telegram_time(
                milestone.starts_at,
                timezone,
                date_only=milestone.precision == "date",
            )
            if milestone.ends_at:
                value += " — " + telegram_time(
                    milestone.ends_at,
                    timezone,
                    date_only=milestone.precision == "date",
                )
        else:
            value = "дата уточняется"
        details: list[str] = []
        if milestone.is_online is True:
            details.append("онлайн")
        elif milestone.is_online is False:
            details.append("очно")
        if milestone.format:
            details.append(milestone.format)
        if milestone.location:
            details.append(milestone.location)
        suffix = f" ({html.escape(', '.join(details))})" if details else ""
        outcome = (progress or {}).get(milestone.id)
        outcome_suffix = f" — {OUTCOME_LABELS[outcome]}" if outcome else ""
        lines.append(f"{icon} {html.escape(milestone.title)}: {value}{suffix}{outcome_suffix}")
    if event.description:
        lines.append(f"<blockquote expandable>{html.escape(event.description)}</blockquote>")
    link = html.escape(event.url or event.source_url, quote=True)
    lines.append(f'<a href="{link}">Официальный источник</a>')
    return "\n".join(lines)


def _toggle_button(text: str, enabled: bool, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"{'✅' if enabled else '❌'} {text}",
        callback_data=callback_data,
        style="success" if enabled else "danger",
    )


def settings_keyboard(profile: UserProfile) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _toggle_button(
                    "Сообщать о новых",
                    profile.notify_new_events,
                    "setting:notify_new_events",
                )
            ],
            [
                _toggle_button(
                    "Автоподписка на новые",
                    profile.auto_subscribe_new_events,
                    "setting:auto_subscribe_new_events",
                )
            ],
            [
                _toggle_button(
                    "Сообщать об изменениях",
                    profile.notify_event_updates,
                    "setting:notify_event_updates",
                )
            ],
            [
                _toggle_button(
                    "Открытая регистрация и участие",
                    profile.notify_open_events,
                    "setting:notify_open_events",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Источники олимпиад",
                    callback_data="settings:sources",
                    style="primary",
                ),
                InlineKeyboardButton(text="Фильтры CTF", callback_data="settings:ctf"),
            ],
            [
                InlineKeyboardButton(
                    text="Класс и темы",
                    callback_data="settings:catalog",
                    style="primary",
                )
            ],
            [InlineKeyboardButton(text="Анкета и подбор олимпиад", callback_data="onboard:back")],
            [InlineKeyboardButton(text="Главное меню", callback_data="home")],
        ]
    )


def _source_settings_keyboard(category_settings: dict[str, Any]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for kind in SourceKind:
        enabled = bool(category_settings.get(kind.value, True))
        rows.append([_toggle_button(kind.value, enabled, f"source:{kind.value}")])
    rows.append([InlineKeyboardButton(text="Назад к настройкам", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _ctf_settings_keyboard(ctf_filters: dict[str, Any]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Площадка: {ctf_filters.get('online', 'all')}",
                    callback_data="ctf:online",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Ограничения: {ctf_filters.get('restrictions', 'all')}",
                    callback_data="ctf:restrictions",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Вес от: {ctf_filters.get('min_weight', 0)}",
                    callback_data="ctf:weight",
                )
            ],
            [InlineKeyboardButton(text="Назад к настройкам", callback_data="settings")],
        ]
    )


def _catalog_filter_keyboard(profile: UserProfile) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for start in range(1, 12, 4):
        row: list[InlineKeyboardButton] = []
        for grade in range(start, min(start + 4, 12)):
            selected = profile.school_grade == grade
            row.append(
                InlineKeyboardButton(
                    text=f"{'✅ ' if selected else ''}{grade} класс",
                    callback_data=f"grade:{grade}",
                    style="success" if selected else None,
                )
            )
        rows.append(row)
    selected_count = len(profile.tag_filters or [])
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text=f"Темы: {selected_count} выбрано",
                    callback_data="settings:tags:0",
                    style="primary",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Открыть каталог",
                    callback_data="list:all",
                    style="success",
                )
            ],
            [InlineKeyboardButton(text="Назад к настройкам", callback_data="settings")],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _tag_filter_keyboard(profile: UserProfile, page: int) -> InlineKeyboardMarkup:
    selected = set(profile.tag_filters or [])
    pages = max(1, (len(FILTERABLE_TAGS) + TAG_PAGE_SIZE - 1) // TAG_PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    start = page * TAG_PAGE_SIZE
    rows: list[list[InlineKeyboardButton]] = []
    for tag, label in FILTERABLE_TAGS[start : start + TAG_PAGE_SIZE]:
        enabled = tag in selected
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{'✅' if enabled else '▫️'} {label}",
                    callback_data=f"tag:{page}:{tag}",
                    style="success" if enabled else None,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="←", callback_data=f"settings:tags:{page - 1}" if page > 0 else "noop"
            ),
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"),
            InlineKeyboardButton(
                text="→",
                callback_data=f"settings:tags:{page + 1}" if page + 1 < pages else "noop",
            ),
        ]
    )
    if selected:
        rows.append(
            [InlineKeyboardButton(text="Сбросить темы", callback_data="tag:clear", style="danger")]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="Применить и открыть каталог",
                callback_data="list:all",
                style="success",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="Назад", callback_data="settings:catalog")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _onboarding_grade_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for start in range(1, 12, 4):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{grade} класс",
                    callback_data=f"onboard:grade:{grade}",
                )
                for grade in range(start, min(start + 4, 12))
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _onboarding_tag_keyboard(profile: UserProfile, page: int) -> InlineKeyboardMarkup:
    selected = set(profile.tag_filters or [])
    pages = max(1, (len(FILTERABLE_TAGS) + TAG_PAGE_SIZE - 1) // TAG_PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    start = page * TAG_PAGE_SIZE
    rows: list[list[InlineKeyboardButton]] = []
    for tag, label in FILTERABLE_TAGS[start : start + TAG_PAGE_SIZE]:
        enabled = tag in selected
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{'✅' if enabled else '▫️'} {label}",
                    callback_data=f"onboard:tag:{page}:{tag}",
                    style="success" if enabled else None,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="←",
                callback_data=f"onboard:tags:{page - 1}" if page > 0 else "onboard:noop",
            ),
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="onboard:noop"),
            InlineKeyboardButton(
                text="→",
                callback_data=(f"onboard:tags:{page + 1}" if page + 1 < pages else "onboard:noop"),
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="Подобрать мои олимпиады",
                callback_data="onboard:done",
                style="success",
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="Все предметы", callback_data="onboard:all")])
    rows.append([InlineKeyboardButton(text="Назад к выбору класса", callback_data="onboard:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _answer_or_edit(event: Message | CallbackQuery, text: str, **kwargs: Any) -> None:
    if isinstance(event, CallbackQuery):
        if isinstance(event.message, Message):
            await event.message.edit_text(text, **kwargs)
        await event.answer()
    else:
        await event.answer(text, **kwargs)


def create_router(factory: async_sessionmaker[AsyncSession], settings: Settings) -> Router:
    router = Router(name="olymping")
    router.message.middleware(AccessMiddleware(factory))
    router.callback_query.middleware(AccessMiddleware(factory))

    async def show_home(event: Message | CallbackQuery) -> None:
        user_id = actor_id(event)
        async with factory() as session:
            profile = await session.get(UserProfile, user_id)
        is_admin = profile is not None and profile.role == UserRole.ADMIN.value
        await _answer_or_edit(
            event,
            "<b>OlymPing</b>\nПерсональный календарь олимпиад и CTF.",
            reply_markup=home_keyboard(is_admin=is_admin),
        )

    async def catalog_items(
        session: AsyncSession,
        profile: UserProfile,
        mode: str,
    ) -> list[Event]:
        if mode == "r":
            return await open_registration_events(
                session,
                profile,
                now=datetime.now(UTC),
            )
        items = await all_olympiads(session, profile)
        if mode != "m":
            return items
        preference_result = await session.execute(
            select(EventPreference).where(
                EventPreference.telegram_user_id == profile.telegram_user_id,
                EventPreference.interest.in_(
                    [EventInterest.WATCHING.value, EventInterest.REGISTERED.value]
                ),
            )
        )
        subscribed = {item.event_id for item in preference_result.scalars()}
        return [item for item in items if item.id in subscribed]

    async def show_period(event: Message | CallbackQuery, period: str) -> None:
        user_id = actor_id(event)
        tz = settings.tz
        now_local = datetime.now(tz)
        start = datetime.combine(now_local.date(), time.min, tzinfo=tz)
        days = {"today": 1, "week": 7, "month": 30}[period]
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            items = await upcoming_events(
                session, profile, starts_at=start, ends_at=start + timedelta(days=days), limit=20
            )
            await session.commit()
        if not items:
            await _answer_or_edit(
                event,
                f"На ближайшие {days} дн. подтверждённых событий нет.",
                reply_markup=home_keyboard(is_admin=profile.role == UserRole.ADMIN.value),
            )
            return
        lines = [f"<b>События на {days} дн.</b>"]
        buttons: list[list[InlineKeyboardButton]] = []
        for item_event, milestone in items:
            assert milestone.starts_at is not None
            when = telegram_time(milestone.starts_at, settings.timezone)
            lines.append(f"• {when} — {html.escape(item_event.title)}")
            label = (
                item_event.title if len(item_event.title) <= 44 else f"{item_event.title[:41]}..."
            )
            buttons.append([InlineKeyboardButton(text=label, callback_data=f"evt:{item_event.id}")])
        buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="home")])
        await _answer_or_edit(
            event, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    async def show_event(
        callback: CallbackQuery,
        event_id: str,
        context: CatalogContext | None = None,
    ) -> None:
        user_id = actor_id(callback)
        async with factory() as session:
            item = await get_event(session, event_id)
            if item is None:
                await callback.answer("Событие больше не найдено", show_alert=True)
                return
            preference = await session.get(
                EventPreference,
                (user_id, item.id),
            )
            progress_result = await session.execute(
                select(StageProgress).where(
                    StageProgress.telegram_user_id == user_id,
                    StageProgress.milestone_id.in_([stage.id for stage in item.milestones]),
                )
            )
            progress = {record.milestone_id: record.outcome for record in progress_result.scalars()}
            reminder_status = await event_reminder_state(
                session,
                user_id,
                item.id,
            )
        await _answer_or_edit(
            callback,
            format_event(item, settings.timezone, progress),
            reply_markup=event_keyboard(
                item,
                preference.interest if preference else None,
                context,
                reminder_status,
            ),
        )

    async def show_progress(
        callback: CallbackQuery,
        event_id: str,
        context: CatalogContext | None = None,
    ) -> None:
        user_id = actor_id(callback)
        async with factory() as session:
            item = await get_event(session, event_id)
            if item is None:
                await callback.answer("Событие больше не найдено", show_alert=True)
                return
            progress_result = await session.execute(
                select(StageProgress).where(
                    StageProgress.telegram_user_id == user_id,
                    StageProgress.milestone_id.in_([stage.id for stage in item.milestones]),
                )
            )
            progress = {record.milestone_id: record.outcome for record in progress_result.scalars()}
        stages = [stage for stage in item.milestones if stage.kind in TRACKABLE_MILESTONE_KINDS]
        stages.sort(
            key=lambda stage: (
                stage.starts_at is None,
                aware_utc(stage.starts_at).timestamp()
                if stage.starts_at is not None
                else float("inf"),
            )
        )
        rows: list[list[InlineKeyboardButton]] = []
        for stage in stages:
            outcome = progress.get(stage.id)
            icon = OUTCOME_ICONS.get(outcome, "▫️") if outcome is not None else "▫️"
            label = stage.title if len(stage.title) <= 40 else f"{stage.title[:37]}..."
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"{icon} {label}",
                        callback_data=_context_callback("stage", context, stage.id),
                        style=(
                            "success"
                            if outcome == StageOutcome.PASSED.value
                            else "danger"
                            if outcome == StageOutcome.NOT_PASSED.value
                            else None
                        ),
                    )
                ]
            )
        back_callback = (
            f"ce:{context.mode}:{context.index}" if context is not None else f"evt:{item.id}"
        )
        rows.append([InlineKeyboardButton(text="Назад к олимпиаде", callback_data=back_callback)])
        await _answer_or_edit(
            callback,
            f"<b>{html.escape(item.title)}</b>\nВыбери этап, чтобы отметить результат.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    async def show_stage(
        callback: CallbackQuery,
        milestone_id: str,
        context: CatalogContext | None = None,
    ) -> None:
        user_id = actor_id(callback)
        async with factory() as session:
            result = await session.execute(
                select(Milestone)
                .options(selectinload(Milestone.event))
                .where(Milestone.id == milestone_id)
            )
            stage = result.scalar_one_or_none()
            if stage is None:
                await callback.answer("Этап больше не найден", show_alert=True)
                return
            progress = await session.get(
                StageProgress,
                (user_id, stage.id),
            )
        current = OUTCOME_LABELS.get(progress.outcome, "не отмечен") if progress else "не отмечен"
        mode = "онлайн" if stage.is_online is True else "очно" if stage.is_online is False else None
        details = [value for value in [mode, stage.format, stage.location] if value]
        details_text = f"\nФормат: {html.escape(', '.join(details))}" if details else ""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Прошёл",
                        callback_data=_context_callback("out:p", context, stage.id),
                        style="success",
                    ),
                    InlineKeyboardButton(
                        text="❌ Не прошёл",
                        callback_data=_context_callback("out:n", context, stage.id),
                        style="danger",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📝 Участвовал",
                        callback_data=_context_callback("out:a", context, stage.id),
                        style="primary",
                    ),
                    InlineKeyboardButton(
                        text="⏭ Пропускаю",
                        callback_data=_context_callback("out:s", context, stage.id),
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="Сбросить отметку",
                        callback_data=_context_callback("out:x", context, stage.id),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Назад к этапам",
                        callback_data=_context_callback("progress", context, stage.event_id),
                    )
                ],
            ]
        )
        await _answer_or_edit(
            callback,
            f"<b>{html.escape(stage.event.title)}</b>\n"
            f"{html.escape(stage.title)}{details_text}\n"
            f"Текущий результат: <b>{current}</b>",
            reply_markup=keyboard,
        )

    async def show_catalog(
        event: Message | CallbackQuery,
        *,
        mode: str = "a",
        page: int = 0,
    ) -> None:
        user_id = actor_id(event)
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            items = await catalog_items(session, profile, mode)
            grade = profile.school_grade
            selected_tags = list(profile.tag_filters or [])
            await session.commit()
        status_icons = {"confirmed": "✅", "tentative": "⚠️", "tbd": "❔", "cancelled": "🚫"}
        pages = max(1, (len(items) + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE)
        page = min(max(page, 0), pages - 1)
        offset = page * CATALOG_PAGE_SIZE
        visible_items = items[offset : offset + CATALOG_PAGE_SIZE]
        titles = {
            "a": "Весь каталог",
            "m": "Мои олимпиады",
            "r": "Сейчас можно зарегистрироваться",
        }
        title = titles.get(mode, "Весь каталог")
        filter_parts = [f"{grade} класс и выше" if grade is not None else "любой класс"]
        if selected_tags:
            filter_parts.append(f"тем: {len(selected_tags)}")
        lines = [f"<b>{title}</b>", f"Фильтр: {', '.join(filter_parts)} · найдено {len(items)}"]
        buttons: list[list[InlineKeyboardButton]] = []
        for local_index, item in enumerate(visible_items):
            icon = status_icons.get(item.status, "•")
            if mode == "r":
                closing = registration_closes_at(item, datetime.now(UTC))
                prefix = (
                    f"до {closing.astimezone(settings.tz):%d.%m} · " if closing is not None else ""
                )
                available = max(12, 44 - len(prefix))
                title_label = (
                    item.title
                    if len(item.title) <= available
                    else f"{item.title[: available - 3]}..."
                )
                label = prefix + title_label
            else:
                label = item.title if len(item.title) <= 44 else f"{item.title[:41]}..."
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"{icon} {label}",
                        callback_data=f"ce:{mode}:{offset + local_index}",
                    )
                ]
            )
        if not items:
            lines.append("Ничего не найдено. Измени класс, темы или источники.")
        buttons.append(
            [
                InlineKeyboardButton(
                    text="←", callback_data=f"cat:{mode}:{page - 1}" if page > 0 else "noop"
                ),
                InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="noop"),
                InlineKeyboardButton(
                    text="→",
                    callback_data=f"cat:{mode}:{page + 1}" if page + 1 < pages else "noop",
                ),
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text="Класс и темы", callback_data="settings:catalog", style="primary"
                )
            ]
        )
        buttons.append([InlineKeyboardButton(text="Главное меню", callback_data="home")])
        await _answer_or_edit(
            event, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    async def show_catalog_event(callback: CallbackQuery, mode: str, index: int) -> None:
        user_id = actor_id(callback)
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            items = await catalog_items(session, profile, mode)
            await session.commit()
        if not items:
            await show_catalog(callback, mode=mode)
            return
        index = min(max(index, 0), len(items) - 1)
        await show_event(
            callback,
            items[index].id,
            CatalogContext(mode=mode, index=index, total=len(items)),
        )

    def parse_contextual_callback(data: str, prefix: str) -> tuple[CatalogContext | None, str]:
        payload = data.removeprefix(prefix + ":")
        parts = payload.split(":", maxsplit=2)
        if len(parts) == 3 and parts[0] in {"a", "m", "r"} and parts[1].isdigit():
            return CatalogContext(parts[0], int(parts[1]), 0), parts[2]
        return None, payload

    async def show_onboarding_tags(callback: CallbackQuery, page: int = 0) -> None:
        user_id = actor_id(callback)
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            await session.commit()
        await _answer_or_edit(
            callback,
            "🏷 <b>Какие направления интересны?</b>\n"
            f"Класс: {profile.school_grade or '—'}. "
            f"Выбрано предметов и групп: {len(profile.tag_filters or [])}.\n"
            "Выбери предметы или целые группы ВсОШ и МОШ. Группа добавляет все её "
            "предметы по классу, даже если отдельно выбраны другие темы. "
            "Подберём события из календаря и включим напоминания. "
            "Или нажми «Все предметы».",
            reply_markup=_onboarding_tag_keyboard(profile, page),
        )

    async def is_admin(user_id: int) -> bool:
        async with factory() as session:
            profile = await session.get(UserProfile, user_id)
            return (
                profile is not None
                and profile.role == UserRole.ADMIN.value
                and profile.access_status == AccessStatus.ACTIVE.value
            )

    async def show_users(event: Message | CallbackQuery) -> None:
        if not await is_admin(actor_id(event)):
            await _answer_or_edit(event, "Команда доступна только администратору.")
            return
        async with factory() as session:
            result = await session.execute(
                select(UserProfile).order_by(UserProfile.created_at, UserProfile.telegram_user_id)
            )
            profiles = list(result.scalars())
        lines = ["👥 <b>Пользователи OlymPing</b>"]
        rows: list[list[InlineKeyboardButton]] = []
        for profile in profiles:
            name = profile.display_name or (
                f"@{profile.username}" if profile.username else str(profile.telegram_user_id)
            )
            role = "админ" if profile.role == UserRole.ADMIN.value else "пользователь"
            lines.append(
                f"• {html.escape(name)} · {role} · {profile.access_status} · "
                f"{profile.school_grade or '—'} класс"
            )
            if profile.role != UserRole.ADMIN.value:
                action = (
                    "unblock" if profile.access_status == AccessStatus.BLOCKED.value else "block"
                )
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=("Разблокировать " if action == "unblock" else "Заблокировать ")
                            + name[:24],
                            callback_data=f"admin:{action}:{profile.telegram_user_id}",
                            style="success" if action == "unblock" else "danger",
                        )
                    ]
                )
        rows.append([InlineKeyboardButton(text="Главное меню", callback_data="home")])
        await _answer_or_edit(
            event,
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        user = message.from_user
        if user is None:
            return
        payload_parts = (message.text or "").split(maxsplit=1)
        payload = payload_parts[1] if len(payload_parts) == 2 else ""
        async with factory() as session:
            profile = await session.get(UserProfile, user.id)
            if profile is None:
                if not payload.startswith("invite_"):
                    await message.answer("Нужна одноразовая ссылка-приглашение администратора.")
                    return
                profile = await redeem_invitation(
                    session,
                    token=payload.removeprefix("invite_"),
                    telegram_user_id=user.id,
                    timezone=settings.timezone,
                    username=user.username,
                    display_name=user.full_name,
                )
                if profile is None:
                    await message.answer(
                        "Приглашение недействительно, уже использовано или истекло."
                    )
                    return
            else:
                if profile.access_status != AccessStatus.ACTIVE.value:
                    await message.answer("Доступ к боту заблокирован администратором.")
                    return
                profile.username = user.username
                profile.display_name = user.full_name
            await session.commit()
            onboarding_completed = profile.onboarding_completed
            has_grade = profile.school_grade is not None
        if onboarding_completed:
            await show_home(message)
        elif not has_grade:
            await message.answer(
                "👋 <b>Добро пожаловать в OlymPing</b>\nСначала выбери свой класс.",
                reply_markup=_onboarding_grade_keyboard(),
            )
        else:
            await message.answer(
                "Продолжим настройку интересов.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Выбрать темы", callback_data="onboard:tags:0")]
                    ]
                ),
            )

    @router.callback_query(F.data.startswith("onboard:"))
    async def onboarding_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        payload = callback.data.removeprefix("onboard:")
        if payload == "noop":
            await callback.answer()
            return
        if payload == "back":
            await _answer_or_edit(
                callback, "Выбери свой класс.", reply_markup=_onboarding_grade_keyboard()
            )
            return
        if payload.startswith("grade:"):
            grade = int(payload.removeprefix("grade:"))
            if not 1 <= grade <= 11:
                await callback.answer("Некорректный класс", show_alert=True)
                return
            async with factory() as session:
                profile = await ensure_user_profile(session, user_id, settings.timezone)
                profile.school_grade = grade
                await session.commit()
            await show_onboarding_tags(callback)
            return
        if payload.startswith("tags:"):
            await show_onboarding_tags(callback, int(payload.removeprefix("tags:")))
            return
        if payload.startswith("tag:"):
            _, page_value, tag = payload.split(":", maxsplit=2)
            if tag not in TAG_LABELS:
                await callback.answer("Неизвестная тема", show_alert=True)
                return
            async with factory() as session:
                profile = await ensure_user_profile(session, user_id, settings.timezone)
                selected = set(profile.tag_filters or [])
                if tag in selected:
                    selected.remove(tag)
                else:
                    selected.add(tag)
                profile.tag_filters = sorted(selected)
                await session.commit()
            await show_onboarding_tags(callback, int(page_value))
            return
        if payload in {"done", "all"}:
            async with factory() as session:
                profile = await ensure_user_profile(session, user_id, settings.timezone)
                if profile.school_grade is None:
                    await callback.answer("Сначала выбери класс", show_alert=True)
                    return
                if payload == "all":
                    profile.tag_filters = []
                elif not profile.tag_filters:
                    await callback.answer(
                        "Выбери предметы, группы или нажми «Все предметы»", show_alert=True
                    )
                    return
                result = await complete_onboarding(session, user_id)
                await session.commit()
            await _answer_or_edit(
                callback,
                f"✅ Анкета готова. Подходит событий: {result.matched}.\n"
                f"Добавлено в твои подписки: {result.subscribed}.\n"
                "Твои отметки регистрации и «Не интересно» сохранены."
                if result.matched
                else (
                    "Пока нет событий по этим интересам и классу. "
                    "Можно изменить выбор или ждать обновлений."
                ),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Мои олимпиады", callback_data="list:mine")],
                        [
                            InlineKeyboardButton(
                                text="Изменить анкету", callback_data="onboard:back"
                            )
                        ],
                        [InlineKeyboardButton(text="Главное меню", callback_data="home")],
                    ]
                ),
            )

    @router.message(Command("onboarding"))
    async def onboarding_command(message: Message) -> None:
        await message.answer(
            "Подберём твой календарь. Сначала выбери класс.",
            reply_markup=_onboarding_grade_keyboard(),
        )

    @router.message(Command("invite"))
    async def invite_handler(message: Message, bot: Bot) -> None:
        user_id = actor_id(message)
        async with factory() as session:
            try:
                invitation = await create_invitation(session, created_by=user_id)
            except AccessDeniedError:
                await message.answer("Команда доступна только администратору.")
                return
            await session.commit()
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start=invite_{invitation.token}"
        await message.answer(
            "🎟 <b>Одноразовое приглашение</b>\n"
            "Действует 7 дней и только для одного аккаунта.\n"
            f"<code>{html.escape(link)}</code>"
        )

    @router.message(Command("users"))
    async def users_handler(message: Message) -> None:
        await show_users(message)

    @router.message(Command("revoke"))
    async def revoke_handler(message: Message) -> None:
        parts = (message.text or "").split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Формат: <code>/revoke TELEGRAM_ID</code>")
            return
        target_id = int(parts[1])
        async with factory() as session:
            try:
                profile = await set_user_access(
                    session,
                    actor_id=actor_id(message),
                    target_id=target_id,
                    status=AccessStatus.BLOCKED,
                )
            except AccessDeniedError:
                await message.answer("Команда доступна только администратору.")
                return
            if profile is None:
                await message.answer("Пользователь не найден или является администратором.")
                return
            await session.commit()
        await message.answer("Доступ пользователя отозван.")

    @router.message(Command("today"))
    async def today_handler(message: Message) -> None:
        await show_period(message, "today")

    @router.message(Command("week"))
    async def week_handler(message: Message) -> None:
        await show_period(message, "week")

    @router.message(Command("all"))
    async def all_handler(message: Message) -> None:
        await show_catalog(message)

    @router.message(Command("mine"))
    async def mine_handler(message: Message) -> None:
        await show_catalog(message, mode="m")

    @router.message(Command("register"))
    async def register_handler(message: Message) -> None:
        await show_catalog(message, mode="r")

    @router.message(Command("settings"))
    async def settings_handler(message: Message) -> None:
        user_id = actor_id(message)
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            await session.commit()
            keyboard = settings_keyboard(profile)
        await message.answer(
            "⚙️ <b>Настройки OlymPing</b>\n"
            "<blockquote>Уведомления о новых событиях и автоподписка работают независимо. "
            "Переключение автоподписки не меняет уже выбранные олимпиады.</blockquote>",
            reply_markup=keyboard,
        )

    @router.message(Command("remind"))
    async def remind_handler(message: Message) -> None:
        user_id = actor_id(message)
        parts = (message.text or "").split()
        usage = (
            "Формат: <code>/remind EVENT_ID DAYS HH:MM [KIND]</code>\n"
            "Также: <code>/remind EVENT_ID off</code> или <code>default</code>."
        )
        if len(parts) < 3:
            await message.answer(usage)
            return
        event_id, action = parts[1], parts[2].casefold()
        async with factory() as session:
            if await session.get(Event, event_id) is None:
                await message.answer("Событие с таким ID не найдено.")
                return
            await session.execute(
                delete(ReminderRule).where(
                    ReminderRule.telegram_user_id == user_id,
                    ReminderRule.event_id == event_id,
                )
            ) if action in {"off", "default"} else None
            if action == "off":
                session.add(
                    ReminderRule(
                        id=f"custom:{uuid4().hex}",
                        telegram_user_id=user_id,
                        event_id=event_id,
                        mode=ReminderMode.CALENDAR.value,
                        enabled=False,
                    )
                )
                await session.commit()
                await message.answer("Напоминания для события отключены.")
                return
            if action == "default":
                await session.commit()
                await message.answer("Восстановлены правила категории.")
                return
            if len(parts) < 4:
                await message.answer(usage)
                return
            try:
                days = int(action)
                hour, minute = (int(value) for value in parts[3].split(":", maxsplit=1))
                if not 0 <= days <= 365 or not 0 <= hour <= 23 or not 0 <= minute <= 59:
                    raise ValueError
            except ValueError:
                await message.answer(usage)
                return
            kind = parts[4] if len(parts) > 4 else None
            if kind and kind not in {value.value for value in MilestoneKind}:
                await message.answer("Неизвестный тип этапа.\n" + usage)
                return
            session.add(
                ReminderRule(
                    id=f"custom:{uuid4().hex}",
                    telegram_user_id=user_id,
                    event_id=event_id,
                    milestone_kind=kind,
                    mode=ReminderMode.CALENDAR.value,
                    days_before=days,
                    local_time=f"{hour:02d}:{minute:02d}",
                )
            )
            await session.commit()
        await message.answer("Правило добавлено. Повторите команду, чтобы добавить ещё одно.")

    @router.callback_query(F.data == "home")
    async def home_callback(callback: CallbackQuery) -> None:
        await show_home(callback)

    @router.callback_query(F.data.in_({"list:today", "list:week", "list:month"}))
    async def list_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        await show_period(callback, callback.data.split(":", maxsplit=1)[1])

    @router.callback_query(F.data == "list:all")
    async def all_callback(callback: CallbackQuery) -> None:
        await show_catalog(callback)

    @router.callback_query(F.data == "list:mine")
    async def mine_callback(callback: CallbackQuery) -> None:
        await show_catalog(callback, mode="m")

    @router.callback_query(F.data == "list:registration")
    async def registration_callback(callback: CallbackQuery) -> None:
        await show_catalog(callback, mode="r")

    @router.callback_query(F.data.startswith("cat:"))
    async def catalog_page_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        _, mode, page = callback.data.split(":", maxsplit=2)
        await show_catalog(callback, mode=mode, page=int(page))

    @router.callback_query(F.data.startswith("ce:"))
    async def catalog_event_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        _, mode, index = callback.data.split(":", maxsplit=2)
        await show_catalog_event(callback, mode, int(index))

    @router.callback_query(F.data == "noop")
    async def noop_callback(callback: CallbackQuery) -> None:
        await callback.answer()

    @router.callback_query(F.data.startswith("evt:"))
    async def event_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        event_id = callback.data.removeprefix("evt:")
        await show_event(callback, event_id)

    @router.callback_query(F.data.startswith("pref:"))
    async def preference_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        _, action, payload = callback.data.split(":", maxsplit=2)
        context, event_id = parse_contextual_callback(f"pref:{payload}", "pref")
        interests = {
            "w": EventInterest.WATCHING,
            "r": EventInterest.REGISTERED,
            "i": EventInterest.IGNORED,
        }
        interest = interests.get(action)
        if interest is None:
            await callback.answer("Некорректное действие", show_alert=True)
            return
        async with factory() as session:
            try:
                await toggle_event_interest(
                    session,
                    actor_id=user_id,
                    event_id=event_id,
                    interest=interest,
                )
            except StateTargetNotFoundError:
                await callback.answer("Олимпиада не найдена", show_alert=True)
                return
            await session.commit()
        if context is not None:
            await show_catalog_event(callback, context.mode, context.index)
        else:
            await show_event(callback, event_id)

    @router.callback_query(F.data.startswith("progress:"))
    async def progress_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        context, event_id = parse_contextual_callback(callback.data, "progress")
        await show_progress(callback, event_id, context)

    @router.callback_query(F.data.startswith("stage:"))
    async def stage_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        context, milestone_id = parse_contextual_callback(callback.data, "stage")
        await show_stage(callback, milestone_id, context)

    @router.callback_query(F.data.startswith("out:"))
    async def outcome_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        _, action, payload = callback.data.split(":", maxsplit=2)
        context, milestone_id = parse_contextual_callback(f"out:{payload}", "out")
        outcomes = {
            "a": StageOutcome.PARTICIPATED,
            "p": StageOutcome.PASSED,
            "n": StageOutcome.NOT_PASSED,
            "s": StageOutcome.SKIPPED,
        }
        if action not in {*outcomes, "x"}:
            await callback.answer("Некорректное действие", show_alert=True)
            return
        async with factory() as session:
            try:
                await set_stage_outcome(
                    session,
                    actor_id=user_id,
                    milestone_id=milestone_id,
                    outcome=outcomes.get(action),
                )
            except StateTargetNotFoundError:
                await callback.answer("Этап не найден", show_alert=True)
                return
            await session.commit()
        await show_stage(callback, milestone_id, context)

    @router.callback_query(F.data.startswith("r:"))
    async def reminder_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        _, action, payload = callback.data.split(":", maxsplit=2)
        context, event_id = parse_contextual_callback(f"r:{payload}", "r")
        async with factory() as session:
            await set_event_reminders_muted(
                session,
                user_id=user_id,
                event_id=event_id,
                muted=action == "m",
            )
            await session.commit()
        if context is not None:
            await show_catalog_event(callback, context.mode, context.index)
        else:
            await show_event(callback, event_id)

    async def show_settings(callback: CallbackQuery, page: str = "main") -> None:
        user_id = actor_id(callback)
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            await session.commit()
            if page == "sources":
                keyboard = _source_settings_keyboard(profile.category_settings)
                text = (
                    "🗂 <b>Источники</b>\n"
                    "Отключённый источник скрывается из календаря и не получает автоподписки."
                )
            elif page == "ctf":
                keyboard = _ctf_settings_keyboard(profile.ctf_filters)
                text = "🚩 <b>Фильтры CTFtime</b>"
            elif page == "catalog":
                keyboard = _catalog_filter_keyboard(profile)
                grade = profile.school_grade
                text = (
                    "🎯 <b>Класс и темы</b>\n"
                    f"Сейчас: <b>{grade or 'не указан'} класс</b>. Показываются олимпиады "
                    "для этого класса и более старших категорий.\n"
                    "<blockquote>Если выбрано несколько тем, достаточно совпадения хотя бы "
                    "с одной. События с неизвестными возрастными ограничениями не скрываются."
                    "</blockquote>"
                )
            elif page.startswith("tags:"):
                tag_page = int(page.split(":", maxsplit=1)[1])
                keyboard = _tag_filter_keyboard(profile, tag_page)
                selected = [TAG_LABELS.get(tag, tag) for tag in (profile.tag_filters or [])]
                selected_text = ", ".join(selected) if selected else "все темы"
                text = (
                    "🏷 <b>Темы олимпиад</b>\n"
                    f"Выбрано: {html.escape(selected_text)}\n"
                    "<blockquote>Достаточно любой выбранной темы или группы. "
                    "Группа включает все её предметы по классу. Выключенные в настройках "
                    "источники остаются скрытыми.</blockquote>"
                )
            else:
                keyboard = settings_keyboard(profile)
                text = (
                    "⚙️ <b>Настройки OlymPing</b>\n"
                    "<blockquote>Новые события и автоподписка — независимые настройки. "
                    "Текущие подписки не изменяются.</blockquote>"
                )
        await _answer_or_edit(callback, text, reply_markup=keyboard)

    @router.callback_query(F.data == "settings")
    async def settings_callback(callback: CallbackQuery) -> None:
        await show_settings(callback)

    @router.callback_query(F.data.startswith("settings:"))
    async def settings_page_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        await show_settings(callback, callback.data.removeprefix("settings:"))

    @router.callback_query(F.data.startswith("setting:"))
    async def setting_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        key = callback.data.removeprefix("setting:")
        fields = {
            "notify_new_events",
            "auto_subscribe_new_events",
            "notify_event_updates",
            "notify_open_events",
        }
        if key not in fields:
            await callback.answer("Неизвестная настройка", show_alert=True)
            return
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            setattr(profile, key, not bool(getattr(profile, key)))
            await session.commit()
        await show_settings(callback)

    @router.callback_query(F.data.startswith("grade:"))
    async def grade_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        grade = int(callback.data.removeprefix("grade:"))
        if not 1 <= grade <= 11:
            await callback.answer("Класс должен быть от 1 до 11", show_alert=True)
            return
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            profile.school_grade = grade
            await session.commit()
        await show_settings(callback, "catalog")

    @router.callback_query(F.data.startswith("tag:"))
    async def tag_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        payload = callback.data.removeprefix("tag:")
        page = 0
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            if payload == "clear":
                profile.tag_filters = []
            else:
                page_value, tag = payload.split(":", maxsplit=1)
                page = int(page_value)
                if tag not in TAG_LABELS:
                    await callback.answer("Неизвестная тема", show_alert=True)
                    return
                selected = set(profile.tag_filters or [])
                if tag in selected:
                    selected.remove(tag)
                else:
                    selected.add(tag)
                profile.tag_filters = sorted(selected)
            await session.commit()
        await show_settings(callback, f"tags:{page}")

    @router.callback_query(F.data.startswith("source:"))
    async def category_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        kind = callback.data.removeprefix("source:")
        if kind not in {source.value for source in SourceKind}:
            await callback.answer("Неизвестный источник", show_alert=True)
            return
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            values = dict(profile.category_settings or {})
            values[kind] = not bool(values.get(kind, True))
            profile.category_settings = values
            await session.commit()
        await show_settings(callback, "sources")

    @router.callback_query(F.data.startswith("ctf:"))
    async def ctf_filter_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        user_id = actor_id(callback)
        key = callback.data.removeprefix("ctf:")
        async with factory() as session:
            profile = await ensure_user_profile(session, user_id, settings.timezone)
            values = dict(profile.ctf_filters or {})
            if key == "online":
                cycle: list[str | int] = ["all", "online", "onsite"]
            elif key == "restrictions":
                cycle = ["all", "open"]
            else:
                cycle = [0, 25, 50]
                key = "min_weight"
            current = values.get(key, cycle[0])
            values[key] = (
                cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else cycle[0]
            )
            profile.ctf_filters = values
            await session.commit()
        await show_settings(callback, "ctf")

    @router.callback_query(F.data.startswith("admin:"))
    async def admin_user_callback(callback: CallbackQuery) -> None:
        assert callback.data is not None
        parts = callback.data.split(":", maxsplit=2)
        if len(parts) != 3 or parts[1] not in {"block", "unblock"} or not parts[2].isdigit():
            await callback.answer("Некорректная команда", show_alert=True)
            return
        _, action, target_value = parts
        target_id = int(target_value)
        async with factory() as session:
            try:
                profile = await set_user_access(
                    session,
                    actor_id=actor_id(callback),
                    target_id=target_id,
                    status=(AccessStatus.ACTIVE if action == "unblock" else AccessStatus.BLOCKED),
                )
            except AccessDeniedError:
                await callback.answer("Недостаточно прав", show_alert=True)
                return
            if profile is None:
                await callback.answer("Пользователь не найден", show_alert=True)
                return
            await session.commit()
        await show_users(callback)

    async def do_sync(event: Message | CallbackQuery) -> None:
        if not await is_admin(actor_id(event)):
            await _answer_or_edit(event, "Синхронизация доступна только администратору.")
            return
        await _answer_or_edit(event, "Синхронизация запущена…")
        try:
            result = await synchronize_calendar(factory, settings)
        except CalendarImportError:
            logger.exception("Manual calendar import failed")
            await _answer_or_edit(
                event, "Не удалось прочитать календарь. Проверь файлы источников."
            )
            return
        text = "Календарь обновлён.\n" + (
            "Рассылка подготовлена на проверку. Пакет придёт отдельным сообщением; "
            "его также можно открыть через /reviews."
            if result.review_batch_id is not None
            else "Новых рассылок нет."
        )
        if result.ctftime is None:
            text += "\nCTFtime временно недоступен; календарь олимпиад обновлён."
        if isinstance(event, CallbackQuery) and isinstance(event.message, Message):
            await event.message.answer(text)
        elif isinstance(event, Message):
            await event.answer(text)

    @router.message(Command("sync"))
    async def sync_handler(message: Message) -> None:
        await do_sync(message)

    @router.callback_query(F.data == "sync")
    async def sync_callback(callback: CallbackQuery) -> None:
        await do_sync(callback)

    register_review_handlers(router, factory)
    return router


async def _notification_loop(
    bot: Bot,
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    stop: asyncio.Event,
) -> None:
    async def send(user_id: int, text: str) -> None:
        await bot.send_message(user_id, text)

    while not stop.is_set():
        try:
            async with factory() as session:
                user_ids = await active_user_ids(session)
            users_loaded = True
        except Exception:
            logger.exception("Unable to retrieve notification users")
            user_ids = []
            users_loaded = False
        for user_id in user_ids:
            try:
                counts = await run_notification_cycle(
                    factory,
                    owner_id=user_id,
                    send=send,
                    grace_hours=settings.reminder_grace_hours,
                    registration_digest=user_id == settings.owner_telegram_id,
                )
                if any(counts):
                    logger.info(
                        "Notification cycle for %d: reminders=%d changes=%d",
                        user_id,
                        *counts,
                    )
            except Exception:
                logger.exception("Notification cycle failed for user %d", user_id)
        if users_loaded:
            record_heartbeat(settings, "notification")
        try:
            await notify_pending_review(bot, factory, settings.owner_telegram_id)
        except Exception:
            logger.exception("Administrator review notification failed")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=settings.reminder_poll_seconds)


async def _ctftime_loop(
    factory: async_sessionmaker[AsyncSession], settings: Settings, stop: asyncio.Event
) -> None:
    interval = settings.ctftime_sync_interval_hours * 3600
    while not stop.is_set():
        try:
            async with factory() as session:
                summary = await sync_ctftime(
                    session,
                    base_url=settings.ctftime_base_url,
                    lookahead_days=settings.ctftime_lookahead_days,
                )
                await queue_open_event_notices(session)
                await session.commit()
            logger.info("Scheduled CTFtime sync completed: %s", summary)
        except Exception:
            logger.exception("Scheduled CTFtime sync failed")
        else:
            record_heartbeat(settings, "ctftime")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)


async def prepare_database(
    engine: AsyncEngine, factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    await upgrade_schema(settings.database_url)
    async with factory() as session:
        await ensure_admin_profile(session, settings.owner_telegram_id, settings.timezone)
        catalog_exists = (
            await session.execute(select(Event.id).limit(1))
        ).scalar_one_or_none() is not None
        try:
            summary = await import_data_directory(
                session,
                settings.data_dir,
                create_new_event_notices=catalog_exists,
            )
            logger.info("Calendar import completed: %s", summary)
            await queue_open_event_notices(session)
        except CalendarImportError:
            logger.exception("Calendar import failed")
            raise
        await session.commit()


async def run_bot(settings: Settings) -> None:
    if settings.telegram_bot_token is None:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the bot")
    if settings.owner_telegram_id <= 0:
        raise RuntimeError("OWNER_TELEGRAM_ID is required to run the bot")
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    bot: Bot | None = None
    stop = asyncio.Event()
    background: list[asyncio.Task[None]] = []
    polling: asyncio.Task[None] | None = None
    try:
        clear_heartbeats(settings)
        await prepare_database(engine, factory, settings)
        bot = Bot(
            token=settings.telegram_bot_token.get_secret_value(),
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True,
            ),
        )
        bot.session.middleware(PollingHeartbeatMiddleware(settings))
        dispatcher = Dispatcher()
        dispatcher.include_router(create_router(factory, settings))
        user_commands = [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="today", description="События сегодня"),
            BotCommand(command="week", description="События на 7 дней"),
            BotCommand(command="mine", description="Мои подписки"),
            BotCommand(command="register", description="Открытая регистрация"),
            BotCommand(command="all", description="Все олимпиады"),
            BotCommand(command="settings", description="Фильтры и категории"),
            BotCommand(command="onboarding", description="Анкета и подбор олимпиад"),
        ]
        await bot.set_my_commands(user_commands)
        await bot.set_my_commands(
            [
                *user_commands,
                BotCommand(command="invite", description="Пригласить друга"),
                BotCommand(command="users", description="Управление доступом"),
                BotCommand(command="revoke", description="Отозвать доступ по ID"),
                BotCommand(command="sync", description="Обновить календарь"),
                BotCommand(command="reviews", description="Проверить рассылки"),
            ],
            scope=BotCommandScopeChat(chat_id=settings.owner_telegram_id),
        )
        background = [
            asyncio.create_task(_notification_loop(bot, factory, settings, stop)),
            asyncio.create_task(_ctftime_loop(factory, settings, stop)),
            asyncio.create_task(supervise_runtime(settings, stop)),
        ]
        polling = asyncio.create_task(dispatcher.start_polling(bot))  # pyright: ignore[reportUnknownMemberType]
        done, _ = await asyncio.wait([polling, *background], return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task is not polling:
                if task.cancelled():
                    raise RuntimeError("background worker was cancelled unexpectedly")
                task.result()
                raise RuntimeError("background worker exited unexpectedly")
        await polling
    finally:
        stop.set()
        if polling is not None and not polling.done():
            polling.cancel()
        pending = [*background, *([polling] if polling is not None else [])]
        if pending:
            _, waiting = await asyncio.wait(pending, timeout=5)
            for task in waiting:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        if bot is not None:
            await bot.session.close()
        await engine.dispose()
