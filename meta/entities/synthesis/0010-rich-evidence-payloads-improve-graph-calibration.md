---
type: synthesis
title: Rich evidence payloads improve graph calibration
status: active
created: '2026-05-06'
updated: '2026-07-01'
report_kind: hypothesis-synthesis
id: synthesis:0010-rich-evidence-payloads-improve-graph-calibration
hypothesis: hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
generated_at: '2026-05-06T03:57:33Z'
source_commit: 591956fe223318a92c9b36ba01afefcfb1246b10
provenance_coverage: thin
---

## State

Arc reconstruction is limited: no interpretations or `.edges.yaml` edges exist for this hypothesis; all support is literature-grounded architectural reasoning.

`hypothesis:0002-rich-evidence-payloads-improve-graph-calibration` proposes that storing structured evidence payloads — rather than scalar support/dispute edges — produces better-calibrated belief updates. The core claim (P1) is that rich-payload aggregation will show lower calibration error against held-out validation outcomes. The mechanism (P2) is that structured fields preserve distinctions that affect evidential meaning: estimand, comparison target, model family, heterogeneity, bias model, source reliability, source dependence, pipeline provenance, transport assumptions, graph object type, agent provenance, and robustness/replication semantics. A minimality constraint (P3) holds that calibration gain must be achievable with a compact core schema, because an authoring burden that is too heavy collapses coverage.

Current support is mostly literature-based across six paper batches (Batches 1-6 cited in `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`). No benchmark or simulation has yet compared scalar-edge against rich-payload aggregation. The completed `[t030]` authoring-cost audit now provides the first practical-viability evidence: the t022 core had to shed or loosen fields, and blind LLM extraction showed rubric-sensitive drift. That supports the compact-core/typed-extension strategy but keeps agent-assisted population as an unresolved evaluation problem. An equally unresolved question is what calibration ground truth is available for scoring; `question:0013-robustness-reproducibility-evaluation` bears on whether typed validation outcomes are sufficiently well-defined to serve as the scoring signal.

## Arc

Arc reconstruction is limited because no `prior_interpretations` chains exist; this hypothesis was drafted during task `t027` (done) as a post-Batch-2 synthesis artifact, and no interpretation artifacts have been generated since.

The investigation opened after Batch 1 Bayesian synthesis literature (covering truth discovery, Bayesian Evidence Synthesis, and causal meta-analysis) suggested that scalar support edges lose too much evidential context. `t027` drafted `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration` alongside H03 and H04 after Batch 2 added source behavior and pipeline provenance findings.

Batches 3–6 extended the payload specification domain-by-domain — causal graph construction (`t034`), graph-valued integration (`t035`), agent/KG operations (`t038`), and robustness/reproducibility semantics (`t040`) — each surfacing a new class of fields whose omission would cause the graph to treat unlike evidence operations as interchangeable. Task `t034` now has a durable implemented contract in `meta/evidence/t034-causal-graph-contract.md`, backed by `meta/src/t034_validator/` and `meta/tests/test_t034_validator.py`. Task `t021` was created as a P1 parent group to coordinate the remaining expanding design surface. The current epistemic position is that the hypothesis has strong literature-derived motivation and one practical authoring-cost audit signal from `[t030]`, but no direct calibration benchmark; it remains in `proposed` status pending replay/benchmark evidence.

## Research fronts

**Open tasks (P1):**
- `t022` — Maintain the minimum quantitative evidence payload schema as implementation feedback accumulates
- follow-up authoring-cost evaluation — recover the original full-context-human-vs-blind-LLM signal or run a multi-model extraction audit after `[t030]`
- `t035` — Design graph-valued synthesis artifact schema
- `t038` — Design graph evolution and KG view provenance
- `t040` — Design robustness/reproducibility evaluation schema

**Open tasks (P2):**
- `t023` — Design typed synthesis nodes
- `t024` — Represent heterogeneity and bias as evidence-generation mechanisms
- `t025` — Add reason-coded uncertainty features to H01 attention
- `t026` — Causal synthesis guardrails
- `t028` — Follow-up literature on Bayesian synthesis, causal meta-analysis, anytime-valid evidence
- `t031` — Source-dependence detection design (related to `question:0006-source-dependence-detection`, `question:0008-llm-agents-as-fallible-sources`)
- `t036` — Follow-up literature on graph-valued and multiview synthesis artifacts
- `t041` — Follow-up literature on replication metrics, robustness, and reproducibility standards

**Open questions (primary):** `question:0002-evidence-payload-schema`, `question:0004-source-and-pipeline-provenance`, `question:0005-authoring-cost-audit`, `question:0006-source-dependence-detection`, `question:0008-llm-agents-as-fallible-sources`, `question:0010-causal-graph-construction-pipeline`, `question:0011-graph-valued-synthesis-artifacts`, `question:0012-agent-tool-kg-operations`, `question:0013-robustness-reproducibility-evaluation`.

**Knowledge gaps:**
- `topic:structured-scientific-knowledge` — 0 papers vs 3 questions referencing it (`question:0005-authoring-cost-audit`, `question:0006-source-dependence-detection`, `question:0008-llm-agents-as-fallible-sources`)
