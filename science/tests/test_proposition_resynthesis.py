import json
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.proposition_reconciliation import (
    build_reconciliation_report,
    judgment_id,
)
from science_tool.annotation.proposition_reconciliation_plan import (
    ReviewedReconciliationInput,
    build_reconciliation_action_plan,
)
from science_tool.annotation.proposition_resynthesis import (
    RESYNTHESIS_SCHEMA_VERSION,
    ResynthesisDraftError,
    build_resynthesis_scaffold,
    draft_to_json,
    resolve_resynthesis_action,
)
from science_tool.entities import parse_markdown_entity_file

_CREATED = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _manifest(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _proposition(
    root: Path,
    slug: str,
    title: str,
    *,
    source_refs: tuple[str, ...] = (),
    status: str = "active",
    subject: str | None = None,
    predicate: str | None = None,
    object_: str | None = None,
    polarity: str | None = None,
) -> Path:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    refs = "".join(f"  - {ref}\n" for ref in source_refs)
    optional = ""
    if subject is not None:
        optional += f"subject: {subject}\n"
    if predicate is not None:
        optional += f"predicate: {predicate}\n"
    if object_ is not None:
        optional += f"object: {object_}\n"
    if polarity is not None:
        optional += f"polarity: {polarity}\n"
    path.write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        "type: proposition\n"
        f"title: {title}\n"
        f"status: {status}\n"
        f"{optional}"
        "source_refs:\n"
        f"{refs}"
        'created: "2026-06-01"\n'
        'updated: "2026-06-01"\n'
        "---\n\n"
        f"# {title}\n\n"
        "Claim body.\n",
        encoding="utf-8",
    )
    return path


def _ann(annotation_id: str, promoted_to: str, *, stance: str = "asserted") -> Annotation:
    body = json.dumps({"section": "results", "stance": stance})
    return Annotation(
        id=annotation_id,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=annotation_id, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1",
        status=Status.OPEN,
        creator="paper-annotate",
        created=_CREATED,
        content_hash="0" * 64,
        promoted_to=promoted_to,
    )


def _paper_sidecar(root: Path, citekey: str, annotations: tuple[Annotation, ...]) -> Path:
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Results show the claim.\n", encoding="utf-8")
    sidecar_path = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sidecar_path, Sidecar(annotations=annotations))
    return sidecar_path


def _factorization_project(root: Path) -> dict:
    _manifest(root)
    _proposition(
        root,
        "broad",
        "BES behaves like pooled meta-analysis",
        source_refs=(
            "paper:A2020",
            "annotation:entities/papers/A2020.source#a1",
            "paper:B2021",
            "annotation:entities/papers/B2021.source#b1",
        ),
    )
    _paper_sidecar(root, "A2020", (_ann("a1", "proposition:broad", stance="asserted"),))
    _paper_sidecar(root, "B2021", (_ann("b1", "proposition:broad", stance="negated"),))
    report = build_reconciliation_report(root)
    candidate = report.factorization_disagreements[0]
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id(
                    "factorization_disagreement",
                    "factorization_needs_resynthesis",
                    [candidate.proposition],
                ),
                "lane": "factorization_disagreement",
                "decision": "factorization_needs_resynthesis",
                "proposition": candidate.proposition,
                "rationale": "The broad proposition mixes distinct literature claims.",
                "confidence": "high",
            }
        ],
    }
    review_path = root / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    plan = build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path=str(review_path), doc=review)],
    )
    action = [row for row in plan.actions if row.kind == "resynthesize_proposition"][0]
    return {"review_path": review_path, "report": report, "review": review, "plan": plan, "action": action}


def test_resolve_resynthesis_action_auto_selects_single_ready_action(tmp_path: Path):
    ctx = _factorization_project(tmp_path)

    selected = resolve_resynthesis_action(ctx["plan"], requested_action_id=None)

    assert selected.action_id == ctx["action"].action_id
    assert selected.kind == "resynthesize_proposition"
    assert selected.status == "ready"


def test_resolve_resynthesis_action_requires_action_when_multiple_ready(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    duplicated = replace(ctx["action"], action_id="reconcile-action:second")
    plan = replace(ctx["plan"], actions=(ctx["action"], duplicated))

    with pytest.raises(ResynthesisDraftError, match="multiple ready resynthesize_proposition actions"):
        resolve_resynthesis_action(plan, requested_action_id=None)


def test_resolve_resynthesis_action_rejects_non_resynthesis_action(tmp_path: Path):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan

    ctx = _factorization_project(tmp_path)
    action = replace(ctx["action"], kind="canonicalize_propositions")
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(action,))

    with pytest.raises(ResynthesisDraftError, match="not ready resynthesize_proposition"):
        resolve_resynthesis_action(plan, requested_action_id=action.action_id)


def test_build_resynthesis_scaffold_emits_identity_context_and_empty_review_fields(tmp_path: Path):
    ctx = _factorization_project(tmp_path)

    draft = build_resynthesis_scaffold(
        ctx["plan"],
        requested_action_id=ctx["action"].action_id,
        source_review=str(ctx["review_path"]),
        model="codex-gpt-5",
    )
    payload = draft_to_json(draft)

    assert payload["schema_version"] == RESYNTHESIS_SCHEMA_VERSION
    assert payload["source"] == "llm-review:codex-gpt-5:proposition-resynthesis-v1"
    assert payload["action_id"] == ctx["action"].action_id
    assert payload["candidate_id"] == ctx["action"].candidate_id
    assert payload["judgment_id"] == ctx["action"].judgment_id
    assert payload["source_review"] == str(ctx["review_path"])
    assert payload["original_proposition"] == "proposition:broad"
    assert payload["disposition"] == "replace"
    assert payload["new_propositions"] == []
    assert payload["annotation_assignments"] == []
    assert payload["context"]["observed_statement_hints"] == list(ctx["action"].inputs["observed_statement_hints"])


def _draft_payload(ctx: dict) -> dict:
    return {
        "schema_version": 1,
        "source": "llm-review:codex-gpt-5:proposition-resynthesis-v1",
        "action_id": ctx["action"].action_id,
        "candidate_id": ctx["action"].candidate_id,
        "judgment_id": ctx["action"].judgment_id,
        "source_review": str(ctx["review_path"]),
        "original_proposition": "proposition:broad",
        "disposition": "replace",
        "new_propositions": [
            {
                "id": "proposition:broad-positive",
                "title": "BES can behave like meta-analysis under informative evidence",
                "body": "BES can behave similarly to meta-analysis when evidence is informative.",
                "frontmatter": {
                    "subject": "BES",
                    "predicate": "associates_with",
                    "object": "meta-analysis behavior",
                    "polarity": "positive",
                    "source_refs": ["manual:curator-note"],
                },
            },
            {
                "id": "proposition:broad-negative",
                "title": "BES can differ from data pooling under weak evidence",
                "body": "BES can differ from data pooling when study evidence is weak.",
                "frontmatter": {
                    "subject": "BES",
                    "predicate": "associates_with",
                    "object": "data-pooling behavior",
                    "polarity": "negative",
                },
            },
        ],
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
        "context": {},
        "notes": "",
    }


def test_parse_resynthesis_draft_rejects_invalid_source(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["source"] = "llm-synth:wrong"

    with pytest.raises(ResynthesisDraftError, match="source"):
        parse_resynthesis_draft(payload)


def test_validate_resynthesis_draft_accepts_complete_replace(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        validate_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    report = validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.status == "ok"
    assert report.original_proposition == "proposition:broad"
    assert report.replacement_propositions == 2
    assert report.moved_annotations == 2
    assert report.retained_annotations == 0
    assert report.errors == ()
    assert report.expected_annotation_targets == {
        "annotation:entities/papers/A2020.source#a1": "proposition:broad-positive",
        "annotation:entities/papers/B2021.source#b1": "proposition:broad-negative",
    }


def test_validate_resynthesis_draft_rejects_unknown_frontmatter_key(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["new_propositions"][0]["frontmatter"]["made_up_field"] = "bad"
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="unknown proposition frontmatter key"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_duplicate_annotation_assignment(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["annotation_assignments"].append(dict(payload["annotation_assignments"][0]))
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="assigned more than once"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_assignment_to_unknown_target(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["annotation_assignments"][0]["to"] = "proposition:not-in-draft"
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="not a draft proposition"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_incomplete_replace_when_input_set_grew(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    _paper_sidecar(tmp_path, "C2022", (_ann("c1", "proposition:broad", stance="asserted"),))

    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="replace must assign every input annotation"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_allows_split_partial_with_retained_original(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    payload["annotation_assignments"][1]["to"] = "proposition:broad"
    draft = parse_resynthesis_draft(payload)

    report = validate_resynthesis_draft(tmp_path, draft)

    assert report.status == "ok"
    assert report.moved_annotations == 1
    assert report.retained_annotations == 1


def test_render_replacement_preserves_existing_created_updated_for_idempotent_compare(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        render_replacement_proposition,
        validate_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    report = validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))
    replacement = draft.new_propositions[0]
    rendered = render_replacement_proposition(
        tmp_path,
        replacement,
        sorted(report.expected_source_refs_by_replacement[replacement.id]),
        as_of=date(2026, 7, 1),
    )
    path = tmp_path / "entities" / "propositions" / "broad-positive.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered.text.replace("2026-07-01", "2026-06-30"), encoding="utf-8")

    rerendered = render_replacement_proposition(
        tmp_path,
        replacement,
        sorted(report.expected_source_refs_by_replacement[replacement.id]),
        as_of=date(2026, 7, 2),
    )

    assert rerendered.path == path
    assert rerendered.changed is False
    frontmatter, _body = parse_markdown_entity_file(path)
    assert str(frontmatter["created"]) == "2026-06-30"
    assert str(frontmatter["updated"]) == "2026-06-30"
