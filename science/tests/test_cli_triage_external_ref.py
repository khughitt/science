from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main

_ENT_REL = "knowledge/sources/local/entities.yaml"


def _write(root: Path, *, layout: int, bib_key: str | None) -> None:
    root.joinpath("science.yaml").write_text(
        f"name: demo\nprofile: research\nprofiles: {{local: local}}\nlayout_version: {layout}\n",
        encoding="utf-8",
    )
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    src.joinpath("entities.yaml").write_text(
        yaml.safe_dump({"entities": [{"canonical_id": "article:Smith2024", "kind": "article", "title": "S"}]}),
        encoding="utf-8",
    )
    if bib_key is not None:
        (root / "papers").mkdir(parents=True, exist_ok=True)
        (root / "papers" / "references.bib").write_text(
            f"@article{{{bib_key},\n  title = {{S}},\n}}\n", encoding="utf-8"
        )


def test_cli_retire_external_refs_apply_v3_drops_backed_row(tmp_path: Path) -> None:
    _write(tmp_path, layout=3, bib_key="Smith2024")
    result = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--retire-external-refs", "--apply"],
    )
    assert result.exit_code == 0, result.output
    assert yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"] == []


def test_cli_retire_external_refs_apply_refused_on_v2(tmp_path: Path) -> None:
    _write(tmp_path, layout=2, bib_key="Smith2024")
    result = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--retire-external-refs", "--apply"],
    )
    assert result.exit_code != 0
    assert "layout_version 2" in result.output
    assert len(yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"]) == 1  # untouched


def test_cli_retire_external_refs_dry_run_v3_does_not_mutate(tmp_path: Path) -> None:
    # Default (no --apply) on a v3 project: previews, does not touch entities.yaml.
    _write(tmp_path, layout=3, bib_key="Smith2024")
    result = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--retire-external-refs"],
    )
    assert result.exit_code == 0, result.output
    # entities.yaml is untouched in dry-run:
    assert len(yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"]) == 1
    # Verified: real dry-run output starts with this prefix:
    assert "PLAN (dry-run)" in result.output
