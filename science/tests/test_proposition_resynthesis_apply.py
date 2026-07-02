import hashlib
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from science_tool.annotation import io as anno_io
from science_tool.annotation import proposition_resynthesis_apply as apply_module
from science_tool.annotation.cross_paper_evidence import build_cross_paper_evidence_report
from science_tool.annotation.model import Status
from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, render_replacement_proposition
from science_tool.annotation.query import read_sidecar_strict
from science_tool.entities import parse_markdown_entity_file, render_entity_frontmatter_updates

from test_proposition_resynthesis import _CREATED, _ann, _draft_payload, _factorization_project, _paper_sidecar


def _edit_by_suffix(preflight, suffix: str):
    matches = [edit for edit in preflight.file_edits if edit.path.as_posix().endswith(suffix)]
    assert len(matches) == 1
    return matches[0]


def _paths_for_reason(preflight, reason: str) -> list[Path]:
    return [edit.path for edit in preflight.file_edits if edit.reason == reason]


def _snapshot_path(tmp_path: Path, action_id: str) -> Path:
    digest = hashlib.sha256(action_id.encode()).hexdigest()[:16]
    return tmp_path / "results" / "annotation" / "proposition-resynthesis" / f"{digest}.json"


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
    snapshot_edit = _edit_by_suffix(
        preflight,
        f"results/annotation/proposition-resynthesis/{hashlib.sha256(draft.action_id.encode()).hexdigest()[:16]}.json",
    )

    assert snapshot_edit.reason == "resynthesis_resume_snapshot"
    assert snapshot_edit.path == _snapshot_path(tmp_path, draft.action_id)
    assert snapshot_edit.changed is True
    snapshot_payload = json.loads(snapshot_edit.final_text)
    assert snapshot_payload == {
        "action_id": draft.action_id,
        "annotation_assignments": [
            {
                "annotation": "annotation:entities/papers/A2020.source#a1",
                "from": "proposition:broad",
                "to": "proposition:broad-positive",
            },
            {
                "annotation": "annotation:entities/papers/B2021.source#b1",
                "from": "proposition:broad",
                "to": "proposition:broad-negative",
            },
        ],
        "candidate_id": draft.candidate_id,
        "disposition": "replace",
        "input_annotations": [
            "annotation:entities/papers/A2020.source#a1",
            "annotation:entities/papers/B2021.source#b1",
        ],
        "judgment_id": draft.judgment_id,
        "original_proposition": "proposition:broad",
        "replacement_propositions": [
            "proposition:broad-positive",
            "proposition:broad-negative",
        ],
        "schema_version": 1,
        "source_review": draft.source_review,
    }
    assert snapshot_edit.final_text == json.dumps(snapshot_payload, sort_keys=True, indent=2) + "\n"

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

    assert [edit.reason for edit in preflight.file_edits] == [
        "resynthesis_resume_snapshot",
        "replacement_proposition",
        "replacement_proposition",
        "annotation_promoted_to_rewrite",
        "annotation_promoted_to_rewrite",
        "original_resynthesis_lineage",
    ]
    assert _paths_for_reason(preflight, "replacement_proposition") == sorted(
        _paths_for_reason(preflight, "replacement_proposition")
    )
    assert _paths_for_reason(preflight, "annotation_promoted_to_rewrite") == sorted(
        _paths_for_reason(preflight, "annotation_promoted_to_rewrite")
    )


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
    payload["input_annotations"][1] = "annotation:entities/papers/A2020.source#b1"
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


def test_apply_resynthesis_draft_ignores_inactive_original_backlink_outside_inputs(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    inactive_sidecar_path = _paper_sidecar(
        tmp_path,
        "C2022",
        (
            replace(
                _ann("inactive", "proposition:broad"),
                status=Status.FIXED,
                modified=_CREATED,
                modified_by="test",
            ),
        ),
    )
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad-positive"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad-negative"
    inactive_annotation = read_sidecar_strict(inactive_sidecar_path).annotations[0]
    assert inactive_annotation.status == Status.FIXED
    assert inactive_annotation.promoted_to == "proposition:broad"


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


def test_apply_resynthesis_draft_second_run_is_noop_and_preserves_dates(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    first = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))
    second = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 2))

    assert first.changed_paths
    assert _snapshot_path(tmp_path, draft.action_id).exists()
    assert second.status == "ok"
    assert second.changed_paths == ()
    assert second.written_paths == ()
    assert second.noop_paths
    assert _snapshot_path(tmp_path, draft.action_id).as_posix() in second.noop_paths
    positive_frontmatter, _positive_body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad-positive.md"
    )
    assert str(positive_frontmatter["created"]) == "2026-07-01"
    assert str(positive_frontmatter["updated"]) == "2026-07-01"


def test_apply_resynthesis_draft_first_run_rejects_manual_only_extra_replacement(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["new_propositions"].append(
        {
            "id": "proposition:broad-extra",
            "title": "BES requires an extra manual-only replacement",
            "body": "This replacement has no moved input annotations.",
            "frontmatter": {
                "subject": "BES",
                "predicate": "associates_with",
                "object": "manual-only replacement",
                "polarity": "positive",
                "source_refs": ["manual:extra-note"],
            },
        }
    )
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisApplyError, match="replacement propositions must match assigned annotation targets"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))


def test_apply_resynthesis_draft_resume_rejects_manual_only_extra_replacement(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    payload = _draft_payload(ctx)
    extra_replacement = {
        "id": "proposition:broad-extra",
        "title": "BES requires an extra manual-only replacement",
        "body": "This replacement has no moved input annotations.",
        "frontmatter": {
            "subject": "BES",
            "predicate": "associates_with",
            "object": "manual-only replacement",
            "polarity": "positive",
            "source_refs": ["manual:extra-note"],
        },
    }
    payload["new_propositions"].append(extra_replacement)
    tampered_draft = parse_resynthesis_draft(payload)
    rendered_extra = render_replacement_proposition(
        tmp_path,
        tampered_draft.new_propositions[-1],
        ("manual:extra-note",),
        as_of=date(2026, 7, 2),
    )
    rendered_extra.path.write_text(rendered_extra.text, encoding="utf-8")

    with pytest.raises(ResynthesisApplyError, match="replacement.*annotation|snapshot"):
        apply_resynthesis_draft(tmp_path, tampered_draft, as_of=date(2026, 7, 2))

    original_frontmatter, _body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["resynthesized_into"] == [
        "proposition:broad-negative",
        "proposition:broad-positive",
    ]


def test_apply_resynthesis_draft_resume_rejects_tampered_extra_replacement_snapshot_mismatch(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    payload = _draft_payload(ctx)
    extra_replacement = {
        "id": "proposition:broad-extra",
        "title": "BES requires an extra replacement",
        "body": "This replacement redirects the B2021 annotation after the original apply.",
        "frontmatter": {
            "subject": "BES",
            "predicate": "associates_with",
            "object": "post-apply replacement",
            "polarity": "positive",
            "source_refs": ["annotation:entities/papers/B2021.source#b1", "paper:B2021"],
        },
    }
    payload["new_propositions"] = [payload["new_propositions"][0], extra_replacement]
    payload["annotation_assignments"][1]["to"] = "proposition:broad-extra"
    tampered_draft = parse_resynthesis_draft(payload)
    rendered_extra = render_replacement_proposition(
        tmp_path,
        tampered_draft.new_propositions[-1],
        ("annotation:entities/papers/B2021.source#b1", "paper:B2021"),
        as_of=date(2026, 7, 2),
    )
    rendered_extra.path.write_text(rendered_extra.text, encoding="utf-8")
    b_sidecar_path = tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    b_sidecar = anno_io.read_sidecar(b_sidecar_path)
    anno_io.write_sidecar(
        b_sidecar_path,
        replace(
            b_sidecar,
            annotations=tuple(
                replace(annotation, promoted_to="proposition:broad-extra")
                if annotation.id == "b1"
                else annotation
                for annotation in b_sidecar.annotations
            ),
        ),
    )

    with pytest.raises(ResynthesisApplyError, match="resume snapshot.*mismatch"):
        apply_resynthesis_draft(tmp_path, tampered_draft, as_of=date(2026, 7, 2))

    original_frontmatter, _body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["resynthesized_into"] == [
        "proposition:broad-negative",
        "proposition:broad-positive",
    ]


def test_apply_resynthesis_draft_resume_uses_snapshot_when_review_decision_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))
    positive_path = tmp_path / "entities" / "propositions" / "broad-positive.md"
    positive_text = positive_path.read_text(encoding="utf-8")
    review = ctx["review"]
    review["judgments"][0]["decision"] = "split_possible"
    ctx["review_path"].write_text(json.dumps(review), encoding="utf-8")
    writes: list[Path] = []

    def spy_atomic_write_text(path: Path, text: str) -> None:
        writes.append(path)

    monkeypatch.setattr(apply_module, "atomic_write_text", spy_atomic_write_text)

    report = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 2))

    assert report.status == "ok"
    assert writes == []
    assert positive_path.read_text(encoding="utf-8") == positive_text


def test_apply_resynthesis_draft_rejects_incomplete_replace_when_live_action_inputs_grew(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    c_sidecar_path = _paper_sidecar(
        tmp_path,
        "C2022",
        (_ann("c1", "proposition:broad", stance="asserted"),),
    )
    input_annotations = tuple(ctx["action"].inputs["annotations"]) + (
        "annotation:entities/papers/C2022.source#c1",
    )
    action = replace(
        ctx["action"],
        inputs={**ctx["action"].inputs, "annotations": input_annotations},
    )
    plan = replace(ctx["plan"], actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisApplyError, match="input_annotations are stale"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    assert not (tmp_path / "entities" / "propositions" / "broad-negative.md").exists()
    assert read_sidecar_strict(c_sidecar_path).annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_rejects_live_plan_error_before_prior_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=(str(ctx["review_path"]),),
        actions=(ctx["action"],),
        errors=({"reason": "scanner-fault"},),
    )
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    with pytest.raises(ResynthesisApplyError, match="action plan has top-level errors: scanner-fault"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    assert not (tmp_path / "entities" / "propositions" / "broad-negative.md").exists()
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_rejects_live_plan_error_after_prior_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

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
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=(str(ctx["review_path"]),),
        actions=(ctx["action"],),
        errors=({"reason": "scanner-fault"},),
    )
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    with pytest.raises(ResynthesisApplyError, match="action plan has top-level errors: scanner-fault"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    assert not (tmp_path / "entities" / "propositions" / "broad-negative.md").exists()
    original_frontmatter, _body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "active"
    assert read_sidecar_strict(sidecar_path).annotations[0].promoted_to == "proposition:broad-positive"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_resumes_when_one_sidecar_already_points_to_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft
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


def test_apply_resynthesis_draft_resumes_after_replacement_writes_and_one_sidecar_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft, plan_resynthesis_apply
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    preflight = plan_resynthesis_apply(tmp_path, draft, as_of=date(2026, 7, 1))
    for edit in preflight.file_edits:
        if edit.reason not in {"resynthesis_resume_snapshot", "replacement_proposition"}:
            continue
        edit.path.parent.mkdir(parents=True, exist_ok=True)
        edit.path.write_text(edit.final_text, encoding="utf-8")

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
    monkeypatch.setattr(
        resynthesis,
        "build_live_action_plan",
        lambda _root, _review: ReconciliationActionPlan(
            schema_version=1,
            source_reviews=(str(ctx["review_path"]),),
            actions=(),
        ),
    )

    report = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.status == "ok"
    assert sidecar_path.read_text(encoding="utf-8") == before_sidecar
    assert any(path.endswith("entities/papers/A2020.source.anno.trig") for path in report.noop_paths)
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad-negative"
    original_frontmatter, _body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "superseded"


def test_apply_resynthesis_draft_resume_uses_draft_input_annotations_not_original_source_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_resynthesis_apply import apply_resynthesis_draft
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
                replace(annotation, promoted_to="proposition:broad-positive")
                if annotation.id == "a1"
                else annotation
                for annotation in sidecar.annotations
            ),
        ),
    )
    original_path = tmp_path / "entities" / "propositions" / "broad.md"
    original_frontmatter, _body = parse_markdown_entity_file(original_path)
    rendered, changed = render_entity_frontmatter_updates(
        original_path,
        {
            "source_refs": [
                ref
                for ref in original_frontmatter["source_refs"]
                if not str(ref).startswith("annotation:")
            ]
        },
        as_of=date(2026, 7, 1),
    )
    assert changed is True
    original_path.write_text(rendered, encoding="utf-8")
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    report = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.status == "ok"
    assert read_sidecar_strict(sidecar_path).annotations[0].promoted_to == "proposition:broad-positive"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad-negative"


def test_apply_resynthesis_draft_resume_rejects_unreviewed_live_assignment(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    apply_resynthesis_draft(tmp_path, parse_resynthesis_draft(_draft_payload(ctx)), as_of=date(2026, 7, 1))
    c_sidecar_path = _paper_sidecar(
        tmp_path,
        "C2022",
        (_ann("c1", "proposition:broad", stance="asserted"),),
    )
    payload = _draft_payload(ctx)
    payload["annotation_assignments"].append(
        {
            "annotation": "annotation:entities/papers/C2022.source#c1",
            "from": "proposition:broad",
            "to": "proposition:broad-positive",
        }
    )
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisApplyError, match="resume snapshot mismatch"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert read_sidecar_strict(c_sidecar_path).annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_resume_rejects_tampered_input_without_replacement_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    for citekey, annotation_id, target in (
        ("A2020", "a1", "proposition:broad-positive"),
        ("B2021", "b1", "proposition:broad-negative"),
    ):
        sidecar_path = tmp_path / "entities" / "papers" / f"{citekey}.source.anno.trig"
        sidecar = anno_io.read_sidecar(sidecar_path)
        anno_io.write_sidecar(
            sidecar_path,
            replace(
                sidecar,
                annotations=tuple(
                    replace(annotation, promoted_to=target)
                    if annotation.id == annotation_id
                    else annotation
                    for annotation in sidecar.annotations
                ),
            ),
        )
    c_sidecar_path = _paper_sidecar(
        tmp_path,
        "C2022",
        (_ann("c1", "proposition:broad", stance="asserted"),),
    )
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=(str(ctx["review_path"]),),
        actions=(),
    )
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)
    payload = _draft_payload(ctx)
    payload["input_annotations"].append("annotation:entities/papers/C2022.source#c1")
    payload["context"]["input_annotations"].append("annotation:entities/papers/C2022.source#c1")
    payload["annotation_assignments"].append(
        {
            "annotation": "annotation:entities/papers/C2022.source#c1",
            "from": "proposition:broad",
            "to": "proposition:broad-positive",
        }
    )
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisApplyError, match="resume snapshot missing"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    assert read_sidecar_strict(c_sidecar_path).annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_resume_rejects_tampered_extra_input_snapshot_mismatch(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))
    c_sidecar_path = _paper_sidecar(
        tmp_path,
        "C2022",
        (_ann("c1", "proposition:broad", stance="asserted"),),
    )
    c_sidecar = anno_io.read_sidecar(c_sidecar_path)
    anno_io.write_sidecar(
        c_sidecar_path,
        replace(
            c_sidecar,
            annotations=tuple(
                replace(annotation, promoted_to="proposition:broad-positive")
                if annotation.id == "c1"
                else annotation
                for annotation in c_sidecar.annotations
            ),
        ),
    )
    positive_path = tmp_path / "entities" / "propositions" / "broad-positive.md"
    positive_frontmatter, _body = parse_markdown_entity_file(positive_path)
    rendered, changed = render_entity_frontmatter_updates(
        positive_path,
        {
            "source_refs": [
                *positive_frontmatter["source_refs"],
                "paper:C2022",
                "annotation:entities/papers/C2022.source#c1",
            ]
        },
        as_of=date(2026, 7, 2),
    )
    assert changed is True
    positive_path.write_text(rendered, encoding="utf-8")

    payload = _draft_payload(ctx)
    payload["input_annotations"].append("annotation:entities/papers/C2022.source#c1")
    payload["context"]["input_annotations"].append("annotation:entities/papers/C2022.source#c1")
    payload["annotation_assignments"].append(
        {
            "annotation": "annotation:entities/papers/C2022.source#c1",
            "from": "proposition:broad",
            "to": "proposition:broad-positive",
        }
    )
    tampered_draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisApplyError, match="resume snapshot.*mismatch"):
        apply_resynthesis_draft(tmp_path, tampered_draft, as_of=date(2026, 7, 2))

    assert read_sidecar_strict(c_sidecar_path).annotations[0].promoted_to == "proposition:broad-positive"


def test_apply_resynthesis_draft_resume_rejects_missing_context_input_annotations(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis import ResynthesisDraftError

    ctx = _factorization_project(tmp_path)

    payload = _draft_payload(ctx)
    del payload["input_annotations"]

    with pytest.raises(ResynthesisDraftError, match="input_annotations"):
        parse_resynthesis_draft(payload)


def test_apply_resynthesis_draft_resume_rejects_omitted_input_annotation_before_superseding_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

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
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=(str(ctx["review_path"]),),
        actions=(),
    )
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)
    payload = _draft_payload(ctx)
    payload["input_annotations"] = payload["input_annotations"][:1]
    payload["context"]["input_annotations"] = payload["context"]["input_annotations"][:1]
    payload["new_propositions"] = payload["new_propositions"][:1]
    payload["annotation_assignments"] = payload["annotation_assignments"][:1]
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(
        ResynthesisApplyError,
        match=(
            "input_annotations are stale|assign every input annotation|remains promoted_to original|"
            "input annotation snapshot is incomplete|resume snapshot missing"
        ),
    ):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    original_frontmatter, _body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "active"
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_resume_rejects_omitted_already_moved_assignment_before_writes(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    for citekey, annotation_id, target in (
        ("A2020", "a1", "proposition:broad-positive"),
        ("B2021", "b1", "proposition:broad-negative"),
    ):
        sidecar_path = tmp_path / "entities" / "papers" / f"{citekey}.source.anno.trig"
        sidecar = anno_io.read_sidecar(sidecar_path)
        anno_io.write_sidecar(
            sidecar_path,
            replace(
                sidecar,
                annotations=tuple(
                    replace(annotation, promoted_to=target)
                    if annotation.id == annotation_id
                    else annotation
                    for annotation in sidecar.annotations
                ),
            ),
        )
    before_b_sidecar = (tmp_path / "entities" / "papers" / "B2021.source.anno.trig").read_text(
        encoding="utf-8"
    )
    payload = _draft_payload(ctx)
    payload["new_propositions"] = payload["new_propositions"][:1]
    payload["annotation_assignments"] = payload["annotation_assignments"][:1]
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(
        ResynthesisApplyError,
        match=(
            "input_annotations are stale|input annotation snapshot is incomplete|"
            "assign every input annotation|resume snapshot missing"
        ),
    ):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    original_frontmatter, _body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "active"
    assert "resynthesized_into" not in original_frontmatter
    assert (tmp_path / "entities" / "papers" / "B2021.source.anno.trig").read_text(
        encoding="utf-8"
    ) == before_b_sidecar


def test_apply_resynthesis_draft_resume_rejects_assignment_only_in_original_source_refs(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    for citekey, annotation_id, target in (
        ("A2020", "a1", "proposition:broad-positive"),
        ("B2021", "b1", "proposition:broad-negative"),
    ):
        sidecar_path = tmp_path / "entities" / "papers" / f"{citekey}.source.anno.trig"
        sidecar = anno_io.read_sidecar(sidecar_path)
        anno_io.write_sidecar(
            sidecar_path,
            replace(
                sidecar,
                annotations=tuple(
                    replace(annotation, promoted_to=target)
                    if annotation.id == annotation_id
                    else annotation
                    for annotation in sidecar.annotations
                ),
            ),
        )
    c_sidecar_path = _paper_sidecar(
        tmp_path,
        "C2022",
        (_ann("c1", "proposition:broad", stance="asserted"),),
    )
    original_path = tmp_path / "entities" / "propositions" / "broad.md"
    original_frontmatter, _body = parse_markdown_entity_file(original_path)
    rendered, changed = render_entity_frontmatter_updates(
        original_path,
        {
            "source_refs": [
                *original_frontmatter["source_refs"],
                "paper:C2022",
                "annotation:entities/papers/C2022.source#c1",
            ]
        },
        as_of=date(2026, 7, 1),
    )
    assert changed is True
    original_path.write_text(rendered, encoding="utf-8")

    payload = _draft_payload(ctx)
    payload["annotation_assignments"].append(
        {
            "annotation": "annotation:entities/papers/C2022.source#c1",
            "from": "proposition:broad",
            "to": "proposition:broad-positive",
        }
    )
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisApplyError):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert read_sidecar_strict(c_sidecar_path).annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_resume_rejects_missing_snapshot_with_prior_sidecar_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    expected_refs_by_replacement = {
        "proposition:broad-positive": (
            "annotation:entities/papers/A2020.source#a1",
            "manual:curator-note",
            "paper:A2020",
        ),
        "proposition:broad-negative": (
            "annotation:entities/papers/B2021.source#b1",
            "paper:B2021",
        ),
    }
    for replacement in draft.new_propositions:
        rendered = render_replacement_proposition(
            tmp_path,
            replacement,
            expected_refs_by_replacement[replacement.id],
            as_of=date(2026, 7, 1),
        )
        rendered.path.write_text(rendered.text, encoding="utf-8")
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
    monkeypatch.setattr(
        resynthesis,
        "build_live_action_plan",
        lambda _root, _review: ReconciliationActionPlan(
            schema_version=1,
            source_reviews=(str(ctx["review_path"]),),
            actions=(),
        ),
    )

    with pytest.raises(ResynthesisApplyError, match="resume snapshot.*missing"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    original_frontmatter, _body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "active"


def test_apply_resynthesis_draft_rejects_stale_candidate_id_without_writes(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["candidate_id"] = "factorization:stale"
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisApplyError, match="draft candidate_id is stale"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    assert read_sidecar_strict(
        tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    ).annotations[0].promoted_to == "proposition:broad"


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


def test_apply_resynthesis_draft_split_partial_resume_rejects_omitted_original_annotation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    payload["new_propositions"] = payload["new_propositions"][:1]
    payload["annotation_assignments"][1]["to"] = "proposition:broad"

    moved_sidecar_path = tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    moved_sidecar = anno_io.read_sidecar(moved_sidecar_path)
    anno_io.write_sidecar(
        moved_sidecar_path,
        replace(
            moved_sidecar,
            annotations=tuple(
                replace(annotation, promoted_to="proposition:broad-positive")
                if annotation.id == "a1"
                else annotation
                for annotation in moved_sidecar.annotations
            ),
        ),
    )
    omitted_sidecar_path = _paper_sidecar(
        tmp_path,
        "C2022",
        (_ann("c1", "proposition:broad", stance="asserted"),),
    )
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=(str(ctx["review_path"]),),
        actions=(),
    )
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(
        ResynthesisApplyError,
        match=(
            "split_partial must assign every input annotation|"
            "input annotation snapshot is incomplete|resume snapshot missing"
        ),
    ):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    original_frontmatter, _body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "active"
    assert read_sidecar_strict(moved_sidecar_path).annotations[0].promoted_to == "proposition:broad-positive"
    assert read_sidecar_strict(omitted_sidecar_path).annotations[0].promoted_to == "proposition:broad"


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

    with pytest.raises(ResynthesisApplyError, match="replacement propositions must match assigned annotation targets"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert writes == []
    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    original_frontmatter, _original_body = parse_markdown_entity_file(
        tmp_path / "entities" / "propositions" / "broad.md"
    )
    assert original_frontmatter["status"] == "active"


def test_apply_resynthesis_draft_postflight_rejects_corrupted_planned_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from science_tool.annotation.proposition_resynthesis_apply import (
        ResynthesisApplyError,
        apply_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    original_atomic_write_text = apply_module.atomic_write_text

    def corrupt_positive_replacement(path: Path, text: str) -> None:
        if path.name == "broad-positive.md":
            text = text.replace(
                "BES can behave similarly to meta-analysis when evidence is informative.",
                "BES can behave similarly to meta-analysis when evidence is informative. Corrupted.",
            )
        original_atomic_write_text(path, text)

    monkeypatch.setattr(apply_module, "atomic_write_text", corrupt_positive_replacement)

    with pytest.raises(ResynthesisApplyError, match="postflight.*hash|planned file state"):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))
