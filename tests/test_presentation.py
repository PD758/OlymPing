from __future__ import annotations

from datetime import UTC, datetime

from olymping.bot import CatalogContext, event_keyboard, format_event, settings_keyboard
from olymping.models import Event, EventInterest, Milestone, UserProfile
from olymping.presentation import telegram_time
from olymping.services.reminders import REMINDER_MUTED


def test_telegram_time_uses_localized_date_entity() -> None:
    value = datetime(2026, 10, 21, 6, tzinfo=UTC)

    rendered = telegram_time(value, "Europe/Moscow")

    assert '<tg-time unix="' in rendered
    assert 'format="wDT"' in rendered
    assert "21.10.2026 09:00" in rendered


def test_event_card_and_buttons_expose_subscription_and_progress() -> None:
    event = Event(
        id="vosh:security-2026",
        source_kind="VOSH",
        title="ВсОШ — информационная безопасность",
        description="Подробное описание олимпиады.",
        source_url="https://example.edu/",
        status="tentative",
    )
    event.milestones = [
        Milestone(
            id="vosh:security-2026:school",
            event_id=event.id,
            kind="qualifier",
            title="Школьный этап",
            starts_at=datetime(2026, 10, 21, 6, tzinfo=UTC),
            precision="exact",
            status="tentative",
            is_online=True,
        )
    ]

    text = format_event(event, "Europe/Moscow")
    keyboard = event_keyboard(event, EventInterest.WATCHING.value)
    buttons = [button for row in keyboard.inline_keyboard for button in row]

    assert "<tg-time" in text
    assert "<blockquote expandable>" in text
    assert any(button.text == "🔔 Подписан" and button.style == "success" for button in buttons)
    assert any(button.callback_data == f"progress:{event.id}" for button in buttons)


def test_settings_have_independent_colored_toggles() -> None:
    profile = UserProfile(
        telegram_user_id=1,
        timezone="Europe/Moscow",
        category_settings={},
        ctf_filters={},
        notify_new_events=True,
        auto_subscribe_new_events=False,
        notify_event_updates=True,
    )

    keyboard = settings_keyboard(profile)
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    by_callback = {button.callback_data: button for button in buttons if button.callback_data}

    assert by_callback["setting:notify_new_events"].style == "success"
    assert by_callback["setting:auto_subscribe_new_events"].style == "danger"
    assert by_callback["setting:notify_event_updates"].style == "success"


def test_catalog_event_keyboard_preserves_navigation_context() -> None:
    event = Event(
        id="rsosh:algorithms-2026",
        source_kind="RSOSH",
        title="Algorithms",
        source_url="https://example.edu/",
        status="tbd",
    )

    keyboard = event_keyboard(
        event,
        None,
        CatalogContext(mode="a", index=4, total=17),
    )
    callbacks = {
        button.callback_data
        for row in keyboard.inline_keyboard
        for button in row
        if button.callback_data
    }

    assert "ce:a:3" in callbacks
    assert "ce:a:5" in callbacks
    assert "cat:a:0" in callbacks
    assert f"pref:w:a:4:{event.id}" in callbacks


def test_reminder_toggle_exposes_current_state_and_next_action() -> None:
    event = Event(
        id="rsosh:reminders-2026",
        source_kind="RSOSH",
        title="Reminders",
        source_url="https://example.edu/",
        status="tbd",
    )

    keyboard = event_keyboard(event, None, reminder_status=REMINDER_MUTED)
    buttons = [button for row in keyboard.inline_keyboard for button in row]

    toggle = next(button for button in buttons if button.text.startswith("🔕"))
    assert toggle.text == "🔕 Напоминания: выключены"
    assert toggle.callback_data == f"r:d:{event.id}"
    assert toggle.style == "danger"
