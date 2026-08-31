from __future__ import annotations

import json
import tomllib
from pathlib import Path

import oscillink_agent


def test_release_candidate_versions_are_consistent() -> None:
    root = Path(__file__).resolve().parents[2]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    web = json.loads((root / "apps/web/package.json").read_text(encoding="utf-8"))

    assert oscillink_agent.__version__ == "0.2.0a1"
    assert project["project"]["version"] == oscillink_agent.__version__
    assert web["version"] == "0.2.0-alpha.1"
