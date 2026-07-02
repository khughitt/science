from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from science_tool.annotation import io as anno_io
from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft
from science_tool.entities import parse_markdown_entity_file

from test_proposition_resynthesis import _ann, _draft_payload, _factorization_project


def _edit_by_suffix(preflight, suffix: str):
    matches = [edit for edit in preflight.file_edits if edit.path.as_posix().endswith(suffix)]
    assert len(matches) == 1
    return matches[0]


def test_plan_resynthesis_apply_creates_replacements_rewrites_sidecars_and_supersedes_original(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import plan_resynthesis_apply

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    preflight = plan_resynthesis_apply(tmp_path, draft, as_of=date(2026, 7, 1))

    assert preflight.expected_annotation_targets == {
        "annotation:entities/papers/A2020.source#a1": "proposition:broad-positive",
        "annotation:entities/papers/B2021.source#b1": "proposition:broad-negative",
    }
    assert preflight.expected_original_state == {
        "status": "superseded",
        "resynthesized_into": ["proposition:broad-negative", "proposition:broad-positive"],
    }
    assert preflight.expected_source_refs_by_replacement["proposition:broad-positive"] == (
        "annotation:entities/papers/A2020.source#a1",
        "manual:curator-note",
        "paper:A2020",
    )
    assert preflight.expected_source_refs_by_replacement["proposition:broad-negative"] == (
        "annotation:entities/papers/B2021.source#b1",
        "paper:B2021",
    )

    positive_edit = _edit_by_suffix(preflight, "entities/propositions/broad-positive.md")
    negative_edit = _edit_by_suffix(preflight, "entities/propositions/broad-negative.md")
    original_edit = _edit_by_suffix(preflight, "entities/propositions/broad.md")
    sidecar_a_edit = _edit_by_suffix(preflight, "entities/papers/A2020.source.anno.trig")
    sidecar_b_edit = _edit_by_suffix(preflight, "entities/papers/B2021.source.anno.trig")

    assert positive_edit.reason == "replacement_proposition"
    assert positive_edit.before_sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert positive_edit.changed is True
    assert "id: proposition:broad-positive" in positive_edit.final_text
    assert "annotation:entities/papers/A2020.source#a1" in positive_edit.final_text
    assert "manual:curator-note" in positive_edit.final_text
    assert negative_edit.changed is True

    assert original_edit.reason == "original_resynthesis_lineage"
    original_frontmatter, _body = parse_markdown_entity_file(original_edit.path)
    assert original_frontmatter["source_refs"] == [
        "paper:A2020",
        "annotation:entities/papers/A2020.source#a1",
        "paper:B2021",
        "annotation:entities/papers/B2021.source#b1",
    ]
    assert "status: superseded" in original_edit.final_text
    assert "resynthesized_into:" in original_edit.final_text
    assert "proposition:broad-positive" in original_edit.final_text
    assert "proposition:broad-negative" in original_edit.final_text

    assert sidecar_a_edit.reason == "annotation_promoted_to_rewrite"
    assert sidecar_b_edit.reason == "annotation_promoted_to_rewrite"
    assert "proposition:broad-positive" in sidecar_a_edit.final_text
    assert "proposition:broad-negative" in sidecar_b_edit.final_text

    assert [edit.path for edit in preflight.file_edits] == sorted(edit.path for edit in preflight.file_edits)


def test_plan_resynthesis_apply_merges_multiple_rewrites_in_one_sidecar(tmp_path: Path, monkeypatch):
    from science_tool.annotation.proposition_resynthesis_apply import plan_resynthesis_apply
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    sidecar_path = tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    sidecar = anno_io.read_sidecar(sidecar_path)
    anno_io.write_sidecar(
        sidecar_path,
        replace(
            sidecar,
            annotations=(
                _ann("a1", "proposition:broad", stance="asserted"),
                _ann("b1", "proposition:broad", stance="negated"),
            ),
        ),
    )
    (tmp_path / "entities" / "papers" / "B2021.source.anno.trig").unlink()
    payload = _draft_payload(ctx)
    payload["annotation_assignments"][1]["annotation"] = "annotation:entities/papers/A2020.source#b1"
    action = replace(
        ctx["action"],
        inputs={
            **ctx["action"].inputs,
            "annotations": (
                "annotation:entities/papers/A2020.source#a1",
                "annotation:entities/papers/A2020.source#b1",
            ),
        },
    )
    plan = replace(ctx["plan"], actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)
    draft = parse_resynthesis_draft(payload)

    preflight = plan_resynthesis_apply(tmp_path, draft, as_of=date(2026, 7, 1))

    sidecar_edits = [
        edit for edit in preflight.file_edits if edit.path.as_posix().endswith(".source.anno.trig")
    ]
    assert len(sidecar_edits) == 1
    assert sidecar_edits[0].path == sidecar_path
    assert "proposition:broad-positive" in sidecar_edits[0].final_text
    assert "proposition:broad-negative" in sidecar_edits[0].final_text


def test_plan_resynthesis_apply_rejects_annotation_drift_to_third_target(tmp_path: Path, monkeypatch):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        plan_resynthesis_apply,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: ctx["plan"])
    sidecar_path = tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    sidecar = anno_io.read_sidecar(sidecar_path)
    anno_io.write_sidecar(
        sidecar_path,
        replace(
            sidecar,
            annotations=tuple(
                replace(annotation, promoted_to="proposition:third")
                if annotation.id == "a1"
                else annotation
                for annotation in sidecar.annotations
            ),
        ),
    )
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    with pytest.raises(ResynthesisApplyError, match="is not from or to proposition"):
        plan_resynthesis_apply(tmp_path, draft, as_of=date(2026, 7, 1))


def test_plan_resynthesis_apply_keeps_original_active_for_split_partial(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis_apply import plan_resynthesis_apply

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    payload["new_propositions"] = payload["new_propositions"][:1]
    payload["annotation_assignments"][1]["to"] = "proposition:broad"
    draft = parse_resynthesis_draft(payload)

    preflight = plan_resynthesis_apply(tmp_path, draft, as_of=date(2026, 7, 1))

    assert preflight.expected_original_state == {}
    assert not any(edit.path.name == "broad.md" for edit in preflight.file_edits)
    sidecar_a_edit = _edit_by_suffix(preflight, "entities/papers/A2020.source.anno.trig")
    assert "proposition:broad-positive" in sidecar_a_edit.final_text
    sidecar_b_edit = _edit_by_suffix(preflight, "entities/papers/B2021.source.anno.trig")
    assert sidecar_b_edit.changed is False
    original_frontmatter, _body = parse_markdown_entity_file(tmp_path / "entities" / "propositions" / "broad.md")
    assert original_frontmatter["status"] == "active"
