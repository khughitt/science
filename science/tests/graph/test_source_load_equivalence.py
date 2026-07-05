"""Behavior-neutral pinning test for the Spec 3 Slice A loop refactor.

Two fixtures exercise the source-load adapter policy branches: markdown
source_document capture, missing-identity skip under strict, datapackage defer
onto a markdown owner, and external-ref (bib) defer onto a markdown owner.
`_snapshot` captures the full normalized load output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_tool.graph.sources import ProjectSources, load_project_sources

_MANIFEST = "name: slice-a\nprofile: research\nprofiles: {local: local}\n"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot(s: ProjectSources) -> dict[str, Any]:
    """Normalize the full load output into deterministic, comparable values."""
    return {
        "entities": [e.canonical_id for e in s.entities],  # load sorts by canonical_id
        "identity_declarations": sorted(
            (d.canonical_id, d.participation_mode.value, d.owner_scope, d.adapter, d.deprecated)
            for d in s.identity_declarations
        ),
        "skipped_entities": sorted((x.path, x.kind, x.reason) for x in s.skipped_entities),
        "markdown_documents": sorted(
            (d.path, tuple(sorted(d.frontmatter)), d.body) for d in s.markdown_documents
        ),
        "dataset_datapackages": dict(s.dataset_datapackages),
        "entity_source_adapters": dict(s.entity_source_adapters),
    }


def _build_strict_project(root: Path) -> None:
    _write(root, "science.yaml", _MANIFEST)
    # branch 1 + a normal markdown owner
    _write(
        root,
        "entities/hypotheses/h1.md",
        '---\nid: "hypothesis:h1"\nkind: "hypothesis"\ntitle: "H1"\n---\nbody\n',
    )
    # branch 2: core hypothesis missing identity → skip-warn even under strict
    _write(root, "entities/hypotheses/bad.md", '---\nkind: "hypothesis"\ntitle: "Bad"\n---\n')
    # branch 3: markdown dataset owner that a datapackage will defer to
    _write(
        root,
        "entities/datasets/ds2.md",
        '---\nid: "dataset:ds2"\nkind: "dataset"\ntitle: "DS2"\n'
        'origin: "external"\naccess: {level: "public", verified: false}\n---\n',
    )
    # branch 3: the deferring datapackage (same id as the markdown owner) + an orphan
    for dsid in ("ds2", "ds1"):
        _write(
            root,
            f"data/{dsid}/datapackage.yaml",
            yaml.safe_dump(
                {
                    "profiles": ["science-pkg-entity-1.0"],
                    "name": dsid,
                    "id": f"dataset:{dsid}",
                    "kind": "dataset",
                    "title": dsid.upper(),
                    "origin": "external",
                    "access": {"level": "public", "verified": False},
                }
            ),
        )


def _build_nonstrict_project(root: Path) -> None:
    _write(root, "science.yaml", _MANIFEST)
    _write(
        root,
        "entities/papers/Smith2024.md",
        '---\nid: "paper:Smith2024"\nkind: "paper"\ntitle: "S"\n'
        'status: "active"\ncreated: "2026-01-01"\nupdated: "2026-01-01"\n---\n',
    )
    # Bib has the same paper id -> defers to the markdown owner.
    _write(root, "papers/references.bib", "@article{Smith2024,\n  title = {Cells},\n}\n")


# Frozen expected output, captured from the current (pre-flip) loop.
EXPECTED_STRICT: dict[str, Any] = {
    "entities": ["dataset:ds1", "dataset:ds2", "hypothesis:h1"],
    "identity_declarations": [
        ("dataset:ds1", "owner", "slice-a", "datapackage", True),
        ("dataset:ds2", "owner", "slice-a", "markdown", False),
        ("hypothesis:h1", "owner", "slice-a", "markdown", False),
    ],
    "skipped_entities": [
        ("entities/hypotheses/bad.md", "hypothesis", "entity_schema_validation_failed"),
    ],
    "markdown_documents": [
        (
            "entities/datasets/ds2.md",
            ("access", "canonical_id", "file_path", "id", "kind", "origin", "title"),
            "",
        ),
        ("entities/hypotheses/bad.md", ("file_path", "kind", "title"), ""),
        (
            "entities/hypotheses/h1.md",
            ("canonical_id", "file_path", "id", "kind", "title"),
            "body\n",
        ),
    ],
    "dataset_datapackages": {"dataset:ds2": "data/ds2/datapackage.yaml"},
    "entity_source_adapters": {
        "dataset:ds1": "datapackage",
        "dataset:ds2": "markdown",
        "hypothesis:h1": "markdown",
    },
}

EXPECTED_NONSTRICT: dict[str, Any] = {
    "entities": ["paper:Smith2024"],
    "identity_declarations": [
        ("paper:Smith2024", "owner", "slice-a", "markdown", False),
    ],
    "skipped_entities": [],
    "markdown_documents": [
        (
            "entities/papers/Smith2024.md",
            ("canonical_id", "created", "file_path", "id", "kind", "status", "title", "updated"),
            "",
        ),
    ],
    "dataset_datapackages": {},
    "entity_source_adapters": {"paper:Smith2024": "markdown"},
}


def test_strict_load_full_output_is_unchanged(tmp_path: Path) -> None:
    _build_strict_project(tmp_path)
    sources = load_project_sources(tmp_path, include_commons=False)  # strict defaults
    assert _snapshot(sources) == EXPECTED_STRICT


def test_nonstrict_load_full_output_is_unchanged(tmp_path: Path) -> None:
    _build_nonstrict_project(tmp_path)
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=True
    )
    assert _snapshot(sources) == EXPECTED_NONSTRICT
