import json
from pathlib import Path

import pytest

from science_tool.annotation.prose_decomposition import (
    DecompositionError,
    artifact_unit_ref,
    parse_submitted_decomposition,
)


def _artifact(tmp_path: Path, *, unit_id: str = "u001", heading=None, quote=None) -> dict:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    return {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": "sha256:" + "0" * 64,
        },
        "artifact": {
            "id": "decomp-1",
            "generated_at": "2026-06-18T12:00:00Z",
            "producer": "offline-agent",
        },
        "units": [
            {
                "unit_id": unit_id,
                "disposition": "candidate",
                "locator": {"regime": "markdown-heading-path", "value": heading or ["Section"]},
                "payload": {
                    "type": "proposition",
                    "exact": quote or "Basalt flows record the cooling history.",
                    "prefix": "",
                    "suffix": "",
                    "stance": "asserted",
                },
            },
            {
                "unit_id": "s001",
                "disposition": "skip",
                "reason": {"code": "not_a_claim", "detail": "Heading only."},
                "locator": {
                    "regime": "markdown-heading-path-with-quote",
                    "value": ["Section"],
                    "quote": {"exact": "Basalt flows", "prefix": "", "suffix": ""},
                },
            },
        ],
    }


def test_parse_valid_decomposition(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    assert artifact.schema_version == 1
    assert artifact.source_ref == "prose-source:example"
    assert artifact.units[0].unit_id == "u001"
    assert artifact.units[0].candidate is not None
    assert artifact.units[1].reason_code == "not_a_claim"


def test_candidate_locator_quote_is_rejected(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][0]["locator"]["quote"] = {"exact": "duplicate", "prefix": "", "suffix": ""}
    with pytest.raises(DecompositionError, match="candidate unit must not carry locator.quote"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_unknown_skip_reason_fails(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][1]["reason"]["code"] = "mystery"
    with pytest.raises(DecompositionError, match="unknown skip reason"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_candidate_payload_must_be_statement_candidate(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][0]["payload"] = {
        "type": "metaphor",
        "exact": "Basalt flows",
        "prefix": "",
        "suffix": "",
        "source_domain": "geology",
        "target_domain": "history",
    }
    with pytest.raises(DecompositionError, match="StatementCandidate"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_duplicate_unit_id_fails(tmp_path):
    raw = _artifact(tmp_path)
    raw["units"][1]["unit_id"] = "u001"
    with pytest.raises(DecompositionError, match="duplicate unit_id"):
        parse_submitted_decomposition(json.dumps(raw), project_root=tmp_path)


def test_fingerprint_ignores_artifact_local_unit_id(tmp_path):
    first = parse_submitted_decomposition(json.dumps(_artifact(tmp_path, unit_id="u001")), project_root=tmp_path)
    second = parse_submitted_decomposition(json.dumps(_artifact(tmp_path, unit_id="u777")), project_root=tmp_path)
    assert first.units[0].fingerprint == second.units[0].fingerprint


def test_artifact_unit_ref_uses_annotation_namespace(tmp_path):
    artifact = parse_submitted_decomposition(json.dumps(_artifact(tmp_path)), project_root=tmp_path)
    assert artifact_unit_ref(artifact, artifact.units[0]) == (
        "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001"
    )
