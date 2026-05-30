from __future__ import annotations

import os
import subprocess
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.materialize import _build_dataset_from_sources
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS
from science_tool.graph.store.constants import (
    GRAPH_EXPORT_EDGE_METADATA_PREDICATES,
)

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)

_DATAPACKAGE = (
    "profiles: [science-pkg-entity-1.0]\n"
    "id: dataset:x\ntype: dataset\ntitle: X\nstatus: active\n"
    "origin: external\ntier: use-now\nlicense: CC-BY-4.0\n"
    # AccessBlock requires both `level` and `verified` (neither has a default).
    "access:\n  level: public\n  availability: available\n  verified: false\n"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def _project(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(_DATAPACKAGE, encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)


def _license_objects(ds) -> set[str]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {str(o) for _, _, o in knowledge.triples((None, SCI_NS.license, None))}


def test_datapackage_license_is_materialized(tmp_path: Path) -> None:
    # Guards BOTH the _ENTITY_FIELDS extraction change and the materialization.
    _project(tmp_path)
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        sources = load_project_sources(tmp_path, include_commons=False)
        ds = _build_dataset_from_sources(sources)
    finally:
        os.chdir(prev)
    assert "CC-BY-4.0" in _license_objects(ds)


def test_license_is_classified_as_edge_metadata() -> None:
    # So graph export treats it as a literal property, not a graph edge.
    assert SCI_NS.license in GRAPH_EXPORT_EDGE_METADATA_PREDICATES


def test_license_predicate_visible_in_graph_predicates() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "predicates", "--format", "json"])
    assert result.exit_code == 0, result.output
    import json

    predicates = {row["predicate"] for row in json.loads(result.output)["rows"]}
    assert "sci:license" in predicates
