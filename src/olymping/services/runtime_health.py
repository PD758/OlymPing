from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from olymping.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RuntimeHealth:
    healthy: bool
    reason: str | None = None


def heartbeat_path(settings: Settings) -> Path:
    prefix = "sqlite+aiosqlite:///"
    if settings.database_url.startswith(prefix):
        return (
            Path(settings.database_url.removeprefix(prefix))
            .expanduser()
            .resolve()
            .with_suffix(".heartbeat.json")
        )
    return Path("./data/olymping.heartbeat.json").resolve()


def record_heartbeat(settings: Settings, worker: str) -> None:
    path = heartbeat_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    values: dict[str, str] = {}
    with suppress(OSError, json.JSONDecodeError):
        values = json.loads(path.read_text())
    values[worker] = datetime.now(UTC).isoformat()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, sort_keys=True))
    temporary.replace(path)


def clear_heartbeats(settings: Settings) -> None:
    heartbeat_path(settings).unlink(missing_ok=True)


async def check_runtime_health(settings: Settings) -> RuntimeHealth:
    try:
        parsed: object = json.loads(heartbeat_path(settings).read_text())
    except (OSError, json.JSONDecodeError):
        return RuntimeHealth(False, "worker heartbeat is unavailable")
    if not isinstance(parsed, dict):
        return RuntimeHealth(False, "worker heartbeat is unavailable")
    values = cast(dict[str, object], parsed)
    now = datetime.now(UTC)
    limits = {
        "notification": timedelta(seconds=max(settings.reminder_poll_seconds * 3, 180)),
        "telegram-api": timedelta(minutes=15),
        "polling": timedelta(minutes=15),
        "ctftime": timedelta(hours=settings.ctftime_sync_interval_hours * 3),
    }
    for worker, limit in limits.items():
        try:
            raw_timestamp = values[worker]
            if not isinstance(raw_timestamp, str):
                raise ValueError
            timestamp = datetime.fromisoformat(raw_timestamp)
            if timestamp.tzinfo is None or timestamp > now or timestamp < now - limit:
                return RuntimeHealth(False, f"{worker} worker heartbeat is stale")
        except (KeyError, TypeError, ValueError):
            return RuntimeHealth(False, f"{worker} heartbeat is unavailable")
    return RuntimeHealth(True)


async def supervise_runtime(settings: Settings, stop: asyncio.Event) -> None:
    """Restart a stuck bot via process failure; tolerate an external CTFtime outage."""
    grace = max(180, settings.reminder_poll_seconds * 3)
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), timeout=grace)
    while not stop.is_set():
        result = await check_runtime_health(settings)
        if not result.healthy:
            if result.reason and result.reason.startswith("ctftime"):
                logger.warning("Runtime health degraded: %s", result.reason)
            else:
                raise RuntimeError(f"Bot workers stopped making progress: {result.reason}")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=60)
