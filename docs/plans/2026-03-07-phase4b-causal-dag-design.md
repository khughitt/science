# Phase 4b: Causal DAG Inquiry — Design

*Date: 2026-03-07*
*Status: Approved*
*Depends on: Phase 3 (complete), Phase 4a inquiry workflow (complete)*

## Goal

Add causal modeling as a typed inquiry within the existing knowledge graph and inquiry infrastructure. Researchers can build causal DAGs, check identifiability, and export scaffold code to ChiRho (Pyro-based causal inference) and pgmpy (graph-theoretic analysis).

## Core Model

Causal DAGs are not a separate module — they are **typed inquiries**. The existing inquiry abstraction gains a lightweight type system that determines which validation checks and exports apply.

### Edge Placement

- **Causal edges** (`scic:causes`, `scic:confounds`) live in `graph/causal` — shared across inquiries, reusable across investigations.
- **Inquiry named graphs** (`:inquiry/<slug>`) contain boundary roles, membership, inquiry metadata, and computational flow edges (`sci:feedsInto`).
- **Variables** referenced by a causal inquiry are regular `sci:Variable` entities in `graph/knowledge`.

A causal inquiry *selects* variables and then the export/validation commands query `graph/causal` filtered to those variables. This keeps causal knowledge upstream and reusable.

### Relationship to Knowledge Graph Layers

| Layer | Role in causal inquiries |
|-------|------------------------|
| `graph/knowledge` | Defines variables (`sci:Variable`), their types, observability, provenance |
| `graph/causal` | Stores `scic:causes` and `scic:confounds` edges (shared, not inquiry-scoped) |
| `graph/provenance` | Claims justifying each causal edge, with confidence and source |
| `:inquiry/<slug>` | Boundary roles, treatment/outcome designation, inquiry metadata |

### Inquiry Type

Stored as `sci:inquiryType "causal"` on the inquiry node. Defaults to `"general"` for backward compatibility. The type determines:
- Which validation checks fire (causal inquiries get identifiability checks)
- Which export commands are available (`export-pgmpy`, `export-chirho`)
- Which skill guidance the agent follows

The type is a lightweight property, not a heavyweight type system. Enforcement of edge/node conventions is the agent's job (via the skill), not the tool's job.

## Command Surface

### New CLI Subcommands

```
science-tool inquiry init <SLUG> --type causal --label <LABEL> --target <HYPOTHESIS>
science-tool inquiry export-pgmpy <SLUG> [--output <FILE>]
science-tool inquiry export-chirho <SLUG> [--output <FILE>]
```

`--type` on `inquiry init` is new (defaults to `general`). Export commands are type-gated — they error if the inquiry type isn't `causal`.

### New Slash Commands

| Command | Purpose | Cognitive mode |
|---------|---------|---------------|
| `/science:build-dag` | Guided construction of a causal DAG from research question + knowledge graph | Divergent then convergent |
| `/science:critique-approach` | Review a causal inquiry for confounders, identifiability, missing variables | Critical / adversarial |

### `/science:build-dag` Workflow

1. Read existing knowledge graph, hypotheses, inquiries
2. Interactive: "What causal question? What's the treatment? What's the outcome?"
3. Identify candidate variables from KG (suggest existing concepts)
4. For each proposed edge: "Why do you believe A causes B?" — create claim with provenance
5. Check for confounders: "What else affects both X and Y?"
6. Add variables to `graph/knowledge`, causal edges to `graph/causal`, create causal inquiry with boundary roles
7. Run `inquiry validate`, generate visualization
8. Suggest next step: `/science:critique-approach <slug>`

### `/science:critique-approach` Workflow

1. Load causal inquiry + its edges from `graph/causal`
2. Export to pgmpy internally for graph-theoretic analysis
3. Check: missing confounders, identifiability, adjustment sets, testable implications
4. Challenge each causal edge: "Could this be reverse causation? Selection bias? Mediated by something?"
5. Produce review report at `doc/inquiries/<slug>-critique.md`

## Validation

Causal inquiries get additional checks beyond standard inquiry validation:

| Check | Severity | Description |
|-------|----------|-------------|
| `causal_acyclicity` | Error | `scic:causes` edges among inquiry variables must form a DAG |
| `identifiability` | Warning | Target causal effect is identifiable given observed variables (via pgmpy back-door criterion) |
| `adjustment_sets` | Info | Report valid adjustment sets for the target effect |
| `confounders_declared` | Warning | Every pair with a common ancestor should have an explicit confounder edge or documented justification |

These fire only when `sci:inquiryType` is `"causal"`. Standard inquiry checks (boundary reachability, orphaned interior, provenance completeness) still apply.

## Ontology Extensions

Minimal — mostly reusing existing predicates:

| Addition | Type | Notes |
|----------|------|-------|
| `sci:inquiryType` | New predicate | Literal on inquiry node: `"general"` or `"causal"` |
| `sci:treatment` | New predicate | Links inquiry to treatment/intervention variable (inquiry-scoped) |
| `sci:outcome` | New predicate | Links inquiry to outcome variable (inquiry-scoped) |
| `scic:causes` | Existing | Already in predicate registry |
| `scic:confounds` | Existing | Already in predicate registry |
| `sci:observability` | Existing | `observed` / `latent` / `computed` on variables |

`sci:treatment` and `sci:outcome` tell export commands which effect to estimate. Without them, exports emit full DAG structure without a specific estimand.

## Causal DAG Skill

New skill at `.claude-plugin/skills/models/causal-dag.md`:

- When to use causal vs. general inquiries
- How to think about causal structure (treatment, outcome, confounders, mediators, colliders)
- Common pitfalls (conditioning on colliders, M-bias, selection bias)
- Provenance discipline: every `scic:causes` edge should have an associated claim with source and confidence
- How to interpret pgmpy identifiability results and adjustment sets
- When to use ChiRho (interventional/counterfactual queries) vs. pgmpy (graph-theoretic analysis)

## Export Details

### pgmpy Export

Generates a self-contained Python script:

```python
# Generated from inquiry: <slug>
# Source graph: knowledge/graph.trig (rev: <hash>)
from pgmpy.models import BayesianNetwork
from pgmpy.inference import CausalInference

model = BayesianNetwork([
    ("X", "Y"),  # claim: "X causes Y" (confidence: 0.85, source: doi:10.xxx)
    ("Z", "X"),  # claim: "Z causes X" (confidence: 0.90, source: doi:10.yyy)
    ("Z", "Y"),  # claim: "Z confounds X->Y" (confidence: 0.80, source: doi:10.zzz)
])

inference = CausalInference(model)
adjustment_sets = inference.get_all_backdoor_adjustment_sets("X", "Y")
```

### ChiRho Export

Generates a Pyro model + handler setup:

```python
# Generated from inquiry: <slug>
# Source graph: knowledge/graph.trig (rev: <hash>)
import pyro
import pyro.distributions as dist
from chirho.interventional.handlers import do

def causal_model():
    Z = pyro.sample("Z", dist.Normal(0, 1))  # observed, source: doi:10.yyy
    X = pyro.sample("X", dist.Normal(Z, 1))  # treatment
    Y = pyro.sample("Y", dist.Normal(X + Z, 1))  # outcome

# Interventional query: P(Y | do(X=1))
with do(actions={"X": torch.tensor(1.0)}):
    # Use Pyro's Predictive for inference
    ...
```

### Export Principles

- Exports generate **scaffold** code, not fitted models. The researcher fills in distributional assumptions, priors, and data.
- Provenance comments link every edge to its source claim/DOI.
- Graph revision hash is embedded for reproducibility.
- A `TODO` section notes latent variables and unresolved assumptions.
- `pgmpy` and `chirho` are optional extras (`[causal]` in pyproject.toml), not required deps.

## Scope Boundaries

**In scope:**
- `--type causal` on `inquiry init`, stored as `sci:inquiryType`
- `sci:treatment` and `sci:outcome` predicates
- `/science:build-dag` and `/science:critique-approach` commands
- `inquiry export-pgmpy` and `inquiry export-chirho` CLI commands
- Causal-specific validation checks
- `skills/models/causal-dag.md` skill
- `pgmpy` and `chirho` as optional `[causal]` extras
- Tests for all new functionality
- Run on exemplar project to close Phase 4 gate

**Out of scope (deferred):**
- PyMC export — defer to future need
- Inquiry-as-pure-projection refactor — see `docs/plans/2026-03-07-inquiry-projection-refactor.md`
- Multi-view inquiries (theoretical + computational as distinct sub-graphs)
- Fitted model generation (exports are scaffolds)
- Dataset discovery, data validation, pipeline generation — moves to 4c

## Phase 4 Gate

> "At least one optional path (causal modeling or software/data operationalization) runs end-to-end with reproducible outputs."

**Demonstrated by:** Build a causal DAG for the 3d-attention-bias exemplar project, export to pgmpy for identifiability analysis and to ChiRho for interventional query scaffold, archive evidence.
