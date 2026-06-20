from __future__ import annotations

import difflib
import importlib
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.validate.checks import CANONICAL_CHECK_MODULES, clear_checks_for_tests
from science_tool.validate.runner import clear_hooks_for_tests

FIXTURES = Path(__file__).parent / "fixtures"
COMBINED_PROJECT = FIXTURES / "_combined"
SNAPSHOTS = Path(__file__).parent / "snapshots"
SNAPSHOT_TERMINAL_WIDTH = 1000
CHECK_MODULES = CANONICAL_CHECK_MODULES


@pytest.fixture(autouse=True)
def clean_validate_registries() -> Generator[None]:
    clear_checks_for_tests()
    clear_hooks_for_tests()
    yield
    clear_hooks_for_tests()
    clear_checks_for_tests()


def _ensure_canonical_checks() -> None:
    clear_checks_for_tests()
    for module_name in CHECK_MODULES:
        importlib.reload(importlib.import_module(f"science_tool.validate.checks.{module_name}"))


def _validate_output(*args: str) -> str:
    _ensure_canonical_checks()
    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(COMBINED_PROJECT), *args],
        env={"COLUMNS": str(SNAPSHOT_TERMINAL_WIDTH)},
        terminal_width=SNAPSHOT_TERMINAL_WIDTH,
    )

    assert result.exit_code == 1, result.output
    return result.stdout


def _assert_snapshot_matches(snapshot_path: Path, actual: str) -> None:
    actual_bytes = actual.encode("utf-8")
    expected_bytes = snapshot_path.read_bytes()
    if actual_bytes == expected_bytes:
        return

    expected = expected_bytes.decode("utf-8")
    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=str(snapshot_path),
            tofile="actual",
        )
    )
    pytest.fail(f"Snapshot mismatch for {snapshot_path}:\n{diff}")


@pytest.mark.snapshot
@pytest.mark.parametrize(
    ("snapshot_name", "args"),
    [
        ("text_default.txt", ()),
        ("json_default.json", ("--format", "json")),
    ],
)
def test_validate_default_formatter_matches_snapshot(
    snapshot_name: str,
    args: tuple[str, ...],
) -> None:
    actual = _validate_output(*args)

    _assert_snapshot_matches(SNAPSHOTS / snapshot_name, actual)
