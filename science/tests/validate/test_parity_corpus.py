from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path

from science_tool.validate import Severity
from science_tool.validate.checks import CANONICAL_CHECK_MODULES, clear_checks_for_tests
from science_tool.validate.runner import run

FIXTURES = Path(__file__).parent / "fixtures"
COMBINED_PROJECT = FIXTURES / "_combined"
CHECK_MODULES = CANONICAL_CHECK_MODULES


def _ensure_canonical_checks() -> None:
    clear_checks_for_tests()
    for module_name in CHECK_MODULES:
        importlib.reload(importlib.import_module(f"science_tool.validate.checks.{module_name}"))


def test_combined_fixture_emits_intended_warn_and_error() -> None:
    _ensure_canonical_checks()

    result = run(COMBINED_PROJECT, strict=False, verbose=False)
    messages = [item.message for item in result.results]

    assert result.warnings >= 1
    assert result.errors >= 1
    # Two intentional markers: doc/overview.md and entities/reports/0001-overview.md.
    # The entities/ one was historically missed until the scanners learned the v3
    # entities/ root; both are now correctly counted.
    assert any(message.startswith("2 [UNVERIFIED] marker(s) found in documents; examples: ") for message in messages)
    assert (
        "Unknown project namespace 'unknown-project' in ref 'unknown-project:question:q01'. "
        "Add it to science.yaml peers: or use a local ref."
    ) in messages
    assert any(item.severity == Severity.WARN.value for item in result.results)
    assert any(item.severity == Severity.ERROR.value for item in result.results)


def test_isolated_copy_excludes_sidecars_and_is_independent(
    isolated_copy: Callable[[Path], Path],
) -> None:
    copied = isolated_copy(COMBINED_PROJECT)
    second_copy = isolated_copy(COMBINED_PROJECT)

    assert copied != COMBINED_PROJECT
    assert second_copy != COMBINED_PROJECT
    assert second_copy != copied
    assert copied.joinpath("science.yaml").is_file()
    assert second_copy.joinpath("science.yaml").is_file()
    assert copied.joinpath("doc", "overview.md").is_file()
    assert not copied.joinpath("validate.local.sh").exists()
    assert not copied.joinpath("validate_local.py").exists()

    copied_manifest = copied / "science.yaml"
    original_manifest = COMBINED_PROJECT / "science.yaml"
    original_text = original_manifest.read_text(encoding="utf-8")
    copied_manifest.write_text("name: mutated-copy\n", encoding="utf-8")

    assert original_manifest.read_text(encoding="utf-8") == original_text
