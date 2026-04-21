"""Sanity test for the mm30 DAG fixture.

Loads all 4 edges.yaml files through EdgesYamlFile.model_validate and runs
validate_ref_entry on every data_support and lit_support entry.

Known fixture issues (Task 14 migration targets):
- h1-h2-bridge.edges.yaml edges 4 and 7: author_year-only lit_support entries
  (no kind tag from REF_KINDS) — fail EdgesYamlFile.model_validate.
- h1-prognosis.edges.yaml and h2-subtype-architecture.edges.yaml: doi=null
  placeholder entries — pass schema validation but fail validate_ref_entry
  because _single_kind filters None values.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

import pytest
import yaml

from science_tool.dag.refs import RefResolutionError, validate_ref_entry
from science_tool.dag.schema import EdgesYamlFile, RefEntry

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "mm30"
DAGS_DIR = FIXTURE_ROOT / "doc" / "figures" / "dags"

SLUGS = [
    "h1-prognosis",
    "h1-progression",
    "h2-subtype-architecture",
    "h1-h2-bridge",
]


class RefLocation(NamedTuple):
    slug: str
    edge_id: int
    support_type: str
    entry: RefEntry


def _all_ref_entries(file: EdgesYamlFile, slug: str) -> list[RefLocation]:
    """Return all ref entries from all edges in the file."""
    locs: list[RefLocation] = []
    for edge in file.edges:
        for support_type in ("data_support", "lit_support"):
            for entry in getattr(edge, support_type, []) or []:
                locs.append(RefLocation(slug, edge.id, support_type, entry))
        if edge.eliminated_by:
            for entry in edge.eliminated_by:
                locs.append(RefLocation(slug, edge.id, "eliminated_by", entry))
    return locs


def _is_doi_null(entry: RefEntry) -> bool:
    """Return True if this entry has doi=null (a placeholder needing Task 14 migration)."""
    extra: dict = entry.__pydantic_extra__ or {}
    return "doi" in extra and extra["doi"] is None


# ---------------------------------------------------------------------------
# Schema loading — one test per DAG
# ---------------------------------------------------------------------------


def test_h1_h2_bridge_schema_loads() -> None:
    path = DAGS_DIR / "h1-h2-bridge.edges.yaml"
    data = yaml.safe_load(path.read_text())
    file = EdgesYamlFile.model_validate(data)
    assert len(file.edges) == 7


def test_h1_prognosis_schema_loads() -> None:
    path = DAGS_DIR / "h1-prognosis.edges.yaml"
    data = yaml.safe_load(path.read_text())
    file = EdgesYamlFile.model_validate(data)
    assert len(file.edges) == 29


def test_h1_progression_schema_loads() -> None:
    path = DAGS_DIR / "h1-progression.edges.yaml"
    data = yaml.safe_load(path.read_text())
    file = EdgesYamlFile.model_validate(data)
    assert len(file.edges) == 6


def test_h2_subtype_architecture_schema_loads() -> None:
    path = DAGS_DIR / "h2-subtype-architecture.edges.yaml"
    data = yaml.safe_load(path.read_text())
    file = EdgesYamlFile.model_validate(data)
    assert len(file.edges) == 43


# ---------------------------------------------------------------------------
# Ref resolution — one test per DAG that parses successfully
# ---------------------------------------------------------------------------


def _validate_dag_refs(slug: str, *, allow_doi_null: bool = True) -> tuple[int, list[str]]:
    """Load and validate all refs for a single DAG.

    Returns (ok_count, failure_messages).
    doi=null entries are skipped when allow_doi_null=True (warn-only).
    """
    path = DAGS_DIR / f"{slug}.edges.yaml"
    data = yaml.safe_load(path.read_text())
    file = EdgesYamlFile.model_validate(data)

    ok = 0
    failures: list[str] = []
    for loc in _all_ref_entries(file, slug):
        entry = loc.entry
        if allow_doi_null and _is_doi_null(entry):
            continue  # doi=null is a known placeholder — Task 14
        try:
            validate_ref_entry(entry, FIXTURE_ROOT)
            ok += 1
        except RefResolutionError as exc:
            failures.append(f"Edge {loc.edge_id} {loc.support_type}: {exc}")
    return ok, failures


def test_h1_prognosis_refs_resolve(caplog: pytest.LogCaptureFixture) -> None:
    """All refs in h1-prognosis resolve cleanly (paper: refs replace doi: null post-migration)."""
    with caplog.at_level(logging.WARNING):
        ok, failures = _validate_dag_refs("h1-prognosis")
    assert not failures, "Ref resolution failures:\n" + "\n".join(failures)
    assert ok > 0


def test_h1_progression_refs_resolve(caplog: pytest.LogCaptureFixture) -> None:
    """All refs in h1-progression resolve cleanly."""
    with caplog.at_level(logging.WARNING):
        ok, failures = _validate_dag_refs("h1-progression")
    assert not failures, "Ref resolution failures:\n" + "\n".join(failures)
    assert ok > 0


def test_h2_subtype_architecture_refs_resolve(caplog: pytest.LogCaptureFixture) -> None:
    """All refs in h2-subtype-architecture resolve cleanly (paper: refs replace doi: null post-migration)."""
    with caplog.at_level(logging.WARNING):
        ok, failures = _validate_dag_refs("h2-subtype-architecture")
    assert not failures, "Ref resolution failures:\n" + "\n".join(failures)
    assert ok > 0


# ---------------------------------------------------------------------------
# Fixture completeness — every cited task_id resolves
# ---------------------------------------------------------------------------


def test_all_cited_task_ids_resolve() -> None:
    """Every task: ref across all 4 DAGs resolves in fixture tasks/ files.

    h1-h2-bridge is loaded raw (bypassing the schema validator) so that its
    task: refs can still be validated despite the author_year-only issue.
    """
    task_ids: set[str] = set()

    for slug in SLUGS:
        path = DAGS_DIR / f"{slug}.edges.yaml"
        data = yaml.safe_load(path.read_text())

        for edge in data.get("edges", []):
            for support_type in ("data_support", "lit_support", "eliminated_by"):
                for entry_data in edge.get(support_type, []) or []:
                    if isinstance(entry_data, dict) and "task" in entry_data:
                        task_ids.add(entry_data["task"])

    from science_tool.dag.refs import _task_exists  # type: ignore[attr-defined]

    missing = [tid for tid in sorted(task_ids) if not _task_exists(tid, FIXTURE_ROOT)]
    assert not missing, f"Task IDs cited in edges.yaml but missing from fixture: {missing}"
