"""Non-secret provider selection from application configuration."""

from collections.abc import Mapping

from oscillink_agent.providers.base import ChatProvider
from oscillink_agent.providers.fake import DeterministicFakeProvider
from oscillink_agent.providers.openai_compatible import (
    OpenAICompatibleProvider,
    ProviderConfigurationError,
)


def build_chat_provider(values: Mapping[str, str]) -> ChatProvider:
    """Build a provider from explicit values while keeping fake as the safe default."""

    provider_kind = values.get("OSCILLINK_CHAT_PROVIDER", "fake").strip().casefold()
    if provider_kind == "fake":
        return DeterministicFakeProvider()
    if provider_kind not in {"ollama", "openai_compatible"}:
        raise ProviderConfigurationError("unsupported OSCILLINK_CHAT_PROVIDER")

    if provider_kind == "ollama":
        base_url = values.get(
            "OSCILLINK_CHAT_BASE_URL", "http://127.0.0.1:11434/v1"
        )
        model = values.get("OSCILLINK_CHAT_MODEL", "qwen3:14b")
    else:
        base_url = values.get("OSCILLINK_CHAT_BASE_URL", "")
        model = values.get("OSCILLINK_CHAT_MODEL", "")
        if not base_url or not model:
            raise ProviderConfigurationError(
                "openai_compatible requires OSCILLINK_CHAT_BASE_URL and OSCILLINK_CHAT_MODEL"
            )
    timeout_value = values.get("OSCILLINK_CHAT_TIMEOUT_SECONDS", "30")
    try:
        timeout_seconds = float(timeout_value)
    except ValueError as error:
        raise ProviderConfigurationError(
            "OSCILLINK_CHAT_TIMEOUT_SECONDS must be numeric"
        ) from error
    api_key = values.get("OSCILLINK_CHAT_API_KEY") or None
    return OpenAICompatibleProvider(
        base_url=base_url,
        model=model,
        timeout_seconds=timeout_seconds,
        api_key=api_key,
    )
