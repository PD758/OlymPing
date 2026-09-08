import asyncio
from itertools import pairwise
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import GetUpdates, SendMessage

from olymping.services.delivery import DeliveryDeferred, background_delivery
from olymping.telegram_delivery import PacedMessages


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        await asyncio.sleep(0)


def limiter(path: Path, clock: Clock) -> PacedMessages:
    return PacedMessages(path, clock=clock.time, wall_clock=clock.time, sleep=clock.sleep)


@pytest.mark.asyncio
async def test_global_and_per_chat_pacing_share_one_budget(tmp_path: Path) -> None:
    clock = Clock()
    paced = limiter(tmp_path / "cooldown.json", clock)
    bot = Bot(token="123456:test-token")
    starts: list[tuple[int | str, float]] = []

    async def request(_bot: Bot, method: SendMessage) -> bool:
        starts.append((method.chat_id, clock.now))
        return True

    transport = AsyncMock(side_effect=request)
    try:
        for user_id in range(1, 101):
            await paced(transport, bot, SendMessage(chat_id=user_id, text="digest"))
        assert all(b[1] - a[1] >= 0.1 - 1e-9 for a, b in pairwise(starts))
        assert abs(starts[-1][1] - starts[0][1] - 9.9) < 1e-6
        for chat_id, interval in [(100, 1.1), (-100, 3.1)]:
            await paced(transport, bot, SendMessage(chat_id=chat_id, text="part 1"))
            before = clock.now
            await paced(transport, bot, SendMessage(chat_id=chat_id, text="part 2"))
            assert clock.now - before >= interval - 1e-9
        assert len(paced.chat_next) < 40  # Old recipients do not accumulate forever.
    finally:
        await bot.session.close()


@pytest.mark.asyncio
async def test_concurrent_senders_do_not_burst(tmp_path: Path) -> None:
    clock = Clock()
    paced = limiter(tmp_path / "cooldown.json", clock)
    bot = Bot(token="123456:test-token")
    times: list[float] = []

    async def request(_bot: Bot, _method: SendMessage) -> bool:
        times.append(clock.now)
        return True

    try:
        transport = AsyncMock(side_effect=request)
        await asyncio.gather(
            *(paced(transport, bot, SendMessage(chat_id=i, text="x")) for i in range(1, 21))
        )
        assert len(times) == 20
        assert all(b - a >= 0.1 - 1e-9 for a, b in pairwise(times))
    finally:
        await bot.session.close()


@pytest.mark.asyncio
async def test_flood_wait_survives_restart_and_does_not_block_polling(tmp_path: Path) -> None:
    clock = Clock()
    path = tmp_path / "cooldown.json"
    paced = limiter(path, clock)
    bot = Bot(token="123456:test-token")
    method = SendMessage(chat_id=1, text="notice")
    transport = AsyncMock(
        side_effect=TelegramRetryAfter(method=method, message="flood", retry_after=60)
    )
    token = background_delivery.set(True)
    try:
        with pytest.raises(DeliveryDeferred) as deferred:
            await paced(transport, bot, method)
        assert deferred.value.retry_after >= 60
        restarted = limiter(path, clock)
        recovered = AsyncMock(return_value=True)
        with pytest.raises(DeliveryDeferred):
            await restarted(recovered, bot, method)
        recovered.assert_not_awaited()
        assert await restarted(recovered, bot, GetUpdates()) is True
        clock.now += 61
        assert await restarted(recovered, bot, method) is True
        assert recovered.await_count == 2
        assert method.allow_paid_broadcast is None
    finally:
        background_delivery.reset(token)
        await bot.session.close()


@pytest.mark.asyncio
async def test_interactive_reply_waits_for_retry_after(tmp_path: Path) -> None:
    clock = Clock()
    paced = limiter(tmp_path / "cooldown.json", clock)
    bot = Bot(token="123456:test-token")
    method = SendMessage(chat_id=1, text="reply")
    transport = AsyncMock(
        side_effect=[TelegramRetryAfter(method=method, message="flood", retry_after=5), True]
    )
    try:
        assert await paced(transport, bot, method) is True
        assert transport.await_count == 2
        assert clock.now >= 1009.1
    finally:
        await bot.session.close()
