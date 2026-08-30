"""Provider-neutral generation contract."""

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from oscillink_agent.chat.contracts import ChatProviderProjection
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.domain.events import Digest, canonical_payload_hash
from oscillink_agent.memory.repository import ProductMemoryRecord

ProviderKind = Literal["fake", "ollama", "openai_compatible"]


class ProviderExecutionIdentity(BaseModel):
    """Public non-secret identity used for provider execution provenance."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    kind: ProviderKind
    model: Annotated[str, Field(min_length=1, max_length=512)]
    actor_id: Annotated[
        str,
        Field(pattern=r"^model_[a-z0-9][a-z0-9_-]{1,62}$"),
    ]
    operation: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{2,127}$")]
    configuration_hash: Digest

    @property
    def projection(self) -> ChatProviderProjection:
        return ChatProviderProjection(kind=self.kind, model=self.model)


def build_execution_identity(
    *,
    kind: ProviderKind,
    model: str,
    public_configuration: Mapping[str, Any],
) -> ProviderExecutionIdentity:
    """Derive stable public execution provenance without secret configuration."""

    configuration = {
        "kind": kind,
        "model": model,
        **public_configuration,
    }
    configuration_hash = canonical_payload_hash(configuration)
    actor_slug = re.sub(r"[^a-z0-9]+", "_", f"{kind}_{model}".casefold()).strip("_")
    if len(actor_slug) > 57:
        suffix = hashlib.sha256(actor_slug.encode()).hexdigest()[:12]
        actor_slug = f"{actor_slug[:44].rstrip('_')}_{suffix}"
    return ProviderExecutionIdentity(
        kind=kind,
        model=model,
        actor_id=f"model_{actor_slug}",
        operation=f"{kind}.chat.completions",
        configuration_hash=configuration_hash,
    )


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

    @property
    def execution_identity(self) -> ProviderExecutionIdentity: ...

    def generate(
        self,
        *,
        message: str,
        context_manifest: ContextManifest,
        records: tuple[ProductMemoryRecord, ...],
    ) -> ProviderResult: ...
