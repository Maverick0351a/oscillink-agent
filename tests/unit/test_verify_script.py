from __future__ import annotations

import importlib.util
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
