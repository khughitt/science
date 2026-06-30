# Cross-Paper Evidence Readiness and Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Phase 4d observable and safe on real projects before semantic reconciliation work begins.

**Architecture:** Keep Phase 4d Half A's belief semantics unchanged. Add root-scoped scanning, explicit empty-state diagnostics, and health/summary surfaces around the existing derived evidence machinery so real-corpus adoption has clear feedback.

**Tech Stack:** Python 3.12+, Click, pytest, rdflib; existing `science_tool.annotation.cross_paper_evidence`, `science_tool.graph.sources`, and validation/health modules.

---

## Context

Phase 4d Half A shipped and full regression passed. The first real-corpus run against
`meta/` returned zero propositions, zero sidecars, zero derived units, and zero faults.
That is accurate for the current corpus. A second run from the package root exposed a
scope issue: `iter_sidecars(project_root)` recursively includes test fixtures when the
selected root is too broad.

This plan is deliberately not 4e. It does not add paraphrase/factorization
reconciliation, embedding dedup, citation-graph independence, or identification-strength
promotion. It makes the current derived evidence layer usable and diagnosable on real
projects.

Observation note: `docs/plans/2026-06-30-cross-paper-evidence-real-corpus-observation.md`.
Phase 4d Half A design: `docs/plans/2026-06-30-proposition-cross-paper-evidence-phase4d-design.md`.

## File Structure

- Modify `science/src/science_tool/annotation/cross_paper_evidence.py`
  - Add a production sidecar-root resolver.
  - Return explicit summary/empty-state fields in diagnostic reports.
- Modify `science/src/science_tool/annotation/cli.py`
  - Render empty states in table output.
  - Keep JSON stable and machine-readable.
- Modify `science/src/science_tool/graph/health.py`
  - Add a `cross_paper_evidence` health check to the existing `science health` registry.
  - Represent empty-state as informational health data and scanner faults as findings.
- Tests:
  - Extend `science/tests/test_cross_paper_evidence.py`.
  - Extend `science/tests/test_cross_paper_evidence_cli.py`.
  - Extend `science/tests/test_health.py`.

## Task 1: Scope Sidecar Scanning to Project Data Roots

**Problem:** `scan_literature_assertions(project_root, refs)` currently scans every
`.anno.trig` below `project_root`. If the root is a repository or package checkout, test
fixtures are treated as epistemic inputs.

**Desired behavior:** Cross-paper evidence scans only sidecars under project data roots
that can hold paper source annotations. At minimum, include `entities/**` under the
selected project root. Do not scan package `tests/**` merely because the CLI was invoked
from a broad checkout.

- [ ] **Step 1: Write a failing test**

Add to `science/tests/test_cross_paper_evidence.py`:

```python
def test_scan_ignores_sidecars_outside_project_entity_roots(tmp_path: Path):
    _write_sidecar_for_markdown(
        tmp_path,
        "tests/_fixtures/annotation/bad.md",
        [_ann("a-1", stance="asserted")],
    )
    _write_paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", stance="asserted")])
    refs = {"proposition:p": frozenset({"paper:Smith2020", _ANN_REF})}

    assertions, faults = scan_literature_assertions(tmp_path, refs)

    assert faults == []
    assert [(a.paper_ref, a.stance) for a in assertions] == [("paper:Smith2020", "asserted")]
```

Expected before implementation: the extra non-entity sidecar is scanned and returns an
`adapter-unresolvable` fault.

- [ ] **Step 2: Implement scoped sidecar iteration**

In `science/src/science_tool/annotation/cross_paper_evidence.py`, add a small helper:

```python
def _iter_project_annotation_sidecars(project_root: Path):
    entities_root = project_root / "entities"
    if entities_root.is_dir():
        yield from iter_sidecars(entities_root)
```

Then change `scan_literature_assertions` to iterate this helper instead of
`iter_sidecars(project_root)`.

If future project layouts need additional annotation roots, add them explicitly in this
helper with tests. Do not fall back to scanning the entire project root.

- [ ] **Step 3: Verify**

Run:

```bash
cd science
uv run --frozen pytest tests/test_cross_paper_evidence.py -q
uv run --frozen pytest tests/test_cross_paper_evidence_cli.py -q
```

- [ ] **Step 4: Commit**

```bash
git add science/src/science_tool/annotation/cross_paper_evidence.py science/tests/test_cross_paper_evidence.py
git commit -m "fix(4d): scope cross-paper sidecar scan to entity roots"
```

## Task 2: Make Empty States Explicit in the Diagnostic

**Problem:** On `meta/`, table output is empty. That is technically correct but not
actionable; users cannot distinguish "no propositions", "no sidecars", and "no derived
units". The current project-wide report also differs from the single-proposition report:
project-wide proposition rows only contain `proposition`, `supporting_papers`, and
`disputing_papers`; they do not contain `units` or `belief`.

**Desired behavior:** First define a stable project-wide report contract that carries the
data needed by CLI and health surfaces, then add summary counts. Table output prints a
short empty-state line when there is nothing to display.

- [ ] **Step 1: Write failing CLI tests for the project-wide contract**

Extend `science/tests/test_cross_paper_evidence_cli.py`:

```python
def test_cross_paper_evidence_json_includes_summary_for_empty_project(tmp_path: Path):
    _manifest(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"] == {
        "propositions": 0,
        "propositions_with_units": 0,
        "units": 0,
        "faults": 0,
        "faults_by_reason": {},
        "contested": 0,
    }


def test_cross_paper_evidence_table_reports_empty_project(tmp_path: Path):
    _manifest(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        ["cross-paper-evidence", "--root", str(tmp_path), "--format", "table"],
    )

    assert result.exit_code == 0, result.output
    assert "No proposition entities found." in result.output


def test_cross_paper_evidence_project_wide_rows_include_units_and_belief(tmp_path: Path):
    _scaffold(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    row = {p["proposition"]: p for p in payload["propositions"]}["proposition:claim"]
    assert row["unit_count"] == 2
    assert row["supporting_papers"] == 1
    assert row["disputing_papers"] == 1
    assert row["belief"]["contested"] is True
    assert payload["summary"]["propositions"] == 1
    assert payload["summary"]["propositions_with_units"] == 1
    assert payload["summary"]["units"] == 2
    assert payload["summary"]["contested"] == 1
```

Also update the existing project-wide JSON tests to tolerate the richer rows. Keep the
existing `supporting_papers` / `disputing_papers` assertions; they remain part of the
contract.

- [ ] **Step 2: Write the same-paper support-stances unit-count regression**

The existing project-wide report counts papers per edge, so one paper with both
`asserted` and `hypothesized` contributes one supporting paper but **two** collapsed
literature units. Pin that distinction:

```python
def test_cross_paper_evidence_summary_units_count_collapsed_assertions_not_edge_counts(tmp_path: Path):
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
        annotate_group,
        ["cross-paper-evidence", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    row = {p["proposition"]: p for p in payload["propositions"]}["proposition:claim"]
    assert row["supporting_papers"] == 1
    assert row["unit_count"] == 2
    assert payload["summary"]["units"] == 2
```

Use the existing `_manifest` helper in `science/tests/test_cross_paper_evidence_cli.py`.

- [ ] **Step 3: Add a project-wide report contract**

In `build_cross_paper_evidence_report`, keep the single-`proposition_ref` branch as-is.
For the project-wide branch, build rows for **every proposition ref in `refs`**, not only
propositions that already have literature units. Each row should have:

```python
{
    "proposition": ref,
    "unit_count": len(ref_units),
    "supporting_papers": len(supporting_papers),
    "disputing_papers": len(disputing_papers),
    "belief": _belief_for_proposition(collapsed, ref),
}
```

Where:

- `ref_units = [a for a in collapsed if a.proposition_ref == ref]`
- `supporting_papers` is the set of `paper_ref` values from `ref_units` whose emitted
  edge is `"supports"`.
- `disputing_papers` is the set of `paper_ref` values from `ref_units` whose emitted
  edge is `"disputes"`.

The project-wide `contested` count must come from
`row["belief"]["contested"]`, not from a hand-rolled support/dispute rule. That reuses
the reducer and keeps health semantics aligned with belief.

- [ ] **Step 4: Add summary fields**

In `build_cross_paper_evidence_report`, compute summary from the real data shapes:

```python
from collections import Counter

faults_by_reason = Counter(row["reason"] for row in fault_rows)
summary = {
    "propositions": len(proposition_reports),
    "propositions_with_units": sum(1 for row in proposition_reports if row["unit_count"] > 0),
    "units": len(collapsed),
    "faults": len(faults),
    "faults_by_reason": dict(sorted(faults_by_reason.items())),
    "contested": sum(1 for row in proposition_reports if row["belief"]["contested"]),
}
```

Return `{"summary": summary, "faults": ..., "propositions": ...}`.

- [ ] **Step 5: Render table empty states**

In `cross_paper_evidence_cmd`, project-wide table mode should print an empty-state line
before the existing fault block when there are no rows or units:

```text
No proposition entities found.
No derived cross-paper literature evidence found.
```

Use the first when `summary["propositions"] == 0`; use the second when propositions
exist but `summary["units"] == 0`. Faults may coexist with either empty state; keep the
existing `FAULTS (...)` block after the empty-state line so corruption remains visible.

- [ ] **Step 6: Verify**

Run:

```bash
cd science
uv run --frozen pytest tests/test_cross_paper_evidence_cli.py -q
```

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/annotation/cross_paper_evidence.py science/src/science_tool/annotation/cli.py science/tests/test_cross_paper_evidence_cli.py
git commit -m "feat(4d): summarize cross-paper evidence diagnostics"
```

## Task 3: Add a Real-Corpus Smoke Fixture

**Problem:** The live corpus currently has no proposition entities or sidecars, so it
cannot exercise the real Phase 4d path.

**Desired behavior:** Add a small fixture project that resembles the live project layout:
`science.yaml`, `entities/papers/*.source.md`, `entities/propositions/*.md`, and paper
sidecars with promoted proposition annotations. This fixture should exercise two
supporting papers and one disputing paper.

- [ ] **Step 1: Add fixture-oriented tests**

Extend `science/tests/test_cross_paper_evidence_materialize.py` with a test that builds
a project containing:

- `paper:Alpha2026` asserted `proposition:p`
- `paper:Beta2026` asserted `proposition:p`
- `paper:Gamma2026` negated `proposition:p`

Assert that:

- the diagnostic summary reports one proposition and three units,
- the belief result is contested,
- no `well_supported` state is reached from literature-only evidence.

- [ ] **Step 2: Reuse existing fixture builders**

Prefer the existing local helpers in `test_cross_paper_evidence_materialize.py`; do not
introduce a new fixture framework.

- [ ] **Step 3: Verify**

Run:

```bash
cd science
uv run --frozen pytest tests/test_cross_paper_evidence_materialize.py tests/test_cross_paper_evidence_cli.py -q
```

- [ ] **Step 4: Commit**

```bash
git add science/tests/test_cross_paper_evidence_materialize.py science/tests/test_cross_paper_evidence_cli.py
git commit -m "test(4d): add corpus-shaped cross-paper evidence smoke fixture"
```

## Task 4: Wire a `science health` Surface

**Problem:** The diagnostic is currently opt-in. Real projects need a project-wide
signal that reports stale `promoted_to`, ownership mismatches, and the amount of derived
literature evidence.

**Desired behavior:** Add a read-only health/check surface that reports:

- cross-paper literature evidence unit count,
- propositions with literature evidence,
- contested propositions,
- scanner fault count by reason,
- empty-state classification.

- [ ] **Step 1: Locate the right surface**

Use the existing project health aggregator:

- `science/src/science_tool/graph/health.py`
- `science/tests/test_health.py`

- [ ] **Step 2: Write failing tests for that surface**

Add tests to `science/tests/test_health.py`. The tests must assert:

- an empty project reports an empty-state message, not a failure,
- stale `promoted_to` or ownership mismatch is a failure/degraded signal,
- a project with two supporting papers reports non-zero derived unit counts.

- [ ] **Step 3: Implement through `build_cross_paper_evidence_report`**

The health/validation layer should call the same report builder used by the CLI. Do not
duplicate scan/collapse/belief logic. Use `report["summary"]["faults_by_reason"]` for
reason-level fault counts and `report["summary"]["contested"]` for contested proposition
counts.

- [ ] **Step 4: Verify**

Run the focused health/validation tests and Phase 4d tests:

```bash
cd science
uv run --frozen pytest tests/test_cross_paper_evidence.py tests/test_cross_paper_evidence_cli.py tests/test_cross_paper_evidence_materialize.py tests/test_health.py -k "cross_paper_evidence or HealthCLI" -q
```

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/health.py science/tests/test_health.py
git commit -m "feat(4d): surface cross-paper evidence health"
```

## Task 5: Re-run the Real-Corpus Diagnostic and Update the Observation Note

- [ ] **Step 1: Run on `meta/`**

```bash
cd science
uv run --frozen science annotate cross-paper-evidence --root ../meta --format json > /tmp/phase4d-cross-paper-evidence.json
uv run --frozen science annotate cross-paper-evidence --root ../meta --format table
```

- [ ] **Step 2: Confirm expected empty state**

Expected until live annotation sidecars/proposition entities exist:

- JSON `summary.propositions == 0`
- JSON `summary.units == 0`
- JSON `summary.faults == 0`
- table says `No proposition entities found.`

- [ ] **Step 3: Update observation note**

Update `docs/plans/2026-06-30-cross-paper-evidence-real-corpus-observation.md` with
the post-hardening output and any health-surface result.

- [ ] **Step 4: Final verification**

Run:

```bash
cd science
uv run --frozen pytest tests/test_cross_paper_evidence.py tests/test_cross_paper_evidence_cli.py tests/test_cross_paper_evidence_materialize.py -q
```

If the health/validation surface is wired, also run its focused test file.

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-06-30-cross-paper-evidence-real-corpus-observation.md
git commit -m "docs(4d): record cross-paper evidence corpus observation"
```

## Non-Goals

- Do not change Phase 4d belief semantics.
- Do not persist virtual evidence-line files.
- Do not add embedding/paraphrase dedup.
- Do not infer paper independence from citation graphs.
- Do not reconcile factorization differences across papers.

## Open Follow-Up After This Plan

Once the readiness/surface work is complete, the next substantive semantic phase should
be factorization reconciliation / 4e: reconcile paraphrased or differently factored
claims across papers before promotion, then revisit independence modeling.
