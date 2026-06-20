import json
from pathlib import Path

import pytest

from science_tool.annotation.prose_decomposition import (
    ProseDecompositionStore,
    artifact_unit_ref,
    compute_source_hash,
    parse_submitted_decomposition,
)
from science_tool.annotation.prose_promote import ProsePromotionError, promote_prose_unit
from science_tool.annotation.prose_promotion_batch import (
    apply_prose_promotion_plan,
    plan_from_json,
    plan_prose_promotions,
)


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    return source


def _artifact_payload(
    tmp_path: Path,
    *,
    artifact_id: str = "decomp-1",
    unit_id: str = "u001",
    disposition: str = "candidate",
    exact: str = "Basalt flows record the cooling history.",
    candidate_type: str = "proposition",
) -> dict[str, object]:
    source = _source(tmp_path)
    if disposition == "candidate":
        unit: dict[str, object] = {
            "unit_id": unit_id,
            "disposition": "candidate",
            "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
            "payload": {
                "type": candidate_type,
                "exact": exact,
                "prefix": "",
                "suffix": "",
                "stance": "asserted",
            },
        }
    else:
        unit = {
            "unit_id": unit_id,
            "disposition": "skip",
            "locator": {
                "regime": "markdown-heading-path-with-quote",
                "value": ["Section"],
                "quote": {"exact": exact, "prefix": "", "suffix": ""},
            },
            "reason": {"code": "not_a_claim", "detail": "Background context."},
        }

    return {
        "schema_version": 1,
        "source": {
            "kind": "prose-source",
            "slug": "example",
            "path": str(source),
            "title": "Example",
            "content_hash": compute_source_hash(source),
        },
        "artifact": {"id": artifact_id, "generated_at": "2026-06-18T12:00:00Z", "producer": "offline-agent"},
        "units": [unit],
    }


def _persist_artifact(
    tmp_path: Path,
    *,
    artifact_id: str = "decomp-1",
    unit_id: str = "u001",
    disposition: str = "candidate",
    exact: str = "Basalt flows record the cooling history.",
):
    artifact = parse_submitted_decomposition(
        json.dumps(
            _artifact_payload(
                tmp_path,
                artifact_id=artifact_id,
                unit_id=unit_id,
                disposition=disposition,
                exact=exact,
            )
        ),
        project_root=tmp_path,
    )
    ProseDecompositionStore(tmp_path).persist(artifact)
    return artifact


def _persist_duplicate_claim_artifact(tmp_path: Path, *, candidate_type: str = "proposition"):
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "# Section\n\nBasalt flows record the cooling history.\n\n"
        "# Other\n\nBasalt flows record the cooling history.\n",
        encoding="utf-8",
    )
    payload = _artifact_payload(tmp_path)
    payload["source"] = {
        "kind": "prose-source",
        "slug": "example",
        "path": str(source),
        "title": "Example",
        "content_hash": compute_source_hash(source),
    }
    payload["units"] = [
        {
            "unit_id": "u001",
            "disposition": "candidate",
            "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
            "payload": {
                "type": candidate_type,
                "exact": "Basalt flows record the cooling history.",
                "prefix": "",
                "suffix": "",
                "stance": "asserted",
            },
        },
        {
            "unit_id": "u002",
            "disposition": "candidate",
            "locator": {"regime": "markdown-heading-path", "value": ["Other"]},
            "payload": {
                "type": candidate_type,
                "exact": "Basalt flows record the cooling history.",
                "prefix": "",
                "suffix": "",
                "stance": "asserted",
            },
        },
    ]
    artifact = parse_submitted_decomposition(json.dumps(payload), project_root=tmp_path)
    ProseDecompositionStore(tmp_path).persist(artifact)
    return artifact


def _persist_duplicate_question_artifact(tmp_path: Path):
    return _persist_duplicate_claim_artifact(tmp_path, candidate_type="question")


def _write_existing_proposition(root: Path) -> None:
    dest = root / "entities" / "propositions" / "existing.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "---\n"
        "id: proposition:existing\n"
        "type: proposition\n"
        "title: Basalt flows record the cooling history.\n"
        "status: active\n"
        "source_refs: []\n"
        "---\n"
        "\n"
        "Existing body.\n",
        encoding="utf-8",
    )


def _write_recovered_proposition(root: Path, source_ref: str) -> None:
    dest = root / "entities" / "propositions" / "recovered.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "---\n"
        "id: proposition:recovered\n"
        "type: proposition\n"
        "title: Basalt flows record the cooling history.\n"
        "status: active\n"
        "source_refs:\n"
        f"  - {source_ref}\n"
        "---\n"
        "\n"
        "Recovered body.\n",
        encoding="utf-8",
    )


def test_plan_is_identity_only_without_candidate_payload_or_claim(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]

    plan = plan_prose_promotions(tmp_path, "example", ["u001"])

    payload = plan.to_json()
    assert payload["schema_version"] == 1
    assert payload["source_slug"] == "example"
    rows = payload["rows"]
    assert isinstance(rows, list)
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, dict)
    assert row == {
        "source_slug": "example",
        "source_ref": "prose-source:example",
        "artifact_id": "decomp-1",
        "unit_id": "u001",
        "fingerprint": unit.fingerprint,
        "artifact_unit_ref": artifact_unit_ref(artifact, unit),
        "decision": "mint",
        "target_ref": None,
    }
    assert "claim" not in row
    assert "candidate" not in row
    assert "candidate_type" not in row
    assert "payload" not in row


def test_plan_links_recovered_unit_before_locator_resolution(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]
    _write_recovered_proposition(tmp_path, artifact_unit_ref(artifact, unit))
    (tmp_path / "docs" / "example.md").unlink()

    plan = plan_prose_promotions(tmp_path, "example", ["u001"])

    rows = plan.to_json()["rows"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    assert row["decision"] == "link"
    assert row["target_ref"] == "proposition:recovered"


def test_apply_recovered_link_records_index_without_link_counter_or_ref_churn(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]
    _write_recovered_proposition(tmp_path, artifact_unit_ref(artifact, unit))
    dest = tmp_path / "entities" / "propositions" / "recovered.md"
    first_text = dest.read_text(encoding="utf-8")
    plan = plan_prose_promotions(tmp_path, "example", ["u001"])

    report = apply_prose_promotion_plan(tmp_path, plan)

    assert report.minted == 0
    assert report.linked == 0
    assert dest.read_text(encoding="utf-8") == first_text
    index = ProseDecompositionStore(tmp_path).load_index("example")
    assert index["units"][unit.fingerprint]["promoted_to"] == "proposition:recovered"


def test_apply_matches_single_unit_promotion_behavior(tmp_path: Path) -> None:
    batch_root = tmp_path / "batch"
    single_root = tmp_path / "single"
    batch_artifact = _persist_artifact(batch_root)
    single_artifact = _persist_artifact(single_root)

    plan = plan_prose_promotions(batch_root, "example", ["u001"])
    batch_report = apply_prose_promotion_plan(batch_root, plan)
    single_report = promote_prose_unit(single_root, "prose-source:example", "u001", apply=True)

    assert batch_report.minted == single_report.minted == 1
    assert batch_report.linked == single_report.linked == 0
    batch_dest = batch_root / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md"
    single_dest = single_root / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md"
    assert batch_dest.exists()
    assert single_dest.exists()
    batch_index = ProseDecompositionStore(batch_root).load_index("example")
    single_index = ProseDecompositionStore(single_root).load_index("example")
    assert batch_index["units"][batch_artifact.units[0].fingerprint]["promoted_to"] == single_index["units"][
        single_artifact.units[0].fingerprint
    ]["promoted_to"]


def test_apply_rejects_stale_artifact_id(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    plan = plan_prose_promotions(tmp_path, "example", ["u001"])
    _persist_artifact(tmp_path, artifact_id="decomp-2")

    with pytest.raises(ProsePromotionError, match="stale artifact"):
        apply_prose_promotion_plan(tmp_path, plan)


def test_apply_rejects_fingerprint_mismatch(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    payload = plan_prose_promotions(tmp_path, "example", ["u001"]).to_json()
    rows = payload["rows"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    row["fingerprint"] = "0" * 64
    plan = plan_from_json(payload)

    with pytest.raises(ProsePromotionError, match="fingerprint mismatch"):
        apply_prose_promotion_plan(tmp_path, plan)


def test_apply_rejects_source_ref_mismatch_before_mutation(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    payload = plan_prose_promotions(tmp_path, "example", ["u001"]).to_json()
    rows = payload["rows"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    row["source_ref"] = "prose-source:other"

    with pytest.raises(ProsePromotionError, match="source_ref"):
        plan_from_json(payload)

    assert not (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()


def test_apply_rejects_artifact_unit_ref_mismatch_before_mutation(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    payload = plan_prose_promotions(tmp_path, "example", ["u001"]).to_json()
    rows = payload["rows"]
    assert isinstance(rows, list)
    row = rows[0]
    assert isinstance(row, dict)
    row["artifact_unit_ref"] = "annotation:data/prose-decompositions/example/generations/decomp-1.json#u999"
    plan = plan_from_json(payload)

    with pytest.raises(ProsePromotionError, match="artifact_unit_ref"):
        apply_prose_promotion_plan(tmp_path, plan)

    assert not (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()


def test_apply_rejects_duplicate_units_before_partial_mutation(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    payload = plan_prose_promotions(tmp_path, "example", ["u001"]).to_json()
    rows = payload["rows"]
    assert isinstance(rows, list)
    rows.append(dict(rows[0]))

    with pytest.raises(ProsePromotionError, match="duplicate"):
        plan_from_json(payload)

    assert not (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()


def test_plan_rejects_duplicate_mint_targets_before_partial_mutation(tmp_path: Path) -> None:
    _persist_duplicate_claim_artifact(tmp_path)

    with pytest.raises(ProsePromotionError, match="duplicate mint target"):
        plan_prose_promotions(tmp_path, "example", ["u001", "u002"])

    assert not (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()


def test_plan_allows_duplicate_numeric_mint_titles(tmp_path: Path) -> None:
    _persist_duplicate_question_artifact(tmp_path)

    plan = plan_prose_promotions(tmp_path, "example", ["u001", "u002"])

    payload = plan.to_json()
    rows = payload["rows"]
    assert isinstance(rows, list)
    assert [row["decision"] for row in rows if isinstance(row, dict)] == ["mint", "mint"]


def test_plan_rejects_empty_unit_list(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)

    with pytest.raises(ProsePromotionError, match="at least one unit"):
        plan_prose_promotions(tmp_path, "example", [])


def test_plan_from_json_rejects_empty_rows() -> None:
    with pytest.raises(ProsePromotionError, match="at least one row"):
        plan_from_json({"schema_version": 1, "source_slug": "example", "rows": []})


def test_apply_rejects_decision_drift(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    plan = plan_prose_promotions(tmp_path, "example", ["u001"])
    _write_existing_proposition(tmp_path)

    with pytest.raises(ProsePromotionError, match="decision drift"):
        apply_prose_promotion_plan(tmp_path, plan)


def test_apply_rejects_artifact_skip_unit(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path, disposition="skip")
    unit = artifact.units[0]
    plan = plan_from_json(
        {
            "schema_version": 1,
            "source_slug": "example",
            "rows": [
                {
                    "source_slug": "example",
                    "source_ref": "prose-source:example",
                    "artifact_id": artifact.artifact.artifact_id,
                    "unit_id": unit.unit_id,
                    "fingerprint": unit.fingerprint,
                    "artifact_unit_ref": artifact_unit_ref(artifact, unit),
                    "decision": "mint",
                    "target_ref": None,
                }
            ],
        }
    )

    with pytest.raises(ProsePromotionError, match="non-candidate"):
        apply_prose_promotion_plan(tmp_path, plan)
