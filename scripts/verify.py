#!/usr/bin/env python
"""Run Oscillink Agent's deterministic local review gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schemas"
PLAN = ROOT / "docs" / "build-plan.md"
PLAN_MIRROR = (
    ROOT / ".hermes" / "plans" / "2026-08-27_183950-oscillink-agent-local-to-cloud.md"
)
SECURITY_PATTERNS = {
    "hardcoded_secret": re.compile(
        r"(?i)(api_key|secret|password|token|passwd)\s*=\s*['\"][^'\"]{6,}['\"]"
    ),
    "shell_injection": re.compile(r"os\.system\(|subprocess[^\n]*shell\s*=\s*True"),
    "dangerous_exec": re.compile(r"\beval\(|\bexec\("),
    "unsafe_deserialization": re.compile(r"pickle\.loads?\("),
    "sql_interpolation": re.compile(
        r"execute\(f['\"]|\.format\([^\n]*(?:SELECT|INSERT)"
    ),
}


def fail(message: str) -> NoReturn:
    raise SystemExit(f"REVIEW FAILED: {message}")


def run(command: list[str], *, capture: bool = False) -> str:
    print("+", " ".join(command), flush=True)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = ""
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        text=True,
        capture_output=capture,
    )
    if result.returncode:
        if capture:
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
        fail(f"command exited {result.returncode}: {' '.join(command)}")
    return result.stdout if capture else ""


def git_output(*arguments: str) -> str:
    return run(["git", *arguments], capture=True)


def require_no_untracked_files() -> None:
    output = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    untracked = [os.fsdecode(raw) for raw in output.split(b"\0") if raw]
    if untracked:
        preview = ", ".join(untracked[:10])
        if len(untracked) > 10:
            preview += f", ... ({len(untracked)} total)"
        fail(
            "candidate review cannot include untracked files; expose them to Git diff "
            f"with `git add --intent-to-add -- <paths>`: {preview}"
        )


def changed_files(base: str) -> list[Path]:
    output = subprocess.run(
        ["git", "diff", "--name-only", "-z", base, "--"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return [ROOT / raw.decode() for raw in output.split(b"\0") if raw]


def check_repository_invariants(base: str, *, require_clean: bool) -> str:
    run(["git", "rev-parse", "--verify", base], capture=True)
    if require_clean and git_output("status", "--porcelain"):
        fail("stable-range review requires a clean worktree")
    require_no_untracked_files()

    run(["git", "diff", "--check", base, "--"])

    if PLAN.read_bytes() != PLAN_MIRROR.read_bytes():
        fail("docs/build-plan.md and its .hermes plan mirror differ")

    for schema_path in sorted(SCHEMA_ROOT.glob("*.json")):
        json.loads(schema_path.read_text(encoding="utf-8"))
    print("schemas: valid JSON")

    crlf_files = [
        str(path.relative_to(ROOT))
        for path in changed_files(base)
        if path.is_file() and b"\r\n" in path.read_bytes()
    ]
    if crlf_files:
        fail(f"changed files contain CRLF: {crlf_files}")
    print("line endings: LF")

    diff = git_output("diff", "--unified=0", base, "--")
    added_lines = "\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    findings = {
        name: len(pattern.findall(added_lines))
        for name, pattern in SECURITY_PATTERNS.items()
    }
    print("security scan:", json.dumps(findings, sort_keys=True))
    if any(findings.values()):
        fail("added-line security scan found a blocking pattern")

    binary_diff = subprocess.run(
        ["git", "diff", "--binary", base, "--"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    digest = hashlib.sha256(binary_diff).hexdigest()
    print(f"reviewed diff sha256: {digest}")
    return digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="HEAD",
        help="Git base revision for the reviewed range (default: HEAD)",
    )
    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Fail unless the worktree is clean (use for stable post-commit review)",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip uv sync --locked --dev when the environment is already synchronized",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if sys.version_info[:2] != (3, 11):
        fail(f"Python 3.11 required, found {sys.version.split()[0]}")

    if not args.skip_sync:
        run(["uv", "sync", "--locked", "--dev"])
    run([sys.executable, "-m", "pytest", "-q"])
    run([sys.executable, "-m", "ruff", "check", ".", "--no-cache"])
    run([sys.executable, "-m", "mypy", "src", "--cache-dir", ".mypy_cache"])
    digest = check_repository_invariants(args.base, require_clean=args.require_clean)
    print(f"REVIEW PASSED: base={args.base} diff_sha256={digest}")


if __name__ == "__main__":
    main()
