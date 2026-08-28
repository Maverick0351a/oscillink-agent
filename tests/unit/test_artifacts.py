from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def artifact_id(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def artifact_path(root: Path, reference: str) -> Path:
    hexadecimal = reference.removeprefix("sha256:")
    return root / hexadecimal[:2] / hexadecimal[2:]


def test_artifact_store_reads_content_after_restart(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import LocalArtifactStore

    root = tmp_path / "artifacts"
    content = b"governed longitudinal evidence\x00\xff"
    store = LocalArtifactStore(root)

    reference = store.put(content)

    assert reference == artifact_id(content)
    reopened = LocalArtifactStore(root)
    assert reopened.get(reference) == content


def test_artifact_store_detects_corruption_on_read(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import (
        ArtifactCorruptionError,
        LocalArtifactStore,
    )

    root = tmp_path / "artifacts"
    store = LocalArtifactStore(root)
    reference = store.put(b"canonical evidence")
    artifact_path(root, reference).write_bytes(b"substituted evidence")

    try:
        store.get(reference)
    except ArtifactCorruptionError as error:
        assert reference in str(error)
    else:
        raise AssertionError("corrupted artifact was returned without an error")


@pytest.mark.parametrize(
    "reference",
    [
        "../../outside",
        "sha256:../" + "0" * 61,
        "sha256:" + "A" * 64,
        "sha256:" + "0" * 63,
    ],
)
def test_artifact_store_rejects_malformed_references(
    tmp_path: Path,
    reference: str,
) -> None:
    from oscillink_agent.storage.artifacts import (
        InvalidArtifactReferenceError,
        LocalArtifactStore,
    )

    store = LocalArtifactStore(tmp_path / "artifacts")
    with pytest.raises(InvalidArtifactReferenceError):
        store.get(reference)


def test_artifact_store_reports_missing_content(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import (
        ArtifactNotFoundError,
        LocalArtifactStore,
    )

    reference = artifact_id(b"never stored")
    store = LocalArtifactStore(tmp_path / "artifacts")

    with pytest.raises(ArtifactNotFoundError, match=reference):
        store.get(reference)


@pytest.mark.parametrize("content", [bytearray(b"mutable"), type("B", (bytes,), {})(b"x")])
def test_artifact_store_rejects_non_exact_bytes(
    tmp_path: Path,
    content: object,
) -> None:
    from oscillink_agent.storage.artifacts import (
        InvalidArtifactContentError,
        LocalArtifactStore,
    )

    store = LocalArtifactStore(tmp_path / "artifacts")
    with pytest.raises(InvalidArtifactContentError):
        store.put(content)  # type: ignore[arg-type]


def test_artifact_store_cleans_up_failed_atomic_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from oscillink_agent.storage.artifacts import LocalArtifactStore

    root = tmp_path / "artifacts"
    content = b"must never be partially visible"
    reference = artifact_id(content)
    store = LocalArtifactStore(root)

    def fail_publish(_source: object, _target: object) -> None:
        raise OSError("simulated publish failure")

    monkeypatch.setattr(os, "link", fail_publish)
    with pytest.raises(OSError, match="simulated publish failure"):
        store.put(content)

    assert not artifact_path(root, reference).exists()
    assert [path for path in root.rglob("*") if path.is_file()] == []


def test_artifact_store_deduplicates_concurrent_writes(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import LocalArtifactStore

    root = tmp_path / "artifacts"
    content = b"one immutable artifact"
    store = LocalArtifactStore(root)

    with ThreadPoolExecutor(max_workers=8) as executor:
        references = list(executor.map(store.put, [content] * 16))

    assert references == [artifact_id(content)] * 16
    assert [path for path in root.rglob("*") if path.is_file()] == [
        artifact_path(root, artifact_id(content))
    ]


def test_artifact_store_never_overwrites_corrupt_existing_object(
    tmp_path: Path,
) -> None:
    from oscillink_agent.storage.artifacts import (
        ArtifactCorruptionError,
        LocalArtifactStore,
    )

    root = tmp_path / "artifacts"
    content = b"canonical content"
    reference = artifact_id(content)
    target = artifact_path(root, reference)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"corrupt existing bytes")
    store = LocalArtifactStore(root)

    with pytest.raises(ArtifactCorruptionError, match=reference):
        store.put(content)

    assert target.read_bytes() == b"corrupt existing bytes"


def test_artifact_store_rejects_symlink_escape(tmp_path: Path) -> None:
    from oscillink_agent.storage.artifacts import (
        ArtifactPathEscapeError,
        LocalArtifactStore,
    )

    content = b"matching bytes outside configured storage"
    reference = artifact_id(content)
    external = tmp_path / "external.bin"
    external.write_bytes(content)
    root = tmp_path / "artifacts"
    target = artifact_path(root, reference)
    target.parent.mkdir(parents=True)
    try:
        target.symlink_to(external)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")

    store = LocalArtifactStore(root)
    with pytest.raises(ArtifactPathEscapeError, match=reference):
        store.get(reference)
