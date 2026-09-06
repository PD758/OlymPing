import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from olymping.config import Settings
from olymping.services.runtime_health import check_runtime_health, heartbeat_path, record_heartbeat


def settings(tmp_path: Path) -> Settings:
    return Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'bot.db'}")


@pytest.mark.asyncio
async def test_health_requires_all_workers(tmp_path: Path) -> None:
    result = await check_runtime_health(settings(tmp_path))
    assert not result.healthy
    assert result.reason == "worker heartbeat is unavailable"


@pytest.mark.asyncio
async def test_health_accepts_fresh_heartbeats(tmp_path: Path) -> None:
    value = settings(tmp_path)
    for worker in ("notification", "ctftime", "telegram-api", "polling"):
        record_heartbeat(value, worker)
    assert (await check_runtime_health(value)).healthy


@pytest.mark.asyncio
async def test_health_rejects_stale_notification(tmp_path: Path) -> None:
    value = settings(tmp_path)
    for worker in ("notification", "ctftime", "telegram-api", "polling"):
        record_heartbeat(value, worker)
    path = heartbeat_path(value)
    data = json.loads(path.read_text())
    data["notification"] = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    path.write_text(json.dumps(data))
    result = await check_runtime_health(value)
    assert not result.healthy
    assert result.reason == "notification worker heartbeat is stale"


@pytest.mark.asyncio
async def test_polling_heartbeat_requires_successful_telegram_response(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    from aiogram import Bot
    from aiogram.methods import GetUpdates

    from olymping.bot import PollingHeartbeatMiddleware

    value = settings(tmp_path)
    middleware = PollingHeartbeatMiddleware(value)
    bot = Bot(token="123456:test-token")
    try:
        failure = AsyncMock(side_effect=RuntimeError("offline"))
        with pytest.raises(RuntimeError):
            await middleware(failure, bot, GetUpdates())
        assert not heartbeat_path(value).exists()
        success = AsyncMock(return_value=[])
        assert await middleware(success, bot, GetUpdates()) == []
        data = json.loads(heartbeat_path(value).read_text())
        assert "polling" in data
        assert "telegram-api" in data
    finally:
        await bot.session.close()


@pytest.mark.asyncio
async def test_migrations_preserve_application_logging(tmp_path: Path) -> None:
    import logging

    from olymping.db import upgrade_schema

    logger = logging.getLogger("olymping.test_runtime")
    logger.disabled = False
    logger.setLevel(logging.DEBUG)
    await upgrade_schema(f"sqlite+aiosqlite:///{tmp_path / 'logging.db'}")
    assert not logger.disabled
    assert logger.level == logging.DEBUG
