from pathlib import Path

from fastapi.routing import APIRoute

from oscillink_agent.api import create_app
from oscillink_agent.chat import runtime as chat_runtime


def _route_module(app_path: str, method: str, *, data_root: Path) -> str:
    application = create_app(data_root=data_root)

    def api_routes(routes: list[object]):
        for candidate in routes:
            if isinstance(candidate, APIRoute):
                yield candidate
            included_router = getattr(candidate, "original_router", None)
            if included_router is not None:
                yield from api_routes(included_router.routes)

    route = next(
        candidate
        for candidate in api_routes(application.routes)
        if candidate.path == app_path and method in candidate.methods
    )
    return route.endpoint.__module__


def test_status_route_is_mounted_from_a_dedicated_router(tmp_path: Path) -> None:
    assert _route_module("/api/v1/status", "GET", data_root=tmp_path / "runtime") == (
        "oscillink_agent.status.routes"
    )


def test_memory_routes_are_mounted_from_a_dedicated_router(tmp_path: Path) -> None:
    assert _route_module("/api/v1/memory/index", "GET", data_root=tmp_path / "runtime") == (
        "oscillink_agent.memory.routes"
    )


def test_artifact_import_route_is_mounted_from_a_dedicated_router(tmp_path: Path) -> None:
    assert _route_module("/api/v1/artifact-imports", "POST", data_root=tmp_path / "runtime") == (
        "oscillink_agent.artifact_imports.routes"
    )


def test_chat_runtime_uses_a_dedicated_approved_retrieval_service() -> None:
    retrieval = getattr(chat_runtime, "retrieve_approved_memory", None)
    assert retrieval is not None
    assert retrieval.__module__ == "oscillink_agent.retrieval.service"


def test_chat_runtime_uses_a_dedicated_context_compiler() -> None:
    compiler = getattr(chat_runtime, "compile_context", None)
    assert compiler is not None
    assert compiler.__module__ == "oscillink_agent.context.compiler"


def test_chat_runtime_uses_a_provider_protocol_and_fake_adapter() -> None:
    provider_protocol = getattr(chat_runtime, "ChatProvider", None)
    fake_provider = getattr(chat_runtime, "DeterministicFakeProvider", None)
    assert provider_protocol is not None
    assert fake_provider is not None
    assert provider_protocol.__module__ == "oscillink_agent.providers.base"
    assert fake_provider.__module__ == "oscillink_agent.providers.fake"


def test_chat_runtime_uses_a_dedicated_run_repository() -> None:
    repository = getattr(chat_runtime, "SQLiteChatRunRepository", None)
    assert repository is not None
    assert repository.__module__ == "oscillink_agent.agent_runtime.repository"


def test_chat_orchestration_lives_in_the_runtime_service() -> None:
    assert chat_runtime.create_chat_message.__module__ == (
        "oscillink_agent.agent_runtime.service"
    )
    assert chat_runtime.inspect_chat_run.__module__ == (
        "oscillink_agent.agent_runtime.service"
    )
