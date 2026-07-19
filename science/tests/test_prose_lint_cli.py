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


def test_lint_uses_project_exclude_paths(tmp_path):
    root = _write_project(
        tmp_path,
        science_yaml=(
            "name: demo\n"
            "prose_lint:\n"
            "  exclude_paths:\n"
            "    - 'doc/plans/historical/**'\n"
        ),
    )
    (root / "doc" / "plans" / "historical").mkdir(parents=True)
    (root / "doc" / "plans" / "historical" / "old.md").write_text(
        "# Old\n\nUnanchored 47% historical note.\n"
    )
    (root / "doc" / "active.md").write_text("# Active\n\nUnanchored 48% active note.\n")
    runner = CliRunner()
    result = runner.invoke(
        prose_group, ["lint", "--root", str(root), "--format", "json"]
    )
    payload = json.loads(result.output)
    assert payload["counts"]["numeric-anchor"] == 1
    assert payload["hits"][0]["file"] == "doc/active.md"


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
    (root / "doc" / "a.md").write_text("# A\n\nThis cites h0007, H0007, h07, and H07.\n")

    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "short-form-ids", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["counts"].get("short-form-ids", 0) == 0


def test_additional_anchor_patterns_reach_numeric_anchor(tmp_path):
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprose_lint:\n  anchor_patterns: ['task:']\n"
        "  additional_anchor_patterns: ['paper:']\n")
    (tmp_path / "entities").mkdir()
    (tmp_path / "entities" / "e.md").write_text(
        "---\nkind: report\n---\n\nGrounded via paper:Foo2024 the value 7.94 holds.\n")
    result = CliRunner().invoke(
        prose_group,
        ["lint", "--root", str(tmp_path), "--format", "json", "--check", "numeric-anchor"],
    )
    payload = json.loads(result.output)
    # `paper:` is only reachable because it was *additional*, not in anchor_patterns
    assert "numeric-anchor" not in payload["counts"]


def _write_verified_numeric_project(tmp_path: Path, *, science_yaml: str = "name: demo\n") -> Path:
    """A project with one bound, fully-`verified` numeric claim.

    `score.json` -> {"v": 0.978}; doc/a.md binds **0.978**[^v1] to it via
    `numeric_claims`. No mismatch, no error -- `run_numeric_verification`
    reports a single `verified` outcome and emits no LintIssue (verified
    outcomes are silent, coverage-only).
    """
    root = _write_project(tmp_path, science_yaml=science_yaml)
    (root / "score.json").write_text('{"v": 0.978}')
    (root / "doc" / "a.md").write_text(
        "---\n"
        "numeric_claims:\n"
        "  v1:\n"
        "    artifact: score.json\n"
        "    locator: {pointer: /v}\n"
        "---\n\n"
        "# A\n\n"
        "Accuracy on the holdout set was **0.978**[^v1] overall.\n"
    )
    return root


def _write_mismatch_numeric_project(tmp_path: Path) -> Path:
    """A project whose bound claim value disagrees with the artifact (`mismatch`)."""
    root = _write_project(tmp_path)
    (root / "score.json").write_text('{"v": 42}')
    (root / "doc" / "a.md").write_text(
        "---\n"
        "numeric_claims:\n"
        "  m1:\n"
        "    artifact: score.json\n"
        "    locator: {pointer: /v}\n"
        "---\n\n"
        "# A\n\n"
        "The reported value was **99**[^m1] units.\n"
    )
    return root


def test_lint_renders_numeric_verification_coverage_on_all_clean_run(tmp_path):
    # A fully-verified fixture produces zero hits (verified is silent) -- the
    # coverage summary is the *only* signal that numeric-verification ran at
    # all, so it must print even though `_render_table` would otherwise take
    # the bare "no issues found" early return.
    root = _write_verified_numeric_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "numeric-verification"],
    )
    assert result.exit_code == 0
    assert "no issues found" not in result.output
    assert "numeric-verification" in result.output
    assert "1 verified" in result.output


def test_lint_numeric_verification_mismatch_strict_exits_nonzero(tmp_path):
    root = _write_mismatch_numeric_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "numeric-verification", "--strict"],
    )
    assert result.exit_code == 1


def test_lint_json_output_includes_coverage(tmp_path):
    root = _write_verified_numeric_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "numeric-verification", "--format", "json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["coverage"]["numeric-verification"] == {
        "verified": 1,
        "unverifiable": 0,
        "mismatch": 0,
        "error": 0,
    }


def test_lint_json_output_includes_empty_coverage_when_check_not_selected(tmp_path):
    root = _write_project(tmp_path)
    (root / "doc" / "a.md").write_text("# A\n\nBrunton 2022 showed it.\n")
    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "bare-author-year", "--format", "json"],
    )
    payload = json.loads(result.output)
    assert payload["coverage"] == {}


def test_lint_selecting_numeric_anchor_couples_in_numeric_verification_coverage(tmp_path):
    # Selecting only `numeric-anchor` must still couple in
    # `numeric-verification` (an atomic pair, see `couple_checks`), so the
    # bound claim is verified and its coverage tally is reported.
    root = _write_verified_numeric_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "numeric-anchor", "--format", "json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["coverage"]["numeric-verification"]["verified"] == 1


def test_lint_forwards_max_json_bytes_config_cap_to_verification_runner(tmp_path):
    # `score.json` is 12 bytes ('{"v": 0.978}'); a `max_json_bytes: 10` cap in
    # science.yaml must make the read fail closed as an over-cap `error`
    # instead of `verified` -- proving the config knob reaches `scan_root`
    # through the CLI rather than being dead configuration.
    root = _write_verified_numeric_project(
        tmp_path,
        science_yaml="name: demo\nprose_lint:\n  max_json_bytes: 10\n",
    )
    runner = CliRunner()
    result = runner.invoke(
        prose_group,
        ["lint", "--root", str(root), "--check", "numeric-verification", "--format", "json"],
    )
    payload = json.loads(result.output)
    assert payload["coverage"]["numeric-verification"] == {
        "verified": 0,
        "unverifiable": 0,
        "mismatch": 0,
        "error": 1,
    }
