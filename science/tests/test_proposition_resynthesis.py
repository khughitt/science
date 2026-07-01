import json
from dataclasses import replace
from datetime import datetime, timezone
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
