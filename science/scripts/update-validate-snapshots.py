#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.validate.checks import clear_checks_for_tests
from science_tool.validate.runner import clear_hooks_for_tests

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "validate" / "fixtures" / "_combined"
SNAPSHOTS = ROOT / "tests" / "validate" / "snapshots"
SNAPSHOT_TERMINAL_WIDTH = 240
CHECK_MODULES = (
    "tooling",
    "manifest",
    "directory_structure",
    "code_files",
    "research_scope",
    "document_structure",
    "hypotheses",
    "references",
    "papers",
    "unresolved_markers",
    "gap_analysis",
    "research_plan",
    "discussions",
    "prereg",
    "hypothesis_comparisons",
    "bias_audits",
    "notes",
    "graph",
    "tasks",
    "id_prefixes",
    "cross_references",
    "variant_identity",
    "genesets",
    "dataset_influence",
    "prose_lints",
    "annotations",
)


def main_script() -> int:
    if Path.cwd().resolve() != ROOT:
        print(f"Run from repository root: {ROOT}", file=sys.stderr)
        return 2

    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    (SNAPSHOTS / "text_default.txt").write_text(_validate_output(), encoding="utf-8")
    (SNAPSHOTS / "json_default.json").write_text(
        _validate_output("--format", "json"),
        encoding="utf-8",
    )
    return 0


def _ensure_canonical_checks() -> None:
    clear_checks_for_tests()
    for module_name in CHECK_MODULES:
        importlib.reload(importlib.import_module(f"science_tool.validate.checks.{module_name}"))


def _validate_output(*args: str) -> str:
    clear_hooks_for_tests()
    _ensure_canonical_checks()
    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(FIXTURE), *args],
        env={"COLUMNS": str(SNAPSHOT_TERMINAL_WIDTH)},
        terminal_width=SNAPSHOT_TERMINAL_WIDTH,
    )
    clear_hooks_for_tests()
    clear_checks_for_tests()

    if result.exit_code != 1:
        print(result.output, file=sys.stderr)
        raise SystemExit(f"science validate exited {result.exit_code}, expected 1")
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main_script())
