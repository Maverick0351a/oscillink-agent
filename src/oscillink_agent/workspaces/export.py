"""Minimal hashed workspace export and atomic verified restore."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import closing, suppress
from pathlib import Path

from pydantic import ValidationError

from oscillink_agent.workspaces.contracts import (
    WorkspaceExportEntry,
    WorkspaceExportManifest,
    WorkspaceStoreVersions,
)

_DATABASES = {
    "events": "events.sqlite3",
    "memory": "memory.sqlite3",
    "capabilities": "capabilities.sqlite3",
}
_CURRENT_VERSIONS = WorkspaceStoreVersions(
    events=1,
    memory=1,
    capabilities=1,
    proposals=1,
)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"(?:^|[\s\"'])[A-Za-z]:[\\/]")
_POSIX_ABSOLUTE_PATH = re.compile(
    r"(?:^|[\s\"'])/(?:home|Users|tmp|var|etc|opt|srv|mnt|media|root)/"
)


class WorkspaceExportError(RuntimeError):
    """A canonical workspace could not be exported safely."""


class WorkspaceRestoreError(RuntimeError):
    """A workspace bundle failed validation before atomic replacement."""


def _digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return "sha256:" + digest.hexdigest(), byte_count


def _backup_sqlite(source: Path, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as source_connection, closing(
        sqlite3.connect(destination)
    ) as destination_connection:
        source_connection.backup(destination_connection)
        destination_connection.commit()
        if destination_connection.execute("PRAGMA integrity_check").fetchone() != (
            "ok",
        ):
            raise WorkspaceExportError(f"database failed integrity check: {source.name}")
        version = int(destination_connection.execute("PRAGMA user_version").fetchone()[0])
    if version < 1:
        raise WorkspaceExportError(f"database has no explicit schema version: {source.name}")
    return version


def _reject_absolute_host_paths(database: Path) -> None:
    with closing(sqlite3.connect(database)) as connection:
        for statement in connection.iterdump():
            if _WINDOWS_ABSOLUTE_PATH.search(statement) or _POSIX_ABSOLUTE_PATH.search(
                statement
            ):
                raise WorkspaceExportError(
                    "canonical database contains an absolute host path"
                )


def _artifact_relative_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    parts = relative.split("/")
    if (
        len(parts) != 2
        or len(parts[0]) != 2
        or len(parts[1]) != 62
        or any(character not in "0123456789abcdef" for character in "".join(parts))
    ):
        raise WorkspaceExportError("artifact store contains a non-content-addressed path")
    return f"artifacts/{relative}"


def _publish_directory(staging: Path, destination: Path, *, replace: bool) -> None:
    backup: Path | None = None
    if destination.exists():
        if not replace:
            raise WorkspaceExportError("export destination already exists")
        backup = destination.with_name(
            f".{destination.name}.replace-{uuid.uuid4().hex}"
        )
        os.replace(destination, backup)
    try:
        os.replace(staging, destination)
    except BaseException:
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def export_workspace(
    data_root: Path,
    destination: Path,
    *,
    replace: bool = False,
) -> WorkspaceExportManifest:
    """Export only canonical databases and immutable artifacts with exact hashes."""

    source = data_root.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if destination == source or destination.is_relative_to(source):
        raise WorkspaceExportError("export destination cannot be inside the active workspace")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-",
            dir=destination.parent,
        )
    )
    entries: list[WorkspaceExportEntry] = []
    version_values = _CURRENT_VERSIONS.model_dump()
    try:
        for store_name, filename in _DATABASES.items():
            database = source / filename
            if not database.is_file():
                continue
            exported = staging / "databases" / filename
            version_values[store_name] = _backup_sqlite(database, exported)
            _reject_absolute_host_paths(exported)
            content_hash, byte_count = _digest(exported)
            entries.append(
                WorkspaceExportEntry(
                    path=f"databases/{filename}",
                    kind="database",
                    byte_count=byte_count,
                    content_hash=content_hash,
                )
            )
        artifact_root = source / "artifacts"
        if artifact_root.is_dir():
            for artifact in sorted(artifact_root.glob("*/*")):
                if artifact.is_symlink() or not artifact.is_file():
                    raise WorkspaceExportError("artifact store contains an unsafe entry")
                export_path = _artifact_relative_path(artifact, artifact_root)
                content_hash, byte_count = _digest(artifact)
                expected_hash = "sha256:" + export_path.replace("artifacts/", "").replace(
                    "/", ""
                )
                if content_hash != expected_hash:
                    raise WorkspaceExportError("artifact bytes do not match content address")
                target = staging / Path(export_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(artifact, target)
                entries.append(
                    WorkspaceExportEntry(
                        path=export_path,
                        kind="artifact",
                        byte_count=byte_count,
                        content_hash=content_hash,
                    )
                )
        manifest = WorkspaceExportManifest(
            store_versions=WorkspaceStoreVersions.model_validate(
                version_values,
                strict=True,
            ),
            entries=tuple(entries),
        )
        (staging / "manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
            newline="\n",
        )
        _publish_directory(staging, destination, replace=replace)
        return manifest
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _load_manifest(bundle: Path) -> WorkspaceExportManifest:
    try:
        return WorkspaceExportManifest.model_validate_json(
            (bundle / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, ValidationError, ValueError) as error:
        raise WorkspaceRestoreError("restore manifest is malformed or non-portable") from error


def _validate_bundle(bundle: Path, manifest: WorkspaceExportManifest) -> None:
    expected_paths = {"manifest.json", *(entry.path for entry in manifest.entries)}
    actual_paths = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file()
    }
    if any(path.is_symlink() for path in bundle.rglob("*")):
        raise WorkspaceRestoreError("restore bundle contains a linked entry")
    if actual_paths != expected_paths:
        raise WorkspaceRestoreError("restore bundle file set does not match manifest")
    for entry in manifest.entries:
        source = bundle / Path(entry.path)
        if source.is_symlink() or not source.is_file():
            raise WorkspaceRestoreError("restore entry is unsafe or missing")
        content_hash, byte_count = _digest(source)
        if content_hash != entry.content_hash or byte_count != entry.byte_count:
            raise WorkspaceRestoreError("restore entry hash or length mismatch")


def _validate_staging(staging: Path, manifest: WorkspaceExportManifest) -> None:
    versions = manifest.store_versions.model_dump()
    for store_name, filename in _DATABASES.items():
        database = staging / filename
        if not database.exists():
            continue
        with closing(sqlite3.connect(database)) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise WorkspaceRestoreError("restored database failed integrity check")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != versions[store_name]:
            raise WorkspaceRestoreError("restored database schema version mismatch")
    artifact_root = staging / "artifacts"
    if artifact_root.exists():
        for artifact in artifact_root.glob("*/*"):
            export_path = _artifact_relative_path(artifact, artifact_root)
            expected = "sha256:" + export_path.replace("artifacts/", "").replace("/", "")
            if _digest(artifact)[0] != expected:
                raise WorkspaceRestoreError("restored artifact failed content verification")


def inspect_workspace_export(bundle_root: Path) -> WorkspaceExportManifest:
    """Verify a portable export without mutating an active workspace."""

    bundle = bundle_root.resolve(strict=True)
    manifest = _load_manifest(bundle)
    _validate_bundle(bundle, manifest)
    return manifest


def restore_workspace(
    bundle_root: Path,
    active_data_root: Path,
) -> WorkspaceExportManifest:
    """Verify in isolation, then atomically replace the inactive workspace directory."""

    bundle = bundle_root.resolve(strict=True)
    manifest = inspect_workspace_export(bundle)
    active = active_data_root.resolve(strict=False)
    if active == bundle or active.is_relative_to(bundle) or bundle.is_relative_to(active):
        raise WorkspaceRestoreError("restore source and destination must be separate")
    active.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{active.name}.restore-", dir=active.parent)
    )
    backup: Path | None = None
    try:
        for entry in manifest.entries:
            source = bundle / Path(entry.path)
            if entry.kind == "database":
                destination = staging / Path(entry.path).name
            else:
                destination = staging / Path(entry.path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            if _digest(destination) != (entry.content_hash, entry.byte_count):
                raise WorkspaceRestoreError("staged restore entry failed verification")
        _validate_staging(staging, manifest)
        if active.exists():
            backup = active.with_name(f".{active.name}.rollback-{uuid.uuid4().hex}")
            os.replace(active, backup)
        try:
            os.replace(staging, active)
        except BaseException:
            if backup is not None and backup.exists() and not active.exists():
                os.replace(backup, active)
            raise
        if backup is not None:
            with suppress(OSError):
                shutil.rmtree(backup)
        return manifest
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
