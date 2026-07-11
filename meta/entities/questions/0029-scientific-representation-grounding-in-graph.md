---
id: question:0029-scientific-representation-grounding-in-graph
kind: question
title: How does the Science toolkit ground its graph models in real-world entities
  rather than in other representations (the Loss of Reality problem)?
status: active
ontology_terms: []
datasets: []
source_refs:
- cite:Ghins2011
related:
- hypothesis:0007-working-model
- question:0019-powers-vs-laws-causal-edge-ontology
created: '2026-07-10'
updated: '2026-07-10'
---

# How does the Science toolkit ground its graph models in real-world entities rather than in other representations (the Loss of Reality problem)?

## Summary

When the Science toolkit builds a knowledge graph of propositions, evidence nodes, and
causal edges, it produces abstract structures — yet those structures are intended to
represent real-world biological or causal relationships.
Ghins (2011) names this the "Loss of Reality problem": an abstract mathematical structure
(a data model, an empirical substructure, a theory) appears to only ever represent phenomena
*as described* by some prior representation, never the phenomena themselves.
This question asks whether the Science toolkit has — or needs — an explicit answer to that
problem, and if so what form that answer should take within its proposition/evidence schema.

## Why It Matters

- **Graph grounding discipline**: the working model (`hypothesis:0007`) describes patches
  as epistemic neighborhoods grounded in evidence; without a grounding theory, the schema
  risks building representations-of-representations with no tether to real-world entities.
- **Proposition truth-conditions**: Science assigns confidence values to propositions, but
  confidence presupposes a determinate truth-condition; if propositions are only about
  other representations rather than about real entities, the probability calculus has no
  genuine referent.
- **Risk if unanswered**: if the toolkit's models are treated as purely structural artefacts
  (maps of maps), the epistemic warrant for belief updates becomes circular — calibration
  against "ground truth" datasets would only establish coherence among representations,
  not correspondence with reality.

## Current Evidence

- Ghins (2011) argues that the Loss of Reality problem is dissolved by grounding representation
  in *ontic judgements* — first-person predicative acts attributing properties to real
  phenomenal entities, not to other structures [@Ghins2011].
- The Science working model (`hypothesis:0007`) currently uses the language of
  "epistemic neighborhoods" and "bearing-on" relationships, but does not explicitly
  distinguish representational *success* (correct denotation of a real target) from
  representational *correctness* (accurate characterization of the target's properties).
- Van Fraassen's pragmatic dissolution (adequacy to phenomena = adequacy to
  phenomena-as-represented) is Ghins' foil; the toolkit's current position is closer
  to van Fraassen's in that it emphasizes empirical adequacy and calibration rather
  than metaphysical correspondence [@Ghins2011].
- The "variety and concordance of independent measurements" argument for realism
  [@Ghins2011, Section 6] maps directly to Science's multi-source evidence corroboration
  machinery — concordant independent sources are the practical grounding mechanism.

## Thoughts

- **Best current interpretation**: Science implicitly adopts a moderate empiricist position
  — graph structures are grounded via the evidence that generated them, and multi-source
  concordance is the practical substitute for metaphysical correspondence. This is compatible
  with Ghins' account if "ontic judgements" are interpreted as the experimental observations
  and measurements that seed evidence nodes.
- **Major uncertainty**: whether the toolkit needs to make the success/correctness distinction
  explicit in its schema (as a denotation metadata field vs. a confidence field on proposition
  edges), or whether collapsing both into a single confidence score is adequate for the
  toolkit's purposes.
- A pragmatic first step would be to annotate proposition nodes with a `grounding_level`
  field indicating whether they derive from direct measurement (phenomenal/data-model level)
  or from theoretical inference (empirical-substructure/embedding-theory level), following
  Ghins' five-level hierarchy.

## Connections to Project

- Related hypotheses: `hypothesis:0007-working-model` (the patch as an epistemic neighborhood
  that must connect to real-world entities), `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`
  (calibration as a practical grounding proxy)
- Required data or analyses: A schema audit mapping each current evidence node type to
  its level in Ghins' five-level hierarchy; comparison of van Fraassen vs. Ghins positions
  against the existing `ProvenanceType` and `source_class` fields.
- Priority level: Medium — philosophical grounding; actionable via schema annotations
  once the working model's patch structure is stabilized.

## Related

- Topic notes: `hypothesis:0007-working-model`, `question:0019-powers-vs-laws-causal-edge-ontology`
- Article notes: `paper:Ghins2011`; future intakes: van Fraassen (2008), French and Ladyman
  on structural realism
- Methods/Datasets: N/A
