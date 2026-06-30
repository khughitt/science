# Proposition Cross-Paper Evidence (Phase 4d, Half A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive virtual literature evidence-lines from promoted statement annotations at materialize time, so a proposition's belief reflects how many independent papers assert it and whether they agree.

**Architecture:** A new `annotation/cross_paper_evidence.py` module scans paper `.anno.trig` sidecars for active proposition-promoted statement annotations, turns each `(proposition, paper, stance)` into a virtual `sci:EvidenceLine` node + `cito:supports`/`disputes` edge + provenance metadata (no authored files), and the existing belief engine aggregates them unchanged. A new materialize-phase call emits these before `_derive_bears_on_layer`. A read-only `science annotate cross-paper-evidence` diagnostic surfaces the derived state and any corruption faults.

**Tech Stack:** Python 3.12+, rdflib, Click, pytest; `science_model.reasoning` enums; existing `science_tool.annotation` (sidecar I/O, `TextSourceAdapter`) and `science_tool.graph` (`materialize`, `belief`, `grounding`) modules.

## Global Constraints

- **Test runner is `cd science && uv run --frozen pytest …`** — NOT plain `python -m pytest` (that fails with `ModuleNotFoundError: science_tool` because it bypasses the uv venv where editable `science-model` is installed). Every test command in this plan uses `uv run --frozen`.
- **No `Co-Authored-By` lines** in any commit message.
- **Fail loud, no silent fallbacks.** A corrupt `promoted_to` is an epistemic-input error, not a skip.
- **Behavior-neutral until exercised.** No proposition in any current corpus has a resolved `promoted_to` with a non-`open` stance, so zero virtual lines are derived and the full belief regression net must stay green.
- **Real enum values only** (from `science_model.reasoning`): `EvidenceType.LITERATURE = "literature"`, `EvidenceRole.PROXY_SUPPORT = "proxy_support"` / `BACKGROUND_CONSTRAINT = "background_constraint"`, `EvidenceStrength.MODERATE = "moderate"` / `WEAK = "weak"`, `IndependenceTag.INDEPENDENT = "independent"`. Edges are `CITO_NS.supports` / `CITO_NS.disputes`.
- **Deterministic virtual URI** = `PROJECT_NS["evidence-line/lit-assertion/<digest>"]`, `<digest>` = full SHA-256 hex over the canonical NUL-joined key `f"{proposition_ref}\0{paper_ref}\0{stance}"`. URI-only; never written to `entities/evidence-lines/`.
- **Layering:** `graph/` must not gain a module-level `import science_tool.annotation`. `materialize._derive_phase` calls the new pass via a **function-scoped import** (matching the existing `promote.py:194` lazy-import convention).
- **Scope filter (closed):** only `annotation_type == "proposition"` annotations with `status in {open, ack}` and `promoted_to.startswith("proposition:")` derive evidence. `question`/`hypothesis`-typed annotations are skipped silently; a `proposition`-typed annotation pointing at a non-`proposition:` target is a fault.

Design spec: `docs/plans/2026-06-30-proposition-cross-paper-evidence-phase4d-design.md`.

---

## File Structure

- **Create `science/src/science_tool/annotation/cross_paper_evidence.py`** — the entire feature: scanner, collapse, deterministic URI, triple emit, the materialize-callable `derive_literature_evidence`, the report builder, and the `CrossPaperEvidenceError` aggregate exception + `AssertionFault` / `LiteratureAssertion` dataclasses.
- **Modify `science/src/science_tool/graph/materialize.py`** — insert one call into `_derive_phase` (after `emit_source_snapshots`, before `_derive_bears_on_layer`) via a function-scoped import.
- **Modify `science/src/science_tool/annotation/cli.py`** — add the read-only `cross-paper-evidence` command to `annotate_group`.
- **Create `science/tests/test_cross_paper_evidence.py`** — unit tests for the URI, collapse, scanner faults/skips.
- **Create `science/tests/test_cross_paper_evidence_materialize.py`** — emit + e2e materialize + ordering + behavior-neutral.
- **Create `science/tests/test_cross_paper_evidence_cli.py`** — the diagnostic command.

---

## Reference: verified facts the implementer needs

**Sidecar reading** (`annotation/`):
- `from science_tool.annotation.query import iter_sidecars, read_sidecar_strict` — `iter_sidecars(root: Path) -> Iterator[tuple[Path, Sidecar]]` (walks `root.rglob("*.anno.trig")`, sorted).
- `Sidecar.annotations` is a `tuple[Annotation, ...]`.
- `Annotation` fields used: `.id`, `.annotation_type` (free `str`; statements use `"proposition"`/`"question"`/`"hypothesis"`), `.status` (`Status` enum), `.promoted_to` (`"proposition:<slug>"` or `None`), `.bodies`.
- `from science_tool.annotation.model import Status, TextualBody` — `Status.OPEN/ACK/FIXED/DISMISSED/SUPERSEDED`.
- Stance lives in a JSON body. Extract exactly as `synthesize.py`/`promote.py` do:
  ```python
  def _statement_body(ann) -> dict:
      for body in ann.bodies:
          if isinstance(body, TextualBody) and body.format == "application/json":
              data = json.loads(body.value)
              if isinstance(data, dict):
                  return data
      return {}
  ```
  The closed stance vocabulary is `{"asserted", "negated", "hypothesized", "open"}` (`statement_extract.STANCES`).

**Paper ownership** (`annotation/`):
- `from science_tool.annotation.io import markdown_for_sidecar` — `foo.anno.trig` → `foo.source.md` path.
- `from science_tool.annotation.text_source_adapter import resolve_adapter, TextSourceAdapterError` — `resolve_adapter(md).source_ref(md)` → `"paper:<citekey>"` (raises `TextSourceAdapterError` if unhandled; `ValueError` if `md` is not a `.source.md`).

**Graph namespaces / URIs** (`graph/`):
- `from science_tool.graph.io import PROJECT_NS, SCI_NS, CITO_NS, entity_uri_for_ref` — `entity_uri_for_ref("proposition:foo")` → `URIRef(PROJECT_NS["proposition/foo"])` (lowercases slug); same for `"paper:Bar2020"` → `PROJECT_NS["paper/bar2020"]`.
- `from rdflib import Literal, URIRef` and `from rdflib.namespace import RDF, PROV`.
- Evidence-line rdf:type is `SCI_NS.EvidenceLine`.

**Belief input contract** (already implemented, unchanged): `collect_evidence_units` counts only `cito:supports`/`disputes` edges whose subject is `(line, RDF.type, SCI_NS.EvidenceLine)` in the knowledge graph; per-line metadata (`SCI_NS.evidenceType/evidenceRole/evidenceStrength/evidenceIndependence/independenceGroup`, `PROV.wasDerivedFrom`) is read from the provenance graph. `aggregate_belief` sets `contested=True` whenever a dispute unit survives; a real `contested_group` arises only when a support and dispute share an `independence_group`.

**Materialize insertion** (`graph/materialize.py`):
- `_derive_phase(emit, *, sources, source_snapshots)` at line ~293; `knowledge`/`provenance` named-graph handles bound locally; insert the new call **after** the `if source_snapshots is not None: emit_source_snapshots(...)` block (~line 310) and **before** `_derive_bears_on_layer(...)` (~line 312).
- `sources.entities` is `list[Entity]`; `entity.kind`, `entity.canonical_id` (`"proposition:<slug>"`), `entity.source_refs` (`list[str]`); `sources.project_root` is a `str`.

**CLI model** (`annotation/cli.py`): copy the `ground-prose-decomposition` command shape — `@annotate_group.command(...)`, `--root`/`--format` options, `project_root = (root or Path.cwd()).resolve()`, errors via `raise click.ClickException(...)` (exit 1), JSON via `click.echo(json.dumps(payload, indent=2, sort_keys=True))`.

**Test runner & fixtures**: `cd science && uv run --frozen pytest tests/<file>.py -q`. Project-builder helpers are module-local (see `tests/test_belief_e2e.py`: `_write`, `_manifest`, `_build_and_load`). CLI tests use `CliRunner().invoke(annotate_group, [...])` with `assert result.exit_code == 0, result.output`. `materialize_graph(root, *, strict=True) -> Path` is `from science_tool.graph.materialize import materialize_graph`.

---

## Task 1: Core dataclasses, stance mapping, deterministic URI, collapse

**Files:**
- Create: `science/src/science_tool/annotation/cross_paper_evidence.py`
- Test: `science/tests/test_cross_paper_evidence.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) LiteratureAssertion(proposition_ref: str, paper_ref: str, stance: str, annotation_id: str, sidecar: str)`
  - `@dataclass(frozen=True) AssertionFault(sidecar: str, annotation_id: str, reason: str, detail: str)`
  - `class CrossPaperEvidenceError(Exception)` — holds `faults: tuple[AssertionFault, ...]`; `__str__` enumerates them.
  - `ACTIVE_STATUSES: frozenset[str]` = `{"open", "ack"}`
  - `DERIVED_STANCES: frozenset[str]` = `{"asserted", "negated", "hypothesized"}`; `KNOWN_STANCES` = `DERIVED_STANCES | {"open"}`
  - `STANCE_EMIT: dict[str, tuple[str, str, str]]` — stance → `(cito_token, evidence_role, strength)`
  - `lit_assertion_uri(proposition_ref: str, paper_ref: str, stance: str) -> URIRef`
  - `collapse_assertions(assertions: list[LiteratureAssertion]) -> list[LiteratureAssertion]`

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_cross_paper_evidence.py`:

```python
import hashlib

from rdflib import URIRef

from science_tool.annotation.cross_paper_evidence import (
    ACTIVE_STATUSES,
    AssertionFault,
    CrossPaperEvidenceError,
    DERIVED_STANCES,
    LiteratureAssertion,
    STANCE_EMIT,
    collapse_assertions,
    lit_assertion_uri,
)
from science_tool.graph.io import PROJECT_NS


def test_lit_assertion_uri_is_full_sha256_of_nul_joined_key():
    uri = lit_assertion_uri("proposition:p", "paper:Smith2020", "asserted")
    digest = hashlib.sha256(b"proposition:p\x00paper:Smith2020\x00asserted").hexdigest()
    assert uri == URIRef(PROJECT_NS[f"evidence-line/lit-assertion/{digest}"])
    assert len(digest) == 64  # full, untruncated


def test_lit_assertion_uri_is_deterministic_and_stance_sensitive():
    a = lit_assertion_uri("proposition:p", "paper:A", "asserted")
    b = lit_assertion_uri("proposition:p", "paper:A", "asserted")
    c = lit_assertion_uri("proposition:p", "paper:A", "negated")
    assert a == b
    assert a != c


def test_stance_emit_table_uses_real_enum_values():
    assert STANCE_EMIT["asserted"] == ("supports", "proxy_support", "moderate")
    assert STANCE_EMIT["negated"] == ("disputes", "proxy_support", "moderate")
    assert STANCE_EMIT["hypothesized"] == ("supports", "background_constraint", "weak")
    assert set(STANCE_EMIT) == DERIVED_STANCES
    assert ACTIVE_STATUSES == frozenset({"open", "ack"})


def test_collapse_dedupes_same_proposition_paper_stance_keeps_one():
    a1 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "A.anno.trig")
    a2 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-2", "A.anno.trig")
    out = collapse_assertions([a1, a2])
    assert len(out) == 1
    assert out[0].proposition_ref == "proposition:p"


def test_collapse_keeps_both_stances_for_same_paper():
    sup = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "A.anno.trig")
    dis = LiteratureAssertion("proposition:p", "paper:A", "negated", "ann-2", "A.anno.trig")
    out = collapse_assertions([sup, dis])
    keys = {(x.paper_ref, x.stance) for x in out}
    assert keys == {("paper:A", "asserted"), ("paper:A", "negated")}


def test_collapse_is_order_independent_and_deterministic():
    a1 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-9", "A.anno.trig")
    a2 = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "A.anno.trig")
    assert collapse_assertions([a1, a2]) == collapse_assertions([a2, a1])
    # deterministic representative: lowest annotation_id wins
    assert collapse_assertions([a1, a2])[0].annotation_id == "ann-1"


def test_cross_paper_evidence_error_lists_all_faults():
    faults = (
        AssertionFault("A.anno.trig", "ann-1", "stale-proposition", "proposition:x missing"),
        AssertionFault("B.anno.trig", "ann-2", "invalid-stance", "stance 'maybe'"),
    )
    err = CrossPaperEvidenceError(faults)
    assert err.faults == faults
    text = str(err)
    assert "stale-proposition" in text and "invalid-stance" in text
    assert "ann-1" in text and "ann-2" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence.py -q`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` (module not created yet).

- [ ] **Step 3: Write minimal implementation**

Create `science/src/science_tool/annotation/cross_paper_evidence.py`:

```python
"""Phase 4d (Half A): cross-paper literature evidence derived from promoted statements.

A proposition promoted from N papers (4a mint-or-link) carries N provenance refs but
no belief support. This module turns each active proposition-promoted statement
annotation into a virtual `sci:EvidenceLine` (cito:supports/disputes the proposition,
evidence_type=literature), so the existing belief engine aggregates cross-paper
corroboration and conflict. Evidence is materialize-time derived state — URI-only,
never authored files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from rdflib import URIRef

from science_model.reasoning import (
    EvidenceRole,
    EvidenceStance,
    EvidenceStrength,
    EvidenceType,
    IndependenceTag,
)

from science_tool.graph.io import PROJECT_NS

ACTIVE_STATUSES: frozenset[str] = frozenset({"open", "ack"})
DERIVED_STANCES: frozenset[str] = frozenset({"asserted", "negated", "hypothesized"})
KNOWN_STANCES: frozenset[str] = DERIVED_STANCES | {"open"}
_PROP_PREFIX = "proposition:"

# stance -> (cito edge token, evidence_role, strength). "open" is known-but-not-derived.
STANCE_EMIT: dict[str, tuple[str, str, str]] = {
    "asserted": (EvidenceStance.SUPPORTS.value, EvidenceRole.PROXY_SUPPORT.value, EvidenceStrength.MODERATE.value),
    "negated": (EvidenceStance.DISPUTES.value, EvidenceRole.PROXY_SUPPORT.value, EvidenceStrength.MODERATE.value),
    "hypothesized": (EvidenceStance.SUPPORTS.value, EvidenceRole.BACKGROUND_CONSTRAINT.value, EvidenceStrength.WEAK.value),
}

LITERATURE_TYPE = EvidenceType.LITERATURE.value
INDEPENDENT = IndependenceTag.INDEPENDENT.value


@dataclass(frozen=True)
class LiteratureAssertion:
    proposition_ref: str
    paper_ref: str
    stance: str
    annotation_id: str
    sidecar: str


@dataclass(frozen=True)
class AssertionFault:
    sidecar: str
    annotation_id: str
    reason: str
    detail: str


class CrossPaperEvidenceError(Exception):
    """Aggregate: one or more corrupt promoted-annotation inputs (fail-loud at build)."""

    def __init__(self, faults: tuple[AssertionFault, ...]):
        self.faults = tuple(faults)
        body = "\n".join(
            f"  - {f.sidecar} [{f.annotation_id}] {f.reason}: {f.detail}" for f in self.faults
        )
        super().__init__(f"cross-paper evidence derivation found {len(self.faults)} fault(s):\n{body}")


def lit_assertion_uri(proposition_ref: str, paper_ref: str, stance: str) -> URIRef:
    key = f"{proposition_ref}\0{paper_ref}\0{stance}".encode("utf-8")
    digest = hashlib.sha256(key).hexdigest()
    return URIRef(PROJECT_NS[f"evidence-line/lit-assertion/{digest}"])


def collapse_assertions(assertions: list[LiteratureAssertion]) -> list[LiteratureAssertion]:
    """One unit per (proposition, paper, stance); deterministic representative = lowest id."""
    seen: dict[tuple[str, str, str], LiteratureAssertion] = {}
    for a in sorted(
        assertions, key=lambda x: (x.proposition_ref, x.paper_ref, x.stance, x.annotation_id)
    ):
        key = (a.proposition_ref, a.paper_ref, a.stance)
        if key not in seen:
            seen[key] = a
    return list(seen.values())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence.py -q`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/cross_paper_evidence.py science/tests/test_cross_paper_evidence.py
git commit -m "feat(4d): cross-paper evidence core model, URI, collapse"
```

---

## Task 2: The shared scanner (`scan_literature_assertions`)

**Files:**
- Modify: `science/src/science_tool/annotation/cross_paper_evidence.py`
- Test: `science/tests/test_cross_paper_evidence.py` (append)

**Interfaces:**
- Consumes: `iter_sidecars` (`annotation.query`), `markdown_for_sidecar` (`annotation.io`), `resolve_adapter`/`TextSourceAdapterError` (`annotation.text_source_adapter`), `TextualBody`/`Status` (`annotation.model`).
- Produces: `scan_literature_assertions(project_root: Path, proposition_source_refs: dict[str, frozenset[str]]) -> tuple[list[LiteratureAssertion], list[AssertionFault]]`. Never raises on data faults; accumulates them. `proposition_source_refs` maps `"proposition:<slug>"` → its `source_refs`; only existing propositions appear as keys.

Fault reason tokens: `"non-proposition-target"`, `"stale-proposition"`, `"invalid-stance"`, `"adapter-unresolvable"`, `"ownership-mismatch"`.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_cross_paper_evidence.py`:

```python
import json as _json
from datetime import datetime, timezone
from pathlib import Path

from science_tool.annotation import io as anno_io
from science_tool.annotation.cross_paper_evidence import scan_literature_assertions
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)

_CREATED = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _ann(frag, *, stance, atype="proposition", status=Status.OPEN, promoted_to="proposition:p"):
    body = _json.dumps({"section": "abstract", "stance": stance})
    non_open = status is not Status.OPEN
    return Annotation(
        id=frag,
        target=SpecificResource(
            source="x.source.md", selector=TextQuoteSelector(exact=frag, prefix="", suffix="")
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type=atype,
        source="llm-annot:m:paper-annotate-v1",
        status=status,
        creator="paper-annotate",
        created=_CREATED,
        content_hash="0" * 64,
        modified=_CREATED if non_open else None,
        modified_by="curator" if non_open else None,
        promoted_to=promoted_to,
    )


def _write_paper_sidecar(root: Path, citekey: str, anns):
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Body.\n", encoding="utf-8")
    anno_io.write_sidecar(anno_io.sidecar_for_markdown(md), anno_io.Sidecar(annotations=tuple(anns)))


# The annotation ref 4a accrues for a-1 in Smith2020's sidecar:
_ANN_REF = "annotation:entities/papers/Smith2020.source#a-1"


def test_scan_happy_path_collects_active_proposition_assertions(tmp_path):
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="asserted")])
    refs = {"proposition:p": frozenset({"paper:Smith2020", _ANN_REF})}
    assertions, faults = scan_literature_assertions(tmp_path, refs)
    assert faults == []
    assert len(assertions) == 1
    a = assertions[0]
    assert (a.proposition_ref, a.paper_ref, a.stance) == ("proposition:p", "paper:Smith2020", "asserted")


def test_scan_skips_question_and_hypothesis_typed_annotations(tmp_path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [
            _ann("q-1", stance="asserted", atype="question", promoted_to="question:q"),
            _ann("h-1", stance="asserted", atype="hypothesis", promoted_to="hypothesis:h"),
        ],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}
    assertions, faults = scan_literature_assertions(tmp_path, refs)
    assert assertions == [] and faults == []  # skipped, not errored


def test_scan_skips_inactive_and_open_stance(tmp_path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [
            _ann("f-1", stance="asserted", status=Status.FIXED),
            _ann("o-1", stance="open"),
            _ann("u-1", stance="asserted", promoted_to=None),  # not promoted
        ],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}
    assertions, faults = scan_literature_assertions(tmp_path, refs)
    assert assertions == [] and faults == []


def test_scan_faults_on_non_proposition_target_for_proposition_typed(tmp_path):
    _write_paper_sidecar(
        tmp_path, "Smith2020", [_ann("a-1", stance="asserted", promoted_to="question:q")]
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}
    assertions, faults = scan_literature_assertions(tmp_path, refs)
    assert assertions == []
    assert [f.reason for f in faults] == ["non-proposition-target"]


def test_scan_faults_on_stale_proposition(tmp_path):
    _write_paper_sidecar(
        tmp_path, "Smith2020", [_ann("a-1", stance="asserted", promoted_to="proposition:gone")]
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}
    _, faults = scan_literature_assertions(tmp_path, refs)
    assert [f.reason for f in faults] == ["stale-proposition"]


def test_scan_faults_on_invalid_stance(tmp_path):
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="maybe")])
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}
    _, faults = scan_literature_assertions(tmp_path, refs)
    assert [f.reason for f in faults] == ["invalid-stance"]


def test_scan_inactive_with_corrupt_target_is_skipped_not_errored(tmp_path):
    # Lifecycle check precedes promoted_to corruption checks: an inactive proposition
    # annotation pointing at a non-proposition target is OUT of scope, not a fault.
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [_ann("a-1", stance="asserted", status=Status.DISMISSED, promoted_to="question:q")],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}
    assertions, faults = scan_literature_assertions(tmp_path, refs)
    assert assertions == [] and faults == []


def test_scan_faults_on_ownership_mismatch_paper_absent(tmp_path):
    # annotation ref present, but the resolved paper ref is not in source_refs
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="asserted")])
    refs = {"proposition:p": frozenset({"paper:Other2019", _ANN_REF})}
    assertions, faults = scan_literature_assertions(tmp_path, refs)
    assert assertions == []
    assert [f.reason for f in faults] == ["ownership-mismatch"]


def test_scan_faults_on_ownership_mismatch_annotation_absent(tmp_path):
    # paper ref present, but THIS annotation's ref is not on the proposition — a different
    # annotation citing the same paper must not derive evidence for it.
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="asserted")])
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}  # no annotation ref
    assertions, faults = scan_literature_assertions(tmp_path, refs)
    assert assertions == []
    assert [f.reason for f in faults] == ["ownership-mismatch"]


def test_scan_accumulates_multiple_faults(tmp_path):
    _write_paper_sidecar(
        tmp_path,
        "Smith2020",
        [_ann("a-1", stance="maybe"), _ann("a-2", stance="asserted", promoted_to="proposition:gone")],
    )
    refs = {"proposition:p": frozenset({"paper:Smith2020"})}
    _, faults = scan_literature_assertions(tmp_path, refs)
    assert {f.reason for f in faults} == {"invalid-stance", "stale-proposition"}
    assert len(faults) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence.py -k scan -q`
Expected: FAIL — `ImportError: cannot import name 'scan_literature_assertions'`.

- [ ] **Step 3: Write minimal implementation**

Append to `science/src/science_tool/annotation/cross_paper_evidence.py` (and add imports at top — `from pathlib import Path`, plus the annotation imports shown):

```python
# --- add to the import block at the top of the module ---
from pathlib import Path

from science_tool.annotation.io import markdown_for_sidecar
from science_tool.annotation.model import Status, TextualBody
from science_tool.annotation.query import entity_relpath_for_sidecar, iter_sidecars
from science_tool.annotation.text_source_adapter import TextSourceAdapterError, resolve_adapter


def _statement_stance(ann) -> str:
    for body in ann.bodies:
        if isinstance(body, TextualBody) and body.format == "application/json":
            data = json.loads(body.value)
            if isinstance(data, dict):
                return str(data.get("stance", ""))
    return ""


def _resolve_paper_ref(sidecar_path: Path) -> str | None:
    """paper:<citekey> for the owning sidecar, or None if no adapter resolves it."""
    try:
        md = markdown_for_sidecar(sidecar_path)
        return resolve_adapter(md).source_ref(md)
    except (ValueError, TextSourceAdapterError):
        return None


def scan_literature_assertions(
    project_root: Path,
    proposition_source_refs: dict[str, frozenset[str]],
) -> tuple[list[LiteratureAssertion], list[AssertionFault]]:
    """Scan promoted proposition-annotations into literature assertions + faults.

    Shared by the materialize pass (which raises on faults) and the diagnostic
    (which reports them). Never raises on data faults.
    """
    assertions: list[LiteratureAssertion] = []
    faults: list[AssertionFault] = []

    for sidecar_path, sidecar in iter_sidecars(project_root):
        sref = str(sidecar_path)
        paper_ref: str | None = None
        paper_resolved = False
        for ann in sidecar.annotations:
            if ann.annotation_type != "proposition":
                continue  # question/hypothesis (4b) etc. — not our concern
            if ann.promoted_to is None:
                continue  # unpromoted proposition annotation
            # Lifecycle check FIRST: an inactive backlink (fixed/dismissed/superseded) is
            # out of the active assertion set entirely — skipped, never scrutinized for
            # promoted_to corruption (design §3/§6).
            if str(ann.status) not in ACTIVE_STATUSES:
                continue
            if not ann.promoted_to.startswith(_PROP_PREFIX):
                faults.append(AssertionFault(sref, ann.id, "non-proposition-target", ann.promoted_to))
                continue
            if ann.promoted_to not in proposition_source_refs:
                faults.append(
                    AssertionFault(sref, ann.id, "stale-proposition", f"{ann.promoted_to} not found")
                )
                continue
            stance = _statement_stance(ann)
            if stance == "open":
                continue  # a question, not an assertion
            if stance not in DERIVED_STANCES:
                faults.append(AssertionFault(sref, ann.id, "invalid-stance", f"stance {stance!r}"))
                continue
            if not paper_resolved:
                paper_ref = _resolve_paper_ref(sidecar_path)
                paper_resolved = True
            if paper_ref is None:
                faults.append(
                    AssertionFault(sref, ann.id, "adapter-unresolvable", "no text source adapter")
                )
                continue
            # Ownership: BOTH the paper ref AND this annotation's ref must be on the target
            # proposition's source_refs — the precise link 4a accrued. The paper ref alone
            # would let any annotation citing the same paper derive evidence (design §3 step 2).
            prop_refs = proposition_source_refs[ann.promoted_to]
            ann_ref = f"annotation:{entity_relpath_for_sidecar(sidecar_path, project_root)}#{ann.id}"
            if paper_ref not in prop_refs or ann_ref not in prop_refs:
                faults.append(
                    AssertionFault(
                        sref, ann.id, "ownership-mismatch",
                        f"{paper_ref} and/or {ann_ref} absent from {ann.promoted_to} source_refs",
                    )
                )
                continue
            assertions.append(
                LiteratureAssertion(ann.promoted_to, paper_ref, stance, ann.id, sref)
            )

    return assertions, faults
```

Notes: `str(ann.status)` works because `Status` is a `StrEnum` (`str(Status.OPEN) == "open"`). `entity_relpath_for_sidecar(<root>/entities/papers/Smith2020.source.anno.trig, <root>)` → `"entities/papers/Smith2020.source"`, so the annotation ref is `annotation:entities/papers/Smith2020.source#<ann.id>` — exactly what 4a's `_annotation_ref` accrues.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence.py -q`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/cross_paper_evidence.py science/tests/test_cross_paper_evidence.py
git commit -m "feat(4d): scanner for promoted proposition assertions + faults"
```

---

## Task 3: Triple emit + materialize-callable `derive_literature_evidence`

**Files:**
- Modify: `science/src/science_tool/annotation/cross_paper_evidence.py`
- Test: `science/tests/test_cross_paper_evidence_materialize.py`

**Interfaces:**
- Produces:
  - `emit_literature_evidence(knowledge, provenance, assertions: list[LiteratureAssertion]) -> None` — emits the virtual line triples for already-collapsed assertions.
  - `derive_literature_evidence(dataset, project_root: Path, proposition_source_refs: dict[str, frozenset[str]]) -> None` — scans, **raises `CrossPaperEvidenceError` if any faults**, else collapses + emits. This is the materialize entry point.
- Consumes: `rdflib` `Dataset`, `Literal`, `URIRef`, `RDF`, `PROV`; `SCI_NS`, `CITO_NS`, `PROJECT_NS`, `entity_uri_for_ref` (`graph.io`).

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_cross_paper_evidence_materialize.py`:

```python
import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.annotation.cross_paper_evidence import (
    CrossPaperEvidenceError,
    LiteratureAssertion,
    derive_literature_evidence,
    emit_literature_evidence,
    lit_assertion_uri,
)
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS


def _named_graphs():
    ds = Dataset()
    return ds, ds.graph(PROJECT_NS["graph/knowledge"]), ds.graph(PROJECT_NS["graph/provenance"])


def test_emit_supports_line_has_full_triple_shape():
    _, knowledge, provenance = _named_graphs()
    a = LiteratureAssertion("proposition:p", "paper:Smith2020", "asserted", "ann-1", "s")
    emit_literature_evidence(knowledge, provenance, [a])

    line = lit_assertion_uri("proposition:p", "paper:Smith2020", "asserted")
    prop = URIRef(PROJECT_NS["proposition/p"])
    paper = URIRef(PROJECT_NS["paper/smith2020"])
    assert (line, RDF.type, SCI_NS.EvidenceLine) in knowledge
    assert (line, CITO_NS.supports, prop) in knowledge
    assert (line, SCI_NS.evidenceType, Literal("literature")) in provenance
    assert (line, SCI_NS.evidenceRole, Literal("proxy_support")) in provenance
    assert (line, SCI_NS.evidenceStrength, Literal("moderate")) in provenance
    assert (line, SCI_NS.evidenceIndependence, Literal("independent")) in provenance
    assert (line, SCI_NS.independenceGroup, Literal("literature-paper:Smith2020")) in provenance
    assert (line, PROV.wasDerivedFrom, paper) in provenance


def test_emit_negated_line_uses_disputes_edge():
    _, knowledge, provenance = _named_graphs()
    a = LiteratureAssertion("proposition:p", "paper:A", "negated", "ann-1", "s")
    emit_literature_evidence(knowledge, provenance, [a])
    line = lit_assertion_uri("proposition:p", "paper:A", "negated")
    assert (line, CITO_NS.disputes, URIRef(PROJECT_NS["proposition/p"])) in knowledge


def test_emit_hypothesized_line_is_weak_background_constraint():
    _, knowledge, provenance = _named_graphs()
    a = LiteratureAssertion("proposition:p", "paper:A", "hypothesized", "ann-1", "s")
    emit_literature_evidence(knowledge, provenance, [a])
    line = lit_assertion_uri("proposition:p", "paper:A", "hypothesized")
    assert (line, SCI_NS.evidenceRole, Literal("background_constraint")) in provenance
    assert (line, SCI_NS.evidenceStrength, Literal("weak")) in provenance
    assert (line, CITO_NS.supports, URIRef(PROJECT_NS["proposition/p"])) in knowledge


def test_derive_raises_aggregate_on_faults(tmp_path):
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import (
        Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
    )
    import json as _json
    from datetime import datetime, timezone

    md = tmp_path / "entities" / "papers" / "Smith2020.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Body.\n", encoding="utf-8")
    ann = Annotation(
        id="a-1",
        target=SpecificResource(source="x.source.md", selector=TextQuoteSelector(exact="a-1", prefix="", suffix="")),
        bodies=(TextualBody(value=_json.dumps({"stance": "maybe"}), format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 30, tzinfo=timezone.utc),
        content_hash="0" * 64, promoted_to="proposition:p",
    )
    anno_io.write_sidecar(anno_io.sidecar_for_markdown(md), anno_io.Sidecar(annotations=(ann,)))

    ds, _, _ = _named_graphs()
    with pytest.raises(CrossPaperEvidenceError) as exc:
        derive_literature_evidence(ds, tmp_path, {"proposition:p": frozenset({"paper:Smith2020"})})
    assert "invalid-stance" in str(exc.value)


def test_derive_emits_when_clean(tmp_path):
    from science_tool.annotation import io as anno_io
    from science_tool.annotation.model import (
        Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
    )
    import json as _json
    from datetime import datetime, timezone

    md = tmp_path / "entities" / "papers" / "Smith2020.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Body.\n", encoding="utf-8")
    ann = Annotation(
        id="a-1",
        target=SpecificResource(source="x.source.md", selector=TextQuoteSelector(exact="a-1", prefix="", suffix="")),
        bodies=(TextualBody(value=_json.dumps({"stance": "asserted"}), format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=datetime(2026, 6, 30, tzinfo=timezone.utc),
        content_hash="0" * 64, promoted_to="proposition:p",
    )
    anno_io.write_sidecar(anno_io.sidecar_for_markdown(md), anno_io.Sidecar(annotations=(ann,)))

    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    derive_literature_evidence(
        ds,
        tmp_path,
        {
            "proposition:p": frozenset(
                {"paper:Smith2020", "annotation:entities/papers/Smith2020.source#a-1"}
            )
        },
    )
    line = lit_assertion_uri("proposition:p", "paper:Smith2020", "asserted")
    assert (line, RDF.type, SCI_NS.EvidenceLine) in knowledge


def test_proposition_source_refs_map_filters_by_kind():
    from types import SimpleNamespace

    from science_tool.annotation.cross_paper_evidence import proposition_source_refs_map

    ents = [
        SimpleNamespace(canonical_id="proposition:p", kind="proposition", source_refs=["paper:A"]),
        SimpleNamespace(canonical_id="hypothesis:h", kind="hypothesis", source_refs=["paper:B"]),
    ]
    assert proposition_source_refs_map(ents) == {"proposition:p": frozenset({"paper:A"})}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence_materialize.py -q`
Expected: FAIL — `ImportError: cannot import name 'emit_literature_evidence'`.

- [ ] **Step 3: Write minimal implementation**

Append to `science/src/science_tool/annotation/cross_paper_evidence.py` (add the rdflib + graph.io imports to the top import block):

```python
# --- add to the import block at the top of the module ---
from rdflib import Dataset, Literal
from rdflib.namespace import PROV, RDF

from science_tool.graph.io import CITO_NS, SCI_NS, entity_uri_for_ref


def emit_literature_evidence(knowledge, provenance, assertions: list[LiteratureAssertion]) -> None:
    """Emit virtual evidence-line triples for already-collapsed assertions."""
    for a in assertions:
        line = lit_assertion_uri(a.proposition_ref, a.paper_ref, a.stance)
        prop = entity_uri_for_ref(a.proposition_ref)
        paper = entity_uri_for_ref(a.paper_ref)
        edge_token, role, strength = STANCE_EMIT[a.stance]
        cito_pred = CITO_NS.supports if edge_token == "supports" else CITO_NS.disputes
        knowledge.add((line, RDF.type, SCI_NS.EvidenceLine))
        knowledge.add((line, cito_pred, prop))
        provenance.add((line, SCI_NS.evidenceType, Literal(LITERATURE_TYPE)))
        provenance.add((line, SCI_NS.evidenceRole, Literal(role)))
        provenance.add((line, SCI_NS.evidenceStrength, Literal(strength)))
        provenance.add((line, SCI_NS.evidenceIndependence, Literal(INDEPENDENT)))
        provenance.add((line, SCI_NS.independenceGroup, Literal(f"literature-{a.paper_ref}")))
        provenance.add((line, PROV.wasDerivedFrom, paper))


def derive_literature_evidence(
    dataset: Dataset,
    project_root: Path,
    proposition_source_refs: dict[str, frozenset[str]],
) -> None:
    """Materialize entry point. Scans, raises on faults (fail-loud), else emits."""
    assertions, faults = scan_literature_assertions(project_root, proposition_source_refs)
    if faults:
        raise CrossPaperEvidenceError(tuple(faults))
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    emit_literature_evidence(knowledge, provenance, collapse_assertions(assertions))


def proposition_source_refs_map(entities) -> dict[str, frozenset[str]]:
    """proposition_ref -> source_refs, from a ProjectSources.entities list.

    Shared by the materialize pass (Task 4 passes `sources.entities`) and the diagnostic
    report (Task 5 passes `load_project_sources(root).entities`) so the two paths never
    diverge on proposition owners.
    """
    return {e.canonical_id: frozenset(e.source_refs) for e in entities if e.kind == "proposition"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence_materialize.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/annotation/cross_paper_evidence.py science/tests/test_cross_paper_evidence_materialize.py
git commit -m "feat(4d): emit virtual evidence-line triples + fail-loud derive"
```

---

## Task 4: Wire into `_derive_phase` + e2e materialize, ordering, behavior-neutral

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (insert one call in `_derive_phase`)
- Test: `science/tests/test_cross_paper_evidence_materialize.py` (append)

**Interfaces:**
- Consumes: `derive_literature_evidence` (function-scoped import inside `_derive_phase`).
- The pass runs after `emit_source_snapshots`, before `_derive_bears_on_layer`.

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_cross_paper_evidence_materialize.py`. These build a real project (paper entities + `.source.md` + `.anno.trig` sidecars + a proposition entity whose `source_refs` list all three papers), run `materialize_graph`, and assert belief.

```python
from datetime import datetime, timezone
import json as _json

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import (
    Annotation, Motivation, SpecificResource, Status, TextQuoteSelector, TextualBody,
)
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.grounding import ground_proposition, load_grounding_graphs

_C = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _manifest(root):
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )


def _paper_entity(root, citekey):
    p = root / "entities" / "papers" / f"{citekey}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\nid: paper:{citekey}\ntype: paper\ntitle: {citekey}\nstatus: active\n---\n\nAbstract.\n",
        encoding="utf-8",
    )


def _proposition_entity(root, slug, source_refs):
    p = root / "entities" / "propositions" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    refs = "".join(f"  - {r}\n" for r in source_refs)
    p.write_text(
        f"---\nid: proposition:{slug}\ntype: proposition\ntitle: {slug}\nstatus: active\n"
        f"source_refs:\n{refs}---\n\nClaim.\n",
        encoding="utf-8",
    )


def _promoted_ann(frag, *, stance, slug="claim"):
    return Annotation(
        id=frag,
        target=SpecificResource(source="x.source.md", selector=TextQuoteSelector(exact=frag, prefix="", suffix="")),
        bodies=(TextualBody(value=_json.dumps({"section": "results", "stance": stance}), format="application/json"),),
        motivation=Motivation.CLASSIFYING, annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1", status=Status.OPEN,
        creator="paper-annotate", created=_C, content_hash="0" * 64,
        promoted_to=f"proposition:{slug}",
    )


def _paper_with_promoted(root, citekey, *, stance, slug="claim"):
    _paper_entity(root, citekey)
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.write_text("Results show the claim.\n", encoding="utf-8")
    anno_io.write_sidecar(
        anno_io.sidecar_for_markdown(md),
        anno_io.Sidecar(annotations=(_promoted_ann(f"{citekey}-1", stance=stance, slug=slug),)),
    )


def _ann_ref(citekey):
    # mirrors 4a's accrued annotation ref: entity_relpath_for_sidecar + "#" + ann.id
    return f"annotation:entities/papers/{citekey}.source#{citekey}-1"


def _scaffold_three_papers(root):
    _manifest(root)
    papers = ["A2020", "B2021", "C2022"]
    # ownership requires BOTH the paper ref AND the annotation ref on the proposition
    source_refs = [f"paper:{c}" for c in papers] + [_ann_ref(c) for c in papers]
    _proposition_entity(root, "claim", source_refs)
    _paper_with_promoted(root, "A2020", stance="asserted")
    _paper_with_promoted(root, "B2021", stance="asserted")
    _paper_with_promoted(root, "C2022", stance="negated")


def test_e2e_two_papers_assert_one_disputes_is_contested(tmp_path):
    _scaffold_three_papers(tmp_path)
    trig = materialize_graph(tmp_path, strict=False)
    knowledge, provenance = load_grounding_graphs(trig)
    result = ground_proposition("proposition:claim", knowledge, provenance, floor="fragile")
    assert result.support_units == 2
    assert result.dispute_units == 1
    assert result.contested is True
    assert result.belief_magnitude == "supported"


def test_e2e_behavior_neutral_when_no_promoted_statements(tmp_path):
    # A proposition with paper source_refs but NO promoted annotations -> no virtual lines.
    _manifest(tmp_path)
    _proposition_entity(tmp_path, "claim", ["paper:A2020"])
    _paper_entity(tmp_path, "A2020")
    trig = materialize_graph(tmp_path, strict=False)
    knowledge, provenance = load_grounding_graphs(trig)
    result = ground_proposition("proposition:claim", knowledge, provenance, floor="fragile")
    assert result.support_units == 0 and result.dispute_units == 0


def test_e2e_virtual_edges_enter_bears_on_closure(tmp_path):
    # Ordering proof: the virtual cito edges exist before _derive_bears_on_layer, so the
    # virtual line bears on the proposition in the derived bridge/closure layer.
    _scaffold_three_papers(tmp_path)
    trig = materialize_graph(tmp_path, strict=False)
    from rdflib import Dataset, URIRef
    from science_tool.graph.io import PROJECT_NS, SCI_NS
    ds = Dataset(); ds.parse(source=str(trig), format="trig")
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    prop = URIRef(PROJECT_NS["proposition/claim"])
    bears_on = list(knowledge.triples((None, SCI_NS.bearsOn, prop)))
    # at least one virtual lit-assertion line bears on the proposition
    assert any("evidence-line/lit-assertion/" in str(s) for s, _, _ in bears_on)


def test_e2e_stale_promoted_to_fails_build(tmp_path):
    _manifest(tmp_path)
    _proposition_entity(tmp_path, "claim", ["paper:A2020"])
    # paper promotes to a proposition that does not exist
    _paper_with_promoted(tmp_path, "A2020", stance="asserted", slug="ghost")
    from science_tool.annotation.cross_paper_evidence import CrossPaperEvidenceError
    with pytest.raises(CrossPaperEvidenceError):
        materialize_graph(tmp_path, strict=False)


def test_same_paper_mixed_stance_yields_contested_group():
    # The design's key fork: one paper asserting AND negating the same proposition shares
    # one independence_group -> a real contested_group (not two corroborations).
    from science_tool.annotation.cross_paper_evidence import (
        LiteratureAssertion, emit_literature_evidence,
    )
    from science_tool.graph.belief import aggregate_belief, collect_evidence_units
    from science_tool.graph.io import entity_uri_for_ref

    ds, knowledge, provenance = _named_graphs()
    sup = LiteratureAssertion("proposition:p", "paper:A", "asserted", "ann-1", "s")
    dis = LiteratureAssertion("proposition:p", "paper:A", "negated", "ann-2", "s")
    emit_literature_evidence(knowledge, provenance, [sup, dis])
    belief = aggregate_belief(
        collect_evidence_units(knowledge, provenance, [entity_uri_for_ref("proposition:p")])
    )
    assert belief.contested is True
    assert belief.contested_groups == {"literature-paper:A"}
```

Notes for the implementer:
- `test_e2e_two_papers_assert_one_disputes_is_contested` asserts both the **structural** invariants (2 supports, 1 dispute, contested) and the exact literature-only magnitude (`"supported"`). If the engine returns a different value, investigate the reducer or policy change rather than weakening this assertion. Literature-only support cannot be `"well_supported"` (no `direct_test`).
- If `materialize_graph(strict=False)` performs structural validation that rejects the hand-authored minimal entities (e.g. missing required frontmatter), add the minimal required fields the validator demands — do not weaken the validator. Run with `-x` and read the error; the proposition/paper frontmatter above mirrors `tests/test_belief_e2e.py` conventions but the validator is the source of truth.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence_materialize.py -k e2e -q`
Expected: FAIL — `support_units == 0` (pass not wired) for the contested test; the stale test fails because no exception is raised.

- [ ] **Step 3: Wire the pass into `_derive_phase`**

In `science/src/science_tool/graph/materialize.py`, inside `_derive_phase`, insert **between** the `emit_source_snapshots` block and the `_derive_bears_on_layer(...)` call:

```python
    if source_snapshots is not None:
        emit_source_snapshots(dataset, source_snapshots)

    # Phase 4d (Half A): derive virtual literature evidence-lines from promoted
    # statement annotations BEFORE bears_on derivation, so the virtual cito edges
    # enter the bears_on closure (not only collect_evidence_units). Function-scoped
    # import keeps graph/ free of a module-level annotation dependency (layering).
    from science_tool.annotation.cross_paper_evidence import (
        derive_literature_evidence,
        proposition_source_refs_map,
    )

    derive_literature_evidence(
        dataset,
        Path(sources.project_root),
        proposition_source_refs_map(sources.entities),
    )

    _derive_bears_on_layer(
        dataset,
        kind_class=emit.kind_class,
        pre_registration_targets=emit.pre_registration_targets,
        eligible_code_files=_eligible_code_files(sources),
    )
```

(`Path` is already imported in materialize.py; confirm with `grep -n "^from pathlib" science/src/science_tool/graph/materialize.py`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence_materialize.py -q`
Expected: PASS. Then pin the exact magnitude per the note and re-run.

- [ ] **Step 5: Run the full belief/materialize regression to confirm behavior-neutral**

Run: `cd science && uv run --frozen pytest tests/ -k "belief or materialize or grounding or freshness" -q`
Expected: PASS — the new pass derives zero lines on existing corpora (no promoted-with-stance annotations), so no prior test changes.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_cross_paper_evidence_materialize.py
git commit -m "feat(4d): derive cross-paper evidence in materialize before bears_on"
```

---

## Task 5: Read-only `cross-paper-evidence` diagnostic command

**Files:**
- Modify: `science/src/science_tool/annotation/cross_paper_evidence.py` (add `build_cross_paper_evidence_report`)
- Modify: `science/src/science_tool/annotation/cli.py` (add the command)
- Test: `science/tests/test_cross_paper_evidence_cli.py`

**Interfaces:**
- Produces:
  - `proposition_source_refs_map(entities) -> dict[str, frozenset[str]]` — shared by **both** the materialize pass (Task 4 passes `sources.entities`) and the report (passes `load_project_sources(root).entities`), so the two paths never diverge on proposition owners.
  - `load_proposition_source_refs(project_root: Path) -> dict[str, frozenset[str]]` — report-mode build via `load_project_sources(project_root).entities` → `proposition_source_refs_map`.
  - `build_cross_paper_evidence_report(project_root: Path, *, proposition_ref: str | None) -> dict` — scanner-only (never raises); JSON-serializable. The per-`--source` payload includes unit rows with `paper`, `stance`, `edge`, `role`, `strength`, and `independence_group`, plus a `"belief"` block (`belief_magnitude`, `contested`, `contested_groups`, `support_units`, `dispute_units`) computed by emitting the proposition's derived units into an in-memory graph and running `collect_evidence_units` → `aggregate_belief`.
  - CLI: `science annotate cross-paper-evidence [--source proposition:<slug>] [--root PATH] [--format table|json]`.

- [ ] **Step 1: Write the failing test**

Create `science/tests/test_cross_paper_evidence_cli.py`:

```python
import json

from click.testing import CliRunner

from science_tool.annotation import io as anno_io
from science_tool.annotation.cli import annotate_group
from tests.test_cross_paper_evidence_materialize import (  # reuse the scaffold helpers
    _ann_ref, _manifest, _paper_with_promoted, _promoted_ann, _proposition_entity,
)


def _scaffold(root):
    _manifest(root)
    _proposition_entity(
        root,
        "claim",
        ["paper:A2020", "paper:B2021", _ann_ref("A2020"), _ann_ref("B2021")],
    )
    _paper_with_promoted(root, "A2020", stance="asserted")
    _paper_with_promoted(root, "B2021", stance="negated")


def test_cli_project_wide_json_lists_assertions(tmp_path):
    _scaffold(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["faults"] == []
    # one proposition with 1 supporting + 1 disputing paper
    props = {p["proposition"]: p for p in payload["propositions"]}
    assert props["proposition:claim"]["supporting_papers"] == 1
    assert props["proposition:claim"]["disputing_papers"] == 1


def test_cli_project_wide_counts_same_paper_support_stances_once(tmp_path):
    _manifest(tmp_path)
    _proposition_entity(
        tmp_path,
        "claim",
        [
            "paper:A2020",
            _ann_ref("A2020"),
            "annotation:entities/papers/A2020.source#A2020-2",
        ],
    )
    _paper_with_promoted(tmp_path, "A2020", stance="asserted")
    md = tmp_path / "entities" / "papers" / "A2020.source.md"
    anno_io.write_sidecar(
        anno_io.sidecar_for_markdown(md),
        anno_io.Sidecar(
            annotations=(
                _promoted_ann("A2020-1", stance="asserted"),
                _promoted_ann("A2020-2", stance="hypothesized"),
            )
        ),
    )

    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    props = {p["proposition"]: p for p in payload["propositions"]}
    # Two support stances from one paper are two assertion units, but one supporting paper.
    assert props["proposition:claim"]["supporting_papers"] == 1
    assert props["proposition:claim"]["disputing_papers"] == 0


def test_cli_single_ref_json_lists_units(tmp_path):
    _scaffold(tmp_path)
    result = CliRunner().invoke(
        annotate_group,
        [
            "cross-paper-evidence",
            "--source",
            "proposition:claim",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    units = {(u["paper"], u["stance"]) for u in payload["units"]}
    assert units == {("paper:A2020", "asserted"), ("paper:B2021", "negated")}
    by_stance = {u["stance"]: u for u in payload["units"]}
    assert by_stance["asserted"]["role"] == "proxy_support"
    assert by_stance["asserted"]["strength"] == "moderate"
    assert by_stance["asserted"]["independence_group"] == "literature-paper:A2020"
    assert by_stance["negated"]["role"] == "proxy_support"
    assert by_stance["negated"]["strength"] == "moderate"
    assert by_stance["negated"]["independence_group"] == "literature-paper:B2021"
    # different-paper support + dispute -> contested, but NOT a shared-group contested_group
    assert payload["belief"]["contested"] is True
    assert payload["belief"]["contested_groups"] == []
    assert payload["belief"]["support_units"] == 1
    assert payload["belief"]["dispute_units"] == 1
    assert payload["belief"]["belief_magnitude"] == "fragile"


def test_cli_reports_faults_without_raising(tmp_path):
    _manifest(tmp_path)
    _proposition_entity(tmp_path, "claim", ["paper:A2020"])
    _paper_with_promoted(tmp_path, "A2020", stance="asserted", slug="ghost")  # stale target
    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output  # report mode never raises
    payload = json.loads(result.output)
    assert [f["reason"] for f in payload["faults"]] == ["stale-proposition"]


def test_cli_table_format_runs(tmp_path):
    _scaffold(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "proposition:claim" in result.output


def test_cli_rejects_non_proposition_source(tmp_path):
    _manifest(tmp_path)
    result = CliRunner().invoke(
        annotate_group, ["cross-paper-evidence", "--source", "question:q", "--root", str(tmp_path)]
    )
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence_cli.py -q`
Expected: FAIL — no such command `cross-paper-evidence`.

- [ ] **Step 3a: Add the report builder**

Append to `science/src/science_tool/annotation/cross_paper_evidence.py`:

```python
# proposition_source_refs_map(...) is defined in Task 3 (with derive_literature_evidence);
# do NOT redefine it here — just import/use it.


def load_proposition_source_refs(project_root: Path) -> dict[str, frozenset[str]]:
    """Report-mode build via the SAME loader materialize uses (load_project_sources)."""
    from science_tool.graph.sources import load_project_sources

    return proposition_source_refs_map(load_project_sources(project_root).entities)


def _belief_for_proposition(collapsed: list[LiteratureAssertion], proposition_ref: str) -> dict:
    """Belief verdict from the proposition's derived literature units alone.

    Emits the virtual lines into an in-memory graph and runs the SAME belief path, so
    the diagnostic reports magnitude / contested / contested_group without depending on
    a built `graph.trig`. (Reflects cross-paper literature evidence only — authored
    evidence-lines are out of this diagnostic's scope.)
    """
    from science_tool.graph.belief import aggregate_belief, collect_evidence_units

    ref_units = [a for a in collapsed if a.proposition_ref == proposition_ref]
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    provenance = ds.graph(PROJECT_NS["graph/provenance"])
    emit_literature_evidence(knowledge, provenance, ref_units)
    belief = aggregate_belief(
        collect_evidence_units(knowledge, provenance, [entity_uri_for_ref(proposition_ref)])
    )
    return {
        "belief_magnitude": belief.magnitude.value,
        "contested": belief.contested,
        "contested_groups": sorted(belief.contested_groups),
        "support_units": len(belief.support_units),
        "dispute_units": len(belief.dispute_units),
    }


def build_cross_paper_evidence_report(
    project_root: Path, *, proposition_ref: str | None = None
) -> dict:
    """Scanner-only diagnostic payload (never raises). JSON-serializable."""
    refs = load_proposition_source_refs(project_root)
    assertions, faults = scan_literature_assertions(project_root, refs)
    collapsed = collapse_assertions(assertions)
    fault_rows = [
        {"sidecar": f.sidecar, "annotation": f.annotation_id, "reason": f.reason, "detail": f.detail}
        for f in sorted(faults, key=lambda x: (x.sidecar, x.annotation_id, x.reason))
    ]

    if proposition_ref is not None:
        units = [
            {
                "paper": a.paper_ref,
                "stance": a.stance,
                "edge": STANCE_EMIT[a.stance][0],
                "role": STANCE_EMIT[a.stance][1],
                "strength": STANCE_EMIT[a.stance][2],
                "independence_group": f"literature-{a.paper_ref}",
            }
            for a in collapsed
            if a.proposition_ref == proposition_ref
        ]
        units.sort(key=lambda u: (u["paper"], u["stance"]))
        return {
            "proposition": proposition_ref,
            "units": units,
            "belief": _belief_for_proposition(collapsed, proposition_ref),
            "faults": fault_rows,
        }

    by_prop: dict[str, dict[str, int]] = {}
    counted: set[tuple[str, str, str]] = set()
    for a in collapsed:
        edge = STANCE_EMIT[a.stance][0]
        count_key = (a.proposition_ref, a.paper_ref, edge)
        if count_key in counted:
            continue
        counted.add(count_key)
        bucket = by_prop.setdefault(
            a.proposition_ref, {"supporting_papers": 0, "disputing_papers": 0}
        )
        bucket["supporting_papers" if edge == "supports" else "disputing_papers"] += 1
    propositions = [{"proposition": ref, **counts} for ref, counts in sorted(by_prop.items())]
    return {"propositions": propositions, "faults": fault_rows}
```

- [ ] **Step 3b: Add the CLI command**

In `science/src/science_tool/annotation/cli.py`, add next to `ground_prose_decomposition_cmd` (the import for the report builder goes at the top with the other `from science_tool.annotation...` imports, or inline in the function to avoid an import cycle — match the file's existing convention):

```python
@annotate_group.command("cross-paper-evidence")
@click.option("--source", "source_ref", default=None, help="proposition:<slug> to inspect; omit for project-wide")
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def cross_paper_evidence_cmd(source_ref: str | None, root: Path | None, fmt: str) -> None:
    """Diagnose derived cross-paper literature evidence (read-only; reports faults)."""
    from science_tool.annotation.cross_paper_evidence import build_cross_paper_evidence_report

    if source_ref is not None and not source_ref.startswith("proposition:"):
        raise click.ClickException("--source must use proposition:<slug>")

    project_root = (root or Path.cwd()).resolve()
    payload = build_cross_paper_evidence_report(project_root, proposition_ref=source_ref)

    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    if source_ref is not None:
        b = payload["belief"]
        click.echo(
            f"cross-paper evidence for {source_ref}: {len(payload['units'])} unit(s); "
            f"belief={b['belief_magnitude']} contested={b['contested']} "
            f"contested_groups={len(b['contested_groups'])}"
        )
        for u in payload["units"]:
            click.echo(
                f"  {u['edge']:8s} {u['paper']} "
                f"({u['stance']}; {u['role']}/{u['strength']})"
            )
    else:
        for p in payload["propositions"]:
            click.echo(
                f"{p['proposition']}: +{p['supporting_papers']} / -{p['disputing_papers']} paper(s)"
            )
    if payload["faults"]:
        click.echo(f"FAULTS ({len(payload['faults'])}):")
        for f in payload["faults"]:
            click.echo(f"  {f['sidecar']} [{f['annotation']}] {f['reason']}: {f['detail']}")
```

(`Path` and `json` and `click` are already imported in `annotation/cli.py`; confirm with `grep -nE "^import json|^from pathlib|^import click" science/src/science_tool/annotation/cli.py`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence_cli.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Confirm the command is registered**

Run: `cd science && uv run --frozen python -c "from science_tool.cli import main; main(['annotate', 'cross-paper-evidence', '--help'], standalone_mode=False)"`
Expected: prints the command help, exit 0.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/cross_paper_evidence.py science/src/science_tool/annotation/cli.py science/tests/test_cross_paper_evidence_cli.py
git commit -m "feat(4d): cross-paper-evidence read-only diagnostic command"
```

---

## Task 6: Full-suite regression + ruff

**Files:** none (verification only)

- [ ] **Step 1: Run the new tests together**

Run: `cd science && uv run --frozen pytest tests/test_cross_paper_evidence.py tests/test_cross_paper_evidence_materialize.py tests/test_cross_paper_evidence_cli.py -q`
Expected: PASS (all).

- [ ] **Step 2: Run the full suite**

Run: `cd science && uv run --frozen pytest -q`
Expected: PASS with zero failures (behavior-neutral on existing corpora). If any pre-existing failures appear unrelated to 4d, capture them and report — do not "fix" by weakening 4d.

- [ ] **Step 3: Lint the touched files**

Run: `cd science && uv run --frozen ruff check src/science_tool/annotation/cross_paper_evidence.py src/science_tool/annotation/cli.py src/science_tool/graph/materialize.py tests/test_cross_paper_evidence.py tests/test_cross_paper_evidence_materialize.py tests/test_cross_paper_evidence_cli.py`
Expected: clean (no errors).

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -A && git commit -m "chore(4d): ruff clean" || echo "nothing to commit"
```

---

## Notes on belief semantics (for reviewers)

- Literature units carry `proxy_support`/`background_constraint`, never `direct_test`, so `aggregate_belief` cannot reach `well_supported` (the direct-test gate). Cross-paper corroboration lifts `speculative/fragile → supported` only.
- **Different-paper** support+dispute → `contested=True` (a surviving dispute unit), but **not** a `contested_group` (different papers → different `independence_group`s).
- **Same-paper** mixed stance → both a support and a dispute unit share `independence_group=literature-paper:<citekey>` → the reducer records a real `contested_group` and does not count the paper as two corroborations (Task 1 `collapse_assertions` keeps both stances; the same group token does the rest).
