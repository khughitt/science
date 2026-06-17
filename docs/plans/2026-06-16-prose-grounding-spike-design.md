# Prose grounding — feature-first spike (design)

**Status:** design approved (brainstorming) 2026-06-16; pending user review of this
spec, then implementation plan.
**Scope:** a deliberately throwaway *learning* spike. Its deliverable is a friction
log, not a shipped feature.
**Predecessors / context:** builds on the sub-article annotation arc
(`docs/plans/2026-06-14-sub-article-annotation-spec.md`) and proposition
synthesis (`docs/plans/2026-06-16-proposition-synthesis-phase4c-design.md`), but
points that machinery *inward* at our own prose.

---

## 1. Original motivation

The proposition / question / hypothesis work so far has targeted **external**
knowledge sources (research articles + books): decompose someone else's text into
units of thought, ground them, promote them into the epistemic graph.

The proposed new use case is to apply the same *representations* **internally**, to
our own rigorous prose. `~/d/natural-systems/` contains extensive prose that is
intended to be rigorous — textual representations of entities described in the
system. If we can decompose that prose into its constituent statements /
propositions, we can assess prose **accuracy and quality at the individual
statement level**. We could then extend `npm run health` to assess not only
prose **coverage** (which it does today) but also how thoroughly each statement has
been **vetted** and whether it is **grounded in evidence** — helping ensure our
articles are as accurate as possible, and letting us **call out statements that are
not backed** (e.g. by stylizing them in rendered prose).

## 2. Reframing (what brainstorming established)

### 2.1 The internal case is the *inverse* of the paper pipeline

- **External papers:** the text is the source of truth. Propositions are *extracted
  from* it and *promoted into* the graph. The heavy anchoring stack
  (`oa:TextQuoteSelector`, BioC offset maps, fuzzy re-anchoring, content-hash
  re-audit, TriG sidecars) exists precisely because the source text is **immutable
  and not ours**.
- **natural-systems prose:** the graph is the source of truth, and the prose is a
  *derived rendering* of it. We are not mining new knowledge from the essays — we
  are checking that **each claim in the rendering is traceable to something the
  graph already backs.**

Consequences: (a) most of the anchoring stack does not apply — the prose is ours and
mutable, so links can be regenerated rather than re-anchored; (b) the hard problem
shifts from *extraction* to *linking* (claim → existing entity), which is the same
judgment-bearing, error-prone matching the promotion phase performs; (c) "grounded
in evidence" may largely be a **read** of existing evidence/belief once a claim is
linked — not new epistemics. (Caveat: in the spike's *current* substrate that
signal barely exists yet — natural-systems has no evidence-lines or authored belief
state — so the spike treats grounding against existing targets as a provenance-density
proxy and exercises the real belief path only on hand-authored gaps; see §5.2.)

### 2.2 natural-systems is already a (partial) science project

Exploration found `science.yaml`, `science` as an editable dep in `pyproject.toml`,
**734 science entities** (192 interpretations, 125 questions, 11 hypotheses, 74
papers, …), and **2,811 `bearsOn` evidence edges**. The native model catalog
(`content/prose/models/*.yml`) is integrated via a shared `model:*` ID namespace.
Two gaps matter:

1. **No propositions.** Propositional content lives implicitly inside hypotheses and
   interpretations; there is no `entities/propositions/` layer.
2. **Two graph builders.** natural-systems has its own TS-built
   `knowledge/graph.trig` (+ `knowledge/layers/`) *and* is a science project that
   materializes its own graph — the duplication the larger program must resolve.

So "migrate natural-systems to the science model" is **finishing a partial
convergence**, not greenfield.

## 3. The larger program (context only — not this spike)

This spike sits under a three-part program. It is recorded here for orientation; the
spike is intentionally scoped to learn what these need.

| | Sub-project | What it is | Depends on |
|---|---|---|---|
| **A** | Epistemic convergence | Promote natural-systems' implicit claims into science propositions; reconcile features (science gains rich model/parameter/dimensionless-group kinds; natural-systems gains propositions/belief) | — |
| **B** | Shared cross-language core | One graph model usable from both Python and TS without drift | partly A |
| **C** | Prose grounding in `health` | Decompose prose → link claims → read belief → flag unbacked | A (reads via B) |

### 3.1 The cross-language core (B) — directional, decided after the spike

The user's prompt floated "identical TS + Python libs, checked against a common
schema." The disciplining principle: **types are safe to share; behavior is not.**
Three patterns, cheapest-risk first:

1. **Single behavior, typed clients (recommended).** Behavior (belief, resolution,
   validation) lives once in Python `science`. Schema is the SSOT
   (Pydantic → JSON Schema → codegen TS *types*). TS gets typed **read** access to
   the materialized graph/artifacts and shells out to the science CLI for
   computation. This formalizes the existing `prose-health.json` pattern; near-zero
   logic drift.
2. **Shared schema + conformance suite.** Real dual implementations bound by a shared
   golden-corpus conformance test. Best per-language ergonomics; highest ongoing
   cost; drift only caught where tests exist.
3. **Service/sidecar.** Science runs as a local service TS calls. Clean boundary;
   adds a runtime dependency to the TS build.

Whether #1 suffices is one of the questions the spike answers (friction axis 5).

## 4. Brainstorming decisions

| Decision | Choice |
|---|---|
| What "grounded in evidence" grounds against | the **science epistemic graph** (propositions + evidence/belief), not natural-systems' native model alone |
| Program sequencing | **feature-first spike** — prototype C against the existing graph to learn what A and B must hold, before committing to architecture |
| Spike prose slices | **one of each** — a narrative essay *and* a canonical YAML record |
| What claims link to | **both** — link to existing hypotheses/interpretations first; hand-author a proposition **only** where a claim has no representable existing target |

## 5. Spike design

Throwaway, all Python, branch-isolated and trivially revertible. Optimized for
learning, not production.

### 5.1 Slices

- Narrative essay: `content/prose/essay/conservation.md` (claim-dense — Noether /
  conservation laws). Stresses the hard parts: decomposing flowing prose into
  discrete claims, and noisy claim → target linking.
- Canonical record: `content/prose/models/silica-sinter.yml` (structured per-model
  sections; claims localized to one model — linking is far more tractable;
  representative of ~99% of the corpus by file count).

Either may be swapped for a slice we already distrust.

### 5.2 Flow

1. **Decompose (brain).** A throwaway agent reads each slice and emits an *untrusted*
   JSON list of discrete claims, each with a **light locator** (heading/section +
   quoted text) — deliberately **no offset anchoring**. Measures decomposition
   granularity (sentence / clause / claim).
2. **Link (brain + deterministic).** For each claim, retrieve candidate targets from
   the **existing** graph (11 hypotheses, 192 interpretations, optionally questions)
   via lexical/embedding similarity, then agent judgment selects a match or returns
   "no match." Output per claim a `target_status` (see step 6) plus the candidate set
   considered.
3. **Adjudicate (curator gold pass — independent of the linking agent).** A separate
   review by the curator (you), **not** the agent that proposed the links, assigns
   gold labels to (a) each extracted claim — is it a well-formed, in-scope claim? —
   and (b) each link decision — is the selected target correct, and is a "no match"
   genuinely unrepresentable? Without this independent step the spike cannot answer
   the linking-error axis: an agent both proposing and judging its own links only logs
   impressions. These gold labels are the measurement substrate for friction axis 2
   (mis-link and false-"no match" rates).
4. **Ground (deterministic) — two regimes, kept strictly distinct:**
   - *Existing targets → provenance-density baseline only.* natural-systems today has
     **no** evidence-lines targeting propositions and no authored belief /
     `evidence_stance` state, so for an existing hypothesis/interpretation the only
     readable signal is **provenance density**: `bearsOn` edge count/depth and
     `source_refs`. This is explicitly **not** "grounded in evidence" in the
     belief-aggregation sense — it is a proxy, labelled as such.
   - *Authored gaps → the real evidence-line/belief path* (step 5).
5. **Author the gaps (manual, instrumented) — ≥1 per slice, guaranteed.** Where a
   claim has no representable existing target, hand-author a `PropositionEntity` **and
   a scoreable `EvidenceLine` targeting it** (`target: proposition:…`), so the spike
   exercises the *real* Science belief-aggregation path — the one place "grounded in
   evidence" is tested honestly.
   - **Scoreable is mandatory.** A line carrying only `stance`/`target` materializes a
     support edge but validation flags it **unscored**, which is not an honest belief
     test. Each authored line MUST set `stance`, `target`, `source`, `evidence_type`,
     `evidence_role`, `strength`, and `independence` (+ `independence_group` where
     lines share a source).
   - **Guarantee, not conditional.** §5.3 axis 3 needs real-belief data to compare
     against the density proxy, so the spike authors **≥1 proposition + scoreable
     evidence-line per slice**. If a slice genuinely yields no unrepresentable claim,
     the curator still authors one representative claim **explicitly for the belief
     test**, marked `synthetic-for-test`; the friction log then records that the
     grounding axis for that slice rests on a synthetic line (a narrowed answer) — it
     is never silently skipped.

   **Log exactly what was missing**: the precise sub-project-A input — "the existing
   substrate couldn't hold claim X; the proposition / evidence-line needed fields Y."
6. **Report (throwaway).** Per claim, two **orthogonal** fields (never collapsed into
   one):
   - `target_status` ∈ {`linked_existing`, `authored_gap`, `no_target`}
   - `grounding` = a `(regime, strength)` pair — `regime` ∈ {`provenance_density`
     (existing target, density proxy), `belief` (authored, from real aggregation),
     `none`}; `strength` is regime-specific (e.g. density tier, or a belief label).

   Plus a small **stylized preview** re-rendering one section with ungrounded /
   weakly-grounded claims visually marked (proves the end payoff); plus the friction
   log (§5.3).

### 5.3 The friction log (the actual deliverable)

Five axes:

1. **Decomposition** — reliable, and at what granularity?
2. **Linking** — measured against the step-3 gold labels: mis-link rate and the
   false-"no match" rate (the trust-killer). Impressions don't count; the gold pass
   is what makes this axis answerable.
3. **Grounding signal** — does the provenance-density proxy (`bearsOn` / `source_refs`)
   on existing targets track real groundedness at all, and how does it compare to the
   genuine belief-aggregation label on the authored-gap slice? I.e. is density enough,
   or is the evidence-line/belief layer genuinely required?
4. **Model fit** — what does a proposition need, and what is the claim ↔ target
   *edge* (new edge vs. reuse of `bearsOn` / `source_refs`)?
5. **Language boundary** — did we need TS at all, or does a Python-produced artifact
   suffice (validates or kills core approach #1, §3.1)?

### 5.4 Out of scope for the spike

- TS / `npm run health` wiring (cheap, known pattern via the `prose-health.json`
  precedent — not where the risk is).
- The offset / anchoring / promotion machinery (designed for external immutable
  text).
- Any shared-core / codegen work (that is sub-project B, designed *after* this).
- Persisting links into the real graph beyond the few hand-authored gap propositions
  (kept on a branch, trivially reverted).

### 5.5 Done when

We can answer all five friction axes with evidence from **both** slices.

## 6. Files

- `docs/plans/2026-06-16-prose-grounding-spike-design.md` — this design.
- Spike code: a clearly-marked throwaway Python module/script under `science` (exact
  location decided in the implementation plan).
- A handful of hand-authored gap `PropositionEntity` records **plus a scoreable
  `EvidenceLine` per proposition** (≥1 per slice, §5.2 step 5) in `~/d/natural-systems`,
  on a branch.
- A written friction log (the deliverable) — location decided in the plan.

## 7. Out of scope (later, post-spike)

- Sub-projects A (epistemic convergence) and B (shared cross-language core), designed
  with the spike's friction log in hand.
- Production `npm run health` integration of grounding (sub-project C proper).
- Stylized-rendering of grounding strength in the published site beyond the spike's
  one-section preview.
