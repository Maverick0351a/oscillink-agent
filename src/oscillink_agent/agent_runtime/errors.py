"""Governed runtime persistence errors."""


class ChatIdempotencyConflictError(ValueError):
    """An idempotency key belongs to another chat request."""


class ChatRunNotFoundError(LookupError):
    """No persisted run matches the requested session and run IDs."""


class ChatRunIncompleteError(ValueError):
    """A persisted run lacks its required trajectory or context artifact."""
