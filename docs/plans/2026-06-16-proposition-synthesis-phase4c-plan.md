# Phase 4c — Proposition reasoning synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science annotate synthesize <source.md>` — a deterministic, curator-reviewed step that fills the `predicate`/`polarity`/`claim_layer` (and refines `subject`/`object`) reasoning fields on the propositions Phase 4a promoted, from an agent-proposed candidates file.

**Architecture:** Brain/hands split mirroring `promote` (Phase 4a/4b). A new `proposition-synthesize` agent emits a candidates file; a new deterministic module `annotation/synthesize.py` builds the read-only scaffold and runs a two-pass (validate-before-write) apply that enforces the proposition interlocks, fills only unset fields, preserves curated bodies, and stamps a versioned `reasoning_source`. One new optional `PropositionEntity.reasoning_source` field.

**Tech Stack:** Python 3.13, Pydantic v2 (`science_model`), Click CLI, the existing W3C annotation sidecar machinery (`science_tool.annotation.*`), `uv` workspace. Tests: pytest.

**Design:** `docs/plans/2026-06-16-proposition-synthesis-phase4c-design.md` (read it; this plan implements it section-by-section).

---

## Environment & conventions (read once)

- **Worktree:** all work happens in `~/d/science/.worktrees/sub-article-annotation-phase4c` on branch `feat/sub-article-annotation-phase4c`. Subagents MUST `cd` there and confirm `rtk git branch --show-current` prints `feat/sub-article-annotation-phase4c` before any edit/commit (the main checkout is Dropbox-synced; commits leak to `main` otherwise).
- **Commands run from `science/`:** `cd ~/d/science/.worktrees/sub-article-annotation-phase4c/science`. Use `rtk uv run --frozen` for everything:
  - test one: `rtk uv run --frozen pytest tests/<file>::<test> -q -p no:warnings`
  - test file: `rtk uv run --frozen pytest tests/<file> -q -p no:warnings`
  - types: `rtk uv run --frozen pyright src/science_tool/annotation/synthesize.py`
  - lint: `rtk uv run --frozen ruff check src/science_tool/annotation/synthesize.py`
  - **Rely on the exit code (0 = pass).** The printed pytest summary may be swallowed when piped; `rtk echo "rc=$?"` if unsure.
- **No `Co-Authored-By` trailers** in commits. Keep science local — **do not push**.
- Shell aliases map `grep`→`rg` and `find`→`rtk`; prefer `rg`.

## File structure (what each unit owns)

| File | Responsibility | Change |
| --- | --- | --- |
| `science/model/src/science_model/propositions.py` | `PropositionEntity` typed model | **Modify** — add `reasoning_source` field (Task 1) |
| `science/src/science_tool/annotation/synthesize.py` | scaffold build + candidate parse + two-pass validate/apply + error classes | **Create** (Tasks 2–6) |
| `science/src/science_tool/annotation/cli.py` | `annotate` Click group | **Modify** — add `synthesize_cmd` (Task 7) |
| `agents/proposition-synthesize.md` | the synthesis agent prompt | **Create** (Task 8) |
| `commands/synthesize-propositions.md` | orchestrator command | **Create** (Task 8) |
| `docs/conventions/annotation-tokens.md` | vocab/source-string registry | **Modify** — add the 4c section (Task 8) |
| `science/tests/test_proposition_reasoning_source.py` | model-field unit test | **Create** (Task 1) |
| `science/tests/test_proposition_synthesize.py` | synthesize.py unit tests | **Create** (Tasks 2–6) |
| `science/tests/test_synthesize_integration.py` | end-to-end CLI test | **Create** (Task 9) |

**Reused unchanged** (import, do not modify): `science_tool.annotation.promote.entity_dest`; `science_tool.entities._parse_markdown_file` / `write_entity_file`; `science_tool.annotation.statement_extract.find_qualified_spans`; `science_tool.annotation.io.sidecar_for_markdown`; `science_tool.annotation.query.read_sidecar_strict` / `entity_relpath_for_sidecar`; `science_model.reasoning` enums + `SIGN_MEANINGFUL_PREDICATES`.

## Shared vocabulary (used across tasks — keep names identical)

```python
# annotation/synthesize.py module constants
import re
from science_model.reasoning import (
    ClaimLayer, Polarity, Predicate, SIGN_MEANINGFUL_PREDICATES,
)

SYNTH_SOURCE_RE = re.compile(r"^llm-synth:[A-Za-z0-9._-]+:proposition-synthesize-v1$")
SYNTH_FIELDS: tuple[str, ...] = ("subject", "object", "predicate", "polarity", "claim_layer")
_ENUM_FIELDS: tuple[str, ...] = ("predicate", "polarity", "claim_layer")
_CANDIDATE_KEYS = frozenset({"proposition", "annotation", "override", *SYNTH_FIELDS})
_PREDICATE_VALUES = frozenset(p.value for p in Predicate)
_POLARITY_VALUES = frozenset(p.value for p in Polarity)
_CLAIM_LAYER_VALUES = frozenset(v.value for v in ClaimLayer)
_SIGN_MEANINGFUL_VALUES = frozenset(p.value for p in SIGN_MEANINGFUL_PREDICATES)
_ENUM_VALUES: dict[str, frozenset[str]] = {
    "predicate": _PREDICATE_VALUES,
    "polarity": _POLARITY_VALUES,
    "claim_layer": _CLAIM_LAYER_VALUES,
}
```

---

## Task 1: `reasoning_source` model field

**Files:**
- Modify: `science/model/src/science_model/propositions.py:55-57`
- Test: `science/tests/test_proposition_reasoning_source.py`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_proposition_reasoning_source.py`:

```python
from science_model.propositions import PropositionEntity

STAMP = "llm-synth:claude-opus-4-8:proposition-synthesize-v1"


def test_reasoning_source_defaults_none_and_omitted():
    p = PropositionEntity(id="proposition:x", title="t")
    assert p.reasoning_source is None
    # exclude_none (how write_entity_file serializes) ⇒ absent when unset
    assert "reasoning_source" not in p.model_dump(mode="json", exclude_none=True)


def test_reasoning_source_serializes_when_set():
    p = PropositionEntity(id="proposition:x", title="t", reasoning_source=STAMP)
    dumped = p.model_dump(mode="json", exclude_none=True)
    assert dumped["reasoning_source"] == STAMP
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --frozen pytest tests/test_proposition_reasoning_source.py -q -p no:warnings`
Expected: FAIL — `TypeError`/`ValidationError` (unexpected keyword `reasoning_source`) on the second test.

- [ ] **Step 3: Add the field**

In `science/model/src/science_model/propositions.py`, in the `# Reasoning metadata` block (after `identification_strength`, currently line 57), add the field as the last reasoning field:

```python
    # Reasoning metadata
    claim_layer: ClaimLayer | None = None
    identification_strength: IdentificationStrength | None = None
    # Versioned identity of the synthesizer that authored the reasoning fields above
    # (Phase 4c: "llm-synth:<model>:proposition-synthesize-v1"). Answers "is this
    # reasoning stale under the current synthesizer?"; a free string the validators ignore.
    reasoning_source: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_proposition_reasoning_source.py -q -p no:warnings`
Expected: PASS (2 passed).

- [ ] **Step 5: Guard — proposition QA checks still pass**

Run: `rtk uv run --frozen pytest tests/validate/test_check_propositions.py tests/test_proposition_relational_fields.py -q -p no:warnings`
Expected: PASS (the new field is a free string the checks ignore).

- [ ] **Step 6: Commit**

```bash
rtk git add science/model/src/science_model/propositions.py science/tests/test_proposition_reasoning_source.py
rtk git commit -m "feat(model): add PropositionEntity.reasoning_source (Phase 4c)"
```

---

## Task 2: scaffold — in-scope discovery + supporting-statement context

**Files:**
- Create: `science/src/science_tool/annotation/synthesize.py`
- Test: `science/tests/test_proposition_synthesize.py`

This task builds the read side **without** relation hints (added in Task 3): discover in-scope propositions from a sidecar's `promoted_to` backlinks and assemble each proposition's current fields + supporting-statement context.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_proposition_synthesize.py`:

```python
from datetime import datetime, timezone

from science_tool.annotation.model import (
    Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
)
from science_tool.annotation.model import Sidecar
from science_tool.annotation.synthesize import in_scope_propositions, statement_context


def _ann(frag, atype, exact, *, body, promoted_to=None, status=Status.OPEN):
    return Annotation(
        id=frag,
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1", status=status,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64, promoted_to=promoted_to,
    )


def test_in_scope_groups_by_promoted_proposition():
    a = _ann("s1", "proposition", "X drives Y",
             body='{"section":"results","stance":"asserted","subject":"X","object":"Y"}',
             promoted_to="proposition:x-drives-y")
    b = _ann("s2", "proposition", "X drives Y too",
             body='{"section":"results","stance":"asserted"}',
             promoted_to="proposition:x-drives-y")
    q = _ann("q1", "question", "What about Z", body='{"section":"results","stance":"open"}',
             promoted_to="question:0001-z")          # not a proposition → excluded
    u = _ann("s3", "proposition", "Unpromoted",
             body='{"section":"results","stance":"asserted"}')   # promoted_to=None → excluded
    sc = Sidecar(annotations=(a, b, q, u))
    scope = in_scope_propositions(sc)
    assert set(scope) == {"proposition:x-drives-y"}
    assert [x.id for x in scope["proposition:x-drives-y"]] == ["s1", "s2"]


def test_statement_context_extracts_body_fields():
    a = _ann("s1", "proposition", "X drives Y",
             body='{"section":"results","stance":"asserted","subject":"X","object":"Y"}')
    ctx = statement_context(a, "annotation:papers/p.source#s1")
    assert ctx == {
        "annotation": "annotation:papers/p.source#s1",
        "exact": "X drives Y", "section": "results", "stance": "asserted",
        "subject": "X", "object": "Y",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: FAIL — `ModuleNotFoundError: science_tool.annotation.synthesize`.

- [ ] **Step 3: Create the module with the read-side core**

Create `science/src/science_tool/annotation/synthesize.py`:

```python
"""Phase 4c — proposition reasoning synthesis (scaffold + two-pass apply).

Fills predicate/polarity/claim_layer (and refines subject/object) on the propositions
Phase 4a promoted, from an agent-proposed candidates file. Brain/hands split: the agent
proposes (untrusted), this module validates the proposition interlocks and persists.

See docs/plans/2026-06-16-proposition-synthesis-phase4c-design.md.
"""

from __future__ import annotations

import json
import re
from typing import Any

from science_model.reasoning import (
    ClaimLayer, Polarity, Predicate, SIGN_MEANINGFUL_PREDICATES,
)

from science_tool.annotation.model import Annotation, Sidecar, TextualBody
```

> Later tasks add their own imports to **this same top-of-file block** (never append an `import` lower in the file — Ruff E402). The full final import set is: `json`, `re`, `from collections import Counter`, `from dataclasses import dataclass, field`, `from datetime import date`, `from pathlib import Path`, `from typing import Any`; `from pydantic import ValidationError`; `from science_model.reasoning import (...)`, `from science_model.propositions import PropositionEntity`; `from science_tool.annotation.model import Annotation, Sidecar, TextualBody`, `from science_tool.annotation.promote import entity_dest`, `from science_tool.annotation.statement_extract import find_qualified_spans`, `from science_tool.entities import _parse_markdown_file, write_entity_file`.

Continue the same `synthesize.py` file with the module constants and read-side functions:

```python

SYNTH_SOURCE_RE = re.compile(r"^llm-synth:[A-Za-z0-9._-]+:proposition-synthesize-v1$")
SYNTH_FIELDS: tuple[str, ...] = ("subject", "object", "predicate", "polarity", "claim_layer")
_ENUM_FIELDS: tuple[str, ...] = ("predicate", "polarity", "claim_layer")
_CANDIDATE_KEYS = frozenset({"proposition", "annotation", "override", *SYNTH_FIELDS})
_PREDICATE_VALUES = frozenset(p.value for p in Predicate)
_POLARITY_VALUES = frozenset(p.value for p in Polarity)
_CLAIM_LAYER_VALUES = frozenset(v.value for v in ClaimLayer)
_SIGN_MEANINGFUL_VALUES = frozenset(p.value for p in SIGN_MEANINGFUL_PREDICATES)
_ENUM_VALUES: dict[str, frozenset[str]] = {
    "predicate": _PREDICATE_VALUES,
    "polarity": _POLARITY_VALUES,
    "claim_layer": _CLAIM_LAYER_VALUES,
}

_PROP_PREFIX = "proposition:"


def in_scope_propositions(sidecar: Sidecar) -> dict[str, list[Annotation]]:
    """Map each promoted `proposition:<slug>` to its supporting statement annotations.

    In scope = the propositions reachable from THIS sidecar via the `sci:promotedTo`
    backlink (Phase 4a sets `promoted_to`). Questions/hypotheses are excluded — only the
    proposition kind carries reasoning fields. Insertion order preserved (stable scaffold).
    """
    scope: dict[str, list[Annotation]] = {}
    for ann in sidecar.annotations:
        pt = ann.promoted_to
        if pt is not None and pt.startswith(_PROP_PREFIX):
            scope.setdefault(pt, []).append(ann)
    return scope


def _statement_body(ann: Annotation) -> dict[str, Any]:
    for body in ann.bodies:
        if isinstance(body, TextualBody) and body.format == "application/json":
            data = json.loads(body.value)
            if isinstance(data, dict):
                return data
    return {}


def statement_context(ann: Annotation, ref: str) -> dict[str, Any]:
    """One supporting-statement context object for the scaffold (exact + body fields)."""
    data = _statement_body(ann)
    ctx: dict[str, Any] = {
        "annotation": ref,
        "exact": ann.target.selector.exact,
        "section": data.get("section", ""),
        "stance": data.get("stance", ""),
    }
    for key in ("subject", "object", "subject_concept", "object_concept"):
        if key in data:
            ctx[key] = data[key]
    return ctx
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: PASS (2 passed).

- [ ] **Step 5: Lint + types**

Run: `rtk uv run --frozen ruff check src/science_tool/annotation/synthesize.py && rtk uv run --frozen pyright src/science_tool/annotation/synthesize.py`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/synthesize.py science/tests/test_proposition_synthesize.py
rtk git commit -m "feat(synthesize): in-scope proposition discovery + statement context (Phase 4c)"
```

---

## Task 3: scaffold — relation hints + `build_scaffold`

**Files:**
- Modify: `science/src/science_tool/annotation/synthesize.py`
- Test: `science/tests/test_proposition_synthesize.py`

Resolve Phase-2b `relation` annotations against the current `.source.md`, attach the ones overlapping a proposition's supporting statements as **non-authoritative** predicate hints, and assemble the full scaffold object. Per design §5: if a selector fails to resolve uniquely, omit and count `synthesize-relation-hint-unresolved` (never fail the scaffold).

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_proposition_synthesize.py`:

```python
from science_tool.annotation.synthesize import build_scaffold, relation_hints


def _rel(frag, exact, *, predicate, subj, obj):
    body = (
        '{"object":"%s","predicate":"%s","predicate_source":"biored",'
        '"subject":"%s"}' % (obj, predicate, subj)
    )
    return _ann(frag, "relation", exact, body=body)


def test_relation_hints_overlap_and_unresolved_count():
    file_text = "alpha BRCA1 affects genomic instability omega"
    stmt = _ann("s1", "proposition", "BRCA1 affects genomic instability",
                body='{"section":"results","stance":"asserted"}',
                promoted_to="proposition:p")
    # overlapping relation (its exact lies inside the statement span)
    hit = _rel("r1", "BRCA1 affects", predicate="biolink:affects",
               subj="ncbigene:672", obj="GO:0006281")
    # relation whose exact is not in file_text → unresolved, counted, omitted
    miss = _rel("r2", "NOT PRESENT", predicate="biolink:regulates",
                subj="a", obj="b")
    hints, unresolved = relation_hints(file_text, [stmt], [hit, miss])
    assert unresolved == 1
    assert hints == [{
        "annotation_frag": "r1", "predicate": "biolink:affects",
        "subject": "ncbigene:672", "object": "GO:0006281",
    }]


def test_build_scaffold_shape():
    file_text = "BRCA1 affects genomic instability"
    stmt = _ann("s1", "proposition", "BRCA1 affects genomic instability",
                body='{"section":"results","stance":"asserted","subject":"BRCA1"}',
                promoted_to="proposition:brca1")
    sc = Sidecar(annotations=(stmt,))
    current = {"proposition:brca1": {"title": "BRCA1 claim", "subject": "BRCA1"}}
    scaffold, unresolved = build_scaffold(
        sc, file_text, current,
        ref_for=lambda frag: f"annotation:papers/p.source#{frag}",
    )
    assert scaffold["source"] == "llm-synth:<MODEL>:proposition-synthesize-v1"
    assert unresolved == 0
    [entry] = scaffold["propositions"]
    assert entry["proposition"] == "proposition:brca1"
    assert entry["title"] == "BRCA1 claim"
    assert entry["current"] == {"subject": "BRCA1", "object": None, "predicate": None,
                                "polarity": None, "claim_layer": None}
    assert entry["statements"][0]["annotation"] == "annotation:papers/p.source#s1"
    assert entry["relation_hints"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'build_scaffold'`.

- [ ] **Step 3: Implement resolution, hints, and `build_scaffold`**

First add this import to the **import block at the top** of `synthesize.py` (keep all imports at the top — never append an `import` mid-file; Ruff E402 rejects it), in the `science_tool.annotation` import group:

```python
from science_tool.annotation.statement_extract import find_qualified_spans
```

Then append the following to the **end** of `science/src/science_tool/annotation/synthesize.py`:

```python
SCAFFOLD_SOURCE_PLACEHOLDER = "llm-synth:<MODEL>:proposition-synthesize-v1"
RELATION_TYPE = "relation"


def _resolve_range(file_text: str, ann: Annotation) -> tuple[int, int] | None:
    """Unique [start, end) of an annotation's quote selector in `file_text`, else None."""
    sel = ann.target.selector
    spans = find_qualified_spans(file_text, sel.exact, sel.prefix, sel.suffix)
    if len(spans) != 1:
        return None
    return spans[0], spans[0] + len(sel.exact)


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _relation_predicate(ann: Annotation) -> dict[str, Any] | None:
    data = _statement_body(ann)
    pred = data.get("predicate")
    if not isinstance(pred, str):
        return None
    return {
        "annotation_frag": ann.id,
        "predicate": pred,
        "subject": data.get("subject"),
        "object": data.get("object"),
    }


def relation_hints(
    file_text: str, statements: list[Annotation], relations: list[Annotation]
) -> tuple[list[dict[str, Any]], int]:
    """Predicate hints from relation annotations co-located with any supporting statement.

    Co-located = overlapping resolved [start,end) ranges. A statement or relation whose
    selector does not resolve uniquely is counted once as unresolved and skipped (never
    fatal). Each qualifying relation appears at most once (first overlap wins).
    """
    unresolved = 0
    stmt_ranges: list[tuple[int, int]] = []
    for s in statements:
        r = _resolve_range(file_text, s)
        if r is None:
            unresolved += 1
        else:
            stmt_ranges.append(r)
    hints: list[dict[str, Any]] = []
    for rel in relations:
        rr = _resolve_range(file_text, rel)
        if rr is None:
            unresolved += 1
            continue
        if any(_overlaps(rr, sr) for sr in stmt_ranges):
            hint = _relation_predicate(rel)
            if hint is not None:
                hints.append(hint)
    return hints, unresolved


def build_scaffold(
    sidecar: Sidecar,
    file_text: str,
    current: dict[str, dict[str, Any]],
    *,
    ref_for,
) -> tuple[dict[str, Any], int]:
    """Assemble the read-only scaffold object + total unresolved-hint count.

    `current[prop_ref]` is that proposition's current frontmatter (subject/object/predicate/
    polarity/claim_layer/title); missing keys are simply absent. `ref_for(frag)` builds the
    `annotation:<relpath>#<frag>` ref for a sidecar annotation. Per design §5 the scaffold
    shows EVERY synthesis field in `current` (unset → `null`) so the agent sees explicitly
    which fields are already set vs available.
    """
    scope = in_scope_propositions(sidecar)
    relations = [a for a in sidecar.annotations if a.annotation_type == RELATION_TYPE]
    entries: list[dict[str, Any]] = []
    total_unresolved = 0
    for prop_ref, statements in scope.items():
        fm = current.get(prop_ref, {})
        cur = {f: fm.get(f) for f in SYNTH_FIELDS}   # all 5 fields; unset → None (design §5)
        hints, unresolved = relation_hints(file_text, statements, relations)
        total_unresolved += unresolved
        entries.append({
            "proposition": prop_ref,
            "title": fm.get("title", ""),
            "current": cur,
            "statements": [statement_context(a, ref_for(a.id)) for a in statements],
            "relation_hints": hints,
        })
    return {"source": SCAFFOLD_SOURCE_PLACEHOLDER, "propositions": entries}, total_unresolved
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: PASS (4 passed).

- [ ] **Step 5: Lint + types**

Run: `rtk uv run --frozen ruff check src/science_tool/annotation/synthesize.py && rtk uv run --frozen pyright src/science_tool/annotation/synthesize.py`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/synthesize.py science/tests/test_proposition_synthesize.py
rtk git commit -m "feat(synthesize): relation-hint co-location + build_scaffold (Phase 4c)"
```

---

## Task 4: candidate parsing + structural validation (Pass 1 part A)

**Files:**
- Modify: `science/src/science_tool/annotation/synthesize.py`
- Test: `science/tests/test_proposition_synthesize.py`

Parse the candidates file into validated `SynthesisCandidate` rows. Enforce design §6/§7 Pass-1 steps 1–3: top-level `source` regex, coverage (duplicate `proposition` → hard error), per-candidate keys, explicit-`null`/empty rejection, enum membership, `proposition` in-scope, `annotation` membership, and `override` legality. Contracts + interlocks come in Task 5.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_proposition_synthesize.py`:

```python
import pytest
from science_tool.annotation.synthesize import (
    SynthesisCandidate, SynthesisReadError, parse_candidates_doc,
)

# in-scope set + per-proposition supporting-statement refs the parser validates against
SCOPE = {"proposition:p": {"annotation:papers/p.source#s1"}}
SRC = "llm-synth:claude-opus-4-8:proposition-synthesize-v1"


def _doc(candidates, source=SRC):
    return {"source": source, "candidates": candidates}


def test_parse_minimal_candidate():
    doc = _doc([{
        "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
        "predicate": "affects", "subject": "X", "object": "Y", "polarity": "positive",
        "claim_layer": "causal_effect",
    }])
    source, cands = parse_candidates_doc(doc, SCOPE)
    assert source == SRC
    assert cands == [SynthesisCandidate(
        proposition="proposition:p", annotation="annotation:papers/p.source#s1",
        fields={"predicate": "affects", "subject": "X", "object": "Y",
                "polarity": "positive", "claim_layer": "causal_effect"},
        override=frozenset(),
    )]


def test_bad_source_rejected():
    with pytest.raises(SynthesisReadError, match="source"):
        parse_candidates_doc(_doc([], source="llm-synth:<MODEL>:proposition-synthesize-v1"), SCOPE)


def test_duplicate_proposition_rejected():
    row = {"proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
           "claim_layer": "causal_effect"}
    with pytest.raises(SynthesisReadError, match="duplicate"):
        parse_candidates_doc(_doc([row, dict(row)]), SCOPE)


def test_explicit_null_field_rejected():
    with pytest.raises(SynthesisReadError, match="null|omit"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": None,
        }]), SCOPE)


def test_unknown_enum_value_rejected():
    with pytest.raises(SynthesisReadError, match="claim_layer"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "made_up",
        }]), SCOPE)


def test_out_of_scope_proposition_rejected():
    with pytest.raises(SynthesisReadError, match="in scope|scope"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:other", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect",
        }]), SCOPE)


def test_annotation_not_supporting_rejected():
    with pytest.raises(SynthesisReadError, match="annotation"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#sX",
            "claim_layer": "causal_effect",
        }]), SCOPE)


def test_override_must_name_a_present_field():
    with pytest.raises(SynthesisReadError, match="override"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect", "override": ["predicate"],
        }]), SCOPE)


def test_override_rejects_reasoning_source():
    with pytest.raises(SynthesisReadError, match="override"):
        parse_candidates_doc(_doc([{
            "proposition": "proposition:p", "annotation": "annotation:papers/p.source#s1",
            "claim_layer": "causal_effect", "override": ["reasoning_source"],
        }]), SCOPE)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'parse_candidates_doc'`.

- [ ] **Step 3: Implement the candidate dataclass, error classes, and parser**

First add this import to the **import block at the top** of `synthesize.py` (stdlib group):

```python
from dataclasses import dataclass, field
```

Then append the following to the **end** of `science/src/science_tool/annotation/synthesize.py`:

```python
class SynthesisReadError(Exception):
    """Malformed candidates file / bad source / scope / annotation (fail loud)."""


class SynthesisApplyError(Exception):
    """Interlock / operand / polarity-without-predicate / write-boundary failure (fail loud)."""


class SynthesisOverrideError(SynthesisReadError):
    """Illegal override: unknown field, field not in patch, currently-unset, or reasoning_source.

    Subclasses SynthesisReadError so the CLI catch and `pytest.raises(SynthesisReadError)`
    cover it; the dedicated type matches design §10's three-class taxonomy.
    """


@dataclass(frozen=True)
class SynthesisCandidate:
    proposition: str
    annotation: str
    fields: dict[str, str] = field(default_factory=dict)   # proposed SYNTH_FIELDS (non-null)
    override: frozenset[str] = frozenset()


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SynthesisReadError(msg)


def _require_override(cond: bool, msg: str) -> None:
    if not cond:
        raise SynthesisOverrideError(msg)


def parse_candidates_doc(
    doc: Any, scope: dict[str, set[str]]
) -> tuple[str, list[SynthesisCandidate]]:
    """Parse + structurally validate a candidates document against the in-scope set.

    `scope[prop_ref]` is the set of that proposition's supporting-statement refs. Returns
    `(validated_source, candidates)`. Raises SynthesisReadError on any structural defect.
    """
    _require(isinstance(doc, dict), "candidates input must be a JSON object")
    extra = set(doc) - {"source", "candidates"}
    _require(not extra, f"unknown top-level keys: {sorted(extra)}")
    source = doc.get("source")
    _require(isinstance(source, str) and bool(SYNTH_SOURCE_RE.match(source)),
             f"top-level 'source' must match {SYNTH_SOURCE_RE.pattern!r} (got {source!r})")
    items = doc.get("candidates")
    _require(isinstance(items, list), "'candidates' must be a JSON array")

    seen: set[str] = set()
    out: list[SynthesisCandidate] = []
    for i, item in enumerate(items):
        out.append(_parse_candidate(item, i, scope, seen))
    return source, out


def _parse_candidate(
    item: Any, idx: int, scope: dict[str, set[str]], seen: set[str]
) -> SynthesisCandidate:
    _require(isinstance(item, dict), f"candidate[{idx}] must be a JSON object")
    extra = set(item) - _CANDIDATE_KEYS
    _require(not extra, f"candidate[{idx}] unknown fields: {sorted(extra)}")

    prop = item.get("proposition")
    _require(isinstance(prop, str) and prop in scope,
             f"candidate[{idx}].proposition {prop!r} is not an in-scope proposition")
    _require(prop not in seen, f"duplicate candidate for proposition {prop!r}")
    seen.add(prop)

    ann = item.get("annotation")
    _require(isinstance(ann, str) and ann in scope[prop],
             f"candidate[{idx}].annotation {ann!r} is not a supporting statement of {prop!r}")

    fields: dict[str, str] = {}
    for f in SYNTH_FIELDS:
        if f not in item:
            continue
        val = item[f]
        _require(isinstance(val, str) and val != "",
                 f"candidate[{idx}].{f} must be a non-empty string (omit it to leave unset; "
                 f"null is not allowed)")
        if f in _ENUM_VALUES:
            _require(val in _ENUM_VALUES[f],
                     f"candidate[{idx}].{f} {val!r} not in {sorted(_ENUM_VALUES[f])}")
        fields[f] = val

    override = item.get("override", [])
    _require_override(isinstance(override, list) and all(isinstance(x, str) for x in override),
                      f"candidate[{idx}].override must be a list of field names")
    for name in override:
        _require_override(name in SYNTH_FIELDS,
                          f"candidate[{idx}].override {name!r} not in {sorted(SYNTH_FIELDS)} "
                          f"(reasoning_source is never overrideable)")
        _require_override(name in fields,
                          f"candidate[{idx}].override names {name!r} which is not present in the patch")
    return SynthesisCandidate(
        proposition=prop, annotation=ann, fields=fields, override=frozenset(override),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: PASS (13 passed).

- [ ] **Step 5: Lint + types**

Run: `rtk uv run --frozen ruff check src/science_tool/annotation/synthesize.py && rtk uv run --frozen pyright src/science_tool/annotation/synthesize.py`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/synthesize.py science/tests/test_proposition_synthesize.py
rtk git commit -m "feat(synthesize): candidate parse + structural validation (Phase 4c)"
```

---

## Task 5: write-plan + contracts + interlocks (Pass 1 part B)

**Files:**
- Modify: `science/src/science_tool/annotation/synthesize.py`
- Test: `science/tests/test_proposition_synthesize.py`

Compute the **effective writes** for a candidate against current frontmatter (fill-only-unset + override + sign-less polarity canonicalization) and validate the contracts + interlocks against the effective state. This single pure function is shared by Pass 1 (validate) and Pass 2 (apply), so Pass 1 validates exactly what Pass 2 writes (design §7).

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_proposition_synthesize.py`:

```python
from science_tool.annotation.synthesize import (
    SynthesisApplyError, SynthesisOverrideError, WritePlan, plan_writes, validate_candidate,
)


def _cand(fields, override=frozenset(), prop="proposition:p",
          ann="annotation:papers/p.source#s1"):
    return SynthesisCandidate(proposition=prop, annotation=ann, fields=fields, override=override)


def test_plan_writes_fill_only_unset():
    current = {"subject": "X"}                      # object/predicate/... unset
    cand = _cand({"subject": "X2", "object": "Y", "claim_layer": "causal_effect"})
    plan = plan_writes(current, cand)
    # subject already set & different & no override → blocked; object/claim_layer fill
    assert plan.writes == {"object": "Y", "claim_layer": "causal_effect"}
    assert plan.blocked == ("subject",)


def test_plan_writes_override_replaces():
    current = {"claim_layer": "empirical_regularity"}
    cand = _cand({"claim_layer": "causal_effect"}, override=frozenset({"claim_layer"}))
    plan = plan_writes(current, cand)
    assert plan.writes == {"claim_layer": "causal_effect"} and plan.blocked == ()


def test_plan_writes_signless_canonicalizes_polarity():
    current: dict = {}
    cand = _cand({"subject": "X", "object": "Y", "predicate": "binds"})   # sign-less
    plan = plan_writes(current, cand)
    assert plan.writes["polarity"] == "not_applicable"


def test_validate_predicate_requires_operands():
    current: dict = {}
    cand = _cand({"predicate": "affects", "subject": "X", "polarity": "positive"})  # no object
    with pytest.raises(SynthesisApplyError, match="subject and object|object"):
        validate_candidate(current, cand)


def test_validate_polarity_requires_predicate():
    current: dict = {}
    cand = _cand({"polarity": "positive"})         # bare polarity, no predicate
    with pytest.raises(SynthesisApplyError, match="predicate"):
        validate_candidate(current, cand)


def test_validate_sign_meaningful_missing_polarity_fails():
    current: dict = {}
    cand = _cand({"subject": "X", "object": "Y", "predicate": "affects"})  # needs signed polarity
    with pytest.raises(SynthesisApplyError):
        validate_candidate(current, cand)


def test_validate_override_of_unset_field_rejected():
    # override may only name a CURRENTLY-SET field; current={} ⇒ hard error (design §6/§7).
    cand = _cand({"claim_layer": "causal_effect"}, override=frozenset({"claim_layer"}))
    with pytest.raises(SynthesisOverrideError, match="override|unset"):
        validate_candidate({}, cand)


def test_validate_ok_returns_plan():
    current = {"subject": "X", "object": "Y"}
    cand = _cand({"predicate": "regulates", "polarity": "negative", "claim_layer": "causal_effect"})
    plan = validate_candidate(current, cand)
    assert plan.writes == {"predicate": "regulates", "polarity": "negative",
                           "claim_layer": "causal_effect"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'plan_writes'`.

- [ ] **Step 3: Implement `plan_writes` + `validate_candidate`**

First add these imports to the **import block at the top** of `synthesize.py` (third-party + science_model groups):

```python
from pydantic import ValidationError
from science_model.propositions import PropositionEntity
```

Then append the following to the **end** of `science/src/science_tool/annotation/synthesize.py`:

```python
NOT_APPLICABLE = Polarity.NOT_APPLICABLE.value


@dataclass(frozen=True)
class WritePlan:
    writes: dict[str, str]          # field -> value to persist (synthesis-owned only)
    blocked: tuple[str, ...]        # proposed fields blocked by an existing differing value


def _effective(current: dict[str, Any], writes: dict[str, str], field_name: str) -> Any:
    if field_name in writes:
        return writes[field_name]
    val = current.get(field_name)
    return None if val is None else str(val)


def plan_writes(current: dict[str, Any], cand: SynthesisCandidate) -> WritePlan:
    """Pure fill-only-unset + override + sign-less-canonicalization plan. No validation."""
    writes: dict[str, str] = {}
    blocked: list[str] = []
    for f in SYNTH_FIELDS:
        if f not in cand.fields:
            continue                                  # omitted → leave unset/unchanged
        proposed = cand.fields[f]
        cur = current.get(f)
        if cur is None:
            writes[f] = proposed                      # unset → fill
        elif str(cur) == proposed:
            continue                                  # already equal → nothing to do
        elif f in cand.override:
            writes[f] = proposed                      # curator-authorised replace
        else:
            blocked.append(f)                         # existing value blocks default apply
    # Sign-less predicate ⇒ canonicalize an omitted polarity to not_applicable (validate-clean).
    eff_pred = _effective(current, writes, "predicate")
    if eff_pred is not None and eff_pred not in _SIGN_MEANINGFUL_VALUES:
        if _effective(current, writes, "polarity") is None:
            writes["polarity"] = NOT_APPLICABLE
    return WritePlan(writes=writes, blocked=tuple(blocked))


def validate_candidate(current: dict[str, Any], cand: SynthesisCandidate) -> WritePlan:
    """Validate one candidate against current frontmatter; return its WritePlan.

    Enforces the design §7 contracts on the *effective* (post-write) state and the model's
    own relational interlocks. Raises SynthesisOverrideError (override of a currently-unset
    field) or SynthesisApplyError (operand/polarity/interlock). Pure (no writes).
    """
    # override may only target a field that is CURRENTLY set (design §6/§7). The parser
    # checks present-in-patch; the currently-set check needs `current`, so it lives here.
    for name in cand.override:
        if current.get(name) is None:
            raise SynthesisOverrideError(
                f"{cand.proposition}: override names {name!r} but it is currently unset "
                f"(nothing to override — omit it to fill normally)"
            )
    plan = plan_writes(current, cand)
    eff = {f: _effective(current, plan.writes, f) for f in SYNTH_FIELDS}

    # predicate → operands contract (effective subject AND object must exist)
    if "predicate" in cand.fields:
        if eff["subject"] is None or eff["object"] is None:
            raise SynthesisApplyError(
                f"{cand.proposition}: predicate {cand.fields['predicate']!r} requires an "
                f"effective subject and object"
            )
    # polarity → predicate contract (no bare polarity)
    if "polarity" in cand.fields and eff["predicate"] is None:
        raise SynthesisApplyError(
            f"{cand.proposition}: polarity requires an effective predicate"
        )
    # interlocks: construct the would-be entity and let the model validator run
    try:
        PropositionEntity(
            id=cand.proposition, title=str(current.get("title") or ""),
            subject=eff["subject"], object=eff["object"], predicate=eff["predicate"],
            polarity=eff["polarity"], claim_layer=eff["claim_layer"],
        )
    except ValidationError as exc:
        raise SynthesisApplyError(f"{cand.proposition}: {exc}") from exc
    return plan
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: PASS (21 passed).

- [ ] **Step 5: Lint + types**

Run: `rtk uv run --frozen ruff check src/science_tool/annotation/synthesize.py && rtk uv run --frozen pyright src/science_tool/annotation/synthesize.py`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/synthesize.py science/tests/test_proposition_synthesize.py
rtk git commit -m "feat(synthesize): write-plan + contracts + interlock validation (Phase 4c)"
```

---

## Task 6: two-pass apply (validate-all → write) + report

**Files:**
- Modify: `science/src/science_tool/annotation/synthesize.py`
- Test: `science/tests/test_proposition_synthesize.py`

Wire the whole apply: load each in-scope proposition's frontmatter, validate ALL candidates (Pass 1; abort with no writes on any hard error), then write (Pass 2) with fill-only-unset, sign-less canonicalization, `reasoning_source` stamp only on a real write, body preservation, and skip-and-count reasons. Includes uncovered-proposition reporting.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_proposition_synthesize.py`. These tests write real entity files, so they scaffold a `science.yaml` + proposition file like the 4a tests:

```python
from pathlib import Path
from science_tool.annotation.synthesize import SynthReport, apply_synthesis
from science_tool.entities import _parse_markdown_file, write_entity_file
from science_model.propositions import PropositionEntity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    return tmp_path


def _write_prop(root: Path, slug: str, *, title: str, body: str = "# t\n\n## Claim\n\nKEEP-ME\n",
                **fields) -> str:
    ref = f"proposition:{slug}"
    write_entity_file(PropositionEntity(id=ref, title=title, **fields),
                      project_root=root, body=body)
    return ref


def test_apply_fills_unset_and_stamps_source(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim", subject="X", object="Y",
                      body="# claim\n\n## Claim\n\nCURATED PROSE\n")
    cand = _cand({"predicate": "affects", "polarity": "positive", "claim_layer": "causal_effect"},
                 prop=ref)
    report = apply_synthesis(
        [cand], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.updated == 1
    fm, body = _parse_markdown_file(root / "entities/propositions/p.md")
    assert fm["predicate"] == "affects" and fm["polarity"] == "positive"
    assert fm["claim_layer"] == "causal_effect"
    assert fm["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"
    assert "CURATED PROSE" in body          # body preserved


def test_apply_noop_when_already_filled_leaves_file_untouched(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim", subject="X", object="Y",
                      claim_layer="causal_effect")
    before = (root / "entities/propositions/p.md").read_text(encoding="utf-8")
    cand = _cand({"claim_layer": "causal_effect"}, prop=ref)
    report = apply_synthesis(
        [cand], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.updated == 0
    assert report.skipped.get("synthesize-nothing-to-fill") == 1
    after = (root / "entities/propositions/p.md").read_text(encoding="utf-8")
    assert after == before                   # untouched: no reasoning_source, no updated bump


def test_apply_existing_value_blocks(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim", claim_layer="empirical_regularity")
    cand = _cand({"claim_layer": "causal_effect"}, prop=ref)   # differs, no override
    report = apply_synthesis(
        [cand], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.updated == 0
    assert report.skipped.get("synthesize-existing-value-blocks") == 1
    fm, _ = _parse_markdown_file(root / "entities/propositions/p.md")
    assert fm["claim_layer"] == "empirical_regularity"        # unchanged


def test_apply_reports_blocked_fields_even_when_other_fields_write(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim", claim_layer="empirical_regularity")
    cand = _cand({"subject": "X", "claim_layer": "causal_effect"}, prop=ref)
    report = apply_synthesis(
        [cand], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.updated == 1
    assert report.skipped.get("synthesize-existing-value-blocks") == 1
    fm, _ = _parse_markdown_file(root / "entities/propositions/p.md")
    assert fm["subject"] == "X"
    assert fm["claim_layer"] == "empirical_regularity"        # blocked value preserved
    assert fm["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"


def test_apply_uncovered_proposition_counted(tmp_path):
    root = _project(tmp_path)
    ref = _write_prop(root, "p", title="claim")
    report = apply_synthesis(
        [], current={ref: _parse_markdown_file(root / "entities/propositions/p.md")[0]},
        project_root=root, source="llm-synth:m:proposition-synthesize-v1", in_scope={ref},
    )
    assert report.skipped.get("synthesize-proposition-uncovered") == 1


def test_apply_is_atomic_on_interlock_error(tmp_path):
    root = _project(tmp_path)
    good = _write_prop(root, "good", title="good claim")
    bad = _write_prop(root, "bad", title="bad claim")
    cur = {
        good: _parse_markdown_file(root / "entities/propositions/good.md")[0],
        bad: _parse_markdown_file(root / "entities/propositions/bad.md")[0],
    }
    good_cand = _cand({"claim_layer": "causal_effect"}, prop=good,
                      ann="annotation:papers/p.source#s1")
    bad_cand = _cand({"polarity": "positive"}, prop=bad,   # bare polarity → Pass-1 abort
                     ann="annotation:papers/p.source#s2")
    with pytest.raises(SynthesisApplyError):
        apply_synthesis([good_cand, bad_cand], current=cur, project_root=root,
                        source="llm-synth:m:proposition-synthesize-v1", in_scope={good, bad})
    # good was NOT written (validate-before-write): no claim_layer on disk
    fm, _ = _parse_markdown_file(root / "entities/propositions/good.md")
    assert "claim_layer" not in fm
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: FAIL — `ImportError: cannot import name 'apply_synthesis'`.

- [ ] **Step 3: Implement the report + two-pass apply**

First add these imports to the **import block at the top** of `synthesize.py` (stdlib + science_tool groups):

```python
from collections import Counter
from datetime import date

from science_tool.annotation.promote import entity_dest
from science_tool.entities import _parse_markdown_file, write_entity_file
```

Then append the following to the **end** of `science/src/science_tool/annotation/synthesize.py`:

```python


@dataclass
class SynthReport:
    updated: int = 0
    skipped: Counter = field(default_factory=Counter)
    written_paths: list[str] = field(default_factory=list)


def apply_synthesis(
    candidates: list[SynthesisCandidate],
    *,
    current: dict[str, dict[str, Any]],
    project_root: Path,
    source: str,
    in_scope: set[str],
    as_of: date | None = None,
) -> SynthReport:
    """Two-pass apply. Pass 1 validates every candidate (raises ⇒ nothing written); Pass 2
    writes with fill-only-unset, sign-less canonicalization, body preservation, and stamps
    `reasoning_source` only on a real write. Uncovered in-scope props are counted, not failed.
    """
    # Pass 1 — validate everything (no writes). plans[i] aligns with candidates[i].
    plans: list[WritePlan] = [
        validate_candidate(current[c.proposition], c) for c in candidates
    ]

    # Pass 2 — apply.
    report = SynthReport()
    for cand, plan in zip(candidates, plans):
        if plan.blocked:
            # Count every proposed field blocked by an existing differing value, even when
            # other fields on the same candidate are written. This keeps curator-visible
            # conflict reporting from disappearing in mixed write/skip patches.
            report.skipped["synthesize-existing-value-blocks"] += len(plan.blocked)
        if not plan.writes:
            if not plan.blocked:
                report.skipped["synthesize-nothing-to-fill"] += 1
            continue
        fm = dict(current[cand.proposition])
        fm.update(plan.writes)
        fm["reasoning_source"] = source            # a synthesis-owned write (stamped on real change)
        _write_proposition(cand.proposition, fm, project_root, as_of)
        report.updated += 1
        report.written_paths.append(str(entity_dest(cand.proposition, project_root)))

    covered = {c.proposition for c in candidates}
    for prop_ref in in_scope:
        if prop_ref not in covered:
            report.skipped["synthesize-proposition-uncovered"] += 1
    return report


def _write_proposition(
    prop_ref: str, merged_fm: dict[str, Any], project_root: Path, as_of: date | None
) -> None:
    """Body-preserving frontmatter write: reconstruct the typed entity, keep the prose body.

    The existing (possibly curated) markdown body is read and passed back verbatim; only
    frontmatter fields change. `write_entity_file` preserves `created` and advances `updated`.
    """
    dest = entity_dest(prop_ref, project_root)
    _, body = _parse_markdown_file(dest)
    prop = PropositionEntity(**merged_fm)          # re-runs interlock validator; extra keys ignored
    write_entity_file(prop, project_root=project_root, body=body, as_of=as_of)
```

> Note on `PropositionEntity(**merged_fm)`: Pydantic's default `extra="ignore"` drops non-model keys; `created`/`updated` strings coerce to `date` and are then overridden by `write_entity_file`; `status` is a model field so it round-trips (no reset). `exclude_none=True` in the writer keeps omitted reasoning fields absent.

- [ ] **Step 4: Run test to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: PASS (27 passed).

- [ ] **Step 5: Lint + types**

Run: `rtk uv run --frozen ruff check src/science_tool/annotation/synthesize.py && rtk uv run --frozen pyright src/science_tool/annotation/synthesize.py`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/annotation/synthesize.py science/tests/test_proposition_synthesize.py
rtk git commit -m "feat(synthesize): two-pass validate-before-write apply + report (Phase 4c)"
```

---

## Task 7: CLI — `science annotate synthesize`

**Files:**
- Modify: `science/src/science_tool/annotation/cli.py` (add a new command on `annotate_group`; mirror `promote_cmd` at cli.py:1147-1235)
- Test: `science/tests/test_proposition_synthesize.py`

Wire the command: read-only emits the scaffold; `--apply --input` validates + writes. Resolve the sidecar from `<source.md>`, load each in-scope proposition's frontmatter, derive `annotation:` refs exactly as 4a does.

- [ ] **Step 1: Write the failing CLI smoke test (read-only scaffold)**

Append to `science/tests/test_proposition_synthesize.py`:

```python
import json as _json
from click.testing import CliRunner
from science_tool.annotation import io as anno_io
from science_tool.annotation.cli import annotate_group
from science_tool.annotation.model import (
    Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody, Sidecar,
)


def _scaffold_project(tmp_path: Path):
    root = _project(tmp_path)
    _write_prop(root, "brca1", title="BRCA1 affects instability", subject="BRCA1")
    (root / "papers").mkdir()
    md = root / "papers" / "p.source.md"
    md.write_text("BRCA1 affects instability\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    stmt = Annotation(
        id="s1",
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact="BRCA1 affects instability",
                                                           prefix="", suffix="")),
        bodies=(TextualBody(value='{"section":"results","stance":"asserted","subject":"BRCA1"}',
                            format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64, promoted_to="proposition:brca1",
    )
    anno_io.write_sidecar(sp, Sidecar(annotations=(stmt,)))
    return root, md


def test_cli_scaffold_lists_in_scope_proposition(tmp_path):
    root, md = _scaffold_project(tmp_path)
    r = CliRunner().invoke(annotate_group,
                           ["synthesize", str(md), "--root", str(root), "--format", "json"])
    assert r.exit_code == 0, r.output
    payload = _json.loads(r.output)
    assert payload["source"] == "llm-synth:<MODEL>:proposition-synthesize-v1"
    [entry] = payload["propositions"]
    assert entry["proposition"] == "proposition:brca1"
    assert entry["statements"][0]["annotation"] == "annotation:papers/p.source#s1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py::test_cli_scaffold_lists_in_scope_proposition -q -p no:warnings`
Expected: FAIL — `No such command 'synthesize'`.

- [ ] **Step 3: Implement `synthesize_cmd`**

In `science/src/science_tool/annotation/cli.py`, immediately after `promote_cmd` (after line 1235), add:

```python
@annotate_group.command("synthesize")
@click.argument("source_md", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path),
              help="Project root (default: cwd). Used to read/write proposition entities.")
@click.option("--apply", "do_apply", is_flag=True, default=False,
              help="Apply the curator-reviewed --input candidates. Default is read-only scaffold.")
@click.option("--input", "input_path", default=None,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Edited candidates.json (required with --apply).")
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="json")
def synthesize_cmd(source_md: Path, root: Path | None, do_apply: bool,
                   input_path: Path | None, fmt: str) -> None:
    """Synthesize predicate/polarity/claim_layer on promoted propositions (curator-reviewed)."""
    from science_tool.annotation.io import sidecar_for_markdown
    from science_tool.annotation.query import entity_relpath_for_sidecar, read_sidecar_strict
    from science_tool.annotation.promote import entity_dest
    from science_tool.annotation.synthesize import (
        SynthesisApplyError, SynthesisReadError, apply_synthesis, build_scaffold,
        in_scope_propositions, parse_candidates_doc,
    )
    from science_tool.entities import _parse_markdown_file

    if do_apply and input_path is None:
        raise click.ClickException("--apply requires --input (the curator-reviewed candidates file)")
    if input_path is not None and not do_apply:
        raise click.ClickException("--input requires --apply")

    project_root = (root or Path.cwd()).resolve()
    sidecar_path = sidecar_for_markdown(source_md)
    sidecar = read_sidecar_strict(sidecar_path)
    relpath = entity_relpath_for_sidecar(sidecar_path, project_root)

    def ref_for(frag: str) -> str:
        return f"annotation:{relpath}#{frag}"

    scope = in_scope_propositions(sidecar)
    # current frontmatter for each in-scope proposition (read once)
    current: dict[str, dict] = {}
    for prop_ref in scope:
        dest = entity_dest(prop_ref, project_root)
        if not dest.exists():
            raise click.ClickException(f"in-scope proposition {prop_ref} has no file at {dest}")
        current[prop_ref], _ = _parse_markdown_file(dest)

    if not do_apply:
        file_text = source_md.read_text(encoding="utf-8")
        scaffold, unresolved = build_scaffold(sidecar, file_text, current, ref_for=ref_for)
        if fmt == "json":
            click.echo(json.dumps(scaffold, indent=2))
        else:
            for e in scaffold["propositions"]:
                click.echo(f"{e['proposition']:50} statements={len(e['statements'])} "
                           f"hints={len(e['relation_hints'])}")
            click.echo(f"unresolved relation hints: {unresolved}")
        return

    assert input_path is not None
    try:
        doc = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"--input is not valid JSON: {exc}") from exc
    scope_refs = {p: {ref_for(a.id) for a in anns} for p, anns in scope.items()}
    try:
        source, candidates = parse_candidates_doc(doc, scope_refs)
        report = apply_synthesis(candidates, current=current, project_root=project_root,
                                 source=source, in_scope=set(scope))
    except SynthesisReadError as exc:
        raise click.ClickException(str(exc)) from exc
    except SynthesisApplyError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        click.echo(json.dumps({"updated": report.updated, "skipped": dict(report.skipped),
                               "written": report.written_paths}, indent=2))
    else:
        click.echo(f"annotate synthesize: {report.updated} updated, "
                   f"skipped {dict(report.skipped) or 'none'}")
```

- [ ] **Step 4: Run the read-only test to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py::test_cli_scaffold_lists_in_scope_proposition -q -p no:warnings`
Expected: PASS.

- [ ] **Step 5: Write the failing CLI apply test (round-trip)**

Append to `science/tests/test_proposition_synthesize.py`:

```python
def test_cli_apply_writes_reasoning_fields(tmp_path):
    root, md = _scaffold_project(tmp_path)
    cand = {
        "source": "llm-synth:m:proposition-synthesize-v1",
        "candidates": [{
            "proposition": "proposition:brca1",
            "annotation": "annotation:papers/p.source#s1",
            "subject": "BRCA1", "object": "genomic instability",
            "predicate": "affects", "polarity": "positive", "claim_layer": "causal_effect",
        }],
    }
    cpath = root / "cand.json"
    cpath.write_text(_json.dumps(cand), encoding="utf-8")
    r = CliRunner().invoke(annotate_group, ["synthesize", str(md), "--root", str(root),
                                            "--apply", "--input", str(cpath)])
    assert r.exit_code == 0, r.output
    fm, _ = _parse_markdown_file(root / "entities/propositions/brca1.md")
    assert fm["predicate"] == "affects" and fm["polarity"] == "positive"
    assert fm["object"] == "genomic instability"
    assert fm["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"
    # second apply is a clean no-op (everything filled)
    r2 = CliRunner().invoke(annotate_group, ["synthesize", str(md), "--root", str(root),
                                             "--apply", "--input", str(cpath), "--format", "json"])
    assert r2.exit_code == 0, r2.output
    assert _json.loads(r2.output)["updated"] == 0
```

- [ ] **Step 6: Run it to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py::test_cli_apply_writes_reasoning_fields -q -p no:warnings`
Expected: PASS.

- [ ] **Step 7: Lint + types + full unit file**

Run: `rtk uv run --frozen ruff check src/science_tool/annotation/cli.py src/science_tool/annotation/synthesize.py && rtk uv run --frozen pyright src/science_tool/annotation/synthesize.py && rtk uv run --frozen pytest tests/test_proposition_synthesize.py -q -p no:warnings`
Expected: 0 lint/type errors; all unit tests pass.

- [ ] **Step 8: Commit**

```bash
rtk git add science/src/science_tool/annotation/cli.py science/tests/test_proposition_synthesize.py
rtk git commit -m "feat(synthesize): science annotate synthesize CLI (Phase 4c)"
```

---

## Task 8: agent + orchestrator command + tokens doc

**Files:**
- Create: `agents/proposition-synthesize.md`
- Create: `commands/synthesize-propositions.md`
- Modify: `docs/conventions/annotation-tokens.md`

No test (prose/agent prompts). Model the agent file on the existing `agents/paper-annotate.md` (same repo) for tone, frontmatter, and the read→emit→call-CLI shape. Confirm the existing structure first:

- [ ] **Step 1: Read the sibling agent + command for house style**

Run: `rtk sed -n '1,40p' agents/paper-annotate.md && rtk echo '---CMD---' && rtk sed -n '1,40p' commands/annotate-paper.md && rtk echo '---DOC---' && rtk rg -n "Statement promotion|Phase 4" docs/conventions/annotation-tokens.md`
Expected: see the frontmatter keys, section structure, and where the Phase-4a/4b promotion sections live.

- [ ] **Step 2: Create the agent prompt**

Create `agents/proposition-synthesize.md` — frontmatter matching the sibling agent's keys (e.g. `name: proposition-synthesize`, `description`, `model: sonnet`), then a body that instructs the agent to:
  - run `rtk uv run --frozen science annotate synthesize <source.md> --root <root> --format json` to get the scaffold;
  - for **each** proposition, read its `title`, `current`, `statements` (exact/stance/section/subject/object), and `relation_hints` (treat hints as **non-authoritative** context, not authority);
  - emit a candidates file `{ "source": "llm-synth:<your-model>:proposition-synthesize-v1", "candidates": [ ... ] }` with **exactly one** patch per proposition it can factor, each carrying `proposition`, the anchoring `annotation` (one of that proposition's statement refs), and any of `subject`/`object`/`predicate`/`polarity`/`claim_layer` it is confident about (omit a field to leave it unset — never guess, never send `null`);
  - obey the controlled vocabularies and interlocks verbatim:
    - `predicate` ∈ {affects, regulates, associates_with, binds, is_proxy_for, induces_state, transitions_to, subtype_of, part_of}; setting it requires an effective subject AND object;
    - `affects`/`regulates`/`associates_with` require `polarity` ∈ {positive, negative, unsigned}; all other predicates take no polarity (the tool writes `not_applicable`);
    - `claim_layer` ∈ {empirical_regularity, causal_effect, mechanistic_narrative, structural_claim}; independent of subject/object;
    - never propose a bare `polarity` without a `predicate`;
  - hand the candidates file to the curator, who runs `rtk uv run --frozen science annotate synthesize <source.md> --apply --input <file>` after review.
  - State that the agent must NOT call `--apply` itself.

- [ ] **Step 3: Create the orchestrator command**

Create `commands/synthesize-propositions.md` — model on `commands/annotate-paper.md`: a short command that dispatches the `proposition-synthesize` agent against a given `<source.md>`, names the read-only-then-curator-review-then-apply flow, and reminds that apply is a curator action.

- [ ] **Step 4: Document the source string + vocab**

In `docs/conventions/annotation-tokens.md`, add a `## Proposition reasoning synthesis (Phase 4c)` section as a sibling of the Phase-4a/4b promotion sections. Record:
  - the source identity `llm-synth:<model>:proposition-synthesize-v1` and its bump policy (bump the `-vN` when the prompt/vocab/schema changes), and that it is stamped into `PropositionEntity.reasoning_source` on apply;
  - the candidate file shape (top-level `source` + `candidates[]`), the closed `override` set `{subject, object, predicate, polarity, claim_layer}`, and that `reasoning_source` is never overrideable;
  - the skip/error reasons: `synthesize-existing-value-blocks`, `synthesize-nothing-to-fill`, `synthesize-proposition-uncovered`, `synthesize-relation-hint-unresolved`.

- [ ] **Step 5: Sanity-check the docs render**

Run: `rtk rg -n "Phase 4c|llm-synth|synthesize-" docs/conventions/annotation-tokens.md`
Expected: the new section + source string + the four reason tokens are present.

- [ ] **Step 6: Commit**

```bash
rtk git add agents/proposition-synthesize.md commands/synthesize-propositions.md docs/conventions/annotation-tokens.md
rtk git commit -m "docs(synthesize): proposition-synthesize agent + command + tokens (Phase 4c)"
```

---

## Task 9: end-to-end integration test (promote → synthesize → validate)

**Files:**
- Create: `science/tests/test_synthesize_integration.py`

Prove the full pipeline against real entity files and the QA checks: promote a statement to a proposition (4a), synthesize its reasoning fields (4c), and assert the corpus validates clean and re-apply is a no-op. Mirrors `tests/test_promote_qh_integration.py`.

- [ ] **Step 1: Write the failing integration test**

Create `science/tests/test_synthesize_integration.py`:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from science_tool.annotation import io as anno_io
from science_tool.annotation.cli import annotate_group
from science_tool.annotation.model import (
    Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody, Sidecar,
)
from science_tool.entities import _parse_markdown_file
from science_tool.validate import ValidateContext
from science_tool.validate.checks.propositions import (
    check_polarity_predicate_aptitude, check_canonical_enum_binding,
)


def _project_with_statement(tmp_path: Path, exact: str):
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    papers = tmp_path / "entities" / "papers"
    papers.mkdir(parents=True)
    (papers / "p.md").write_text(
        "---\nid: paper:p\ntype: paper\ntitle: Demo\nstatus: active\n"
        'created: "2026-06-16"\nupdated: "2026-06-16"\n---\n# Demo\n\nx\n', encoding="utf-8")
    (tmp_path / "papers").mkdir()
    md = tmp_path / "papers" / "p.source.md"
    md.write_text(f"{exact}\n", encoding="utf-8")
    sp = anno_io.sidecar_for_markdown(md)
    ann = Annotation(
        id="s1",
        target=SpecificResource(source="p.source.md",
                                selector=TextQuoteSelector(exact=exact, prefix="", suffix="")),
        bodies=(TextualBody(value='{"section":"results","stance":"asserted",'
                            '"subject":"BRCA1","object":"genomic instability"}',
                            format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 16, tzinfo=timezone.utc),
        content_hash="0" * 64)
    anno_io.write_sidecar(sp, Sidecar(annotations=(ann,)))
    return md


def test_promote_then_synthesize_validates_clean(tmp_path):
    md = _project_with_statement(tmp_path, "BRCA1 affects genomic instability")
    runner = CliRunner()

    # 4a promote → mints a proposition with predicate/polarity/claim_layer UNSET
    rp = runner.invoke(annotate_group, ["promote", str(md), "--root", str(tmp_path), "--apply"])
    assert rp.exit_code == 0, rp.output
    [prop_file] = list((tmp_path / "entities" / "propositions").glob("*.md"))
    fm0, _ = _parse_markdown_file(prop_file)
    assert "predicate" not in fm0
    prop_ref = fm0["id"]

    # read-only scaffold sees the in-scope proposition + its statement
    rs = runner.invoke(annotate_group, ["synthesize", str(md), "--root", str(tmp_path)])
    assert rs.exit_code == 0, rs.output
    assert prop_ref in rs.output

    # curator candidates → apply
    cand = {"source": "llm-synth:m:proposition-synthesize-v1", "candidates": [{
        "proposition": prop_ref, "annotation": "annotation:papers/p.source#s1",
        "subject": "BRCA1", "object": "genomic instability",
        "predicate": "affects", "polarity": "positive", "claim_layer": "causal_effect"}]}
    cpath = tmp_path / "cand.json"
    cpath.write_text(json.dumps(cand), encoding="utf-8")
    ra = runner.invoke(annotate_group, ["synthesize", str(md), "--root", str(tmp_path),
                                        "--apply", "--input", str(cpath)])
    assert ra.exit_code == 0, ra.output

    fm1, _ = _parse_markdown_file(prop_file)
    assert fm1["predicate"] == "affects" and fm1["polarity"] == "positive"
    assert fm1["claim_layer"] == "causal_effect"
    assert fm1["reasoning_source"] == "llm-synth:m:proposition-synthesize-v1"

    # corpus QA checks pass on the synthesized proposition
    ctx = ValidateContext.from_project_root(tmp_path, strict=False, verbose=False)
    assert list(check_polarity_predicate_aptitude(ctx)) == []
    assert list(check_canonical_enum_binding(ctx)) == []

    # idempotent re-apply
    ra2 = runner.invoke(annotate_group, ["synthesize", str(md), "--root", str(tmp_path),
                                         "--apply", "--input", str(cpath), "--format", "json"])
    assert ra2.exit_code == 0, ra2.output
    assert json.loads(ra2.output)["updated"] == 0
```

- [ ] **Step 2: Run it to verify it passes**

Run: `rtk uv run --frozen pytest tests/test_synthesize_integration.py -q -p no:warnings`
Expected: PASS. (`ValidateContext.from_project_root(root, strict=False, verbose=False)` is the verified constructor — same call `tests/validate/test_check_propositions.py` uses; it works with the minimal `name: demo` manifest.) Do **not** change production code to satisfy the test.

- [ ] **Step 3: Full regression gate**

Run: `rtk uv run --frozen pytest tests/test_proposition_synthesize.py tests/test_synthesize_integration.py tests/test_annotation_promote.py tests/test_promote_qh_integration.py tests/test_promote_numeric_mint.py tests/validate/test_check_propositions.py -q -p no:warnings`
Expected: all pass (4c unit + integration + 4a/4b promote regression + proposition QA).

- [ ] **Step 4: Commit**

```bash
rtk git add science/tests/test_synthesize_integration.py
rtk git commit -m "test(synthesize): end-to-end promote→synthesize→validate integration (Phase 4c)"
```

---

## Final verification (after all tasks)

- [ ] **Broader regression** (annotation + entities + model + validate surfaces):

Run: `rtk uv run --frozen pytest tests/ -q -p no:warnings -k "annotation or promote or synthesize or proposition or validate or entities"`
Expected: green.

- [ ] **Lint + types on all touched production files:**

Run: `rtk uv run --frozen ruff check src/science_tool/annotation/synthesize.py src/science_tool/annotation/cli.py && rtk uv run --frozen pyright src/science_tool/annotation/synthesize.py`
Expected: 0 errors. (`cli.py` may carry pre-existing F401s inherited from the branch base — confirm any finding predates this branch before touching it.)

- [ ] **Hand off** to `superpowers:finishing-a-development-branch`.

---

## Self-review (performed while writing — recorded for the implementer)

**Spec coverage** (design §→task):
- §2 vocab/interlocks → Task 5 (`validate_candidate` builds `PropositionEntity`, the SSOT validator) + Task 1 (field).
- §3 architecture (agent + CLI + module) → Tasks 7, 8, 2–6.
- §4 scope (promotedTo, proposition-only) → Task 2 `in_scope_propositions`.
- §5 scaffold + relation-hint resolution/omission → Task 3.
- §6 candidate shape (source, annotation, override present-in-patch + currently-set, null rule, coverage) → Task 4 (parse-time: present-in-patch, unknown-field, reasoning_source) + Task 5 (currently-set, needs `current`).
- §7 two-pass apply (operand/polarity contracts, interlocks, fill-only-unset, canonicalization, provenance stamp, body preservation, failure boundary) → Tasks 5 + 6.
- §8 idempotency → Tasks 6 (no-op) + 7/9 (re-apply tests).
- §9 model field → Task 1.
- §10 error classes + skip reasons → Tasks 4 (`SynthesisReadError`, `SynthesisOverrideError(SynthesisReadError)`), 5 (`SynthesisApplyError` + override-currently-unset → `SynthesisOverrideError`), 6 (reason counters). The three-class taxonomy matches the design; `SynthesisOverrideError` subclasses `SynthesisReadError` so one CLI catch covers it.

**Imports:** every import lives in the single top-of-file block in `synthesize.py`; later tasks ADD to that block (never append an `import` mid-file) so each task's own Ruff gate stays clean (no E402, no premature F401 — `Path`/`Counter`/`date`/`ValidationError`/`PropositionEntity`/`entity_dest`/`find_qualified_spans`/`write_entity_file` are each introduced in the task that first uses them).

**Scaffold `current`:** emits all five synthesis fields with `null` for unset (design §5), so the agent sees set-vs-available explicitly (Task 3).
- §12 tests → Tasks 2–7, 9.

**Type/name consistency:** `SynthesisCandidate(proposition, annotation, fields, override)`, `WritePlan(writes, blocked)`, `SynthReport(updated, skipped, written_paths)`, `plan_writes`/`validate_candidate`/`apply_synthesis`/`build_scaffold`/`in_scope_propositions`/`parse_candidates_doc` are used identically across tasks. `source` regex, `SYNTH_FIELDS`, and the four skip reasons match the design verbatim.

**Placeholder scan:** every code step carries complete code; the only deliberately prose task (8) is agent/doc text with explicit required content, and Task 9 step 2 names the exact fallback (copy the existing validate test's context setup) rather than leaving it open.
