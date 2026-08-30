"""Authenticated local-workspace contracts."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from oscillink_agent.domain.events import Digest, EventId


class LocalWorkspacePrincipal(BaseModel):
    """Server-derived identity for one authenticated local workspace request."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    workspace_id: Annotated[str, Field(pattern=r"^ws_[a-z0-9][a-z0-9_-]{0,62}$")]
    actor_id: Annotated[str, Field(pattern=r"^human_[a-z0-9][a-z0-9_-]{0,62}$")]


class WorkspaceAuthStatus(BaseModel):
    """Credential-free local-workspace authentication readiness."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    state: Literal["unavailable", "locked", "ready"]


class WorkspaceStoreVersions(BaseModel):
    """Canonical store versions included in a portable export."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    events: Literal[1]
    memory: Literal[1]
    capabilities: Literal[1]
    proposals: Literal[1] = 1


class WorkspaceExportEntry(BaseModel):
    """One hashed canonical database or immutable artifact."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    path: Annotated[str, Field(min_length=1, max_length=4096)]
    kind: Literal["database", "artifact"]
    byte_count: Annotated[int, Field(ge=0)]
    content_hash: Digest

    @field_validator("path")
    @classmethod
    def require_portable_relative_path(cls, value: str) -> str:
        parts = value.split("/")
        if (
            "\\" in value
            or value.startswith("/")
            or ":" in value
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise ValueError("export entry path must be portable and relative")
        return value

    @model_validator(mode="after")
    def require_kind_specific_path(self) -> "WorkspaceExportEntry":
        database_paths = {
            "databases/events.sqlite3",
            "databases/memory.sqlite3",
            "databases/capabilities.sqlite3",
        }
        if self.kind == "database" and self.path not in database_paths:
            raise ValueError("database export entry path is not recognized")
        if self.kind == "artifact":
            parts = self.path.split("/")
            hexadecimal = "".join(parts[1:]) if len(parts) == 3 else ""
            if (
                len(parts) != 3
                or parts[0] != "artifacts"
                or len(parts[1]) != 2
                or len(parts[2]) != 62
                or any(character not in "0123456789abcdef" for character in hexadecimal)
            ):
                raise ValueError("artifact export entry path is not content addressed")
        return self


class WorkspaceExportManifest(BaseModel):
    """Complete integrity manifest for one minimal canonical workspace export."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    store_versions: WorkspaceStoreVersions
    entries: tuple[WorkspaceExportEntry, ...]

    @model_validator(mode="after")
    def require_unique_entry_paths(self) -> "WorkspaceExportManifest":
        paths = tuple(entry.path for entry in self.entries)
        if len(paths) != len(set(paths)):
            raise ValueError("export manifest entry paths must be unique")
        return self


class WorkspaceExportRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    request_id: EventId


class WorkspaceExportResponse(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    export_id: Annotated[str, Field(pattern=r"^exp_[0-9A-HJKMNP-TV-Z]{26}$")]
    manifest: WorkspaceExportManifest


class WorkspaceRestoreRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1]
    export_id: Annotated[str, Field(pattern=r"^exp_[0-9A-HJKMNP-TV-Z]{26}$")]


class WorkspaceRestoreResponse(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: Literal[1] = 1
    state: Literal["restored"] = "restored"
    export_id: Annotated[str, Field(pattern=r"^exp_[0-9A-HJKMNP-TV-Z]{26}$")]
    manifest: WorkspaceExportManifest
