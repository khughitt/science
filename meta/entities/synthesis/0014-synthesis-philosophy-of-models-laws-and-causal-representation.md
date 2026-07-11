---
kind: synthesis
title: 'Synthesis: Philosophy of Models, Laws, and Causal Representation'
status: active
created: '2026-07-10'
updated: '2026-07-10'
id: synthesis:0014-synthesis-philosophy-of-models-laws-and-causal-representation
report_kind: paper-batch-synthesis
generated_at: '2026-07-10T23:27:24-04:00'
source_commit: 2da34b4e55374c9de1e29aa8e0454c1bfd411e33
source_refs:
- paper:Giere2004
- paper:Ghins2011
- paper:Frigg2025
- paper:Tahko2023
- paper:Mumford2004
- paper:Gaspar2024
- paper:Hoefer2023
- paper:Cornelissen2025
- paper:Keil2006
- paper:Hoover2009
- paper:Baumeler2025
- paper:Almodovar2025
- paper:Kornblith2019
- paper:Groger2025
- paper:Findley2021
- paper:Liu2025
- paper:Besharatifard2024
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0001-stochastic-revisiting
- hypothesis:0005-sequential-evidence-improves-attention
- hypothesis:0006-adaptive-project-topology-improves-research-fit
- synthesis:0003-synthesis-causal-graph-construction-and-discovery
- synthesis:0007-project-synthesis-science-meta
- topic:structured-scientific-knowledge
---

# Synthesis: Philosophy of Models, Laws, and Causal Representation

## TL;DR

This batch is the philosophical foundation the Science working model (`hypothesis:0007-working-model`) had been asserting without a literature behind it.
Seventeen papers — a dense core of philosophy-of-science (models, representation, laws, mechanisms) plus a supporting ring of causal-inference and machine-learning method papers — converge on one load-bearing claim: **science is a patchwork of locally-valid, purpose-indexed, uncertainty-bearing models, not a pyramid deducible from universal laws** [@Frigg2025; @Mumford2004; @Gaspar2024; @Giere2004].
That is exactly the toolkit's "federated patchwork of epistemic neighborhoods" picture, and the batch supplies both its grounding and its guardrails: causal edges need modal/structural truthmakers, not bare arrows [@Tahko2023; @Hoover2009; @Hoefer2023]; agent-authored explanatory claims are at systematic risk of the illusion of explanatory depth [@Keil2006]; and patch federation can borrow concrete representation-similarity metrics (CKA, STRUCTURE) from ML [@Kornblith2019; @Groger2025].

## Key Contribution

The batch answers a question the project had left as an act of faith: *is the patchwork working model philosophically legitimate, or is it a workaround for not having a unified theory of the graph?*
The answer is that the patchwork is the faithful representation, corroborated from three independent directions — metaphysics (powers, not governing laws) [@Mumford2004], philosophy of science (autonomous mediating models) [@Frigg2025; @Giere2004], and physics (cosmological evidence forbids universal law-sets) [@Gaspar2024].
It simultaneously supplies the missing schema requirements that turn "patch" from a metaphor into an entity with fields: a `purpose` slot [@Giere2004], a model-system-vs-target-system claim distinction [@Tahko2023], enabling-condition / nomological-machine boundaries [@Gaspar2024], structural-identity conditions for when two evidence items concern the *same* causal system [@Hoover2009], and mechanism-perspective typing for causal evidence [@Cornelissen2025].
The single most-cited missing text across the batch is **Cartwright (1999), *The Dappled World*** — flagged as the keystone source by [@Mumford2004], [@Frigg2025], [@Gaspar2024], and [@Cornelissen2025] independently.

## Methods

The synthesis compares seventeen local paper summaries and organizes them into six sub-themes running from the most abstract (what a model *is*) to the most operational (metrics and AI tooling).
It prioritizes implications for the toolkit's graph-oriented working model, causal-edge semantics, evidence-payload schema, and belief-calibration machinery over the domain-specific content of any single paper (cosmology, drug synergy, neural-network internals).
Because the philosophy core is partial-source in one case ([@Mumford2004] is a publisher preview, Chapter 1 only) and pre-computational throughout, all cross-links to toolkit code are treated as architectural conjectures to be operationalized, not settled requirements.

## Sub-Theme 1: Scientific Representation and Models

**Shared finding.** Models are autonomous epistemic agents that mediate between theory and world, not formal shadows of theory; they represent through partial, purpose-selected, ineliminably idealized resemblance rather than mirror-copying [@Frigg2025; @Giere2004; @Ghins2011].
Frigg and Hartmann's SEP survey is the canonical anchor: it names and legitimizes the "patchwork of models" picture (Cartwright/Hacking), the object/target-vs-meta/representation split (surrogative reasoning), the ineliminable-idealization ceiling on calibration, and Levins's irreducible accuracy/generality/simplicity trade-off — each of which maps onto a toolkit construct (`object_layer`/`meta_layer`, the L0–L4 ladder, the belief ceiling) [@Frigg2025].
Giere sharpens this into an operational schema: **S uses X to represent W for purposes P** — representation is a four-place, agent-and-purpose-indexed act, and principles (Newton's laws, natural selection) are *templates* for building models, not empirical claims [@Giere2004].
Tahko supplies the modal underpinning: every model represents a *network of possibilities* grounded in the modal properties of actual entities, so even fictional/idealized models have actual-world truthmakers via isomorphism of counterfactual structure [@Tahko2023].

**Tension (flagged for h0007).** There is a genuine, unresolved split on *what grounds representation*.
Ghins argues contact with reality rests on the truth of **ontic judgements** (predicative acts attributing properties to real targets), grounded in the variety and concordance of independent measurements — a robustly realist, judgement-first, correspondence-leaning position [@Ghins2011].
Giere argues representation is **pragmatic and agent-based**: designated similarity requires no objective similarity measure, and multiple purpose-relative models of the same target coexist without conflict (water-as-molecules vs. water-as-fluid) [@Giere2004].
Frigg/Hartmann sit between them with perspectival realism [@Frigg2025].
This is the isomorphism/correspondence-vs-pragmatic axis, and it is not academic for the toolkit: it decides whether a proposition's truth-condition is "the graph structure is homomorphic to the target" (structural) or "an agent, for a purpose, judges this property to hold and independent measurements concur" (pragmatic/judgement).
The toolkit's provenance-and-purpose-indexed, multi-source-corroboration design already leans Giere/Ghins-pragmatic — every patch is authored *by* an agent *for* a purpose — but the batch shows this is a live philosophical commitment that should be made explicit, not smuggled in.

**Implication.** Adopt Giere's four-place schema as the patch's identity: the patch is X, provenance fills S, `object_layer` fills W, and **P (purpose) is currently missing from the patch schema** — Giere and question:0027 both motivate adding it.
Ghins's success/correctness distinction (does the node *denote* a real relation vs. does it *accurately characterize* it) is a candidate two-field split on proposition nodes, and his measurement-concordance argument for realism is precisely what H02's multi-source evidence corroboration operationalizes.

## Sub-Theme 2: Laws, Powers, and the Dappled/Patchwork World

**Shared finding — the strongest convergence in the batch.** Three papers arriving from three disjoint routes reach the same anti-Humean, patchwork conclusion, which is the direct philosophical grounding for h0007.
Mumford's *realist lawlessness*: properties are intrinsically modal (power-bearing), so distinct "governing laws" are explanatorily redundant — "the world is more of a jigsaw than a mosaic" [@Mumford2004].
Gaspar and Tambor show the *same* patchwork is forced by physics: cosmological evidence (fine-tuning, the dark sector, singularity regimes) makes a static universal law-set untenable, the Standard Cosmological Model itself behaves as a Cartwright **nomological machine** generating the expansion law only within its boundary conditions, and Smolin–Unger's *false universality* and *false anachronism* are named methodological errors [@Gaspar2024].
Frigg/Hartmann independently report the Cartwright/Hacking patchwork-of-models thesis as the mainstream philosophy-of-science position [@Frigg2025].
Hoefer's SEP entry closes the modal side: determination is logical entailment, determinism is neither predictability nor fatalism, and — critically for the project's D-003 — **non-trivial objective chances strictly in (0,1) are compatible with determinism** under a Humean account; a finite embedded agent cannot even distinguish deterministic chaos from genuine stochasticity [@Hoefer2023].

**Tension.** The batch is anti-Humean at its core (Mumford's powers, Tahko's objective modal properties, Cartwright's capacities) but Hoefer's compatibilist move — Humean best-systems chances suffice to justify (0,1) beliefs — means the toolkit does **not** have to buy the full powers metaphysics to license its continuous-belief representation. D-003 is over-determined: it holds under both the anti-Humean and Humean readings, which is a robustness result, not a conflict to resolve.

**Implication.** h0007's patchwork is grounded twice over — metaphysically [@Mumford2004] and physically [@Gaspar2024] — and this is a promotion-worthy result: the patchwork is a feature (faithful to how laws actually work), not a limitation of the graph.
Gaspar's *false universality* is the cosmological paradigm case of H04's core problem (evidence from domain A silently licensing an update in domain B), and his nomological-machine framing motivates recording each patch's **enabling conditions / boundary** (question:0036), so a causal edge is explicitly scoped to the machine that generated it.
The **key missing intake is Cartwright's *The Dappled World* (1999)** — it is the common ancestor of Mumford, Gaspar, Frigg/Hartmann, and Cornelissen, and every one of them defers to it.

## Sub-Theme 3: Mechanisms and Explanation

**Shared finding.** "Mechanism" is not one thing, and neither is "explanation."
Cornelissen and Werner identify three methodologically distinct mechanism perspectives — **interventionist** (mediating variables, RCT/quasi-experiment), **contextual** (situated process, case-inferred), and **constitutive** (integrative micro-macro / bathtub) — each with its own inferential blind spot (microscopic bias, surface contingency, stylized projection), and argue that *epistemological pluralism* (perspective-taking / causal triangulation) is what strengthens mechanism inference [@Cornelissen2025].
Keil supplies the cognitive-science counterpart and the batch's sharpest warning: the **illusion of explanatory depth (IOED)** — people (and, by extension, LLM agents) systematically and specifically overestimate their grasp of causal mechanisms (not of facts or procedures), confusing knowing a *function* for understanding a *mechanism*, and cope with inevitable incompleteness by outsourcing to trusted experts and maintaining skeletal causal gists [@Keil2006].

**Tension.** Cornelissen's pluralism says accept interventionist, contextual, and constitutive evidence — but as evidence bearing on *different* aspects/layers, never as interchangeable support for the same edge; naive synthesis that pools them commits a category error. Keil says the very act of producing an explanation is where confidence should *drop*, which is in tension with any pipeline that rewards fluent agent-authored explanations with higher belief.

**Implication.** A patch is exactly Keil's "causal gist": a bounded neighborhood with known incompleteness, and h0007's explicit provenance + uncertainty representation is a mechanism for making explanatory gaps *visible* — a structural counter to IOED.
Concretely: add a `mechanism_perspective` field (interventionist/contextual/constitutive) to the evidence payload so guardrails can be perspective-aware (question:0022), and treat IOED as a first-class threat to agent-authored explanatory claims (question:0021) — a `functional_relation_only` evidence tag and reason codes like `function_for_mechanism`, `implicit_only`, `situationally_supported`, `outsourced` flag propositions whose stated confidence may be explanatory illusion rather than mechanistic grounding (feeds H03's reason-coded revisiting).
Outsourced-explanation provenance should record not just the source but the delegating agent's *own* verification depth (question:0023).

## Sub-Theme 4: Causal Structure and Representation

**Shared finding.** A causal edge is not primitive — it is shorthand for a structure that needs an explicit substrate.
Hoover grounds causal order in a **privileged (variation-free) parameterization**: two causal systems are *identical* iff they share variables, parameter space, and functional form, and modularity holds at the parameter level but can fail at the mechanism level (carburetors, the Lucas critique) — vindicating Cartwright against Woodward's too-strong come-what-may intervention test [@Hoover2009].
Baumeler and Wolf make causal structure **dynamical**: the effective structure changes as agents intervene sequentially, a single cyclic graph encodes many operational structures (the "flow"), and a parameter-free **superflow** answers qualitative causal-order questions from structure alone [@Baumeler2025].
Almodóvar et al. (DeCaFlow) operationalize the estimand side: correct interventional/counterfactual estimates under hidden confounding via **proxy variables**, with an explicit identifiability tier (do-calculus / proxy-identifiable / unidentifiable) [@Almodovar2025].
Hoefer supplies the ceteris-paribus backstop: every event-level sufficient-cause claim hides an open-ended exclusion list [@Hoefer2023].

**Tension.** Baumeler's superflow says *structure alone* answers real causal questions (a case for a parameter-free structural layer); DeCaFlow says correct causal *magnitudes* need the full parameterized model plus proxy machinery. These are complementary, not contradictory — they argue for **separating a structural-hypothesis evidence role from an estimand-bearing one** (superflow ↔ `evidence_role: structural_hypothesis`; DeCaFlow ↔ estimand + `identification_status`).

**Implication (H04).** The guardrail is not only statistical estimand-mismatch but **structural-identity mismatch** (Hoover): evidence gathered under a different causal structure targets a different system and must not strengthen the same proposition.
New payload fields the batch demands: `identification_status` (do-calculus/proxy/unidentifiable), `proxy_vars`/`null_proxy_vars`, `hidden_confounder` node annotation, `structural_only` flag, and a `modularity-failure`/`cross-equation-restriction` reason code [@Hoover2009; @Almodovar2025; @Baumeler2025].
Causal structure may need an *intervention-history* or *regime* index (question:0028) — reinforced by Gaspar's mutable-law argument in Sub-Theme 2.

## Sub-Theme 5: Representation Similarity and Alignment

**Shared finding.** The abstract "latent common axis" glue in h0007 has concrete, validated operational metrics.
Kornblith et al. give **Centered Kernel Alignment (CKA)** — a principled representation-similarity index (normalized HSIC) that reliably identifies layer correspondences across initializations, widths, and architectures where CCA-family methods fail, with a proof that invertible-linear invariance is pathological when dimensionality exceeds sample count [@Kornblith2019].
Gröger et al. (STRUCTURE) show that preserving **multi-scale neighborhood geometry** during alignment (plus selecting the most cross-modally similar *intermediate* layers, per the Platonic Representation Hypothesis) achieves high-quality alignment with <1% of the usual paired data — directly the "limited cross-source pairing" regime the toolkit faces when aligning literature, database, and experimental evidence [@Groger2025].

**Tension.** CKA collapses two representation spaces to a single scalar and can read high even when the shared subspace is low-dimensional; it is not a calibrated distance and needs per-domain thresholding before it can gate federation. STRUCTURE preserves *relational* structure but is COCO-centric and needs in-domain supplements for specialized scientific domains. So the metrics are candidates, not drop-in solutions — they need empirical calibration on Science's own patch embeddings.

**Implication.** CKA is the concrete candidate implementation of the `latent_common_axis` glue metric (question:0033); its invariance analysis (orthogonal + isotropic-scaling, *not* invertible-linear) tells the toolkit exactly what "same representation" should mean when comparing patches, and the `p >= n` pathology warns against over-invariant indices in small-data patches.
STRUCTURE's geometry-preservation principle answers "how do you align sources without destroying each source's informative internal structure" (question:0034), and its RSM/concordance framing is a practical realization of Ghins's variety-and-concordance-of-measurements grounding from Sub-Theme 1.

## Sub-Theme 6: Methodology and AI-as-Research-Tool

**Shared finding.** Three method papers discipline how the toolkit imports evidence and uses AI.
Findley et al. extend UTOS into **M-STOUT** (adding Mechanisms and Time), distinguish generalizability (S ⊆ P, PATE) from transportability (S ⊄ P_target, TATE), and decompose external-validity bias into sample-selection and variable-selection components — sharpening exactly what H04's "transport assumptions" must cover [@Findley2021].
Liu et al. (BAITSAO) show LLMs as **fallible embedding engines with measurable fidelity** (GPT-3.5 embeddings ≈ GPT-4 ≈ Claude 3.5 on the task, validated against curated DrugBank) and demonstrate that added information is *not* uniformly beneficial — a Help-Harm matrix shows some signals hurt joint objectives [@Liu2025].
Besharatifard and Vafaee document, across 25 GNN drug-synergy models, the benchmark-discipline failure mode: no shared dataset, inconsistent synergy metrics/thresholds/splits make cross-study comparison uninformative, and richer heterogeneous features reliably beat single-feature baselines [@Besharatifard2024].

**Tension.** BAITSAO and Besharatifard both show "richer features help" (supporting H02) — but BAITSAO's Help-Harm matrix shows the marginal contribution of an added signal can be *negative*, so H02's "rich payloads improve calibration" must be qualified: payloads should be selected by cross-task improvement profile, not assumed additive. Besharatifard also warns that GNN attention weights are aggregation weights, *not* evidential support — a semantic distinction the toolkit must preserve (relevant to H05).

**Implication.** Add `temporal_scope`, `mechanism_invariance_claim`, and an explicit generalizability-vs-transportability type (PATE/TATE) to evidence payloads, and split H04's transport-assumption field into sample-selection vs. variable-selection paths [@Findley2021].
Represent LLM-derived fields as **sources with measurable fidelity, not infallible extractors**, with a minimal validation protocol against a curated reference (question:0038) [@Liu2025].
Science's benchmark tooling must enforce fixed splits, logged preprocessing, and metric provenance to avoid Besharatifard's fragmentation, and prefer AUPR over AUC-ROC under class imbalance; heterogeneous typed-edge propagation is a distinct graph-model question (question:0039) [@Besharatifard2024].

## Cross-Cutting Threads

**(a) The patchwork/dappled convergence — the batch's headline.**
Mumford (metaphysics), Gaspar (cosmology), Frigg/Hartmann (philosophy of science), and Giere (representation) independently converge on locally-valid, non-deductively-related models as the true shape of scientific knowledge [@Mumford2004; @Gaspar2024; @Frigg2025; @Giere2004]. This is the strongest single grounding h0007 has ever had, and it is triangulated across disjoint literatures rather than resting on one source. The convergence has a named common ancestor — **Cartwright's *The Dappled World* (1999)** — which is absent from the collection and is the batch's most important missing intake.

**(b) Representation-as-isomorphism vs. pragmatic/agent-based — the open axis (Sub-Theme 1).**
Ghins (judgement/correspondence-leaning) vs. Giere (pragmatic/purpose-indexed), with Frigg/Hartmann's perspectival realism between them [@Ghins2011; @Giere2004; @Frigg2025]. The toolkit's design already leans pragmatic; the batch makes that a decision to own explicitly. This is the one place where the batch does not converge, and it directly conditions how proposition truth-conditions are defined.

**(c) IOED as a concrete threat to agent-authored claims (Sub-Theme 3).**
Keil's illusion of explanatory depth is domain-specific to causal mechanism and empirically robust; an LLM stating a mechanistic claim is a prime candidate for artificial IOED [@Keil2006]. This is the most actionable threat-model finding in the batch and it cuts across H02, H03, and the LLM-as-fallible-source line (Liu).

**(d) CKA and STRUCTURE as operational patch-similarity metrics (Sub-Theme 5).**
The two ML papers convert h0007's hand-wavy "latent common axis" into candidate, empirically-validated procedures with known invariance properties and known failure modes [@Kornblith2019; @Groger2025]. They are the batch's clearest path from philosophy to code.

## Implications for Science

**1. The patch schema needs a `purpose` slot and a claim-layer distinction.**
Giere's P and Tahko's model-system-vs-target-system split are both currently absent; adding them turns "patch" from metaphor into a schema with identity conditions [@Giere2004; @Tahko2023].

**2. Causal edges need structural/modal substrate metadata, not just estimands.**
`identification_status`, `structural_only`/`evidence_role: structural_hypothesis`, `proxy_vars`/`null_proxy_vars`, `hidden_confounder`, structural-identity checks, and a `modularity-failure` reason code [@Hoover2009; @Almodovar2025; @Baumeler2025].

**3. Patches should record enabling conditions / domain scope (nomological-machine boundary).**
A causal edge is valid only within its patch's boundary conditions; asserting it beyond is false-universality in miniature [@Gaspar2024].

**4. Add mechanism-perspective typing and IOED reason codes.**
`mechanism_perspective` (interventionist/contextual/constitutive) for perspective-aware guardrails and cross-perspective triangulation; `functional_relation_only` + IOED reason codes to flag explanatory-illusion risk on agent-authored claims [@Cornelissen2025; @Keil2006].

**5. External-validity vocabulary belongs in the payload.**
Generalizability-vs-transportability type, PATE/TATE estimand, M-STOUT axes, `temporal_scope`, split sample- vs. variable-selection bias in the transport field [@Findley2021].

**6. Treat LLM-derived fields as fidelity-measured sources; enforce benchmark discipline.**
Validate embeddings/extractions against curated references; do not assume added payloads are additive (Help-Harm); enforce fixed splits + metric provenance; prefer AUPR under imbalance [@Liu2025; @Besharatifard2024].

**7. CKA is the candidate `latent_common_axis` metric; STRUCTURE the candidate alignment regularizer.**
With per-domain calibration and attention to the `p >= n` pathology and small-data geometry loss [@Kornblith2019; @Groger2025].

**8. D-003 is over-determined and should stay.**
Non-trivial (0,1) chances are licensed under both anti-Humean and Humean readings; a finite agent cannot certify determinism from finite observation, so hard-gating a low-evidence claim is never warranted (grounds H01) [@Hoefer2023].

## Open Questions

1. Does the toolkit commit to a pragmatic/agent-based (Giere) or judgement/correspondence (Ghins) account of proposition truth-conditions — or hold perspectival realism (Frigg) explicitly as a middle position?
2. Should proposition nodes carry Ghins's success (denotation) vs. correctness (characterization) as two separate fields?
3. Should causal edges carry a structural-identity fingerprint (Hoover's variables + parameter space + functional form) so aggregation can check same-system-ness before strengthening?
4. What is the minimal validation protocol before an LLM-derived embedding/field is admitted as evidence (question:0038)?
5. Should isomorphism-of-counterfactual-structure (Tahko/Bokulich) be a formal inter-patch relation type, stronger than latent-axis similarity but weaker than reduction (question:0026)?
6. How should Science distinguish and store the three mechanism perspectives so triangulation strengthens *different* edges rather than double-counting one?

## Prioritized Follow-ups

**P1: Intake Cartwright (1999), *The Dappled World*.**
The keystone missing text, deferred to by [@Mumford2004], [@Frigg2025], [@Gaspar2024], and [@Cornelissen2025]. Its nomological-machine and patchwork-of-laws arguments are the common ancestor of the entire Sub-Theme 2 convergence.

**P2: Add `purpose` (Giere P) and a model-system-vs-target-system claim-layer to the patch/evidence schema.**
Turns h0007's patch into a schema with identity conditions [@Giere2004; @Tahko2023].

**P3: Extend H04 with structural-identity + proxy-identifiability guardrail fields.**
`identification_status`, `structural_only`, proxy/null-proxy vars, structural-identity check, `modularity-failure` reason code [@Hoover2009; @Almodovar2025; @Baumeler2025].

**P4: Operationalize CKA as the `latent_common_axis` patch-federation similarity metric.**
With STRUCTURE-style geometry preservation for low-pairing alignment; calibrate thresholds per domain [@Kornblith2019; @Groger2025].

**P5: Add an IOED guard for agent-authored explanatory claims.**
`functional_relation_only` tag + IOED reason codes feeding H03; a Rozenblit-Keil-style explanation-generation probe as an agent-calibration check [@Keil2006].

**P6: Record patch enabling-conditions / domain-scope (nomological-machine boundary) and external-validity type.**
Domain/regime scope on causal propositions; generalizability-vs-transportability + M-STOUT + temporal scope on payloads [@Gaspar2024; @Findley2021].

## Known Gaps

- **Cartwright (1999) is unread.** The single load-bearing source of the patchwork convergence is absent; every downstream claim about the dappled world is currently second-hand (see P1).
- **[@Mumford2004] is a partial preview** (Chapter 1 only); the Central Dilemma, the positive powers account, and all objection-and-reply material are inaccessible and its chapter-level claims are from Mumford's own §1.6 summary, not the chapters.
- **The philosophy core is pre-computational.** None of Frigg, Giere, Ghins, Tahko, Mumford, Gaspar, Hoefer, Hoover advises on serialization or graph schemas; all toolkit mappings are architectural conjectures.
- **The representation-grounding axis is unresolved** (Ghins vs. Giere); the toolkit is leaning pragmatic without having recorded the decision.
- **CKA/STRUCTURE are ML-domain metrics** validated on vision/text, not on symbolic knowledge-graph patches; adopting them for patch federation requires separate calibration and a directed/causal-representation extension neither paper provides.

## Relationship to Existing Hypotheses and Topics

This batch most strongly strengthens `hypothesis:0007-working-model`, supplying its triangulated patchwork grounding (Sub-Themes 1–2) and the schema fields (`purpose`, enabling conditions, structural substrate) that make a patch a first-class entity.
It sharpens `hypothesis:0004` with structural-identity and proxy-identifiability guardrails (Sub-Theme 4) and the false-universality / external-validity scoping argument (Sub-Themes 2, 6).
It supports `hypothesis:0002` (richer payloads help — with the Help-Harm caveat) and `hypothesis:0003` (new IOED and modularity-failure reason codes), corroborates `hypothesis:0001`/D-003 via Hoefer's determinism-and-chance analysis, and touches `hypothesis:0006` through Giere's purpose-relative, adaptable project topology.
No existing topic covers philosophy-of-models, scientific representation, or laws/powers — the four current topics are analytic-flexibility, Bayesian continuous belief, cross-project coordination, and structured-knowledge/nanopublications. This batch warrants a **new topic** (see the accompanying recommendations) to house the philosophy-of-models / patchwork-epistemology core.
