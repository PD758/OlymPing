from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def telegram_time(value: datetime, timezone: str, *, date_only: bool = False) -> str:
    """Render a Bot API date-time entity with a readable fallback."""

    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value
    local = aware.astimezone(ZoneInfo(timezone))
    fallback = local.strftime("%d.%m.%Y" if date_only else "%d.%m.%Y %H:%M")
    date_format = "D" if date_only else "wDT"
    return f'<tg-time unix="{int(aware.timestamp())}" format="{date_format}">{fallback}</tg-time>'
