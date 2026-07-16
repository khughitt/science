"""Pins the full source-load output under exhaustive, selection-free collection.

Two fixtures exercise the source-load adapter branches: markdown source_document capture,
missing-identity skip under strict, a datapackage contending with a markdown owner, and an
external-ref (bib) contending with a markdown owner. `_snapshot` captures the full normalized
load output.

Collection is now exhaustive: every validated adapter entity becomes a contribution and every
contribution declares, whatever else claims the same id. Adapter-time deferral used to DELETE
the losing declaration, so the datapackage and bib rows below did not exist -- the load reported
that only markdown had ever spoken for these ids. Materialization still yields one entity per
id; what changed is that losing a representative contest no longer erases the evidence that the
contest happened, which is exactly what the identity audit reads.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_tool.graph.sources import ProjectSources, load_project_sources

_MANIFEST = "name: slice-a\nprofile: research\nknowledge_profiles: {local: local}\n"


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


# Frozen expected output under arbitration.
EXPECTED_STRICT: dict[str, Any] = {
    "entities": ["dataset:ds1", "dataset:ds2", "hypothesis:h1"],
    "identity_declarations": [
        ("dataset:ds1", "owner", "slice-a", "datapackage", True),
        # ds2's datapackage declares even though markdown wins the representative. The
        # deprecated row IS the migration signal the identity audit reports on; deferral
        # deleted it, so the audit could not see a datapackage still needing migration.
        ("dataset:ds2", "owner", "slice-a", "datapackage", True),
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
    # ds2 only. ds1's datapackage REPRESENTS dataset:ds1, so this column has nothing to add
    # for it -- the consumer resolves a datapackage-represented dataset from its own path.
    # The column means "where else do this dataset's resources live", and that stays true
    # without deferral: ds2's markdown owner represents it, so ds2's datapackage says here
    # where its resources are.
    "dataset_datapackages": {"dataset:ds2": "data/ds2/datapackage.yaml"},
    # ds2 still materializes from markdown: the datapackage declared, and lost, on the merits
    # of being deprecated -- not by being dropped before it could speak.
    "entity_source_adapters": {
        "dataset:ds1": "datapackage",
        "dataset:ds2": "markdown",
        "hypothesis:h1": "markdown",
    },
}

EXPECTED_NONSTRICT: dict[str, Any] = {
    "entities": ["paper:Smith2024"],
    "identity_declarations": [
        # The bib row declares as an EXTERNAL_REFERENCE and never as an owner. It supports the
        # markdown owner rather than contending with it; deferral deleted this row entirely,
        # which is how a bib entry came to shadow a commons canonical (fb-2026-07-16-005).
        # owner_scope "bib" is the external-reference AUTHORITY scope, not this project's:
        # `classify_owner_scope` gives bib its own scope precisely so a bib row can never be
        # mistaken for a project owner row.
        ("paper:Smith2024", "external-reference", "bib", "bib", False),
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


def test_strict_load_declares_every_owner_and_materializes_one_per_id(tmp_path: Path) -> None:
    _build_strict_project(tmp_path)
    sources = load_project_sources(tmp_path, include_commons=False)  # strict defaults
    assert _snapshot(sources) == EXPECTED_STRICT


def test_nonstrict_load_declares_the_external_reference_beside_its_owner(tmp_path: Path) -> None:
    _build_nonstrict_project(tmp_path)
    sources = load_project_sources(
        tmp_path, include_commons=False, strict_core_schema=False, strict_identity=True
    )
    assert _snapshot(sources) == EXPECTED_NONSTRICT
