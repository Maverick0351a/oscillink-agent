"""Run the deterministic public longitudinal evaluation smoke suite."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from oscillink_agent.evaluation.baselines import DeterministicSmokeExecutor
from oscillink_agent.evaluation.runner import load_suite, run_suite

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "evaluations" / "manifests" / "public-smoke.yaml"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace an existing report instead of preserving it.",
    )
    return parser


def _git(command: list[str]) -> str:
    completed = subprocess.run(  # noqa: S603
        ["git", *command],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_report(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError("report already exists; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    revision = _git(["rev-parse", "HEAD"])
    worktree_dirty = bool(_git(["status", "--porcelain", "--untracked-files=normal"]))
    output = args.output or (
        ROOT / "evaluations" / "reports" / f"public-smoke-{revision}.json"
    )
    suite = load_suite(args.manifest.resolve())
    report = run_suite(
        suite,
        DeterministicSmokeExecutor(),
        code_revision=revision,
        worktree_dirty=worktree_dirty,
    )
    _write_report(
        output.resolve(),
        report.model_dump_json(indent=2) + "\n",
        overwrite=args.overwrite,
    )
    print(
        json.dumps(
            {
                "passed": report.passed,
                "report": str(output.resolve()),
                "results": len(report.results),
                "smoke_only": report.smoke_only,
            },
            sort_keys=True,
        )
    )
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
