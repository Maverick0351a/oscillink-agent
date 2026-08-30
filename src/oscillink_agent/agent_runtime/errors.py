"""Governed runtime persistence errors."""


class ChatIdempotencyConflictError(ValueError):
    """An idempotency key belongs to another chat request."""


class ChatRunNotFoundError(LookupError):
    """No persisted run matches the requested session and run IDs."""


class ChatRunIncompleteError(ValueError):
    """A persisted run lacks its required trajectory or context artifact."""


class ChatProviderRunFailedError(RuntimeError):
    """A prior dispatch has a durable bounded failure and cannot be retried."""

    def __init__(self, failure_kind: str) -> None:
        super().__init__(failure_kind)
        self.failure_kind = failure_kind


class ChatProviderDispatchUncertainError(RuntimeError):
    """A prior dispatch may have occurred and cannot safely be repeated."""
