from __future__ import annotations

import asyncio
import json
import math
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import SendMessage

from olymping.services.delivery import DeliveryDeferred, background_delivery


class PacedMessages(BaseRequestMiddleware):
    """One shared, non-bursting sendMessage budget for this polling instance."""

    def __init__(
        self,
        cooldown_path: Path,
        messages_per_second: float = 10,
        *,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not 0 < messages_per_second <= 20:
            raise ValueError("message rate must be greater than 0 and at most 20")
        self.path = cooldown_path
        self.clock, self.wall_clock, self.sleep = clock, wall_clock, sleep
        self.interval = 1 / messages_per_second
        self.lock = asyncio.Lock()
        # Avoid an immediate second message to the same chat across a restart.
        self.next_global = clock() + 3.1
        self.chat_next: dict[int | str, float] = {}
        self.cooldown_until = 0.0
        if cooldown_path.exists():
            raw = json.loads(cooldown_path.read_text())
            deadline = float(raw["retry_until"])
            if not math.isfinite(deadline):
                raise ValueError("invalid Telegram cooldown timestamp")
            self.cooldown_until = clock() + max(0, deadline - wall_clock())

    def defer(self, seconds: float) -> None:
        seconds = max(1, seconds) + 1  # Margin around Telegram's supplied deadline.
        self.cooldown_until = self.clock() + seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w") as handle:
            json.dump({"retry_until": self.wall_clock() + seconds}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self.path)

    async def __call__(
        self, make_request: NextRequestMiddlewareType[Any], bot: Bot, method: Any
    ) -> Any:
        if not isinstance(method, SendMessage):
            return await make_request(bot, method)
        while True:
            async with self.lock:
                now = self.clock()
                cooldown = self.cooldown_until - now
                if cooldown > 0:
                    if background_delivery.get():
                        raise DeliveryDeferred(cooldown)
                    delay = cooldown
                else:
                    delay = max(self.next_global, self.chat_next.get(method.chat_id, 0)) - now
                    if delay <= 0:
                        self.next_global = now + self.interval
                        self.chat_next = {
                            key: value for key, value in self.chat_next.items() if value > now
                        }
                        group = isinstance(method.chat_id, str) or method.chat_id < 0
                        self.chat_next[method.chat_id] = now + (3.1 if group else 1.1)
                        try:
                            return await make_request(bot, method)
                        except TelegramRetryAfter as exc:
                            self.defer(exc.retry_after)
                            if background_delivery.get():
                                raise DeliveryDeferred(self.cooldown_until - self.clock()) from exc
                            delay = self.cooldown_until - self.clock()
            # Never hold the lock while waiting; polling and callbacks stay responsive.
            await self.sleep(min(max(delay, 0), 30))
