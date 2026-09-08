from contextvars import ContextVar

# Background workers defer durable queue entries; interactive replies can wait.
background_delivery: ContextVar[bool] = ContextVar("background_delivery", default=False)


class DeliveryDeferred(Exception):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(f"Telegram flood control: retry in {retry_after:.1f}s")
