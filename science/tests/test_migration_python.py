"""Python migration step adapter: loads dotted module, dispatches check/apply/unapply."""

from pathlib import Path

from science_tool.project_artifacts.migrations.python import PythonStepAdapter
from science_tool.project_artifacts.registry_schema import MigrationStep


def _step() -> MigrationStep:
    return MigrationStep.model_validate(
        {
            "id": "fixture",
            "description": "Test fixture step.",
            "impl": {"kind": "python", "module": "_fixtures.migration_add_phase"},
            "touched_paths": ["specs/*.md"],
            "reversible": True,
            "idempotent": True,
        }
    )


def test_python_step_check_apply_check(tmp_path: Path) -> None:
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    (spec_dir / "h01.md").write_text("---\n# missing phase\n---\n", encoding="utf-8")

    adapter = PythonStepAdapter(_step())
    assert adapter.check(tmp_path) is False  # phase missing → action needed
    applied = adapter.apply(tmp_path)
    assert adapter.check(tmp_path) is True  # phase added → satisfied
    adapter.unapply(tmp_path, applied)
    assert adapter.check(tmp_path) is False  # back to needing action
