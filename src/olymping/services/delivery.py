from contextvars import ContextVar

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramUnauthorizedError,
)

# Background workers defer durable queue entries; interactive replies can wait.
background_delivery: ContextVar[bool] = ContextVar("background_delivery", default=False)
PERMANENT_ERROR_PREFIX = "permanent:"
PERMANENT_DELIVERY_ERRORS = (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramUnauthorizedError,
)


def is_permanent_delivery_error(exc: Exception) -> bool:
    """Whether Telegram rejected a request that a later retry cannot repair."""
    return isinstance(exc, PERMANENT_DELIVERY_ERRORS)


def delivery_error_detail(exc: Exception) -> str:
    prefix = PERMANENT_ERROR_PREFIX if is_permanent_delivery_error(exc) else ""
    return f"{prefix}{type(exc).__name__}: {exc}"[:2000]


def retry_delay_minutes(attempts: int) -> int:
    """Bound exponential retry delay shared by durable notification queues."""
    return min(60, 1 << min(max(attempts, 0), 6))


class DeliveryDeferred(Exception):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(f"Telegram flood control: retry in {retry_after:.1f}s")
