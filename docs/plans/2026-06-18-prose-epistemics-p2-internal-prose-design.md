# P2 - Internal prose adapter design

**Status:** approved design (brainstorming) 2026-06-18.

**Parent:** `~/d/science/docs/plans/2026-06-17-prose-epistemics-umbrella-design.md`

**Depends on:** P1 source-adapter refactor.

**Scope of this document:** P2 only. This designs the internal-prose source framework,
the regenerable decomposition artifact, and the ingest/check/promote flow for authored
Markdown prose. It does not design domain grounding, prose health rendering, or the
natural-systems campaign.

---

## 1. Goal

P2 makes authored internal Markdown prose usable as a first-class source for the
proposition pipeline.

The key outcome is:

```text
Markdown source
  -> offline agent creates decomposition JSON
  -> science-tool ingests and validates artifact
  -> prose-source entity is resolved or created
  -> InternalProseAdapter resolves Markdown locators and source refs
  -> check/promote consume validated units
  -> promoted claims retain provenance to prose-source + artifact unit
```

P2 is **framework-only**. It proves the machinery for internal prose without running a
natural-systems content campaign and without live model integration.

## 2. Decisions

### 2.1 Source kind

Add a new first-class operational source kind: `prose-source`.

`prose-source:<slug>` identifies an authored internal Markdown source. It is a source
node, parallel in role to `paper:<citekey>`, not an epistemic output like `report`,
`discussion`, or `finding`.

The internal-prose path must guarantee source-ref resolvability before promotion writes a
source ref. For P2, this means ingesting a decomposition artifact auto mints or links the
corresponding `prose-source:<slug>` entity.

### 2.2 Input scope

P2 supports Markdown sources only.

YAML/model records and other prose containers are deferred until a later phase has an
actual consumer. This keeps the locator regime small enough to validate rigorously.

### 2.3 Artifact shape

P2 introduces a new JSON decomposition artifact. It does not reuse `.anno.trig`.

The long-term shape is one source-neutral decomposition artifact family with `units[]` as
a discriminated union. Candidate, skip, and stale records are peer unit shapes inside that
family. Agent-submitted P2 artifacts normally contain candidate and skip units; stale
units are system-derived during re-ingest when earlier units are missing from the latest
decomposition. The existing `StatementCandidate` shape should remain the candidate
payload, not be replaced by a prose-specific candidate model.

### 2.4 Decomposition production

P2 ingests offline agent output only.

There is no live LLM call, model client, retry policy, prompt executor, or generation queue
in this phase. P2 may document the offline prompt contract, but the implemented path only
validates and persists JSON produced elsewhere.

### 2.5 Staleness

Re-decomposition is non-destructive.

If a newer artifact for the same `prose-source` no longer contains a prior unit, the prior
unit is marked stale or missing in the artifact-tracking layer. P2 must not auto-retire
propositions, delete provenance, or rewrite old artifact content.

## 3. Architecture

P2 is artifact-led:

- `prose-source` is the durable source identity.
- Decomposition JSON is the regenerable text-layer artifact.
- `InternalProseAdapter` handles Markdown source text, source refs, locator regimes, and
  quote resolution.
- Check and promotion consume validated artifact units, not raw agent output.
- Stale marking belongs to the artifact/unit tracking layer, not proposition validity.

This keeps generated decomposition output separate from source identity and avoids
stretching `.anno.trig` into a second, incompatible role.

## 4. Components

### 4.1 `prose-source` entity resolution

Artifact ingest resolves the source entity before persisting promotable units.

The resolver should:

- Accept `kind = "prose-source"` and a stable slug.
- Create the entity when missing.
- Link to the existing entity when present.
- Update only conservative machine-owned metadata, such as source path, title, content
  hash, updated timestamp, and artifact references.
- Preserve authored notes, curated fields, and manually edited metadata.

The ideal long-term shape is a shared source-entity resolution layer reused by future
adapters. P2 may implement the thin prose-source version first, but the interface should
not bake entity persistence into ad hoc CLI code.

### 4.2 `InternalProseAdapter`

`InternalProseAdapter` is the P2 source adapter for Markdown prose.

Declared behavior:

- Source kind: `prose-source`.
- Source ref scheme: `prose-source:<slug>`.
- Locator regime: `regenerable`.
- Fetch: none; reads repo-local Markdown paths.
- Seed: none.

Responsibilities:

- Resolve a source ref from artifact source metadata.
- Read Markdown source text.
- Resolve supported Markdown locators to current text.
- Produce quote/source-ref data for check and promotion.
- Fail loudly when the artifact references a source it cannot handle.

It should not generate decompositions. Generation remains offline.

### 4.3 Decomposition artifact parser

Add a parser/validator for decomposition JSON schema version 1.

The parser should produce typed, validated records for:

- Artifact metadata.
- Source metadata.
- Candidate units.
- Skip units.
- Stale units.

Validation should happen before state changes. Callers should not need to inspect raw JSON
or tolerate partial records.

### 4.4 Artifact storage

P2 needs durable storage for decomposition artifact generations and unit state.

The storage model should preserve each ingested artifact generation. Re-ingest creates a
new generation and records missing prior units as stale or missing in latest. Old artifact
content remains immutable.

The implementation plan should choose the concrete storage location by following existing
project conventions. The design requirement is that check and promotion can load the
latest artifact for a `prose-source`, and promotion can refer to a specific artifact/unit
identity for provenance.

## 5. Decomposition JSON schema

Schema version 1 should be intentionally small:

```json
{
  "schema_version": 1,
  "source": {
    "kind": "prose-source",
    "slug": "example-source",
    "path": "~/d/science/docs/example.md",
    "title": "Example Source",
    "content_hash": "sha256:..."
  },
  "artifact": {
    "id": "decomp_...",
    "generated_at": "2026-06-18T12:00:00Z",
    "producer": "offline-agent"
  },
  "units": [
    {
      "unit_id": "u001",
      "disposition": "candidate",
      "locator": {
        "regime": "markdown-heading-path",
        "value": ["Section", "Subsection"]
      },
      "payload": {
        "statement": "...",
        "kind": "claim",
        "confidence": "..."
      }
    },
    {
      "unit_id": "u002",
      "disposition": "skip",
      "reason": {
        "code": "non_claim",
        "detail": "Background framing, not a proposition."
      },
      "locator": {
        "regime": "markdown-heading-path",
        "value": ["Section"]
      }
    }
  ]
}
```

Required top-level fields:

- `schema_version`
- `source`
- `artifact`
- `units`

Required source fields:

- `kind`
- `slug`
- `path`
- `content_hash`

Supported P2 source kind:

- `prose-source`

Supported P2 dispositions:

- `candidate`: a promotable unit whose `payload` validates through the existing
  `StatementCandidate` parser/model. If the implementation needs a thin envelope around
  that payload, the envelope belongs to the decomposition parser, not to a new
  prose-specific candidate model.
- `skip`: a reviewed unit that should not be promoted, with a reason code.
- `stale`: a system-derived unit state for a unit from an earlier artifact generation
  that is absent from the latest decomposition.

Supported P2 locator regimes:

- `markdown-heading-path`: identifies a Markdown section by heading path.
- `markdown-heading-path-with-quote`: identifies a Markdown section plus quoted text
  inside that section.

The implementation plan may refine names if existing code has a stronger local naming
pattern, but P2 should not add offset-based selectors for internal Markdown.

## 6. CLI/data flow

P2 adds an offline ingest workflow. Command names can be adjusted to match local CLI
style during implementation, but the operations should remain separate:

```text
science-tool annotate ingest-prose-decomposition path/to/decomposition.json
science-tool annotate check --source prose-source:<slug>
science-tool annotate promote --source prose-source:<slug> --unit u001
```

### 6.1 Ingest

Ingest should:

- Parse JSON and validate schema version 1.
- Verify the source kind is `prose-source`.
- Verify the source path exists and is Markdown.
- Compute or verify the Markdown content hash.
- Resolve or create `prose-source:<slug>`.
- Persist a new artifact generation.
- Compare prior unit identities for the same source with the new artifact and record
  missing prior units as stale.

Ingest should not partially persist state if validation fails.

### 6.2 Check

Check should:

- Load the latest decomposition artifact for a `prose-source`.
- Resolve locators through `InternalProseAdapter`.
- Report promotable candidates.
- Report skip records with reasons.
- Report stale units.
- Report unresolved locators, quote mismatches, and invalid payloads.

The old offset/hash source-change check is not meaningful for the regenerable locator
regime. P2 must add a regime-appropriate check path instead of forcing internal prose
through `.source.md`/`.anno.trig` assumptions.

### 6.3 Promote

Promote should:

- Select candidate units by artifact/unit identity.
- Reject non-candidate units.
- Reject stale units.
- Resolve the locator against the current Markdown source.
- Create downstream proposition/provenance records through the existing graph-layer
  machinery.
- Record provenance to both `prose-source:<slug>` and the decomposition artifact/unit
  identity.

Promotion must not trust raw agent output directly. It promotes only from validated,
persisted decomposition units whose locators still resolve.

## 7. Validation and error handling

P2 should fail early for structural and identity problems.

Hard failures:

- Invalid JSON.
- Unsupported `schema_version`.
- Missing required source fields.
- Source kind other than `prose-source`.
- Source path missing or not Markdown.
- Content hash mismatch unless the command explicitly allows ingesting against changed
  prose.
- Duplicate `unit_id` within one artifact.
- Unknown disposition.
- Candidate payload cannot be parsed as the expected statement-candidate shape.
- Attempting to promote a non-candidate unit.
- Attempting to promote a stale unit.
- Attempting to promote a unit whose locator no longer resolves.

Check/report findings:

- Locator cannot resolve to Markdown text.
- Quote text differs from located source text.
- Skip reason code is unknown but structurally valid.
- Earlier artifact unit is missing from the latest artifact.
- Candidate is structurally valid but missing optional review-quality metadata.

State updates should be transactional where possible. A failed ingest should not leave a
half-created source entity or half-persisted artifact.

## 8. Testing

P2 tests should cover contracts and failure modes, not model quality.

Core tests:

- Artifact parser accepts a valid schema v1 artifact.
- Parser rejects malformed JSON, unsupported versions, duplicate unit IDs, unknown
  dispositions, and invalid candidate payloads.
- `InternalProseAdapter` resolves supported Markdown locators.
- Ingest auto creates a missing `prose-source:<slug>`.
- Ingest links an existing `prose-source:<slug>` without overwriting curated metadata.
- Check reports candidate, skip, stale, and unresolved units.
- Promote accepts only valid candidate units.
- Promote records provenance to `prose-source:<slug>` plus artifact/unit identity.
- Re-ingest marks missing previous units stale without retiring propositions or rewriting
  old artifacts.

Existing paper annotation behavior must remain unchanged.

## 9. Out of scope

P2 does not include:

- Live LLM/model calls.
- Natural-systems campaign or pilot content.
- YAML/model-record prose decomposition.
- Reworking `.anno.trig`.
- Offset anchoring for internal Markdown.
- Claim retirement semantics based on stale units.
- Broad source-ingest framework for every future source kind.
- Domain grounding or belief-as-grounding implementation.
- Prose health rendering or unbacked-claim styling.

## 10. Alternatives considered

### Minimal adapter patch

This would add `InternalProseAdapter` and enough CLI wiring to ingest JSON, resolve
Markdown locators, and promote candidates.

It was rejected as the primary shape because it risks baking internal-prose behavior into
adapter methods and CLI paths before the artifact contract is explicit.

### Artifact-led source framework

This is the chosen design.

The decomposition artifact is the center of P2. A small source-neutral artifact
parser/validator, prose-source resolution, `InternalProseAdapter`, and check/promote wiring
give the right long-term boundary while staying within P2 scope.

### General source-ingest framework

This would design a broad ingest framework now for future papers, books, talks, YAML
records, generated artifacts, and internal prose.

It was rejected for P2 because it would mix future unknowns into a phase that only needs to
prove the internal Markdown path.

## 11. Open implementation choices for the plan

These are intentionally left for the implementation plan, where they can be tied to local
code structure:

- Exact CLI command names.
- Concrete artifact storage path and file naming convention.
- Concrete source-entity file path for `prose-source` records.
- Exact names for locator regime enum members.
- Whether stale marks are materialized as explicit latest-artifact units, side metadata,
  or a small artifact index.

These choices should not change the design invariants above.
