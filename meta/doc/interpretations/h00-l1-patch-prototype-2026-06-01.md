---
id: "interpretation:h00-l1-patch-prototype-2026-06-01"
type: "interpretation"
title: "L1 epistemic-neighborhood patch prototype on the pan-disease q14 slice"
hypothesis: "hypothesis:h00-working-model"
artifact: "meta/src/h00_patch_l1/"
related:
  - task:t065
  - task:t064
created: "2026-06-01"
updated: "2026-06-01"
---

# L1 patch prototype (t065)

RFC §11 step 3, executed. This is the first **runnable** instantiation of the
`h00` working model: one epistemic-neighborhood **patch** at ladder level **L1**,
built on a **real** data slice, **reusing** the shipped belief machinery (D-005)
and emitting the patch as a **TriG named graph** (D-006). Code:
`meta/src/h00_patch_l1/`; tests: `meta/tests/test_h00_patch_l1.py` (8, all green);
demo: `PYTHONPATH=src uv run python -m h00_patch_l1 [--trig DIR]`.

## What the patch is

The gene→disease association neighborhood of a single disease. Two evidence
routes per edge realize the prior↔posterior duality (RFC §3.5):

- **Elicited / editorial** — the pan-disease q14 curated panel asserts "gene G is
  a causal gene of disease D" (ai-drafted, human-ratified). Modelled as an
  `expert_judgment` / `background_constraint` `EvidenceUnit` with
  `is_reference_dataset=True`, so the shipped **curation step penalty** gives it
  structurally lower status than empirical evidence.
- **Discovered / empirical** — PubTator literature co-occurrence. Modelled as a
  `literature` / `proxy_support` unit with `proxy_directness=indirect` and no
  measurement model → a **gated proxy** (proxy step penalty). Genes co-occurring
  with ~every disease (ubiquity ≥ q99 = 3702 of 3831) are pure publication
  gravity → `independence=shared-source`, one `publication-gravity` group.

Only the fixture numbers are real (`meta/src/h00_patch_l1/fixtures/q14_slice.json`,
extracted from pan-disease `gene_disease_comat_filtered.feather`, PubTator
2026-03-17). The mapping to evidence-schema fields is the prototype's modelling
choice — documented, contestable, and exactly the kind of decision RFC fork
§12.3 is meant to settle.

## Results (CMT = ClinGen-definitive; HSP = OMIM/GeneReviews-broad)

**Provenance honesty is structural, not annotated.** Per-edge subjective-logic
uncertainty mass `u`:

| edge class | CMT (ClinGen, strong) | HSP (OMIM/GR-broad, moderate) |
|---|---|---|
| panel gene (editorial + empirical) | `supported`, u = 0.50 | `supported`, u = 0.67 |
| universal gene (empirical only) | `fragile`, u = 0.67 | `fragile`, u = 0.67 |
| panel gene, **editorial-only** (no data yet) | u = 0.67 | **u = 1.00** (total ignorance) |

The provenance-*qualified* HSP panel is **measurably less certain** than the
ClinGen CMT panel — and an HSP label *on its own*, before any empirical
corroboration, collapses to **maximal ignorance** (`u = 1.0`). This is precisely
the property K.H. asked for (editorial/AI labels carry lower epistemic status /
higher uncertainty), achieved **structurally** — the weaker the provenance, the
larger the honest ignorance mass — rather than by a hand-set confidence number.

**Publication gravity is removed as independence-discounted fusion.** The
patch-level claim "disease D's PubTator gene profile reflects D-specific biology"
takes one literature support per co-occurring gene:

| | supports | support score | opinion `u` | projected `E` |
|---|---|---|---|---|
| naive (count every gene) | 17 | 17 | 0.105 | 0.947 |
| discounted (shipped reduction) | 8 | 8 | 0.200 | 0.900 |

The 10 universal genes collapse to **one** unit; the reduction removes **53 % of
the naive support score** as publication gravity, and the opinion's uncertainty
mass rises (0.105 → 0.200) — the naive read was over-confident exactly because it
double-counted a single corpus-wide mechanism. No curated panel gene crosses the
publication-gravity threshold, so specific biology survives intact.

## What this tells the RFC forks

- **§12.3 (uncertainty representation): the "derived view, behind a flag"
  recommendation holds.** The subjective-logic opinion is computed *from the same
  post-reduction support/dispute scores* the shipped `belief_scalar` already
  produces — no fork of the core aggregation. It adds the one thing the log-odds
  scalar cannot name: an explicit **ignorance mass**, which is what makes editorial
  honesty and over-confidence visible above. No evidence yet that a v4 successor
  aggregation is needed; a derived opinion view is sufficient and cheap.
- **§5 / R5 (provenance query): the axes were enough.** Editorial-vs-empirical
  honesty needed no new tier enum — `is_reference_dataset` (curation penalty) +
  `evidence_type` + `proxy_directness` already carried it; PROV-O carries the
  AI-drafted/human-ratified agent axis on the emitted edge.
- **§2 / D-006 (patch = named graph): confirmed end-to-end.** Each patch
  serializes to a TriG named graph whose IRI *is* the context, with patch-level
  metadata (ladder level, naive/discounted scores) as triples about that IRI and
  every association as a reified edge-node (edge-as-node, multi-edge ready).
- **§8.1 / R3 (latent construct) is the next earned step.** Publication gravity
  here is *flagged-and-discounted*, not *corrected*: ubiquity is a hand-thresholded
  proxy for the latent corpus-attention construct. The natural successor (t066) is
  a measurement model that estimates and subtracts that latent axis instead of
  thresholding it.

## Limitations (carry-forward, not defects)

- The evidence-field mapping (strength tiers, proxy gating, the q99 threshold) is
  a modelling **choice**; the prototype's job is to make it concrete and testable,
  not to ratify it. Sensitivity to the threshold is unexamined.
- Two focal diseases, one panel source each; the panel is treated as a single
  editorial act (no per-gene ClinGen study independence modelled).
- "D-specific biology" as the fused claim is a deliberately simple stand-in; it
  shows the fusion mechanic, not a validated similarity estimand.
- Publication gravity is discounted, not corrected — the §8.1 latent-construct
  model (t066) is what would actually subtract the bias.
