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
    assert draft.input_annotations == tuple(ctx["action"].inputs["annotations"])
    assert payload["input_annotations"] == list(ctx["action"].inputs["annotations"])
    assert payload["new_propositions"] == []
    assert payload["annotation_assignments"] == []
    assert payload["context"]["observed_statement_hints"] == list(ctx["action"].inputs["observed_statement_hints"])


def test_build_resynthesis_context_packet_expands_scaffold_with_live_context(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(
        draft_to_json(
            build_resynthesis_scaffold(
                ctx["plan"],
                requested_action_id=ctx["action"].action_id,
                source_review=str(ctx["review_path"]),
                model="codex-gpt-5",
            )
        )
    )

    packet = build_resynthesis_context_packet(
        tmp_path,
        draft,
        draft_path="resynthesis-draft.json",
    )

    assert packet["schema_version"] == 1
    assert packet["source"] == "derived:proposition-resynthesis-context-v1"
    assert packet["draft_path"] == "resynthesis-draft.json"
    assert packet["action_id"] == ctx["action"].action_id
    assert packet["candidate_id"] == ctx["action"].candidate_id
    assert packet["judgment_id"] == ctx["action"].judgment_id
    assert packet["original_proposition"]["id"] == "proposition:broad"
    assert packet["original_proposition"]["title"] == "BES behaves like pooled meta-analysis"
    assert "Claim body." in packet["original_proposition"]["body"]
    assert packet["original_proposition"]["frontmatter"] == {
        "subject": None,
        "predicate": None,
        "object": None,
        "polarity": None,
        "claim_layer": None,
        "identification_strength": None,
        "source_refs": [
            "paper:A2020",
            "annotation:entities/papers/A2020.source#a1",
            "paper:B2021",
            "annotation:entities/papers/B2021.source#b1",
        ],
    }
    assert packet["review"] == {
        "decision": "factorization_needs_resynthesis",
        "confidence": "high",
        "rationale": "The broad proposition mixes distinct literature claims.",
    }
    assert packet["input_annotations"] == [
        {
            "annotation": "annotation:entities/papers/A2020.source#a1",
            "paper": "paper:A2020",
            "stance": "asserted",
            "section": "results",
            "exact": "a1",
            "subject": None,
            "object": None,
            "subject_concept": None,
            "object_concept": None,
            "current_promoted_to": "proposition:broad",
        },
        {
            "annotation": "annotation:entities/papers/B2021.source#b1",
            "paper": "paper:B2021",
            "stance": "negated",
            "section": "results",
            "exact": "b1",
            "subject": None,
            "object": None,
            "subject_concept": None,
            "object_concept": None,
            "current_promoted_to": "proposition:broad",
        },
    ]
    assert packet["draft_progress"] == {
        "disposition": "replace",
        "new_propositions": [],
        "annotation_assignments": [],
        "notes": "",
    }
    assert packet["constraints"]["required_assignment_annotations"] == [
        "annotation:entities/papers/A2020.source#a1",
        "annotation:entities/papers/B2021.source#b1",
    ]
    assert packet["output_contract"]["validate_with"] == (
        "science annotate validate-proposition-resynthesis --input resynthesis-draft.json"
    )


def test_resynthesis_context_derives_constraints_has_no_timestamps_and_echoes_progress(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        ALLOWED_REPLACEMENT_FRONTMATTER_KEYS,
        RESYNTHESIS_DISPOSITIONS,
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["notes"] = "Reviewer wants a conservative split."
    draft = parse_resynthesis_draft(payload)

    packet = build_resynthesis_context_packet(tmp_path, draft, draft_path="draft.json")
    encoded = json.dumps(packet, sort_keys=True)

    assert packet["constraints"]["allowed_dispositions"] == sorted(RESYNTHESIS_DISPOSITIONS)
    assert packet["constraints"]["allowed_replacement_frontmatter_keys"] == sorted(
        ALLOWED_REPLACEMENT_FRONTMATTER_KEYS
    )
    assert packet["draft_progress"]["disposition"] == "replace"
    assert packet["draft_progress"]["new_propositions"] == payload["new_propositions"]
    assert packet["draft_progress"]["annotation_assignments"] == payload["annotation_assignments"]
    assert packet["draft_progress"]["notes"] == "Reviewer wants a conservative split."
    assert "2026-07-03" not in encoded
    assert "created" not in packet["original_proposition"]["frontmatter"]
    assert "updated" not in packet["original_proposition"]["frontmatter"]


def test_resynthesis_context_rejects_missing_observed_hint_for_input_annotation(
    tmp_path: Path,
    monkeypatch,
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    draft = parse_resynthesis_draft(payload)
    action = replace(
        ctx["action"],
        inputs={
            **ctx["action"].inputs,
            "observed_statement_hints": tuple(ctx["action"].inputs["observed_statement_hints"][:1]),
        },
    )
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    with pytest.raises(ResynthesisDraftError, match="has no observed statement hint"):
        build_resynthesis_context_packet(tmp_path, draft)


def test_resynthesis_context_excludes_annotationless_hints_from_assignment_rows(
    tmp_path: Path,
    monkeypatch,
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    draft = parse_resynthesis_draft(payload)
    annotationless_hint = {
        "paper": "paper:NoAnnotation2026",
        "stance": "asserted",
        "section": "discussion",
        "subject": "BES",
        "object": "unassignable claim text",
        "subject_concept": None,
        "object_concept": None,
        "exact": "This hint has no annotation ref.",
    }
    action = replace(
        ctx["action"],
        inputs={
            **ctx["action"].inputs,
            "observed_statement_hints": (
                *ctx["action"].inputs["observed_statement_hints"],
                annotationless_hint,
            ),
        },
    )
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    packet = build_resynthesis_context_packet(tmp_path, draft)

    assert [row["annotation"] for row in packet["input_annotations"]] == list(payload["input_annotations"])
    assert all(row.get("exact") != "This hint has no annotation ref." for row in packet["input_annotations"])


def test_resynthesis_context_preserves_subject_object_hint_fields(tmp_path: Path, monkeypatch):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    draft = parse_resynthesis_draft(payload)
    hints = tuple(
        {
            **hint,
            "subject": "BES",
            "object": "meta-analysis behavior",
            "subject_concept": "concept:bes",
            "object_concept": "concept:meta-analysis",
        }
        if hint.get("annotation") == "annotation:entities/papers/A2020.source#a1"
        else hint
        for hint in ctx["action"].inputs["observed_statement_hints"]
    )
    action = replace(ctx["action"], inputs={**ctx["action"].inputs, "observed_statement_hints": hints})
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    packet = build_resynthesis_context_packet(tmp_path, draft)
    row = packet["input_annotations"][0]

    assert row["annotation"] == "annotation:entities/papers/A2020.source#a1"
    assert row["subject"] == "BES"
    assert row["object"] == "meta-analysis behavior"
    assert row["subject_concept"] == "concept:bes"
    assert row["object_concept"] == "concept:meta-analysis"


def test_build_resynthesis_context_packet_uses_draft_placeholder_without_path(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    packet = build_resynthesis_context_packet(tmp_path, draft)

    assert packet["draft_path"] is None
    assert packet["output_contract"]["validate_with"] == (
        "science annotate validate-proposition-resynthesis --input <draft>"
    )


def test_resynthesis_context_finds_original_proposition_by_id_not_replacement_path(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    original_path = tmp_path / "entities" / "propositions" / "broad.md"
    relocated_path = tmp_path / "entities" / "propositions" / "legacy" / "broad-legacy-layout.md"
    relocated_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.rename(relocated_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    packet = build_resynthesis_context_packet(tmp_path, draft, draft_path="draft.json")

    assert packet["original_proposition"]["id"] == "proposition:broad"
    assert packet["original_proposition"]["title"] == "BES behaves like pooled meta-analysis"
    assert "Claim body." in packet["original_proposition"]["body"]


def test_resynthesis_context_markdown_renders_same_packet_as_json_block(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        build_resynthesis_context_packet,
        parse_resynthesis_draft,
        resynthesis_context_to_markdown,
    )

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    packet = build_resynthesis_context_packet(tmp_path, draft, draft_path="draft.json")

    rendered = resynthesis_context_to_markdown(packet)

    assert rendered.startswith("# Proposition Resynthesis Draft Context\n")
    assert "## Instructions" in rendered
    assert "Do not edit proposition files or annotation sidecars directly." in rendered
    assert "## Context JSON" in rendered
    json_block = rendered.split("```json\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(json_block) == packet


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
        "input_annotations": list(ctx["action"].inputs["annotations"]),
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
        "context": {"input_annotations": list(ctx["action"].inputs["annotations"])},
        "notes": "",
    }


def test_parse_resynthesis_draft_rejects_invalid_source(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["source"] = "llm-synth:wrong"

    with pytest.raises(ResynthesisDraftError, match="source"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_bool_schema_version(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["schema_version"] = True

    with pytest.raises(ResynthesisDraftError, match="schema_version"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_unknown_top_level_key(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["unexpected"] = True

    with pytest.raises(ResynthesisDraftError, match="unknown resynthesis draft key"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_missing_context(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    del payload["context"]

    with pytest.raises(ResynthesisDraftError, match="missing resynthesis draft key: context"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_missing_notes(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    del payload["notes"]

    with pytest.raises(ResynthesisDraftError, match="missing resynthesis draft key: notes"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_missing_input_annotations(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    del payload["input_annotations"]

    with pytest.raises(ResynthesisDraftError, match="missing resynthesis draft key: input_annotations"):
        parse_resynthesis_draft(payload)


@pytest.mark.parametrize(
    "input_annotations",
    [
        "annotation:entities/papers/A2020.source#a1",
        [" annotation:entities/papers/A2020.source#a1"],
        [""],
        ["annotation:entities/papers/A2020.source#a1", "annotation:entities/papers/A2020.source#a1"],
    ],
)
def test_parse_resynthesis_draft_rejects_malformed_input_annotations(
    tmp_path: Path, input_annotations: object
):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["input_annotations"] = input_annotations

    with pytest.raises(ResynthesisDraftError, match="input_annotations"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_unknown_new_proposition_key(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["new_propositions"][0]["unexpected"] = True

    with pytest.raises(ResynthesisDraftError, match=r"unknown new_propositions\[0\] key"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_unknown_assignment_key(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["annotation_assignments"][0]["unexpected"] = True

    with pytest.raises(ResynthesisDraftError, match=r"unknown annotation_assignments\[0\] key"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_non_mapping_context(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["context"] = "not an object"

    with pytest.raises(ResynthesisDraftError, match="context"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_non_string_notes(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["notes"] = 7

    with pytest.raises(ResynthesisDraftError, match="notes"):
        parse_resynthesis_draft(payload)


def test_parse_resynthesis_draft_rejects_normalized_required_string(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["action_id"] = f" {ctx['action'].action_id}"

    with pytest.raises(ResynthesisDraftError, match="action_id"):
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
    assert report.planned_changed_paths == 2
    assert report.planned_noop_paths == 0
    assert report.expected_annotation_targets == {
        "annotation:entities/papers/A2020.source#a1": "proposition:broad-positive",
        "annotation:entities/papers/B2021.source#b1": "proposition:broad-negative",
    }


def test_validate_resynthesis_draft_rejects_conflicting_existing_replacement_file(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    _proposition(
        tmp_path,
        "broad-positive",
        "Conflicting existing proposition",
        source_refs=("manual:conflict",),
    )
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    with pytest.raises(ResynthesisDraftError, match="existing replacement proposition differs from draft"):
        validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))


def test_validate_resynthesis_draft_rejects_model_invalid_replacement_frontmatter(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    del payload["new_propositions"][0]["frontmatter"]["object"]
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="predicate requires both subject and object"):
        validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))


def test_validate_resynthesis_draft_rejects_unassigned_replacement_without_source_refs(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["annotation_assignments"][1]["to"] = "proposition:broad-positive"
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="replacement propositions must match assigned annotation targets"):
        validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))


def test_validate_resynthesis_draft_rejects_manual_only_extra_replacement(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

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

    with pytest.raises(ResynthesisDraftError, match="replacement propositions must match assigned annotation targets"):
        validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))


def test_validate_resynthesis_draft_rejects_original_as_replacement(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["new_propositions"][0]["id"] = "proposition:broad"
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="original proposition cannot be a replacement"):
        validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))


@pytest.mark.parametrize("source_refs", [None, [" paper:A2020 "]])
def test_validate_resynthesis_draft_rejects_normalized_source_refs(tmp_path: Path, source_refs):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["new_propositions"][0]["frontmatter"]["source_refs"] = source_refs
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="source_refs"):
        validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))


def test_validate_resynthesis_draft_ignores_inactive_promoted_backlinks(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        validate_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    inactive = replace(
        _ann("c1", "proposition:broad", stance="asserted"),
        status=Status.FIXED,
        modified=_CREATED,
        modified_by="test",
    )
    _paper_sidecar(tmp_path, "C2022", (inactive,))
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    report = validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.status == "ok"
    assert report.expected_annotation_targets == {
        "annotation:entities/papers/A2020.source#a1": "proposition:broad-positive",
        "annotation:entities/papers/B2021.source#b1": "proposition:broad-negative",
    }


def test_validate_resynthesis_draft_rejects_missing_action_input_annotations(tmp_path: Path, monkeypatch):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        validate_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    malformed = replace(ctx["action"], inputs={})
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(malformed,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    with pytest.raises(ResynthesisDraftError, match="malformed input annotations"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_duplicate_live_action_input_annotations(
    tmp_path: Path, monkeypatch
):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        validate_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    duplicated_inputs = tuple(ctx["action"].inputs["annotations"]) + (
        ctx["action"].inputs["annotations"][0],
    )
    malformed = replace(
        ctx["action"],
        inputs={**ctx["action"].inputs, "annotations": duplicated_inputs},
    )
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(malformed,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="duplicate input annotations|malformed input annotations"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_reordered_live_action_input_annotations(
    tmp_path: Path, monkeypatch
):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    reordered = tuple(reversed(ctx["action"].inputs["annotations"]))
    action = replace(
        ctx["action"],
        inputs={**ctx["action"].inputs, "annotations": reordered},
    )
    plan = replace(ctx["plan"], actions=(action,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="input_annotations are stale"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_blocked_live_action(tmp_path: Path, monkeypatch):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        validate_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    blocked = replace(ctx["action"], status="blocked", blockers=("review changed",))
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=(str(ctx["review_path"]),), actions=(blocked,))
    monkeypatch.setattr(resynthesis, "build_live_action_plan", lambda _root, _review: plan)

    with pytest.raises(ResynthesisDraftError, match="not ready resynthesize_proposition"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_top_level_action_plan_errors(tmp_path: Path, monkeypatch):
    from science_tool.annotation.proposition_reconciliation_plan import ReconciliationActionPlan
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        validate_resynthesis_draft,
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

    with pytest.raises(ResynthesisDraftError, match="action plan has top-level errors: scanner-fault"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_noncanonical_replacement_id(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["new_propositions"][0]["id"] = "proposition:bad/slash"
    payload["annotation_assignments"][0]["to"] = "proposition:bad/slash"
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="invalid replacement proposition id"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_requires_paper_ref_for_moved_annotations(tmp_path: Path, monkeypatch):
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        validate_resynthesis_draft,
    )
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    monkeypatch.setattr(resynthesis, "_resolve_paper_ref", lambda _sidecar_path: None)

    with pytest.raises(ResynthesisDraftError, match="paper ref"):
        validate_resynthesis_draft(tmp_path, draft)


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


def test_validate_resynthesis_draft_rejects_incomplete_replace_when_action_inputs_grew(
    tmp_path: Path, monkeypatch
):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft
    import science_tool.annotation.proposition_resynthesis as resynthesis

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    _paper_sidecar(tmp_path, "C2022", (_ann("c1", "proposition:broad", stance="asserted"),))
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

    with pytest.raises(ResynthesisDraftError, match="input_annotations are stale"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_stale_top_level_input_annotations(
    tmp_path: Path,
):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["input_annotations"] = payload["input_annotations"][:1]
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="input_annotations are stale"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_allows_split_partial_with_retained_original(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    payload["new_propositions"] = payload["new_propositions"][:1]
    payload["annotation_assignments"][1]["to"] = "proposition:broad"
    draft = parse_resynthesis_draft(payload)

    report = validate_resynthesis_draft(tmp_path, draft)

    assert report.status == "ok"
    assert report.moved_annotations == 1
    assert report.retained_annotations == 1


def test_validate_resynthesis_draft_rejects_incomplete_split_partial(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    payload["new_propositions"] = payload["new_propositions"][:1]
    payload["annotation_assignments"][1]["to"] = "proposition:broad"
    del payload["annotation_assignments"][1]
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="split_partial must assign every input annotation"):
        validate_resynthesis_draft(tmp_path, draft)


def test_validate_resynthesis_draft_rejects_split_partial_without_retained_original(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft, validate_resynthesis_draft

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisDraftError, match="split_partial must retain at least one annotation"):
        validate_resynthesis_draft(tmp_path, draft)


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
    report = validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 2))
    assert report.planned_changed_paths == 1
    assert report.planned_noop_paths == 1
    frontmatter, _body = parse_markdown_entity_file(path)
    assert str(frontmatter["created"]) == "2026-06-30"
    assert str(frontmatter["updated"]) == "2026-06-30"


def test_render_replacement_owns_status_even_when_draft_supplies_status(tmp_path: Path):
    from science_tool.annotation.proposition_resynthesis import (
        parse_resynthesis_draft,
        render_replacement_proposition,
        validate_resynthesis_draft,
    )

    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["new_propositions"][0]["frontmatter"]["status"] = "superseded"
    draft = parse_resynthesis_draft(payload)
    report = validate_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))
    replacement = draft.new_propositions[0]

    rendered = render_replacement_proposition(
        tmp_path,
        replacement,
        sorted(report.expected_source_refs_by_replacement[replacement.id]),
        as_of=date(2026, 7, 1),
    )

    rendered.path.parent.mkdir(parents=True, exist_ok=True)
    rendered.path.write_text(rendered.text, encoding="utf-8")
    frontmatter, _body = parse_markdown_entity_file(rendered.path)
    assert frontmatter["status"] == "active"
