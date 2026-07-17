# tests/graph/test_curie_external_reference_load.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.identity_table import ParticipationMode, build_identity_table
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nknowledge_profiles: {local: local}\nlayout_version: 2\nontologies:\n  - biology\n"


def _src(root: Path) -> Path:
    p = root / "knowledge" / "sources" / "local"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _base(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")


def test_curie_row_synthesizes_external_reference_declaration(tmp_path: Path) -> None:
    _base(tmp_path)
    _src(tmp_path).joinpath("external_refs.yaml").write_text(
        yaml.safe_dump(
            {
                "references": [
                    {
                        "id": "protein:BCMA",
                        "kind": "protein",
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
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    decl = next(d for d in sources.identity_declarations if d.canonical_id == "protein:BCMA")
    assert decl.participation_mode is ParticipationMode.EXTERNAL_REFERENCE
    assert decl.adapter == "curie-ref"
    ent = next(e for e in sources.entities if e.canonical_id == "protein:BCMA")
    assert "UniProtKB:Q02223" in list(ent.same_as)


def test_curie_declares_beside_a_markdown_owner_no_collision(tmp_path: Path) -> None:
    # Same id present as BOTH a markdown owner and a curie authority row. Under STRICT load this
    # must not raise -- not because the curie row vanishes, but because it declares as an
    # EXTERNAL_REFERENCE and only owners can collide.
    _base(tmp_path)
    src = _src(tmp_path)
    owner = tmp_path / "entities" / "proteins" / "BCMA.md"
    owner.parent.mkdir(parents=True, exist_ok=True)
    owner.write_text(
        '---\nid: "protein:BCMA"\nkind: "protein"\ntitle: "BCMA"\n'
        'status: "active"\ncreated: "2026-01-01"\nupdated: "2026-01-01"\n---\n',
        encoding="utf-8",
    )
    src.joinpath("external_refs.yaml").write_text(
        yaml.safe_dump(
            {
                "references": [
                    {
                        "id": "protein:BCMA",
                        "kind": "protein",
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
    # strict_identity=True must NOT raise: only one OWNER exists.
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=True)
    table = build_identity_table(sources)

    owners = table.owners()[("demo", "protein:BCMA")]
    assert all(r.adapter == "markdown" for r in owners)
    rows = [r for r in table.rows if r.canonical_id == "protein:BCMA"]
    assert {(r.adapter, r.participation_mode) for r in rows} == {
        ("markdown", ParticipationMode.OWNER),
        ("curie-ref", ParticipationMode.EXTERNAL_REFERENCE),
    }

    materialized = [e for e in sources.entities if e.canonical_id == "protein:BCMA"]
    assert len(materialized) == 1
    assert sources.entity_source_adapters["protein:BCMA"] == "markdown"
    # The curie authority SUPPORTS the owner: the owner authored no `same_as`, so the authority's
    # CURIE fills that vacancy rather than being discarded with the row. Deferral dropped the
    # curie row wholesale, so an owner that cited no CURIE lost the authority mapping entirely.
    assert "UniProtKB:Q02223" in list(materialized[0].same_as)
