# Cross-Paper Evidence Validation Integration — Design

**Date:** 2026-06-30
**Status:** Draft for review
**Kind:** Tool-facing validation improvement for Phase 4d Half A

---

## 1. Problem

Phase 4d Half A now derives virtual literature evidence from promoted paper
annotations. The cross-paper diagnostic and health surface correctly recognize those
derived units, and materialized graphs contain virtual `sci:EvidenceLine` nodes with
`cito:supports` / `cito:disputes` edges. But the generic validation check
`evidence.unstanced` still predates 4d.

`science validate` currently checks proposition `source_refs` against authored
evidence-line markdown only:

- `entities/evidence-lines/*.md` frontmatter provides `(target, source)` coverage.
- proposition `source_refs` that lack such authored coverage emit
  `evidence.unstanced`.

For 4d propositions, the source refs are intentionally paper and annotation refs:

- `paper:<citekey>`
- `annotation:entities/papers/<citekey>.source#<annotation-id>`

Those refs are epistemically covered by derived virtual literature evidence, not by
authored evidence-line files. As a result, valid 4d smoke propositions produce noisy
`evidence.unstanced` warnings even though cross-paper evidence health is clean.

## 2. Goal

Teach generic validation that clean Phase 4d literature assertions count as source-ref
coverage for the proposition they support or dispute.

Success criteria:

- Valid 4d paper and annotation refs no longer emit `evidence.unstanced`.
- Invalid or stale 4d refs still warn or fault through existing mechanisms.
- Authored evidence-line validation behavior remains unchanged.
- No graph/materialization semantics change.

## 3. Non-goals

- Do not create persisted evidence-line markdown files for derived literature units.
- Do not weaken proposition `source_refs` ownership checks.
- Do not treat scanner faults as coverage.
- Do not change belief magnitudes, contested logic, independence grouping, or 4d
  materialization.
- Do not solve 4e reconciliation: paraphrase dedup, factorization reconciliation,
  citation-graph independence, and identification-strength promotion remain out of
  scope.

## 4. Design

Extend `check_evidence_lines_unstanced` with a second coverage source alongside the
existing authored evidence-line coverage.

Current authored coverage:

```text
(target proposition id, evidence-line source ref)
```

New derived literature coverage:

```text
(assertion.proposition_ref, assertion.paper_ref)
(assertion.proposition_ref, assertion annotation ref)
```

The annotation ref is the same ownership ref Phase 4d already requires in proposition
`source_refs`:

```text
annotation:<sidecar markdown relpath without .md>#<annotation-id>
```

For example:

```text
annotation:entities/papers/VanWonderen2024.source#bes-similar-meta-analysis
```

Implementation should reuse the existing Phase 4d scanner rather than re-parsing
sidecars independently:

- Build proposition ownership with `proposition_source_refs_map(...)` from a cached
  non-strict source load, for example
  `ctx.project_sources(strict_core_schema=False, strict_identity=False).entities`, so
  validation reuses `ValidateContext`'s caches instead of doing an independent full
  project load and does not turn this structural check into a schema validator.
- Run `scan_literature_assertions(project_root, proposition_source_refs)`.
- For each clean `LiteratureAssertion`, add paper and annotation coverage pairs.
- Ignore returned faults for coverage purposes.

This keeps the validator aligned with the materializer and diagnostic instead of
duplicating stance, ownership, lifecycle, or adapter rules.

### Scanner contract change

The scanner already constructs the full annotation ownership ref while checking
proposition `source_refs`:

```text
annotation:{entity_relpath_for_sidecar(sidecar_path, project_root)}#{ann.id}
```

Today that value is discarded after the ownership check. The implementation should add
it as a field on `LiteratureAssertion`, for example:

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

That is a behavior-neutral scanner API extension: materialization can keep using
`proposition_ref`, `paper_ref`, and `stance`; the validator can read
`assertion.annotation_ref` directly. The validator should not reconstruct the annotation
ref from `assertion.sidecar` and `assertion.annotation_id`, because that would duplicate
the string-building rule the scanner already owns.

The new field should be appended after `sidecar`, not inserted before it, to minimize
positional-constructor churn and avoid shifting the old `sidecar` argument into the new
field. Implementation still needs to update every constructor site explicitly. Current
known sites are:

- `science/src/science_tool/annotation/cross_paper_evidence.py` real scanner append
  site, where `ann_ref` is already computed.
- `science/tests/test_cross_paper_evidence_materialize.py` fixture/helper calls.
- `science/tests/test_cross_paper_evidence.py` collapse/scanner fixture calls.

Where a fixture has a natural annotation ref, use it; otherwise use a deterministic
test-only ref such as `annotation:entities/papers/A.source#ann-1`. Prefer keyword
arguments for new or heavily edited fixture constructors so the dataclass shape is
obvious at the call site.

### ID-form consistency

Coverage pairs use canonical proposition refs in byte-identical form:

```text
proposition:<local-id>
```

The authored validator loop reads `prop_id` from proposition frontmatter. The derived
coverage helper receives `assertion.proposition_ref`, which comes from
`ann.promoted_to` after scanner ownership checks against
`proposition_source_refs_map(ctx.project_sources(...).entities)`. The implementation
should test that these forms line up, so a future change that emits `p1` in one path
and `proposition:p1` in another fails loudly.

### Silent skips remain unstanced

The scanner silently skips annotations that are valid but not belief-bearing literature
assertions:

- `promoted_to is None`
- status outside `{open, ack}`
- `stance: open`

Those skips must not create coverage. If a proposition's only sidecar annotation is
`stance: open`, the source ref remains unstanced and `evidence.unstanced` should still
warn. That is intentional: `open` is a question-like marker, not support or dispute.

## 5. Fault Semantics

Scanner faults must not suppress `evidence.unstanced` warnings.

If a sidecar assertion is malformed, stale, adapter-unresolvable, or lacks required
ownership refs, it is not valid evidence coverage. The 4d diagnostic/health path remains
responsible for reporting the specific scanner fault. The generic `evidence.unstanced`
check may still warn that the proposition source ref has no covered evidence-line.

This preserves fail-early behavior:

- Clean 4d assertions reduce false positives.
- Corrupt 4d assertions remain visible.
- The validator does not silently bless refs merely because a sidecar exists.
- Other non-`cite:` proposition `source_refs` outside clean 4d coverage, such as
  unrelated `dataset:` or `external:` refs, keep the current behavior. This design
  narrows only the known false positives for clean Phase 4d paper/annotation refs.

## 6. Alternatives Considered

### A. Read the built graph and inspect virtual evidence lines

Pros:

- Closest to the final materialized evidence state.
- Would recognize exactly what belief sees after `graph build`.

Cons:

- `evidence.unstanced` is currently a frontmatter-time structural check that works
  before graph build.
- It would make validation depend on a possibly stale or missing `knowledge/graph.trig`.
- It duplicates logic already available through the Phase 4d scanner.

Rejected.

### B. Suppress `paper:` and `annotation:` refs on propositions

Pros:

- Very small code change.

Cons:

- Too broad. It would hide real ungrounded proposition provenance outside 4d.
- It weakens the purpose of `evidence.unstanced`.

Rejected.

### C. Reuse the Phase 4d scanner to add derived coverage

Pros:

- Shares the exact ownership, lifecycle, stance, and sidecar-scope rules already used by
  materialization and health.
- Keeps validation useful before graph build.
- Narrowly removes only valid 4d false positives.

Cons:

- The validator will do bounded sidecar scanning in this check.
- The check becomes aware of the annotation subsystem.

Chosen.

## 7. Testing

Add focused tests in `science/tests/validate/test_checks_evidence_lines.py`:

1. A proposition with valid 4d `paper:` and `annotation:` source refs emits no
   `evidence.unstanced`.
2. A proposition whose sidecar assertion is faulted by missing annotation ownership
   still warns for the `paper:` ref, because the whole assertion grants no derived
   coverage.
3. A sidecar that parses but faults, such as `invalid-stance` or `stale-proposition`,
   does not cover either its `paper:` or annotation refs; both remain eligible for
   `evidence.unstanced` warnings when present in `source_refs`.
4. A proposition whose only annotation is silently skipped (`stance: open`, inactive
   status, or no `promoted_to`) still emits `evidence.unstanced`.
5. The derived coverage pair uses the same canonical proposition id as proposition
   frontmatter (`proposition:p1`), guarding against future byte-form divergence.
6. Existing authored evidence-line coverage still suppresses warnings.
7. Existing missing authored coverage still emits warnings.

Run targeted validation tests plus the cross-paper evidence tests:

```bash
cd science
uv run --frozen pytest tests/validate/test_checks_evidence_lines.py -q
uv run --frozen pytest tests/test_cross_paper_evidence.py -q
```

For real-corpus acceptance, run:

```bash
cd science
uv run --frozen science validate --project-root ../meta
uv run --frozen science health --project-root ../meta --check cross_paper_evidence --format json
```

Expected real-corpus outcome:

- The two 4d smoke propositions no longer emit `evidence.unstanced` for their valid
  paper/annotation refs.
- Cross-paper evidence health remains `ok`.
- Existing unrelated validation warnings remain unchanged.

## 8. Implementation Notes

The implementation should keep `check_evidence_lines_unstanced` readable by extracting a
small helper, for example:

```python
def _derived_literature_coverage(ctx: ValidateContext) -> set[tuple[str, str]]:
    ...
```

The helper should fail closed for optional infrastructure problems: if the scanner
returns faults, do not add coverage for faulted assertions. If loading project sources
or scanning sidecars raises an unexpected exception, let validation surface the existing
exception rather than silently suppressing the check.

The result should be a validator-only integration apart from the behavior-neutral
`LiteratureAssertion.annotation_ref` scanner-field addition. No changes are expected in
`graph/materialize.py`, belief reduction, cross-paper diagnostic output, or health
summary semantics.
