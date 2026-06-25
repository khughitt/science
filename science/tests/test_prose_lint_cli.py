import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.prose_lint_cli import prose_group


def _write_project(tmp_path: Path, *, science_yaml: str = "name: demo\n") -> Path:
    (tmp_path / "science.yaml").write_text(science_yaml)
    (tmp_path / "doc").mkdir()
    return tmp_path


def test_lint_json_output(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(
        prose_group, ["lint", "--root", str(root), "--format", "json"]
    )
    assert result.exit_code == 0  # warn-level by default doesn't fail
    payload = json.loads(result.output)
    assert payload["counts"]["bare-author-year"] == 1
    assert len(payload["hits"]) == 1
    assert payload["hits"][0]["check"] == "bare-author-year"


def test_lint_table_output(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(prose_group, ["lint", "--root", str(root)])
    assert result.exit_code == 0
    assert "bare-author-year" in result.output
    assert "Brunton 2022" in result.output


def test_lint_filters_by_check(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text(
        "# A\n\nBrunton 2022 showed rho = 0.168.\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "bare-author-year", "--format", "json"],
    )
    payload = json.loads(result.output)
    assert "numeric-anchor" not in payload["counts"]
    assert payload["counts"]["bare-author-year"] == 1


def test_lint_strict_exits_nonzero(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(prose_group, ["lint", "--root", str(root), "--strict"])
    assert result.exit_code == 1


def test_lint_warn_severity_does_not_exit_nonzero_without_strict(tmp_path):
    # Mirrors `science markers scan` behavior: warn issues are reported but
    # don't fail the run unless --strict is set.
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(prose_group, ["lint", "--root", str(root)])
    assert result.exit_code == 0


def test_lint_uses_project_anchor_patterns(tmp_path):
    root = _write_project(
        tmp_path,
        science_yaml=(
            "name: demo\n"
            "prose_lint:\n"
            "  anchor_patterns:\n"
            "    - 'doc/'\n"
        ),
    )
    (root / "doc" / "a.md").write_text(
        "# A\n\nResult rho = 0.168 (see doc/notes/foo.md).\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        prose_group, ["lint", "--root", str(root), "--format", "json"]
    )
    payload = json.loads(result.output)
    assert "numeric-anchor" not in payload["counts"]


def test_lint_uses_short_form_ids_deny_from_config(tmp_path):
    root = _write_project(
        tmp_path,
        science_yaml=(
            "name: demo\n"
            "prose_lint:\n"
            "  short_form_ids_deny:\n"
            "    - 'D1'\n"
            "    - 'H3'\n"
        ),
    )
    (root / "doc" / "a.md").write_text("Cyclin D1 effect; H3 marks chromatin.\n")
    runner = CliRunner()
    result = runner.invoke(
        prose_group, ["lint", "--root", str(root), "--format", "json"]
    )
    payload = json.loads(result.output)
    assert payload["counts"].get("short-form-ids", 0) == 0


def test_lint_resolves_v3_numeric_entity_ids_as_short_forms(tmp_path):
    root = _write_project(tmp_path)
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "entities" / "hypotheses" / "0007-foo.md").write_text(
        "---\n"
        "kind: hypothesis\n"
        "id: hypothesis:0007-foo\n"
        "title: Foo\n"
        "---\n\n"
        "# Foo\n"
    )
    (root / "doc" / "a.md").write_text("# A\n\nThis cites h0007 and H0007.\n")

    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "short-form-ids", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["counts"].get("short-form-ids", 0) == 0
