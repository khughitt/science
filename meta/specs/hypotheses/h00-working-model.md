---
id: hypothesis:h00-working-model
type: hypothesis
role: working-model
title: "Science working model: a federated patchwork of provenance-typed, uncertainty-bearing epistemic models"
status: proposed
phase: active
related:
- hypothesis:h01-stochastic-revisiting
- hypothesis:h02-rich-evidence-payloads-improve-graph-calibration
- hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting
- hypothesis:h04-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:h05-sequential-evidence-improves-attention
- hypothesis:h06-adaptive-project-topology-improves-research-fit
- question:01-evidence-payload-schema
- question:02-causal-synthesis-guardrails
- question:08-mcda-bayesian-interoperability
- question:10-causal-graph-construction-pipeline
- question:11-graph-valued-synthesis-artifacts
- question:12-agent-tool-kg-operations
- question:13-robustness-reproducibility-evaluation
- question:14-adaptive-project-topology
- task:t064
- task:t065
- task:t066
- task:t067
- task:t068
- task:t069
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
  ├─ provenance       : SPLIT across existing axes (RFC §5 — NOT one tier enum):
  │                     ProvenanceType{math|empirical|editorial|derived} · evidence_type{lit|emp|sim|bench|expert}
  │                     · source_class{obs|derived|ref}+derived_kind · PROV agent{human|ai} · review_state{ratified?}
  ├─ object_layer     : world entities + relations (genes, diseases, …)     [ABox]
  ├─ meta_layer       : claims/evidence/belief about those relations        [proposition+evidence]
  └─ uncertainty      : belief result (+ optional opinion / parameter priors)

GLUE  (connect patches)
  ├─ ontology_alignment : shared symbolic ids (MONDO/MeSH/HGNC)
  └─ latent_common_axis : data-driven, bias-corrected coordinate (measurement-model, RFC §8.1)

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
| Belief DYNAMICS — revisiting, sequential update, ladder maturation (evidence moves prior→posterior) | `h01`, `h03`, `h05` |
| FEDERATION — patch / project topology (the multi-scale composition) | `h06`, `q14` |

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

The model is **working/proposed**. Its two **foundational** forks are now
resolved (`task:t064` → `core/decisions.md` **D-005**, **D-006**): the
causal/edge substrate is **reused t034 verbatim** with `h00` net-new riding the
t022 extension contract, and the storage substrate stays **W3C-native** (a patch
*is* a named graph; world↔claim reification uses the existing edge-as-node
pattern). The remaining load-bearing decisions are still explicit **forks** in
the RFC §12 (uncertainty representation, argumentation backbone, latent-construct
scope, elicited-belief richness, delivery shape). Net-new beyond existing work: R1 patch-as-first-class +
glue, R2 richer uncertainty view, R3 latent/measurement bias-correction, R4 wiring
the existing pgmpy/ChiRho exporters, R5 provenance query surface, R6 elicited-belief
representation.

A first **L1 patch is now runnable** (`task:t065`,
`interpretation:h00-l1-patch-prototype-2026-06-01`, code `meta/src/h00_patch_l1/`):
on the real pan-disease q14 slice it reuses the shipped belief machinery, emits a
patch as a TriG named graph (D-006), and shows two headline properties on real
numbers — provenance-qualified editorial labels carry *structurally* higher
uncertainty (an HSP label alone → ignorance mass `u`=1.0), and publication-gravity
**double-counting is discounted** by the independence reduction (10 universal
genes collapse to one; 53 % of the naive support score), though the latent
attention axis is *not yet subtracted* — that correction is `task:t066`. It
supports a subjective-logic opinion as the **default next representation** (RFC
§12.3) — scoped to this L1 positive-support, post-reduction diagnostic view, not
yet evidence of calibration, contested/base-rate, multi-source, or L2+ adequacy.
Pre-pattern hardening (mapping sensitivity sweep + PROV-O activity/agent modeling)
is `task:t069`.

**Proving ground (external, planned).** The intended proving ground is the
**pan-disease** project — a *separate* Science project, not registered under this
repo. The references below are **cross-project, named in prose only** (they are
deliberately *not* resolvable `meta` typed refs, to avoid colliding with meta's
own namespace — e.g. meta's `question:14` is "adaptive-project-topology", unrelated):

- pan-disease's **monogenic-vs-polygenic gene-axis** question — the **elicitation** route (curated panels as an elicited model);
- pan-disease's **data-driven-causal-gene-sets** question — the **discovery** route (data-derived gene sets);
- pan-disease's **first replication-probe** task — the slice that will exercise the model.

It *will* exercise this model on live data once both projects are connected; the
local execution surface in this repo is the task chain `task:t064`–`task:t067`.

**Cross-project reference policy (interim).** Typed `type:id` refs (in `related:`
*and* in prose) are **local-only** — the validator resolves them against this repo,
so a foreign `type:id` reads as a broken ref (the refs-checker even resolves the
bare token locally). References to entities in other projects (pan-disease) are
therefore written **descriptively** (project name + plain short-id in parentheses),
never in `type:id` form, *until a validating cross-project ref syntax exists*.

This interim de-typing is a **known limitation, not the model's stance**. The model
holds the opposite: **all projects live in one world**, and a project is *sub-structure*
— itself decomposable into the hypothesis/domain neighborhoods this model calls
**patches**. A cross-project reference is thus a same-world reference crossing a
sub-structure boundary, *not* a foreign reference needing a bridge; the resolver
should treat project scope as one grouping level in a single addressable space
(`patch ⊂ project ⊂ project-collection`, as in the federation schema above). The
gap between that stance and the current local-only resolver is tracked as the
federation-layer primitive `task:t068` (the single syntax that the deferred
cross-project items — freshness propagation, typed blockers, the cross-project
blockers spec — all separately need). It is the reference-layer instance of the
same patchwork claim the rest of `h00` makes.
