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


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    return source


def _artifact_payload(
    tmp_path: Path,
    *,
    artifact_id: str = "decomp-1",
    unit_id: str = "u001",
    disposition: str = "candidate",
    exact: str = "Basalt flows record the cooling history.",
) -> dict[str, object]:
    source = _source(tmp_path)
    unit: dict[str, object]
    if disposition == "candidate":
        unit = {
            "unit_id": unit_id,
            "disposition": "candidate",
            "locator": {"regime": "markdown-heading-path", "value": ["Section"]},
            "payload": {
                "type": "proposition",
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


def test_promote_prose_unit_mints_proposition_and_records_state(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]

    report = promote_prose_unit(
        project_root=tmp_path,
        source_ref="prose-source:example",
        unit_id="u001",
        apply=True,
    )

    assert report.minted == 1
    dest = tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md"
    assert dest.exists()
    text = dest.read_text(encoding="utf-8")
    assert "prose-source:example" in text
    assert artifact_unit_ref(artifact, unit) in text

    index = ProseDecompositionStore(tmp_path).load_index("example")
    row = index["units"][unit.fingerprint]
    assert row["promoted_to"].startswith("proposition:")


def test_promote_prose_unit_dry_run_reports_mint_without_writing_or_recording(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]

    report = promote_prose_unit(
        project_root=tmp_path,
        source_ref="prose-source:example",
        unit_id="u001",
        apply=False,
    )

    assert report.minted == 1
    assert not (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()
    index = ProseDecompositionStore(tmp_path).load_index("example")
    assert "promoted_to" not in index["units"][unit.fingerprint]


def test_promote_prose_unit_recovers_index_when_retry_sees_minted_ref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]
    original_record = ProseDecompositionStore.record_promotion
    calls = 0

    def fail_once(self, source_slug: str, fingerprint: str, promoted_to: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated index write failure")
        original_record(self, source_slug, fingerprint, promoted_to)

    monkeypatch.setattr(ProseDecompositionStore, "record_promotion", fail_once)

    with pytest.raises(RuntimeError, match="simulated index write failure"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )

    dest = tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md"
    assert dest.exists()
    first_text = dest.read_text(encoding="utf-8")
    assert artifact_unit_ref(artifact, unit) in first_text
    index = ProseDecompositionStore(tmp_path).load_index("example")
    assert "promoted_to" not in index["units"][unit.fingerprint]

    report = promote_prose_unit(
        project_root=tmp_path,
        source_ref="prose-source:example",
        unit_id="u001",
        apply=True,
    )

    assert report.minted == 0
    assert report.linked == 0
    assert sorted((tmp_path / "entities" / "propositions").glob("*.md")) == [dest]
    assert dest.read_text(encoding="utf-8") == first_text
    index = ProseDecompositionStore(tmp_path).load_index("example")
    assert index["units"][unit.fingerprint]["promoted_to"] == "proposition:basalt-flows-record-the-cooling-history"


def test_promote_prose_unit_links_existing_proposition_and_appends_two_refs(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]
    dest = tmp_path / "entities" / "propositions" / "existing.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "---\n"
        "id: proposition:existing\n"
        "kind: proposition\n"
        "title: Basalt flows record the cooling history.\n"
        "status: active\n"
        "source_refs: []\n"
        "---\n"
        "\n"
        "Existing body.\n",
        encoding="utf-8",
    )

    report = promote_prose_unit(
        project_root=tmp_path,
        source_ref="prose-source:example",
        unit_id="u001",
        apply=True,
    )

    assert report.linked == 1
    text = dest.read_text(encoding="utf-8")
    assert "prose-source:example" in text
    assert artifact_unit_ref(artifact, unit) in text
    assert not (tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md").exists()


def test_promote_prose_unit_recovers_index_when_retry_sees_linked_ref_without_duplicate_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]
    dest = tmp_path / "entities" / "propositions" / "existing.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "---\n"
        "id: proposition:existing\n"
        "kind: proposition\n"
        "title: Basalt flows record the cooling history.\n"
        "status: active\n"
        "source_refs: []\n"
        "---\n"
        "\n"
        "Existing body.\n",
        encoding="utf-8",
    )
    original_record = ProseDecompositionStore.record_promotion
    calls = 0

    def fail_once(self, source_slug: str, fingerprint: str, promoted_to: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated index write failure")
        original_record(self, source_slug, fingerprint, promoted_to)

    monkeypatch.setattr(ProseDecompositionStore, "record_promotion", fail_once)

    with pytest.raises(RuntimeError, match="simulated index write failure"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )

    first_text = dest.read_text(encoding="utf-8")
    assert first_text.count("prose-source:example") == 1
    assert first_text.count(artifact_unit_ref(artifact, unit)) == 1

    report = promote_prose_unit(
        project_root=tmp_path,
        source_ref="prose-source:example",
        unit_id="u001",
        apply=True,
    )

    assert report.minted == 0
    assert report.linked == 0
    retry_text = dest.read_text(encoding="utf-8")
    assert retry_text.count("prose-source:example") == 1
    assert retry_text.count(artifact_unit_ref(artifact, unit)) == 1
    index = ProseDecompositionStore(tmp_path).load_index("example")
    assert index["units"][unit.fingerprint]["promoted_to"] == "proposition:existing"


def test_promote_prose_unit_wraps_missing_source_as_promotion_error(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    (tmp_path / "docs" / "example.md").unlink()

    with pytest.raises(ProsePromotionError, match="source|locator"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )


def test_promote_prose_unit_rejects_skip_unit(tmp_path: Path) -> None:
    _persist_artifact(tmp_path, disposition="skip")

    with pytest.raises(ProsePromotionError, match="non-candidate"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )


def test_promote_prose_unit_rejects_previous_unit_missing_from_latest_artifact(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    source = tmp_path / "docs" / "example.md"
    source.write_text(
        "# Section\n\nBasalt flows record the cooling history.\n\nAsh layers date the eruption sequence.\n",
        encoding="utf-8",
    )
    _persist_artifact(
        tmp_path,
        artifact_id="decomp-2",
        unit_id="u002",
        exact="Ash layers date the eruption sequence.",
    )

    with pytest.raises(ProsePromotionError, match="not in latest artifact|stale"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )


def test_promote_prose_unit_rejects_already_promoted_fingerprint(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]
    ProseDecompositionStore(tmp_path).record_promotion(
        source_slug="example",
        fingerprint=unit.fingerprint,
        promoted_to="proposition:already",
    )

    with pytest.raises(ProsePromotionError, match="already promoted"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )


def test_promote_prose_unit_rejects_type_without_promotable_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _persist_artifact(tmp_path)

    def without_proposition():
        return {"question": object(), "hypothesis": object()}

    monkeypatch.setattr("science_tool.annotation.prose_promote.build_targets", without_proposition)

    with pytest.raises(ProsePromotionError, match="not a promotable target"):
        promote_prose_unit(
            project_root=tmp_path,
            source_ref="prose-source:example",
            unit_id="u001",
            apply=True,
        )
