# Prose Epistemics Framework Checkpoint

This checkpoint preserves the as-built prose-epistemics framework contract that
replaced the P1-P4 and pilot-improvement planning documents from 2026-06-17 to
2026-06-19.

## Status

Implemented in the Science framework. The active plan files were stale as
planning surfaces after this checkpoint:

- `2026-06-17-prose-epistemics-p1-source-adapter-plan.md`
- `2026-06-18-prose-epistemics-p2-internal-prose-design.md`
- `2026-06-18-prose-epistemics-p2-internal-prose-plan.md`
- `2026-06-18-prose-epistemics-p3-domain-grounding-design.md`
- `2026-06-18-prose-epistemics-p3-domain-grounding-plan.md`
- `2026-06-18-prose-epistemics-p4-health-coverage-design.md`
- `2026-06-18-prose-epistemics-p4-health-coverage-plan.md`
- `2026-06-19-prose-epistemics-pilot-improvements-design.md`
- `2026-06-19-prose-epistemics-pilot-improvements-plan.md`

The first downstream pilot validated framework plumbing only. Broader
offline-agent decomposition quality and larger natural-systems coverage remain
campaign work, not framework blockers.

## P1: Text Source Adapter

`science_tool.annotation.text_source_adapter` defines the source-neutral
annotation seam:

- `LocatorRegime.OFFSET_ANCHORED` for immutable paper-like sources.
- `LocatorRegime.REGENERABLE` for internal Markdown prose.
- `LocatorRegime.NONE` for sources without span provenance.
- `TextSourceAdapter` declares source capabilities and polymorphic methods.
- `PaperSourceAdapter` preserves existing paper behavior by deriving
  `paper:<citekey>` refs and delegating offset-anchored extraction.

The P1 boundary was deliberate: regenerable locators were declared, but the
artifact-led Markdown implementation belongs to P2. Paper `extract` and
`promote` behavior stays routed through the adapter seam without changing the
paper annotation sidecar contract.

## P2: Internal Prose Decomposition

P2 makes authored Markdown prose usable as a first-class source for promotion
into propositions and related epistemic entities.

### Source Identity

`prose-source:<slug>` is an operational source entity for authored internal
Markdown. It is parallel to `paper:<citekey>` as a provenance source; it is not
an authored conclusion such as a report, discussion, or finding.

Ingest resolves or creates the `prose-source` entity before persisting
promotable units. The resolver preserves authored notes and curated fields while
updating machine-owned metadata such as source path, content hash, and latest
artifact id. Durable paths should be project-relative when they are inside the
project root.

### Artifact Contract

Submitted decomposition artifacts are JSON schema version `1`. They contain:

- `source`: `kind`, `slug`, `path`, `title`, and `content_hash`.
- `artifact`: `id`, `generated_at`, and `producer`.
- `units`: candidate or skip units.

Candidate units carry their quoted claim in the `StatementCandidate` payload.
Skip units may carry locator quote fields because they have no candidate
payload. A unit must not have two competing quote homes.

Stored artifacts are immutable generations:

```text
data/prose-decompositions/<slug>/generations/<artifact_id>.json
```

Cross-generation state lives in:

```text
data/prose-decompositions/<slug>/index.json
```

The index records:

- `latest_artifact_id`
- known artifact ids
- unit rows keyed by stable source-span fingerprint
- latest artifact-local unit id
- latest disposition
- `artifact_unit_ref`
- stale state
- optional `promoted_to`

`unit_id` is artifact-local display identity. The cross-generation identity is
the source-span fingerprint over source ref, locator regime, normalized heading
path, and normalized quote. This allows a later offline decomposition to
renumber units without losing promotion state.

Promoted entities receive both the `prose-source:<slug>` ref and an annotation
unit ref:

```text
annotation:data/prose-decompositions/<slug>/generations/<artifact_id>.json#<unit_id>
```

### Locator Contract

`InternalProseAdapter` handles Markdown sources with the regenerable locator
regime. It resolves Markdown heading-path locators, optionally with quote
context, against the current source text.

Resolution outcomes are:

- `resolved`
- `unresolved`
- `ambiguous`

The resolver searches inside the matched section body and requires a single
context match for quoted units. Unsupported locator regimes fail loudly.

### Operator Commands

The implemented P2 command family is:

```bash
science annotate validate-prose-decomposition-artifact <artifact.json> --root . [--allow-changed] [--format table|json]
science annotate ingest-prose-decomposition <artifact.json> --root . [--allow-changed] [--format table|json]
science annotate check-prose-decomposition --source prose-source:<slug> --root . [--format table|json]
science annotate promote-prose-decomposition --source prose-source:<slug> --unit <unit_id> --root . [--apply] [--format table|json]
```

Validation is read-only and uses the same parser and locator resolver as
persisted-artifact checks. Ingest is the state-changing operation. Promotion is
single-unit by default and records promotion state back into the decomposition
index.

## Pilot Hardening: Batch Promotion

Batch promotion is an ergonomic wrapper over the same single-unit promotion
engine. It does not copy candidate payloads into the plan.

```bash
science annotate plan-prose-promotions --source prose-source:<slug> --unit <unit_id> --output plan.json
science annotate apply-prose-promotion-plan plan.json --root . [--format table|json]
```

The plan is identity-only and includes source slug/ref, artifact id, unit id,
fingerprint, artifact unit ref, decision, and optional target ref. Apply re-reads
the latest artifact and fails early if the latest artifact id, fingerprint,
artifact unit ref, candidate disposition, or decision has drifted. Recovered
links are allowed when the target entity already carries the artifact unit ref.

## P3: Prose Grounding

P3 projects graph belief state back onto P2 decomposition units.

The source-agnostic grounding kernel is:

```text
proposition ref + graph -> evidence units -> aggregate belief -> grounding result
```

The prose projection joins the latest P2 artifact and index by fingerprint,
calls the grounding kernel for promoted proposition units, and writes a latest
artifact:

```text
data/prose-grounding/<slug>/grounding.json
```

The artifact records:

- `schema_version: 1`
- `source_ref`
- `decomposition_artifact_id`
- `graph_path`
- `generated_at`
- `grounding_policy`, including floor and belief policy identity/version
- summary counts
- unit rows

Default floor is `supported`. Unit statuses are:

- `grounded`
- `below_floor`
- `unbacked`
- `unpromoted`
- `skipped`
- `stale`

Grounding writes skip timestamp-only rewrites: if only `generated_at` changes,
the artifact is left unchanged.

Command:

```bash
science annotate ground-prose-decomposition --source prose-source:<slug> --graph knowledge/graph.trig --floor supported --write
```

Without `--write`, the command computes and prints the report without
persisting it.

## P4: Prose Health

P4 is the downstream-consumer contract. It reads an explicit manifest plus P2
and P3 artifacts and writes one cross-source rollup:

```text
data/prose-health/manifest.json
data/prose-health/prose-health.json
```

The manifest owns the denominator:

```json
{
  "schema_version": 1,
  "sources": [
    {
      "source_ref": "prose-source:example",
      "path": "doc/example.md",
      "title": "Example"
    }
  ]
}
```

Declared sources are in scope. Undeclared artifacts are diagnostics, not
coverage inputs.

`prose-health.json` records:

- top-level summary counts
- coverage ratios for promotion, grounding, and strict grounding
- source rows
- enriched unit rows with locator/quote information
- findings

Source state precedence is:

1. `missing_decomposition`
2. `invalid_decomposition`
3. `missing_grounding`
4. `invalid_grounding`
5. `stale_grounding`
6. `complete`

Every non-complete declared source state emits a corresponding finding. The
writer also skips timestamp-only rewrites.

Command:

```bash
science annotate build-prose-health --manifest data/prose-health/manifest.json --write
```

`science health` reads this P4 artifact. It does not rebuild P4 implicitly. When
prose epistemics is applicable and findings are present, the health output points
operators back to `science annotate build-prose-health --write`.

## Consumer Boundary

Downstream consumers should read P4 `prose-health.json`. They should not parse
P2 decomposition stores, recompute P3 grounding, or mirror Markdown locator
resolution rules.

The framework keeps Python as the source of truth for:

- Markdown locator validation
- promotion decisions and drift checks
- graph grounding and belief interpretation
- prose health source-state precedence
- coverage-ramp metrics

## Remaining Non-Goals

These remain outside the implemented framework:

- live LLM orchestration or retry policy
- automatic evidence authoring
- domain-paper ingestion
- automatic pass/fail health gating for sparse early grounding
- historical grounding trends
- broad validation of offline-agent decomposition quality beyond the artifact
  schema and locator checks
