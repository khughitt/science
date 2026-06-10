"""Phase 3c: CLI surface for decision promotion + the generated view."""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.decision_log import DecisionSection, render_owner_file

_LOCAL_MANIFEST = (
    "name: t-local\nimports:\n  - core\nstrictness: typed-extension\n"
    "entity_kinds:\n"
    "  - name: decision\n    canonical_prefix: decision\n    layer: layer/local\n"
    "    description: Project-local design decision.\n"
    "relation_kinds: []\n"
)


def _v3_project(tmp_path: Path, rows: list[dict], decisions_md: str) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n",
        encoding="utf-8",
    )
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    # decision is a local registry kind in 3c — declare it so rows load (see Task 5).
    (src / "manifest.yaml").write_text(_LOCAL_MANIFEST, encoding="utf-8")
    (src / "entities.yaml").write_text(yaml.safe_dump({"entities": rows}), encoding="utf-8")
    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "decisions.md").write_text(decisions_md, encoding="utf-8")
    return tmp_path


def test_promote_decisions_apply_promotes_on_v3(tmp_path: Path):
    proj = _v3_project(
        tmp_path,
        [{"canonical_id": "decision:D1", "kind": "decision", "title": "D1. X", "source_path": "core/decisions.md"}],
        "# Decisions\n\n## D1. X (2026-03-31)\n\n**Date**: 2026-03-31\n**Status**: active\n\nWhy.\n",
    )
    res = CliRunner().invoke(
        main,
        [
            "entities",
            "triage-aggregate",
            "--project-root",
            str(proj),
            "--promote-decisions",
            "--apply",
            "--format",
            "json",
        ],
    )
    assert res.exit_code == 0, res.output
    import json

    payload = json.loads(res.output)
    assert "decision:D1" in payload["promoted"]
    assert (proj / "entities" / "decision" / "D1.md").is_file()


def test_promote_decisions_apply_refused_on_v2(tmp_path: Path):
    proj = _v3_project(
        tmp_path,
        [{"canonical_id": "decision:D1", "kind": "decision", "title": "D1", "source_path": "core/decisions.md"}],
        "# Decisions\n\n## D1. X\n\nWhy.\n",
    )
    (proj / "science.yaml").write_text(
        "name: t\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\n",
        encoding="utf-8",
    )
    res = CliRunner().invoke(
        main,
        ["entities", "triage-aggregate", "--project-root", str(proj), "--promote-decisions", "--apply"],
    )
    assert res.exit_code == 1
    assert "layout_version" in res.output


def test_generate_decisions_write(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    (d / "D1.md").write_text(
        render_owner_file(
            DecisionSection("decision:D1", "D1", "First", "2026-01-01", "active", "Why.\n"),
            promoted_from="x",
            today="2026-06-09",
        ),
        encoding="utf-8",
    )
    res = CliRunner().invoke(main, ["entities", "generate-decisions", "--project-root", str(tmp_path), "--write"])
    assert res.exit_code == 0, res.output
    out = (tmp_path / "core" / "decisions.md").read_text(encoding="utf-8")
    assert out.startswith("<!-- GENERATED")
    assert "## D1. First" in out


def test_generate_decisions_dry_run_does_not_write(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    (d / "D1.md").write_text(
        render_owner_file(
            DecisionSection("decision:D1", "D1", "First", None, None, "Why.\n"), promoted_from="x", today="2026-06-09"
        ),
        encoding="utf-8",
    )
    res = CliRunner().invoke(main, ["entities", "generate-decisions", "--project-root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "## D1. First" in res.output
    assert not (tmp_path / "core" / "decisions.md").exists()
