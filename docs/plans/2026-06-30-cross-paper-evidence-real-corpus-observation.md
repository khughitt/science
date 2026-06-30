# Cross-Paper Evidence Real-Corpus Observation

**Date:** 2026-06-30
**Status:** Observed after Phase 4d readiness-surface hardening
**Scope:** Project-wide run of the derived cross-paper literature evidence diagnostic and health surface.

## Command

Run from the package environment against the live `science-meta` project root:

```bash
cd science
rtk uv run --frozen science annotate cross-paper-evidence --root ../meta --format json > /tmp/phase4d-cross-paper-evidence.json
rtk uv run --frozen science annotate cross-paper-evidence --root ../meta --format table
rtk uv run --frozen science health --project-root ../meta --check cross_paper_evidence --format json > /tmp/phase4d-cross-paper-evidence-health.json
```

## Result

The hardened diagnostic completed successfully against `../meta` and returned an
explicit empty-state report:

```json
{
  "faults": [],
  "propositions": [],
  "summary": {
    "contested": 0,
    "faults": 0,
    "faults_by_reason": {},
    "propositions": 0,
    "propositions_with_units": 0,
    "units": 0
  }
}
```

Table output:

```text
No proposition entities found.
```

Observed counts:

| Metric | Count |
|---|---:|
| Proposition entities | 0 |
| Propositions with derived units | 0 |
| Derived literature evidence units | 0 |
| Contested propositions | 0 |
| Scanner faults | 0 |
| Scanner fault reasons | 0 |

The relevant `cross_paper_evidence` section of the health report showed the same
clean empty state:

```json
{
  "cross_paper_evidence": {
    "status": "ok",
    "empty_state": "no_propositions",
    "summary": {
      "propositions": 0,
      "propositions_with_units": 0,
      "units": 0,
      "faults": 0,
      "faults_by_reason": {},
      "contested": 0
    },
    "findings": [],
    "propositions": []
  }
}
```

This is consistent with the current `meta/` corpus: it has papers, hypotheses,
synthesis documents, and manually written proposition-like sections inside those
documents, but it does not yet have promoted `proposition:*` entities or paper
annotation sidecars. Phase 4d is therefore behavior-neutral on the live corpus today.

## Diagnostic Scope Finding

The pre-hardening run from the package root without an explicit project root failed:

```bash
cd science
uv run --frozen science annotate cross-paper-evidence --format json
```

Failure mode: the scanner recursively walked `science/tests/_fixtures/**` and tried to
parse an intentionally malformed annotation fixture:

```text
science_tool.annotation.query.SidecarParseError:
failed to parse sidecar .../science/tests/_fixtures/annotation/malformed-missing-type.anno.trig
```

Root cause: Phase 4d Half A used `iter_sidecars(project_root)`, which recursively
scanned all `.anno.trig` files under the selected root. That was correct for narrow
fixture projects but too broad for a repository/package root that contains test
fixtures. The post-hardening `../meta` run above now reports the live empty corpus
without scanner faults.

## Implications

- There is no real cross-paper literature belief to inspect yet; the next useful corpus
  step is to annotate/promote at least one multi-paper proposition fixture or live paper
  slice.
- The diagnostic now reports this empty state explicitly, so an empty table is not
  mistaken for a successful non-empty corpus scan.
- The health surface exposes the same state as `cross_paper_evidence.status == "ok"`
  with `empty_state == "no_propositions"`.
