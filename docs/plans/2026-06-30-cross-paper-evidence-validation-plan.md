# Cross-Paper Evidence Validation Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `science validate` from reporting `evidence.unstanced` for clean Phase 4d virtual literature evidence while preserving warnings for corrupt or genuinely unstanced refs.

**Architecture:** Extend the Phase 4d scanner result with the full annotation ownership ref it already computes, then let `check_evidence_lines_unstanced` treat clean scanned literature assertions as coverage alongside authored evidence-line frontmatter. Scanner faults and silent non-assertion skips grant no coverage.

**Tech Stack:** Python 3.13 in this repo, pytest, rdflib, `science_tool.annotation.cross_paper_evidence`, `science_tool.validate.checks.evidence_lines`, `ValidateContext` caches.

---

## Context

Design spec: `docs/plans/2026-06-30-cross-paper-evidence-validation-design.md`.

The current `evidence.unstanced` check lives in
`science/src/science_tool/validate/checks/evidence_lines.py`. It builds coverage from
authored evidence-line markdown only:

```python
covered: set[tuple[str, str]] = set()
for _path, fm in lines:
    target = fm.get("target", "")
    source = fm.get("source", "")
    if target and source:
        covered.add((str(target), str(source)))
```

Phase 4d clean literature evidence comes from sidecars, not authored evidence-line
files. The scanner already validates ownership against both:

```text
paper:<citekey>
annotation:<sidecar relpath without .md>#<annotation-id>
```

The scanner currently discards the full annotation ref after using it for ownership.

## File Structure

- Modify `science/src/science_tool/annotation/cross_paper_evidence.py`
  - Append `annotation_ref: str` to `LiteratureAssertion`.
  - Pass the already-computed `ann_ref` into the scanner's `LiteratureAssertion`.
- Modify `science/tests/test_cross_paper_evidence.py`
  - Update positional fixture constructors.
  - Add a scanner assertion that exposes `annotation_ref`.
- Modify `science/tests/test_cross_paper_evidence_materialize.py`
  - Update fixture constructors.
- Modify `science/src/science_tool/validate/checks/evidence_lines.py`
  - Add a small derived-literature coverage helper.
  - Merge that coverage into `check_evidence_lines_unstanced`.
- Modify `science/tests/validate/test_checks_evidence_lines.py`
  - Add 4d validation coverage and fail-closed tests.

## Task 1: Expose `annotation_ref` on `LiteratureAssertion`

**Files:**
- Modify: `science/src/science_tool/annotation/cross_paper_evidence.py`
- Modify: `science/tests/test_cross_paper_evidence.py`
- Modify: `science/tests/test_cross_paper_evidence_materialize.py`

- [ ] **Step 1: Write the failing scanner contract assertion**

In `science/tests/test_cross_paper_evidence.py`, extend
`test_scan_happy_path_collects_active_proposition_assertions`:

```python
    assert a.annotation_ref == _ANN_REF
```

Place it after the existing tuple assertion:

```python
    assert (a.proposition_ref, a.paper_ref, a.stance) == (
        "proposition:p",
        "paper:Smith2020",
        "asserted",
    )
    assert a.annotation_ref == _ANN_REF
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/test_cross_paper_evidence.py::test_scan_happy_path_collects_active_proposition_assertions -q
```

Expected: FAIL with `AttributeError: 'LiteratureAssertion' object has no attribute 'annotation_ref'`.

- [ ] **Step 3: Add the dataclass field**

In `science/src/science_tool/annotation/cross_paper_evidence.py`, change
`LiteratureAssertion` to append the new field after `sidecar`:

```python
@dataclass(frozen=True)
class LiteratureAssertion:
    proposition_ref: str
    paper_ref: str
    stance: str
    annotation_id: str
    sidecar: str
    annotation_ref: str
```

Do not insert `annotation_ref` before `sidecar`; appending minimizes positional churn and
keeps the old `sidecar` argument from sliding into the new field.

- [ ] **Step 4: Pass the scanner-owned annotation ref**

In `scan_literature_assertions`, replace the positional append:

```python
assertions.append(
    LiteratureAssertion(ann.promoted_to, paper_ref, stance, ann.id, sidecar_ref)
)
```

with keyword arguments:

```python
assertions.append(
    LiteratureAssertion(
        proposition_ref=ann.promoted_to,
        paper_ref=paper_ref,
        stance=stance,
        annotation_id=ann.id,
        sidecar=sidecar_ref,
        annotation_ref=ann_ref,
    )
)
```

- [ ] **Step 5: Update materialize-test fixture constructors**

In `science/tests/test_cross_paper_evidence_materialize.py`, update `_assertion`:

```python
def _assertion(stance: str) -> LiteratureAssertion:
    return LiteratureAssertion(
        proposition_ref="proposition:p",
        paper_ref="paper:Smith2020",
        stance=stance,
        annotation_id="a-1",
        sidecar="entities/papers/Smith2020.source.anno.trig",
        annotation_ref=_ANN_REF,
    )
```

In `test_same_paper_mixed_stance_yields_contested_group`, replace the two positional
constructors with:

```python
support = LiteratureAssertion(
    proposition_ref="proposition:p",
    paper_ref="paper:A",
    stance="asserted",
    annotation_id="ann-1",
    sidecar="s",
    annotation_ref="annotation:entities/papers/A.source#ann-1",
)
dispute = LiteratureAssertion(
    proposition_ref="proposition:p",
    paper_ref="paper:A",
    stance="negated",
    annotation_id="ann-2",
    sidecar="s",
    annotation_ref="annotation:entities/papers/A.source#ann-2",
)
```

- [ ] **Step 6: Add a local constructor helper in `test_cross_paper_evidence.py`**

In `science/tests/test_cross_paper_evidence.py`, after `test_stance_emit_table_uses_real_enum_values`,
add:

```python
def _lit_assertion(
    *,
    proposition_ref: str = "proposition:p",
    paper_ref: str = "paper:A",
    stance: str = "asserted",
    annotation_id: str = "ann-1",
    sidecar: str = "A.anno.trig",
) -> LiteratureAssertion:
    citekey = paper_ref.split(":", 1)[1]
    return LiteratureAssertion(
        proposition_ref=proposition_ref,
        paper_ref=paper_ref,
        stance=stance,
        annotation_id=annotation_id,
        sidecar=sidecar,
        annotation_ref=f"annotation:entities/papers/{citekey}.source#{annotation_id}",
    )
```

Then update the collapse tests:

```python
def test_collapse_dedupes_same_proposition_paper_stance_keeps_one():
    a1 = _lit_assertion(annotation_id="ann-1")
    a2 = _lit_assertion(annotation_id="ann-2")
    out = collapse_assertions([a1, a2])
    assert len(out) == 1
    assert out[0].proposition_ref == "proposition:p"


def test_collapse_keeps_both_stances_for_same_paper():
    sup = _lit_assertion(annotation_id="ann-1", stance="asserted")
    dis = _lit_assertion(annotation_id="ann-2", stance="negated")
    out = collapse_assertions([sup, dis])
    keys = {(x.paper_ref, x.stance) for x in out}
    assert keys == {("paper:A", "asserted"), ("paper:A", "negated")}


def test_collapse_is_order_independent_and_deterministic():
    a1 = _lit_assertion(annotation_id="ann-9")
    a2 = _lit_assertion(annotation_id="ann-1")
    assert collapse_assertions([a1, a2]) == collapse_assertions([a2, a1])
    assert collapse_assertions([a1, a2])[0].annotation_id == "ann-1"


def test_collapse_uses_sidecar_as_final_deterministic_tiebreaker():
    a1 = _lit_assertion(annotation_id="ann-1", sidecar="B.anno.trig")
    a2 = _lit_assertion(annotation_id="ann-1", sidecar="A.anno.trig")
    assert collapse_assertions([a1, a2]) == collapse_assertions([a2, a1])
    assert collapse_assertions([a1, a2])[0].sidecar == "A.anno.trig"
```

- [ ] **Step 7: Run focused scanner/materialize tests and verify GREEN**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/test_cross_paper_evidence.py tests/test_cross_paper_evidence_materialize.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
rtk git add science/src/science_tool/annotation/cross_paper_evidence.py science/tests/test_cross_paper_evidence.py science/tests/test_cross_paper_evidence_materialize.py
rtk git commit -m "feat(4d): expose annotation refs on literature assertions"
```

## Task 2: Add 4d-Derived Coverage to `evidence.unstanced`

**Files:**
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py`
- Modify: `science/tests/validate/test_checks_evidence_lines.py`

- [ ] **Step 1: Add validation-test imports**

At the top of `science/tests/validate/test_checks_evidence_lines.py`, change the imports
to include JSON, datetimes, and annotation helpers:

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from rdflib import RDF, Dataset, Literal, URIRef
from rdflib.namespace import PROV

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.graph.io import CITO_NS, SCI_NS
from science_tool.graph.store import PROJECT_NS, _graph_uri
from science_tool.validate import Severity, ValidateContext
```

- [ ] **Step 2: Add 4d validation fixtures**

Below `_write`, add:

```python
_CREATED = datetime(2026, 6, 30, tzinfo=timezone.utc)
_ANN_REF = "annotation:entities/papers/Smith2020.source#a-1"


def _write_proposition_with_refs(root: Path, refs: list[str]) -> Path:
    refs_yaml = "\n".join(f"  - {ref}" for ref in refs)
    return _write(
        root,
        "entities/propositions/p1.md",
        "\n".join(
            [
                "---",
                "type: proposition",
                "title: P1",
                "status: active",
                "created: '2026-06-30'",
                "updated: '2026-06-30'",
                "id: proposition:p1",
                "ontology_terms: []",
                "source_refs:",
                refs_yaml,
                "---",
                "",
                "Claim.",
                "",
            ]
        ),
    )


def _statement_annotation(
    annotation_id: str = "a-1",
    *,
    stance: str = "asserted",
    promoted_to: str | None = "proposition:p1",
    status: Status = Status.OPEN,
) -> Annotation:
    non_open = status is not Status.OPEN
    return Annotation(
        id=annotation_id,
        target=SpecificResource(
            source="Smith2020.source.md",
            selector=TextQuoteSelector(exact=annotation_id, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value=json.dumps({"section": "abstract", "stance": stance}), format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="proposition",
        source="manual:validation-test",
        status=status,
        creator="curator",
        created=_CREATED,
        modified=_CREATED if non_open else None,
        modified_by="curator" if non_open else None,
        promoted_to=promoted_to,
    )


def _write_paper_source_sidecar(root: Path, annotations: list[Annotation]) -> None:
    md = root / "entities" / "papers" / "Smith2020.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Body.\n", encoding="utf-8")
    anno_io.write_sidecar(
        anno_io.sidecar_for_markdown(md),
        anno_io.Sidecar(annotations=tuple(annotations)),
    )
```

- [ ] **Step 3: Add failing 4d coverage tests**

Under the "Rule: evidence.unstanced — sub-case (b)" section, add:

```python
def test_unstanced_valid_4d_literature_refs_are_counted_as_coverage(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write_proposition_with_refs(tmp_path, ["paper:Smith2020", _ANN_REF])
    _write_paper_source_sidecar(tmp_path, [_statement_annotation("a-1", stance="asserted")])

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert [r for r in results if r.rule == "evidence.unstanced"] == []


def test_unstanced_4d_ownership_mismatch_does_not_cover_paper_ref(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    prop = _write_proposition_with_refs(tmp_path, ["paper:Smith2020"])
    _write_paper_source_sidecar(tmp_path, [_statement_annotation("a-1", stance="asserted")])

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))
    unstanced = [r for r in results if r.rule == "evidence.unstanced"]

    assert len(unstanced) == 1
    assert unstanced[0].path == prop
    assert "paper:Smith2020" in unstanced[0].message


def test_unstanced_4d_faulted_assertion_does_not_cover_refs(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write_proposition_with_refs(tmp_path, ["paper:Smith2020", _ANN_REF])
    _write_paper_source_sidecar(tmp_path, [_statement_annotation("a-1", stance="maybe")])

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    messages = [r.message for r in results if r.rule == "evidence.unstanced"]
    assert len(messages) == 2
    assert any("paper:Smith2020" in message for message in messages)
    assert any(_ANN_REF in message for message in messages)


@pytest.mark.parametrize(
    ("annotation", "case_id"),
    [
        (_statement_annotation("a-1", stance="open"), "open-stance"),
        (_statement_annotation("a-1", promoted_to=None), "unpromoted"),
        (_statement_annotation("a-1", status=Status.FIXED), "inactive"),
    ],
)
def test_unstanced_4d_silent_skips_remain_unstanced(
    tmp_path: Path,
    annotation: Annotation,
    case_id: str,
) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write_proposition_with_refs(tmp_path, ["paper:Smith2020", _ANN_REF])
    _write_paper_source_sidecar(tmp_path, [annotation])

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    messages = [r.message for r in results if r.rule == "evidence.unstanced"]
    assert len(messages) == 2, case_id
    assert any("paper:Smith2020" in message for message in messages)
    assert any(_ANN_REF in message for message in messages)
```

These tests also cover canonical ID-form consistency: the proposition frontmatter uses
`id: proposition:p1`, the annotation uses `promoted_to="proposition:p1"`, and derived
coverage only suppresses warnings if those forms match byte-for-byte.

- [ ] **Step 4: Run the new tests and verify RED**

Run:

```bash
cd science
rtk uv run --frozen pytest \
  tests/validate/test_checks_evidence_lines.py::test_unstanced_valid_4d_literature_refs_are_counted_as_coverage \
  tests/validate/test_checks_evidence_lines.py::test_unstanced_4d_ownership_mismatch_does_not_cover_paper_ref \
  tests/validate/test_checks_evidence_lines.py::test_unstanced_4d_faulted_assertion_does_not_cover_refs \
  tests/validate/test_checks_evidence_lines.py::test_unstanced_4d_silent_skips_remain_unstanced \
  -q
```

Expected: the first test FAILS because `paper:Smith2020` and `_ANN_REF` still warn.
The fail-closed tests may already pass before implementation; keep them because they
guard the boundary.

- [ ] **Step 5: Add derived-literature coverage helper**

In `science/src/science_tool/validate/checks/evidence_lines.py`, after `_ev_lines`, add:

```python
def _derived_literature_coverage(ctx: ValidateContext) -> set[tuple[str, str]]:
    """Return proposition source_refs covered by clean Phase 4d literature assertions."""
    entities_root = ctx.project_root / "entities"
    if not entities_root.is_dir() or not any(entities_root.rglob("*.anno.trig")):
        return set()

    from science_tool.annotation.cross_paper_evidence import (
        proposition_source_refs_map,
        scan_literature_assertions,
    )

    sources = ctx.project_sources(strict_core_schema=False, strict_identity=False)
    proposition_refs = proposition_source_refs_map(sources.entities)
    assertions, _faults = scan_literature_assertions(ctx.project_root, proposition_refs)

    covered: set[tuple[str, str]] = set()
    for assertion in assertions:
        covered.add((assertion.proposition_ref, assertion.paper_ref))
        covered.add((assertion.proposition_ref, assertion.annotation_ref))
    return covered
```

The early sidecar check avoids loading full project sources for projects that have no
annotation sidecars, preserving existing frontmatter-only behavior for ordinary
`evidence.unstanced` tests.

- [ ] **Step 6: Merge derived coverage into the existing check**

In `check_evidence_lines_unstanced`, after the authored `covered` set is built, add:

```python
    covered.update(_derived_literature_coverage(ctx))
```

The resulting block should be:

```python
    covered: set[tuple[str, str]] = set()
    for _path, fm in lines:
        target = fm.get("target", "")
        source = fm.get("source", "")
        if target and source:
            covered.add((str(target), str(source)))
    covered.update(_derived_literature_coverage(ctx))
```

- [ ] **Step 7: Run focused validation tests and verify GREEN**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -q
```

Expected: PASS.

- [ ] **Step 8: Run cross-paper evidence regression tests**

Run:

```bash
cd science
rtk uv run --frozen pytest tests/test_cross_paper_evidence.py tests/test_cross_paper_evidence_materialize.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```bash
rtk git add science/src/science_tool/validate/checks/evidence_lines.py science/tests/validate/test_checks_evidence_lines.py
rtk git commit -m "fix(4d): count virtual literature evidence in validation"
```

## Task 3: Real-Corpus Acceptance

**Files:**
- No source edits expected.

- [ ] **Step 1: Run cross-paper health on `meta`**

Run:

```bash
cd science
rtk uv run --frozen science health --project-root ../meta --check cross_paper_evidence --format json
```

Expected:

- `"status": "ok"`
- `"faults": 0`
- `"total_issues": 0`

The current smoke corpus reports `"contested": 1`; treat that as informational rather
than a hard gate, because the count can legitimately increase as more real-corpus 4d
smoke propositions are added.

- [ ] **Step 2: Run full meta validation**

Run:

```bash
cd science
rtk uv run --frozen science validate --project-root ../meta
```

Expected: exit code 0. Existing unrelated warnings are acceptable.

- [ ] **Step 3: Confirm the 4d smoke propositions no longer produce `evidence.unstanced`**

If the validation output is long, rerun it into a temporary file:

```bash
cd science
rtk uv run --frozen science validate --project-root ../meta > /tmp/phase4d-validation.out
```

Then run:

```bash
rtk rg "evidence\\.unstanced.*(bes-behaves-like-pooled-meta-analysis|conceptual-replication-evidence-can-be-aggregated-over-informative-hypotheses)" /tmp/phase4d-validation.out
```

Expected: no matches.

`rg` exits with status 1 when it finds no matches; in this step, no output and exit
code 1 is the expected result.

- [ ] **Step 4: Run the full targeted suite one more time**

Run:

```bash
cd science
rtk uv run --frozen pytest \
  tests/validate/test_checks_evidence_lines.py \
  tests/test_cross_paper_evidence.py \
  tests/test_cross_paper_evidence_materialize.py \
  -q
```

Expected: PASS.

- [ ] **Step 5: Final status check**

Run:

```bash
rtk git status --short
```

Expected: clean except for unrelated pre-existing untracked files in the main checkout,
if this command is run from the main checkout. In the implementation worktree itself,
the expected status is clean.
