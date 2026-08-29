from __future__ import annotations

from pathlib import Path

import pytest

import oscillink_agent.memory.obsidian as obsidian_index
from oscillink_agent.memory.obsidian import (
    IndexIssueCode,
    MemoryCategory,
    MemoryDomain,
    build_reviewed_obsidian_index,
)


def write_note(vault: Path, relative_path: str, content: str) -> None:
    path = vault / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def test_indexes_curated_notes_with_categories_domains_and_links(tmp_path: Path) -> None:
    write_note(
        tmp_path,
        "20 Projects/Oscillink.md",
        """---
type: project
status: active
area: AI Research
topics:
  - electromagnetic world models
  - machine learning
---
# Oscillink

See [[30 Notes/Research/Field Geometry]].
""",
    )
    write_note(
        tmp_path,
        "30 Notes/Research/Field Geometry.md",
        """---
type: research-note
status: active
topics: [physics, mathematics, geometry]
---
# Field Geometry
""",
    )
    write_note(
        tmp_path,
        "00 Inbox/Unreviewed.md",
        """---
type: note
status: captured
---
# Unreviewed
""",
    )
    write_note(
        tmp_path,
        "99 Templates/Project Template.md",
        """---
type: project
status: proposed
---
# Template
""",
    )
    write_note(tmp_path, "README.md", "# Vault guidance\n")

    index = build_reviewed_obsidian_index(tmp_path)

    assert [note.source_path for note in index.notes] == [
        "20 Projects/Oscillink.md",
        "30 Notes/Research/Field Geometry.md",
    ]
    project, research = index.notes
    assert project.category is MemoryCategory.PROJECT
    assert project.domains == (MemoryDomain.AI_ML, MemoryDomain.RF_EM)
    assert project.wikilinks == ("30 Notes/Research/Field Geometry",)
    assert project.content_hash.startswith("sha256:")
    assert project.id.startswith("doc_")
    assert research.category is MemoryCategory.RESEARCH
    assert research.domains == (MemoryDomain.SCIENCE, MemoryDomain.MATHEMATICS)

    legend = {entry.category: entry for entry in index.category_legend}
    assert legend[MemoryCategory.PROJECT].label == "Projects"
    assert legend[MemoryCategory.PROJECT].color == "#ff4fd8"
    assert legend[MemoryCategory.RESEARCH].label == "Research"
    assert legend[MemoryCategory.EXPERIMENT].label == "Experiments"
    assert legend[MemoryCategory.TOOLING].label == "Tooling"


def test_rebuild_is_deterministic_read_only_and_keeps_identity_across_edits(
    tmp_path: Path,
) -> None:
    relative_path = "30 Notes/Research/Continuity.md"
    write_note(
        tmp_path,
        relative_path,
        """---
type: research-note
status: active
topics: [agent architecture]
---
# Continuity
""",
    )
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    first = build_reviewed_obsidian_index(tmp_path)
    second = build_reviewed_obsidian_index(tmp_path)

    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert first == second
    assert before == after

    original_id = first.notes[0].id
    original_index_hash = first.index_hash
    write_note(
        tmp_path,
        relative_path,
        """---
type: research-note
status: active
topics: [agent architecture]
---
# Continuity

New reviewed detail.
""",
    )
    changed = build_reviewed_obsidian_index(tmp_path)
    assert changed.notes[0].id == original_id
    assert changed.notes[0].content_hash != first.notes[0].content_hash
    assert changed.index_hash != original_index_hash


def test_reports_invalid_typed_records_without_hiding_valid_notes(tmp_path: Path) -> None:
    write_note(
        tmp_path,
        "20 Projects/Valid.md",
        """---
type: project
status: active
---
# Valid
""",
    )
    write_note(
        tmp_path,
        "30 Notes/Bad Frontmatter.md",
        """---
type: note
type: research-note
---
# Duplicate
""",
    )
    write_note(
        tmp_path,
        "30 Notes/Unknown Type.md",
        """---
type: mystery-record
---
# Mystery
""",
    )
    invalid_utf8 = tmp_path / "30 Notes" / "Invalid UTF-8.md"
    invalid_utf8.write_bytes(b"---\ntype: note\n---\n# Invalid\n\xff")

    index = build_reviewed_obsidian_index(tmp_path)

    assert [note.title for note in index.notes] == ["Valid"]
    assert [(issue.source_path, issue.code) for issue in index.issues] == [
        ("30 Notes/Bad Frontmatter.md", IndexIssueCode.INVALID_FRONTMATTER),
        ("30 Notes/Invalid UTF-8.md", IndexIssueCode.INVALID_UTF8),
        ("30 Notes/Unknown Type.md", IndexIssueCode.UNSUPPORTED_TYPE),
    ]


def test_reviewed_category_and_domain_labels_override_automatic_classification(
    tmp_path: Path,
) -> None:
    write_note(
        tmp_path,
        "30 Notes/Research/Bench Trial.md",
        """---
type: research-note
status: active
category: experiment
domains: [science, mathematics]
---
# Bench Trial
""",
    )
    write_note(
        tmp_path,
        "30 Notes/Invalid Category.md",
        """---
type: note
category: unknowable
---
# Invalid Category
""",
    )

    index = build_reviewed_obsidian_index(tmp_path)

    assert len(index.notes) == 1
    note = index.notes[0]
    assert note.category is MemoryCategory.EXPERIMENT
    assert note.domains == (MemoryDomain.SCIENCE, MemoryDomain.MATHEMATICS)
    assert "frontmatter:category=experiment" in note.classification_basis
    assert [(issue.source_path, issue.code) for issue in index.issues] == [
        ("30 Notes/Invalid Category.md", IndexIssueCode.UNSUPPORTED_CATEGORY),
    ]


def test_reports_oversized_typed_source(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_note(
        tmp_path,
        "30 Notes/Oversized.md",
        """---
type: note
---
# Oversized
""",
    )
    monkeypatch.setattr(obsidian_index, "MAX_NOTE_BYTES", 8)

    index = build_reviewed_obsidian_index(tmp_path)

    assert index.notes == ()
    assert [(issue.source_path, issue.code) for issue in index.issues] == [
        ("30 Notes/Oversized.md", IndexIssueCode.TOO_LARGE),
    ]


def test_rejects_symbolic_link_source_that_escapes_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    outside = tmp_path / "outside.md"
    write_note(
        tmp_path,
        "outside.md",
        """---
type: note
---
# Outside
""",
    )
    link = vault / "30 Notes" / "Escape.md"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symlink creation unavailable: {error}")

    index = build_reviewed_obsidian_index(vault)

    assert index.notes == ()
    assert [(issue.source_path, issue.code) for issue in index.issues] == [
        ("30 Notes/Escape.md", IndexIssueCode.UNSAFE_PATH),
    ]
