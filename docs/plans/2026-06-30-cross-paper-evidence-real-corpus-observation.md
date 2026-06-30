# Cross-Paper Evidence Real-Corpus Observation

**Date:** 2026-06-30
**Status:** Observed after Phase 4d Half A merge
**Scope:** First project-wide run of the derived cross-paper literature evidence diagnostic.

## Command

Run from the package environment against the live `science-meta` project root:

```bash
cd science
uv run --frozen science annotate cross-paper-evidence --root ../meta --format json > /tmp/phase4d-cross-paper-evidence.json
uv run --frozen science annotate cross-paper-evidence --root ../meta --format table
```

Independent corpus checks:

```bash
rg --files meta -g '*.anno.trig'
rg -n '^type: proposition$|^id: proposition:' meta/entities -g '*.md'
```

## Result

The diagnostic completed successfully against `../meta` and returned an empty report:

```json
{
  "faults": [],
  "propositions": []
}
```

Observed counts:

| Metric | Count |
|---|---:|
| Proposition entities | 0 |
| Live annotation sidecars | 0 |
| Derived literature evidence units | 0 |
| Propositions gaining literature belief | 0 |
| Contested propositions | 0 |
| Scanner faults | 0 |

This is consistent with the current `meta/` corpus: it has papers, hypotheses,
synthesis documents, and manually written proposition-like sections inside those
documents, but it does not yet have promoted `proposition:*` entities or paper
annotation sidecars. Phase 4d is therefore behavior-neutral on the live corpus today.

## Diagnostic Scope Finding

Running the command from the package root without an explicit project root failed:

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

Root cause: Phase 4d Half A used `iter_sidecars(project_root)`, which recursively scans
all `.anno.trig` files under the selected root. That is correct for narrow fixture
projects but too broad for a repository/package root that contains test fixtures.

## Implications

- There is no real cross-paper literature belief to inspect yet; the next useful corpus
  step is to annotate/promote at least one multi-paper proposition fixture or live paper
  slice.
- The diagnostic should be hardened before relying on default-root usage: production
  scanning should be limited to project source/entity roots, not arbitrary test fixture
  trees under the current working directory.
- The health surface should report this empty-state explicitly ("no proposition entities"
  or "no promoted paper-sidecar assertions") so an empty table is not mistaken for a
  successful non-empty corpus scan.
