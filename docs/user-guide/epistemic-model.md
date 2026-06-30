# Epistemic Model

Science treats uncertainty as part of the project record. The goal is not to
turn every claim green; the goal is to make current support, dispute,
fragility, and missing evidence visible.

## Core Types

| Type | Purpose |
|---|---|
| `question` | Frames what the project wants to learn. |
| `hypothesis` | Organizes one or more propositions into a working conjecture. |
| `proposition` | The primary truth-apt, belief-bearing assertion. |
| `observation` | A concrete empirical finding or recorded datum. |
| `evidence-line` | Durable support or dispute linked to a proposition or other epistemic target. |
| `inquiry` | A scoped work program connecting questions, variables, assumptions, propositions, datasets, transformations, and decisions. |
| `mechanism` | Named explanatory structure linking multiple typed entities and propositions. |
| `patch-definition` | Authored profile for a local epistemic neighborhood. |

## Inquiries

An `inquiry` is a scoped work program: it names what the project is trying to
understand, which variables or data sources are treated as givens, which outputs
or decisions it is trying to produce, and which assumptions or transformations
connect those parts.

Science has two inquiry-related source surfaces:

| Surface | Role |
|---|---|
| `entities/inquiries/<slug>.md` | A normal inquiry entity for prose-first records, legacy projects, and human-readable scoped work notes. |
| `entities/patches/<slug>.md` with `type: patch-definition` and `patch_type: inquiry` | The source-first graph inquiry profile compiled by `science graph build`. |

The queryable inquiry graph is derived state. Do not hand-edit
`knowledge/graph.trig` to change an inquiry. Edit the source file, then run
`science graph build`.

### Inquiry Patch Profiles

The graph-backed inquiry path uses `patch-definition` because an inquiry is also
a local epistemic neighborhood: it has a focal hypothesis or question and a
derived member set around that focal target. `science inquiry init` scaffolds
this source file:

```bash
science inquiry init <slug> \
  --label "<title>" \
  --target hypothesis:<id> \
  --profile investigation
```

For causal inquiries, include the estimand when the file is created:

```bash
science inquiry init <slug> \
  --label "<title>" \
  --target hypothesis:<id> \
  --profile causal \
  --treatment concept:<treatment> \
  --outcome concept:<outcome>
```

The authored `inquiry:` block carries:

| Field | Purpose |
|---|---|
| `profile` | `investigation` or `causal`. Causal profiles require `treatment` and `outcome`. |
| `status` | `sketch`, `specified`, `planned`, `in-progress`, or `complete`. |
| `boundary_roles` | Existing entity refs marked as `BoundaryIn` or `BoundaryOut`. |
| `flow_edges` | Directed inquiry edges using `feedsInto`, `produces`, or `causes`, optionally backed by `proposition:` refs in `claim_refs`. |
| `assumptions` | Inquiry-local assumption nodes minted during graph build, with optional provenance. |
| `transformations` | Inquiry-local transformation nodes, tools, parameters, and validation refs. |
| `unknowns` | Existing refs marked as `sci:Unknown` until resolved or justified. |

The graph build compiles inquiry patch profiles into dedicated `sci:Inquiry`
named graphs and then derives patch-membership records. Boundary nodes and edge
endpoints must resolve to existing entities; assumption and transformation nodes
are minted by the compiler.

### Causal Inquiry Profiles

Causal modeling is a typed inquiry profile, not a separate project subsystem.
Use `profile: causal` when the inquiry is about a treatment, intervention,
causal DAG, confounders, or a treatment-effect estimand. Use
`profile: investigation` for data flow, computational flow, and non-causal
exploration.

A causal inquiry source must name:

| Field | Purpose |
|---|---|
| `profile: causal` | Enables causal validation and export behavior after graph build. |
| `treatment` | Existing entity ref for the intervention or exposure variable. |
| `outcome` | Existing entity ref for the effect variable. |

Causal variables remain normal source-authored entities. The inquiry source
selects the treatment, outcome, boundary variables, assumptions, unknowns, and
local candidate edges around the focal question or hypothesis.

Causal edges use `predicate: causes` in the authored inquiry `flow_edges` block;
graph build materializes them as `scic:causes` in the compiled inquiry graph.
Reusable project-level causal structure can also live in the generated
`graph/causal` layer and is read by causal exports when it connects inquiry
members. Treat causal edges as claim-like assertions: attach candidate
`proposition:` refs in `claim_refs` when a causal edge has explicit support, and
leave weak or ungrounded edges visible rather than upgrading them into evidence.

Causal validation and export commands read the materialized graph:

```bash
science inquiry validate <slug> --format json
science inquiry export-pgmpy <slug> --output code/causal/<slug>.py
science inquiry export-chirho <slug> --output code/causal/<slug>.py
```

`export-pgmpy` produces a graph-theoretic analysis scaffold for adjustment-set
and identifiability review. `export-chirho` produces a Pyro/ChiRho scaffold for
future interventional or counterfactual modeling. Exports are scaffolds, not
fitted models; researchers still need to provide data, distributions, priors,
and sensitivity analysis.

When reviewing causal inquiries, keep two questions separate:

- Is the relation replicated or otherwise well supported?
- Is the causal direction identified by interventional, longitudinal,
  observational, structural, or no evidence?

`references/dag-two-axis-evidence-model.md` documents that two-axis evidence
vocabulary for rendered causal DAG edges.

### Inquiry CLI

The current `science inquiry` CLI is source-first:

- `science inquiry init` scaffolds the source file and does not write the graph.
- `science inquiry import` is a bridge from an existing graph inquiry into a
  patch-definition source file.
- `science inquiry list`, `science inquiry show`, `science inquiry validate`,
  `science inquiry export-pgmpy`, and `science inquiry export-chirho` read the
  materialized graph.
- The old graph-mutating commands (`add-node`, `add-edge`, `add-assumption`,
  `add-transformation`, and `set-estimand`) are retired. Edit the source file
  and rebuild instead.

## Proposition-Centered Belief

Propositions are the main units whose belief can be summarized. A proposition
may be simple prose or carry subject/predicate/object structure when that makes
the scientific relation clearer.

Evidence does not prove propositions outright. Evidence lines support or dispute
propositions, and the belief machinery derives the current state from eligible
evidence.

### Relational Propositions

A truth-apt graph edge is represented as a `proposition` with relational fields,
not as a separate edge store linked to a proposition. The proposition is the
belief-bearing unit and, when rendered as a graph edge, its canonical IRI is also
the reified edge-node IRI. Belief, evidence, and rendering therefore address the
same assertion.

Relational propositions factor the assertion into orthogonal axes:

| Field | Purpose |
|---|---|
| `subject` | Existing entity ref for the source endpoint. |
| `predicate` | Sign-free relation kind such as `affects`, `regulates`, `associates_with`, `binds`, `is_proxy_for`, `subtype_of`, or `part_of`. |
| `object` | Existing entity ref for the target endpoint. |
| `polarity` | `positive`, `negative`, `unsigned`, or `not_applicable`; this is the sign carrier. |
| `claim_layer` | What kind of claim is being made. |
| `identification_strength` | Identification leverage: `none`, `structural`, `observational`, `longitudinal`, `interventional`, or `analogical`. |

Predicates are deliberately sign-free. Sign-meaningful predicates require
`positive`, `negative`, or `unsigned`; sign-less predicates require
`not_applicable`. Multiple propositions may share a subject/object pair when
they make different claims.

### Proposition Edges And Plumbing

A proposition-edge is truth-apt and belief-bearing, including a
`claim_layer: structural_claim` assertion when the structure itself is under
claim. Plumbing edges are different: containment, grouping, patch membership,
and measurement-model wiring organize the graph but do not carry belief.

Rendered causal edges use derived visual channels rather than authored
`edge_status`. `derived_edge_status` is a lossy compatibility projection over
canonical state:

1. `eliminated` when a refutation cap has fired.
2. `unknown` when there is no grounding evidence.
3. `structural` for grounded `structural_claim` propositions.
4. `supported` for `supported` or `well_supported` belief.
5. `tentative` for the remaining grounded cases.

`contested`, polarity, identification strength, claim layer, and scalar belief
remain separate channels. Do not author `edge_status` as scientific truth.

## Belief Vocabulary

| Term | Meaning |
|---|---|
| `belief_state` | Derived interpretation of the proposition given the current evidence. |
| `speculative` | Little or no eligible support. |
| `fragile` | Some support, but narrow, weak, indirect, or dependent on too little evidence. |
| `supported` | Support clears the configured floor. |
| `well_supported` | Stronger support, usually requiring multiple independent and relevant lines. |
| `contestation` | Credible support and credible dispute coexist. |
| `fragility` | The current belief could change easily because support is narrow or dependent. |
| `uncertainty` | Remaining lack of warranted confidence. |

Use these as readings of the record, not as manually assigned labels to chase.

## Belief Policy

Belief aggregation is controlled by an explicit, versioned policy. The current
built-in policy is `DEFAULT_BELIEF_POLICY`, with `policy_id: core-default` and
`policy_version: 1`. It gathers the ordinal evidence rank tables, the
curation-step penalty, reduction vocabulary, magnitude thresholds, refutation-cap
conditions, authored-assertion gates, and dataset-QA ceiling into one immutable
object.

The default policy preserves the core belief math: evidence lines are reduced by
independence group and quality, clean support determines the ordinal magnitude,
and decisive whole-claim refutations can cap stronger support to `fragile`.
Callers may pass an explicit policy to the belief engine, but persisted belief
records and bundle rollups must remain policy-comparable. Science refuses to
roll up bundle members computed under mixed `(policy_id, policy_version)` pairs
rather than silently combining results with different semantics.

Policy identity is persisted with belief outputs. Belief snapshot rows include
`policy_id` and `policy_version`, and snapshot de-duplication treats those fields
as part of the identity of a reproducible row. Patch RDF summaries also stamp the
default belief policy identity alongside the derived belief magnitude. Older
snapshot rows that predate explicit policies are read as `core-default` version
`1`, which is the policy that produced them.

The belief policy is separate from the optional log-odds scalar projection. The
scalar has its own configuration version and remains a derived projection over
the ordinal result; policy version and scalar config version should not be
treated as interchangeable.

## Verdict Tokens And Atomic Decomposition

Interpretations use a compact verdict line for fast scanning:

```markdown
**Verdict:** [~] Bimodal result across contexts
```

The token is with respect to the predicted direction or hypothesis arm under
test, not project valence. A `[-]` result can be valuable project progress when
it closes a question honestly.

| Token | Meaning |
|---|---|
| `[+]` | Evidence supports the predicted direction or hypothesis arm. |
| `[-]` | Evidence refutes or contradicts the predicted direction. |
| `[~]` | Mixed, null, bimodal, or context-dependent signal with structured content. |
| `[?]` | Inconclusive because of protocol failure, data gaps, or insufficient power. |
| `[⌀]` | Non-adjudicating terminal where the test discriminated, but the rollup is deliberately closed without resolving polarity. |

When a verdict depends on multiple subclaims, add a `verdict:` frontmatter block
so tooling can parse and roll it up:

```yaml
verdict:
  composite: "[~]"
  rule: "weighted-majority"
  claims:
    - id: "h1#edge5-ifn-arm"
      polarity: "[+]"
      strength: "strong"
      weight: 3.0
      evidence_summary: "NES positive in both contexts"
      contexts:
        - context: "RPMI-8226"
          polarity: "[+]"
          strength: "strong"
    - id: "h1#edge5-e2f-arm"
      polarity: "[-]"
      strength: "moderate"
```

The block is optional for legacy interpretations. Once present, `composite` and
`rule` are required, and every listed claim requires `id` and `polarity`.
Supported rules are:

| Rule | Derived composite |
|---|---|
| `and` | `[+]` when all claims are positive, `[-]` when any claim is negative, otherwise `[~]`. |
| `or` | `[+]` when any claim is positive, `[-]` when all claims are negative, otherwise `[~]`. |
| `majority` | Strict positive or negative majority over all claims; exact ties return `[~]`. |
| `weighted-majority` | Strict positive or negative majority over adjudicating weight only; unresolved or non-adjudicating weight can keep the result `[~]`. |
| `bimodal` | Always `[~]`; use when distribution shape is the finding. |
| `non-adjudicating` | Always `[⌀]`; add `closure_terminal` to name the closure reason. |
| `reframed` | Always `[~]`; add `reframing_target` and `reframing_reason` to preserve measurement lineage. |

The body verdict remains authoritative. If the rule-derived composite differs
from the body token, `science verdict parse` reports
`rule_disagrees_with_body: true` so reviewers can see the human override or
repair the rule choice.

Claim-scoped rollups need stable project-local claim IDs. Put the registry at
`entities/claim-registry.yaml`:

```yaml
version: 1
project: example
claims:
  - id: "h1#edge5-ifn-arm"
    source: "hypothesis:h1"
    definition: "IFN arm of the edge-5 mechanism."
    predicted_direction: "[+]"
    synonyms:
      - "h1-edge6-ifn-arm"
```

Canonical IDs and synonyms must be unique. `science verdict parse` can warn on
unresolved IDs when a registry is available. `science verdict rollup --scope
claim` and `science verdict rollup --by-claim` require a registry; `--strict`
turns unresolved IDs and validation warnings into command failures.

Use the implemented CLI surface to inspect verdict structure:

```bash
science verdict parse entities/interpretations/<slug>.md
science verdict parse entities/interpretations/<slug>.md --registry entities/claim-registry.yaml
science verdict rollup --scope all --root entities/interpretations --format json
science verdict rollup --by-claim --root entities/interpretations --registry entities/claim-registry.yaml --format json
```

Verdict tokens summarize interpretations. They do not replace proposition
belief state, evidence-line stance, causal identification, or quantitative
effect estimates; those remain authored and derived on their own surfaces.

## Authored Versus Derived

Authored fields record what a person, source, result, or project file says:
proposition text, scope, evidence stance, source, method, caveats, and quality
inputs.

Derived fields summarize what follows from the authored record: belief state,
support and dispute summaries, contestation, fragility, and freshness.

## Hypotheses And Bundle Belief

A hypothesis is an organizing conjecture. It may contain several propositions
whose evidence differs. A hypothesis should not be treated as supported merely
because it was written down or because one member proposition looks promising.

Hypotheses and mechanisms are proposition bundles. Their `composition_rule`
declares how member propositions compose:

| Rule | Use |
|---|---|
| `conjunctive` | Hypothesis default. Core subclaims jointly assert the conjecture. |
| `all_steps` | Mechanism default. Every core step must hold. |
| `evidence_union` | Reserved name; not implemented. |
| `faceted_support` | Reserved name; not implemented. |

The implemented rules currently share weakest-link behavior: the bundle is only
as strong as its least-supported core member. Ties are deterministic, and the
reported bottleneck members explain which core propositions set the bundle's
belief. Refutation propagates as a cap, not as a separate positive belief
state. Contested and unresolved members are reported separately.

Bundle belief is about truth of the bundle. Linked-evidence coverage and
neighborhood coverage are separate questions; a bundle can be well connected
without all core subclaims being well supported.

If a hypothesis has no resolved member propositions and no authored
`composition_rule`, Science falls back to direct evidence on the hypothesis
itself. An authored bundle rule, a mechanism with zero members, or a bundle
whose only members are non-core fails loudly because there is no conjunction to
roll up.

### Bundle Membership Roles

Bundle membership roles describe how one proposition participates in one
hypothesis or mechanism frame. They are frame-relative plumbing for bundle
belief and coverage; they are not proposition roles, evidence roles, or causal
roles such as mediator, confounder, or collider.

The vocabulary is closed:

| Role | Meaning |
|---|---|
| `core` | Enters the bundle-belief conjunction. Bare `discusses:` entries mean `core`. |
| `rival` | A competing proposition inside the bundle neighborhood. Excluded from bundle belief. |
| `background` | Context for the bundle neighborhood. Excluded from bundle belief. |

Proposition frontmatter can declare membership with `discusses:`:

```yaml
discusses:
  - hypothesis:h1
  - frame: hypothesis:h1
    role: rival
```

`sci:hasProposition` mechanism steps are always core. If a proposition is both a
mechanism step and a `discusses:` member of the same frame, the mechanism step
wins for bundle belief.

`knowledge/sources/local/relations.yaml` can also author membership with
`predicate: cito:discusses` and `role: core|rival|background`. A `role:` is
valid only when the subject is a proposition and the object is a live hypothesis
or mechanism. Other `cito:discusses` links, such as `paper -> question`,
`paper -> hypothesis`, or `proposition -> topic`, remain plain structural links
and do not create membership roles.

For graph-level experiments, `science graph add proposition --bridge-between`
accepts `--bridge-role core|rival|background`. Direct graph additions are still
ephemeral; use proposition source files or `relations.yaml` for durable project
knowledge.

## Optional Layered-Claim Metadata

Use optional metadata when it clarifies the scientific claim:

- `claim_layer`: `empirical_regularity`, `causal_effect`, `mechanistic_narrative`, or `structural_claim`.
- `identification_strength`: what kind of identification leverage exists, such as structural, observational, longitudinal, interventional, analogical, or none.
- `measurement_model`: how an observed proxy relates to a latent construct.
- `supports_scope`: a review-radius hint, not a graph override.
- `rival_model_packet`: a bounded comparison among competing models.

Do not fill these fields performatively. Add them when they reduce ambiguity.

## Evidence Integrity

Belief state, validation, and health checks are instruments for reading the
evidence. They are not targets to game.

Never relabel weak or indirect evidence as strong or direct just to clear a
warning. Never split a shared cohort, instrument, or source into fake
independence groups. Never overstate stance, strength, relevance, or
identification strength to improve a dashboard.

An honest yellow warning is often the correct state of the science.
