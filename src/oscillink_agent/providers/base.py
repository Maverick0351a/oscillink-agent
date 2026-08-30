"""Provider-neutral generation contract."""

from dataclasses import dataclass
from typing import Protocol

from oscillink_agent.chat.contracts import ChatProviderProjection
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.memory.repository import ProductMemoryRecord


class ProviderRequestError(RuntimeError):
    """The configured provider could not complete the request."""


class ProviderTimeoutError(ProviderRequestError):
    """The configured provider exceeded its bounded request timeout."""


class ProviderResponseError(RuntimeError):
    """The configured provider returned an invalid completion payload."""


@dataclass(frozen=True)
class ProviderResult:
    """Provider output before governed citations and persistence are attached."""

    answer: str


class ChatProvider(Protocol):
    """A provider consumes compiled context but cannot select memory authority."""

    @property
    def projection(self) -> ChatProviderProjection: ...

    def generate(
        self,
        *,
        message: str,
        context_manifest: ContextManifest,
        records: tuple[ProductMemoryRecord, ...],
    ) -> ProviderResult: ...
