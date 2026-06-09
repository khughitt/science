# tests/test_cli_triage_curie.py
from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main

_MANIFEST_V2 = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\nontologies:\n  - biology\n"
_MANIFEST_V3 = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\nontologies:\n  - biology\n"


def _project(root: Path, manifest: str) -> None:
    (root / "science.yaml").write_text(manifest, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "terms.yaml").write_text(
        yaml.safe_dump(
            {
                "terms": [
                    {
                        "id": "protein:BCMA",
                        "title": "BCMA",
                        "primary_external_id": {
                            "source": "UniProtKB",
                            "id": "Q02223",
                            "curie": "UniProtKB:Q02223",
                            "provenance": "manual",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_dry_run_lists_curie_migration(tmp_path: Path) -> None:
    _project(tmp_path, _MANIFEST_V3)
    res = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--migrate-curie-refs", "--format", "json"],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["dry_run"] is True
    assert "protein:BCMA" in payload["migrated"]
    # Dry-run wrote nothing.
    assert not (tmp_path / "knowledge" / "sources" / "local" / "external_refs.yaml").exists()


def test_apply_refused_on_v2(tmp_path: Path) -> None:
    _project(tmp_path, _MANIFEST_V2)
    res = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--migrate-curie-refs", "--apply"],
    )
    assert res.exit_code != 0
    assert "layout_version" in res.output


def test_apply_without_bucket_flag_is_usage_error(tmp_path: Path) -> None:
    _project(tmp_path, _MANIFEST_V3)
    res = CliRunner().invoke(main, ["entities", "triage-aggregate", "--project-root", str(tmp_path), "--apply"])
    assert res.exit_code != 0
    assert "--migrate-curie-refs" in res.output
