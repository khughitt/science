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

This resolves the umbrella's tentative `doc:`/`prose:` naming in favor of
`prose-source:` because the node is not an authored document product; it is the operational
source record that propositions cite. Adding it is real model work: P2 must add the kind
descriptor/profile entry and pass the existing kind reconciliation gates instead of using
an ad hoc resolver branch. Reusing an epistemic prose kind such as `report` or
`discussion` would blur source identity with authored conclusions, which is exactly the
separation this phase needs.

### 2.2 Input scope

P2 supports Markdown sources only.

YAML/model records and other prose containers are deferred until a later phase has an
actual consumer. This keeps the locator regime small enough to validate rigorously.

### 2.3 Artifact shape

P2 introduces a new JSON decomposition artifact. It does not reuse `.anno.trig`.

The long-term shape is one source-neutral decomposition artifact family with `units[]` as
a discriminated union. Candidate, skip, and stale records are logical peer unit shapes
inside that family. Agent-submitted P2 artifacts normally contain candidate and skip
units; stale units are system-derived during re-ingest when earlier units are missing from
the latest decomposition. The physical representation of stale state can be an explicit
unit, side metadata, or an artifact index, but check/promotion should expose it through
the same logical unit model. The existing `StatementCandidate` shape should remain the
candidate payload, not be replaced by a prose-specific candidate model.

For candidate units, the quote has one authoritative home: the `StatementCandidate`
payload's `exact`/`prefix`/`suffix` fields. The unit-level Markdown locator identifies the
section/container; the adapter composes the section locator with the candidate quote
fields to resolve the current text. Skip units have no `StatementCandidate` payload, so
they may carry their own quote fields in the locator when span-level review is needed.
Candidate units must not put a second, competing quote in the locator.

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

The source-level `content_hash` is a whole-document freshness fingerprint, not a span
anchoring mechanism. It answers "was this decomposition produced against the current
Markdown?" and does not resurrect the offset/re-anchoring stack ruled out by the umbrella.
The hash can make ingest fail by default when prose changed, with an explicit
allow-changed mode for controlled re-ingest, but it is never used to repair or re-anchor
individual spans.

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

The P1 `TextSourceAdapter` interface is still path-keyed:
`handles(source_md: Path)`, `source_ref(source_md: Path)`, and `extract(...)`.
P2 should not pretend that this is already the full artifact-led interface. The adapter
fit is:

- `InternalProseAdapter` implements path handling for Markdown sources where useful.
- Artifact ingest is the `regenerable` counterpart of paper `extract`; it replaces the
  offset-anchoring step instead of calling paper-style `.anno.trig` extraction.
- P2 adds explicit artifact/source-metadata methods around the adapter, such as resolving
  `source_ref` from artifact source metadata and resolving a unit locator against source
  text.
- The current `extract(...)` method may remain unimplemented for `InternalProseAdapter`
  unless the implementation plan deliberately generalizes the ABC.

The exact method names are an implementation-plan choice, but the boundary is not: paper
extract persists offset-anchored annotations; prose ingest persists a regenerable
decomposition artifact.

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
        "type": "proposition",
        "exact": "Basalt flows record the cooling history of the ridge.",
        "prefix": "In this setting, ",
        "suffix": " The surrounding strata constrain the timing.",
        "stance": "asserted",
        "subject": "basalt flows",
        "object": "cooling history of the ridge",
        "subject_concept": null,
        "object_concept": null
      }
    },
    {
      "unit_id": "u002",
      "disposition": "skip",
      "reason": {
        "code": "not_a_claim",
        "detail": "Background framing, not a proposition."
      },
      "locator": {
        "regime": "markdown-heading-path-with-quote",
        "value": ["Section"],
        "quote": {
          "exact": "This section motivates the framing.",
          "prefix": "",
          "suffix": ""
        }
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
- `stale`: a logical, system-derived unit state for a unit from an earlier artifact
  generation that is absent from the latest decomposition. Agent-submitted artifacts do
  not normally contain stale units.

Supported P2 locator regimes:

- `markdown-heading-path`: identifies a Markdown section by heading path.
- `markdown-heading-path-with-quote`: identifies a Markdown section plus quoted text
  inside that section. In P2 this is for skip units or other units without a
  `StatementCandidate` payload; candidate units use `payload.exact` / `payload.prefix` /
  `payload.suffix` as their within-section quote.

The implementation plan may refine names if existing code has a stronger local naming
pattern, but P2 should not add offset-based selectors for internal Markdown.

### 5.1 Skip reason vocabulary

P2 owns the initial skip-reason vocabulary because P4's coverage denominator depends on
seeing what the decomposition reviewed but did not promote.

Required P2 skip codes:

- `meta_commentary`: prose about the model, method, narrative structure, or project
  framing rather than a domain proposition.
- `not_a_claim`: headings, transitions, rhetorical framing, lists without truth-apt
  content, or other text that is not a proposition.
- `duplicate_or_restatement`: repeated content already represented by another candidate
  in the same artifact.
- `citation_or_reference_only`: bibliography, citation-only, or pointer text that does
  not itself assert the domain claim.
- `out_of_scope`: truth-apt text intentionally outside the P2 extraction target.
- `unresolved_or_malformed`: text the agent recognized as relevant but could not express
  as a valid candidate or located skip.

Meta-vs-domain discrimination is recorded through this vocabulary, not through a new
persistent field on propositions. Unknown skip codes should fail artifact validation in
P2; extension vocabularies can be designed later when there is a concrete consumer.

## 6. CLI/data flow

P2 adds an offline ingest workflow. Command names can be adjusted to match local CLI
style during implementation, but the operations should remain separate:

```text
science-tool annotate ingest-prose-decomposition path/to/decomposition.json
science-tool annotate check --source prose-source:<slug>
science-tool annotate promote --source prose-source:<slug> --unit u001
```

### 6.1 Ingest

Ingest is the regenerable counterpart of paper `extract`: paper extraction anchors
candidates into `.anno.trig`; prose ingest validates an offline decomposition artifact
and persists its regenerable locator/unit state.

Ingest should:

- Parse JSON and validate schema version 1.
- Verify the source kind is `prose-source`.
- Verify the source path exists and is Markdown.
- Compute or verify the Markdown content hash as a whole-source freshness check.
- Resolve or create `prose-source:<slug>`.
- Persist a new artifact generation.
- Compare prior unit identities for the same source with the new artifact and record
  missing prior units as stale.

Ingest should validate fully before writing. The safe write invariant is:
validate artifact and source first, mint-or-link the source entity as an idempotent upsert,
then persist the artifact generation. If artifact persistence fails after source creation,
rerun is safe because source resolution is idempotent and conservative.

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
- Whole-source content hash mismatch unless the command explicitly allows ingesting
  against changed prose.
- Duplicate `unit_id` within one artifact.
- Unknown disposition.
- Unknown skip reason code.
- Candidate unit contains a competing quote in its unit-level locator.
- Candidate payload cannot be parsed as the expected statement-candidate shape.
- Attempting to promote a non-candidate unit.
- Attempting to promote a stale unit.
- Attempting to promote a unit whose locator no longer resolves.

Check/report findings:

- Locator cannot resolve to Markdown text.
- Quote text differs from located source text.
- Earlier artifact unit is missing from the latest artifact.
- Candidate is structurally valid but missing optional review-quality metadata.

The freshness hash is not a span re-audit. A matching hash is evidence that the artifact
was produced from the current document; a mismatch means the artifact may be stale and
requires an explicit operator choice.

## 8. Testing

P2 tests should cover contracts and failure modes, not model quality.

Core tests:

- Artifact parser accepts a valid schema v1 artifact.
- Parser rejects malformed JSON, unsupported versions, duplicate unit IDs, unknown
  dispositions, unknown skip reason codes, competing candidate locator quotes, and
  invalid candidate payloads.
- Candidate units compose heading-path locators with `StatementCandidate` quote fields.
- Skip units can use heading-path-with-quote locators.
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
- Span-level content-hash re-audit or automatic re-anchoring for internal Markdown.
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
- Exact kind-descriptor fields for `prose-source`, including home, category, strategy,
  status set, and reconciliation tests.
- Exact names for locator regime enum members.
- Exact adapter method names for artifact-led source-ref and locator resolution, given
  the current P1 ABC is path-keyed.
- Whether system-derived stale marks are materialized as explicit latest-artifact units,
  side metadata, or a small artifact index.

These choices should not change the design invariants above.
