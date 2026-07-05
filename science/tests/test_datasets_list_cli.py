"""Tests for `science dataset list --origin` filter (Task 7.1)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed_filterable(root: Path) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cand.md").write_text(
        '---\nid: "dataset:cand"\nkind: "dataset"\ntitle: "Cand"\nstatus: "candidate"\n'
        'origin: "external"\ntier: "use-now"\naccess: {level: "public", verified: false}\n---\n',
        encoding="utf-8",
    )
    (d / "acq.md").write_text(
        '---\nid: "dataset:acq"\nkind: "dataset"\ntitle: "Acq"\nstatus: "active"\n'
        'origin: "external"\ntier: "track"\ndatapackage: "r/dp.yaml"\n'
        'access: {level: "controlled", verified: true}\n---\n',
        encoding="utf-8",
    )
    # A derived dataset (no access block) — must NOT appear under --unverified.
    (d / "der.md").write_text(
        '---\nid: "dataset:der"\nkind: "dataset"\ntitle: "Der"\nstatus: "active"\n'
        'origin: "derived"\ntier: "track"\ndatapackage: "r/dp.yaml"\n---\n',
        encoding="utf-8",
    )
    # A non-entity note with frontmatter but type != dataset — must be excluded.
    (d / "note.md").write_text(
        '---\ntitle: "Combined note"\ntype: "note"\n---\nfree text\n',
        encoding="utf-8",
    )


def _list(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "list", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_list_excludes_non_dataset_notes(tmp_path: Path) -> None:
    _seed_filterable(tmp_path)
    res = _list(tmp_path)
    assert res.exit_code == 0
    assert "dataset:cand" in res.output
    assert "Combined note" not in res.output


def test_list_candidate_filter(tmp_path: Path) -> None:
    _seed_filterable(tmp_path)
    res = _list(tmp_path, "--candidate")
    assert "dataset:cand" in res.output
    assert "dataset:acq" not in res.output


def test_list_tier_and_unverified_filters(tmp_path: Path) -> None:
    _seed_filterable(tmp_path)
    assert "dataset:cand" in _list(tmp_path, "--tier", "use-now").output
    assert "dataset:acq" not in _list(tmp_path, "--tier", "use-now").output
    assert "dataset:cand" in _list(tmp_path, "--unverified").output
    assert "dataset:acq" not in _list(tmp_path, "--unverified").output
    # derived rows have no access block; --unverified is external-only
    assert "dataset:der" not in _list(tmp_path, "--unverified").output


def test_list_commons_missing_registry_degrades(tmp_path: Path) -> None:
    _seed_filterable(tmp_path)
    commons = tmp_path / "empty-commons"
    commons.mkdir()
    res = CliRunner().invoke(
        science_cli,
        ["dataset", "list", "--commons"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(commons)},
    )
    assert res.exit_code == 0
    assert "dataset:cand" in res.output  # local rows still shown
    assert "commons" in res.output.lower()  # a notice about commons unavailability


def _seed_two_origins(root: Path) -> None:
    (root / "entities" / "datasets").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "datasets" / "ext.md").write_text(
        '---\nid: "dataset:ext"\nkind: "dataset"\ntitle: "Ext"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n',
        encoding="utf-8",
    )
    (root / "entities" / "datasets" / "der.md").write_text(
        '---\nid: "dataset:der"\nkind: "dataset"\ntitle: "Der"\norigin: "derived"\n'
        'derivation: {workflow: "workflow:w", workflow_run: "workflow-run:r", git_commit: "a", config_snapshot: "c", produced_at: "t", inputs: []}\n'
        'datapackage: "results/w/r/x/datapackage.yaml"\n---\n',
        encoding="utf-8",
    )


def test_dataset_list_origin_filter(tmp_path: Path) -> None:
    _seed_two_origins(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        science_cli,
        ["dataset", "list", "--origin", "external"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0
    assert "dataset:ext" in res.output
    assert "dataset:der" not in res.output

    res2 = runner.invoke(
        science_cli,
        ["dataset", "list", "--origin", "derived"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert "dataset:der" in res2.output
    assert "dataset:ext" not in res2.output


def test_dataset_list_no_filter_shows_all(tmp_path: Path) -> None:
    # ext is public (non-gated) and der is derived (no access block); both are
    # actionable, so a bare `list` shows them by default.
    _seed_two_origins(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        science_cli,
        ["dataset", "list"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )
    assert res.exit_code == 0
    assert "dataset:ext" in res.output
    assert "dataset:der" in res.output


def _seed_gated_mix(root: Path) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pub.md").write_text(
        '---\nid: "dataset:pub"\nkind: "dataset"\ntitle: "Pub"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n', encoding="utf-8")
    (d / "reg.md").write_text(
        '---\nid: "dataset:reg"\nkind: "dataset"\ntitle: "Reg"\norigin: "external"\n'
        'access: {level: "registration", verified: false}\n---\n', encoding="utf-8")
    (d / "ctrl.md").write_text(
        '---\nid: "dataset:ctrl"\nkind: "dataset"\ntitle: "Ctrl"\norigin: "external"\n'
        'access: {level: "controlled", verified: true}\n---\n', encoding="utf-8")


def test_list_hides_gated_by_default(tmp_path: Path) -> None:
    _seed_gated_mix(tmp_path)
    out = _list(tmp_path).output
    assert "dataset:pub" in out          # public is non-gated
    assert "dataset:reg" not in out      # registration is gated
    assert "dataset:ctrl" not in out     # controlled is gated


def test_list_include_gated_shows_gated(tmp_path: Path) -> None:
    _seed_gated_mix(tmp_path)
    out = _list(tmp_path, "--include-gated").output
    assert "dataset:pub" in out
    assert "dataset:reg" in out
    assert "dataset:ctrl" in out


def test_list_explicit_level_overrides_gated_default(tmp_path: Path) -> None:
    _seed_gated_mix(tmp_path)
    out = _list(tmp_path, "--level", "controlled").output
    assert "dataset:ctrl" in out         # naming the gated level surfaces it
    assert "dataset:pub" not in out
