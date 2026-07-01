# Proposition Reconciliation Phase 4e Half D Resynthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reviewed factorization-resynthesis path that scaffolds, validates, and applies explicit replacement propositions plus annotation rewrites for ready `resynthesize_proposition` actions.

**Architecture:** Keep Half B action plans read-only and add a separate Half D draft artifact as the mutation authority. Put scaffold/validation/reporting in `science_tool.annotation.proposition_resynthesis`, put mutation preflight/write/postflight in `science_tool.annotation.proposition_resynthesis_apply`, and wire three flat `annotate` commands. Validation and apply both rebuild the live Half B action from `source_review`, compare against current sidecars/proposition files, and never trust saved action-plan JSON.

**Tech Stack:** Python dataclasses, Click, existing annotation sidecar parser/serializer, existing entity markdown render helpers, `load_project_sources`, `pytest`, `CliRunner`, `ruff`, `pyright`.

---

## File Structure

- Modify: `science/src/science_tool/entities.py`
  - Register `resynthesized_into` as a managed frontmatter reference key.
  - No graph/materialization changes in Half D.

- Create: `science/src/science_tool/annotation/proposition_resynthesis.py`
  - Draft schema constants and validation errors.
  - Draft dataclasses and JSON parsing.
  - Ready `resynthesize_proposition` action resolution from a live Half B plan.
  - Scaffold document builder.
  - Draft semantic validation and replacement proposition render/compare helpers shared by validate/apply.
  - JSON/table-ready validation report helpers.

- Create: `science/src/science_tool/annotation/proposition_resynthesis_apply.py`
  - File-edit preflight.
  - Sidecar assignment merge and final-text planning.
  - Apply report and postflight checks.
  - Write execution with honest partial-write diagnostics.

- Modify: `science/src/science_tool/annotation/cli.py`
  - Add flat commands:
    - `scaffold-proposition-resynthesis`
    - `validate-proposition-resynthesis`
    - `apply-proposition-resynthesis`

- Create: `science/tests/test_proposition_resynthesis.py`
  - Unit tests for scaffold, draft parser, action freshness, validation, replacement rendering, date-preserving idempotency checks, and input-set growth.

- Create: `science/tests/test_proposition_resynthesis_apply.py`
  - Unit/e2e tests for preflight, writes, sidecar merge, original supersession, partial split, resume/no-op, and postflight.

- Modify: `science/tests/test_proposition_reconciliation_cli.py`
  - CLI tests for the three new commands.
  - Keep Half C rejection of direct `resynthesize_proposition` actions pinned.

- Modify: `science/tests/test_entity_writer.py` or `science/tests/test_entity_reference_removal.py`
  - Add coverage that `resynthesized_into` participates in managed frontmatter reference removal/rewrite.

---

## Shared Test Fixtures

The new tests should use these local helpers in `science/tests/test_proposition_resynthesis.py` and import/reuse them from sibling test files with `from test_proposition_resynthesis import ...` where practical. Do not import through a package-qualified tests path that does not exist.

```python
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

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
```

If this fixture does not generate a factorization candidate because the live candidate heuristic changes, do not weaken the production heuristic. Adjust the fixture annotations/statements to create the documented mixed-stance or incompatible-object disagreement.

Also verify fixture paper-ref resolution before relying on derived `paper:` source-ref assertions. `_resolve_paper_ref(sidecar_path)` should produce `paper:A2020` from `entities/papers/A2020.source.md`; if the adapter now requires richer paper source structure, update the fixture to write the minimal real paper entity/source metadata rather than weakening production ref resolution.

---

## Task 1: Managed `resynthesized_into` Frontmatter References

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Test: `science/tests/test_entity_writer.py` or `science/tests/test_entity_reference_removal.py`

- [ ] **Step 1: Add a failing test for `resynthesized_into` as a removable managed ref**

Append this test to the existing entity reference-removal test file. If there is no dedicated file, append to `science/tests/test_entity_writer.py`.

```python
def test_entity_removal_treats_resynthesized_into_as_managed_frontmatter_ref(tmp_path: Path):
    from science_tool.entities import plan_entity_removal, remove_entity

    root = tmp_path
    (root / "science.yaml").write_text("name: test\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    original = root / "entities" / "propositions" / "broad.md"
    replacement = root / "entities" / "propositions" / "narrow.md"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text(
        "---\n"
        "id: proposition:broad\n"
        "type: proposition\n"
        "title: Broad\n"
        "status: superseded\n"
        "resynthesized_into:\n"
        "  - proposition:narrow\n"
        "---\n\n"
        "Broad body.\n",
        encoding="utf-8",
    )
    replacement.write_text(
        "---\n"
        "id: proposition:narrow\n"
        "type: proposition\n"
        "title: Narrow\n"
        "status: active\n"
        "---\n\n"
        "Narrow body.\n",
        encoding="utf-8",
    )

    plan = plan_entity_removal(root, "proposition:narrow")

    assert any(
        hit.path == original and hit.kind == "safe structured reference" and "resynthesized_into" in hit.detail
        for hit in plan.safe_hits
    )

    remove_entity(root, "proposition:narrow")

    assert "resynthesized_into" not in original.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_entity_writer.py -q
```

Expected before implementation: the new assertion fails because `resynthesized_into` is reported as a manual hit or is not removed.

- [ ] **Step 3: Register the managed key**

In `science/src/science_tool/entities.py`, add `resynthesized_into` to `_REMOVABLE_FRONTMATTER_REF_KEYS` next to `superseded_by`:

```python
_REMOVABLE_FRONTMATTER_REF_KEYS: frozenset[str] = frozenset(
    {
        "related",
        "source_refs",
        "supersedes",
        "superseded_by",
        "resynthesized_into",
        "consolidates",
        "consolidated_into",
        "members",
        "member_refs",
        "depends_on",
        "blockers",
    }
)
```

- [ ] **Step 4: Verify**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_entity_writer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/entities.py science/tests/test_entity_writer.py
rtk git commit -m "feat(4e): manage resynthesized lineage refs"
```

---

## Task 2: Resynthesis Draft Schema, Action Resolution, And Scaffold

**Files:**
- Create: `science/src/science_tool/annotation/proposition_resynthesis.py`
- Test: `science/tests/test_proposition_resynthesis.py`

- [ ] **Step 1: Add failing scaffold/action-resolution tests**

Create `science/tests/test_proposition_resynthesis.py` with the shared fixtures above and these tests:

```python
from science_tool.annotation.proposition_resynthesis import (
    RESYNTHESIS_SCHEMA_VERSION,
    ResynthesisDraftError,
    build_resynthesis_scaffold,
    draft_to_json,
    resolve_resynthesis_action,
)


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
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_resynthesis.py -q
```

Expected: FAIL because `science_tool.annotation.proposition_resynthesis` does not exist.

- [ ] **Step 3: Implement draft schema and scaffold**

Create `science/src/science_tool/annotation/proposition_resynthesis.py` with:

```python
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from science_tool.annotation.proposition_reconciliation import (
    ReconciliationValidationError,
    build_reconciliation_report,
)
from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
    ReviewedReconciliationInput,
    build_reconciliation_action_plan,
)

RESYNTHESIS_SCHEMA_VERSION = 1
RESYNTHESIS_SOURCE_RE = re.compile(r"^llm-review:[A-Za-z0-9._-]+:proposition-resynthesis-v1$")
DEFAULT_RESYNTHESIS_SOURCE_MODEL = "codex-gpt-5"
RESYNTHESIS_DISPOSITIONS = frozenset({"replace", "split_partial"})


class ResynthesisDraftError(ValueError):
    """Raised when a proposition resynthesis draft cannot be used safely."""


@dataclass(frozen=True)
class NewPropositionDraft:
    id: str
    title: str
    body: str
    frontmatter: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnnotationAssignment:
    annotation: str
    from_proposition: str
    to_proposition: str


@dataclass(frozen=True)
class ResynthesisDraft:
    schema_version: int
    source: str
    action_id: str
    candidate_id: str
    judgment_id: str
    source_review: str
    original_proposition: str
    disposition: Literal["replace", "split_partial"]
    new_propositions: tuple[NewPropositionDraft, ...] = ()
    annotation_assignments: tuple[AnnotationAssignment, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)
    notes: str = ""


def _read_review(path: Path) -> Mapping[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResynthesisDraftError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise ResynthesisDraftError(f"{path} must contain a JSON object")
    return loaded


def build_live_action_plan(project_root: Path, source_review: str) -> ReconciliationActionPlan:
    review_path = Path(source_review)
    if not review_path.is_absolute():
        review_path = project_root / review_path
    doc = _read_review(review_path)
    report = build_reconciliation_report(project_root)
    try:
        return build_reconciliation_action_plan(
            report,
            [ReviewedReconciliationInput(path=str(review_path), doc=doc)],
        )
    except (ReconciliationValidationError, ValueError) as exc:
        raise ResynthesisDraftError(str(exc)) from exc


def resolve_resynthesis_action(
    plan: ReconciliationActionPlan,
    *,
    requested_action_id: str | None,
) -> ReconciliationAction:
    if plan.errors:
        details = "; ".join(str(error.get("reason", error)) for error in plan.errors)
        raise ResynthesisDraftError(f"action plan has top-level errors: {details}")
    ready = tuple(
        action
        for action in plan.actions
        if action.kind == "resynthesize_proposition" and action.status == "ready" and not action.blockers
    )
    if requested_action_id is None:
        if len(ready) == 1:
            return ready[0]
        if not ready:
            raise ResynthesisDraftError("no ready resynthesize_proposition actions")
        raise ResynthesisDraftError("multiple ready resynthesize_proposition actions; pass --action")
    by_id = {action.action_id: action for action in plan.actions}
    action = by_id.get(requested_action_id)
    if action is None:
        raise ResynthesisDraftError(f"unknown reconciliation action: {requested_action_id}")
    if action.kind != "resynthesize_proposition" or action.status != "ready" or action.blockers:
        raise ResynthesisDraftError(f"{requested_action_id} is not ready resynthesize_proposition")
    return action


def build_resynthesis_scaffold(
    plan: ReconciliationActionPlan,
    *,
    requested_action_id: str | None,
    source_review: str,
    model: str = DEFAULT_RESYNTHESIS_SOURCE_MODEL,
) -> ResynthesisDraft:
    action = resolve_resynthesis_action(plan, requested_action_id=requested_action_id)
    if action.proposition is None:
        raise ResynthesisDraftError(f"{action.action_id} has no proposition")
    return ResynthesisDraft(
        schema_version=RESYNTHESIS_SCHEMA_VERSION,
        source=f"llm-review:{model}:proposition-resynthesis-v1",
        action_id=action.action_id,
        candidate_id=action.candidate_id,
        judgment_id=action.judgment_id,
        source_review=source_review,
        original_proposition=action.proposition,
        disposition="replace",
        new_propositions=(),
        annotation_assignments=(),
        context={
            "rationale": action.rationale,
            "observed_statement_hints": tuple(action.inputs.get("observed_statement_hints", ())),
            "input_annotations": tuple(action.inputs.get("annotations", ())),
            "papers": tuple(action.inputs.get("papers", ())),
        },
    )


def draft_to_json(draft: ResynthesisDraft) -> dict[str, Any]:
    return {
        "schema_version": draft.schema_version,
        "source": draft.source,
        "action_id": draft.action_id,
        "candidate_id": draft.candidate_id,
        "judgment_id": draft.judgment_id,
        "source_review": draft.source_review,
        "original_proposition": draft.original_proposition,
        "disposition": draft.disposition,
        "new_propositions": [
            {
                "id": row.id,
                "title": row.title,
                "body": row.body,
                "frontmatter": dict(row.frontmatter),
            }
            for row in draft.new_propositions
        ],
        "annotation_assignments": [
            {
                "annotation": row.annotation,
                "from": row.from_proposition,
                "to": row.to_proposition,
            }
            for row in draft.annotation_assignments
        ],
        "context": dict(draft.context),
        "notes": draft.notes,
    }
```

Keep the module narrow: do not add validation or apply logic in this task beyond action selection and scaffold generation.

- [ ] **Step 4: Verify**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_resynthesis.py -q
```

Expected: PASS for the scaffold tests.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_resynthesis.py science/tests/test_proposition_resynthesis.py
rtk git commit -m "feat(4e): scaffold proposition resynthesis drafts"
```

---

## Task 3: Draft Parser, Shared Validation, And Replacement Rendering

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_resynthesis.py`
- Test: `science/tests/test_proposition_resynthesis.py`

- [ ] **Step 1: Add failing validation tests**

Append:

```python
from datetime import date

from science_tool.entities import parse_markdown_entity_file


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
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_resynthesis.py -q
```

Expected: FAIL for missing parser/validator/render functions.

- [ ] **Step 3: Add parser/report dataclasses and strict draft shape validation**

In `proposition_resynthesis.py`, add:

```python
from datetime import date

from science_model.propositions import PropositionEntity
from science_tool.annotation.proposition_reconciliation_apply import _live_annotation_index
from science_tool.annotation.cross_paper_evidence import _resolve_paper_ref
from science_tool.entities import (
    _render_markdown,
    parse_markdown_entity_file,
    resolve_path_policy,
)

ALLOWED_REPLACEMENT_FRONTMATTER_KEYS = frozenset(
    {
        "type",
        "kind",
        "status",
        "related",
        "source_refs",
        "subject",
        "predicate",
        "object",
        "polarity",
        "claim_layer",
        "identification_strength",
        "ontology_terms",
        "discusses",
    }
)


@dataclass(frozen=True)
class RenderedReplacement:
    proposition: str
    path: Path
    text: str
    changed: bool


@dataclass(frozen=True)
class ResynthesisValidationReport:
    status: str
    original_proposition: str
    replacement_propositions: int
    moved_annotations: int
    retained_annotations: int
    planned_changed_paths: int = 0
    planned_noop_paths: int = 0
    expected_annotation_targets: Mapping[str, str] = field(default_factory=dict)
    expected_source_refs_by_replacement: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    action: ReconciliationAction | None = None
    errors: tuple[Mapping[str, Any], ...] = ()
    warnings: tuple[Mapping[str, Any], ...] = ()
```

Add `parse_resynthesis_draft(payload)`. It must:

- require a JSON object;
- require `schema_version == 1`;
- require `source` matches `RESYNTHESIS_SOURCE_RE`;
- require all identity strings are non-empty;
- require `disposition in {"replace", "split_partial"}`;
- require `new_propositions` and `annotation_assignments` are lists;
- convert assignment JSON key `from` to dataclass field `from_proposition`;
- fail early on malformed rows, not silently coerce missing values.

Use explicit field extraction like:

```python
def _required_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ResynthesisDraftError(f"missing or invalid {key}")
    return value.strip()
```

- [ ] **Step 4: Implement live action validation and assignment checks**

Add `validate_resynthesis_draft(project_root, draft, as_of=None)`.

Required implementation shape:

```python
def _live_action_for_draft(project_root: Path, draft: ResynthesisDraft) -> ReconciliationAction:
    plan = build_live_action_plan(project_root, draft.source_review)
    action = resolve_resynthesis_action(plan, requested_action_id=draft.action_id)
    if action.candidate_id != draft.candidate_id:
        raise ResynthesisDraftError("candidate_id is stale")
    if action.judgment_id != draft.judgment_id:
        raise ResynthesisDraftError("judgment_id is stale")
    if action.proposition != draft.original_proposition:
        raise ResynthesisDraftError("original_proposition is stale")
    return action
```

Assignment validation rules:

- `action.inputs["annotations"]` is the current input annotation set.
- Each draft assignment annotation must be in that current set.
- Duplicate assignment annotations fail.
- `assignment.from_proposition == draft.original_proposition`.
- Live sidecar `promoted_to` for each assigned annotation must be either `from` or `to`; a third value is drift.
- `to` must be a draft new proposition id, except `split_partial` may target the original.
- `replace` must assign every current input annotation and all assignments must target a new proposition.
- `split_partial` must move at least one annotation to a new proposition.

Use `_live_annotation_index(project_root)` from Half C for current sidecar state, and `_resolve_paper_ref(sidecar_path)` to derive paper refs for assignments. This is acceptable internal reuse; both modules live in `science_tool.annotation`.

- [ ] **Step 5: Implement replacement proposition rendering**

Add `render_replacement_proposition(project_root, replacement, source_refs, as_of=None)`.

Rules:

- Canonical path is `project_root / resolve_path_policy("proposition", project_root=project_root).root / f"{local_part}.md"`.
- Validate `replacement.id` starts with `proposition:`.
- Frontmatter renderer owns `id`, `type`, `title`, `status`, `created`, `updated`, and derived/source refs.
- Draft `source_refs` are additive; derived assignment refs are always included.
- Unknown draft frontmatter keys fail before typed model validation.
- Create dates use `as_of or date.today()`.
- If file exists, parse existing `created`/`updated` and preserve them for comparison/rendering.
- If file exists and non-date content differs, raise `ResynthesisDraftError("existing replacement proposition differs from draft")`.
- Validate by constructing `PropositionEntity(**frontmatter)` after removing raw markdown-only keys that are not model fields if needed; do not rely on the loader to reject unknown keys.

Implementation sketch:

```python
def _replacement_path(project_root: Path, proposition_id: str) -> Path:
    if not proposition_id.startswith("proposition:"):
        raise ResynthesisDraftError(f"replacement id must be proposition:<slug>: {proposition_id}")
    local_part = proposition_id.split(":", 1)[1]
    policy = resolve_path_policy("proposition", project_root=project_root)
    return project_root / policy.root / f"{local_part}.md"


def _canonical_replacement_frontmatter(
    replacement: NewPropositionDraft,
    source_refs: Sequence[str],
    *,
    created: str,
    updated: str,
) -> dict[str, Any]:
    unknown = sorted(set(replacement.frontmatter) - ALLOWED_REPLACEMENT_FRONTMATTER_KEYS)
    if unknown:
        raise ResynthesisDraftError(f"unknown proposition frontmatter key(s): {', '.join(unknown)}")
    draft_refs = replacement.frontmatter.get("source_refs") or []
    if not isinstance(draft_refs, Sequence) or isinstance(draft_refs, str):
        raise ResynthesisDraftError(f"{replacement.id} frontmatter source_refs must be a list")
    refs = tuple(sorted({str(ref) for ref in draft_refs} | {str(ref) for ref in source_refs}))
    frontmatter = {
        "id": replacement.id,
        "type": "proposition",
        "title": replacement.title,
        "status": "active",
        **{key: value for key, value in replacement.frontmatter.items() if key not in {"id", "type", "kind", "title", "status", "created", "updated", "source_refs"}},
        "source_refs": list(refs),
        "created": created,
        "updated": updated,
    }
    PropositionEntity(**frontmatter)
    return frontmatter


def render_replacement_proposition(
    project_root: Path,
    replacement: NewPropositionDraft,
    source_refs: Sequence[str],
    *,
    as_of: date | None = None,
) -> RenderedReplacement:
    path = _replacement_path(project_root, replacement.id)
    created = (as_of or date.today()).isoformat()
    updated = created
    if path.exists():
        existing_fm, _existing_body = parse_markdown_entity_file(path)
        # Preserve existing dates so a same-draft re-run on a later day is a no-op,
        # not spurious drift (design idempotency rule).
        created = str(existing_fm.get("created", created))
        updated = str(existing_fm.get("updated", updated))
    frontmatter = _canonical_replacement_frontmatter(
        replacement, source_refs, created=created, updated=updated
    )
    text = _render_markdown(frontmatter, f"# {replacement.title}\n\n{replacement.body}\n")
    if path.exists():
        before = path.read_text(encoding="utf-8")
        if before != text:
            raise ResynthesisDraftError(
                f"existing replacement proposition differs from draft: {replacement.id}"
            )
        return RenderedReplacement(proposition=replacement.id, path=path, text=text, changed=False)
    return RenderedReplacement(proposition=replacement.id, path=path, text=text, changed=True)
```

`_render_markdown(frontmatter, body)` (from `science_tool.entities`) owns canonical
frontmatter ordering; it is the fresh-file renderer, distinct from
`render_entity_frontmatter_updates`, which only edits an existing file.

Do not write files in this module.

- [ ] **Step 6: Verify**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_resynthesis.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_resynthesis.py science/tests/test_proposition_resynthesis.py
rtk git commit -m "feat(4e): validate proposition resynthesis drafts"
```

---

## Task 4: Resynthesis Apply Preflight

**Files:**
- Create: `science/src/science_tool/annotation/proposition_resynthesis_apply.py`
- Test: `science/tests/test_proposition_resynthesis_apply.py`

- [ ] **Step 1: Add failing preflight tests**

Create `science/tests/test_proposition_resynthesis_apply.py`:

```python
from datetime import date
from pathlib import Path

import pytest

from science_tool.annotation.query import read_sidecar_strict
from science_tool.annotation.proposition_resynthesis import parse_resynthesis_draft
from science_tool.annotation.proposition_resynthesis_apply import (
    ResynthesisApplyError,
    plan_resynthesis_apply,
)
from science_tool.entities import parse_markdown_entity_file

from test_proposition_resynthesis import (
    _ann,
    _draft_payload,
    _factorization_project,
    _paper_sidecar,
)


def test_plan_resynthesis_apply_creates_replacements_rewrites_sidecars_and_supersedes_original(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    preflight = plan_resynthesis_apply(tmp_path, draft, as_of=date(2026, 7, 1))

    reasons = {edit.reason for edit in preflight.file_edits}
    assert "replacement_proposition" in reasons
    assert "sidecar_promoted_to" in reasons
    assert "original_resynthesis_lineage" in reasons
    assert preflight.expected_original_state == {
        "status": "superseded",
        "resynthesized_into": ["proposition:broad-negative", "proposition:broad-positive"],
    }
    assert preflight.expected_annotation_targets == {
        "annotation:entities/papers/A2020.source#a1": "proposition:broad-positive",
        "annotation:entities/papers/B2021.source#b1": "proposition:broad-negative",
    }
    assert all(edit.path.exists() or edit.reason == "replacement_proposition" for edit in preflight.file_edits)


def test_plan_resynthesis_apply_merges_multiple_rewrites_in_one_sidecar(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    (tmp_path / "entities" / "papers" / "A2020.source.anno.trig").unlink()
    (tmp_path / "entities" / "papers" / "B2021.source.anno.trig").unlink()
    shared = tmp_path / "entities" / "papers" / "Shared.source.md"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_text("Shared paper.\n", encoding="utf-8")
    sidecar_path = shared.with_name("Shared.source.anno.trig")
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Sidecar

    anno_io.write_sidecar(
        sidecar_path,
        Sidecar(annotations=(_ann("a1", "proposition:broad"), _ann("b1", "proposition:broad", stance="negated"))),
    )
    payload = _draft_payload(ctx)
    payload["annotation_assignments"] = [
        {
            "annotation": "annotation:entities/papers/Shared.source#a1",
            "from": "proposition:broad",
            "to": "proposition:broad-positive",
        },
        {
            "annotation": "annotation:entities/papers/Shared.source#b1",
            "from": "proposition:broad",
            "to": "proposition:broad-negative",
        },
    ]
    draft = parse_resynthesis_draft(payload)

    preflight = plan_resynthesis_apply(tmp_path, draft, as_of=date(2026, 7, 1))

    sidecar_edits = [edit for edit in preflight.file_edits if edit.path == sidecar_path]
    assert len(sidecar_edits) == 1
    assert "proposition:broad-positive" in sidecar_edits[0].final_text
    assert "proposition:broad-negative" in sidecar_edits[0].final_text


def test_plan_resynthesis_apply_rejects_annotation_drift_to_third_target(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    path = tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    sidecar = read_sidecar_strict(path)
    from dataclasses import replace
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Sidecar

    anno_io.write_sidecar(
        path,
        Sidecar(
            annotations=(replace(sidecar.annotations[0], promoted_to="proposition:other"),),
            ledgers=sidecar.ledgers,
            shared_targets=sidecar.shared_targets,
        ),
    )
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    with pytest.raises(ResynthesisApplyError, match="not proposition:broad or proposition:broad-positive"):
        plan_resynthesis_apply(tmp_path, draft)


def test_plan_resynthesis_apply_keeps_original_active_for_split_partial(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    payload["annotation_assignments"][1]["to"] = "proposition:broad"
    draft = parse_resynthesis_draft(payload)

    preflight = plan_resynthesis_apply(tmp_path, draft, as_of=date(2026, 7, 1))

    assert preflight.expected_original_state == {"status": "active"}
    original_edits = [edit for edit in preflight.file_edits if edit.path.name == "broad.md"]
    assert not original_edits
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_resynthesis_apply.py -q
```

Expected: FAIL because `proposition_resynthesis_apply` does not exist.

- [ ] **Step 3: Implement preflight dataclasses and helpers**

Create `science/src/science_tool/annotation/proposition_resynthesis_apply.py`:

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

from science_tool.annotation.io import atomic_write_text, serialize_sidecar
from science_tool.annotation.model import Sidecar
from science_tool.annotation.proposition_reconciliation_apply import (
    PlannedFileEdit,
    ReconciliationApplyError,
    _changed_and_noop_paths,
    _edit,
    _live_annotation_index,
    _path_string,
    _sha256_text,
)
from science_tool.annotation.query import SidecarParseError, read_sidecar_strict
from science_tool.annotation.proposition_resynthesis import (
    AnnotationAssignment,
    ResynthesisDraft,
    ResynthesisDraftError,
    ResynthesisValidationReport,
    render_replacement_proposition,
    validate_resynthesis_draft,
)
from science_tool.entities import find_entity, parse_markdown_entity_file, render_entity_frontmatter_updates


class ResynthesisApplyError(ReconciliationApplyError):
    """Raised when reviewed proposition resynthesis cannot be applied safely."""


@dataclass(frozen=True)
class ResynthesisPreflight:
    draft: ResynthesisDraft
    validation: ResynthesisValidationReport
    file_edits: tuple[PlannedFileEdit, ...]
    expected_annotation_targets: Mapping[str, str] = field(default_factory=dict)
    expected_source_refs_by_replacement: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    expected_original_state: Mapping[str, Any] = field(default_factory=dict)
```

Add local wrappers that convert `ResynthesisDraftError` into `ResynthesisApplyError` at apply boundary:

```python
def _validate(project_root: Path, draft: ResynthesisDraft, *, as_of: date | None) -> ResynthesisValidationReport:
    try:
        return validate_resynthesis_draft(project_root, draft, as_of=as_of)
    except ResynthesisDraftError as exc:
        raise ResynthesisApplyError(str(exc)) from exc
```

- [ ] **Step 4: Implement replacement/original/sidecar final text planning**

Implement:

```python
def _sidecar_final_texts_for_assignments(
    project_root: Path,
    assignments: Sequence[AnnotationAssignment],
) -> dict[Path, str]:
    index = _live_annotation_index(project_root)
    targets_by_path: dict[Path, dict[str, str]] = {}
    for assignment in assignments:
        indexed = index.get(assignment.annotation)
        if indexed is None:
            raise ResynthesisApplyError(f"{assignment.annotation} resolves to no live sidecar annotation")
        sidecar_path, _sidecar, promoted_to = indexed
        if promoted_to == assignment.to_proposition:
            continue
        if promoted_to != assignment.from_proposition:
            raise ResynthesisApplyError(
                f"{assignment.annotation} promoted_to {promoted_to!r} is not "
                f"{assignment.from_proposition} or {assignment.to_proposition}"
            )
        targets = targets_by_path.setdefault(sidecar_path, {})
        annotation_id = assignment.annotation.rsplit("#", 1)[1]
        other = targets.get(annotation_id)
        if other is not None and other != assignment.to_proposition:
            raise ResynthesisApplyError(f"{assignment.annotation} has incompatible assignment targets")
        targets[annotation_id] = assignment.to_proposition
    final: dict[Path, str] = {}
    for sidecar_path, targets in targets_by_path.items():
        try:
            sidecar = read_sidecar_strict(sidecar_path)
        except SidecarParseError as exc:
            raise ResynthesisApplyError(str(exc)) from exc
        annotations = []
        seen: set[str] = set()
        for annotation in sidecar.annotations:
            target = targets.get(annotation.id)
            if target is None:
                annotations.append(annotation)
            else:
                seen.add(annotation.id)
                annotations.append(replace(annotation, promoted_to=target))
        missing = sorted(set(targets) - seen)
        if missing:
            raise ResynthesisApplyError(f"{sidecar_path} missing targeted annotation(s): {', '.join(missing)}")
        final[sidecar_path] = serialize_sidecar(
            Sidecar(
                annotations=tuple(annotations),
                ledgers=sidecar.ledgers,
                shared_targets=sidecar.shared_targets,
            )
        )
    return final
```

Implement original state updates:

```python
def _original_updates(draft: ResynthesisDraft) -> dict[str, Any]:
    if draft.disposition == "split_partial":
        return {}
    replacement_ids = sorted(row.id for row in draft.new_propositions)
    if len(replacement_ids) == 1:
        return {"status": "superseded", "superseded_by": replacement_ids[0]}
    return {"status": "superseded", "resynthesized_into": replacement_ids}
```

Do not prune original `source_refs`; the design explicitly treats them as historical provenance.

- [ ] **Step 5: Implement `plan_resynthesis_apply`**

`plan_resynthesis_apply(project_root, draft, as_of=None)` must:

1. Resolve `project_root`.
2. Run shared validation.
3. Render each replacement proposition with validation-derived source refs.
4. Build one `PlannedFileEdit` per replacement path. For non-existing paths, compute hashes using `before_sha256` of empty string and `changed=True` instead of calling `_edit` on a missing file. Half C `_edit` reads the current file from disk and should still be used for existing files.
5. Render original proposition frontmatter updates for `replace` via `_original_edit`
   below (locate the file with `find_entity`, apply `_original_updates`); no original
   edit for `split_partial` (`_original_updates` returns `{}`).
6. Build sidecar edits by merging all assignments per file.
7. Sort edits by path and return `ResynthesisPreflight`.

Locate and render the original proposition edit:

```python
def _original_edit(project_root: Path, draft: ResynthesisDraft, *, as_of: date | None) -> PlannedFileEdit | None:
    updates = _original_updates(draft)
    if not updates:  # split_partial leaves the original untouched
        return None
    original_path = find_entity(project_root, draft.original_proposition).path
    final_text, _changed = render_entity_frontmatter_updates(original_path, updates, as_of=as_of)
    return _edit(original_path, final_text, "original_resynthesis_lineage")
```

`render_entity_frontmatter_updates` bumps `updated` only when a field actually
changes, so a re-run over an already-superseded original is a no-op; `_edit`
recomputes `changed` by diffing current-vs-final text.

Use this helper for new files:

```python
def _new_or_existing_edit(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=_sha256_text(before),
        after_sha256=_sha256_text(final_text),
        final_text=final_text,
        changed=before != final_text,
    )
```

Use this helper only where the target may not exist yet. Keep using the existing Half C `_edit` helper for original proposition and sidecar edits that must already exist.

- [ ] **Step 6: Verify**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_resynthesis.py science/tests/test_proposition_resynthesis_apply.py -q
```

Expected: PASS for validation and preflight tests.

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_resynthesis_apply.py science/tests/test_proposition_resynthesis_apply.py
rtk git commit -m "feat(4e): preflight proposition resynthesis apply"
```

---

## Task 5: Apply Writes, Postflight, Idempotency, And Resume

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_resynthesis_apply.py`
- Test: `science/tests/test_proposition_resynthesis_apply.py`

- [ ] **Step 1: Add failing apply/postflight/idempotency tests**

Append:

```python
from science_tool.annotation.cross_paper_evidence import build_cross_paper_evidence_report
from science_tool.annotation.proposition_resynthesis_apply import (
    apply_resynthesis_draft,
    apply_resynthesis_report_to_json,
)


def test_apply_resynthesis_draft_creates_files_rewrites_sidecars_and_supersedes_original(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    report = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.status == "ok"
    positive = tmp_path / "entities" / "propositions" / "broad-positive.md"
    negative = tmp_path / "entities" / "propositions" / "broad-negative.md"
    assert positive.exists()
    assert negative.exists()
    original_fm, _ = parse_markdown_entity_file(tmp_path / "entities" / "propositions" / "broad.md")
    assert original_fm["status"] == "superseded"
    assert original_fm["resynthesized_into"] == [
        "proposition:broad-negative",
        "proposition:broad-positive",
    ]
    sidecar = read_sidecar_strict(tmp_path / "entities" / "papers" / "A2020.source.anno.trig")
    assert sidecar.annotations[0].promoted_to == "proposition:broad-positive"
    replacement_fm, _body = parse_markdown_entity_file(positive)
    assert "annotation:entities/papers/A2020.source#a1" in replacement_fm["source_refs"]
    assert "paper:A2020" in replacement_fm["source_refs"]
    assert "manual:curator-note" in replacement_fm["source_refs"]


def test_apply_resynthesis_draft_second_run_is_noop_and_preserves_dates(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    first = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))
    positive = tmp_path / "entities" / "propositions" / "broad-positive.md"
    first_text = positive.read_text(encoding="utf-8")
    second = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 2))

    assert first.written_paths
    assert second.written_paths == ()
    assert positive.read_text(encoding="utf-8") == first_text
    payload = apply_resynthesis_report_to_json(second, project_root=tmp_path)
    assert payload["summary"]["changed_paths"] == 0
    assert payload["summary"]["noop_paths"] > 0


def test_apply_resynthesis_draft_resumes_when_one_sidecar_already_points_to_target(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))
    sidecar_path = tmp_path / "entities" / "papers" / "A2020.source.anno.trig"
    sidecar = read_sidecar_strict(sidecar_path)
    from dataclasses import replace
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import Sidecar

    anno_io.write_sidecar(
        sidecar_path,
        Sidecar(
            annotations=(replace(sidecar.annotations[0], promoted_to="proposition:broad-positive"),),
            ledgers=sidecar.ledgers,
            shared_targets=sidecar.shared_targets,
        ),
    )

    report = apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert report.status == "ok"
    assert any(path.endswith("B2021.source.anno.trig") for path in report.written_paths)


def test_apply_resynthesis_draft_split_partial_keeps_original_active(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["disposition"] = "split_partial"
    payload["annotation_assignments"][1]["to"] = "proposition:broad"
    draft = parse_resynthesis_draft(payload)

    apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    original_fm, _ = parse_markdown_entity_file(tmp_path / "entities" / "propositions" / "broad.md")
    assert original_fm["status"] == "active"
    retained = read_sidecar_strict(tmp_path / "entities" / "papers" / "B2021.source.anno.trig")
    assert retained.annotations[0].promoted_to == "proposition:broad"


def test_apply_resynthesis_draft_cross_paper_evidence_moves_to_replacements(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    draft = parse_resynthesis_draft(_draft_payload(ctx))

    apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    positive = build_cross_paper_evidence_report(tmp_path, proposition_ref="proposition:broad-positive")
    broad = build_cross_paper_evidence_report(tmp_path, proposition_ref="proposition:broad")
    assert len(positive["units"]) == 1
    assert len(broad["units"]) == 0


def test_apply_resynthesis_draft_preflight_failure_writes_nothing(tmp_path: Path):
    ctx = _factorization_project(tmp_path)
    payload = _draft_payload(ctx)
    payload["new_propositions"][0]["frontmatter"]["unknown"] = "bad"
    draft = parse_resynthesis_draft(payload)

    with pytest.raises(ResynthesisApplyError):
        apply_resynthesis_draft(tmp_path, draft, as_of=date(2026, 7, 1))

    assert not (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()
    sidecar = read_sidecar_strict(tmp_path / "entities" / "papers" / "A2020.source.anno.trig")
    assert sidecar.annotations[0].promoted_to == "proposition:broad"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_resynthesis_apply.py -q
```

Expected: FAIL for missing apply/report functions.

- [ ] **Step 3: Add report dataclasses and JSON serialization**

In `proposition_resynthesis_apply.py`, add:

```python
@dataclass(frozen=True)
class ResynthesisApplyReport:
    status: str
    original_proposition: str
    replacement_propositions: tuple[str, ...]
    rewritten_annotations: tuple[str, ...]
    changed_paths: tuple[str, ...]
    noop_paths: tuple[str, ...]
    written_paths: tuple[str, ...]
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    original_state: Mapping[str, Any] = field(default_factory=dict)


def apply_resynthesis_report_to_json(
    report: ResynthesisApplyReport,
    *,
    project_root: Path | None = None,
) -> dict[str, Any]:
    def rel(path: str) -> str:
        parsed = Path(path)
        if project_root is None or not parsed.is_absolute():
            return parsed.as_posix()
        try:
            return parsed.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            return parsed.as_posix()

    return {
        "schema_version": 1,
        "status": report.status,
        "original_proposition": report.original_proposition,
        "replacement_propositions": list(report.replacement_propositions),
        "rewritten_annotations": list(report.rewritten_annotations),
        "changed_paths": [rel(path) for path in report.changed_paths],
        "noop_paths": [rel(path) for path in report.noop_paths],
        "written_paths": [rel(path) for path in report.written_paths],
        "original_state": dict(report.original_state),
        "diagnostics": [dict(row) for row in report.diagnostics],
        "summary": {
            "replacement_propositions": len(report.replacement_propositions),
            "rewritten_annotations": len(report.rewritten_annotations),
            "changed_paths": len(report.changed_paths),
            "noop_paths": len(report.noop_paths),
            "written_paths": len(report.written_paths),
            "diagnostics": len(report.diagnostics),
        },
    }
```

- [ ] **Step 4: Implement postflight checks**

Add `_postflight(project_root, preflight)`:

- Every replacement proposition file exists and parses via `parse_markdown_entity_file`.
- Every expected annotation target now matches live sidecar state.
- For `replace`, no input annotation remains promoted to original.
- For `split_partial`, assignments to original still point to original.
- Replacement `source_refs` include all expected assignment-derived refs.
- Original frontmatter has expected `status`, `superseded_by`, and/or `resynthesized_into`.
- Do not check graph materialization; Half D explicitly keeps live frontmatter lineage graph-invisible.

Use `_live_annotation_index(project_root)` for sidecar checks.

- [ ] **Step 5: Implement `apply_resynthesis_draft`**

Implementation shape:

```python
def apply_resynthesis_draft(
    project_root: Path,
    draft: ResynthesisDraft,
    *,
    as_of: date | None = None,
) -> ResynthesisApplyReport:
    project_root = project_root.resolve()
    preflight = plan_resynthesis_apply(project_root, draft, as_of=as_of)
    changed_paths, noop_paths = _changed_and_noop_paths(preflight.file_edits)
    written: list[str] = []
    for edit in preflight.file_edits:
        if not edit.changed:
            continue
        try:
            edit.path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(edit.path, edit.final_text)
        except OSError as exc:
            raise ResynthesisApplyError(
                f"[stage=write, files_written={len(written)}, written_paths={tuple(written)}] "
                f"failed to write {_path_string(edit.path)}: {exc}"
            ) from exc
        written.append(_path_string(edit.path))

    try:
        _postflight(project_root, preflight)
    except ResynthesisApplyError as exc:
        raise ResynthesisApplyError(f"[stage=postflight, written_paths={tuple(written)}] {exc}") from exc

    rewritten = tuple(
        sorted(
            annotation
            for annotation, target in preflight.expected_annotation_targets.items()
            if target != draft.original_proposition
        )
    )
    return ResynthesisApplyReport(
        status="ok",
        original_proposition=draft.original_proposition,
        replacement_propositions=tuple(sorted(row.id for row in draft.new_propositions)),
        rewritten_annotations=rewritten,
        changed_paths=changed_paths,
        noop_paths=noop_paths,
        written_paths=tuple(written),
        original_state=preflight.expected_original_state,
    )
```

- [ ] **Step 6: Verify**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_resynthesis.py science/tests/test_proposition_resynthesis_apply.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_resynthesis_apply.py science/tests/test_proposition_resynthesis_apply.py
rtk git commit -m "feat(4e): apply reviewed proposition resynthesis"
```

---

## Task 6: CLI Surfaces

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `science/tests/test_proposition_reconciliation_cli.py`:

```python
def test_scaffold_proposition_resynthesis_cli_writes_draft(tmp_path: Path):
    from test_proposition_resynthesis import _factorization_project
    from science_tool.annotation.cli import annotate_group

    ctx = _factorization_project(tmp_path)
    output = tmp_path / "draft.json"
    result = CliRunner().invoke(
        annotate_group,
        [
            "scaffold-proposition-resynthesis",
            "--root",
            str(tmp_path),
            "--input",
            str(ctx["review_path"]),
            "--action",
            ctx["action"].action_id,
            "--output",
            str(output),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["action_id"] == ctx["action"].action_id
    assert payload["new_propositions"] == []
    assert json.loads(result.output)["selected_action_id"] == ctx["action"].action_id


def test_validate_proposition_resynthesis_cli_reports_valid_draft(tmp_path: Path):
    from test_proposition_resynthesis import _draft_payload, _factorization_project
    from science_tool.annotation.cli import annotate_group

    ctx = _factorization_project(tmp_path)
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(_draft_payload(ctx)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-proposition-resynthesis",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["summary"]["replacement_propositions"] == 2


def test_apply_proposition_resynthesis_cli_applies_valid_draft(tmp_path: Path):
    from test_proposition_resynthesis import _draft_payload, _factorization_project
    from science_tool.annotation.cli import annotate_group

    ctx = _factorization_project(tmp_path)
    draft_path = tmp_path / "draft.json"
    draft_path.write_text(json.dumps(_draft_payload(ctx)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-resynthesis",
            "--root",
            str(tmp_path),
            "--input",
            str(draft_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert (tmp_path / "entities" / "propositions" / "broad-positive.md").exists()


def test_validate_proposition_resynthesis_cli_includes_input_path_on_malformed_json(tmp_path: Path):
    from science_tool.annotation.cli import annotate_group

    draft_path = tmp_path / "bad.json"
    draft_path.write_text("{", encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        ["validate-proposition-resynthesis", "--root", str(tmp_path), "--input", str(draft_path)],
    )

    assert result.exit_code != 0
    assert str(draft_path) in result.output
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_cli.py -q
```

Expected: FAIL because commands are not registered.

- [ ] **Step 3: Add command helpers and imports in `cli.py`**

Add three flat commands near `apply-proposition-reconciliation`:

```python
@annotate_group.command("scaffold-proposition-resynthesis")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--action", "action_id", default=None)
@click.option("--output", "output_path", default=None, type=click.Path(dir_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def scaffold_proposition_resynthesis_cmd(...):
    ...
```

Implementation requirements:

- Build live Half B plan from the single review input using `build_reconciliation_report` and `build_reconciliation_action_plan`.
- Call `build_resynthesis_scaffold`.
- If `--output` is set, write `json.dumps(draft_to_json(draft), indent=2, sort_keys=True) + "\n"`.
- JSON output should include:
  - `schema_version`
  - `status: "ok"`
  - `selected_action_id`
  - `output_path`
  - `draft`
- Table output:
  - `proposition resynthesis scaffold: action=<id> annotations=<n> replacements=0`
  - print `wrote JSON draft to <path>` when output is provided.

Add `validate-proposition-resynthesis`:

- Read JSON with input-path-specific errors.
- `parse_resynthesis_draft`.
- `validate_resynthesis_draft`.
- Serialize with a new `validation_report_to_json(report)` helper from `proposition_resynthesis.py`.
- Table output:
  - `proposition resynthesis validate: status=ok replacements=2 moved=2 retained=0`

Add `apply-proposition-resynthesis`:

- Read/parse draft.
- Call `apply_resynthesis_draft`.
- Serialize with `apply_resynthesis_report_to_json(report, project_root=project_root)`.
- Table output:
  - `proposition resynthesis apply: replacements=2 moved_annotations=2 changed=4 noop=0`
  - list changed/noop paths compactly like Half C.

All command exceptions from `ResynthesisDraftError`, `ResynthesisApplyError`, `ReconciliationValidationError`, and `ValueError` should become `click.ClickException`.

- [ ] **Step 4: Add report serializer for validation**

In `proposition_resynthesis.py`, add:

```python
def validation_report_to_json(report: ResynthesisValidationReport) -> dict[str, Any]:
    return {
        "schema_version": RESYNTHESIS_SCHEMA_VERSION,
        "status": report.status,
        "original_proposition": report.original_proposition,
        "replacement_propositions": report.replacement_propositions,
        "moved_annotations": report.moved_annotations,
        "retained_annotations": report.retained_annotations,
        "planned_changed_paths": report.planned_changed_paths,
        "planned_noop_paths": report.planned_noop_paths,
        "expected_annotation_targets": dict(report.expected_annotation_targets),
        "expected_source_refs_by_replacement": {
            key: list(value) for key, value in sorted(report.expected_source_refs_by_replacement.items())
        },
        "errors": [dict(error) for error in report.errors],
        "warnings": [dict(warning) for warning in report.warnings],
        "summary": {
            "replacement_propositions": report.replacement_propositions,
            "moved_annotations": report.moved_annotations,
            "retained_annotations": report.retained_annotations,
            "errors": len(report.errors),
            "warnings": len(report.warnings),
        },
    }
```

- [ ] **Step 5: Verify**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_cli.py science/tests/test_proposition_resynthesis.py science/tests/test_proposition_resynthesis_apply.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/cli.py science/src/science_tool/annotation/proposition_resynthesis.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "feat(4e): add proposition resynthesis cli"
```

---

## Task 7: Full Verification And Real-Corpus Smoke

**Files:**
- No source changes unless verification exposes a bug.

- [ ] **Step 1: Run focused tests**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_proposition_resynthesis.py \
  science/tests/test_proposition_resynthesis_apply.py \
  science/tests/test_proposition_reconciliation_cli.py \
  science/tests/test_entity_writer.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run type/lint checks**

Run:

```bash
rtk uv run --frozen ruff check science/src/science_tool/annotation/proposition_resynthesis.py science/src/science_tool/annotation/proposition_resynthesis_apply.py science/src/science_tool/annotation/cli.py science/tests/test_proposition_resynthesis.py science/tests/test_proposition_resynthesis_apply.py science/tests/test_proposition_reconciliation_cli.py
rtk uv run --frozen pyright science/src/science_tool/annotation/proposition_resynthesis.py science/src/science_tool/annotation/proposition_resynthesis_apply.py
```

Expected: PASS. If pyright is not configured for file-scoped invocation, run the repo's established pyright command and record the result.

- [ ] **Step 3: Run a read-only real-corpus scaffold smoke**

Use an existing reviewed factorization file only if one exists in the working corpus. Do not create or apply a real draft in `main` without explicit user approval.

Run:

```bash
rtk rg -n '"decision": "factorization_needs_resynthesis"|factorization_needs_resynthesis' results docs meta -g '*.json'
```

If a review JSON exists, run:

```bash
rtk uv run --frozen science annotate scaffold-proposition-resynthesis \
  --root . \
  --input <review-json> \
  --format json
```

Expected: Either a valid scaffold JSON, or a clear stale-review/action error. A stale real-corpus review is not automatically a Half D bug; inspect before changing code.

- [ ] **Step 4: Run all affected reconciliation tests**

Run:

```bash
rtk uv run --frozen pytest \
  science/tests/test_proposition_reconciliation.py \
  science/tests/test_proposition_reconciliation_plan.py \
  science/tests/test_proposition_reconciliation_apply.py \
  science/tests/test_proposition_reconciliation_cli.py \
  science/tests/test_proposition_resynthesis.py \
  science/tests/test_proposition_resynthesis_apply.py \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit verification fixes if needed**

Only commit if Step 1-4 required source or test fixes:

```bash
rtk git add <changed-files>
rtk git commit -m "test(4e): verify proposition resynthesis flow"
```

---

## Acceptance Checklist

- [ ] Scaffold builds a draft only from a current ready `resynthesize_proposition` action.
- [ ] Draft validate/apply rebuild live Half B state from `source_review`.
- [ ] Draft identity fields fail loud when stale.
- [ ] Unknown draft frontmatter keys fail in Half D validation, not silently through loader behavior.
- [ ] `replace` assigns every current input annotation away from the original.
- [ ] Input-set growth after scaffold is detected by the incomplete `replace` check.
- [ ] `split_partial` can retain reviewed annotations on the original while moving at least one.
- [ ] Replacement proposition files derive `paper:` and `annotation:` refs from assignments.
- [ ] Existing replacement files are accepted only when non-date content matches and existing `created`/`updated` are preserved.
- [ ] Sidecar rewrites are merged per file and conflict only on same-annotation incompatible targets.
- [ ] Apply can resume from a mixed state where some annotations already point to `to`.
- [ ] Re-running the same draft is a no-op.
- [ ] `replace` marks the original superseded and writes `superseded_by` for one replacement or `resynthesized_into` for multiple replacements.
- [ ] Original `source_refs` remain unchanged as historical provenance.
- [ ] `resynthesized_into` is managed by entity reference removal/rewrite machinery.
- [ ] Half D does not claim graph-visible live supersession lineage.
- [ ] Half C still rejects direct `resynthesize_proposition` actions.

---

## Notes For Implementers

- Keep path examples in docs/tests generic or rooted in temp dirs. If a documented user path is needed, use the project convention `~/d/...` rather than host-specific absolute paths.
- Do not add graph materialization for `superseded_by` or `resynthesized_into` in this plan. That is future work for live lineage visibility.
- Do not create compatibility aliases for command names or schemas. Half D is new and can fail early on malformed drafts.
- Do not let apply synthesize scientific wording from hints. Replacement proposition text is accepted only from reviewed draft fields.
- If tests import helpers from another test module, keep those helpers clearly named with `_` and avoid circular imports. If import-time coupling becomes awkward, duplicate small fixture helpers rather than adding production-only fixture utilities.
