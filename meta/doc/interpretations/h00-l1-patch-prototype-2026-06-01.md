---
id: "interpretation:h00-l1-patch-prototype-2026-06-01"
type: "interpretation"
title: "L1 epistemic-neighborhood patch prototype on the pan-disease q14 slice"
hypothesis: "hypothesis:h00-working-model"
artifact: "science_tool.model (machinery); pan-disease code/scripts/h00_patch_demo.py (application)"
related:
  - task:t065
  - task:t064
  - task:t066
  - task:t069
created: "2026-06-01"
updated: "2026-06-01"
---

# L1 patch prototype (t065)

RFC §11 step 3, executed. This is the first **runnable** instantiation of the
`h00` working model: one epistemic-neighborhood **patch** at ladder level **L1**,
built on a **real** data slice, **reusing** the shipped belief machinery (D-005)
and emitting the patch as a **TriG named graph** (D-006). Code:
the patch/fusion/opinion machinery is `science_tool.model.patch` /
`.opinion` (framework; graduated per **D-007**), driven by the pan-disease
application `code/scripts/h00_patch_demo.py` (the q14→`EvidenceUnit` mapping);
demo: `uv run python code/scripts/h00_patch_demo.py`. (Originally prototyped in the
now-retired `meta/src/h00_patch_l1`.)

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

Only the fixture numbers are real (pan-disease `code/scripts/h00_fixtures/q14_slice.json`,
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

**Publication-gravity double-counting is discounted by independence-aware
fusion** (not the same as *removing* the bias — see below). The patch-level claim
"disease D's PubTator gene profile reflects D-specific biology" takes one
literature support per co-occurring gene:

| | supports | support score | opinion `u` | projected `E` |
|---|---|---|---|---|
| naive (count every gene) | 17 | 17 | 0.105 | 0.947 |
| discounted (shipped reduction) | 8 | 8 | 0.200 | 0.900 |

The 10 universal genes collapse to **one** unit; the reduction discounts **53 % of
the naive support score** — the double-counting of a single corpus-wide
mechanism — and the opinion's uncertainty mass rises (0.105 → 0.200), correcting
an over-confident naive read. No curated panel gene crosses the publication-gravity
threshold, so specific biology survives intact. **What this does *not* do:**
estimate or subtract the latent corpus-attention axis. It prevents *double-counting*
the shared-source group; it does not debias the individual co-occurrence signals.
True correction is the §8.1 / `task:t066` latent-construct model.

## What this tells the RFC forks

- **§12.3 (uncertainty representation): a derived opinion view is the right
  *default next* representation — scoped, not settled.** The subjective-logic
  opinion is computed *from the same post-reduction support/dispute scores* the
  shipped `belief_scalar` already produces — no fork of the core aggregation — and
  adds the one thing the log-odds scalar cannot name: an explicit **ignorance
  mass**, which is what makes editorial honesty and over-confidence visible above.
  This is sufficient for *this* L1 positive-support, post-reduction **diagnostic**
  view. It is **not** yet evidence that the opinion mapping is calibrated,
  decision-ready, or adequate for contested evidence, base-rate-sensitive claims,
  multi-source panels, or L2+ causal structure. The mapping rests on explicit
  assumptions — prior weight `W=2`, `base_rate=0.5`, and treating ordinal support
  scores as evidential counts (`opinion.py`) — that a v4-vs-derived-view decision
  must still test. So: derived view as default next step, *not* "no v4 needed."
- **§5 / R5 (provenance query): the axes were enough; PROV-O round-trips
  structurally.** Editorial-vs-empirical honesty needed no new tier enum —
  `is_reference_dataset` (curation penalty) + `evidence_type` + `proxy_directness`
  already carried it. The PROV-O emission **round-trips structurally** but is a
  *placeholder*, not a sanctioned pattern: it annotates the edge with
  `prov:wasGeneratedBy` → an agent IRI, whereas PROV-O expects generation by an
  *Activity* with agents attached via attribution/association, and the three
  distinct activities (source provenance, AI extraction/drafting, human
  ratification) should not collapse into one edge annotation. Correct modeling is
  `task:t069` before this is reused.
- **§2 / D-006 (patch = named graph): confirmed end-to-end.** Each patch
  serializes to a TriG named graph whose IRI *is* the context, with patch-level
  metadata (ladder level, naive/discounted scores) as triples about that IRI and
  every association as a reified edge-node (edge-as-node, multi-edge ready).
- **§8.1 / R3 (latent construct) is the next earned step.** As above, publication
  gravity here is *double-counting-discounted*, not *corrected*: ubiquity is a
  hand-thresholded proxy for the latent corpus-attention construct. The natural
  successor (`task:t066`) is a measurement model that estimates and subtracts that
  latent axis instead of thresholding it.

## Limitations (carry-forward, not defects)

- **Evidence-field mapping is the main sensitivity surface** (`model.py`): ClinGen
  strict → `strength=strong`, OMIM/GeneReviews-broad → `moderate`, curated panels
  → `is_reference_dataset=True`, q99 ubiquity → publication gravity. These are
  reasonable prototype choices but **asserted, not swept** — the headline numbers
  (u = 0.50/0.67/1.0; the 53 % discount) could move under other choices. Sweep =
  `task:t069` (or fold into t066).
- **Opinion-mapping assumptions** (`W=2`, `base_rate=0.5`, ordinal-scores-as-counts)
  are unexamined; calibration and decision-readiness are untested (see §12.3 above).
- **PROV-O emission is a structural placeholder**, not a sanctioned pattern —
  activity/agent modeling deferred to `task:t069`.
- **"One world" is only partially exercised.** The fixture is a **real, documented
  extracted slice** — *not* federated live cross-project linkage. That is the
  correct scope for t065, but the distinction matters: a live patch glued across
  the meta↔pan-disease boundary still needs the validating cross-project reference
  primitive (`task:t068`, still load-bearing).
- Two focal diseases, one panel source each; the panel is treated as a single
  editorial act (no per-gene ClinGen study independence modelled).
- "D-specific biology" as the fused claim is a deliberately simple stand-in; it
  shows the fusion mechanic, not a validated similarity estimand.
