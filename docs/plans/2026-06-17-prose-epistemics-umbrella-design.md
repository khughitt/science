# Prose epistemics — umbrella design

**Status:** umbrella design approved (brainstorming) 2026-06-17. This is the big-picture
tie-together; each phase below gets its own spec → plan in a later session, and the
natural-systems application gets a separate downstream plan.

**Scope of this document:** the long-term shape only — the architectural seam, the
refactor strategy, the layer model, and the phase sequencing. It deliberately does *not*
specify per-phase implementation detail.

**Predecessors / context:**
- Spike findings: `~/d/science/docs/plans/2026-06-17-prose-grounding-spike-findings.md`
- Spike design: `~/d/science/docs/plans/2026-06-16-prose-grounding-spike-design.md`
- The sub-article annotation arc and proposition synthesis (Phase 4a–4c) — the machinery
  this generalizes.

---

## 1. Original motivation

The proposition / question / hypothesis work so far has targeted **external** knowledge
sources (research articles, books): decompose someone else's text into units of thought,
ground them, promote them into the epistemic graph.

The new use case points that machinery **inward**, at our own rigorous prose.
`~/d/natural-systems/` contains extensive prose intended to be rigorous. If we can
decompose that prose into its constituent statements / propositions, we can assess prose
**accuracy and quality at the individual statement level**, extend `npm run health` to
report not just prose **coverage** but how thoroughly each statement is **grounded in
evidence**, and **call out unbacked statements** (e.g. by stylizing them in rendered prose).

Two refinements shaped the program:

1. **Source-agnostic by design.** The text-processing machinery must be separable from the
   entity/graph system so the same pipeline applies to text from *any* source — papers,
   books, our own prose — without re-implementation.
2. **Long-term shape over quick wins.** Get the architecture right first (this umbrella),
   then build it out in phases.

## 2. What the spike established (and what changed because of it)

The feature-first spike (findings doc above) ran the full decompose → link → ground loop
over two natural-systems slices. Headline: **0 of 64** prose claims linked to any existing
entity — a **level mismatch**. The existing epistemic graph holds *meta-modeling* claims
(morphisms, generator bases, fit audits); the prose asserts *domain* facts
(physics/geology). Consequences that this design bakes in:

- For the domain layer the internal case is **extract-and-promote** (like the paper
  pipeline, sourced from our own prose), **not** check-against-an-existing-graph.
- **Grounding = belief** (`aggregate_belief`), not `bearsOn`/provenance density.
- **Almost nothing is backed initially** → the health metric is a **coverage ramp /
  promotion forcing-function**, not a red/green gate.
- **Verbatim-locator decomposition is reliable** (0/64 mismatches); the
  offset/re-anchoring stack is **unnecessary for internal mutable prose**.
- **Python-only is confirmed** — TS consumes JSON/markdown artifacts; the dual-language
  shared core is deferred.

## 3. Architecture — the seam (directive #2 made literal)

The system splits at the **candidate artifact** into two layers. The text layer is
replaceable per source; the graph layer never changes.

```
 TEXT LAYER (per-source adapters)          │  GRAPH LAYER (source-agnostic, exists today)
                                           │
 source ──▶ normalized repr ──▶ decompose ─┼─▶ candidates.json ──▶ extract / persist
   │            │                 (agent)  │     (THE SEAM)              │
   fetch?     anchor?                      │   units-of-thought       promote (mint / link)
   seed?      (im/mutable)                 │                             │
                                           │                          synthesize
                                           │                             │
                                           │                       aggregate_belief
```

### 3.1 Text layer — per-source adapters with declared capabilities

Everything that turns a *specific kind of source* into source-neutral candidates. Three
capabilities, each opt-in and **declared** (no `isinstance`/name branching — the same
"declared policy" pattern the Source Compiler used for `StorageAdapter`):

- **fetch** — acquire the text. Papers fetch via DOI/PMID; internal prose reads repo files.
- **anchor** — produce locators. *Immutable* sources (papers, books) anchor with
  `oa:TextQuoteSelector`/offsets because the text is not ours and must survive re-audit.
  *Mutable* internal prose uses cheap **regenerable** locators (heading/section + quoted
  text) and **opts out** of the anchoring stack entirely (spike finding 6).
- **seed** — entity-mention pre-annotation. PubTator3 for bio papers; nothing for prose.

Each adapter also declares its **`source_ref` scheme** (`paper:<citekey>`, `doc:<slug>`, …),
which the graph layer consumes as an injected string.

### 3.2 Candidate artifact — the seam

The frozen `candidates.json` contract (`StatementCandidate` / `FigurativeCandidate`).
Nothing downstream knows or cares what produced it. This already exists and is already
source-neutral; the program **formalizes it as the boundary** rather than inventing a new one.

### 3.3 Graph layer — source-agnostic (already true today)

`extract → promote → synthesize → aggregate_belief`. The map confirmed this layer is
already source-agnostic: `promote.apply_candidates` takes `paper_ref` as an injected
string, mint logic never reaches back into `.source.md`, and `aggregate_belief` runs
standalone with no graph materialization. The only change needed is that the `source_ref`
becomes **adapter-supplied** rather than paper-derived.

## 4. The refactor — one core, papers = one adapter

Decision (brainstorming): generalize the shipped pipeline around a source-agnostic core;
**paper becomes one `SourceAdapter` among several**, not a special case.

- Introduce a `SourceAdapter` abstraction carrying the **declared capability profile**
  from §3.1.
- Re-seat today's pipeline as **`PaperSourceAdapter`** (DOI/PMID fetch → `.source.md`,
  `TextQuoteSelector` anchoring, PubTator seeding, `paper:<citekey>` ref). This is a
  **behavior-neutral extraction refactor** — papers must behave byte-for-byte as before.
- **`InternalProseAdapter`** (P2) declares: no fetch (reads repo files), no anchor
  (mutable → regenerable locators), no seed, `doc:`/`prose:` ref scheme.
- Books, talks, datasets, etc. become future adapters for free.

The three paper-coupled spots that move behind the adapter boundary: `persist-source`
(fetch + license gating), `extract` (`TextQuoteSelector` anchoring in `.source.md`), and
`pubtator` (BioC seeding). The graph layer is untouched.

## 5. The domain-proposition layer & the grounding bar

- **Propositions are domain-level by construction.** Every `ClaimLayer` value
  (`empirical_regularity`, `causal_effect`, `mechanistic_narrative`, `structural_claim`)
  is a domain claim type. The domain-proposition layer is simply *propositions minted from
  our own prose*, produced by the P2 adapter flowing through the unchanged graph layer.
  The existing meta entities (questions/hypotheses/interpretations) stay as they are.
- **Meta vs. domain is an extraction-time discrimination, not a new field.** The decompose
  agent simply does not emit meta-commentary as domain candidates (natural-systems prose
  mixes both). **No `ClaimScope` field** is added — we revisit only if a real need for
  meta-propositions appears. (Deferred option, §8.)
- **Grounding bar = strict; grounding = belief.** A prose claim is grounded **iff** it
  links to a domain proposition carrying real belief support from `aggregate_belief` (a
  magnitude at/above a configured floor). This explicitly rejects (a) provenance/`bearsOn`
  density as grounding, and (b) recitation of a fact inside a meta-entity. Building the
  domain layer presupposes the strict bar.
- **"Almost nothing is backed" is the honest start.** Strict grounding only yields signal
  once domain **evidence-lines** and domain **source papers** exist. The metric is a
  **coverage ramp / forcing-function**, never an all-red gate (spike finding 4).

## 6. Phase breakdown

Each phase gets its own spec → plan in a later session.

| Phase | Delivers | Depends on |
|---|---|---|
| **P1 — Source-agnostic core** | The §4 refactor. `SourceAdapter` + declared capability profile; re-seat today's pipeline as `PaperSourceAdapter`; formalize the candidate artifact as the seam. **Behavior-neutral for papers.** No new content — pure shape. | — |
| **P2 — Internal-prose adapter** | `InternalProseAdapter` (reads repo prose, mutable, regenerable locators, no anchor/seed) + a decompose-agent variant that discriminates meta vs. domain. Output: domain propositions minted from our own prose through the *unchanged* graph layer. | P1 |
| **P3 — Domain grounding** | Belief-as-grounding read; the evidence-line authoring path (closing the `_lift_evidence_line` structural-defaults gap, spike finding 8); domain-source ingestion so `aggregate_belief` has real inputs. Makes "grounded in evidence" honest. | P2 |
| **P4 — Health coverage-ramp** | A `prose-health.json`-style artifact (Python-produced, TS-consumed) carrying per-claim grounding; the coverage-ramp metric; stylized marking of unbacked claims in rendered prose. | P3 |

**Dependency chain is linear** (P1 → P2 → P3 → P4). Each phase produces working, testable
software on its own: P1 is a behavior-neutral refactor verifiable by the existing paper
suite; P2 mints propositions; P3 grounds them; P4 surfaces them.

## 7. Downstream natural-systems application (separate plan)

Project-specific, rides on P1–P4, planned separately:

- Full migration of natural-systems to the science model.
- Ingest its (sparse) domain papers (1/74 were domain-relevant) — feeds P3 belief inputs.
- Run the extract → promote campaign over its prose (P2) → domain propositions.
- Author the domain evidence corpus (P3) → real belief.
- Set the concrete grounding floor (the strict-bar magnitude threshold).
- Wire `npm run health` to the P4 artifact.
- Resolve the **two-graph-builders duplication**: natural-systems' TS-built
  `knowledge/graph.trig` vs. `science materialize` (a convergence the larger program owes).

Mapping to the spike's A/B/C program: **A** (epistemic convergence) ≈ P2 + P3 + this NS
plan; **B** (shared cross-language core) **deferred**; **C** (prose grounding in health) ≈ P4.

## 8. Non-goals (recorded so they don't creep in)

- **No dual-language core** (sub-project B). Python-only; TS consumes JSON/markdown
  artifacts (the `prose-health.json` pattern). Revisit only if a TS consumer needs to
  *compute* belief/resolution rather than read it.
- **No anchoring stack for mutable internal prose** — no offsets, re-anchoring, or
  content-hash re-audit on text we own and regenerate.
- **No `ClaimScope` field** unless a concrete need for meta-propositions appears;
  discriminate at extraction instead.
- **No new candidate contract** — formalize and reuse the existing one.

## 9. Open decisions deferred to phase specs

- The exact `SourceAdapter` interface surface and where it lives (P1 spec).
- The regenerable-locator format for mutable prose, and how re-decomposition reconciles
  with already-minted propositions when prose changes (P2 spec).
- The grounding-floor magnitude and the precise coverage-ramp metric shape (P3/P4 specs).
- Whether the decompose-agent meta/domain discrimination is a prompt concern or needs a
  lightweight classifier step (P2 spec).
