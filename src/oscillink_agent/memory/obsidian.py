"""Read-only, deterministic indexing for curated Obsidian Markdown."""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

import rfc8785
from pydantic import Field

from oscillink_agent.domain.events import Digest, FrozenModel

DocumentId = Annotated[str, Field(pattern=r"^doc_[0-9A-HJKMNP-TV-Z]{26}$")]
ColorToken = Annotated[str, Field(pattern=r"^#[0-9a-f]{6}$")]
MAX_NOTE_BYTES = 2 * 1024 * 1024
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_EXCLUDED_DIRECTORY_NAMES = frozenset({".git", ".obsidian", "00 Inbox", "99 Templates"})
_NAVIGATION_TYPES = frozenset(
    {
        "area-index",
        "archive-index",
        "dashboard",
        "journal-index",
        "note-index",
        "project-index",
    }
)
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_HEADING = re.compile(r"(?m)^#\s+(.+?)\s*$")
_FRONTMATTER_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]{0,63}):(?:[ \t]*(.*))?$")


class MemoryCategory(StrEnum):
    """Primary organizational category used by the Memory Lattice."""

    RESEARCH = "research"
    TOOLING = "tooling"
    PROJECT = "project"
    EXPERIMENT = "experiment"
    GOVERNANCE = "governance"
    REFERENCE = "reference"
    NOTE = "note"


class MemoryDomain(StrEnum):
    """Multi-label subject domains independent of a node's primary category."""

    AI_ML = "ai_ml"
    RF_EM = "rf_em"
    SCIENCE = "science"
    MATHEMATICS = "mathematics"
    ENGINEERING = "engineering"
    SOFTWARE = "software"
    BUSINESS = "business"
    GENERAL = "general"


class IndexIssueCode(StrEnum):
    """Bounded failure vocabulary for notes omitted from an index snapshot."""

    INVALID_UTF8 = "invalid_utf8"
    INVALID_FRONTMATTER = "invalid_frontmatter"
    UNSUPPORTED_TYPE = "unsupported_type"
    UNSUPPORTED_CATEGORY = "unsupported_category"
    UNSUPPORTED_DOMAIN = "unsupported_domain"
    TOO_LARGE = "too_large"
    UNSAFE_PATH = "unsafe_path"
    IO_ERROR = "io_error"


class CategoryLegendEntry(FrozenModel):
    """Stable text, color, and symbol treatment for one category."""

    category: MemoryCategory
    label: str
    color: ColorToken
    symbol: str


class IndexedObsidianNote(FrozenModel):
    """Derived metadata for one curated, typed Obsidian note."""

    id: DocumentId
    source_path: str
    title: str
    content: str
    frontmatter_type: str
    source_status: str | None
    category: MemoryCategory
    domains: tuple[MemoryDomain, ...]
    topics: tuple[str, ...]
    wikilinks: tuple[str, ...]
    classification_basis: tuple[str, ...]
    content_hash: Digest


class IndexIssue(FrozenModel):
    """Sanitized explanation for a source record omitted from the index."""

    source_path: str
    code: IndexIssueCode
    message: Annotated[str, Field(min_length=1, max_length=256)]


class ReviewedObsidianIndex(FrozenModel):
    """Rebuildable snapshot of curated Markdown metadata."""

    schema_version: Literal[1] = 1
    source_kind: Literal["obsidian_curated_markdown"] = "obsidian_curated_markdown"
    vault_name: str
    notes: tuple[IndexedObsidianNote, ...]
    issues: tuple[IndexIssue, ...]
    category_legend: tuple[CategoryLegendEntry, ...]
    index_hash: Digest


CATEGORY_LEGEND = (
    CategoryLegendEntry(
        category=MemoryCategory.RESEARCH,
        label="Research",
        color="#36f1cd",
        symbol="R",
    ),
    CategoryLegendEntry(
        category=MemoryCategory.TOOLING,
        label="Tooling",
        color="#8a7dff",
        symbol="T",
    ),
    CategoryLegendEntry(
        category=MemoryCategory.PROJECT,
        label="Projects",
        color="#ff4fd8",
        symbol="P",
    ),
    CategoryLegendEntry(
        category=MemoryCategory.EXPERIMENT,
        label="Experiments",
        color="#ffb84d",
        symbol="X",
    ),
    CategoryLegendEntry(
        category=MemoryCategory.GOVERNANCE,
        label="Governance",
        color="#5ea8ff",
        symbol="G",
    ),
    CategoryLegendEntry(
        category=MemoryCategory.REFERENCE,
        label="Reference",
        color="#93a4ad",
        symbol="L",
    ),
    CategoryLegendEntry(
        category=MemoryCategory.NOTE,
        label="Notes",
        color="#7ee787",
        symbol="N",
    ),
)

_TYPE_CATEGORIES = {
    "archive": MemoryCategory.REFERENCE,
    "experiment": MemoryCategory.EXPERIMENT,
    "journal": MemoryCategory.NOTE,
    "note": MemoryCategory.NOTE,
    "policy": MemoryCategory.GOVERNANCE,
    "procedure": MemoryCategory.TOOLING,
    "project": MemoryCategory.PROJECT,
    "research-note": MemoryCategory.RESEARCH,
    "system": MemoryCategory.GOVERNANCE,
    "tool": MemoryCategory.TOOLING,
    "tooling": MemoryCategory.TOOLING,
}

_DOMAIN_ALIASES = {
    "ai": MemoryDomain.AI_ML,
    "ai/ml": MemoryDomain.AI_ML,
    "ai_ml": MemoryDomain.AI_ML,
    "artificial intelligence": MemoryDomain.AI_ML,
    "business": MemoryDomain.BUSINESS,
    "engineering": MemoryDomain.ENGINEERING,
    "general": MemoryDomain.GENERAL,
    "math": MemoryDomain.MATHEMATICS,
    "mathematics": MemoryDomain.MATHEMATICS,
    "rf": MemoryDomain.RF_EM,
    "rf/em": MemoryDomain.RF_EM,
    "rf_em": MemoryDomain.RF_EM,
    "science": MemoryDomain.SCIENCE,
    "software": MemoryDomain.SOFTWARE,
}

_DOMAIN_PATTERNS = (
    (
        MemoryDomain.AI_ML,
        re.compile(
            r"\b(?:ai|artificial intelligence|machine learning|agent|llm|neural|"
            r"world models?|physicsnemo)\b",
            re.IGNORECASE,
        ),
    ),
    (
        MemoryDomain.RF_EM,
        re.compile(
            r"\b(?:rf|radio frequency|electromagnetic|spectrum|wireless|antenna|"
            r"propagation)\b",
            re.IGNORECASE,
        ),
    ),
    (
        MemoryDomain.SCIENCE,
        re.compile(r"\b(?:science|physics|chemistry|biology|scientific)\b", re.IGNORECASE),
    ),
    (
        MemoryDomain.MATHEMATICS,
        re.compile(
            r"\b(?:math|mathematics|geometry|algebra|calculus|statistics|probability)\b",
            re.IGNORECASE,
        ),
    ),
    (
        MemoryDomain.ENGINEERING,
        re.compile(r"\b(?:engineering|hardware|systems design)\b", re.IGNORECASE),
    ),
    (
        MemoryDomain.SOFTWARE,
        re.compile(
            r"\b(?:software|python|typescript|react|api|database|sqlite|programming)\b",
            re.IGNORECASE,
        ),
    ),
    (
        MemoryDomain.BUSINESS,
        re.compile(
            r"\b(?:business|commercial|market|customer|revenue|company|product)\b",
            re.IGNORECASE,
        ),
    ),
)


class FrontmatterError(ValueError):
    """Raised when bounded frontmatter cannot be interpreted safely."""


class NoteIndexError(ValueError):
    """Internal typed failure converted to a sanitized public issue."""

    def __init__(self, code: IndexIssueCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    if len(value) > 4_096:
        raise FrontmatterError("frontmatter scalar exceeds 4096 characters")
    return value


def _parse_inline_list(value: str) -> tuple[str, ...]:
    inner = value[1:-1].strip()
    if not inner:
        return ()
    items = next(csv.reader([inner], skipinitialspace=True))
    return tuple(_clean_scalar(item) for item in items if _clean_scalar(item))


def _parse_frontmatter(text: str) -> tuple[dict[str, str | tuple[str, ...]], str] | None:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        closing = lines.index("---", 1, min(len(lines), 202))
    except ValueError as error:
        raise FrontmatterError("frontmatter closing delimiter not found") from error

    metadata: dict[str, str | tuple[str, ...]] = {}
    index = 1
    while index < closing:
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _FRONTMATTER_KEY.fullmatch(line)
        if match is None:
            raise FrontmatterError(f"unsupported frontmatter line {index}")
        key = match.group(1).casefold()
        if key in metadata:
            raise FrontmatterError(f"duplicate frontmatter key: {key}")
        raw_value = match.group(2) or ""
        if raw_value.strip():
            value = _clean_scalar(raw_value)
            metadata[key] = (
                _parse_inline_list(value)
                if value.startswith("[") and value.endswith("]")
                else value
            )
            continue

        items: list[str] = []
        while index < closing:
            item_match = re.fullmatch(r"[ \t]+-[ \t]+(.+)", lines[index])
            if item_match is None:
                break
            item = _clean_scalar(item_match.group(1))
            if item:
                items.append(item)
            index += 1
        metadata[key] = tuple(items) if items else ""

    body = "\n".join(lines[closing + 1 :])
    return metadata, body


def _stable_document_id(source_path: str) -> str:
    normalized = unicodedata.normalize("NFC", source_path).casefold().encode("utf-8")
    value = int.from_bytes(hashlib.sha256(normalized).digest(), "big") >> 126
    encoded = ""
    for _ in range(26):
        encoded = _CROCKFORD[value & 31] + encoded
        value >>= 5
    return "doc_" + encoded


def _as_values(value: str | tuple[str, ...] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    return (value,) if value else ()


def _classify_domains(
    title: str,
    metadata: dict[str, str | tuple[str, ...]],
) -> tuple[MemoryDomain, ...]:
    explicit_domains = _as_values(metadata.get("domains"))
    if explicit_domains:
        selected: set[MemoryDomain] = set()
        for value in explicit_domains:
            domain = _DOMAIN_ALIASES.get(value.casefold())
            if domain is None:
                raise NoteIndexError(
                    IndexIssueCode.UNSUPPORTED_DOMAIN,
                    f"unsupported domain label: {value}",
                )
            selected.add(domain)
        return tuple(domain for domain in MemoryDomain if domain in selected)

    evidence = " ".join(
        (
            title,
            *_as_values(metadata.get("area")),
            *_as_values(metadata.get("topics")),
            *_as_values(metadata.get("domains")),
            *_as_values(metadata.get("tags")),
        )
    )
    domains = tuple(domain for domain, pattern in _DOMAIN_PATTERNS if pattern.search(evidence))
    return domains or (MemoryDomain.GENERAL,)


def _extract_title(body: str, source_path: str) -> str:
    match = _HEADING.search(body)
    return match.group(1).strip() if match is not None else Path(source_path).stem


def _extract_wikilinks(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(match.group(1).strip() for match in _WIKILINK.finditer(text)))


def _build_note(path: Path, root: Path) -> IndexedObsidianNote | None:
    if path.is_symlink():
        raise NoteIndexError(IndexIssueCode.UNSAFE_PATH, "symbolic-link sources are not indexed")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise NoteIndexError(
            IndexIssueCode.IO_ERROR,
            "source path could not be resolved",
        ) from error
    if not resolved.is_relative_to(root):
        raise NoteIndexError(IndexIssueCode.UNSAFE_PATH, "source resolves outside the vault")
    try:
        if path.stat().st_size > MAX_NOTE_BYTES:
            raise NoteIndexError(IndexIssueCode.TOO_LARGE, "source exceeds the note byte limit")
        raw = path.read_bytes()
    except NoteIndexError:
        raise
    except OSError as error:
        raise NoteIndexError(IndexIssueCode.IO_ERROR, "source could not be read") from error

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise NoteIndexError(IndexIssueCode.INVALID_UTF8, "source is not valid UTF-8") from error
    try:
        parsed = _parse_frontmatter(text)
    except FrontmatterError as error:
        raise NoteIndexError(IndexIssueCode.INVALID_FRONTMATTER, str(error)) from error
    if parsed is None:
        return None
    metadata, body = parsed
    frontmatter_type = str(metadata.get("type", "")).casefold()
    if not frontmatter_type or frontmatter_type in _NAVIGATION_TYPES:
        return None
    category = _TYPE_CATEGORIES.get(frontmatter_type)
    if category is None:
        raise NoteIndexError(
            IndexIssueCode.UNSUPPORTED_TYPE,
            f"unsupported frontmatter type: {frontmatter_type}",
        )

    category_value = metadata.get("category")
    if category_value:
        if not isinstance(category_value, str):
            raise NoteIndexError(
                IndexIssueCode.UNSUPPORTED_CATEGORY,
                "category must be one label",
            )
        try:
            category = MemoryCategory(category_value.casefold())
        except ValueError as error:
            raise NoteIndexError(
                IndexIssueCode.UNSUPPORTED_CATEGORY,
                f"unsupported category label: {category_value}",
            ) from error

    source_path = path.relative_to(root).as_posix()
    title = _extract_title(body, source_path)
    topics = _as_values(metadata.get("topics"))
    status_value = metadata.get("status")
    source_status = status_value if isinstance(status_value, str) and status_value else None
    domain_basis = tuple(
        f"metadata:{key}={value}"
        for key in ("area", "topics", "domains", "tags")
        for value in _as_values(metadata.get(key))
    )
    category_basis = (
        f"frontmatter:category={category.value}"
        if category_value
        else f"frontmatter:type={frontmatter_type}"
    )

    return IndexedObsidianNote(
        id=_stable_document_id(source_path),
        source_path=source_path,
        title=title,
        content=text,
        frontmatter_type=frontmatter_type,
        source_status=source_status,
        category=category,
        domains=_classify_domains(title, metadata),
        topics=topics,
        wikilinks=_extract_wikilinks(text),
        classification_basis=(category_basis, *domain_basis),
        content_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
    )


def build_reviewed_obsidian_index(vault_root: Path) -> ReviewedObsidianIndex:
    """Build a deterministic metadata index without modifying the source vault."""
    root = vault_root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)

    notes: list[IndexedObsidianNote] = []
    issues: list[IndexIssue] = []
    for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix().casefold()):
        relative = path.relative_to(root)
        if any(part in _EXCLUDED_DIRECTORY_NAMES for part in relative.parts[:-1]):
            continue
        try:
            note = _build_note(path, root)
        except NoteIndexError as error:
            issues.append(
                IndexIssue(
                    source_path=relative.as_posix(),
                    code=error.code,
                    message=str(error),
                )
            )
            continue
        if note is not None:
            notes.append(note)

    note_tuple = tuple(notes)
    issue_tuple = tuple(issues)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source_kind": "obsidian_curated_markdown",
        "vault_name": root.name,
        "notes": [note.model_dump(mode="json") for note in note_tuple],
        "issues": [issue.model_dump(mode="json") for issue in issue_tuple],
        "category_legend": [entry.model_dump(mode="json") for entry in CATEGORY_LEGEND],
    }
    index_hash = "sha256:" + hashlib.sha256(rfc8785.dumps(payload)).hexdigest()
    return ReviewedObsidianIndex(
        vault_name=root.name,
        notes=note_tuple,
        issues=issue_tuple,
        category_legend=CATEGORY_LEGEND,
        index_hash=index_hash,
    )
