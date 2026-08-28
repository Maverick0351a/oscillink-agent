from __future__ import annotations

import re

import oscillink_agent


def test_package_exposes_semantic_version() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", oscillink_agent.__version__)
