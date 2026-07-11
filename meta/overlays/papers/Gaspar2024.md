---
id: paper:Gaspar2024
overlay_of: paper:Gaspar2024
pin_version: "1.0.0"
status: active
created: "2026-07-10"
updated: "2026-07-10"
source_refs:
- cite:Gaspar2024
related:
- hypothesis:0007-working-model
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- question:0019-powers-vs-laws-causal-edge-ontology
- question:0028-dynamical-causal-structure-representation
- question:0036-nomological-machine-patch-enabling-conditions
---
# The Laws of Nature and the Problems of Modern Cosmology

- **Authors:** Yves Gaspar and Paweł Tambor
- **Year:** 2024 (published online 17 February 2023; Foundations of Science vol. 29,
  pp. 847–870; CrossRef metadata reports year 2023 for the online-first record —
  the journal volume header reads 2024 and that is the citekey year used here)
- **Journal:** Foundations of Science
- **DOI:** 10.1007/s10699-023-09904-1
- **BibTeX key:** Gaspar2024
- **Source:** PDF (project file
  `~/d/science/meta/papers/pdfs/2024_Gaspar_laws-of-nature-problems-of-modern-cosmology.pdf`);
  DOI cross-checked via `science paper-fetch` (status: ok, source: crossref_text_mining)

## Key Contribution

Gaspar and Tambor argue that the concept of "law of nature" requires fundamental revision
in the context of modern cosmology. Drawing primarily on Nancy Cartwright's nomological
machine and Tim Maudlin's Fundamental Law of Temporal Evolution (FLOTE), they show
that cosmological evidence — unsolved problems of the Standard Hot Big Bang model,
the fine-tuning crisis, inflation's proliferation, and the dark energy/matter puzzle — makes
a static, universal conception of natural laws untenable. Laws are instead domain-specific,
potentially mutable across cosmic regimes, and subject to formal limits of computability.
The paper further shows that the Standard Cosmological Model (SCM/ΛCDM) can itself
be treated as a nomological machine in Cartwright's sense: a physical-theoretical arrangement
that generates the law of cosmic expansion within its operating domain but cannot be
extended without qualification to all regimes or all of cosmic history.

## Methods

This is a work of philosophy of science applying conceptual synthesis to contemporary
cosmology. The paper proceeds in four stages:

1. **Survey of law-of-nature theories** (§1): Humean best-systems/Lewis regularity
   account; universals-based Armstrong necessitation; van Fraassen/Giere antirealism;
   Maudlin's primitive-ontological ("ontological bedrock") account; Cartwright's
   capacities/nomological-machine account.
2. **Core frameworks** (§2): Detailed exposition of (a) Cartwright's nomological machine
   across three phases of her thought (*How the Laws of Physics Lie*, *The Dappled World*,
   *Nature the Artful Modeler*) and (b) Maudlin's FLOTE, its adjunct principles, boundary
   conditions, and support for counterfactuals and explanation.
3. **Cosmological case studies** (§3): Application of both frameworks to: the problems of
   the Standard Hot Big Bang model (flatness, horizon, singularity, fine-tuning, dark matter,
   dark energy); the Smolin–Unger critique of false universality and false anachronism;
   complexity theory and uncomputability (Moore 1990, Chaitin 2004); and the expansion
   law of the universe derived from the Robertson–Walker metric.
4. **Conclusion** (§4): Synthesis drawing on Mittelstaedt and Weingartner's eight
   interpretations of natural laws; realism/antirealism debate in cosmology.

No empirical data or computational experiments are generated; the paper is conceptual
with mathematical illustrations drawn from existing cosmological results (Friedmann
equations, Hubble–Lemaître law, R–W metric).

## Relevance

**Direct relevance to Science toolkit design:**

1. **Patchwork / federated model (H07 — strongest link).** Cartwright's explicit patchwork
   formulation is reproduced verbatim in the paper: "the laws that describe this world are
   a patchwork, not a pyramid." The Science working model (`hypothesis:0007-working-model`)
   describes knowledge as a "federated patchwork of epistemic neighborhoods." Gaspar2024
   shows that this patchwork structure is motivated not only by epistemological arguments
   (Mumford2004's realist lawlessness) but by *physical* ones: the cosmological evidence
   actively requires domain-local laws. The patchwork representation is not a limitation of
   knowledge but a faithful reflection of how laws work.

2. **False universality → cross-domain causal validity.** The Smolin–Unger false-universality
   critique maps directly to the toolkit's evidence-domain scoping problem: causal claims
   supported in one domain (e.g., low-energy physical regime, or a specific biological
   system) should not be silently assumed valid across all domains. This is an argument for
   the toolkit to carry explicit domain / regime / context annotations on causal propositions —
   a weakness that Gaspar2024 exposes as a methodological failure even in cosmology.

3. **Nomological machines → patches as enabling-condition sets.** Each toolkit patch is the
   analogue of a Cartwright nomological machine: a sufficiently stable arrangement generating
   regular enough causal relationships *within its boundary conditions*. The paper's argument
   that cosmological models function as nomological machines motivates the toolkit to
   represent the *background / enabling conditions* under which a patch's causal claims hold,
   not merely the claims themselves. A causal edge is valid only within the nomological
   machine (patch) that generated it; asserting it beyond that machine's domain is
   false-universality in miniature.

4. **Causal-estimand guardrails (H04).** The false-universality problem is structurally
   parallel to the guardrail problem: how does evidence gathered in domain A license an
   update to a causal proposition scoped to domain B? Both are failures of domain-scope
   specification. Gaspar2024 provides the cosmological paradigm case and argues that
   explicitly acknowledging the regime-dependence of laws is the correct response — an
   argument that extends to the toolkit's guardrail design.

5. **Dynamical / mutable causal structure (q0028).** FLOTE's emphasis on temporal
   evolution as fundamental and Smolin–Unger's mutable laws complement q0028's
   intervention-conditioned causal structure question. Both suggest that causal structure
   is not a static object but indexed by context (intervention history for q0028; energy
   regime / cosmic epoch for Gaspar2024). The toolkit may eventually need a regime or
   context index on causal propositions — a design decision motivated by both sources.

6. **Powers-based vs. laws-based edge ontology (q0019).** Cartwright's capacities-based
   account (which Gaspar2024 inherits) and Mumford2004's powers-based account (which
   q0019 is grounded in) converge: causal edges in the toolkit should represent intrinsic
   causal capacities of entities, not external laws governing them. Gaspar2024 adds
   cosmological support: even in the grandest domain, capacity-based and nomological-machine-
   based reasoning outperforms the appeal to universal laws.

7. **Natural-systems / cosmology cross-link (for commons promotion).** The paper's
   primary domain is cosmology (laws of physics, cosmic expansion, Big Bang). It is
   directly relevant to any Science project studying physical natural systems. This paper
   is a candidate for promotion to science-commons once cross-project synthesis is enabled.

## Project Framework Mapping

| Gaspar2024 Concept | Science Toolkit Concept | Notes |
|---|---|---|
| Nomological machine | Patch (epistemic neighborhood) | A patch is the toolkit's analogue of a stable-enough physical/causal arrangement generating regular laws |
| Patchwork of laws | Federated patchwork model (H07) | Cartwright's direct formulation; the terminological match is exact |
| False universality | Cross-domain causal validity | Causal propositions should carry explicit domain / regime annotations |
| False anachronism | Temporal / epoch-indexed causal claims | Laws valid in one cosmic epoch may not hold in another; analogous to time-indexed evidence payloads |
| FLOTE (temporal-evolution law) | Dynamic causal structure (q0028) | Both treat temporality as fundamental to the structure of laws / causal relationships |
| Ceteris paribus laws | Enabling conditions / causal field in a patch | Background conditions that make a causal edge hold within its patch boundary |
| Formal uncomputability | Prediction limits of probabilistic inference | Some system behaviors exceed what any fixed algorithm (causal model) can capture |
| SCM as nomological machine | Project-level causal model as a patch system | Cosmological model represents "everything" → a project's causal model represents its domain |
| Situation-specific model | Local epistemic neighborhood (patch) | Cartwright's situation-specific models are non-deductive, non-law-governed — like patches |
| "Knowledge how" vs. "knowledge that" | Functional vs. propositional causal claims | Functional causal knowledge (how the system evolves) is as legitimate as propositional |
| Mutable laws (regime-dependent) | Context-conditioned causal propositions | A causal proposition valid in one regime should carry its regime scope explicitly |
| Capacities (Cartwright) | Causal powers / intrinsic edge semantics (q0019) | Bridges Mumford2004 and Gaspar2024 into one coherent edge-semantics design argument |

## Model / Tool Availability

No software artifact. This is a philosophy-of-science journal article.

## Follow-up

- Read Cartwright (1999) *The Dappled World* — the primary source for the patchwork and
  nomological-machine concepts. Question `question:0019-powers-vs-laws-causal-edge-ontology`
  already flags this as a missing citation.
- Read Cartwright (2019) *Nature, the Artful Modeler* — the most recent development
  of her metaphysics of nature; Gaspar2024 cites her three-interpretation taxonomy of
  nature's nomological structure.
- Read Smolin and Unger (2015) *The Singular Universe and the Reality of Time* — the
  main source for false universality, false anachronism, and the mutability-of-laws argument.
- Cross-reference with `paper:Mumford2004`: both papers are Cartwright-adjacent; Mumford
  takes the metaphysical route (realist lawlessness / powers), Gaspar2024 takes the
  cosmological / philosophy-of-science route (nomological machines / mutable laws).
  Together they make a two-pronged case for the patchwork evidence model.
- New question reserved: whether the toolkit's patch schema should encode the enabling
  conditions (nomological-machine boundary) under which a patch's causal claims hold —
  see `question:0036-nomological-machine-patch-enabling-conditions`.
