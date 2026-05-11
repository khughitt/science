# Annotation System P3.0 — Data Model + Sidecar I/O Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the data-model + sidecar I/O foundation for the phase-3
annotation system specified in
`plan:2026-05-10-annotation-system-spec`. P3.0 is the load-bearing
phase — every subsequent phase (P3.1 verify, P3.2 lift, P3.3 CRUD,
P3.4 render, P3.5 LLM audit, P3.6 graph integration, P3.7 dashboard)
consumes the API delivered here. No CLI in this plan; this is the
in-process Python surface plus the sidecar file format.

**Architecture:** New package `science_tool/annotation/` with one
submodule per concern (`model`, `hash`, `skolem`, `io`, `selector`,
`lifecycle`, `ledger`). Frozen dataclasses for the in-process domain
model. `rdflib.Dataset` for TriG parsing; hand-written canonical
serializer for deterministic git-friendly output (mirroring the pattern
in `science_tool/graph/io.py`). Sidecars MAY use blank nodes for
target/selector/body compactness; the skolemization rule lives here so
P3.6 can apply it at graph-ingest time. All public surface is
test-covered; the data-model contract is defined by tests.

**Tech Stack:** Python 3.11, rdflib >=7.0, pytest, dataclasses (frozen).
No new dependencies.

---

## Revision history

- **2026-05-11 (rev 2)** — review pass addressing 6 findings:
  1. **Graph URI mismatch** — parser switches to
     `Dataset(default_union=True)`; named-graph wrapping in the writer
     becomes cosmetic only.
  2. **Relative source IRIs** — parser passes `publicID = sidecar
     directory URI` and strips it on read so `<citation-audit-pilot.md>`
     round-trips as a bare relative path. Model stores authored relative
     paths (not RDF-resolved IRIs).
  3. **Annotation.creator preservation** — added `modified_by` field to
     `Annotation`; `mutate_status` preserves `creator` and writes the
     actor to `modified_by`. Writer emits `dc:contributor` for
     `modified_by`. Lifecycle test gains a `modified_by` assertion.
  4. **Selector fuzzy-tie bug** — algorithm restructured: fuzzy
     matching is now reachable only when `exact` has *zero* occurrences
     in the source. Multiple-match-without-disambiguation returns
     `SUPERSEDED` directly, eliminating the tied-fuzzy attribution
     hazard.
  5. **Fuzzy test fixture** — replaced 2-edit-distance fixture with a
     1-char-substitution fixture that respects `_FUZZY_MAX_RATIO=0.05`.
  6. **Silent missing-field reads** — added `_required()` helper used
     for every required RDF field in the parser; added a malformed
     fixture and a test asserting that missing required fields raise
     `ValueError`.
- **2026-05-11 (rev 1)** — initial draft.

## Spec references

This plan implements the following sections of
`docs/plans/2026-05-10-annotation-system-spec.md`:

- §Data model — surface form table, namespaces note
- §Span addressing — `oa:TextQuoteSelector` resolution algorithm
- §Skolemization for graph ingest — blank-node → IRI rule
- §Multi-annotation per span — shared-target pattern
- §Status lifecycle — mutation API + `prov:wasRevisionOf` chain
- §File layout — twin-file `<entity>.anno.trig`
- §Re-audit cache — `sci:AuditLedger` model
- §Concrete sidecar example — reference fixture for tests

CLI surface, render, audit sources, lift-tokens, and graph integration
are explicitly **out of scope** for P3.0; they land in P3.1+.

---

## File Structure

**Create (source):**

- `science/src/science_tool/annotation/__init__.py` — package init,
  public re-exports of the model + top-level helpers
- `science/src/science_tool/annotation/model.py` — frozen dataclasses
  (`TextQuoteSelector`, `SpecificResource`, `TextualBody`, `IriBody`,
  `Annotation`, `AuditLedger`, `Sidecar`, status/motivation enums)
- `science/src/science_tool/annotation/hash.py` — `content_hash()` for
  the audit-cache key
- `science/src/science_tool/annotation/skolem.py` — blank-node → IRI
  rule used by the graph-ingest step (P3.6)
- `science/src/science_tool/annotation/io.py` — `read_sidecar()` and
  `write_sidecar()`; hand-rolled canonical TriG serializer; rdflib for
  parsing
- `science/src/science_tool/annotation/selector.py` — `resolve_selector()`
  implementing the 4-step algorithm
- `science/src/science_tool/annotation/lifecycle.py` — `mutate_status()`
  with `prov:wasRevisionOf` preservation
- `science/src/science_tool/annotation/ledger.py` — `find_or_create_ledger()`,
  `ledger_contains_hash()`, `ledger_append_hash()`

**Create (tests):**

- `science/tests/test_annotation_model.py`
- `science/tests/test_annotation_hash.py`
- `science/tests/test_annotation_skolem.py`
- `science/tests/test_annotation_io.py`
- `science/tests/test_annotation_selector.py`
- `science/tests/test_annotation_lifecycle.py`
- `science/tests/test_annotation_ledger.py`
- `science/tests/_fixtures/annotation/citation-audit-pilot.anno.trig`
  — reference sidecar matching the spec's concrete example
- `science/tests/_fixtures/annotation/citation-audit-pilot.md` — minimal
  source markdown for selector-resolution tests

**Reference (read-only):**

- `docs/plans/2026-05-10-annotation-system-spec.md` — the spec
- `science/src/science_tool/graph/io.py` — `SCI_NS` binding,
  `_assert_no_blank_nodes`, `_serialize_dataset_deterministically`
  (pattern to follow for canonical writer)
- `science/src/science_tool/markers.py` — module style reference
  (frozen dataclass + `from __future__ import annotations`)

---

## Task 1: Package skeleton + base dataclasses

**Files:**
- Create: `science/src/science_tool/annotation/__init__.py`
- Create: `science/src/science_tool/annotation/model.py`
- Test: `science/tests/test_annotation_model.py`

- [ ] **Step 1: Write failing tests for the model surface**

```python
# science/tests/test_annotation_model.py
"""Unit tests for science_tool.annotation.model."""
from datetime import datetime, timezone

import pytest

from science_tool.annotation.model import (
    Annotation,
    AuditLedger,
    IriBody,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def test_status_values() -> None:
    assert {s.value for s in Status} == {
        "open", "ack", "fixed", "dismissed", "superseded"
    }


def test_motivation_values() -> None:
    assert {m.value for m in Motivation} == {
        "commenting", "tagging", "classifying", "linking",
        "questioning", "identifying", "highlighting",
    }


def test_text_quote_selector_is_frozen() -> None:
    sel = TextQuoteSelector(exact="x", prefix="a ", suffix=" b")
    with pytest.raises(AttributeError):
        sel.exact = "y"  # type: ignore[misc]


def test_specific_resource_holds_source_and_selector() -> None:
    sel = TextQuoteSelector(exact="x", prefix="a ", suffix=" b")
    sr = SpecificResource(source="foo.md", selector=sel)
    assert sr.source == "foo.md"
    assert sr.selector is sel


def test_annotation_minimal_construction() -> None:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    body = TextualBody(value="comment")
    ann = Annotation(
        id="a-1",
        target=target,
        bodies=(body,),
        motivation=Motivation.COMMENTING,
        annotation_type="comment",
        source="human:test",
        status=Status.OPEN,
        creator="test",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
    )
    assert ann.id == "a-1"
    assert ann.bodies == (body,)
    assert ann.content_hash is None  # optional for human source


def test_annotation_audit_source_requires_content_hash() -> None:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    body = TextualBody(value="finding")
    with pytest.raises(ValueError, match="content_hash required"):
        Annotation(
            id="a-2",
            target=target,
            bodies=(body,),
            motivation=Motivation.CLASSIFYING,
            annotation_type="consensus-claim-unsupported",
            source="llm-audit:gap-d-v1",
            status=Status.OPEN,
            creator="claude-opus-4-7",
            created=datetime(2026, 5, 11, tzinfo=timezone.utc),
            content_hash=None,
        )


def test_annotation_modified_required_when_status_changed() -> None:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    body = TextualBody(value="finding")
    with pytest.raises(ValueError, match="modified required"):
        Annotation(
            id="a-3",
            target=target,
            bodies=(body,),
            motivation=Motivation.CLASSIFYING,
            annotation_type="consensus-claim-unsupported",
            source="llm-audit:gap-d-v1",
            status=Status.ACK,           # not the initial state
            creator="claude-opus-4-7",
            created=datetime(2026, 5, 11, tzinfo=timezone.utc),
            content_hash="sha256:abc",
            modified=None,                # but no modified timestamp
            modified_by="alice",
        )


def test_annotation_modified_by_required_when_modified_set() -> None:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    body = TextualBody(value="finding")
    with pytest.raises(ValueError, match="modified_by required"):
        Annotation(
            id="a-4",
            target=target,
            bodies=(body,),
            motivation=Motivation.CLASSIFYING,
            annotation_type="consensus-claim-unsupported",
            source="llm-audit:gap-d-v1",
            status=Status.ACK,
            creator="claude-opus-4-7",
            created=datetime(2026, 5, 11, tzinfo=timezone.utc),
            content_hash="sha256:abc",
            modified=datetime(2026, 5, 11, 11, tzinfo=timezone.utc),
            modified_by=None,            # missing
        )


def test_audit_ledger_holds_source_and_hashes() -> None:
    led = AuditLedger(
        id="ledger-gap-d-v1",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:1f9d", "sha256:abc1"),
        modified=datetime(2026, 5, 11, tzinfo=timezone.utc),
    )
    assert led.source == "llm-audit:gap-d-v1"
    assert led.audited_hashes == ("sha256:1f9d", "sha256:abc1")


def test_sidecar_is_an_aggregate() -> None:
    sc = Sidecar(annotations=(), ledgers=(), shared_targets=())
    assert sc.annotations == ()
    assert sc.ledgers == ()
    assert sc.shared_targets == ()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd science && uv run pytest tests/test_annotation_model.py -v`
Expected: ImportError or ModuleNotFoundError on
`science_tool.annotation.model`.

- [ ] **Step 3: Implement the model**

```python
# science/src/science_tool/annotation/model.py
"""Frozen domain model for the phase-3 annotation system.

See docs/plans/2026-05-10-annotation-system-spec.md §Data model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Optional


class Status(StrEnum):
    OPEN = "open"
    ACK = "ack"
    FIXED = "fixed"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"


class Motivation(StrEnum):
    COMMENTING = "commenting"
    TAGGING = "tagging"
    CLASSIFYING = "classifying"
    LINKING = "linking"
    QUESTIONING = "questioning"
    IDENTIFYING = "identifying"
    HIGHLIGHTING = "highlighting"


# Source kinds whose annotations require a content_hash for re-audit caching.
HASH_REQUIRED_SOURCE_PREFIXES: tuple[str, ...] = ("llm-audit:", "lint:", "marker-scanner:")


@dataclass(frozen=True)
class TextQuoteSelector:
    exact: str
    prefix: str
    suffix: str


@dataclass(frozen=True)
class SpecificResource:
    """Named or shared annotation target. id is None for inline blank-node form."""

    source: str
    selector: TextQuoteSelector
    id: Optional[str] = None  # only set for shared (named-node) targets


@dataclass(frozen=True)
class TextualBody:
    value: str
    format: str = "text/plain"


@dataclass(frozen=True)
class IriBody:
    iri: str


Body = TextualBody | IriBody


@dataclass(frozen=True)
class PriorState:
    """Snapshot of an annotation's pre-mutation state, written into prov:wasRevisionOf."""

    status: Status
    creator: str
    created: datetime


@dataclass(frozen=True)
class Annotation:
    id: str
    target: SpecificResource
    bodies: tuple[Body, ...]
    motivation: Motivation
    annotation_type: str
    source: str
    status: Status
    creator: str                          # original producing agent (preserved across mutations)
    created: datetime
    content_hash: Optional[str] = None
    modified: Optional[datetime] = None
    modified_by: Optional[str] = None     # actor of most recent status mutation
    description: Optional[str] = None
    lifted_from: Optional[str] = None
    prior_states: tuple[PriorState, ...] = ()

    def __post_init__(self) -> None:
        if any(self.source.startswith(p) for p in HASH_REQUIRED_SOURCE_PREFIXES):
            if self.content_hash is None:
                raise ValueError(
                    f"content_hash required for source {self.source!r}"
                )
        if self.status is not Status.OPEN and self.modified is None:
            raise ValueError(
                f"modified required when status is {self.status.value!r} (not 'open')"
            )
        if self.modified is not None and self.modified_by is None:
            raise ValueError(
                "modified_by required whenever modified is set"
            )
        if not self.bodies:
            raise ValueError("annotation must have at least one body")


@dataclass(frozen=True)
class AuditLedger:
    id: str
    source: str
    audited_hashes: tuple[str, ...]
    modified: datetime


@dataclass(frozen=True)
class Sidecar:
    annotations: tuple[Annotation, ...] = ()
    ledgers: tuple[AuditLedger, ...] = ()
    shared_targets: tuple[SpecificResource, ...] = ()
```

```python
# science/src/science_tool/annotation/__init__.py
"""Phase-3 annotation system: data model + sidecar I/O.

See docs/plans/2026-05-10-annotation-system-spec.md.
"""

from science_tool.annotation.model import (
    Annotation,
    AuditLedger,
    Body,
    IriBody,
    Motivation,
    PriorState,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)

__all__ = [
    "Annotation",
    "AuditLedger",
    "Body",
    "IriBody",
    "Motivation",
    "PriorState",
    "Sidecar",
    "SpecificResource",
    "Status",
    "TextQuoteSelector",
    "TextualBody",
]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd science && uv run pytest tests/test_annotation_model.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/__init__.py \
        science/src/science_tool/annotation/model.py \
        science/tests/test_annotation_model.py
git commit -m "feat(annotation): add frozen dataclass model for phase-3"
```

---

## Task 2: Content-hash function

**Files:**
- Create: `science/src/science_tool/annotation/hash.py`
- Test: `science/tests/test_annotation_hash.py`

- [ ] **Step 1: Write failing tests**

```python
# science/tests/test_annotation_hash.py
"""Unit tests for science_tool.annotation.hash."""
from science_tool.annotation.hash import content_hash


def test_content_hash_format() -> None:
    h = content_hash("hello world", "llm-audit:gap-d-v1")
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64  # 32-byte hex


def test_content_hash_deterministic() -> None:
    a = content_hash("the same sentence", "llm-audit:gap-d-v1")
    b = content_hash("the same sentence", "llm-audit:gap-d-v1")
    assert a == b


def test_content_hash_changes_with_text() -> None:
    a = content_hash("text one", "llm-audit:gap-d-v1")
    b = content_hash("text two", "llm-audit:gap-d-v1")
    assert a != b


def test_content_hash_changes_with_source_version() -> None:
    a = content_hash("same text", "llm-audit:gap-d-v1")
    b = content_hash("same text", "llm-audit:gap-d-v2")
    assert a != b


def test_content_hash_separator_prevents_collisions() -> None:
    # "abc" + "def" must differ from "ab" + "cdef" if naive concat were used.
    a = content_hash("abc", "def")
    b = content_hash("ab", "cdef")
    assert a != b
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd science && uv run pytest tests/test_annotation_hash.py -v`
Expected: ImportError on `science_tool.annotation.hash`.

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/annotation/hash.py
"""Content-hash function for annotation re-audit caching.

See docs/plans/2026-05-10-annotation-system-spec.md §Re-audit cache.
"""

from __future__ import annotations

import hashlib

# Domain separator between the two inputs to prevent
# (text="ab", source="cdef") colliding with (text="abc", source="def").
_SEP = b"\x1e"  # ASCII RS (record separator)


def content_hash(exact_text: str, source_version: str) -> str:
    """Return ``"sha256:<hex>"`` for the (text, source-version) pair.

    Used as the cache key for `sci:AuditLedger.audited_hashes`. Two inputs
    are joined with a record-separator byte to prevent boundary collisions.
    """
    h = hashlib.sha256()
    h.update(exact_text.encode("utf-8"))
    h.update(_SEP)
    h.update(source_version.encode("utf-8"))
    return f"sha256:{h.hexdigest()}"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd science && uv run pytest tests/test_annotation_hash.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/hash.py \
        science/tests/test_annotation_hash.py
git commit -m "feat(annotation): add content_hash for audit-cache key"
```

---

## Task 3: Skolemization rule

**Files:**
- Create: `science/src/science_tool/annotation/skolem.py`
- Test: `science/tests/test_annotation_skolem.py`

- [ ] **Step 1: Write failing tests**

```python
# science/tests/test_annotation_skolem.py
"""Unit tests for science_tool.annotation.skolem."""
import pytest

from science_tool.annotation.skolem import skolem_iri


def test_target_iri() -> None:
    assert skolem_iri("a-7f3a", "target") == "a-7f3a/target"


def test_selector_iri() -> None:
    assert skolem_iri("a-7f3a", "selector") == "a-7f3a/target/selector"


def test_first_body_iri_omits_index() -> None:
    assert skolem_iri("a-7f3a", "body") == "a-7f3a/body"


def test_second_body_iri_appends_index() -> None:
    assert skolem_iri("a-7f3a", "body", index=2) == "a-7f3a/body/2"


def test_first_body_with_explicit_index_one_omits() -> None:
    assert skolem_iri("a-7f3a", "body", index=1) == "a-7f3a/body"


def test_unknown_role_raises() -> None:
    with pytest.raises(ValueError, match="unknown role"):
        skolem_iri("a-7f3a", "bogus")  # type: ignore[arg-type]


def test_index_invalid_for_target() -> None:
    with pytest.raises(ValueError, match="index"):
        skolem_iri("a-7f3a", "target", index=2)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd science && uv run pytest tests/test_annotation_skolem.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/annotation/skolem.py
"""Blank-node → IRI rule for graph ingest.

The canonical graph writer (`science_tool/graph/io.py`) rejects blank
nodes. Sidecars MAY use blank nodes for compactness; the ingest step
(P3.6) calls this function to mint stable IRIs before merge.

See docs/plans/2026-05-10-annotation-system-spec.md
§Skolemization for graph ingest.
"""

from __future__ import annotations

from typing import Literal

Role = Literal["target", "selector", "body"]
_VALID_ROLES: frozenset[str] = frozenset(("target", "selector", "body"))


def skolem_iri(annotation_id: str, role: Role, *, index: int = 1) -> str:
    """Return the skolemized IRI suffix for a blank-node role.

    - target  → ``<id>/target``
    - selector → ``<id>/target/selector``
    - body (1) → ``<id>/body``
    - body (N≥2) → ``<id>/body/<N>``

    ``index`` is meaningful only for ``role="body"``; passing it with
    other roles raises ``ValueError``.
    """
    if role not in _VALID_ROLES:
        raise ValueError(f"unknown role: {role!r}")
    if role != "body" and index != 1:
        raise ValueError(f"index is only valid for role='body'; got role={role!r}")
    if role == "target":
        return f"{annotation_id}/target"
    if role == "selector":
        return f"{annotation_id}/target/selector"
    # role == "body"
    if index == 1:
        return f"{annotation_id}/body"
    return f"{annotation_id}/body/{index}"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd science && uv run pytest tests/test_annotation_skolem.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/skolem.py \
        science/tests/test_annotation_skolem.py
git commit -m "feat(annotation): add skolemization rule for graph ingest"
```

---

## Task 4: Sidecar parser (read TriG → Sidecar)

**Files:**
- Create: `science/src/science_tool/annotation/io.py` (parser only;
  writer added in Task 5)
- Create: `science/tests/_fixtures/annotation/citation-audit-pilot.anno.trig`
  (reference fixture matching the spec's concrete example)
- Create: `science/tests/_fixtures/annotation/citation-audit-pilot.md`
  (minimal source markdown)
- Test: `science/tests/test_annotation_io.py` (parse half)

- [ ] **Step 1: Create the reference fixture**

Write to `science/tests/_fixtures/annotation/citation-audit-pilot.anno.trig`:

```turtle
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix oa:   <http://www.w3.org/ns/oa#> .
@prefix dc:   <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix sci:  <http://example.org/science/vocab/> .
@prefix anno: <#> .

anno:annotations {
  anno:t-7f3a a oa:SpecificResource ;
    oa:hasSource <citation-audit-pilot.md> ;
    oa:hasSelector [
      a oa:TextQuoteSelector ;
      oa:exact   "category theory is the right framework" ;
      oa:prefix  "background ('category theory is the right framework', " ;
      oa:suffix  "', 'ontologies remain siloed', 'shared parameters not"
    ] .

  anno:a-7f3a a oa:Annotation ;
    oa:hasTarget       anno:t-7f3a ;
    oa:hasBody         [
      a oa:TextualBody ;
      dc:format        "text/plain" ;
      rdf:value        "Strong field-state claim with no anchor or explicit hedge."
    ] ;
    oa:motivatedBy     oa:classifying ;
    sci:annotationType "consensus-claim-unsupported" ;
    sci:source         "llm-audit:gap-d-v1" ;
    sci:status         "ack" ;
    sci:contentHash    "sha256:1f9dab" ;
    dc:creator         "claude-opus-4-7" ;
    dc:created         "2026-05-10T14:23:00+00:00"^^xsd:dateTime ;
    dc:modified        "2026-05-10T15:01:00+00:00"^^xsd:dateTime ;
    dc:contributor     "keith.hughitt@gmail.com" ;
    dc:description     "Standard textbook framing; no source needed." ;
    prov:wasRevisionOf [
      sci:status       "open" ;
      dc:created       "2026-05-10T14:23:00+00:00"^^xsd:dateTime ;
      dc:creator       "claude-opus-4-7"
    ] .

  anno:a-7f3b a oa:Annotation ;
    oa:hasTarget       anno:t-7f3a ;
    oa:hasBody         [
      a oa:TextualBody ;
      dc:format        "text/plain" ;
      rdf:value        "Worth a footnote pointing at Spivak when we revisit ch3."
    ] ;
    oa:motivatedBy     oa:commenting ;
    sci:annotationType "comment" ;
    sci:source         "human:keith.hughitt@gmail.com" ;
    sci:status         "open" ;
    dc:creator         "keith.hughitt@gmail.com" ;
    dc:created         "2026-05-10T15:02:00+00:00"^^xsd:dateTime .

  anno:ledger-gap-d-v1 a sci:AuditLedger ;
    sci:source         "llm-audit:gap-d-v1" ;
    sci:auditedHashes  ( "sha256:1f9dab" "sha256:abc1" "sha256:def2" ) ;
    dc:modified        "2026-05-10T14:23:00+00:00"^^xsd:dateTime .
}
```

Write to `science/tests/_fixtures/annotation/citation-audit-pilot.md`:

```markdown
---
id: "interpretation:citation-audit-pilot"
type: "interpretation"
---

## Background

Reviewers raised three field-state assertions in the
background ('category theory is the right framework', 'ontologies
remain siloed', 'shared parameters not well explored') without
inline anchors. These are the gap-D pattern.
```

- [ ] **Step 2: Write failing parse tests**

```python
# science/tests/test_annotation_io.py
"""Unit tests for science_tool.annotation.io (parse half — Task 4)."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation import (
    Annotation,
    AuditLedger,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.io import read_sidecar

FIXTURE = Path(__file__).parent / "_fixtures/annotation/citation-audit-pilot.anno.trig"


def test_read_sidecar_returns_sidecar() -> None:
    sc = read_sidecar(FIXTURE)
    assert isinstance(sc, Sidecar)


def test_read_sidecar_finds_two_annotations() -> None:
    sc = read_sidecar(FIXTURE)
    assert len(sc.annotations) == 2


def test_read_sidecar_finds_one_ledger() -> None:
    sc = read_sidecar(FIXTURE)
    assert len(sc.ledgers) == 1


def test_read_sidecar_finds_one_shared_target() -> None:
    sc = read_sidecar(FIXTURE)
    assert len(sc.shared_targets) == 1
    target = sc.shared_targets[0]
    assert target.id == "t-7f3a"
    assert target.source == "citation-audit-pilot.md"
    assert target.selector.exact == "category theory is the right framework"


def test_audit_annotation_parses() -> None:
    sc = read_sidecar(FIXTURE)
    by_id = {a.id: a for a in sc.annotations}
    a = by_id["a-7f3a"]
    assert a.annotation_type == "consensus-claim-unsupported"
    assert a.source == "llm-audit:gap-d-v1"
    assert a.status is Status.ACK
    assert a.motivation is Motivation.CLASSIFYING
    assert a.content_hash == "sha256:1f9dab"
    assert a.creator == "claude-opus-4-7"          # original producer preserved
    assert a.modified_by == "keith.hughitt@gmail.com"   # mutating actor
    assert a.created == datetime(2026, 5, 10, 14, 23, tzinfo=timezone.utc)
    assert a.modified == datetime(2026, 5, 10, 15, 1, tzinfo=timezone.utc)
    assert a.description == "Standard textbook framing; no source needed."
    assert a.target.id == "t-7f3a"  # references shared target by ID
    assert a.target.source == "citation-audit-pilot.md"  # bare relative path, not file URI


def test_audit_annotation_has_prior_state() -> None:
    sc = read_sidecar(FIXTURE)
    a = next(a for a in sc.annotations if a.id == "a-7f3a")
    assert len(a.prior_states) == 1
    prior = a.prior_states[0]
    assert prior.status is Status.OPEN
    assert prior.creator == "claude-opus-4-7"
    assert prior.created == datetime(2026, 5, 10, 14, 23, tzinfo=timezone.utc)


def test_comment_annotation_parses() -> None:
    sc = read_sidecar(FIXTURE)
    a = next(a for a in sc.annotations if a.id == "a-7f3b")
    assert a.annotation_type == "comment"
    assert a.source == "human:keith.hughitt@gmail.com"
    assert a.status is Status.OPEN
    assert a.motivation is Motivation.COMMENTING
    assert a.content_hash is None  # comment source omits hash
    body = a.bodies[0]
    assert isinstance(body, TextualBody)
    assert "Spivak" in body.value


def test_ledger_parses() -> None:
    sc = read_sidecar(FIXTURE)
    led = sc.ledgers[0]
    assert led.id == "ledger-gap-d-v1"
    assert led.source == "llm-audit:gap-d-v1"
    assert led.audited_hashes == ("sha256:1f9dab", "sha256:abc1", "sha256:def2")


def test_read_sidecar_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        read_sidecar(Path("/nonexistent/path.anno.trig"))


def test_empty_sidecar_returns_empty() -> None:
    # An empty TriG file (no annotations or ledgers) is valid.
    sc = read_sidecar(FIXTURE.parent / "empty.anno.trig")
    assert sc.annotations == ()
    assert sc.ledgers == ()
    assert sc.shared_targets == ()


def test_malformed_sidecar_missing_required_field_raises() -> None:
    # An annotation missing sci:annotationType MUST raise, not silently
    # produce annotation_type="None" or "".
    with pytest.raises(ValueError, match="missing required"):
        read_sidecar(FIXTURE.parent / "malformed-missing-type.anno.trig")
```

Also create `science/tests/_fixtures/annotation/empty.anno.trig`:

```turtle
@prefix anno: <#> .

anno:annotations {
}
```

And `science/tests/_fixtures/annotation/malformed-missing-type.anno.trig`:

```turtle
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix oa:   <http://www.w3.org/ns/oa#> .
@prefix dc:   <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix sci:  <http://example.org/science/vocab/> .
@prefix anno: <#> .

anno:annotations {
  anno:a-bad a oa:Annotation ;
    oa:hasTarget [
      oa:hasSource <citation-audit-pilot.md> ;
      oa:hasSelector [
        a oa:TextQuoteSelector ;
        oa:exact   "x" ;
        oa:prefix  "" ;
        oa:suffix  ""
      ]
    ] ;
    oa:hasBody [
      a oa:TextualBody ;
      dc:format "text/plain" ;
      rdf:value "body"
    ] ;
    oa:motivatedBy oa:classifying ;
    # sci:annotationType deliberately missing
    sci:source         "lint:test" ;
    sci:status         "open" ;
    sci:contentHash    "sha256:zzz" ;
    dc:creator         "test" ;
    dc:created         "2026-05-11T00:00:00+00:00"^^xsd:dateTime .
}
```

- [ ] **Step 3: Run tests to verify failure**

Run: `cd science && uv run pytest tests/test_annotation_io.py -v`
Expected: ImportError on `science_tool.annotation.io`.

- [ ] **Step 4: Implement parser**

```python
# science/src/science_tool/annotation/io.py
"""Sidecar TriG I/O.

Parser uses rdflib.Dataset (default_union=True) so the named-graph URI
is irrelevant — we walk all triples in the file. The publicID is set to
the sidecar's directory URI so that relative source IRIs like
<citation-audit-pilot.md> resolve to absolute file URIs at parse time;
the parser strips that prefix back off before storing into the model
(`SpecificResource.source` holds the bare relative path as authored).

Writer (Task 5) hand-rolls canonical TriG for deterministic git-friendly
output. See spec §File layout and §Concrete sidecar example.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from rdflib import RDF, Dataset, Literal, URIRef
from rdflib.namespace import DCTERMS, Namespace, PROV
from rdflib.term import Node

from science_tool.annotation.model import (
    Annotation,
    AuditLedger,
    IriBody,
    Motivation,
    PriorState,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
    Body,
)

OA = Namespace("http://www.w3.org/ns/oa#")
SCI = Namespace("http://example.org/science/vocab/")


def read_sidecar(path: Path) -> Sidecar:
    """Parse a `*.anno.trig` file into a Sidecar.

    Walks all named graphs in the file (via ``default_union=True``), so
    the wrapping graph URI is cosmetic. Relative source IRIs are
    normalized back to bare relative paths against the sidecar's
    directory.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    base_dir_uri = path.parent.resolve().as_uri() + "/"
    ds = Dataset(default_union=True)
    ds.parse(source=str(path), format="trig", publicID=base_dir_uri)

    shared_targets = tuple(_iter_shared_targets(ds, base_dir_uri))
    target_index = {t.id: t for t in shared_targets if t.id is not None}
    annotations = tuple(_iter_annotations(ds, target_index, base_dir_uri))
    ledgers = tuple(_iter_ledgers(ds))
    return Sidecar(
        annotations=annotations,
        ledgers=ledgers,
        shared_targets=shared_targets,
    )


def _iter_shared_targets(ds: Dataset, base_dir_uri: str) -> "list[SpecificResource]":
    out: list[SpecificResource] = []
    for subj in ds.subjects(RDF.type, OA.SpecificResource):
        if not isinstance(subj, URIRef):
            continue  # only named SpecificResources are "shared"
        target_id = _local_name(subj)
        source = _normalize_source_uri(
            _required(ds, subj, OA.hasSource, context="shared target"),
            base_dir_uri,
        )
        sel_node = _required(ds, subj, OA.hasSelector, context="shared target")
        selector = _read_selector(ds, sel_node)
        out.append(SpecificResource(source=source, selector=selector, id=target_id))
    return out


def _read_selector(ds: Dataset, node: Node) -> TextQuoteSelector:
    return TextQuoteSelector(
        exact=str(_required(ds, node, OA.exact, context="selector")),
        prefix=str(_required(ds, node, OA.prefix, context="selector")),
        suffix=str(_required(ds, node, OA.suffix, context="selector")),
    )


def _iter_annotations(
    ds: Dataset,
    target_index: "dict[str, SpecificResource]",
    base_dir_uri: str,
) -> "list[Annotation]":
    out: list[Annotation] = []
    for subj in ds.subjects(RDF.type, OA.Annotation):
        if not isinstance(subj, URIRef):
            continue  # annotations are always named
        ann_id = _local_name(subj)
        ctx = f"annotation {ann_id}"
        target = _read_target(ds, subj, target_index, base_dir_uri, ctx=ctx)
        bodies = tuple(_read_bodies(ds, subj, ctx=ctx))
        motivation = Motivation(
            _local_name(_required(ds, subj, OA.motivatedBy, context=ctx))
        )
        annotation_type = str(_required(ds, subj, SCI.annotationType, context=ctx))
        source = str(_required(ds, subj, SCI.source, context=ctx))
        status = Status(str(_required(ds, subj, SCI.status, context=ctx)))
        creator = str(_required(ds, subj, DCTERMS.creator, context=ctx))
        created = _read_dt(_required(ds, subj, DCTERMS.created, context=ctx))
        modified = _read_optional_dt(ds.value(subj, DCTERMS.modified))
        modified_by = _str_or_none(ds.value(subj, DCTERMS.contributor))
        content_hash = _str_or_none(ds.value(subj, SCI.contentHash))
        description = _str_or_none(ds.value(subj, DCTERMS.description))
        lifted_from = _str_or_none(ds.value(subj, SCI.liftedFrom))
        prior_states = tuple(_read_prior_states(ds, subj))
        out.append(
            Annotation(
                id=ann_id,
                target=target,
                bodies=bodies,
                motivation=motivation,
                annotation_type=annotation_type,
                source=source,
                status=status,
                creator=creator,
                created=created,
                modified=modified,
                modified_by=modified_by,
                content_hash=content_hash,
                description=description,
                lifted_from=lifted_from,
                prior_states=prior_states,
            )
        )
    return out


def _read_target(
    ds: Dataset,
    ann: URIRef,
    target_index: "dict[str, SpecificResource]",
    base_dir_uri: str,
    *,
    ctx: str,
) -> SpecificResource:
    node = _required(ds, ann, OA.hasTarget, context=ctx)
    if isinstance(node, URIRef):
        # Reference to a shared target.
        target_id = _local_name(node)
        if target_id in target_index:
            return target_index[target_id]
    # Inline blank-node target.
    source = _normalize_source_uri(
        _required(ds, node, OA.hasSource, context=f"{ctx} target"),
        base_dir_uri,
    )
    sel_node = _required(ds, node, OA.hasSelector, context=f"{ctx} target")
    return SpecificResource(source=source, selector=_read_selector(ds, sel_node), id=None)


def _read_bodies(ds: Dataset, ann: URIRef, *, ctx: str) -> "list[Body]":
    bodies: list[Body] = []
    for body_node in ds.objects(ann, OA.hasBody):
        if isinstance(body_node, URIRef):
            bodies.append(IriBody(iri=str(body_node)))
            continue
        # Blank-node TextualBody.
        value = _required(ds, body_node, RDF.value, context=f"{ctx} body")
        fmt_node = ds.value(body_node, DCTERMS.format)
        fmt = str(fmt_node) if fmt_node is not None else "text/plain"
        bodies.append(TextualBody(value=str(value), format=fmt))
    if not bodies:
        raise ValueError(f"missing required oa:hasBody on {ctx}")
    return bodies


def _read_prior_states(ds: Dataset, ann: URIRef) -> "list[PriorState]":
    out: list[PriorState] = []
    for prior_node in ds.objects(ann, PROV.wasRevisionOf):
        status = Status(str(_required(ds, prior_node, SCI.status, context="prior state")))
        creator = str(_required(ds, prior_node, DCTERMS.creator, context="prior state"))
        created = _read_dt(_required(ds, prior_node, DCTERMS.created, context="prior state"))
        out.append(PriorState(status=status, creator=creator, created=created))
    return out


def _iter_ledgers(ds: Dataset) -> "list[AuditLedger]":
    out: list[AuditLedger] = []
    for subj in ds.subjects(RDF.type, SCI.AuditLedger):
        if not isinstance(subj, URIRef):
            continue
        led_id = _local_name(subj)
        ctx = f"ledger {led_id}"
        source = str(_required(ds, subj, SCI.source, context=ctx))
        hashes_node = ds.value(subj, SCI.auditedHashes)
        hashes = (
            tuple(str(item) for item in ds.items(hashes_node)) if hashes_node else ()
        )
        modified = _read_dt(_required(ds, subj, DCTERMS.modified, context=ctx))
        out.append(
            AuditLedger(
                id=led_id, source=source, audited_hashes=hashes, modified=modified
            )
        )
    return out


def _required(ds: Any, subj: Node, pred: URIRef, *, context: str) -> Node:
    """Look up a required predicate. Raise loudly if absent."""
    val = ds.value(subj, pred)
    if val is None:
        raise ValueError(f"missing required {pred} on {context} ({subj})")
    return val


def _str_or_none(node: Node | None) -> str | None:
    return None if node is None else str(node)


def _normalize_source_uri(uri_node: Node, base_dir_uri: str) -> str:
    """Strip the sidecar's directory URI prefix to recover the bare relative path.

    URIs that don't start with ``base_dir_uri`` (e.g., absolute http:// or
    cross-directory file://) are returned unchanged.
    """
    s = str(uri_node)
    if s.startswith(base_dir_uri):
        return s[len(base_dir_uri):]
    return s


def _local_name(node: Node | None) -> str:
    if node is None:
        return ""
    s = str(node)
    if "#" in s:
        return s.rsplit("#", 1)[1]
    return s.rsplit("/", 1)[-1]


def _read_dt(node: Node) -> datetime:
    if isinstance(node, Literal):
        py = node.toPython()
        if isinstance(py, datetime):
            return py
    return datetime.fromisoformat(str(node))


def _read_optional_dt(node: Node | None) -> datetime | None:
    if node is None:
        return None
    return _read_dt(node)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd science && uv run pytest tests/test_annotation_io.py -v`
Expected: 11 passed (10 base + malformed-sidecar).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/io.py \
        science/tests/_fixtures/annotation/ \
        science/tests/test_annotation_io.py
git commit -m "feat(annotation): add sidecar parser (rdflib-backed)"
```

---

## Task 5: Sidecar writer (canonical TriG output)

**Files:**
- Modify: `science/src/science_tool/annotation/io.py` (add writer)
- Modify: `science/tests/test_annotation_io.py` (add round-trip tests)

- [ ] **Step 1: Write failing round-trip tests**

Append to `science/tests/test_annotation_io.py`:

```python
from science_tool.annotation.io import write_sidecar


def test_write_sidecar_creates_file(tmp_path: Path) -> None:
    sc = Sidecar()  # empty
    out = tmp_path / "empty.anno.trig"
    write_sidecar(out, sc)
    assert out.exists()


def test_round_trip_preserves_annotations(tmp_path: Path) -> None:
    original = read_sidecar(FIXTURE)
    out = tmp_path / "roundtrip.anno.trig"
    write_sidecar(out, original)
    re_read = read_sidecar(out)
    assert len(re_read.annotations) == len(original.annotations)
    assert len(re_read.ledgers) == len(original.ledgers)
    assert len(re_read.shared_targets) == len(original.shared_targets)
    by_id_orig = {a.id: a for a in original.annotations}
    by_id_new = {a.id: a for a in re_read.annotations}
    for ann_id, orig_ann in by_id_orig.items():
        new_ann = by_id_new[ann_id]
        assert new_ann.annotation_type == orig_ann.annotation_type
        assert new_ann.source == orig_ann.source
        assert new_ann.status == orig_ann.status
        assert new_ann.motivation == orig_ann.motivation
        assert new_ann.content_hash == orig_ann.content_hash
        assert new_ann.creator == orig_ann.creator
        assert new_ann.created == orig_ann.created
        assert new_ann.modified == orig_ann.modified
        assert new_ann.modified_by == orig_ann.modified_by
        assert new_ann.description == orig_ann.description
        assert new_ann.target.source == orig_ann.target.source  # round-trip relative path
        assert len(new_ann.bodies) == len(orig_ann.bodies)
        assert len(new_ann.prior_states) == len(orig_ann.prior_states)


def test_writer_output_is_deterministic(tmp_path: Path) -> None:
    sc = read_sidecar(FIXTURE)
    out_a = tmp_path / "a.anno.trig"
    out_b = tmp_path / "b.anno.trig"
    write_sidecar(out_a, sc)
    write_sidecar(out_b, sc)
    assert out_a.read_text() == out_b.read_text()


def test_writer_sorts_annotations_by_id(tmp_path: Path) -> None:
    sc = read_sidecar(FIXTURE)
    out = tmp_path / "sorted.anno.trig"
    write_sidecar(out, sc)
    text = out.read_text()
    # a-7f3a should appear before a-7f3b in the serialized output
    assert text.index("anno:a-7f3a ") < text.index("anno:a-7f3b ")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd science && uv run pytest tests/test_annotation_io.py -v`
Expected: 4 new failures on `write_sidecar`.

- [ ] **Step 3: Implement writer**

Append to `science/src/science_tool/annotation/io.py`:

```python
def write_sidecar(path: Path, sidecar: Sidecar) -> None:
    """Write a Sidecar to TriG with deterministic, git-friendly formatting.

    Hand-rolled rather than rdflib-serialized to control ordering and
    spacing; rdflib's TriG serializer randomizes blank-node IDs and
    triple ordering across runs.
    """
    lines: list[str] = []
    lines.append("@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .")
    lines.append("@prefix oa:   <http://www.w3.org/ns/oa#> .")
    lines.append("@prefix dc:   <http://purl.org/dc/terms/> .")
    lines.append("@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .")
    lines.append("@prefix prov: <http://www.w3.org/ns/prov#> .")
    lines.append("@prefix sci:  <http://example.org/science/vocab/> .")
    lines.append("@prefix anno: <#> .")
    lines.append("")
    lines.append("anno:annotations {")

    # Shared targets first (so by-ID references resolve), sorted.
    for target in sorted(sidecar.shared_targets, key=lambda t: t.id or ""):
        lines.extend(_emit_shared_target(target))
        lines.append("")

    # Annotations sorted by ID.
    for ann in sorted(sidecar.annotations, key=lambda a: a.id):
        lines.extend(_emit_annotation(ann))
        lines.append("")

    # Ledgers sorted by ID.
    for led in sorted(sidecar.ledgers, key=lambda l: l.id):
        lines.extend(_emit_ledger(led))
        lines.append("")

    lines.append("}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _emit_shared_target(target: SpecificResource) -> "list[str]":
    if target.id is None:
        raise ValueError("shared target requires id")
    sel = target.selector
    return [
        f"  anno:{target.id} a oa:SpecificResource ;",
        f"    oa:hasSource <{target.source}> ;",
        f"    oa:hasSelector [",
        f"      a oa:TextQuoteSelector ;",
        f"      oa:exact   {_str_lit(sel.exact)} ;",
        f"      oa:prefix  {_str_lit(sel.prefix)} ;",
        f"      oa:suffix  {_str_lit(sel.suffix)}",
        f"    ] .",
    ]


def _emit_annotation(ann: Annotation) -> "list[str]":
    out: list[str] = []
    out.append(f"  anno:{ann.id} a oa:Annotation ;")
    if ann.target.id is not None:
        out.append(f"    oa:hasTarget       anno:{ann.target.id} ;")
    else:
        sel = ann.target.selector
        out.append(f"    oa:hasTarget       [")
        out.append(f"      oa:hasSource <{ann.target.source}> ;")
        out.append(f"      oa:hasSelector [")
        out.append(f"        a oa:TextQuoteSelector ;")
        out.append(f"        oa:exact   {_str_lit(sel.exact)} ;")
        out.append(f"        oa:prefix  {_str_lit(sel.prefix)} ;")
        out.append(f"        oa:suffix  {_str_lit(sel.suffix)}")
        out.append(f"      ]")
        out.append(f"    ] ;")
    for body in ann.bodies:
        out.extend(_emit_body(body))
    out.append(f"    oa:motivatedBy     oa:{ann.motivation.value} ;")
    out.append(f"    sci:annotationType {_str_lit(ann.annotation_type)} ;")
    out.append(f"    sci:source         {_str_lit(ann.source)} ;")
    out.append(f"    sci:status         {_str_lit(ann.status.value)} ;")
    if ann.content_hash is not None:
        out.append(f"    sci:contentHash    {_str_lit(ann.content_hash)} ;")
    if ann.lifted_from is not None:
        out.append(f"    sci:liftedFrom     {_str_lit(ann.lifted_from)} ;")
    out.append(f"    dc:creator         {_str_lit(ann.creator)} ;")
    out.append(f"    dc:created         {_dt_lit(ann.created)}")
    if ann.modified is not None:
        out[-1] += " ;"
        out.append(f"    dc:modified        {_dt_lit(ann.modified)}")
        # modified_by is required whenever modified is set (model invariant).
        assert ann.modified_by is not None
        out[-1] += " ;"
        out.append(f"    dc:contributor     {_str_lit(ann.modified_by)}")
    if ann.description is not None:
        out[-1] += " ;"
        out.append(f"    dc:description     {_str_lit(ann.description)}")
    for prior in ann.prior_states:
        out[-1] += " ;"
        out.append(f"    prov:wasRevisionOf [")
        out.append(f"      sci:status       {_str_lit(prior.status.value)} ;")
        out.append(f"      dc:created       {_dt_lit(prior.created)} ;")
        out.append(f"      dc:creator       {_str_lit(prior.creator)}")
        out.append(f"    ]")
    out[-1] += " ."
    return out


def _emit_body(body: Body) -> "list[str]":
    if isinstance(body, IriBody):
        return [f"    oa:hasBody         <{body.iri}> ;"]
    return [
        f"    oa:hasBody         [",
        f"      a oa:TextualBody ;",
        f"      dc:format        {_str_lit(body.format)} ;",
        f"      rdf:value        {_str_lit(body.value)}",
        f"    ] ;",
    ]


def _emit_ledger(led: AuditLedger) -> "list[str]":
    hashes = " ".join(_str_lit(h) for h in led.audited_hashes)
    return [
        f"  anno:{led.id} a sci:AuditLedger ;",
        f"    sci:source         {_str_lit(led.source)} ;",
        f"    sci:auditedHashes  ( {hashes} ) ;",
        f"    dc:modified        {_dt_lit(led.modified)} .",
    ]


def _str_lit(s: str) -> str:
    """Escape a string for use as a TriG plain literal."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _dt_lit(dt: datetime) -> str:
    return f'"{dt.isoformat()}"^^xsd:dateTime'
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd science && uv run pytest tests/test_annotation_io.py -v`
Expected: 15 passed (11 from Task 4 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/io.py \
        science/tests/test_annotation_io.py
git commit -m "feat(annotation): add deterministic sidecar TriG writer"
```

---

## Task 6: Selector resolution algorithm

**Files:**
- Create: `science/src/science_tool/annotation/selector.py`
- Test: `science/tests/test_annotation_selector.py`

- [ ] **Step 1: Write failing tests**

```python
# science/tests/test_annotation_selector.py
"""Unit tests for science_tool.annotation.selector."""
import pytest

from science_tool.annotation import TextQuoteSelector
from science_tool.annotation.selector import (
    ResolutionStatus,
    resolve_selector,
)


def _sel(exact: str, prefix: str = "", suffix: str = "") -> TextQuoteSelector:
    return TextQuoteSelector(exact=exact, prefix=prefix, suffix=suffix)


def test_anchored_exact_unique_match() -> None:
    text = "alpha beta gamma delta"
    sel = _sel(exact="beta", prefix="alpha ", suffix=" gamma")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.RESOLVED
    assert text[r.start:r.end] == "beta"


def test_bare_exact_unique_match_when_anchored_misses() -> None:
    # prefix/suffix don't match (the surrounding context drifted)
    # but exact appears uniquely.
    text = "alpha beta gamma delta"
    sel = _sel(exact="beta", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.DEGRADED
    assert text[r.start:r.end] == "beta"


def test_bare_exact_ambiguous_falls_through_to_prefix_disambiguation() -> None:
    # exact appears twice; prefix uniquely identifies the first occurrence.
    text = "alpha foo, then alpha foo again"
    sel = _sel(exact="foo", prefix="alpha ", suffix=", then")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.RESOLVED  # prefix+exact+suffix wins
    # The first "foo" in "alpha foo,"
    assert text.index("foo") == r.start


def test_bare_exact_ambiguous_with_prefix_only() -> None:
    text = "x foo y; z foo w"
    sel = _sel(exact="foo", prefix="x ", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.DEGRADED
    assert text[r.start:r.end] == "foo"
    assert r.start == text.index("foo")  # the "x foo" occurrence


def test_fuzzy_match_with_clear_margin() -> None:
    # Source text has a single 1-char-substituted version of exact.
    # exact = "quick brawn fox" (15 chars); source contains "quick brown fox".
    # Distance: 1 substitution (a↔o). max_distance = max(1, int(15*0.05)) = 1.
    # Within threshold; only one candidate → margin trivially satisfied.
    text = "the quick brown fox jumps over the lazy dog"
    sel = _sel(exact="quick brawn fox", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.FUZZY
    matched = text[r.start:r.end]
    assert "brown" in matched


def test_fuzzy_match_rejected_without_margin() -> None:
    # Two distinct windows in the source, each one substitution from exact.
    # Both are equally good fuzzy candidates → reject (margin requirement).
    text = "abcdy   ;   abcdz"
    sel = _sel(exact="abcdx", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.SUPERSEDED


def test_ambiguous_exact_returns_superseded_without_attempting_fuzzy() -> None:
    # exact appears multiple times and one-sided anchors don't help.
    # Algorithm MUST NOT fall through to fuzzy (which would silently
    # attribute to the first occurrence with distance-0 ties).
    text = "alpha foo bar; alpha foo bar"
    sel = _sel(exact="foo", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.SUPERSEDED


def test_no_match_returns_superseded() -> None:
    text = "completely different content"
    sel = _sel(exact="missing string", prefix="WRONG", suffix="WRONG")
    r = resolve_selector(text, sel)
    assert r.status is ResolutionStatus.SUPERSEDED
    assert r.start is None
    assert r.end is None
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd science && uv run pytest tests/test_annotation_selector.py -v`
Expected: ImportError on `science_tool.annotation.selector`.

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/annotation/selector.py
"""TextQuoteSelector resolution algorithm.

See docs/plans/2026-05-10-annotation-system-spec.md §Span addressing.
The algorithm is uniqueness-preserving at every step: ambiguous matches
fall through rather than guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from science_tool.annotation.model import TextQuoteSelector


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"           # anchored prefix+exact+suffix matched uniquely
    DEGRADED = "degraded"           # bare exact (or one-sided anchor) matched uniquely
    FUZZY = "fuzzy"                 # Levenshtein match with clear-margin
    SUPERSEDED = "superseded"       # no qualifying match


@dataclass(frozen=True)
class ResolutionResult:
    status: ResolutionStatus
    start: Optional[int] = None
    end: Optional[int] = None


# Fuzzy match acceptance threshold: best score must be ≤ this fraction of len(exact).
_FUZZY_MAX_RATIO = 0.05
# Clear-margin requirement: second-best score must be ≥ this multiple of best.
_FUZZY_MARGIN = 2.0


def resolve_selector(source_text: str, selector: TextQuoteSelector) -> ResolutionResult:
    """Resolve a TextQuoteSelector against the source text per the spec algorithm.

    Algorithm (per spec §Span addressing): each step requires a *unique* match.
    Fuzzy matching is only attempted when ``exact`` has zero occurrences in
    the source — multiple-match-without-disambiguation returns SUPERSEDED
    directly to avoid silent misattribution to a tied span.
    """
    exact = selector.exact
    prefix = selector.prefix
    suffix = selector.suffix

    # Step 1: anchored exact (prefix + exact + suffix), unique.
    if prefix or suffix:
        anchored = prefix + exact + suffix
        positions = _all_occurrences(source_text, anchored)
        if len(positions) == 1:
            start = positions[0] + len(prefix)
            return ResolutionResult(
                status=ResolutionStatus.RESOLVED, start=start, end=start + len(exact)
            )

    # Step 2: bare exact, unique → DEGRADED.
    bare_positions = _all_occurrences(source_text, exact)
    if len(bare_positions) == 1:
        start = bare_positions[0]
        return ResolutionResult(
            status=ResolutionStatus.DEGRADED, start=start, end=start + len(exact)
        )

    # Step 3: bare exact appears multiple times. Try one-sided anchors to
    # disambiguate. If still ambiguous, return SUPERSEDED (do NOT fall
    # through to fuzzy — fuzzy on multiple distance-0 candidates would
    # silently attribute to the first occurrence).
    if len(bare_positions) > 1:
        if prefix:
            left = _all_occurrences(source_text, prefix + exact)
            if len(left) == 1:
                start = left[0] + len(prefix)
                return ResolutionResult(
                    status=ResolutionStatus.DEGRADED,
                    start=start,
                    end=start + len(exact),
                )
        if suffix:
            right = _all_occurrences(source_text, exact + suffix)
            if len(right) == 1:
                start = right[0]
                return ResolutionResult(
                    status=ResolutionStatus.DEGRADED,
                    start=start,
                    end=start + len(exact),
                )
        return ResolutionResult(status=ResolutionStatus.SUPERSEDED)

    # Step 4: zero exact matches. Try fuzzy with margin requirement.
    assert len(bare_positions) == 0
    fuzzy = _fuzzy_unique_match(source_text, exact)
    if fuzzy is not None:
        return ResolutionResult(
            status=ResolutionStatus.FUZZY,
            start=fuzzy,
            end=fuzzy + len(exact),
        )

    # Step 5: superseded.
    return ResolutionResult(status=ResolutionStatus.SUPERSEDED)


def _all_occurrences(haystack: str, needle: str) -> list[int]:
    if not needle:
        return []
    out: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            return out
        out.append(idx)
        start = idx + 1


def _fuzzy_unique_match(source_text: str, exact: str) -> Optional[int]:
    n = len(exact)
    if n == 0 or len(source_text) < n:
        return None
    max_distance = max(1, int(n * _FUZZY_MAX_RATIO))
    best_score = max_distance + 1
    best_offset = -1
    second_best = max_distance + 1
    for offset in range(0, len(source_text) - n + 1):
        window = source_text[offset : offset + n]
        d = _levenshtein_capped(window, exact, max_distance)
        if d < best_score:
            second_best = best_score
            best_score = d
            best_offset = offset
        elif d < second_best:
            second_best = d
    if best_offset < 0 or best_score > max_distance:
        return None
    # Clear-margin requirement.
    if second_best <= max_distance and second_best < best_score * _FUZZY_MARGIN:
        return None
    return best_offset


def _levenshtein_capped(a: str, b: str, max_distance: int) -> int:
    """Levenshtein distance, returning max_distance+1 if the true distance exceeds it.

    Equal-length inputs only (we only ever compare same-length windows).
    """
    if a == b:
        return 0
    n = len(a)
    if n != len(b):
        return max_distance + 1
    prev = list(range(n + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * n
        row_min = curr[0]
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_distance:
            return max_distance + 1
        prev = curr
    return prev[n]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd science && uv run pytest tests/test_annotation_selector.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/selector.py \
        science/tests/test_annotation_selector.py
git commit -m "feat(annotation): add selector resolution (uniqueness-preserving)"
```

---

## Task 7: Status mutation + prov chain

**Files:**
- Create: `science/src/science_tool/annotation/lifecycle.py`
- Test: `science/tests/test_annotation_lifecycle.py`

- [ ] **Step 1: Write failing tests**

```python
# science/tests/test_annotation_lifecycle.py
"""Unit tests for science_tool.annotation.lifecycle."""
from datetime import datetime, timezone

import pytest

from science_tool.annotation import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.lifecycle import mutate_status


def _open_audit_annotation() -> Annotation:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    return Annotation(
        id="a-1",
        target=target,
        bodies=(TextualBody(value="finding"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="consensus-claim-unsupported",
        source="llm-audit:gap-d-v1",
        status=Status.OPEN,
        creator="claude-opus-4-7",
        created=datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
        content_hash="sha256:abc",
    )


def test_ack_mutates_status_and_records_modified() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    out = mutate_status(ann, Status.ACK, actor="alice@example.com", now=later)
    assert out.status is Status.ACK
    assert out.modified == later
    assert out.modified_by == "alice@example.com"   # actor recorded as modifier
    # Other fields preserved — creator stays the original producer.
    assert out.id == ann.id
    assert out.created == ann.created
    assert out.creator == ann.creator               # NOT overwritten by actor
    assert out.content_hash == ann.content_hash


def test_ack_records_prior_state() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    out = mutate_status(ann, Status.ACK, actor="alice@example.com", now=later)
    assert len(out.prior_states) == 1
    prior = out.prior_states[0]
    assert prior.status is Status.OPEN
    assert prior.creator == ann.creator
    assert prior.created == ann.created


def test_dismiss_with_reason_sets_description() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    out = mutate_status(
        ann, Status.DISMISSED, actor="alice", now=later, reason="false positive"
    )
    assert out.status is Status.DISMISSED
    assert out.description == "false positive"


def test_fix_does_not_require_reason() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    out = mutate_status(ann, Status.FIXED, actor="alice", now=later)
    assert out.status is Status.FIXED
    assert out.description is None


def test_cannot_mutate_to_open() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="cannot transition to 'open'"):
        mutate_status(ann, Status.OPEN, actor="alice", now=later)


def test_cannot_mutate_already_terminal() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    out = mutate_status(ann, Status.ACK, actor="alice", now=later)
    even_later = datetime(2026, 5, 11, 13, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="already in terminal status"):
        mutate_status(out, Status.DISMISSED, actor="bob", now=even_later)


def test_supersede_is_allowed_from_any_state() -> None:
    # Selector loss can fire even after ack/fixed/dismissed.
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    acked = mutate_status(ann, Status.ACK, actor="alice", now=later)
    even_later = datetime(2026, 5, 11, 13, 0, tzinfo=timezone.utc)
    superseded = mutate_status(acked, Status.SUPERSEDED, actor="tool:verify", now=even_later)
    assert superseded.status is Status.SUPERSEDED
    # Two prior states now.
    assert len(superseded.prior_states) == 2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd science && uv run pytest tests/test_annotation_lifecycle.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/annotation/lifecycle.py
"""Status mutation with prov:wasRevisionOf preservation.

See docs/plans/2026-05-10-annotation-system-spec.md §Status lifecycle.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Optional

from science_tool.annotation.model import Annotation, PriorState, Status

# Statuses that cannot be re-mutated by author action (only the auto
# `* → superseded` transition is permitted from these states).
_TERMINAL_STATES: frozenset[Status] = frozenset(
    {Status.ACK, Status.FIXED, Status.DISMISSED}
)


def mutate_status(
    annotation: Annotation,
    new_status: Status,
    *,
    actor: str,
    now: datetime,
    reason: Optional[str] = None,
) -> Annotation:
    """Return a new Annotation with status mutated and the prior state preserved.

    - Records ``dc:modified = now``.
    - Appends a ``PriorState`` snapshot to ``prior_states`` capturing the
      pre-mutation status, creator, and created.
    - When ``reason`` is provided, sets ``dc:description``.
    - Refuses transitions to ``open`` and refuses author-initiated
      transitions out of terminal states (ack/fixed/dismissed).
      The auto ``* → superseded`` transition is always permitted.
    """
    if new_status is Status.OPEN:
        raise ValueError("cannot transition to 'open'; status flows forward only")
    if new_status is not Status.SUPERSEDED and annotation.status in _TERMINAL_STATES:
        raise ValueError(
            f"annotation {annotation.id!r} is already in terminal status "
            f"{annotation.status.value!r}"
        )

    prior = PriorState(
        status=annotation.status,
        creator=annotation.creator,
        created=annotation.created,
    )
    new_prior_states = annotation.prior_states + (prior,)

    description = reason if reason is not None else annotation.description

    return replace(
        annotation,
        status=new_status,
        modified=now,
        modified_by=actor,           # actor recorded here, NOT in creator
        description=description,
        prior_states=new_prior_states,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd science && uv run pytest tests/test_annotation_lifecycle.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/lifecycle.py \
        science/tests/test_annotation_lifecycle.py
git commit -m "feat(annotation): add status mutation with prov chain"
```

---

## Task 8: Audit ledger ops

**Files:**
- Create: `science/src/science_tool/annotation/ledger.py`
- Test: `science/tests/test_annotation_ledger.py`

- [ ] **Step 1: Write failing tests**

```python
# science/tests/test_annotation_ledger.py
"""Unit tests for science_tool.annotation.ledger."""
from datetime import datetime, timezone

import pytest

from science_tool.annotation import AuditLedger, Sidecar
from science_tool.annotation.ledger import (
    find_or_create_ledger,
    ledger_append_hash,
    ledger_contains_hash,
)


def _now() -> datetime:
    return datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)


def test_find_or_create_returns_existing_ledger_unchanged() -> None:
    led = AuditLedger(
        id="ledger-gap-d-v1",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:abc",),
        modified=_now(),
    )
    sc = Sidecar(ledgers=(led,))
    new_sc, found = find_or_create_ledger(sc, "llm-audit:gap-d-v1", now=_now())
    assert found is led
    assert new_sc is sc  # no mutation needed


def test_find_or_create_creates_when_missing() -> None:
    sc = Sidecar()
    new_sc, led = find_or_create_ledger(sc, "llm-audit:gap-d-v1", now=_now())
    assert led.source == "llm-audit:gap-d-v1"
    assert led.audited_hashes == ()
    assert led.id.startswith("ledger-")
    assert "gap-d-v1" in led.id
    assert len(new_sc.ledgers) == 1
    assert new_sc.ledgers[0] is led


def test_ledger_contains_hash() -> None:
    led = AuditLedger(
        id="ledger-x",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:abc", "sha256:def"),
        modified=_now(),
    )
    assert ledger_contains_hash(led, "sha256:abc")
    assert ledger_contains_hash(led, "sha256:def")
    assert not ledger_contains_hash(led, "sha256:missing")


def test_ledger_append_hash_returns_new_ledger() -> None:
    led = AuditLedger(
        id="ledger-x",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:abc",),
        modified=datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
    )
    later = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    new_led = ledger_append_hash(led, "sha256:def", now=later)
    assert new_led.audited_hashes == ("sha256:abc", "sha256:def")
    assert new_led.modified == later
    # Original unchanged.
    assert led.audited_hashes == ("sha256:abc",)


def test_ledger_append_hash_dedupes() -> None:
    led = AuditLedger(
        id="ledger-x",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:abc",),
        modified=datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
    )
    later = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    new_led = ledger_append_hash(led, "sha256:abc", now=later)
    # Already present → no append, no modified bump.
    assert new_led is led
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd science && uv run pytest tests/test_annotation_ledger.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# science/src/science_tool/annotation/ledger.py
"""Audit-ledger operations.

The ledger tracks which (sentence, source-version) pairs have been
audited so re-runs skip clean sentences. See spec §Re-audit cache.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from science_tool.annotation.model import AuditLedger, Sidecar


def find_or_create_ledger(
    sidecar: Sidecar, source_version: str, *, now: datetime
) -> tuple[Sidecar, AuditLedger]:
    """Return ``(sidecar, ledger)``; sidecar is unchanged if the ledger exists."""
    for existing in sidecar.ledgers:
        if existing.source == source_version:
            return sidecar, existing
    new_ledger = AuditLedger(
        id=_ledger_id_for(source_version),
        source=source_version,
        audited_hashes=(),
        modified=now,
    )
    new_sidecar = replace(sidecar, ledgers=sidecar.ledgers + (new_ledger,))
    return new_sidecar, new_ledger


def ledger_contains_hash(ledger: AuditLedger, content_hash: str) -> bool:
    return content_hash in ledger.audited_hashes


def ledger_append_hash(
    ledger: AuditLedger, content_hash: str, *, now: datetime
) -> AuditLedger:
    """Return a new ledger with ``content_hash`` appended; idempotent."""
    if content_hash in ledger.audited_hashes:
        return ledger
    return replace(
        ledger,
        audited_hashes=ledger.audited_hashes + (content_hash,),
        modified=now,
    )


def _ledger_id_for(source_version: str) -> str:
    """Mint a stable ledger ID from a source-version string.

    ``llm-audit:gap-d-v1`` → ``ledger-gap-d-v1``
    ``lint:bare-author-year`` → ``ledger-bare-author-year``
    """
    _, _, suffix = source_version.partition(":")
    safe = suffix.replace(":", "-").replace("/", "-")
    return f"ledger-{safe}"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd science && uv run pytest tests/test_annotation_ledger.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/ledger.py \
        science/tests/test_annotation_ledger.py
git commit -m "feat(annotation): add audit-ledger ops (find/contains/append)"
```

---

## Final verification

- [ ] **Run the full annotation test suite**

Run: `cd science && uv run pytest tests/test_annotation_*.py -v`
Expected: 57 tests passed (10 model + 5 hash + 7 skolem + 15 io + 8 selector + 7 lifecycle + 5 ledger).

- [ ] **Run the full project test suite to confirm no regressions**

Run: `cd science && uv run pytest`
Expected: same baseline as before this plan (2179+ passed) plus 57 new annotation tests.

- [ ] **Type-check the new package** (informational; pyright runs in basic mode)

Run: `cd science && uv run pyright src/science_tool/annotation`
Expected: 0 errors.

---

## Out of scope (deferred to later phases)

The following are explicitly NOT in P3.0 — they belong to subsequent phases:

- Any CLI subcommand (`science annotate ...`) — P3.1+
- `verify` drift-detection workflow — P3.1
- Lifting inline tokens or prose-lint hits to annotations — P3.2
- Author CRUD commands (`ack`/`dismiss`/`fix` as CLI surface) — P3.3
  (the underlying `mutate_status()` API ships in P3.0 because it's
  load-bearing for the data model contract, but no CLI binding yet)
- Render (terminal or HTML) — P3.4
- LLM auditor sources — P3.5
- Graph integration / `bears_on` materialization / skolemization at ingest — P3.6
  (the skolemization rule is implemented in P3.0 because the data model
  contract requires it, but invoking it during ingest is P3.6 work)
- Dashboard consumer — P3.7

## Risks / things to watch during execution

1. **rdflib's RDF list parsing.** `g.items(rdf_list_node)` may return
   results in non-source order on some rdflib versions. The ledger
   parser test asserts a specific order; if it fails on the CI rdflib
   version, the parser may need to walk `rdf:first`/`rdf:rest` manually.
2. **TriG round-trip preserves blank-node count, not blank-node IDs.**
   The round-trip test compares model objects (which don't carry
   blank-node IDs), not the raw TriG text. This is intentional —
   rdflib re-mints blank-node IDs on parse.
3. **Determinism of writer ordering.** The hand-rolled writer sorts by
   ID. If two annotations share an ID (shouldn't happen, but the
   constructor doesn't enforce uniqueness), output order is non-
   deterministic. P3.0 doesn't guard against this; could be a
   follow-up if it matters.
4. **datetime timezone awareness.** All datetimes in tests are
   tz-aware (UTC). The model doesn't enforce tz-awareness; the writer
   relies on `isoformat()` which produces an offset suffix only when
   tz-aware. Naive datetimes would silently round-trip wrong.
   Consider adding a constructor-level guard if it surfaces during
   review.
