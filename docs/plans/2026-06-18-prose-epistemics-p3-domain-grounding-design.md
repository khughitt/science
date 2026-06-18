# P3 - Domain grounding design

**Status:** approved design (brainstorming) 2026-06-18.

**Parent:** `~/d/science/docs/plans/2026-06-17-prose-epistemics-umbrella-design.md`

**Predecessor:** `~/d/science/docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`

**Scope of this document:** P3 only. This designs the read-only grounding layer that
turns promoted domain propositions into explicit grounding results, then projects those
results back onto P2 prose decomposition units. It does not design evidence authoring,
domain-paper ingestion, prose-health rendering, natural-systems content migration, or live
LLM integration.

---

## 1. Goal

P3 makes "grounded in evidence" an explicit, reusable read model.

P2 can promote authored prose claims into propositions and preserve provenance from each
prose unit to the minted or linked proposition. P3 reads those promoted propositions
against the existing evidence-line and belief machinery:

```text
proposition ref + graph
  -> collect evidence-line units
  -> aggregate_belief
  -> grounding result
```

Then P3 projects that result back to authored prose:

```text
prose-source:<slug>
  -> latest P2 decomposition artifact and index
  -> promoted proposition refs
  -> proposition grounding results
  -> durable prose-grounding JSON artifact
```

P3 is framework-only. It proves the read path and artifact seam without running a
natural-systems evidence campaign.

## 2. Decisions

### 2.1 Build the grounding core first

Grounding is graph-layer behavior, not prose-layer behavior.

P3 introduces a small source-agnostic grounding **kernel**: the central computation that
everything else wraps. In this document, "kernel" does not mean an operating-system kernel
or a mathematical kernel method; it means the minimal core rule:

```text
proposition ref + graph -> evidence units -> aggregate_belief -> GroundingResult
```

The prose report is the first projection over that kernel. Future source types should be
able to call the same core without knowing anything about P2 decomposition artifacts.

### 2.2 Read-only first

P3 consumes existing graph state and P2 decomposition state. It does not create evidence
or propositions.

Out of scope:

- evidence-line authoring or import tooling
- domain-paper ingestion
- prose decomposition or proposition promotion
- live LLM generation
- rendered prose styling
- historical grounding snapshots or trend semantics

This boundary keeps P3 honest: missing evidence is reported as a first-class result, not
papered over by a new authoring shortcut.

### 2.3 Default grounded floor

The default grounding floor is **`supported` or above**.

The existing belief ladder is:

```text
speculative < fragile < supported < well_supported
```

With a `supported` floor:

- `speculative` means no eligible support.
- `fragile` means evidence-present but below the grounding bar.
- `supported` and `well_supported` mean grounded.

The floor must be recorded in every output artifact and CLI JSON payload. Downstream
consumers must not infer grounding policy from a boolean field.

### 2.4 Durable latest artifact, no history yet

P3 writes a durable latest JSON artifact for P4 to consume.

It does not create append-only history. Historical trend semantics should wait until a
real consumer needs them and P4 has settled the health metric.

## 3. Architecture

P3 adds one reusable core and one prose-specific projection.

```text
                         ┌────────────────────────────┐
                         │ Grounding kernel            │
knowledge/provenance ───▶│ proposition -> belief read  │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
                         ┌────────────────────────────┐
P2 decomposition/index ─▶│ Prose grounding projection  │
                         │ unit -> grounding row       │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
                         data/prose-grounding/<slug>/grounding.json
```

The grounding kernel reads the materialized graph, gathers evidence-line units with the
existing `collect_evidence_units(...)` path, and delegates belief computation to
`aggregate_belief(...)`. It does not define a new belief algorithm.

The prose projection joins the latest P2 unit state to promoted propositions, calls the
kernel for each promoted proposition, and writes a stable JSON artifact. It does not
compute belief directly.

## 4. Components

### 4.1 Grounding kernel

Likely module: `science_tool.graph.grounding`.

Responsibilities:

- Accept proposition refs or graph URIs.
- Validate the grounding floor against known belief magnitudes.
- Resolve proposition refs through existing graph/entity URI conventions.
- Read evidence via `collect_evidence_units(knowledge, provenance, [target])`.
- Compute belief via `aggregate_belief(units)`.
- Return a typed `GroundingResult`.

Suggested public shape:

```python
ground_proposition(ref_or_uri, knowledge, provenance, *, floor) -> GroundingResult
ground_propositions(refs_or_uris, knowledge, provenance, *, floor) -> list[GroundingResult]
```

`GroundingResult` should include:

- target proposition ref
- status: `grounded`, `below_floor`, or `unbacked`
- belief magnitude and display string
- floor
- contested flag
- evidence counts by role/status
- cap flags already exposed by `BeliefResult`
- belief policy identity/version

The exact dataclass field names are implementation-plan detail. The invariant is that all
policy needed to interpret `status` travels with the result.

### 4.2 Prose grounding projection

Likely module: `science_tool.annotation.prose_grounding`.

Responsibilities:

- Accept `prose-source:<slug>`.
- Load the latest P2 artifact with `ProseDecompositionStore.load_latest(...)`.
- Load the P2 index to read unit fingerprints, stale state, and `promoted_to`.
- Build one output row for each relevant latest or stale unit.
- Call the grounding kernel for promoted proposition units.
- Compute summary counts.
- Write the durable latest JSON artifact.

Unit classification:

| P2 unit state | P3 status | Counted in current domain denominator? |
|---|---|---|
| candidate + `promoted_to` + belief >= floor | `grounded` | yes |
| candidate + `promoted_to` + belief `fragile` | `below_floor` | yes |
| candidate + `promoted_to` + belief `speculative` | `unbacked` | yes |
| candidate + no `promoted_to` | `unpromoted` | yes |
| skip | `skipped` with reason | no |
| stale | `stale` | no |

This preserves the distinction P4 needs: unpromoted and unbacked are different problems,
and skipped meta/non-claim spans are visible without inflating the domain grounding
denominator.

### 4.3 CLI

Add an operator command under the annotation command group, for example:

```text
science annotate ground-prose \
  --source prose-source:<slug> \
  --graph knowledge/graph.trig \
  --format table|json \
  --write
```

Behavior:

- Without `--write`, compute and print rows or JSON.
- With `--write`, persist the latest artifact.
- JSON output and persisted JSON use the same payload shape.
- Table output is a convenience surface and must not be the only machine-readable form.

## 5. Artifact

P3 writes the latest prose-grounding artifact to:

```text
data/prose-grounding/<source-slug>/grounding.json
```

Schema version 1:

```json
{
  "schema_version": 1,
  "source_ref": "prose-source:example",
  "decomposition_artifact_id": "decomp-2026-06-18",
  "graph_path": "knowledge/graph.trig",
  "generated_at": "2026-06-18T12:00:00Z",
  "grounding_policy": {
    "floor": "supported",
    "belief_policy_id": "core-default",
    "belief_policy_version": "1"
  },
  "summary": {
    "current_candidate_units": 10,
    "promoted_units": 8,
    "grounded_units": 3,
    "fragile_units": 2,
    "unbacked_units": 3,
    "unpromoted_units": 2,
    "skipped_units": 4,
    "stale_units": 1,
    "contested_units": 1
  },
  "units": [
    {
      "unit_id": "u001",
      "fingerprint": "sha256:...",
      "disposition": "candidate",
      "artifact_ref": "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001",
      "proposition_ref": "proposition:basalt-flows-record-cooling-history",
      "status": "grounded",
      "grounding": {
        "belief_magnitude": "supported",
        "belief_display": "supported",
        "floor": "supported",
        "contested": false,
        "support_units": 2,
        "dispute_units": 0,
        "diagnostic_units": 0,
        "excluded_units": 0,
        "capped_by_refutation": false,
        "authored_capped": false,
        "qa_dataset_capped": false
      }
    }
  ]
}
```

Notes:

- `generated_at` is metadata, not identity.
- The artifact is a latest-state file, not an immutable generation.
- `graph_path` should be project-relative.
- `fragile_units` are below-floor units, not grounded units.
- Skip rows preserve the P2 skip reason.
- Stale rows may be included for audit, but are excluded from current coverage metrics.

## 6. Error handling

P3 fails early for structural/data-integrity problems and represents epistemic absence as
data.

Hard failures:

- `--source` is not `prose-source:<slug>`.
- Latest P2 decomposition/index is missing or invalid.
- The graph file is missing, unreadable, or lacks expected named graphs.
- A unit has `promoted_to` but the proposition cannot be found in the graph.
- A `promoted_to` ref is not a proposition ref.
- The decomposition index points at an artifact/unit that cannot be reloaded.
- The grounding floor is not a known belief magnitude.

Data statuses:

- Candidate unit has no `promoted_to`: `unpromoted`.
- Promoted proposition has no eligible evidence: `unbacked`.
- Promoted proposition has only below-floor evidence: `below_floor`.
- Promoted proposition is at or above floor: `grounded`.
- Skip unit: `skipped`.
- Stale unit: `stale`.
- Contested proposition: retain magnitude-derived status and set `contested: true`.

Broken joins are implementation or data-integrity failures. Missing evidence is the signal
P3 exists to report.

## 7. Testing

P3 should be implemented test-first across the grounding core, prose projection,
artifact writer, CLI, and regression suite.

Grounding kernel:

- No evidence gives `speculative` and `unbacked`.
- One eligible support gives `fragile` and `below_floor`.
- Two independent supports give `supported` or `well_supported` and `grounded`.
- Dispute evidence preserves `contested`.
- Invalid floor fails loudly.

Prose projection:

- Promoted candidate joins to proposition grounding.
- Unpromoted candidate becomes `unpromoted`.
- Skip unit preserves skip reason and is excluded from the domain denominator.
- Stale unit is surfaced and excluded from the current denominator.
- Missing promoted proposition hard-fails.
- `supported` floor counts `fragile` separately.

Artifact writer:

- Writes `data/prose-grounding/<slug>/grounding.json`.
- Includes decomposition artifact id, graph path, policy identity, summary, and rows.
- Avoids brittle assertions on `generated_at`.

CLI:

- `--format json` prints the payload shape.
- `--write` persists the payload.
- Bad source ref, missing graph, and missing decomposition produce clean CLI errors.

Regression:

- P2 ingest/check/promote tests still pass.
- Belief aggregation tests still pass.
- P1 paper extract/promote tests still pass.

## 8. Alternatives considered

### Prose-only grounding report

Rejected. It would be faster to implement, but it would bake prose into the core
grounding abstraction. That repeats the kind of source coupling P1/P2 were designed to
avoid.

### Full grounding platform

Rejected for P3. A platform with graph-wide reports, historical snapshots, evidence
authoring/import, domain-paper ingestion, and policy configuration is plausible later, but
it mixes read-model work with source curation and health policy. P3 should first make the
grounding read path correct and reusable.

### CLI-only output

Rejected. P4 needs a stable Python-owned JSON seam. Printing JSON on demand is useful, but
without a durable artifact P4 would have to recompute or shell out to read grounding.

### Append-only grounding snapshots

Deferred. Snapshot history may be useful after P4 defines trend semantics, but a latest
artifact is the right first contract.

## 9. Non-goals

- No new belief algorithm.
- No evidence-line authoring/import.
- No domain-paper ingestion.
- No proposition promotion changes.
- No decomposition generation.
- No rendered prose styling.
- No natural-systems content campaign.
- No historical grounding trend semantics.

## 10. Open implementation choices

- Exact dataclass names and field names for `GroundingResult`.
- Whether the CLI command is named `ground-prose`, `grounding-report`, or another
  annotation-group verb.
- Whether stale rows are physically included in `units[]` or summarized from index state
  only. The logical status must exist either way.
- Whether `support_units` and `dispute_units` count reduced units only or include a richer
  split of reduced/collapsed/excluded counts. The artifact should not hide excluded or
  diagnostic evidence, but the exact row shape can be settled in the plan.
