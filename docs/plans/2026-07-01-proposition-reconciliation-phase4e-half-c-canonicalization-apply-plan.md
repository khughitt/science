# Proposition Reconciliation Phase 4e Half C Canonicalization Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mutation command that applies only ready `canonicalize_propositions` reconciliation actions by moving provenance, rewriting sidecar `promoted_to` backlinks, and marking duplicate propositions as superseded.

**Architecture:** Keep the CLI thin and put apply mechanics in a new focused module, `science_tool.annotation.proposition_reconciliation_apply`. The command rebuilds the current Half B action plan from reviewed JSON inputs, preflights every file edit in memory, writes deterministic atomic replacements only after preflight succeeds, and verifies the live corpus afterward.

**Tech Stack:** Python dataclasses, Click, existing annotation sidecar models/serialization, existing entity markdown parser/rendering helpers, `pytest`, `CliRunner`.

---

## File Structure

- Modify: `science/src/science_tool/entities.py`
  - Add pure rendering helpers so Half C can compute final entity text during preflight while preserving the same ordering/dedup/update semantics as `append_entity_source_ref`.
  - Refactor `append_entity_source_ref` to call the new source-ref renderer.

- Create: `science/src/science_tool/annotation/proposition_reconciliation_apply.py`
  - Owns action selection, live sidecar backlink scanning, preflight, planned file edits, write execution, postflight validation, and JSON/table-ready reports.
  - Does not parse saved Half B plan JSON as authority.

- Modify: `science/src/science_tool/annotation/cli.py`
  - Add flat command `apply-proposition-reconciliation`.
  - Read reviewed JSON inputs, call the apply module, render table/JSON output, and convert apply errors to `click.ClickException`.

- Modify: `science/tests/test_entity_writer.py`
  - Cover pure entity rendering helpers and the existing `append_entity_source_ref` behavior after refactor.

- Create: `science/tests/test_proposition_reconciliation_apply.py`
  - Unit tests for action selection, preflight, sidecar worklist authority, shared-sidecar merge, idempotency, and postflight blockers, plus an end-to-end test that rebuilds cross-paper evidence and asserts belief re-attribution onto the canonical proposition.

- Modify: `science/tests/test_proposition_reconciliation_cli.py`
  - CLI smoke tests for successful apply, JSON/table output, `--action`, and hard rejection of non-canonicalization actions.

---

### Task 1: Pure Entity Rendering Helpers

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Test: `science/tests/test_entity_writer.py`

- [ ] **Step 1: Write failing tests for source-ref rendering and frontmatter updates**

Append these tests to `science/tests/test_entity_writer.py`:

```python
def test_render_entity_source_refs_computes_text_without_writing(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    dest.write_text(
        "---\n"
        "id: proposition:existing\n"
        "type: proposition\n"
        "title: Existing\n"
        "status: active\n"
        "source_refs:\n"
        '  - "paper:old"\n'
        'created: "2026-06-01"\n'
        'updated: "2026-06-01"\n'
        "---\n"
        "# Existing\n\nHand-authored prose.\n",
        encoding="utf-8",
    )

    from science_tool.entities import render_entity_source_refs

    rendered, changed = render_entity_source_refs(
        dest,
        ["paper:old", "annotation:entities/papers/A.source#a1", "paper:A"],
        as_of=date(2026, 7, 1),
    )

    assert changed is True
    assert dest.read_text(encoding="utf-8").count("paper:A") == 0
    assert "Hand-authored prose." in rendered
    assert "paper:old" in rendered
    assert "annotation:entities/papers/A.source#a1" in rendered
    assert "paper:A" in rendered
    assert (
        "updated: 2026-07-01" in rendered
        or 'updated: "2026-07-01"' in rendered
        or "updated: '2026-07-01'" in rendered
    )


def test_render_entity_source_refs_noops_when_all_refs_exist(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    original = (
        "---\n"
        "id: proposition:existing\n"
        "type: proposition\n"
        "title: Existing\n"
        "status: active\n"
        "source_refs:\n"
        '  - "paper:old"\n'
        'updated: "2026-06-01"\n'
        "---\n"
        "Body.\n"
    )
    dest.write_text(original, encoding="utf-8")

    from science_tool.entities import render_entity_source_refs

    rendered, changed = render_entity_source_refs(dest, ["paper:old"], as_of=date(2026, 7, 1))

    assert changed is False
    assert rendered == original


def test_render_entity_frontmatter_updates_sets_supersession_without_writing(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "duplicate.md"
    dest.write_text(
        "---\n"
        "id: proposition:duplicate\n"
        "type: proposition\n"
        "title: Duplicate\n"
        "status: active\n"
        'updated: "2026-06-01"\n'
        "---\n"
        "Duplicate body.\n",
        encoding="utf-8",
    )

    from science_tool.entities import render_entity_frontmatter_updates

    rendered, changed = render_entity_frontmatter_updates(
        dest,
        {"status": "superseded", "superseded_by": "proposition:canonical"},
        as_of=date(2026, 7, 1),
    )

    assert changed is True
    assert "Duplicate body." in rendered
    assert "status: superseded" in rendered
    assert "superseded_by: proposition:canonical" in rendered
    assert "superseded_by" not in dest.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_entity_writer.py -q
```

Expected: FAIL with import errors for `render_entity_source_refs` and `render_entity_frontmatter_updates`.

- [ ] **Step 3: Add pure render helpers and refactor `append_entity_source_ref`**

In `science/src/science_tool/entities.py`, replace the body of `append_entity_source_ref` and add the two helpers immediately above it:

```python
def render_entity_source_refs(
    file_path: Path,
    refs_to_append: Sequence[str],
    *,
    as_of: date | None = None,
) -> tuple[str, bool]:
    """Return rendered entity markdown after appending missing source refs.

    This is the pure form of append_entity_source_ref: existing refs keep their
    current order, new refs are appended in caller-provided order, exact strings
    are deduped, and updated advances only when the rendered content changes.
    """
    frontmatter, body = _parse_markdown_file(file_path)
    refs = list(frontmatter.get("source_refs") or [])
    changed = False
    for ref in refs_to_append:
        if ref in refs:
            continue
        refs.append(ref)
        changed = True
    if not changed:
        return (file_path.read_text(encoding="utf-8"), False)
    frontmatter["source_refs"] = refs
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    return (_render_markdown(frontmatter, body), True)


def render_entity_frontmatter_updates(
    file_path: Path,
    updates: Mapping[str, object],
    *,
    as_of: date | None = None,
) -> tuple[str, bool]:
    """Return rendered entity markdown after applying exact frontmatter updates."""
    frontmatter, body = _parse_markdown_file(file_path)
    changed = False
    for key, value in updates.items():
        if frontmatter.get(key) == value:
            continue
        frontmatter[key] = value
        changed = True
    if not changed:
        return (file_path.read_text(encoding="utf-8"), False)
    frontmatter["updated"] = (as_of or date.today()).isoformat()
    return (_render_markdown(frontmatter, body), True)


def append_entity_source_ref(file_path: Path, ref: str, *, as_of: date | None = None) -> bool:
    """Append ``ref`` to an existing entity file's ``source_refs`` frontmatter, preserving
    the body. Returns True if added, False if already present. Used by promotion LINK so a
    hand-authored proposition's prose is never clobbered. When a ref is added, `updated`
    advances to ``as_of`` (or today), matching other entity mutations."""
    rendered, changed = render_entity_source_refs(file_path, [ref], as_of=as_of)
    if not changed:
        return False
    _atomic_replace_text(file_path, rendered)
    return True
```

Also ensure the existing imports at the top of `entities.py` include:

```python
from collections.abc import Mapping, Sequence
```

If `Mapping` is already imported from another typing module, consolidate to one import rather than duplicating names.

- [ ] **Step 4: Run the entity writer tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_entity_writer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/entities.py science/tests/test_entity_writer.py
rtk git commit -m "feat(4e): add pure entity render helpers"
```

---

### Task 2: Apply Module Skeleton And Action Selection

**Files:**
- Create: `science/src/science_tool/annotation/proposition_reconciliation_apply.py`
- Test: `science/tests/test_proposition_reconciliation_apply.py`

- [ ] **Step 1: Write failing action-selection tests**

Create `science/tests/test_proposition_reconciliation_apply.py` with these imports and tests:

```python
import json
from pathlib import Path

import pytest

from science_tool.annotation.proposition_reconciliation import judgment_id
from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
    reconciliation_action_id,
)
from science_tool.annotation.proposition_reconciliation_apply import (
    ReconciliationApplyError,
    select_canonicalization_actions,
)


def _action(
    *,
    kind: str = "canonicalize_propositions",
    status: str = "ready",
    action_id: str | None = None,
    canonical: str | None = "proposition:a",
    members: tuple[str, ...] = ("proposition:a", "proposition:b"),
    blockers: tuple[dict, ...] = (),
) -> ReconciliationAction:
    judgment = judgment_id("same_claim", "same_claim", members)
    return ReconciliationAction(
        action_id=action_id or reconciliation_action_id(kind, judgment, canonical or members[0], members[1:]),
        kind=kind,
        status=status,
        decision="same_claim",
        candidate_id="reconcile:same-claim/candidate",
        judgment_id=judgment,
        confidence="high",
        rationale="Same claim.",
        source_review="review.json",
        review_source="llm-review:claude:proposition-reconcile-v1",
        canonical_proposition=canonical,
        members=members,
        inputs={
            "source_ref_moves": (
                {"from": "proposition:b", "to": "proposition:a", "source_refs": ("paper:B",)},
            ),
            "sidecar_backlink_rewrites": (
                {
                    "from": "proposition:b",
                    "to": "proposition:a",
                    "annotation_refs": ("annotation:entities/papers/B.source#b1",),
                },
            ),
            "archive_candidates": ("proposition:b",),
        },
        blockers=blockers,
    )


def test_select_canonicalization_actions_returns_all_ready_when_unfiltered():
    ready = _action()
    advisory = _action(kind="record_reconciliation_decision", status="advisory", canonical=None)
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=("review.json",), actions=(advisory, ready))

    selected = select_canonicalization_actions(plan, requested_action_ids=())

    assert selected == (ready,)


def test_select_canonicalization_actions_rejects_plan_errors():
    plan = ReconciliationActionPlan(
        schema_version=1,
        source_reviews=("review.json",),
        actions=(_action(),),
        errors=({"reason": "component-too-large", "detail": "too many", "members": []},),
    )

    with pytest.raises(ReconciliationApplyError, match="action plan has top-level errors"):
        select_canonicalization_actions(plan, requested_action_ids=())


def test_select_canonicalization_actions_rejects_requested_advisory_action():
    advisory = _action(
        kind="record_reconciliation_decision",
        status="advisory",
        canonical=None,
        action_id="reconcile-action:advisory",
    )
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=("review.json",), actions=(advisory,))

    with pytest.raises(ReconciliationApplyError, match="not executable by Half C"):
        select_canonicalization_actions(plan, requested_action_ids=("reconcile-action:advisory",))


def test_select_canonicalization_actions_rejects_empty_applicable_set():
    plan = ReconciliationActionPlan(schema_version=1, source_reviews=("review.json",), actions=())

    with pytest.raises(ReconciliationApplyError, match="no ready canonicalize_propositions actions"):
        select_canonicalization_actions(plan, requested_action_ids=())
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_apply.py -q
```

Expected: FAIL because `proposition_reconciliation_apply.py` does not exist.

- [ ] **Step 3: Create the apply module skeleton and selector**

Create `science/src/science_tool/annotation/proposition_reconciliation_apply.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from science_tool.annotation.proposition_reconciliation_plan import (
    ReconciliationAction,
    ReconciliationActionPlan,
)


class ReconciliationApplyError(RuntimeError):
    """Raised when proposition reconciliation apply cannot proceed safely."""


@dataclass(frozen=True)
class PlannedFileEdit:
    path: Path
    reason: str
    before_sha256: str
    after_sha256: str
    final_text: str
    changed: bool


@dataclass(frozen=True)
class ApplyActionResult:
    action_id: str
    kind: str
    canonical_proposition: str
    members: tuple[str, ...]
    duplicate_propositions: tuple[str, ...]
    status: str
    changed_paths: tuple[str, ...] = ()
    noop_paths: tuple[str, ...] = ()
    diagnostics: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class ReconciliationApplyReport:
    status: str
    selected_actions: int
    changed_paths: tuple[str, ...]
    noop_paths: tuple[str, ...]
    actions: tuple[ApplyActionResult, ...]
    diagnostics: tuple[Mapping[str, Any], ...] = ()
    written_paths: tuple[str, ...] = ()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def select_canonicalization_actions(
    plan: ReconciliationActionPlan,
    *,
    requested_action_ids: Sequence[str] = (),
) -> tuple[ReconciliationAction, ...]:
    if plan.errors:
        raise ReconciliationApplyError("action plan has top-level errors; run plan-proposition-reconciliation first")

    by_id = {action.action_id: action for action in plan.actions}
    if requested_action_ids:
        unknown = sorted(set(requested_action_ids) - set(by_id))
        if unknown:
            raise ReconciliationApplyError(f"unknown reconciliation action(s): {', '.join(unknown)}")
        candidates = tuple(by_id[action_id] for action_id in requested_action_ids)
    else:
        candidates = tuple(
            action
            for action in plan.actions
            if action.kind == "canonicalize_propositions" and action.status == "ready" and not action.blockers
        )

    selected: list[ReconciliationAction] = []
    for action in candidates:
        if action.kind == "resynthesize_proposition":
            raise ReconciliationApplyError(
                f"{action.action_id} is resynthesize_proposition; factorization resynthesis is not executable by Half C"
            )
        if action.kind != "canonicalize_propositions" or action.status != "ready" or action.blockers:
            raise ReconciliationApplyError(
                f"{action.action_id} is {action.status} {action.kind}, not executable by Half C"
            )
        if not action.canonical_proposition:
            raise ReconciliationApplyError(f"{action.action_id} has no canonical_proposition")
        if len(action.members) < 2:
            raise ReconciliationApplyError(f"{action.action_id} has fewer than two members")
        selected.append(action)

    if not selected:
        raise ReconciliationApplyError("no ready canonicalize_propositions actions to apply")

    seen_members: dict[str, str] = {}
    for action in selected:
        for member in action.members:
            other = seen_members.get(member)
            if other is not None and other != action.action_id:
                raise ReconciliationApplyError(
                    f"{member} is targeted by multiple selected actions: {other}, {action.action_id}"
                )
            seen_members[member] = action.action_id

    return tuple(sorted(selected, key=lambda action: action.action_id))
```

- [ ] **Step 4: Run the selection tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_apply.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_apply.py science/tests/test_proposition_reconciliation_apply.py
rtk git commit -m "feat(4e): select canonicalization apply actions"
```

---

### Task 3: Live Backlink Scan And Preflight Planning

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py`
- Test: `science/tests/test_proposition_reconciliation_apply.py`

- [ ] **Step 1: Add test fixtures for a minimal reconciliation project**

Add these helpers near the top of `science/tests/test_proposition_reconciliation_apply.py`:

```python
from dataclasses import replace
from datetime import datetime, timezone

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.proposition_reconciliation import build_reconciliation_report
from science_tool.annotation.proposition_reconciliation_plan import (
    ReviewedReconciliationInput,
    build_reconciliation_action_plan,
)
from science_tool.annotation.proposition_reconciliation_apply import (
    plan_canonicalization_apply,
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
    superseded_by: str | None = None,
    subject: str = "BRCA1 loss",
    object_: str = "genomic instability",
) -> Path:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    extra = ""
    if source_refs:
        extra += "source_refs:\n" + "".join(f'  - "{ref}"\n' for ref in source_refs)
    if superseded_by is not None:
        extra += f"superseded_by: {superseded_by}\n"
    path.write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        "type: proposition\n"
        f"title: {title}\n"
        f"status: {status}\n"
        f"subject: {subject}\n"
        "predicate: affects\n"
        f"object: {object_}\n"
        "polarity: positive\n"
        'created: "2026-06-01"\n'
        'updated: "2026-06-01"\n'
        f"{extra}"
        "---\n"
        f"{title} body.\n",
        encoding="utf-8",
    )
    return path


def _ann(annotation_id: str, promoted_to: str) -> Annotation:
    return Annotation(
        id=annotation_id,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=annotation_id, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value='{"section":"results","stance":"asserted"}', format="application/json"),),
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
    md.write_text("Paper body.\n", encoding="utf-8")
    sidecar = anno_io.sidecar_for_markdown(md)
    anno_io.write_sidecar(sidecar, anno_io.Sidecar(annotations=annotations))
    return sidecar


def _review_doc_for_current_candidate(root: Path, canonical: str = "proposition:a") -> dict:
    report = build_reconciliation_report(root)
    candidate = report.same_claim_candidates[0]
    members = list(candidate.propositions)
    return {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate.candidate_id,
                "judgment_id": judgment_id("same_claim", "same_claim", members),
                "lane": "same_claim",
                "decision": "same_claim",
                "canonical_proposition": canonical,
                "members": members,
                "rationale": "Same signed relation over same endpoints.",
                "confidence": "high",
            }
        ],
    }


def _ready_plan(root: Path, review_doc: dict) -> ReconciliationActionPlan:
    report = build_reconciliation_report(root)
    return build_reconciliation_action_plan(
        report,
        [ReviewedReconciliationInput(path="review.json", doc=review_doc)],
    )


def _manual_ready_plan(
    *,
    actions: tuple[ReconciliationAction, ...] | None = None,
) -> ReconciliationActionPlan:
    return ReconciliationActionPlan(
        schema_version=1,
        source_reviews=("review.json",),
        actions=actions or (_action(),),
    )
```

- [ ] **Step 2: Write failing preflight tests**

Append these tests:

```python
def test_plan_canonicalization_apply_uses_live_sidecar_backlinks_not_only_half_b_inputs(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021",),
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    action = replace(
        _action(),
        inputs={
            "source_ref_moves": (
                {"from": "proposition:b", "to": "proposition:a", "source_refs": ("paper:B2021",)},
            ),
            "sidecar_backlink_rewrites": (
                {"from": "proposition:b", "to": "proposition:a", "annotation_refs": ()},
            ),
            "archive_candidates": ("proposition:b",),
        },
    )
    plan = _manual_ready_plan(actions=(action,))

    preflight = plan_canonicalization_apply(tmp_path, plan, requested_action_ids=())

    canonical_edit = next(edit for edit in preflight.file_edits if edit.path.name == "a.md")
    assert "paper:B2021" in canonical_edit.final_text
    assert "annotation:entities/papers/B2021.source#b1" in canonical_edit.final_text
    assert any(
        diag["reason"] == "half_b_missing_live_backlink"
        for diag in preflight.diagnostics
    )


def test_plan_canonicalization_apply_merges_distinct_rewrites_in_same_sidecar(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/Shared.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/Shared.source#b1"),
    )
    _proposition(
        tmp_path,
        "c",
        "TP53 loss increases chromosomal instability",
        source_refs=("paper:C2022", "annotation:entities/papers/Shared.source#c1"),
        subject="TP53 loss",
        object_="chromosomal instability",
    )
    _proposition(
        tmp_path,
        "d",
        "Loss of TP53 raises chromosomal instability",
        source_refs=("paper:D2023", "annotation:entities/papers/Shared.source#d1"),
        subject="TP53 loss",
        object_="chromosomal instability",
    )
    _paper_sidecar(
        tmp_path,
        "Shared",
        (
            _ann("a1", "proposition:a"),
            _ann("b1", "proposition:b"),
            _ann("c1", "proposition:c"),
            _ann("d1", "proposition:d"),
        ),
    )
    first = replace(
        _action(),
        inputs={
            "source_ref_moves": (
                {
                    "from": "proposition:b",
                    "to": "proposition:a",
                    "source_refs": ("paper:B2021", "annotation:entities/papers/Shared.source#b1"),
                },
            ),
            "sidecar_backlink_rewrites": (
                {
                    "from": "proposition:b",
                    "to": "proposition:a",
                    "annotation_refs": ("annotation:entities/papers/Shared.source#b1",),
                },
            ),
            "archive_candidates": ("proposition:b",),
        },
    )
    second = _action(
        action_id="reconcile-action:second",
        canonical="proposition:c",
        members=("proposition:c", "proposition:d"),
    )
    second = replace(
        second,
        inputs={
            "source_ref_moves": (
                {
                    "from": "proposition:d",
                    "to": "proposition:c",
                    "source_refs": ("paper:D2023", "annotation:entities/papers/Shared.source#d1"),
                },
            ),
            "sidecar_backlink_rewrites": (
                {
                    "from": "proposition:d",
                    "to": "proposition:c",
                    "annotation_refs": ("annotation:entities/papers/Shared.source#d1",),
                },
            ),
            "archive_candidates": ("proposition:d",),
        },
    )
    plan = _manual_ready_plan(actions=(first, second))

    preflight = plan_canonicalization_apply(tmp_path, plan, requested_action_ids=())

    sidecar_edits = [edit for edit in preflight.file_edits if edit.path.name == "Shared.source.anno.trig"]
    assert len(sidecar_edits) == 1
    assert "proposition:a" in sidecar_edits[0].final_text
    assert "proposition:c" in sidecar_edits[0].final_text


def test_plan_canonicalization_apply_errors_when_duplicate_superseded_elsewhere(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
        status="superseded",
        superseded_by="proposition:other",
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    review_doc = _review_doc_for_current_candidate(tmp_path)
    plan = _ready_plan(tmp_path, review_doc)

    with pytest.raises(ReconciliationApplyError, match="superseded_by proposition:other"):
        plan_canonicalization_apply(tmp_path, plan, requested_action_ids=())
```

- [ ] **Step 3: Run the failing preflight tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_apply.py -q
```

Expected: FAIL because `plan_canonicalization_apply` and preflight types are not implemented.

- [ ] **Step 4: Implement live backlink scanning and preflight planning**

Extend `science/src/science_tool/annotation/proposition_reconciliation_apply.py` with these imports:

```python
from dataclasses import replace
from datetime import date

from science_tool.annotation.cross_paper_evidence import (
    _iter_project_annotation_sidecar_paths,
    _resolve_paper_ref,
)
from science_tool.annotation.io import serialize_sidecar
from science_tool.annotation.model import Sidecar
from science_tool.annotation.query import (
    SidecarParseError,
    entity_relpath_for_sidecar,
    read_sidecar_strict,
)
from science_tool.entities import (
    EntityCommandError,
    find_entity,
    parse_markdown_entity_file,
    render_entity_frontmatter_updates,
    render_entity_source_refs,
)
```

Then add these dataclasses and helpers below the existing report dataclasses:

```python
@dataclass(frozen=True)
class InboundBacklink:
    duplicate: str
    canonical: str
    annotation_ref: str
    paper_ref: str
    sidecar_path: Path
    annotation_id: str
    current_promoted_to: str


@dataclass(frozen=True)
class CanonicalizationPreflight:
    actions: tuple[ReconciliationAction, ...]
    file_edits: tuple[PlannedFileEdit, ...]
    expected_source_refs_by_canonical: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    diagnostics: tuple[Mapping[str, Any], ...] = ()


def _current_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _edit(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    before = _current_text(path)
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=_sha256_text(before),
        after_sha256=_sha256_text(final_text),
        final_text=final_text,
        changed=before != final_text,
    )


def _annotation_ref(sidecar_path: Path, project_root: Path, annotation_id: str) -> str:
    return f"annotation:{entity_relpath_for_sidecar(sidecar_path, project_root)}#{annotation_id}"


def _live_annotation_index(project_root: Path) -> dict[str, tuple[Path, Sidecar, str | None]]:
    index: dict[str, tuple[Path, Sidecar, str | None]] = {}
    for sidecar_path in _iter_project_annotation_sidecar_paths(project_root):
        try:
            sidecar = read_sidecar_strict(sidecar_path)
        except SidecarParseError as exc:
            raise ReconciliationApplyError(str(exc)) from exc
        for ann in sidecar.annotations:
            index[_annotation_ref(sidecar_path, project_root, ann.id)] = (
                sidecar_path,
                sidecar,
                ann.promoted_to,
            )
    return index


def _duplicate_to_canonical(actions: Sequence[ReconciliationAction]) -> dict[str, str]:
    out: dict[str, str] = {}
    for action in actions:
        canonical = str(action.canonical_proposition)
        for member in action.members:
            if member == canonical:
                continue
            previous = out.get(member)
            if previous is not None and previous != canonical:
                raise ReconciliationApplyError(
                    f"{member} maps to both {previous} and {canonical}"
                )
            out[member] = canonical
    return out


def scan_inbound_backlinks(
    project_root: Path,
    duplicate_to_canonical: Mapping[str, str],
) -> tuple[InboundBacklink, ...]:
    backlinks: list[InboundBacklink] = []
    for sidecar_path in _iter_project_annotation_sidecar_paths(project_root):
        try:
            sidecar = read_sidecar_strict(sidecar_path)
        except SidecarParseError as exc:
            raise ReconciliationApplyError(str(exc)) from exc
        paper_ref = _resolve_paper_ref(sidecar_path)
        if paper_ref is None:
            if any(ann.promoted_to in duplicate_to_canonical for ann in sidecar.annotations):
                raise ReconciliationApplyError(f"{sidecar_path} has duplicate backlinks but no resolvable paper ref")
            continue
        for ann in sidecar.annotations:
            if ann.promoted_to not in duplicate_to_canonical:
                continue
            duplicate = str(ann.promoted_to)
            backlinks.append(
                InboundBacklink(
                    duplicate=duplicate,
                    canonical=duplicate_to_canonical[duplicate],
                    annotation_ref=_annotation_ref(sidecar_path, project_root, ann.id),
                    paper_ref=paper_ref,
                    sidecar_path=sidecar_path,
                    annotation_id=ann.id,
                    current_promoted_to=duplicate,
                )
            )
    return tuple(sorted(backlinks, key=lambda row: (str(row.sidecar_path), row.annotation_id)))
```

Add these planner helpers:

```python
def _listed_sidecar_refs(actions: Sequence[ReconciliationAction]) -> dict[str, str]:
    listed: dict[str, str] = {}
    for action in actions:
        for row in action.inputs.get("sidecar_backlink_rewrites", ()):
            duplicate = str(row["from"])
            for annotation_ref in row.get("annotation_refs", ()):
                listed[str(annotation_ref)] = duplicate
    return listed


def _validate_listed_refs(
    *,
    listed_refs: Mapping[str, str],
    live_backlinks: Sequence[InboundBacklink],
    live_index: Mapping[str, tuple[Path, Sidecar, str | None]],
    duplicate_to_canonical: Mapping[str, str],
) -> tuple[Mapping[str, Any], ...]:
    diagnostics: list[Mapping[str, Any]] = []
    live_refs = {row.annotation_ref for row in live_backlinks}
    for row in live_backlinks:
        if row.annotation_ref not in listed_refs:
            diagnostics.append(
                {
                    "reason": "half_b_missing_live_backlink",
                    "annotation_ref": row.annotation_ref,
                    "duplicate": row.duplicate,
                    "canonical": row.canonical,
                }
            )
    for annotation_ref, duplicate in sorted(listed_refs.items()):
        if annotation_ref in live_refs:
            continue
        live = live_index.get(annotation_ref)
        canonical = duplicate_to_canonical.get(duplicate)
        if live is not None and live[2] == canonical:
            diagnostics.append(
                {
                    "reason": "listed_backlink_already_canonical",
                    "annotation_ref": annotation_ref,
                    "duplicate": duplicate,
                    "canonical": canonical,
                }
            )
            continue
        if live is None:
            raise ReconciliationApplyError(f"{annotation_ref} from Half B inputs resolves to no live sidecar annotation")
        raise ReconciliationApplyError(
            f"{annotation_ref} from Half B inputs points to {live[2]!r}, not {duplicate} or {canonical}"
        )
    return tuple(diagnostics)


def _entity_location(project_root: Path, ref: str):
    try:
        return find_entity(project_root, ref)
    except EntityCommandError as exc:
        raise ReconciliationApplyError(str(exc)) from exc


def _canonical_source_refs(
    action: ReconciliationAction,
    live_backlinks: Sequence[InboundBacklink],
) -> tuple[str, ...]:
    refs: set[str] = set()
    for row in action.inputs.get("source_ref_moves", ()):
        refs.update(str(ref) for ref in row.get("source_refs", ()))
    for backlink in live_backlinks:
        if backlink.duplicate in action.members:
            refs.add(backlink.paper_ref)
            refs.add(backlink.annotation_ref)
    return tuple(sorted(refs))


def _sidecar_final_texts(
    project_root: Path,
    live_backlinks: Sequence[InboundBacklink],
) -> dict[Path, str]:
    by_path: dict[Path, dict[str, str]] = {}
    for backlink in live_backlinks:
        path_targets = by_path.setdefault(backlink.sidecar_path, {})
        previous = path_targets.get(backlink.annotation_id)
        if previous is not None and previous != backlink.canonical:
            raise ReconciliationApplyError(
                f"{backlink.annotation_ref} has incompatible rewrite targets: {previous}, {backlink.canonical}"
            )
        path_targets[backlink.annotation_id] = backlink.canonical

    final_texts: dict[Path, str] = {}
    for sidecar_path, targets in sorted(by_path.items(), key=lambda item: str(item[0])):
        try:
            sidecar = read_sidecar_strict(sidecar_path)
        except SidecarParseError as exc:
            raise ReconciliationApplyError(str(exc)) from exc
        annotations = []
        for ann in sidecar.annotations:
            target = targets.get(ann.id)
            annotations.append(replace(ann, promoted_to=target) if target is not None else ann)
        final_texts[sidecar_path] = serialize_sidecar(
            Sidecar(
                annotations=tuple(annotations),
                ledgers=sidecar.ledgers,
                shared_targets=sidecar.shared_targets,
            )
        )
    return final_texts
```

Finally add `plan_canonicalization_apply`:

```python
def plan_canonicalization_apply(
    project_root: Path,
    plan: ReconciliationActionPlan,
    *,
    requested_action_ids: Sequence[str] = (),
    as_of: date | None = None,
) -> CanonicalizationPreflight:
    root = project_root.resolve()
    actions = select_canonicalization_actions(plan, requested_action_ids=requested_action_ids)
    duplicate_to_canonical = _duplicate_to_canonical(actions)
    live_backlinks = scan_inbound_backlinks(root, duplicate_to_canonical)
    live_index = _live_annotation_index(root)
    diagnostics = list(
        _validate_listed_refs(
            listed_refs=_listed_sidecar_refs(actions),
            live_backlinks=live_backlinks,
            live_index=live_index,
            duplicate_to_canonical=duplicate_to_canonical,
        )
    )

    edits: dict[Path, PlannedFileEdit] = {}
    expected_source_refs_by_canonical: dict[str, tuple[str, ...]] = {}
    for action in actions:
        canonical = str(action.canonical_proposition)
        canonical_location = _entity_location(root, canonical)
        refs = _canonical_source_refs(action, live_backlinks)
        expected_source_refs_by_canonical[canonical] = tuple(
            sorted(set(expected_source_refs_by_canonical.get(canonical, ())) | set(refs))
        )
        canonical_text, _ = render_entity_source_refs(
            canonical_location.path,
            refs,
            as_of=as_of,
        )
        edits[canonical_location.path] = _edit(
            canonical_location.path,
            canonical_text,
            f"canonical source_refs for {action.action_id}",
        )

        for duplicate in sorted(ref for ref in action.members if ref != canonical):
            duplicate_location = _entity_location(root, duplicate)
            frontmatter, _body = parse_markdown_entity_file(duplicate_location.path)
            existing_superseded_by = frontmatter.get("superseded_by")
            if existing_superseded_by is not None and existing_superseded_by != canonical:
                raise ReconciliationApplyError(
                    f"{duplicate} superseded_by {existing_superseded_by}, not {canonical}"
                )
            duplicate_text, _ = render_entity_frontmatter_updates(
                duplicate_location.path,
                {"status": "superseded", "superseded_by": canonical},
                as_of=as_of,
            )
            edits[duplicate_location.path] = _edit(
                duplicate_location.path,
                duplicate_text,
                f"mark duplicate superseded for {action.action_id}",
            )

    for sidecar_path, final_text in _sidecar_final_texts(root, live_backlinks).items():
        edits[sidecar_path] = _edit(sidecar_path, final_text, "rewrite sidecar promoted_to backlinks")

    return CanonicalizationPreflight(
        actions=actions,
        file_edits=tuple(edits[path] for path in sorted(edits)),
        expected_source_refs_by_canonical=expected_source_refs_by_canonical,
        diagnostics=tuple(diagnostics),
    )
```

- [ ] **Step 5: Run the preflight tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_apply.py -q
```

Expected: PASS for the new preflight tests plus Task 2 tests.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_apply.py science/tests/test_proposition_reconciliation_apply.py
rtk git commit -m "feat(4e): preflight canonicalization apply"
```

---

### Task 4: Write Execution, Idempotency, And Postflight

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py`
- Test: `science/tests/test_proposition_reconciliation_apply.py`

- [ ] **Step 1: Write failing apply and idempotency tests**

Append these tests:

```python
def test_apply_canonicalization_rewrites_files_and_postflight_passes(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    sidecar = _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    review_doc = _review_doc_for_current_candidate(tmp_path)
    plan = _ready_plan(tmp_path, review_doc)

    from science_tool.annotation.proposition_reconciliation_apply import apply_canonicalization_plan

    report = apply_canonicalization_plan(tmp_path, plan, requested_action_ids=())

    assert report.status == "ok"
    assert report.selected_actions == 1
    assert any(path.endswith("entities/propositions/a.md") for path in report.changed_paths)
    assert "paper:B2021" in (tmp_path / "entities" / "propositions" / "a.md").read_text(encoding="utf-8")
    duplicate_text = (tmp_path / "entities" / "propositions" / "b.md").read_text(encoding="utf-8")
    assert "status: superseded" in duplicate_text
    assert "superseded_by: proposition:a" in duplicate_text
    assert "proposition:a" in sidecar.read_text(encoding="utf-8")
    assert "proposition:b" not in sidecar.read_text(encoding="utf-8")


def test_apply_canonicalization_is_idempotent_on_second_run(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    review_doc = _review_doc_for_current_candidate(tmp_path)

    from science_tool.annotation.proposition_reconciliation_apply import apply_canonicalization_plan

    first_plan = _ready_plan(tmp_path, review_doc)
    first = apply_canonicalization_plan(tmp_path, first_plan, requested_action_ids=())
    second_plan = _ready_plan(tmp_path, review_doc)
    second = apply_canonicalization_plan(tmp_path, second_plan, requested_action_ids=())

    assert first.changed_paths
    assert second.status == "ok"
    assert second.changed_paths == ()
    assert second.noop_paths


def test_postflight_fails_if_duplicate_backlink_remains_after_write(tmp_path: Path, monkeypatch):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    review_doc = _review_doc_for_current_candidate(tmp_path)
    plan = _ready_plan(tmp_path, review_doc)

    import science_tool.annotation.proposition_reconciliation_apply as apply_mod

    original_write = apply_mod.atomic_write_text

    def skip_sidecar_write(path: Path, text: str) -> None:
        if path.name.endswith(".anno.trig"):
            return
        original_write(path, text)

    monkeypatch.setattr(apply_mod, "atomic_write_text", skip_sidecar_write)

    with pytest.raises(ReconciliationApplyError, match="stage=postflight") as excinfo:
        apply_mod.apply_canonicalization_plan(tmp_path, plan, requested_action_ids=())
    # Postflight failure must surface the files already written this run for recovery.
    message = str(excinfo.value)
    assert "written_paths=" in message
    assert "b.md" in message
```

- [ ] **Step 2: Run the failing apply tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_apply.py -q
```

Expected: FAIL because `apply_canonicalization_plan` and postflight are missing.

- [ ] **Step 3: Implement apply execution and postflight**

Add this import to `proposition_reconciliation_apply.py`:

```python
from science_tool.annotation.io import atomic_write_text
```

Then add these functions:

```python
def _changed_and_noop_paths(edits: Sequence[PlannedFileEdit]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    changed = tuple(str(edit.path) for edit in edits if edit.changed)
    noop = tuple(str(edit.path) for edit in edits if not edit.changed)
    return changed, noop


def _postflight(
    project_root: Path,
    actions: Sequence[ReconciliationAction],
    expected_source_refs_by_canonical: Mapping[str, Sequence[str]],
) -> None:
    root = project_root.resolve()
    duplicate_to_canonical = _duplicate_to_canonical(actions)
    for duplicate, canonical in sorted(duplicate_to_canonical.items()):
        location = _entity_location(root, duplicate)
        frontmatter, _body = parse_markdown_entity_file(location.path)
        if frontmatter.get("status") != "superseded":
            raise ReconciliationApplyError(f"postflight: {duplicate} status is not superseded")
        if frontmatter.get("superseded_by") != canonical:
            raise ReconciliationApplyError(
                f"postflight: {duplicate} superseded_by is {frontmatter.get('superseded_by')!r}, not {canonical}"
            )

    remaining = scan_inbound_backlinks(root, duplicate_to_canonical)
    if remaining:
        refs = ", ".join(row.annotation_ref for row in remaining)
        raise ReconciliationApplyError(f"postflight: duplicate promoted_to backlinks remain: {refs}")

    for canonical, expected_refs in sorted(expected_source_refs_by_canonical.items()):
        location = _entity_location(root, canonical)
        frontmatter, _body = parse_markdown_entity_file(location.path)
        refs = set(str(ref) for ref in (frontmatter.get("source_refs") or ()))
        expected = set(str(ref) for ref in expected_refs)
        if not expected <= refs:
            missing = ", ".join(sorted(expected - refs))
            raise ReconciliationApplyError(f"postflight: {canonical} missing source_refs: {missing}")


def _action_result(
    action: ReconciliationAction,
    changed_paths: Sequence[str],
    noop_paths: Sequence[str],
    diagnostics: Sequence[Mapping[str, Any]],
) -> ApplyActionResult:
    canonical = str(action.canonical_proposition)
    duplicates = tuple(ref for ref in action.members if ref != canonical)
    return ApplyActionResult(
        action_id=action.action_id,
        kind=action.kind,
        canonical_proposition=canonical,
        members=tuple(action.members),
        duplicate_propositions=duplicates,
        status="applied" if changed_paths else "noop",
        changed_paths=tuple(changed_paths),
        noop_paths=tuple(noop_paths),
        diagnostics=tuple(diagnostics),
    )


def apply_canonicalization_plan(
    project_root: Path,
    plan: ReconciliationActionPlan,
    *,
    requested_action_ids: Sequence[str] = (),
    as_of: date | None = None,
) -> ReconciliationApplyReport:
    preflight = plan_canonicalization_apply(
        project_root,
        plan,
        requested_action_ids=requested_action_ids,
        as_of=as_of,
    )
    written: list[str] = []
    try:
        for edit in preflight.file_edits:
            if not edit.changed:
                continue
            atomic_write_text(edit.path, edit.final_text)
            written.append(str(edit.path))
    except OSError as exc:
        raise ReconciliationApplyError(
            f"write failed after writing {len(written)} file(s): {exc}; written_paths={written}"
        ) from exc

    try:
        _postflight(
            project_root,
            preflight.actions,
            preflight.expected_source_refs_by_canonical,
        )
    except ReconciliationApplyError as exc:
        # Postflight runs after every write, so a failure here leaves a partially
        # mutated tree. Preserve the honest-atomicity contract: report the stage and
        # the files already written this run. Re-run is safe because writes are idempotent.
        raise ReconciliationApplyError(
            f"{exc} [stage=postflight, written_paths={written}]"
        ) from exc
    changed_paths, noop_paths = _changed_and_noop_paths(preflight.file_edits)
    action_results = tuple(
        _action_result(action, changed_paths, noop_paths, preflight.diagnostics)
        for action in preflight.actions
    )
    return ReconciliationApplyReport(
        status="ok",
        selected_actions=len(preflight.actions),
        changed_paths=changed_paths,
        noop_paths=noop_paths,
        actions=action_results,
        diagnostics=preflight.diagnostics,
        written_paths=tuple(written),
    )
```

- [ ] **Step 4: Run apply tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_apply.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_apply.py science/tests/test_proposition_reconciliation_apply.py
rtk git commit -m "feat(4e): apply canonicalization writes"
```

---

### Task 5: JSON Serialization And CLI Command

**Files:**
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Modify: `science/tests/test_proposition_reconciliation_cli.py`

- [ ] **Step 1: Write failing CLI tests**

First replace the existing `_proposition` helper in `science/tests/test_proposition_reconciliation_cli.py` with this backwards-compatible version:

```python
def _proposition(
    root: Path,
    slug: str,
    title: str,
    *,
    source_refs: tuple[str, ...] = (),
) -> None:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    refs = ""
    if source_refs:
        refs = "source_refs:\n" + "".join(f'  - "{ref}"\n' for ref in source_refs)
    path.write_text(
        f"---\nid: proposition:{slug}\ntype: proposition\ntitle: {title}\n"
        "status: active\nsubject: BRCA1 loss\npredicate: affects\n"
        "object: genomic instability\npolarity: positive\n"
        f"{refs}"
        "---\n\nClaim.\n",
        encoding="utf-8",
    )
```

Then append these tests to `science/tests/test_proposition_reconciliation_cli.py`:

```python
def test_apply_proposition_reconciliation_cli_applies_ready_canonicalization(tmp_path: Path):
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import (
        Annotation,
        Motivation,
        SpecificResource,
        Status,
        TextQuoteSelector,
        TextualBody,
    )
    from datetime import datetime, timezone

    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    created = datetime(2026, 7, 1, tzinfo=timezone.utc)

    def ann(annotation_id: str, promoted_to: str) -> Annotation:
        return Annotation(
            id=annotation_id,
            target=SpecificResource(
                source="x.source.md",
                selector=TextQuoteSelector(exact=annotation_id, prefix="", suffix=""),
            ),
            bodies=(TextualBody(value='{"section":"results","stance":"asserted"}', format="application/json"),),
            motivation=Motivation.CLASSIFYING,
            annotation_type="proposition",
            source="llm-annot:m:paper-annotate-v1",
            status=Status.OPEN,
            creator="paper-annotate",
            created=created,
            content_hash="0" * 64,
            promoted_to=promoted_to,
        )

    for citekey, annotation in [
        ("A2020", ann("a1", "proposition:a")),
        ("B2021", ann("b1", "proposition:b")),
    ]:
        md = tmp_path / "entities" / "papers" / f"{citekey}.source.md"
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text("Paper body.\n", encoding="utf-8")
        anno_io.write_sidecar(anno_io.sidecar_for_markdown(md), anno_io.Sidecar(annotations=(annotation,)))

    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(_review_for_candidate(candidate)), encoding="utf-8")

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["summary"]["selected_actions"] == 1
    assert payload["summary"]["changed_paths"] > 0
    assert "status: superseded" in (tmp_path / "entities" / "propositions" / "b.md").read_text(encoding="utf-8")


def test_apply_proposition_reconciliation_cli_rejects_empty_review(tmp_path: Path):
    _manifest(tmp_path)
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "source": "llm-review:claude:proposition-reconcile-v1",
                "judgments": [],
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
        ],
    )

    assert result.exit_code != 0
    assert "produced no judgments" in result.output


def test_apply_proposition_reconciliation_cli_rejects_non_canonicalization_action(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(tmp_path, "a", "BRCA1 loss increases genomic instability")
    _proposition(tmp_path, "b", "Loss of BRCA1 raises genome instability")

    generated = CliRunner().invoke(
        annotate_group,
        ["reconcile-propositions", "--all", "--root", str(tmp_path), "--format", "json"],
    )
    candidate = json.loads(generated.output)["same_claim_candidates"][0]
    members = candidate["propositions"]
    # A Lane A "related_but_distinct" judgment yields an advisory
    # record_reconciliation_decision action, not a canonicalize_propositions one.
    review = {
        "source": "llm-review:claude:proposition-reconcile-v1",
        "judgments": [
            {
                "candidate_id": candidate["candidate_id"],
                "judgment_id": judgment_id("same_claim", "related_but_distinct", members),
                "lane": "same_claim",
                "decision": "related_but_distinct",
                "members": members,
                "rationale": "Overlapping topic but different endpoints.",
                "confidence": "high",
            }
        ],
    }
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")

    planned = CliRunner().invoke(
        annotate_group,
        [
            "plan-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--format",
            "json",
        ],
    )
    assert planned.exit_code == 0, planned.output
    advisory = next(
        action
        for action in json.loads(planned.output)["actions"]
        if action["kind"] == "record_reconciliation_decision"
    )

    result = CliRunner().invoke(
        annotate_group,
        [
            "apply-proposition-reconciliation",
            "--root",
            str(tmp_path),
            "--input",
            str(review_path),
            "--action",
            advisory["action_id"],
        ],
    )

    assert result.exit_code != 0
    assert "not executable by Half C" in result.output
```

- [ ] **Step 2: Run the failing CLI tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_cli.py::test_apply_proposition_reconciliation_cli_applies_ready_canonicalization science/tests/test_proposition_reconciliation_cli.py::test_apply_proposition_reconciliation_cli_rejects_empty_review science/tests/test_proposition_reconciliation_cli.py::test_apply_proposition_reconciliation_cli_rejects_non_canonicalization_action -q
```

Expected: FAIL because the command is missing.

- [ ] **Step 3: Add JSON serialization to the apply module**

Append this function to `proposition_reconciliation_apply.py`:

```python
def apply_report_to_json(report: ReconciliationApplyReport) -> dict[str, Any]:
    return {
        "status": report.status,
        "summary": {
            "selected_actions": report.selected_actions,
            "changed_paths": len(report.changed_paths),
            "noop_paths": len(report.noop_paths),
            "diagnostics": len(report.diagnostics),
            "written_paths": len(report.written_paths),
        },
        "changed_paths": list(report.changed_paths),
        "noop_paths": list(report.noop_paths),
        "written_paths": list(report.written_paths),
        "diagnostics": [dict(item) for item in report.diagnostics],
        "actions": [
            {
                "action_id": action.action_id,
                "kind": action.kind,
                "canonical_proposition": action.canonical_proposition,
                "members": list(action.members),
                "duplicate_propositions": list(action.duplicate_propositions),
                "status": action.status,
                "changed_paths": list(action.changed_paths),
                "noop_paths": list(action.noop_paths),
                "diagnostics": [dict(item) for item in action.diagnostics],
            }
            for action in report.actions
        ],
    }
```

- [ ] **Step 4: Add the CLI command**

In `science/src/science_tool/annotation/cli.py`, add this command immediately after `plan_proposition_reconciliation_cmd`:

```python
@annotate_group.command("apply-proposition-reconciliation")
@click.option(
    "--input",
    "input_paths",
    required=True,
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--action",
    "action_ids",
    multiple=True,
    help="Specific reconcile-action:<sha256> id to apply; repeat for multiple actions.",
)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def apply_proposition_reconciliation_cmd(
    input_paths: tuple[Path, ...],
    root: Path | None,
    action_ids: tuple[str, ...],
    fmt: str,
) -> None:
    """Apply ready canonical proposition reconciliation actions."""
    from science_tool.annotation.proposition_reconciliation import (
        ReconciliationValidationError,
        build_reconciliation_report,
    )
    from science_tool.annotation.proposition_reconciliation_apply import (
        ReconciliationApplyError,
        apply_canonicalization_plan,
        apply_report_to_json,
    )
    from science_tool.annotation.proposition_reconciliation_plan import (
        ReviewedReconciliationInput,
        build_reconciliation_action_plan,
    )

    project_root = (root or Path.cwd()).resolve()
    reviews: list[ReviewedReconciliationInput] = []
    for input_path in input_paths:
        try:
            doc = json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"{input_path} is not valid JSON: {exc}") from exc
        reviews.append(ReviewedReconciliationInput(path=str(input_path), doc=doc))

    try:
        report = build_reconciliation_report(project_root)
        plan = build_reconciliation_action_plan(report, reviews)
        apply_report = apply_canonicalization_plan(
            project_root,
            plan,
            requested_action_ids=action_ids,
        )
    except (ReconciliationValidationError, ReconciliationApplyError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    payload = apply_report_to_json(apply_report)
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = payload["summary"]
    click.echo(
        "applied proposition reconciliation: "
        f"actions={summary['selected_actions']} "
        f"changed={summary['changed_paths']} "
        f"noop={summary['noop_paths']} "
        f"diagnostics={summary['diagnostics']}"
    )
    for action in payload["actions"]:
        click.echo(
            f"{action['status']:8s} {action['kind']} "
            f"{action['canonical_proposition']} <- {','.join(action['duplicate_propositions'])}"
        )
    for path in payload["changed_paths"]:
        click.echo(f"changed {path}")
    for path in payload["noop_paths"]:
        click.echo(f"noop    {path}")
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/proposition_reconciliation_apply.py science/src/science_tool/annotation/cli.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "feat(4e): add canonicalization apply CLI"
```

---

### Task 6: Conflict Coverage, Formatting, And Smoke Verification

**Files:**
- Modify: `science/tests/test_proposition_reconciliation_apply.py`
- Modify: `science/src/science_tool/annotation/proposition_reconciliation_apply.py`

- [ ] **Step 1: Add conflict/no-op boundary tests**

Append these tests to `science/tests/test_proposition_reconciliation_apply.py`:

```python
def test_plan_canonicalization_apply_errors_when_half_b_ref_points_to_third_proposition(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    _proposition(
        tmp_path,
        "other",
        "Other proposition",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    review_doc = _review_doc_for_current_candidate(tmp_path)
    plan = _ready_plan(tmp_path, review_doc)
    anno_io.write_sidecar(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig",
        anno_io.Sidecar(annotations=(_ann("b1", "proposition:other"),)),
    )

    with pytest.raises(ReconciliationApplyError, match="not proposition:b or proposition:a"):
        plan_canonicalization_apply(tmp_path, plan, requested_action_ids=())


def test_apply_canonicalization_accepts_sidecar_already_canonical_as_noop(tmp_path: Path):
    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
        status="superseded",
        superseded_by="proposition:a",
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    review_doc = _review_doc_for_current_candidate(tmp_path)
    plan = _ready_plan(tmp_path, review_doc)
    anno_io.write_sidecar(
        tmp_path / "entities" / "papers" / "B2021.source.anno.trig",
        anno_io.Sidecar(annotations=(_ann("b1", "proposition:a"),)),
    )

    from science_tool.annotation.proposition_reconciliation_apply import apply_canonicalization_plan

    report = apply_canonicalization_plan(tmp_path, plan, requested_action_ids=())

    assert report.status == "ok"
    assert any(diag["reason"] == "listed_backlink_already_canonical" for diag in report.diagnostics)


def test_apply_canonicalization_reattributes_cross_paper_evidence(tmp_path: Path):
    """End-to-end: belief must move to the canonical proposition after apply.

    This is the design's acceptance criterion — the whole point of Half C is that
    cross-paper literature evidence stops aggregating on the duplicate and starts
    aggregating on the canonical proposition.
    """
    from science_tool.annotation.cross_paper_evidence import build_cross_paper_evidence_report
    from science_tool.annotation.proposition_reconciliation_apply import apply_canonicalization_plan

    _manifest(tmp_path)
    _proposition(
        tmp_path,
        "a",
        "BRCA1 loss increases genomic instability",
        source_refs=("paper:A2020", "annotation:entities/papers/A2020.source#a1"),
    )
    _proposition(
        tmp_path,
        "b",
        "Loss of BRCA1 raises genome instability",
        source_refs=("paper:B2021", "annotation:entities/papers/B2021.source#b1"),
    )
    _paper_sidecar(tmp_path, "A2020", (_ann("a1", "proposition:a"),))
    _paper_sidecar(tmp_path, "B2021", (_ann("b1", "proposition:b"),))
    review_doc = _review_doc_for_current_candidate(tmp_path)

    before_a = build_cross_paper_evidence_report(tmp_path, proposition_ref="proposition:a")
    before_b = build_cross_paper_evidence_report(tmp_path, proposition_ref="proposition:b")
    assert {unit["paper"] for unit in before_a["units"]} == {"paper:A2020"}
    assert {unit["paper"] for unit in before_b["units"]} == {"paper:B2021"}

    plan = _ready_plan(tmp_path, review_doc)
    report = apply_canonicalization_plan(tmp_path, plan, requested_action_ids=())
    assert report.status == "ok"

    after_a = build_cross_paper_evidence_report(tmp_path, proposition_ref="proposition:a")
    after_b = build_cross_paper_evidence_report(tmp_path, proposition_ref="proposition:b")

    # Both papers' assertions now aggregate on the canonical proposition.
    assert {unit["paper"] for unit in after_a["units"]} == {"paper:A2020", "paper:B2021"}
    assert after_a["belief"]["support_units"] >= 2
    # The superseded duplicate no longer carries any literature assertion.
    assert after_b["units"] == []
    assert "status: superseded" in (
        tmp_path / "entities" / "propositions" / "b.md"
    ).read_text(encoding="utf-8")
```

- [ ] **Step 2: Run apply and CLI suites**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_proposition_reconciliation_apply.py science/tests/test_proposition_reconciliation_cli.py -q
```

Expected: PASS, including the hard error for a Half-B-listed annotation that now points at a third proposition.

- [ ] **Step 3: Run formatting and targeted quality checks**

Run:

```bash
rtk uv run --frozen ruff format science/src/science_tool/entities.py science/src/science_tool/annotation/proposition_reconciliation_apply.py science/src/science_tool/annotation/cli.py science/tests/test_entity_writer.py science/tests/test_proposition_reconciliation_apply.py science/tests/test_proposition_reconciliation_cli.py
rtk uv run --frozen ruff check science/src/science_tool/entities.py science/src/science_tool/annotation/proposition_reconciliation_apply.py science/src/science_tool/annotation/cli.py science/tests/test_entity_writer.py science/tests/test_proposition_reconciliation_apply.py science/tests/test_proposition_reconciliation_cli.py
```

Expected: both commands exit 0.

- [ ] **Step 4: Run the complete relevant regression set**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_entity_writer.py science/tests/test_proposition_reconciliation.py science/tests/test_proposition_reconciliation_plan.py science/tests/test_proposition_reconciliation_apply.py science/tests/test_proposition_reconciliation_cli.py science/tests/test_cross_paper_evidence.py -q
```

Expected: PASS.

- [ ] **Step 5: Optional live-corpus smoke**

Only run this after the synthetic tests are green and the worktree has the expected review artifact available. Treat the exact counts as inspection data, not a hard invariant of Half C:

```bash
rtk uv run --frozen science annotate plan-proposition-reconciliation --root . --input results/proposition-reconciliation/review.json --format json
```

Expected: command exits 0 if the reviewed artifact still matches the live corpus. Inspect that any intended `canonicalize_propositions` action is `ready` before running the apply command on the real corpus.

Do not run the mutating real-corpus apply command unless the user explicitly asks for it.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/entities.py science/src/science_tool/annotation/proposition_reconciliation_apply.py science/src/science_tool/annotation/cli.py science/tests/test_entity_writer.py science/tests/test_proposition_reconciliation_apply.py science/tests/test_proposition_reconciliation_cli.py
rtk git commit -m "test(4e): cover canonicalization apply boundaries"
```

---

## Acceptance Checklist

- [ ] `science annotate apply-proposition-reconciliation --input review.json` applies only ready `canonicalize_propositions` actions.
- [ ] The command refuses top-level plan errors, advisory actions, blocked actions, unknown action ids, and `resynthesize_proposition`.
- [ ] Preflight computes every final file text before writing anything.
- [ ] Canonical propositions receive duplicate `source_refs` plus live inbound paper/annotation refs discovered from sidecars.
- [ ] Duplicate proposition files remain on disk and become `status: superseded` with `superseded_by: <canonical>`.
- [ ] All live sidecar `promoted_to` backlinks to duplicate propositions are rewritten to canonical propositions.
- [ ] Two selected actions touching different annotations in one sidecar produce one merged sidecar edit.
- [ ] A stale Half-B-listed annotation ref that points to a third proposition or no live annotation hard-errors.
- [ ] Re-running the same command after success is a no-op with `status: ok`.
- [ ] Postflight fails if any inbound `promoted_to` backlink to a selected duplicate remains.
- [ ] A postflight failure surfaces the stage and the files already written this run.
- [ ] After apply, cross-paper evidence aggregates both papers' assertions on the canonical proposition and none on the superseded duplicate.
- [ ] The implementation does not delete or move duplicate proposition files.
- [ ] The implementation does not apply factorization resynthesis.

---

## Self-Review Notes

- Spec coverage: tasks cover CLI surface, action selection, canonical source-ref provenance, duplicate supersession, authoritative live sidecar scan, shared-sidecar merge, preflight/write/postflight, idempotency, JSON/table reporting, and the end-to-end cross-paper belief re-attribution that is the design's headline acceptance criterion.
- Placeholder scan: no forbidden marker text or unspecified "add tests" steps remain. The optional smoke explicitly avoids mutating the real corpus without user approval.
- Type consistency: `ReconciliationApplyError`, `PlannedFileEdit`, `CanonicalizationPreflight`, `ReconciliationApplyReport`, `select_canonicalization_actions`, `plan_canonicalization_apply`, `apply_canonicalization_plan`, and `apply_report_to_json` are introduced before later tasks use them.
- Repo conventions: plan is under `docs/plans/`, command names are flat `annotate` commands, shell snippets use `rtk`, and path examples avoid machine-local absolute prefixes.
- Honest atomicity: a postflight failure now re-raises with `stage=postflight` and `written_paths=...` so a partially mutated tree is recoverable; re-run is safe because every write is idempotent.
- Accepted minor deferrals: (1) the apply module reuses `_iter_project_annotation_sidecar_paths` / `_resolve_paper_ref` from `cross_paper_evidence` and mirrors `promote._annotation_ref` rather than promoting those to shared public helpers — deliberate reuse to avoid a wider refactor; revisit if a third caller appears. (2) Member-snapshot existence (design §4) is enforced indirectly by `find_entity` raising in preflight rather than by an explicit snapshot check; the error is fail-loud but generic. Both are conscious choices, not oversights.
