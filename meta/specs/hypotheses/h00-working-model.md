---
id: hypothesis:h00-working-model
type: hypothesis
role: working-model
title: "Science working model: a federated patchwork of provenance-typed, uncertainty-bearing epistemic models"
status: proposed
phase: active
related:
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:01-evidence-payload-schema
- question:02-causal-synthesis-guardrails
- question:08-mcda-bayesian-interoperability
- question:10-causal-graph-construction-pipeline
- question:11-graph-valued-synthesis-artifacts
- question:12-agent-tool-kg-operations
- question:13-robustness-reproducibility-evaluation
source_refs: []
created: '2026-05-31'
updated: '2026-05-31'
---

# Science working model (h00)

This is `science-meta`'s **explicit working model** — how the framework represents
knowledge, evidence, and belief. Per `convention:project-working-model-h00`, `h00`
is the umbrella the framework's ordinary hypotheses (`h01`–`h06`) and questions
(`q01`–`q14`) are *facets of*; it is a **model**, not a testable conjecture
(`role: working-model`). Full design, prior-art reconciliation, and open forks:
`doc/plans/2026-05-31-epistemic-causal-probabilistic-graph-model-design.md` (the RFC).

## The model (one paragraph)

Knowledge is **not** one graph, nor two fixed layers, but a **federated patchwork
of small epistemic neighborhoods** ("patches") — local graphical representations
(causal DAGs, Bayesian DAGs, data→evidence and literature→evidence maps, elicited
belief subgraphs, discovered CPDAG fragments) each surrounding a hypothesis /
question / evidence cluster. Patches grow incrementally as data assesses specific
beliefs (edges / subgraphs / sub-models), and connect over time through a **dual
common space**: ontologies (symbolic identifier alignment) and data-driven,
bias-corrected **latent axes** (a learned common coordinate). Every patch carries
honest **provenance** (discovered vs elicited; empirical vs editorial/ai-drafted)
and **uncertainty**, and sits at a level on a progressive **ladder** (typed edge →
belief+provenance → associative/causal role → partial causal structure → full
PGM/SCM). Views compose **within** a patch/project or **aggregate** across the
project collection (subset / sampled / global).

## Structural representation

Typed schema (the model's entities + relations):

```
Patch (epistemic neighborhood)
  ├─ ladder_level     : L0 typed-edge | L1 belief+provenance | L2 assoc/causal-role
  │                     | L3 partial-causal (CPDAG/PAG/ADMG) | L4 full PGM/SCM
  ├─ provenance_route : discovered (data→posterior) | elicited (belief→prior)
  ├─ provenance_tier  : empirical | derived | literature | editorial(ai/human) | mathematical
  ├─ object_layer     : world entities + relations (genes, diseases, …)     [ABox]
  ├─ meta_layer       : claims/evidence/belief about those relations        [proposition+evidence]
  └─ uncertainty      : belief result (+ optional opinion / parameter priors)

GLUE  (connect patches)
  ├─ ontology_alignment : shared symbolic ids (MONDO/MeSH/HGNC)
  └─ latent_common_axis : data-driven, bias-corrected coordinate (q15 / measurement-model)

FEDERATION (compose views)
  patch  ⊂  project  ⊂  project-collection
  view ∈ { within(patch|project), aggregate(subset | sampled | global) }

DYNAMICS
  evidence moves a patch prior → posterior (bears_on / belief machinery)
  patch matures up the ladder as evidence accrues
```

ASCII sketch:

```
        ontology + latent common space
   ┌───────────────┬───────────────┬───────────────┐
 [patch A]       [patch B]       [patch C]   …   (epistemic neighborhoods)
 elicited DAG    discovered      data→evidence
 (prior)         CPDAG (post.)   map
   │  each: object↔meta layers · provenance · uncertainty · ladder-level
   └── evidence ──▶ prior→posterior ──▶ ladder maturation
   federation: within-patch · within-project · aggregate(subset|sampled|global)
```

## Facets — which existing entities instantiate which part

| Model component | Instantiating hypotheses / questions |
|---|---|
| Evidence payloads & calibration | `h02`, `q01` |
| Causal-graph construction (discovery; CPDAG/PAG/ADMG; pipeline) | `q10` (t034), `q02` |
| Causal-estimand guardrails (don't strengthen on assertion) | `h04` |
| Graph-valued / multiview synthesis (patch federation hook) | `q11` (t035) |
| Agent/tool KG operations (elicitation provenance) | `q12` (t037) |
| Robustness / reproducibility (adversarial perturbation) | `q13` (t040) |
| Uncertainty representation & MCDA/Bayesian interop | `q08` |

## Falsifiability

As a **working model** (`role: working-model`), `h00` is not a single falsifiable
conjecture — it is **revised, not refuted**. The falsifiable content lives in its
**facets** (`h01`–`h06` and their questions): a facet's evidence forcing a
structural change is what revises the model. The model's *core* commitments are
nonetheless contestable, and would be undermined if:

- a flat single-graph / two-layer representation matched belief **calibration**
  as well as the patchwork (that comparison is `h02`'s job) — i.e. the patch /
  federation structure buys no measurable advantage; or
- making **provenance + uncertainty** first-class did not improve bias-resistance
  or downstream decisions over the status-quo ordinal/log-odds belief scalar; or
- the **dual common space** (ontology + latent axis) failed to connect patches
  usefully, leaving the federation no better than disconnected local models.

These are model-revision triggers, evaluated through the facet hypotheses, not a
pass/fail on `h00` itself. (Tooling note: the hypothesis validator requires this
section; a `role: working-model`-aware exemption is a deferred follow-up named in
`convention:project-working-model-h00`.)

## Status & open forks

The model is **working/proposed**; its load-bearing design decisions are explicit
**forks** in the RFC §12 (t034 disposition, storage substrate, uncertainty
representation, argumentation backbone, latent-construct scope, elicited-belief
richness, delivery shape). Net-new beyond existing work: R1 patch-as-first-class +
glue, R2 richer uncertainty view, R3 latent/measurement bias-correction, R4 wiring
the existing pgmpy/ChiRho exporters, R5 provenance query surface, R6 elicited-belief
representation.

**Proving ground:** the `pan-disease` project exercises this model on live data —
`question:q14` (elicited curated panels) and `question:q15` (data-driven gene sets)
are the elicitation and discovery routes respectively; `task:t071` is the first slice.
