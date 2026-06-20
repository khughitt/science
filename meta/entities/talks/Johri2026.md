---
type: talk
title: Evaluating AI agents in biological discovery
status: active
created: '2026-06-10'
updated: '2026-06-10'
id: talk:Johri2026
ontology_terms: []
speakers:
- Shreya Johri
- Maha Shady
year: 2026
venue: MIA (Models, Inference & Algorithms) Seminar, Broad Institute
url: https://www.youtube.com/watch?v=BCugR49h3ts
transcript_path: ~/d/science/archive/2026-06-09-talk-evaluating-ai-agents-in-biological-discovery.txt
source_refs:
- cite:Johri2026
related: []
---

# Evaluating AI agents in biological discovery

<!--
- **Speakers:** Shreya Johri (main talk); Maha Shady (primer)
- **Venue / event:** MIA (Models, Inference & Algorithms) Seminar, Broad Institute
- **Video URL:** https://www.youtube.com/watch?v=BCugR49h3ts
- **Transcript:** ~/d/science/archive/2026-06-09-talk-evaluating-ai-agents-in-biological-discovery.txt
- **BibTeX key:** Johri2026
-->

## Overview

Two-part MIA seminar. Maha Shady gives a primer on the anatomy of agentic AI systems
(base model, scaffolding, tools, memory, reflection, planning) and the hard problem of
*evaluating* them. Shreya Johri (PhD, Harvard BBS; postdoc in Eli Van Allen's lab,
Dana-Farber Cancer Institute) then presents ongoing work systematically benchmarking
agentic AI on **real multimodal oncology workflows** via an **M3A** framework
(Multi-step, Multimodal, Multiomic, Agentic), spanning single-cell RNA + ATAC across
15 cancer types and 240+ patients, in autonomous and human-copilot configurations.
A preprint is forthcoming.

## Key Points

**On evaluation (primer):**
- **Evaluate the process, not just the result.** For novel research you don't know the
  answer, so a correct-looking output is no evidence the workflow was sound.
- **Reasoning traces are not faithful** (cited Anthropic work): the stated rationale need
  not reflect what the model did, and faithfulness *drops on harder problems*.
- **Long-term memory split (cognitive science):** episodic (past runs/failures),
  semantic (facts/RAG/DBs), procedural (rules / "agent skills" e.g. QC best practices).
- **Contamination, reliability, multi-agent coordination** all make benchmark scores
  diverge from deployment performance; mitigate with held-out/private/time-restricted
  benchmarks, parallel runs (pass^k), and hard-coded safety gates.

**On real computational-biology workflows (main talk):**
- **Agents follow the standard pipeline verbatim and never iterate on it.** They iterated
  on cell-type *annotations* but never revisited QC, clustering resolution, or parameters
  — yet "no computational biologist one-shots the analysis," and real papers always
  deviate from the canned scanpy recipe for dataset-specific reasons.
- **Overconfident, no external grounding.** Marker genes were chosen purely from internal
  knowledge; telemetry showed web/literature search was never even *considered*. Given a
  refusal option, agents opt out of hard analysis at near-random rates.
- **Rare subtypes get mislabeled.** AUROC ~0.9–0.99 but macro-F1 collapsed — rare cell
  types were quietly folded into abundant ones (report the metric that exposes the tail).
- **Robustness = orthogonal cross-modality / cross-dataset validation.** A signal found in
  scRNA was confirmed in an independent dataset/modality (TCGA bulk) against *independent*
  ground truth (IHC ER-status, survival). Concordance was highly variable across tasks.
- **Human-on-the-loop ≥ human-in-the-loop.** Heavy human steering often *hurt* — it
  suppressed the agent's data exploration by constraining it prematurely.
- **Re-evaluate on every model swap** — a model's known weakness need not persist across
  versions.

## Relevance

This talk is the grounding source for the data-driven discovery improvements umbrella
(`~/d/science/docs/plans/2026-06-10-data-driven-discovery-improvements.md`, in the
framework repo).
It is an **unrefereed source** (a seminar on ongoing work): treat its specific claims as
hints to verify, but its framing maps directly onto Science workstreams —

- **Process over cookbook execution** (no-iteration failure mode; verbatim-pipeline) →
  QA toolkit, QA-breadth quantification, no-iteration flagging, adaptive (not rigid)
  pre-registration.
- **Orthogonal cross-modality validation** → evidence-strength tiering
  (paper-hint < single-dataset < multi-dataset < multi-modal) and systematically rewarding
  cross-modality corroboration, extending the dataset-independence machinery
  (`dataset_usage` / overlap / B2 collapse).
- **Reasoning-trace unfaithfulness** → weight verifiable artifacts (code/numbers/plots)
  over prose rationale in interpret-results / review.
- **Decision telemetry (why + expected-output, logged pre-execution)** → richer step-level
  provenance that turns each step into a falsifiable micro-prediction.
- **Cognitive-science memory taxonomy** → the "episodic" (failure-memory) gap in Science's
  memory system.
- **Overconfidence / no-grounding / opt-out** → new bias-audit checks.

## Source Details

- **Video:** https://www.youtube.com/watch?v=BCugR49h3ts
- **Transcript (retrieved 2026-06-09):**
  `~/d/science/archive/2026-06-09-talk-evaluating-ai-agents-in-biological-discovery.txt`
- **Speakers:** Shreya Johri (Van Allen Lab, Dana-Farber Cancer Institute); primer by
  Maha Shady.
- **Venue:** MIA (Models, Inference & Algorithms) Seminar, Broad Institute, 2026.

## Follow-up

- Watch for the **M3A preprint** (referenced as forthcoming) and replace/augment this
  entry's claims with the published, citable results.
- Related Science background: the **Platonic Representation Hypothesis** talk
  (cross-modal convergence on a shared latent) — referenced from Theme A of the umbrella.
