# Natural-systems prose epistemics application design

**Status:** draft design, 2026-06-19.

**Parent:** `~/d/science/docs/plans/2026-06-17-prose-epistemics-umbrella-design.md`

**Framework predecessors:**
- P2 internal prose:
  `~/d/science/docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`
- P3 domain grounding:
  `~/d/science/docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-design.md`
- P4 health coverage:
  `~/d/science/docs/plans/2026-06-18-prose-epistemics-p4-health-coverage-design.md`

**Scope of this document:** downstream application only. The P1-P4 framework exists in
`science`; this design applies it to `~/d/natural-systems/`. It does not introduce new
prose-epistemics framework APIs, new source kinds, live LLM execution, or a dual-language
belief core.

---

## 1. Goal

Use the shipped prose-epistemics framework to make natural-systems prose epistemically
auditable at statement level.

The application loop is:

```text
natural-systems Markdown prose
  -> offline decomposition JSON
  -> science annotate ingest-prose-decomposition
  -> science annotate promote-prose-decomposition --source ... --unit ...
  -> npm run kg:build
  -> science annotate ground-prose-decomposition --floor ...
  -> science annotate build-prose-health --write
  -> natural-systems health/rendering consumes prose-health.json
```

The first outcome is not a green health gate. It is a trustworthy coverage ramp:

- which in-scope prose has been decomposed
- which candidate claims have been promoted
- which promoted claims are grounded at the configured belief floor
- which claims are unbacked, below the floor, skipped, stale, or still unpromoted
- which evidence-writing work should happen next

## 2. Boundary

This is content and integration work over an existing framework.

In scope:

- create `data/prose-health/` and a natural-systems P4 manifest
- choose an initial tranche of Markdown sources
- produce offline decomposition artifacts for those sources
- ingest and check those artifacts with P2
- promote selected domain candidate units into propositions, one `--unit` invocation at a
  time unless the application plan adds a wrapper
- materialize the science graph for the project
- build P3 grounding reports for manifest sources
- build the P4 prose-health artifact
- wire natural-systems health and/or prose rendering to read P4 JSON
- author or ingest evidence lines for high-priority unbacked propositions

Out of scope:

- live model orchestration for decomposition
- new locator regimes or non-Markdown source support
- changing the P2/P3/P4 schemas before a concrete consumer break appears
- TS recomputation of belief or grounding
- making strict grounding a pass/fail release gate
- full natural-systems migration as a single atomic task

## 3. Long-term shape

The long-term natural-systems system should have one epistemic spine:

1. Natural-systems prose is authored normally.
2. A manifest declares which prose sources are inside the epistemic denominator.
3. P2 decomposition artifacts provide stable unit identity, quote locators, skip reasons,
   stale state, and promotion links.
4. Promoted propositions and evidence lines live in the science entity model.
5. The materialized graph is the source for belief aggregation.
6. P3 reads belief and writes per-source grounding reports.
7. P4 writes one project-level health artifact.
8. Natural-systems UI/health/rendering reads the P4 artifact and never reimplements P2/P3
   logic.

The ideal end state is boring: one authored-prose manifest, one materialized graph, one
prose-health artifact, and consumers that treat missing epistemic work as visible backlog.

## 4. Initial tranche

Start with a small, representative manifest rather than the whole project.

Recommended first tranche:

- one conceptual overview page
- one geology/physics-heavy explanatory page
- one page known to mix domain claims with project/meta commentary

The tranche should be large enough to exercise all row types (`candidate`, `skip`,
promoted, unpromoted, unbacked, below-floor if evidence exists), but small enough that
manual review of every decomposition unit is realistic.

The P4 manifest should live in natural-systems at:

```text
data/prose-health/manifest.json
```

Each entry should use `prose-source:<slug>` refs, project-relative paths, and stable display
titles. The manifest is the denominator authority; sources outside it do not count.

## 5. Decomposition campaign

Decomposition remains offline-agent output.

The artifact contract is the shipped P2 schema, especially:

- `schema_version: 1`
- `source.kind: "prose-source"`
- candidate units carrying the existing `StatementCandidate` payload fields
- skip units carrying the canonical P2 reason codes: `meta_commentary`, `not_a_claim`,
  `duplicate_or_restatement`, `citation_or_reference_only`, `out_of_scope`, and
  `unresolved_or_malformed`
- candidate quotes living in `payload.exact` / `payload.prefix` / `payload.suffix`, not in
  the unit locator

The P2 design's §5 schema and §5.1 skip vocabulary are the source of truth:
`~/d/science/docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`.

For each manifest source:

1. Generate a P2 decomposition JSON artifact from the current Markdown.
2. Include candidate units for domain claims.
3. Include skip units for meta commentary, non-claims, headings, transitions, or other
   excluded spans.
4. Use the P2 skip vocabulary rather than ad hoc reason strings.
5. Ingest with `science annotate ingest-prose-decomposition`.
6. Run `science annotate check-prose-decomposition`.
7. Review unresolved locators, ambiguous heading paths, stale units, and skip/candidate
   classification.

Ingest persists artifacts under the framework convention:

```text
data/prose-decompositions/<slug>/
```

The implementation plan may choose where temporary offline-agent output files are staged
before ingest, but persisted generations and indexes should use the P2 store path above.

The decomposition review is the quality gate. Promotion should not be used to compensate
for weak decomposition. If the agent missed spans or classified meta/domain incorrectly,
regenerate or edit the artifact and re-ingest.

## 6. Promotion campaign

Promotion is the point where natural-systems prose claims become science propositions.

Promotion policy:

- promote only domain candidate units
- prefer linking to an existing proposition when `decide_all` finds the same claim
- mint new propositions for real domain claims not yet represented
- do not promote skip units
- do not auto-retire stale promoted propositions
- treat unpromoted candidates as backlog, not as invisible failure

`science annotate promote-prose-decomposition` promotes exactly one unit per invocation:

```text
science annotate promote-prose-decomposition \
  --source prose-source:<slug> \
  --unit <unit_id> \
  --apply
```

For a tranche with many reviewed candidates, the application plan should either document a
small operator loop around that command or add a natural-systems-local wrapper. The
framework command should remain precise and auditable.

The first pass should optimize for accurate proposition identity over quantity. A small set
of correctly promoted claims is more useful than a large set of noisy propositions.

## 7. Evidence and grounding campaign

P3 can only report evidence that exists in the materialized graph. Most early rows are
expected to be `unbacked` or `unpromoted`.

Grounding uses `science annotate ground-prose-decomposition --floor ...`. The shipped
default floor is `supported`, but the natural-systems campaign should pin the selected floor
in project configuration or an explicit operator script before artifacts are treated as
reproducible. The P4 manifest does not carry the floor.

Evidence work should be driven by P4:

1. Build P4 health.
2. Sort unbacked promoted propositions by importance to the prose.
3. For each priority proposition, identify the domain source paper(s) needed.
4. Ingest or create the source entities required for provenance.
5. Author evidence lines targeting the proposition.
6. Re-run `npm run kg:build`.
7. Re-run P3 grounding and P4 health.

This creates the coverage ramp. The metric improves because domain evidence becomes real,
not because the health calculation relaxes.

## 8. Graph contract verification

The umbrella identified a possible two-builder problem. The current natural-systems state
appears mostly converged: `npm run kg:build` invokes `uv run science graph build
--project-root .`, and P3's grounding command defaults to the same `knowledge/graph.trig`
path.

For the first application tranche, the action is verification rather than architecture:

- confirm `npm run kg:build` still produces the `knowledge/graph.trig` consumed by P3
- confirm the graph has the named knowledge and provenance graphs P3 expects
- confirm natural-systems TS health checkers read that graph rather than writing a competing
  one

If those checks hold, there is no builder collision to resolve for the pilot. The long-term
preference remains one graph-building spine.

## 9. Health and rendering integration

Natural-systems should consume P4 JSON, not reconstruct health from P2/P3 internals.

The initial integration should be read-only:

- `npm run health` reports prose epistemics summary from `data/prose-health/prose-health.json`
- missing/stale/invalid P4 artifact is a visible health finding with the next command to run
- no TS code computes belief, resolves evidence, or scans P2 stores

`science health` already reads the P4 artifact through the shipped `prose_epistemics`
section. The new downstream work is natural-systems' TS `npm run health` reader and any
rendered-prose consumer.

Rendered prose styling can follow once the JSON contract is stable against real content.
The renderer should use P4 unit rows and locators to mark:

- unpromoted claims
- unbacked promoted claims
- below-floor promoted claims
- stale units
- skipped spans only if the authoring UI needs review affordances

Styling is a consumer feature, not a grounding source of truth.

## 10. Operating workflow

The steady-state operator loop should be explicit and repeatable:

```text
1. Edit prose.
2. Regenerate offline decomposition artifact for changed sources.
3. Ingest and check P2 artifacts.
4. Promote reviewed candidate units one at a time, or run the documented project wrapper.
5. Run `npm run kg:build`.
6. Build P3 grounding reports with the pinned floor.
7. Build P4 prose health.
8. Run natural-systems health/rendering.
9. Author evidence for the highest-value unbacked claims.
```

Stale marking is expected after prose edits. It is not a failure by itself; it is the signal
that decomposition and grounding artifacts need to be refreshed.

## 11. Validation

The implementation plan should verify the campaign with a pilot tranche before expanding.

Minimum pilot checks:

- `data/prose-health/` exists and contains the pilot manifest.
- P4 manifest loads and names only intended sources.
- Every manifest source has an ingested P2 latest artifact.
- P2 check resolves all candidate locators.
- Promotion links or mints expected propositions.
- Materialization succeeds with all `prose-source:` refs resolvable.
- P3 grounding reports write for each manifest source.
- P4 health writes one artifact and shipped `science health` reads it.
- Natural-systems health consumes the P4 artifact without knowing P2/P3 internals.
- The pilot produces a usable backlog of unpromoted and unbacked units.

Regression checks:

- editing prose and re-ingesting preserves promotion links by fingerprint when the quote is
  unchanged
- renumbered `unit_id`s do not break P3/P4 joins
- stale units do not inflate current denominators
- missing evidence is reported as `unbacked`, not silently dropped

## 12. Risks

**Decomposition quality.** The first real risk is not code; it is whether candidate/skip
classification is consistently useful. Keep the tranche small until review proves the
offline prompt contract is good enough.

**Evidence scarcity.** The spike found a level mismatch and little domain evidence in the
existing graph. Early health will look sparse. That is expected and useful.

**Graph contract drift.** P3 requires the named graph structure used by `science graph
build`. The application plan must verify natural-systems' existing graph path before running
the campaign.

**Consumer overreach.** Natural-systems should not reimplement belief, promotion state, or
fingerprint joins in TS. P4 is the consumer contract.

## 13. Open decisions for the implementation plan

- Which three to five Markdown sources form the pilot manifest.
- Where temporary offline-agent output files are staged before ingest. Persisted P2 state
  should use `data/prose-decompositions/<slug>/`.
- Where the grounding floor is pinned for repeatable natural-systems runs: project config,
  a committed operator script, or an explicit generated-artifact build command.
- How to record the verified graph command/path in the pilot workflow. Expected baseline:
  `npm run kg:build` produces `knowledge/graph.trig`, which P3 consumes by default.
- Whether batch-promotion ergonomics are handled by documentation, a shell loop, or a
  natural-systems-local wrapper around the one-unit framework command.
- Whether the first health integration is CLI-only, rendered-prose styling, or both.
- Which evidence-authoring queue format natural-systems should use for unbacked claims.
- Whether the pilot commits generated P2/P3/P4 artifacts or treats them as reproducible
  build outputs.
