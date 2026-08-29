from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
from pathlib import Path

import pytest


def load_verify_module() -> object:
    path = Path(__file__).resolve().parents[2] / "scripts" / "verify.py"
    spec = importlib.util.spec_from_file_location("oscillink_verify", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_review_rejects_untracked_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = load_verify_module()
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "new_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(verify, "ROOT", tmp_path)

    with pytest.raises(SystemExit, match="git add --intent-to-add"):
        verify.require_no_untracked_files()  # type: ignore[attr-defined]


def test_main_runs_locked_frontend_review_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = load_verify_module()
    web_root = tmp_path / "apps" / "web"
    web_root.mkdir(parents=True)
    (web_root / "package.json").write_text("{}\n", encoding="utf-8")
    commands: list[list[str]] = []

    monkeypatch.setattr(verify, "ROOT", tmp_path)
    monkeypatch.setattr(verify, "WEB_ROOT", web_root, raising=False)
    monkeypatch.setattr(
        verify,
        "parse_args",
        lambda: argparse.Namespace(base="HEAD", require_clean=False, skip_sync=True),
    )
    monkeypatch.setattr(
        verify,
        "run",
        lambda command, **_kwargs: commands.append(command) or "",
    )
    monkeypatch.setattr(
        verify,
        "check_repository_invariants",
        lambda _base, *, require_clean: "test-digest",
    )

    verify.main()  # type: ignore[attr-defined]

    npm = "npm.cmd" if os.name == "nt" else "npm"
    assert [npm, "--prefix", "apps/web", "ci"] in commands
    assert [npm, "--prefix", "apps/web", "test"] in commands
    assert [npm, "--prefix", "apps/web", "run", "typecheck"] in commands
    assert [npm, "--prefix", "apps/web", "run", "build"] in commands


def test_git_binary_diff_is_not_scanned_for_line_endings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = load_verify_module()
    binary_path = tmp_path / "logo.png"
    binary_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00binary\r\nbytes")

    monkeypatch.setattr(verify, "ROOT", tmp_path)

    class BinaryDiffResult:
        returncode = 0
        stdout = b"-\t-\tlogo.png\x00"
        stderr = b""

    monkeypatch.setattr(
        verify.subprocess,
        "run",
        lambda *_args, **_kwargs: BinaryDiffResult(),
    )

    assert not verify.git_diff_classifies_as_text(  # type: ignore[attr-defined]
        "HEAD",
        binary_path,
    )
