# Prose grounding spike — findings & design implications

**Status:** spike COMPLETE 2026-06-17; spike branches discarded (deliverable = these
findings). **Design:** `docs/plans/2026-06-16-prose-grounding-spike-design.md`.
(The throwaway implementation plan and per-run artifacts lived on a now-discarded branch;
this file is the durable record.)

## What was run

A throwaway Python spike (`spikes/prose_grounding/`, discarded) over two `~/d/natural-systems`
slices — `content/prose/essay/conservation.md` (narrative → 47 claims) and
`content/prose/models/silica-sinter.yml` (canonical record → 17 claims). Full loop:
decompose (agent) → link to existing epistemic graph (agent, with independent gold pass) →
ground (provenance-density on existing targets; real `aggregate_belief` on hand-authored
gaps) → report + stylized preview. 24 unit tests, real-graph smokes.

## Findings (what should change the real design)

1. **The premise inverts — for the domain layer this is extract-and-promote, not
   check-against-graph.** The design's reframing ("graph is the source of truth, prose is a
   derived rendering") is **false for natural-systems today**: **0 of 64** prose claims had
   any domain target. The epistemic graph holds *meta-modeling* claims (morphisms, generator
   bases, fit audits), not the physics/geology the prose asserts. So step one of the real
   implementation is to **build a domain-proposition layer by decomposing prose** — the
   internal case resembles the external paper pipeline (extract→promote), sourced from our
   own prose. Grounding-against-existing is a near-no-op until that layer exists.

2. **Two distinct layers.** Meta (about the modeling enterprise) vs domain (what the prose is
   about). The design must keep a **domain-proposition kind separate** from the meta-research
   entities. Central input to sub-project A.

3. **Grounding = belief, not provenance density.** `bearsOn` density is a red herring — rich
   (2811 edges, up to 152/target) but on the wrong entities, and it measures connectivity,
   not evidential support. Use the real belief layer (`aggregate_belief`) — it works
   **standalone, no materialization**. It needs domain evidence-lines + domain source papers,
   which barely exist (**1 of 74** papers domain-relevant).

4. **The honest initial state is "almost nothing is backed."** The original "stylize the
   *few* unbacked statements" is backwards: ~everything starts unbacked (authored gaps scored
   `fragile`/`speculative`; the authored-confidence gate correctly zeroed an ungrounded
   `expert_judgment` line). So the `health` feature's real launch value is a **forcing
   function** — quantifying unformalized domain knowledge and driving a promotion campaign —
   not a polish pass. Design the metric as a **coverage ramp**, not a red/green gate that is
   all-red on day one.

5. **The one decision that gates everything: the grounding bar.** Does an entity that
   *recites* a claim as background (e.g. a meta question recounting Euler–Lagrange) count as
   grounding it (**loose**), or must a domain proposition *assert* it (**strict**)? Strict →
   existing graph contributes ~nothing → must build the domain layer. Loose → a few
   background matches count but grounding gets fuzzy. The spike used strict; decide explicitly.

6. **Keep: decomposition is cheap; the anchoring stack is unnecessary.** Verbatim-locator
   decomposition was 100% reliable (0/64 mismatches). Skip `TextQuoteSelector`/offsets/TriG
   sidecars for internal *mutable* prose — that part of the reframing held.

7. **Python-only confirmed.** The whole pipeline ran Python→JSON/md; TS just consumes
   artifacts (like `prose-health.json`). Sub-project B's dual-language core is **unneeded**
   (approach #1, single Python behavior + typed TS consumers); defer B.

8. **Tooling gaps to budget.** Authoring needs `Entity` structural-field defaults (the
   `_lift_evidence_line` pattern — bare `model_validate` on authored frontmatter false-fails);
   you'll need a proposition-authoring path + domain-paper ingestion; the
   `predicate`/`polarity`/`claim_layer` interlocks already work (`induces_state` sign-less →
   `polarity: not_applicable`).

## Implications for the program (A / B / C)

- **A (epistemic convergence):** the real first step is to **add a domain-level proposition
  layer** (promote domain claims out of prose) *and* a domain evidence corpus — **not** to
  reconcile the existing meta-level entities. The current graph is the wrong substrate for
  prose grounding.
- **B (shared core):** approach #1 confirmed sufficient; **defer** any dual-language library.
- **C (prose grounding in `health`):** the decompose→ground→report harness works end-to-end;
  once A supplies domain propositions, C is mostly JSON-artifact + TS-consumer wiring. Frame
  it as a coverage ramp / promotion forcing-function (finding 4).
- **First user decision:** the grounding bar (finding 5).
