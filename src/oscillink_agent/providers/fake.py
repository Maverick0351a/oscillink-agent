"""Deterministic provider used to verify governed runtime contracts."""

from oscillink_agent.chat.contracts import ChatProviderProjection
from oscillink_agent.domain.context import ContextManifest
from oscillink_agent.memory.repository import ProductMemoryRecord
from oscillink_agent.providers.base import ProviderResult


class DeterministicFakeProvider:
    """Generate a stable answer without network or model variability."""

    @property
    def projection(self) -> ChatProviderProjection:
        return ChatProviderProjection()

    def generate(
        self,
        *,
        message: str,
        context_manifest: ContextManifest,
        records: tuple[ProductMemoryRecord, ...],
    ) -> ProviderResult:
        del message, context_manifest
        answer = (
            "Grounded in approved memory: "
            + ", ".join(record.title for record in records)
            + "."
            if records
            else "No approved memory was available for this request."
        )
        return ProviderResult(answer=answer)
