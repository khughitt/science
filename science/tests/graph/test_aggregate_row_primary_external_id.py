# tests/graph/test_aggregate_row_primary_external_id.py
from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 2\nontologies:\n  - biology\n"


def _write(root: Path, terms: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "terms.yaml").write_text(yaml.safe_dump({"terms": terms}), encoding="utf-8")


def _meta_for(sources, cid):
    return next(m for m in sources.aggregate_rows if m.canonical_id == cid)


def test_wellformed_primary_external_id_captured(tmp_path: Path) -> None:
    _write(
        tmp_path,
        [
            {
                "id": "protein:BCMA",
                "title": "BCMA",
                # Full ExternalId shape: source, id, curie, provenance are ALL required.
                "primary_external_id": {
                    "source": "UniProtKB",
                    "id": "Q02223",
                    "curie": "UniProtKB:Q02223",
                    "provenance": "manual",
                },
            }
        ],
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    meta = _meta_for(sources, "protein:BCMA")
    # Captured from the validated entity; model_dump(exclude_none=True) drops only `version`.
    assert meta.primary_external_id == {
        "source": "UniProtKB",
        "id": "Q02223",
        "curie": "UniProtKB:Q02223",
        "provenance": "manual",
    }


def test_malformed_primary_external_id_row_is_skipped(tmp_path: Path) -> None:
    # A half-filled primary_external_id fails ExternalId schema validation
    # (source/id/curie/provenance all required) at sources.py:359, so the row is
    # SKIPPED before the aggregate-meta capture at :452 — it never appears in
    # aggregate_rows (not even as a None-PEI row). A row with NO primary_external_id
    # validates fine and IS captured with primary_external_id is None. `concept` is a
    # core kind that permits an absent primary_external_id (mirrors real terms.yaml).
    _write(
        tmp_path,
        [
            {
                "id": "concept:partial",
                "title": "Partial",
                "primary_external_id": {"source": "UniProtKB"},
            },  # missing id/curie/provenance -> skipped
            {"id": "concept:plain", "title": "Plain"},  # no primary_external_id -> captured, None
        ],
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    cids = {m.canonical_id for m in sources.aggregate_rows}
    assert "concept:partial" not in cids  # skipped at ExternalId validation
    assert "concept:plain" in cids  # captured
    assert _meta_for(sources, "concept:plain").primary_external_id is None
    assert sources.skipped_entities  # the malformed row was recorded as a skip
