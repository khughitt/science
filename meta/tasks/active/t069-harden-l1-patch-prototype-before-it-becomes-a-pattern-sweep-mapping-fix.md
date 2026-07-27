---
id: t069
project: ''
title: Harden L1 patch prototype before it becomes a pattern (sweep mapping + fix
  PROV-O)
type: ''
aspects:
- software-development
priority: P2
status: proposed
blocked_by: []
related:
- hypothesis:0007-working-model
- task:t065
- task:t066
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-06-01'
completed: null
---

Two pre-pattern hardening items from the t065 review (2026-06-01), to settle before the L1 patch is treated as canonical:

(1) EVIDENCE-FIELD MAPPING SENSITIVITY (review #5). The prototype's mapping choices are the main sensitivity surface and are currently asserted, not swept: ClinGen-strict -> strength=strong, OMIM/GeneReviews-broad -> moderate, curated panels -> is_reference_dataset=True, and q99 ubiquity defines publication gravity (meta/src/h00_patch_l1/model.py). Sweep these (esp. the pub-gravity ubiquity threshold and the strength tiers) and report how the headline numbers (u=0.50/0.67/1.0; the 53% double-counting discount) move. Can fold into t066.

(2) PROV-O ACTIVITY/AGENT MODELING (review #3). The current emission (meta/src/h00_patch_l1/patch.py) uses prov:wasGeneratedBy with an AGENT IRI as a placeholder. PROV-O expects generation by an Activity, with agents linked via attribution/association (prov:wasAttributedTo / prov:wasAssociatedWith). Source provenance, AI extraction/prototype provenance, and human ratification are DISTINCT activities and must not collapse into one edge annotation. Model them as separate activities before this emission is reused as a pattern.

Until both are done, t065 claims stay scoped: 'PROV-O round-trips structurally' (not 'fully carries the agent axis'); 'supports derived opinion as the default next representation' (not 'decides no v4 successor needed').