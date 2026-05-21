"""`science project artifacts port-validate-sidecar` helper."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _write_legacy_sidecar(project: Path) -> None:
    project.joinpath("validate.local.sh").write_text(
        """
legacy_pre() {
  echo "pre body"
}

legacy_extra() {
  WARN "extra warning"
}

register_validation_hook pre_validation legacy_pre
register_validation_hook extra_checks legacy_extra
""".lstrip(),
        encoding="utf-8",
    )


def test_port_validate_sidecar_writes_draft_with_hook_skeletons(tmp_path: Path) -> None:
    _write_legacy_sidecar(tmp_path)

    result = CliRunner().invoke(
        main,
        [
            "project",
            "artifacts",
            "port-validate-sidecar",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    draft = tmp_path / "validate_local.py.draft"
    assert draft.is_file()
    text = draft.read_text(encoding="utf-8")
    compile(text, str(draft), "exec")
    assert "from science_tool.validate import Result, Severity, hook" in text
    assert '@hook("pre_validation")' in text
    assert '@hook("extra_checks")' in text
    assert "def legacy_pre(ctx):" in text
    assert "def legacy_extra(ctx):" in text
    assert 'echo "pre body"' in text
    assert 'WARN "extra warning"' in text
    assert "return []" in text
    assert "validate_local.py.draft" in result.output


def test_port_validate_sidecar_refuses_existing_validate_local_without_force(tmp_path: Path) -> None:
    _write_legacy_sidecar(tmp_path)
    tmp_path.joinpath("validate_local.py").write_text("# existing\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        [
            "project",
            "artifacts",
            "port-validate-sidecar",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "validate_local.py already exists" in result.output
    assert not tmp_path.joinpath("validate_local.py.draft").exists()


def test_port_validate_sidecar_force_overwrites_validate_local(tmp_path: Path) -> None:
    _write_legacy_sidecar(tmp_path)
    target = tmp_path / "validate_local.py"
    target.write_text("# existing\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        [
            "project",
            "artifacts",
            "port-validate-sidecar",
            "--project-root",
            str(tmp_path),
            "--force",
        ],
    )

    assert result.exit_code == 0, result.output
    text = target.read_text(encoding="utf-8")
    assert "# existing" not in text
    assert '@hook("pre_validation")' in text
    assert not tmp_path.joinpath("validate_local.py.draft").exists()
    assert "validate_local.py" in result.output


def test_port_validate_sidecar_fails_when_no_registrations_found(tmp_path: Path) -> None:
    tmp_path.joinpath("validate.local.sh").write_text("echo no hooks\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        [
            "project",
            "artifacts",
            "port-validate-sidecar",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "no register_validation_hook calls found" in result.output


def test_port_validate_sidecar_fails_when_legacy_sidecar_missing(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        main,
        [
            "project",
            "artifacts",
            "port-validate-sidecar",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "validate.local.sh not found" in result.output


def test_port_validate_sidecar_help_is_registered() -> None:
    result = CliRunner().invoke(main, ["project", "artifacts", "port-validate-sidecar", "--help"])

    assert result.exit_code == 0, result.output
    assert "Best-effort skeleton generator" in result.output
    assert "--project-root" in result.output
    assert "--force" in result.output
