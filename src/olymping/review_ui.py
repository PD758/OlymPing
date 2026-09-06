from __future__ import annotations

import logging
from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from olymping.models import Event, NotificationReview, ReviewSelection
from olymping.services.reviews import (
    StaleReviewError,
    decide_review,
    refresh_review,
    safe_event_block,
    toggle_review_event,
)
from olymping.services.users import AccessDeniedError, require_admin_profile

logger = logging.getLogger(__name__)


async def review_page(
    session: AsyncSession,
    batch_id: int,
    page: int = 0,
) -> tuple[str, InlineKeyboardMarkup]:
    batch = await session.get(NotificationReview, batch_id)
    if batch is None:
        return "Пакет не найден.", InlineKeyboardMarkup(inline_keyboard=[])
    if batch.status != "pending":
        status = (
            "Рассылка подтверждена." if batch.status == "approved" else "Сохранено без рассылки."
        )
        return f"Пакет №{batch.id}. {status}", InlineKeyboardMarkup(inline_keyboard=[])
    items = list(
        await session.scalars(
            select(ReviewSelection)
            .where(
                ReviewSelection.review_batch_id == batch_id,
            )
            .order_by(ReviewSelection.event_id)
        )
    )
    entries: list[tuple[int, ReviewSelection, Event, str]] = []
    for index, item in enumerate(items):
        event = await session.get(Event, item.event_id)
        if event is not None:
            entries.append(
                (
                    index,
                    item,
                    event,
                    safe_event_block(event, [item.summary], selected=item.selected),
                )
            )
    pages: list[list[tuple[int, ReviewSelection, Event, str]]] = [[]]
    size = 0
    for entry in entries:
        length = len(entry[3].encode("utf-16-le")) // 2
        if pages[-1] and size + length > 3500:
            pages.append([])
            size = 0
        pages[-1].append(entry)
        size += length + 2
    page = min(max(page, 0), len(pages) - 1)
    selected = sum(item.selected for item in items)
    text = (
        f"📋 <b>Проверка рассылки №{batch_id}</b>\n"
        f"Выбрано олимпиад: {selected}/{len(items)}. Данные уже обновлены.\n"
        "Каждому придут только подходящие ему пункты.\n\n"
    )
    text += "\n\n".join(entry[3] for entry in pages[page])
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if item.selected else "▫️ ") + event.title[:42],
                callback_data=f"review:toggle:{batch_id}:{index}:{page}",
            )
        ]
        for index, item, event, _ in pages[page]
    ]
    if len(pages) > 1:
        rows.append(
            [
                InlineKeyboardButton(
                    text="←", callback_data=f"review:show:{batch_id}:{max(0, page - 1)}"
                ),
                InlineKeyboardButton(
                    text=f"{page + 1}/{len(pages)}", callback_data=f"review:show:{batch_id}:{page}"
                ),
                InlineKeyboardButton(
                    text="→",
                    callback_data=f"review:show:{batch_id}:{min(len(pages) - 1, page + 1)}",
                ),
            ]
        )
    rows.extend(
        [
            [
                InlineKeyboardButton(
                    text="Обновить сведения", callback_data=f"review:refresh:{batch_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Разослать выбранное ({selected})",
                    style="success",
                    callback_data=f"review:approve:{batch_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Сохранить всё без рассылки", callback_data=f"review:dismiss:{batch_id}"
                )
            ],
        ]
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def notify_pending_review(
    bot: Bot,
    factory: async_sessionmaker[AsyncSession],
    admin_id: int,
) -> None:
    async with factory() as session:
        await require_admin_profile(session, admin_id)
        batch_id = await session.scalar(
            select(NotificationReview.id)
            .where(
                NotificationReview.status == "pending",
                NotificationReview.notified_at.is_(None),
            )
            .order_by(NotificationReview.id)
            .limit(1)
        )
        if batch_id is None:
            return
        claimed = await session.scalar(
            update(NotificationReview)
            .where(
                NotificationReview.id == batch_id,
                NotificationReview.notified_at.is_(None),
            )
            .values(notified_at=datetime.now(UTC))
            .returning(NotificationReview.id)
        )
        if claimed is None:
            return
        text, keyboard = await review_page(session, batch_id)
        await session.commit()
    try:
        await bot.send_message(admin_id, text, reply_markup=keyboard)
    except Exception as exc:
        async with factory() as session:
            await session.execute(
                update(NotificationReview)
                .where(NotificationReview.id == batch_id)
                .values(notified_at=None)
            )
            await session.commit()
        logger.warning("Could not deliver administrator review (%s)", type(exc).__name__)


def register_review_handlers(
    router: Router,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    @router.message(Command("reviews"))
    async def reviews_command(message: Message) -> None:
        if message.from_user is None:
            return
        async with factory() as session:
            try:
                await require_admin_profile(session, message.from_user.id)
            except AccessDeniedError:
                await message.answer("Проверка рассылок доступна только администратору.")
                return
            batches = list(
                await session.scalars(
                    select(NotificationReview)
                    .where(
                        NotificationReview.status == "pending",
                    )
                    .order_by(NotificationReview.id)
                    .limit(30)
                )
            )
        if not batches:
            await message.answer("Нет рассылок, ожидающих проверки.")
            return
        await message.answer(
            "Пакеты на проверку:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"Пакет №{batch.id}", callback_data=f"review:show:{batch.id}:0"
                        )
                    ]
                    for batch in batches
                ],
            ),
        )

    @router.callback_query(F.data.startswith("review:"))
    async def review_callback(callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) < 3 or not all(p.isdigit() for p in parts[2:]):
            await callback.answer("Некорректная команда", show_alert=True)
            return
        action, batch_id = parts[1], int(parts[2])
        page = 0
        async with factory() as session:
            try:
                await require_admin_profile(session, callback.from_user.id)
                if action in {"approve", "dismiss"}:
                    await decide_review(
                        session,
                        batch_id=batch_id,
                        actor_id=callback.from_user.id,
                        approve=action == "approve",
                    )
                elif action == "refresh":
                    await refresh_review(session, batch_id=batch_id, actor_id=callback.from_user.id)
                elif action == "toggle" and len(parts) == 5:
                    await toggle_review_event(
                        session,
                        batch_id=batch_id,
                        actor_id=callback.from_user.id,
                        index=int(parts[3]),
                    )
                    page = int(parts[4])
                elif action == "show" and len(parts) == 4:
                    page = int(parts[3])
                else:
                    await callback.answer("Некорректная команда", show_alert=True)
                    return
                text, keyboard = await review_page(session, batch_id, page)
                batch = await session.get(NotificationReview, batch_id)
                if batch is not None:
                    batch.notified_at = datetime.now(UTC)
                await session.commit()
            except AccessDeniedError:
                await callback.answer("Недостаточно прав", show_alert=True)
                return
            except StaleReviewError as exc:
                await callback.answer(str(exc), show_alert=True)
                return
        await callback.answer()
        if isinstance(callback.message, Message) and (
            callback.message.html_text != text or callback.message.reply_markup != keyboard
        ):
            try:
                await callback.message.edit_text(text, reply_markup=keyboard)
            except TelegramBadRequest as exc:
                if "message is not modified" not in str(exc):
                    raise
