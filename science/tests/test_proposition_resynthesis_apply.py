from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from science_tool.annotation import io as anno_io
from science_tool.annotation import proposition_resynthesis_apply as apply_module
from science_tool.annotation.cross_paper_evidence import build_cross_paper_evidence_report
from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft
from science_tool.annotation.query import read_sidecar_strict
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


def test_apply_resynthesis_draft_creates_files_rewrites_sidecars_and_supersedes_original(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        apply_resynthesis_draft,
        apply_resynthesis_report_to_json,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    report = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.status == "ok"
    assert report.original_proposition == "proposition:broad"
    assert report.replacement_propositions == (
        "proposition:broad-negative",
        "proposition:broad-positive",
    )
    assert report.rewritten_annotations == (
        "annotation:entities/papers/A2020.source#a1",
        "annotation:entities/papers/B2021.source#b1",
    )
    assert report.original_state == {
        "status": "superseded",
        "resynthesized_into": ["proposition:broad-negative", "proposition:broad-positive"],
    }
    assert any(path.endswith("entities/propositions/broad-positive.md") for path in report.written_paths)
    assert any(path.endswith("entities/propositions/broad-negative.md") for path in report.written_paths)
    assert any(path.endswith("entities/propositions/broad.md") for path in report.written_paths)
    assert any(path.endswith("entities/papers/A2020.source.anno.trig") for path in report.written_paths)
    assert any(path.endswith("entities/papers/B2021.source.anno.trig") for path in report.written_paths)

    positive_frontmatter, _positive_body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad-positive.md"
    )
    assert positive_frontmatter["status"] == "active"
    assert positive_frontmatter["source_refs"] == [
        "manual:curator-note",
        "annotation:entities/papers/A2020.source#a1",
        "paper:A2020",
    ]
    original_frontmatter, _original_body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "superseded"
    assert original_frontmatter["resynthesized_into"] == [
        "proposition:broad-negative",
        "proposition:broad-positive",
    ]
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad-positive"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad-negative"

    payload = apply_resynthesis_report_to_json(report, project_root=tmp_path)
    assert payload["schema_version"] == 1
    assert payload["summary"]["replacement_propositions"] == 2
    assert payload["summary"]["rewritten_annotations"] == 2
    assert payload["summary"]["written_paths"] == len(report.written_paths)
    assert all(not path.startswith("/") for path in payload["written_paths"])


def test_apply_resynthesis_draft_second_run_is_noop_and_preserves_dates(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    first = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))
    second = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 2))

    assert first.changed_paths
    assert second.status == "ok"
    assert second.changed_paths == ()
    assert second.written_paths == ()
    assert second.noop_paths
    positive_frontmatter, _positive_body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad-positive.md"
    )
    assert str(positive_frontmatter["created"]) == "2026-07-01"
    assert str(positive_frontmatter["updated"]) == "2026-07-01"


def test_apply_resynthesis_draft_resumes_when_one_sidecar_already_points_to_target(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    sidecar_path = tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    sidecar = anno_io.read_sidecar(sidecar_path)
    anno_io.write_sidecar(
        sidecar_path,
        replace(
            sidecar,
            annotations=tuple(
                replace(annotation, promoted_to="proposition:broad-positive")
                if annotation.id == "a1"
                else annotation
                for annotation in sidecar.annotations
            ),
        ),
    )
    before_sidecar = sidecar_path.read_text(encoding="utf-8")
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    report = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert sidecar_path.read_text(encoding="utf-8") == before_sidecar
    assert any(path.endswith("entities/papers/A2020.source.anno.trig") for path in report.noop_paths)
    assert not any(path.endswith("entities/papers/A2020.source.anno.trig") for path in report.written_paths)
    assert read_sidecar_strict(sidecar_path).annotations[0].promoted_to == "proposition:broad-positive"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad-negative"


def test_apply_resynthesis_draft_split_partial_keeps_original_active(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    payload["new_propositions"] = payload["new_propositions"][:1]
    payload["annotation_assignments"][1]["to"] = "proposition:broad"
    draft = parse_resynthesis_draft(payload)

    report = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.original_state == {}
    assert not any(path.endswith("entities/propositions/broad.md") for path in report.written_paths)
    original_frontmatter, _original_body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "active"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad-positive"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_cross_paper_evidence_moves_to_replacements(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    positive = build_cross_paper_evidence_report(tmp_path, proposition_ref="proposition:broad-positive")
    broad = build_cross_paper_evidence_report(tmp_path, proposition_ref="proposition:broad")
    assert len(positive["units"]) == 1
    assert len(broad["units"]) == 0


def test_apply_resynthesis_draft_preflight_failure_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["annotation_assignments"][1]["to"] = "proposition:broad-positive"
    draft = parse_resynthesis_draft(payload)
    writes: list[Path] = []

    def spy_atomic_write_text(path: Path, text: str) -> None:
        writes.append(path)

    monkeypatch.setattr(apply_module, "atomic_write_text", spy_atomic_write_text)

    with pytest.raises(ResynthesisApplyError, match="replacement proposition has no source refs"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert writes == []
    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    original_frontmatter, _original_body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "active"
