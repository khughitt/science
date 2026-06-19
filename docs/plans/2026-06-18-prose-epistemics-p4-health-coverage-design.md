# P4 - Prose health coverage-ramp design

**Status:** design approved in brainstorming, 2026-06-18.

**Parent:** `~/d/science/docs/plans/2026-06-17-prose-epistemics-umbrella-design.md`

**Predecessors:**
- P2 internal prose:
  `~/d/science/docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`
- P3 domain grounding:
  `~/d/science/docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-design.md`

**Implementation precondition:** P4 implementation requires shipped P2 and P3 contracts.
This design intentionally references the P2/P3 designs, but the eventual implementation
plan must reconcile names and schemas against the shipped code before coding starts.

**Scope of this document:** P4 only. P4 turns existing P2 decomposition state and P3
grounding reports into a project-level prose-health artifact that downstream consumers can
read without knowing P2/P3 storage internals. P4 is framework-only but consumer-shaped.
It does not run decomposition, promotion, grounding, evidence authoring, source ingestion,
or downstream rendering.

---

## 1. Purpose

P1-P3 now provide the internal prose path:

```text
Markdown prose
  -> P2 decomposition/promotion state
  -> P3 per-source grounding report
```

P4 provides the missing consumer contract:

```text
prose epistemics manifest
  + P2 decomposition/index state
  + P3 grounding reports
  -> data/prose-health/prose-health.json
  -> science health summary
  -> downstream TS/rendering consumers
```

The point is not to decide whether the prose is "good" or "bad". The point is to expose a
coverage ramp: which in-scope prose claims are decomposed, promoted, grounded, below the
floor, unbacked, skipped, or stale.

P4 keeps epistemic absence explicit. A source declared in scope but missing a decomposition
or grounding report is a reportable state, not an invisible absence.

## 2. Long-term shape

The long-term system has five separate responsibilities.

1. **Manifest:** declares the prose sources in scope and owns the denominator.
2. **P2 decomposition store:** owns source units, locators, fingerprints, skip reasons,
   stale state, and promotion links.
3. **P3 grounding reports:** own per-source belief/grounding status for promoted units.
4. **P4 prose health artifact:** owns cross-source rollups, consumer rows,
   missing-artifact diagnostics, and coverage-ramp metrics.
5. **Downstream consumers:** read P4 JSON only. They do not learn P2/P3 layouts or
   recompute epistemic logic.

P4 deliberately reads both P2 and P3. P3 is not sufficient by itself because P3 rows do not
carry the full locator/quote information downstream renderers need. P4 therefore depends on
the P2 store's latest decomposition, unit fingerprints, locator composition, and
artifact-unit references, as well as P3's per-source grounding summary and status rows.

`science health` is a reader/summarizer of P4. It is not the canonical prose-health data
source and should not rebuild P4 implicitly.

### 2.1 Explicit manifest, not blind discovery

P4 should use an explicit manifest of in-scope prose sources. Auto-discovery is useful only
as a diagnostic for undeclared artifacts.

This distinction matters:

- "Not declared" means outside the denominator.
- "Declared but missing decomposition" means in scope and incomplete.
- "Declared but missing grounding" means decomposed/promoted state may exist, but the P3
  read model has not been produced.
- "Grounding report exists but source is undeclared" is a cleanup warning, not a coverage
  input.

The manifest is intentionally small:

```json
{
  "schema_version": 1,
  "sources": [
    {
      "source_ref": "prose-source:example",
      "path": "docs/example.md",
      "title": "Example"
    }
  ]
}
```

The default manifest path is:

```text
data/prose-health/manifest.json
```

## 3. P4 artifact

P4 writes one latest-state JSON artifact:

```text
data/prose-health/prose-health.json
```

The artifact is the stable Python-produced, downstream-consumed contract.

### 3.1 Top-level schema

```json
{
  "schema_version": 1,
  "generated_at": "2026-06-18T13:00:00Z",
  "manifest_path": "data/prose-health/manifest.json",
  "summary": {
    "declared_sources": 12,
    "sources_with_decomposition": 10,
    "sources_with_grounding": 9,
    "current_candidate_units": 120,
    "promoted_units": 70,
    "grounded_units": 22,
    "below_floor_units": 8,
    "unbacked_units": 40,
    "unpromoted_units": 50,
    "skipped_units": 35,
    "stale_units": 4,
    "contested_units": 3
  },
  "coverage": {
    "promotion": {
      "numerator": 70,
      "denominator": 120,
      "ratio": 0.5833
    },
    "grounding": {
      "numerator": 22,
      "denominator": 70,
      "ratio": 0.3143
    },
    "strict_grounding": {
      "numerator": 22,
      "denominator": 120,
      "ratio": 0.1833
    }
  },
  "sources": [],
  "units": [],
  "findings": []
}
```

`generated_at` is metadata, not identity. The writer should skip timestamp-only rewrites,
mirroring P3's grounding report writer.

### 3.2 Source rows

Each declared manifest source produces a source row:

```json
{
  "source_ref": "prose-source:example",
  "title": "Example",
  "path": "docs/example.md",
  "state": "complete",
  "decomposition_artifact_id": "decomp-1",
  "grounding_report_path": "data/prose-grounding/example/grounding.json",
  "summary": {
    "current_candidate_units": 10,
    "promoted_units": 8,
    "grounded_units": 3,
    "below_floor_units": 1,
    "unbacked_units": 4,
    "unpromoted_units": 2,
    "skipped_units": 5,
    "stale_units": 0,
    "contested_units": 1
  }
}
```

Initial source states:

- `complete`
- `missing_decomposition`
- `missing_grounding`
- `invalid_decomposition`
- `invalid_grounding`
- `stale_grounding`

`stale_grounding` means the P3 report does not match the latest P2 decomposition artifact
for the manifest source.

`state` is a single summary value, so P4 must assign it deterministically. Precedence:

1. `missing_decomposition`
2. `invalid_decomposition`
3. `missing_grounding`
4. `invalid_grounding`
5. `stale_grounding`
6. `complete`

For artifact findings, every non-`complete` source state emits exactly one corresponding
source-level finding with the same `code`, and every source-level artifact finding with one
of those codes is reflected by the source row's `state`. Additional non-source findings
such as `undeclared_grounding_report` do not affect a declared source's `state`.

`invalid_decomposition` should be rare because P2 validates at ingest. It is still a P4
state for later file corruption, hand-edited stored artifacts, or stricter P4 validation of
the P2/P3 join contract.

### 3.3 Unit rows

P4 enriches P3 rows by joining back to P2 locators. Downstream consumers need enough
location data to style prose without parsing P2 artifacts.

```json
{
  "source_ref": "prose-source:example",
  "source_path": "docs/example.md",
  "unit_id": "u001",
  "fingerprint": "sha256:...",
  "artifact_ref": "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001",
  "heading_path": ["Section"],
  "quote": {
    "exact": "Basalt flows record the cooling history.",
    "prefix": "",
    "suffix": ""
  },
  "status": "grounded",
  "disposition": "candidate",
  "proposition_ref": "proposition:basalt-cooling",
  "grounding": {},
  "skip_reason": null,
  "skip_detail": null
}
```

Row identity and locator rules:

- `source_ref` is the durable source identity.
- `fingerprint` is the durable unit identity.
- `unit_id` is artifact-local display data only.
- Candidate quote comes from `StatementCandidate.exact/prefix/suffix`.
- Skip quote comes from `locator.quote`.
- `heading_path` is always included.
- `grounding` is copied from P3 as an opaque object.
- Rows use a uniform shape. Missing fields are `null`, not omitted, for stable downstream
  consumption.

P4 joins units by fingerprint. Joining by `unit_id` would reintroduce the renumbering bug
P2 was designed to avoid.

## 4. Coverage semantics

P4 reports coverage as a ramp, not as a pass/fail gate.

### 4.1 Status vocabulary

P4 preserves P3's status vocabulary:

- `grounded`: promoted and at or above the grounding floor.
- `below_floor`: promoted with eligible evidence, but below the floor.
- `unbacked`: promoted but no eligible evidence.
- `unpromoted`: candidate exists but has no proposition link.
- `skipped`: non-domain, non-claim, meta, malformed, or otherwise intentionally skipped.
- `stale`: historical unit missing from the latest decomposition.

Skipped and stale units remain visible but do not inflate current candidate denominators.

### 4.2 Metrics

P4 computes three primary ratios:

- `promotion`: promoted candidate claims / current candidate claims.
- `grounding`: grounded promoted claims / promoted claims.
- `strict_grounding`: grounded claims / current candidate claims.

Here `strict_grounding` names the widest-denominator coverage metric. It is distinct from
the umbrella's "strict grounding bar", which is the belief-floor policy for deciding whether
an individual promoted claim counts as grounded.

The distinction is load-bearing:

- `promotion` measures graph adoption of decomposed domain claims.
- `grounding` measures evidence support among claims represented in the graph.
- `strict_grounding` measures evidence support across all decomposed domain claims.

For zero denominators, the ratio should be `null`, not `0.0`, because there is no measured
coverage yet.

### 4.3 Findings and issue policy

P4 findings are structured diagnostic rows, not free-form prose. Initial finding codes:

| Code | Surfaces in artifact? | Surfaces in health? | Counts as issue by default? |
|---|---:|---:|---:|
| `missing_decomposition` | yes | yes | yes |
| `missing_grounding` | yes | yes | yes |
| `stale_grounding` | yes | yes | yes |
| `invalid_decomposition` | yes | yes | yes |
| `invalid_grounding` | yes | yes | yes |
| `undeclared_grounding_report` | yes | yes | no |
| `manifest_invalid` | no | yes | yes |

`manifest_invalid` is health-only because the explicit P4 builder must fail rather than
write an artifact from an untrusted denominator. `science health` may still catch that
failure and surface it as a finding so users get a repair path.

Finding rows should carry at least:

```json
{
  "code": "missing_grounding",
  "severity": "warning",
  "counts_as_issue": true,
  "source_ref": "prose-source:example",
  "path": "docs/example.md",
  "message": "Declared prose source has no P3 grounding report."
}
```

Low coverage is not a `total_issues` contributor by default. Missing or invalid declared
artifacts and stale grounding reports do count as issues because they prevent the coverage
ramp from representing the declared denominator. `undeclared_grounding_report` is a cleanup
warning and does not count as an issue by default. A future threshold policy may promote low
coverage to an issue, but P4 does not bake in threshold gates beyond P3's grounding floor.

`sources_with_grounding` counts sources that have a P3 grounding report file, including
`stale_grounding` sources. Freshness is represented by `state` and findings, not by hiding
the report from the existence count.

## 5. Build and health integration

### 5.1 P4 builder

Likely module:

```text
science_tool.annotation.prose_health
```

Core API:

```python
load_prose_health_manifest(
    project_root: Path,
    manifest_path: Path | None = None,
) -> ProseHealthManifest

build_prose_health_report(
    project_root: Path,
    *,
    manifest_path: Path | None = None,
    generated_at: str,
) -> ProseHealthReport

write_prose_health_report(
    project_root: Path,
    report: ProseHealthReport,
) -> bool

prose_health_path(project_root: Path) -> Path
```

Build flow:

1. Load and validate the manifest.
2. For each declared source:
   - Load latest P2 decomposition.
   - Load P3 grounding report.
   - Validate `source_ref` and `decomposition_artifact_id` against the latest P2 state.
   - Join P3 rows to P2 units by fingerprint.
   - Emit enriched source and unit rows.
3. Discover P3 grounding reports not declared in the manifest and emit
   `undeclared_grounding_report` findings.
4. Compute project summaries and coverage ratios.
5. Write canonical JSON, skipping timestamp-only rewrites.

Structural corruption in P2/P3 artifacts should become source states/findings in the P4
report where possible. Manifest-level corruption should fail the build, because the
denominator cannot be trusted.

### 5.2 CLI

Add an explicit builder command:

```bash
science annotate build-prose-health \
  --root . \
  --manifest data/prose-health/manifest.json \
  --write \
  --format table
```

Options:

- `--root`: project root.
- `--manifest`: optional manifest path, defaulting to `data/prose-health/manifest.json`.
- `--write`: persist `data/prose-health/prose-health.json`.
- `--format table|json`: print a compact table or the full JSON payload.

The command should not run P2 ingest, P2 promotion, P3 grounding, graph materialization, or
evidence authoring. It is a read-model builder over existing artifacts.

### 5.3 `science health`

Add a `prose_epistemics` health check.

Behavior:

- If the manifest and artifact are both absent, return an empty/non-applicable section.
- If the manifest exists but is invalid, report a `manifest_invalid` finding.
- If the manifest exists but the artifact is missing, report a finding to run
  `science annotate build-prose-health --write`.
- If the artifact exists, read and summarize it.
- Do not rebuild P4 from `science health`.
- Include `prose_epistemics` in health JSON.
- Keep table output compact: summary counts, coverage ratios, and incomplete source rows.

The health section should summarize the P4 artifact faithfully. Downstream consumers should
read the P4 JSON artifact directly instead of scraping `science health` table output.

## 6. Validation and errors

P4 validates at boundaries:

- Manifest JSON must be an object with `schema_version: 1` and a `sources` array.
- Source refs must be `prose-source:<slug>`.
- Source slugs must match the P2/P3 slug grammar.
- Manifest source paths must stay under the project root.
- Duplicate source refs are invalid.
- P3 report `source_ref` must match the manifest source.
- P3 report `decomposition_artifact_id` must match the latest P2 artifact id.
- P3 unit rows must join to latest P2 units by fingerprint for current rows.

Invalid manifest structure should fail early. Invalid per-source P2/P3 state should be
recorded as a source state and finding when the rest of the manifest can still be reported.
`science health` may catch manifest-load failures and surface a `manifest_invalid` finding,
but the explicit P4 builder should not write a prose-health artifact from an invalid
manifest.

## 7. Testing

P4 should be implemented test-first.

Unit tests:

- Manifest validation rejects invalid refs, duplicate sources, path traversal, and malformed
  JSON.
- Complete source produces expected summary, coverage, and enriched rows.
- Multi-condition source failures use the documented source-state precedence.
- Every non-`complete` source state emits one corresponding source-level finding.
- Missing decomposition produces `missing_decomposition`.
- Missing grounding produces `missing_grounding`.
- Grounding report for an older decomposition produces `stale_grounding`.
- Invalid grounding JSON produces `invalid_grounding`.
- A grounding report that is both invalid and stale resolves to `invalid_grounding`.
- A grounding report with matching source/artifact ids but mismatched unit fingerprints
  degrades that source to `invalid_grounding` without aborting the whole report.
- Skip rows carry skip reason and quote locator.
- Candidate rows carry candidate quote and heading path.
- Unit join uses `fingerprint`, not `unit_id`.
- Undeclared grounding reports are findings and excluded from denominators.
- Zero-denominator coverage ratios are `null`.
- Writer skips timestamp-only rewrites.

CLI and health tests:

- `science annotate build-prose-health --format json` prints the full payload.
- `science annotate build-prose-health --write` persists the artifact.
- `science health --check prose_epistemics --format json` reports the P4 section without
  rebuilding it.
- Missing P4 artifact with present manifest is surfaced as a health finding.
- No manifest and no artifact yields an empty/non-applicable health section.

Regression tests:

- P2 decomposition/promote tests still pass.
- P3 grounding tests still pass.
- Existing health tests still pass.

## 8. Alternatives considered

### Health check only, no artifact

Rejected. This would make `science health` the only consumer surface and force downstream
projects either to shell out to Python or duplicate P2/P3 scanning logic. It contradicts the
Python-produced, TS-consumed artifact pattern.

### Extend P3 grounding reports into health artifacts

Rejected. P3 reports answer "what is this source unit's grounding state?" P4 answers "what
is the project's prose epistemic health?" Mixing those responsibilities would make
cross-source metrics and denominator policy harder to change without perturbing P3.

### Blind auto-discovery

Rejected as the denominator authority. Auto-discovery cannot distinguish "not in scope" from
"missing from the pipeline". It remains useful as a cleanup diagnostic for undeclared
artifacts.

## 9. Non-goals

- No live LLM calls.
- No decomposition, promotion, or grounding execution.
- No evidence-line authoring/import.
- No natural-systems-specific content campaign.
- No downstream TS rendering implementation.
- No coverage thresholds beyond reporting P3's grounding floor.
- No historical trend/snapshot semantics.

## 10. Open implementation choices

- Exact `science health` table formatting.
- Whether the P4 builder should include the full `units` array in health JSON or only in the
  durable artifact. The durable artifact must contain it.
- Whether the manifest should later support groups/chapters. P4 schema version 1 should stay
  flat unless a concrete consumer needs grouping.
