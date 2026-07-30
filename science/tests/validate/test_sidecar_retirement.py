"""Python validation sidecars are reported, never executed."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

from science_tool.validate.runner import run
from science_tool.validate.runtime import RULE_PYTHON_SIDECAR_REMOVED, RULE_SIDECAR_REMOVED

SENTINEL = "science_sidecar_executed_sentinel"

SIDECAR = f'''
import pathlib
pathlib.Path(__file__).parent.joinpath("{SENTINEL}").write_text("ran")
'''


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: fixture\n", encoding="utf-8")
    return tmp_path


def _run(root: Path):
    return run(root, strict=False, verbose=False)


def test_sidecar_file_yields_exactly_one_retirement_finding(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "validate_local.py").write_text(SIDECAR, encoding="utf-8")

    result = _run(root)

    matching = [f for f in result.results if f.rule_id == RULE_PYTHON_SIDECAR_REMOVED.id]
    assert len(matching) == 1
    assert matching[0].severity == "error"
    assert matching[0].subject.type == "project"


def test_sidecar_is_never_imported_or_executed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "validate_local.py").write_text(SIDECAR, encoding="utf-8")

    _run(root)

    assert "validate_local" not in sys.modules
    assert not (root / SENTINEL).exists()


def test_python_and_legacy_sidecars_are_distinct_rules(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "validate_local.py").write_text(SIDECAR, encoding="utf-8")
    (root / "validate.local.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    result = _run(root)

    rule_ids = {f.rule_id for f in result.results}
    assert RULE_PYTHON_SIDECAR_REMOVED.id in rule_ids
    assert RULE_SIDECAR_REMOVED.id in rule_ids
    assert RULE_PYTHON_SIDECAR_REMOVED.id != RULE_SIDECAR_REMOVED.id


def test_clean_project_has_no_retirement_finding(tmp_path: Path) -> None:
    result = _run(_project(tmp_path))

    assert not [f for f in result.results if f.rule_id == RULE_PYTHON_SIDECAR_REMOVED.id]


def test_hook_api_is_gone() -> None:
    import science_tool.validate as validate_pkg

    assert not hasattr(validate_pkg, "hook")


def test_run_has_no_sidecar_parameter() -> None:
    assert "enable_python_sidecar" not in inspect.signature(run).parameters


def test_cli_emits_valid_json_with_one_retirement_rule(tmp_path: Path) -> None:
    """Design §5.3.1 is about CLI JSON, not run() — the crash was a CLI traceback."""
    import json

    from click.testing import CliRunner

    from science_tool.validate.cli import validate_cmd

    root = _project(tmp_path)
    (root / "validate_local.py").write_text(SIDECAR, encoding="utf-8")
    report = tmp_path / "report.json"

    result = CliRunner().invoke(
        validate_cmd,
        ["--project-root", str(root), "--format", "json", "--output", str(report)],
    )

    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Traceback" not in result.output
    payload = json.loads(report.read_text(encoding="utf-8"))
    rules = [r.get("rule") for r in payload["results"]]
    assert rules.count(RULE_PYTHON_SIDECAR_REMOVED.id) == 1
