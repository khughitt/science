---
id: paper:Hoover2009
kind: paper
title: Identity, Structure, and Causal Representation in Scientific Models
status: active
paper_kind: ''
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Hoover2009
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0003-causal-synthesis-guardrails
- question:0010-causal-graph-construction-pipeline
- question:0019-powers-vs-laws-causal-edge-ontology
- question:0031-structural-modularity-in-causal-patches
created: '2026-07-10'
updated: '2026-07-10'
---
# Identity, Structure, and Causal Representation in Scientific Models

- **Authors:** Kevin D. Hoover
- **Year:** 2009
- **Venue:** Working paper / conference paper, Duke University (presented at Modeling the World: Perspectives from Biology and Economics, Helsinki, May 2009)
- **DOI/URL:** http://www.econ.duke.edu/~kdh9/research.html (no DOI; working paper)
- **BibTeX key:** Hoover2009
- **Source:** PDF

## Key Contribution

Hoover develops a **structural account of causal order** — a formal generalization of Herbert Simon's (1953) parameter-based approach to causal representation — and uses it to resolve several contested issues in the philosophy of causation: the identity conditions for causal mechanisms, the nature and limits of modularity, the scope of Woodward's manipulability account, and whether types such as sex and race can be causes [@Hoover2009].
The core technical claim is that causal order is determined by a privileged parameterization (satisfying the Reichenbach Convention: parameters are variation-free) rather than by graphs or equations alone, and that two causal systems are **identical** if and only if they share the same structural form and parameter space and differ only in token parameter values.
The account handles recursive (DAG), cyclical/simultaneous, and cross-equation-restricted (Lucas-critique) systems, and defines direct cause, mutual cause, and causal independence through subset relations among parameter sets in partial solutions.

## Methods

The paper is a theoretical/philosophical analysis combining formal econometric methodology with philosophy of science.

**Core formal machinery.** A causal system `S: V = F(V; P)` maps variables and variation-free parameters to variables. A *complete solution* `V = Ψ(P)` expresses each variable as a function of parameters only. A *partial solution* `V₁ = Ψ(P | V₂)` conditions out a subset of variables, analogous to conditional probability. The causal direction between two variables is read off subset relations among their parameter sets:
- **Direct cause**: `V₁ → V₂` iff `P₁² ⊂ P₂²` (parameter set of V₁ is a strict subset of that of V₂ in the partial solution conditional on remaining variables).
- **Mutual/simultaneous cause**: `V₁ ↔ V₂` iff `P₁² = P₂²`.
- **Causal independence**: `V₁ ⊥ V₂` iff `P₁² ∩ P₂² = ∅`.

**Reichenbach Convention.** Parameters are required to be variation-free (no mutual constraints); apparent parameter dependencies are moved into functional forms, restoring variation-freedom. This convention is purely representational, not metaphysical.

**Causal field.** From Anderson (1938) and Mackie (1980): background conditions are impounded by fixing parameters to constants, absorbing their causal role into functional forms. This enables hierarchical, context-relative causal analysis without eliminating the background structure.

**Worked examples** drawn from macroeconomics: simple three-variable recursive systems, the Lucas-critique rational-expectations monetary policy model (cross-equation restrictions), and simultaneous systems (IS-LM style). Cartwright's carburetor and toaster counterexamples to modularity are reanalyzed.

## Key Findings

**Structural account subsumes Simon.** Simon's original account of causal order applied only to linear recursive (DAG) systems. The structural account handles cyclical/simultaneous systems (systems with no self-contained subsystems under Simon's definition) and cross-equation restrictions (nonlinearity in parameters), which Simon could not.

**Independence from functional form.** The partial solution — and thus the causal order it reveals — is uniquely recoverable from the complete solution regardless of how the system of equations is initially written. Different notational choices cannot change the causal verdict; the privileged parameterization is the anchor.

**Modularity holds at parameter level, not mechanism level.** Woodward requires that causal systems be modular (each equation can be disrupted without affecting others). The structural account shows Woodward's definition of direct cause is too strong: it rules out causal systems that display genuine causal structure but fail the come-what-may intervention test (e.g., carburetors, steam engines, Lucas-critique monetary systems). Modularity holds conventionally at the parameter level (the Reichenbach Convention forces it) but not necessarily at the level of mechanisms or equations. This vindicates Cartwright's critique of Woodward while preserving the structural account's content.

**Identity conditions for causal mechanisms.** Two mechanisms are causally identical iff they share the same variable set, parameter space (same parameters, not just same values), and functional form — differing only in token parameter values. This precise identity criterion is unavailable in graph-only or equation-only representations.

**Causal identity without token intervention.** Woodward's account requires defining cause through a token intervention on a variable. The structural account defines cause through type-level parameter subset relations; token interventions are not definitionally required. This allows counterfactual causal questions (comparative statics, causal questions about sex/race/species) to be well-posed even where no physical transformation is possible, provided causal identity (shared functional structure and parameter space) is established.

**Lucas critique as structural phenomenon.** Cross-equation restrictions arise when a parameter appears in multiple equations (e.g., forward-looking expectations). In such systems, "wiping out" one causal arrow per Woodward's intervention does not merely alter a parameter value — it can destroy the meaning of parameters in other equations. The structural account represents this directly: a come-what-may intervention on one equation can structurally alter the causal order of the remaining system, not just its parameterization.

## Relevance

This paper is a foundational reference for the Science toolkit's causal representation layer, with several direct load-bearing connections:

**1. Privileged parameterization as the semantic grounding of causal edges** (`hypothesis:0007-working-model`, `question:0010-causal-graph-construction-pipeline`). The structural account shows that a causal graph edge is not a primitive; it is a shorthand for a privileged parameterization that determines which variables' parameter sets are nested in which. In the toolkit, this implies that a causal edge should carry — or at least be traceable to — the parameterization that grounds it. An edge without an identifiable parameterization substrate is representationally incomplete.

**2. Causal-system identity as a constraint on causal strengthening** (`hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening`, `question:0003-causal-synthesis-guardrails`). The structural account's identity conditions give a precise criterion for when two pieces of evidence bear on *the same* causal proposition: they must concern the same variables under the same causal structure (same parameter space and functional form). Evidence gathered under a different structure — even if superficially about the "same" variables — targets a different causal system and should not naively strengthen the same proposition. This sharpens the toolkit's existing guardrail logic: the guardrail is not just about estimand mismatch in the statistical sense, but about structural-identity mismatch at the model level.

**3. Modularity failure as a reason code** (`hypothesis:0003-reason-coded-revisiting-beats-posterior-only-revisiting`). The Lucas critique and carburetor examples show that modularity failure is a specific, identifiable failure mode: the causal system has cross-equation parameter dependencies that make come-what-may interventions structurally destructive. The toolkit's reason-code vocabulary should include `modularity-failure` or `cross-equation-restriction` as a distinct reason code separate from `hidden-variable-risk` or `missing-identification`. Evidence gathered by an intervention that breaks modularity is structurally different from evidence gathered under proper causal isolation.

**4. Causal field and contextual scoping** (`hypothesis:0007-working-model` patch concept). The causal field (fixing parameters to constants to focus analysis) maps directly onto the toolkit's patch concept: a patch is exactly a local causal neighborhood in which background conditions have been impounded in the causal field. The structural account clarifies that this is not an approximation or an error but a principled representational choice — it changes the effective scope, not the underlying causal structure.

**5. Relation to `question:0019-powers-vs-laws`**. Hoover's structural account is a third position beyond Woodward's manipulability and Cartwright's dispositionalism: it grounds causation in structural/representational invariance of parameterizations rather than either powers or governing laws. This enriches the option space for the toolkit's causal-edge ontology question.

**Note on natural-systems relevance.** This paper is also relevant to the `natural-systems` project (pan-disease), which uses causal graphs over biological systems. Many biological causal systems exhibit the Lucas-critique-like cross-equation restriction pattern (feedback loops, pathway cross-talk) and the modularity-failure pattern (interventions that destroy causal relationships rather than isolating them). The structural account's treatment of cyclical/simultaneous causation directly addresses these cases.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Privileged parameterization | Causal-edge substrate (what grounds a directed edge) | An edge is shorthand for a nested parameter-set relation; needs parameterization to be semantically grounded |
| Variation-free parameters (Reichenbach Convention) | Variation-free independent evidence | Parameters that are mutually constrained violate the convention; analogously, evidence sources with shared dependencies violate independence assumptions |
| Causal system identity (same variables + parameters + functional form) | Structural identity constraint on evidence aggregation | Two evidence items must target the same causal system to be jointly interpreted |
| Causal field (background conditions fixed as constants) | Patch scope / context-local analysis | A patch fixes the causal field; cross-patch reasoning must make field assumptions explicit |
| Cross-equation restriction / Lucas critique | Modularity-failure reason code | Evidence from come-what-may interventions in non-modular systems is structurally invalid; needs its own reason code |
| Partial solution (conditional causal order) | Conditional causal structure | Conditional causal claims in the toolkit should specify the conditioning variable set |
| Direct / mutual / independent causal relations | Directed / bidirected / absent edge types | Three-way topology of causal relations matches the existing graph edge vocabulary |
| Simon's hierarchical systems | Patch nesting / federation ladder | Patches that contain sub-patches correspond to Simon's hierarchies of self-contained subsystems |
| Causal identity of tokens (applicant = vector of causally relevant variables) | Entity as variable bundle | Categorical entities (disease, gene, patient) are represented as variable bundles; causal questions concern bundle-level relationships |

## Limitations

The paper is a theoretical/philosophical analysis with worked mathematical examples but no empirical applications or computational implementations:
- The formal account is stated for finite systems of equations with a fixed structure; it does not directly address the case where structure itself is uncertain (as in causal discovery from data).
- The paper assumes a structural causal model perspective throughout and does not fully engage with the potential-outcomes (Rubin) framework, which is widely used in epidemiology and social science.
- The Reichenbach Convention (variation-free parameters) is asserted as a representational choice, not motivated by an underlying metaphysics; the paper does not address what to do when genuinely non-separable parameters are encountered (e.g., quantum entanglement, social mechanisms with constitutive interdependence).
- The treatment of cyclical systems (simultaneous causation) stops at identification of mutual-cause structure; it does not provide identification or estimation strategies for such systems (this is acknowledged as outside scope).
- The paper's engagement with Cartwright focuses on the carburetor and toaster examples; it does not address Cartwright's positive account (capacities / nomological machines) in depth, which is the subject of `question:0019-powers-vs-laws-causal-edge-ontology`.

## Model / Tool Availability

No software artifact. This is a philosophical/theoretical working paper. The formal account of causal order can be mechanized, but no implementation is provided.

## Follow-up

- Hoover (2001), *Causality in Macroeconomics* (Cambridge UP): the earlier monograph that this paper extends; contains fuller treatment of empirical causal inference strategies.
- Woodward (2003), *Making Things Happen*: the manipulability account under critique here; already on the intake list.
- Cartwright (2007), *Hunting Causes and Using Them*: the pluralistic account Hoover reacts to; directly relevant to `question:0019`.
- Pearl (2000), *Causality*: the graphical framework with which the structural account is compared; already cited widely in the project.
- Simon (1953), "Causal Order and Identifiability" (in Hood and Koopmans 1953): the source this paper extends; historical but load-bearing for understanding the parameterization idea.
- Spawns new question: how should the toolkit represent modularity status and cross-equation restrictions as properties of a causal patch or causal edge? See `question:0031-structural-modularity-in-causal-patches`.
