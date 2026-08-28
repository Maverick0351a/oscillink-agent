"""Local content-addressed artifact storage."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path

from oscillink_agent.storage.interfaces import ArtifactStoreError

_ARTIFACT_REFERENCE = re.compile(r"sha256:[0-9a-f]{64}")


class ArtifactCorruptionError(ArtifactStoreError):
    """Artifact bytes do not match their content address."""


class InvalidArtifactReferenceError(ArtifactStoreError):
    """An artifact reference does not match the SHA-256 contract."""


class ArtifactNotFoundError(ArtifactStoreError):
    """No artifact exists for a valid content address."""


class InvalidArtifactContentError(ArtifactStoreError):
    """Artifact ingress requires exact immutable bytes."""


class ArtifactPathEscapeError(ArtifactStoreError):
    """An artifact path traverses a symlink or reparse point."""


class LocalArtifactStore:
    """Store immutable byte artifacts under SHA-256-derived paths."""

    def __init__(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self._root = root.resolve(strict=True)

    def put(self, content: bytes) -> str:
        if type(content) is not bytes:
            raise InvalidArtifactContentError(
                "artifact content must use the built-in bytes type"
            )
        hexadecimal = hashlib.sha256(content).hexdigest()
        target = self._root / hexadecimal[:2] / hexadecimal[2:]
        reference = f"sha256:{hexadecimal}"
        self._reject_path_escape(target.parent, reference)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._reject_path_escape(target.parent, reference)
        self._reject_path_escape(target, reference)
        if target.exists():
            self.get(reference)
            return reference

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{hexadecimal}.",
            suffix=".tmp",
            dir=target.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                self.get(reference)
        finally:
            temporary.unlink(missing_ok=True)
        return reference

    def get(self, reference: str) -> bytes:
        hexadecimal = self._parse_reference(reference)
        target = self._root / hexadecimal[:2] / hexadecimal[2:]
        self._reject_path_escape(target.parent, reference)
        self._reject_path_escape(target, reference)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(target, flags)
        except FileNotFoundError:
            raise ArtifactNotFoundError(f"artifact not found: {reference}") from None
        with os.fdopen(descriptor, "rb") as artifact_file:
            content = artifact_file.read()
        if hashlib.sha256(content).hexdigest() != hexadecimal:
            raise ArtifactCorruptionError(
                f"artifact bytes do not match content address: {reference}"
            )
        return content

    def verify(self, reference: str) -> None:
        self.get(reference)

    def _reject_path_escape(self, path: Path, reference: str) -> None:
        try:
            status = path.lstat()
        except FileNotFoundError:
            return
        file_attributes = getattr(status, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if stat.S_ISLNK(status.st_mode) or bool(file_attributes & reparse_flag):
            raise ArtifactPathEscapeError(
                f"artifact path contains a link or reparse point: {reference}"
            )
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self._root):
            raise ArtifactPathEscapeError(
                f"artifact path escapes configured root: {reference}"
            )

    @staticmethod
    def _parse_reference(reference: str) -> str:
        if type(reference) is not str or _ARTIFACT_REFERENCE.fullmatch(reference) is None:
            raise InvalidArtifactReferenceError(
                "artifact reference must be sha256 followed by 64 lowercase hex digits"
            )
        return reference[7:]
