"""Behavior-neutral contract pins for the Spec 3 Slice C compiler refactor.

These pass against the current code and must remain green through the phase
split and audit/materialize unification. They lock the public contracts the
refactor must preserve: the materialize-only project-root preflight, the audit
hard-gate on the materialize path, the non-raising audit-only path, and the
load/audit-free `build_dataset_from_sources`.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from rdflib import Dataset

from science_tool.graph.io import entity_uri_for_ref
from science_tool.graph.materialize import (
    build_dataset_from_sources,
    materialization_audit,
    materialize_graph,
)
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")


_SEED = "name: proj\nprofile: research\nprofiles: {local: local}\n"


def _question(root: Path, filename: str, cid: str) -> None:
    _write(
        root / "entities" / "questions" / filename,
        f'---\nid: "{cid}"\ntype: "question"\ntitle: "{cid}"\n---\n',
    )


def _build_dup_project(root: Path) -> None:
    """Two non-deprecated owners of one id → genuine audit failure (§B1)."""
    _write(root / "science.yaml", _SEED)
    _question(root, "q1.md", "question:q1")
    _question(root, "q1-dup.md", "question:q1")


def _build_unmigrated_dp_project(root: Path) -> None:
    """Valid manifest + one active (unmigrated) data-package → preflight target."""
    _write(root / "science.yaml", _SEED)
    _question(root, "q1.md", "question:q1")
    _write(
        root / "doc" / "data-packages" / "u.md",
        '---\nid: "data-package:u"\ntype: "data-package"\ntitle: "U"\nstatus: "active"\n---\n',
    )


def _build_clean_project(root: Path) -> Path:
    """Minimal project that materializes cleanly with freshness + snapshots."""
    demo = root / "demo"
    _write(demo / "science.yaml", "name: demo\nknowledge_profiles:\n  local: core\n")
    _write(demo / "knowledge" / "graph.trig", "")
    _write(
        demo / "entities" / "hypotheses" / "h1.md",
        """
        ---
        id: "hypothesis:h1"
        kind: "hypothesis"
        title: "Demo hypothesis"
        last_reviewed: "2026-05-01"
        created: "2026-04-01"
        updated: "2026-04-01"
        ---
        Original body.
        """,
    )
    return demo


def test_materialize_raises_on_audit_failure(tmp_path: Path) -> None:
    _build_dup_project(tmp_path)
    with pytest.raises(ValueError, match="Cannot materialize graph with unresolved references"):
        materialize_graph(tmp_path, strict=True)


def test_audit_only_path_does_not_raise_or_write(tmp_path: Path) -> None:
    _build_dup_project(tmp_path)
    rows, has_failures = materialization_audit(tmp_path)  # must NOT raise
    assert has_failures is True
    assert any(r["status"] == "fail" for r in rows)
    # audit writes nothing
    assert not (tmp_path / "knowledge" / "graph.trig").exists()


def test_preflight_is_materialize_only(tmp_path: Path) -> None:
    _build_unmigrated_dp_project(tmp_path)
    # materialize path runs the preflight and raises RuntimeError
    with pytest.raises(RuntimeError) as exc:
        materialize_graph(tmp_path, strict=True)
    assert "data-package:u" in str(exc.value)
    assert "data-package migrate" in str(exc.value)
    # audit path skips the preflight: it must not raise RuntimeError
    rows, _ = materialization_audit(tmp_path)
    assert isinstance(rows, list)


def test_build_dataset_from_sources_is_load_audit_free(tmp_path: Path) -> None:
    root = _build_clean_project(tmp_path)
    sources = load_project_sources(root, strict_identity=False)
    # delete the pre-seeded graph.trig to prove build_dataset_from_sources writes nothing
    (root / "knowledge" / "graph.trig").unlink()

    ds = build_dataset_from_sources(sources)

    assert isinstance(ds, Dataset)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    h1 = entity_uri_for_ref("hypothesis:h1")
    assert (h1, None, None) in knowledge  # entity emitted
    # build_dataset_from_sources does no filesystem write
    assert not (root / "knowledge" / "graph.trig").exists()
