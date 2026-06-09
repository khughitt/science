# tests/graph/test_curie_external_reference_load.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.identity_table import ParticipationMode, build_identity_table
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\nontologies:\n  - biology\n"


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
                        "type": "protein",
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


def test_curie_defers_to_transitional_aggregate_stub_no_collision(tmp_path: Path) -> None:
    # Same id present as BOTH an aggregate stub (terms.yaml) and a curie authority
    # row. Under STRICT load this must not raise: the curie defers to the stub.
    _base(tmp_path)
    src = _src(tmp_path)
    src.joinpath("terms.yaml").write_text(
        yaml.safe_dump({"terms": [{"id": "protein:BCMA", "title": "BCMA"}]}), encoding="utf-8"
    )
    src.joinpath("external_refs.yaml").write_text(
        yaml.safe_dump(
            {
                "references": [
                    {
                        "id": "protein:BCMA",
                        "type": "protein",
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
    # strict_identity=True must NOT raise (defer fires).
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=True)
    table = build_identity_table(sources)
    owners = table.owners()[("demo", "protein:BCMA")]
    # Only the aggregate stub is an owner row; the curie row deferred (no second decl).
    assert all(r.adapter == "aggregate" for r in owners)
