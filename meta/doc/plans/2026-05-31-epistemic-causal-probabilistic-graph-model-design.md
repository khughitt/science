# RFC / Design Exploration — Epistemic + Causal/Probabilistic Graph Model

**Status:** DRAFT / exploration (not a committed spec). v2 (2026-05-31) — patched after K. Hughitt's review to anchor against existing **t034 causal-graph** work, the **implemented belief-aggregation** pipeline, and the existing **provenance axes** + **causal exporters**. Outstanding schema choices are now explicit **forks** (§12), not implied decisions.
**Author:** drafted by Claude (opus-4-8) at K.H.'s request; AI-drafted, human-reviewed (review 1 complete).
**Trigger:** pan-disease `question:q15` (data-derived gene sets need per-gene confidence) and the request to make **epistemic weight + uncertainty first-class and measurable across the graph**, with an explicit **causal/probabilistic graphical model** and a **causal-vs-associative edge distinction**, approached **progressively**. Companion: feedback `fb-2026-05-31-009`.

---

## 0. TL;DR / recommendation

1. **This is mostly a reconciliation, not a greenfield.** Three mature bodies of work already cover ~70% of the ask (§1). The RFC's real job is to (a) name the **two-layer** structure explicitly, (b) **reuse t034** for all causal/edge semantics, (c) decide how a richer uncertainty representation **composes with the implemented belief pipeline**, and (d) **split** the provenance ask onto the existing axes. Net-new is small. One framing *is* net-new and load-bearing: a model can arrive by **discovery** *or* **elicitation** (a user asserting a belief), and both are first-class, distinguished only by provenance + uncertainty — the Bayesian prior↔posterior duality (§3.5).
2. **Foundational move:** make the *object/world* vs *epistemic/meta* layering explicit (§2). It is already half-built; naming it dissolves most confusion and answers "science model alongside the project KG as the common world."
3. **Do NOT invent a second CPDAG/PAG vocabulary.** t034 already owns `graph_object_type`, `epistemic_role`, the discovery→identification→estimate pipeline, and identification-by-reference promotion. Reuse verbatim (§3).
4. **Do NOT make subjective-logic opinions canonical by fiat.** `belief-logodds-v3` (`aggregate_belief`/`belief_scalar`) is implemented and opt-in-shipped. Opinions are a **fork** (§4, §12): experimental derived view vs proposed v4 successor vs not-adopted.
5. **Highest-leverage net-new framings** (worth exploring first, §8): a **latent-construct / measurement-model** layer (the right frame for publication gravity in pan-disease) and an **argumentation-framework** backbone for the belief derivation that is currently formula-based.
6. **Scope as an opt-in aspect**, delivered up the progressive ladder (§6); L3–L4 are t034 payloads, already specced.

---

## 1. Prior art this RFC must anchor against (and the actual residual gap)

| Existing work | Where | What it already provides |
|---|---|---|
| **t034 causal-graph extension** (v1.4) + sisters **t035** graph-valued/multiview, **t037** agent/tool ops, **t038** graph-evolution/KG-views, **t040** robustness; **t022** evidence-payload contract, **t025** reason-code registry, **t026** causal guardrails | `meta/doc/plans/2026-05-06-t034-causal-graph-extension-design.md` | `graph_object_type` enum (DAG/CPDAG/PAG/ADMG/equivalence-class-feature/candidate-graph/graph-posterior); 10-role `epistemic_role` edge taxonomy; Petersen-stage payload pipeline (`causal-prior-bundle`→`causal-discovery-run`+`causal-graph`→`graph-diagnostic`→`causal-identification`→`causal-effect-estimate`(+`mediation`/`mr`)); **identification-by-reference promotion** (edge roles never rewritten in place); `target_estimand`/`identification_method` (do-calculus + counterfactual estimands); per-role validation + reason codes |
| **Belief aggregation (implemented, shipped opt-in)** | `science/src/science_tool/graph/belief.py`, `belief_scalar.py`, `belief_weights.py` | `aggregate_belief(units) → BeliefResult` (magnitude + `contested`); `belief_scalar(result) → BeliefScalar` (log-odds, `DELTA_ENVELOPE`, `PROXY_STEP_PENALTY`, `CURATION_STEP_PENALTY`, `CONFIG_VERSION="belief-logodds-v3"`, `belief_scalar_enabled()`); proxy-gating, decisive-refutation, independence-aware reduction |
| **Proposition & evidence model** | `docs/proposition-and-evidence-model.md` | uncertain S-P-O propositions; derived `belief_state`/`confidence`/`uncertainty`/`contestation`/`fragility`; evidence edges + taxonomy; `claim_layer`/`identification_strength`/`measurement_model`; `bears_on`/freshness; **evidence-integrity non-negotiables** |
| **Provenance axes (three, already separate)** | `science_model/provenance.py`; `entities.py` (`source_class`, `derived_kind`, `review_state`/`EpistemicReviewState`) | `ProvenanceType{mathematical,empirical,editorial,derived}`; dataset `source_class{observational,derived,reference}`+`derived_kind`; review/ratification via `review_state`; `EvidenceIndependence{independent,shared_source,circular}` |
| **Causal PGM exporters (exist as scaffolds)** | `science/src/science_tool/causal/export_pgmpy.py`, `export_chirho.py` | export causal **inquiry graphs** → pgmpy `BayesianNetwork` scripts / ChiRho-Pyro scaffolds (topological sort over `causes` edges) |

**Residual gap (what is genuinely net-new):**

- **R1 — explicit two-layer naming + reification** linking domain (world) edges ⇄ propositions/payloads (§2). Implicit today.
- **R2 — a richer on-edge uncertainty representation** *if* the team wants more than the log-odds scalar, and a decision on how it composes with `belief-logodds-v3` (§4). **Fork, not a given.**
- **R3 — a latent-construct / measurement-model layer** that *corrects* (not just flags) proxy bias like publication gravity (§8). Extends existing `measurement_model` metadata.
- **R4 — wiring the existing causal exporters into the real pipeline**: calibrated CPDs, identification payloads as inputs, counterfactual semantics, validation gates (§7).
- **R5 — graph-wide queryability** of the *already-separate* provenance axes ("show all ai-drafted-unratified facts") — a CLI/query surface, not new schema (§5).
- **R6 — elicited-belief representation** — let a user *assert* a model (belief) with honest uncertainty: per-edge held-credence + optional parameter priors, distinct from t034's discovery-fed priors (§3.5). The prior half of the prior↔posterior duality.

Everything else the original draft proposed already exists in one of the rows above.

---

## 2. Foundational reframe: two layers over one world (R1)

Two graphs share one identifier space:

- **Object / world layer (ABox).** Domain entities (genes, diseases, tissues) and relations among them. Uncertainty = *"is this real-world relationship true?"*
- **Epistemic / meta layer.** Claims about those relations + evidence + derived belief. Uncertainty = *"how warranted is our credence, given the record?"*

These are routinely conflated and must not be. The framework already separates them: **S-P-O propositions and t034 payloads are the lift** from world-relation to epistemic object. Your "multigraph of causal/associative edges with uncertainty vectors" = *a set of propositions/causal-graph edges over the same (subject, object) differing in `epistemic_role`/`claim_layer`*, each carrying its own evidence and belief. t034 already does exactly this: parallel edges with distinct `epistemic_role`, promoted by reference rather than overwrite.

**Net-new = R1 only:** an explicit, queryable reification linking a world-layer edge to the proposition(s)/payload(s) that assert it, so the world graph renders at any belief threshold. Substrate is a **fork** (§12.2): RDF-star/named-graphs/PROV-O (W3C-native, current TriG stack) vs labeled-property-graph (multigraph-native). This *is* the "science model alongside the project KG as the common world."

---

## 3. Domain edges: associative vs causal — REUSE t034 (do not reinvent)

t034 already owns this. The RFC's only job is a **strict crosswalk** from the coarse "associative vs causal" framing to t034's finer machinery, and to fix the loose mapping in v1 of this draft.

**Where the Pearl rung actually lives.** It is *not* a single `claim_layer` value. t034 distributes it:

| Pearl rung | t034 representation (authoritative) | NOT this (v1 error) |
|---|---|---|
| Associational `P(Y\|X)` | no `causal-identification` payload; `causal-graph` edge role `data_discovered_adjacency`/`assumed_background_edge`; proposition `claim_layer: empirical_regularity` | — |
| Interventional `P(Y\|do(X))` | a `causal-identification` payload with `target_estimand ∈ {ATE, CATE, interventional-distribution}`, `identification_status: identified`, promoting the edge by reference | ✗ `identification_strength: longitudinal` (longitudinal is *observational-over-time*, not `do()`); ✗ `identification_strength: structural` (structural is often *definitional/model-structure*, not interventional) |
| Counterfactual | `target_estimand ∈ {NDE, NIE, counterfactual-quantity}` (+ `mediation-analysis` for NDE/NIE) | ✗ a new `claim_layer: counterfactual` invented silently |

**Corrections to v1 of this draft:**
- `identification_strength` (`observational`/`longitudinal`/`interventional`/`structural`) is a **proposition-level "what kind of identification situation is this?" hint** — it is **not** a Pearl-rung encoding and must not be crosswalked 1:1 to `do()`. The rung is carried by the **`causal-identification` payload's `identification_method` + `target_estimand` + `identification_status`**, per t034.
- A `claim_layer: counterfactual` value would be an **enum/schema migration** (`reasoning.py` + validators + migration helper), not a free addition — and is likely **unnecessary**, since counterfactual estimands already live in `target_estimand`. Flag as a fork (§12.6), default **no**.
- CPDAG/PAG/ADMG honesty (can't orient all edges observationally; latent confounding ⇒ bidirected) is **already** t034's `graph_object_type` + the `equivalence_class_feature`/`latent_variable_hypothesis` roles. Reuse; do not restate as new.
- Acyclicity-vs-feedback and multigraph-over-merge are **satisfied** by t034 (candidate-graph for non-DAG hypotheses; promotion-by-reference preserves the associative edge alongside the causal claim).

**Decision (§12.1):** reuse t034 verbatim as the causal/edge-typing substrate; this RFC adds only the world↔payload reification (R1), the optional uncertainty representation (R2), and the elicited-belief representation (R6, §3.5).

---

## 3.5 Two routes to a model: discovery vs elicitation (both first-class)

A crucial framing (K.H., 2026-05-31): causal **discovery** (data → CPDAG/PAG, t034's main thrust) is *one* goal, not the only one. The system must equally let a user (or AI) **assert a model — a belief about structure and/or mechanism — and represent it with honest, appropriate uncertainty + epistemic status.** Neither route is privileged as "the real model"; they differ only in *provenance* and *where on the prior→posterior arc* they sit.

This is the **Bayesian prior↔posterior duality made first-class**:

- **Elicitation** specifies a *prior* model: believed structure (+ optionally believed parameters/mechanisms) + the author's uncertainty over it. Provenance = editorial / expert-judgment / ai-drafted (§5). Guardrail (t034 H04): an assertion is a prior/hypothesis, **never** evidence for itself — `causal-prior-bundle`/`mechanistic-hypothesis-bundle` forbid `strengthen-belief`. Honesty is carried by provenance + uncertainty, *not* by refusing the assertion.
- **Discovery** produces a *posterior*: a graph-posterior / fitted model from data. Provenance = empirical/derived.
- **Evidence moves prior→posterior** on the *same* `bears_on`/belief machinery.

**What t034 already covers (elicited *structure*):** `causal-prior-bundle` (prior_role background-knowledge/llm-prior/structural-constraint), `candidate-graph` with `assumed_background_edge`/`llm_prior_edge` roles, `mechanistic-hypothesis-bundle`. "Express a believed graph" is supported.

**Genuine net-new (R6) — elicited *beliefs/parameters* with uncertainty:** t034 represents asserted *structure*, but an elicited model as the user means it — "my believed model, with my uncertainty over its edges and, where I have them, its mechanisms/parameters" — needs (a) per-edge *belief* with explicit uncertainty mass (a held credence, not a measured frequency), and (b) optional *parameter priors* (believed CPDs as distributions, updatable). This is the **prior half of Pyro/ChiRho** (priors over SCM parameters), complementing the discovery-side graph-posterior, and it is where §4's representation earns its keep. "As best we can" = the progressive ladder (§6): an elicited model may be L1 (a few believed associations with uncertainty) or aspire to L4 (a full believed SCM); represent it at whatever level the author can express, with honest uncertainty at that level.

**This unifies the project's two tracks:** the q14 **curated panels are already an elicited model** (editorial gene–disease beliefs, ai-drafted/human-ratified, honest uncertainty) — the elicitation route. q15 (data-derived gene sets) is the discovery route. Same machinery; the discovered posterior can then *update* the elicited prior (does data recover the panel?).

---

## 4. Uncertainty representation (R2) — a FORK, composed against belief-logodds-v3

The implemented pipeline is `aggregate_belief → BeliefResult` then opt-in `belief_scalar → BeliefScalar` (log-odds over ordinal evidence steps, with proxy/curation penalties, `CONFIG_VERSION="belief-logodds-v3"`). Any richer representation must say **how it composes with or replaces this** — it cannot be declared "the on-edge representation."

Options for a richer representation (if adopted at all):

| Option | Carries | Relation to belief-logodds-v3 |
|---|---|---|
| **Keep scalars only** (status quo) | log-odds magnitude + `contested` | no change; lowest cost |
| **Subjective-logic opinion** (belief, disbelief, **uncertainty mass**, base rate) | explicit ignorance mass; ≅ Beta | could be a **derived view** *computed from the same `EvidenceUnit`s* (opinion as an alternate read-out of the existing reduction), OR a proposed **v4** aggregation algebra replacing the log-odds map |
| Beta/Dirichlet posterior | full posterior on a probability | derived from counts; display layer over belief result |
| Credal set / imprecise prob.; Dempster–Shafer | set-of-distributions / mass-on-unknown + conflict | heavier; reserve for deep-ignorance / high-conflict regimes |

**Recommended framing (not a decision):** treat a subjective-logic opinion as an **experimental derived view computed from the existing `EvidenceUnit` reduction**, behind the same opt-in flag pattern as `belief_scalar_enabled()`, so it composes with `belief-logodds-v3` rather than forking the core. Promote to a v4 successor *only* if a prototype shows the log-odds scalar is inadequate. **This is fork §12.3 — explicitly the team's call.** Note the representation matters *most* for **elicited** models (§3.5): an opinion's explicit ignorance mass / a Beta prior is the natural way to record "I believe X→Y but I'm quite unsure," and converts cleanly into a Pyro/ChiRho parameter prior for the L4 case.

**Fusion under non-independence is already handled in spirit:** `belief.py`'s independence-aware reduction + `EvidenceIndependence{independent,shared_source,circular}` + `independence_group`. Any opinion-fusion must route through the *same* independence logic (no parallel, weaker independence model). The publication-gravity trap = circular/shared-source evidence; the existing reduction already refuses to count it twice.

---

## 5. Provenance (R5) — SPLIT onto the three existing axes, do not add a 5th

v1 of this draft proposed a single `provenance_tier ∈ {empirical, derived, literature, ai_drafted, human_ratified, expert_curated, mathematical}`. That **conflates four orthogonal axes** that already exist separately. Correct decomposition:

| Need | Existing axis (reuse) | Not a new field |
|---|---|---|
| derivation/formal basis (mathematical, empirical, editorial, derived) | `ProvenanceType` (`provenance.py`) | — |
| dataset epistemic class | `source_class{observational,derived,reference}` + `derived_kind` (`entities.py`) | — |
| evidence kind (literature/empirical/simulation/benchmark/expert) | evidence-edge `evidence_type` taxonomy | — |
| **who/what produced it (human vs AI) + review/ratification state** | **PROV agent/activity** (`prov:wasGeneratedBy`, `prov:Agent`) **+ `review_state`/`EpistemicReviewState`** | — |

The q14-panels need ("mark these as AI-drafted, human-ratified; query graph-wide") = **PROV agent = AI + `review_state` ratification record**, *not* a new tier enum. Net-new is **R5 only**: a **query/CLI surface** that joins these existing axes — e.g. `science graph audit --produced-by ai --unreviewed`. No schema addition; an audit view over fields that already exist.

---

## 6. The progressive ladder (maps onto t034 stages, not a new pipeline)

Levels coexist; each subsumes the prior. The upper levels are **t034 payload stages**, already specced — the ladder is a navigational lens, not a new mechanism.

| Level | Representation | t034 / existing locus | Library |
|---|---|---|---|
| **L0** | typed edge + scalar | plain KG edge | KG |
| **L1** | edge + belief result + provenance axes (§5) + independence | proposition + `aggregate_belief`; `EvidenceIndependence` | belief.py |
| **L2** | + associative-vs-causal role + measurement model | t034 `causal-graph` edge `epistemic_role`; `measurement_model` | t034 validator |
| **L3** | partial causal structure (CPDAG/PAG/ADMG) + identification | t034 `causal-discovery-run`+`causal-graph`→`causal-identification` | causal-learn/Tetrad (discovery); pgmpy (discrete) |
| **L4** | full PGM/SCM; `do()` + counterfactual | t034 `causal-effect-estimate`(+`mediation`/`mr`); **existing** `export_pgmpy`/`export_chirho` | pgmpy / Pyro·NumPyro / **ChiRho** |

Honest default L0–L2 for almost everything; L3–L4 local and earned. t034's evidence-integrity + reason-code machinery already forbids the relabeling that would fake a level-up.

---

## 7. Library/tool map (existing scaffolds + what remains) — corrects v1 "future" framing

- **Bayesian networks ≡ Bayesian belief networks ≡ Bayes nets** — one option, not two.
- **pgmpy** — **already wired**: `export_pgmpy.py` emits `BayesianNetwork` scripts from causal inquiry graphs. **Remaining:** calibrated CPDs (exporter emits structure, not fitted parameters), consuming `causal-identification` payloads, validation gates on the emitted model.
- **ChiRho / Pyro** — **already scaffolded**: `export_chirho.py` emits a ChiRho/Pyro scaffold (topo-sorted over `causes` edges). **Remaining:** actual interventional/counterfactual *semantics* (the scaffold is structural), tie-in to `target_estimand ∈ counterfactual`, NumPyro fitting.
- **DoWhy / EconML** — identification + estimation + **refutation**; maps to t034 `causal-identification`/`causal-effect-estimate` + the diagnostic/refutation reason codes. Not yet integrated.
- **causal-learn / Tetrad** — discovery → CPDAG/PAG, i.e. t034 `causal-discovery-run` output (`discovery_algorithm: PC/GES/FCI`, already named in t034 examples).
- **PyTorch-Geometric** — **different paradigm**: GNN feature-learning / link-prediction, often uncalibrated, *not* causal semantics. Useful at L1–L2 (candidate-edge discovery, scalable propagation) but walled off from the L3–L4 causal layer. **PGM/SCM libraries supply semantics; GNN libraries supply features.**

---

## 8. Net-new framings worth exploring FIRST (§ your direct question)

After anchoring, two framings are genuinely net-new and high-leverage — explore these before any opinion-algebra or library work:

1. **Latent-construct / measurement-model layer (R3).** Separate the *true* construct (real disease biology) from *measured proxies* (literature co-occurrence, DEG overlap) as noisy/biased measurements of a latent node. Extends existing `measurement_model`. **The right frame for pan-disease specifically:** publication gravity is a measurement bias on the literature proxy, and a latent-variable model is how you *correct* it, not merely flag it (BC-2 only flagged). Highest leverage for the actual science. Composes with t034 (the latent node is a `latent_variable_hypothesis`-role construct).
2. **Argumentation-framework backbone (bipolar/ASPIC+) for the belief derivation.** `aggregate_belief` currently maps evidence→magnitude via a fixed reduction. A bipolar argumentation semantics gives a *principled* support+attack→justified/contested/defeated calculus, composes with subjective-logic trust discounting, and would *replace the ad hoc parts of `belief.py`'s reduction with a named semantics*. Evaluate against a real slice before hand-tuning more reduction rules.

Lower-priority (already partially covered): credal/Dempster–Shafer (deep ignorance/conflict; reserve), CPDAG/PAG equivalence classes (t034 has them), subjective logic (fork §4).

---

## 9. "Diffusion / noise to push back on our biases"

Keep, but note it cuts both ways: **naive belief diffusion amplifies shared bias** (echo chamber / citation laundering). Bias-*reducing* formalizations, all of which compose with existing machinery:

1. **Independence-discounted propagation** — propagate belief but down-weight by source overlap, routed through the *existing* `EvidenceIndependence`/`independence_group` reduction. Directly attacks publication gravity.
2. **Skepticism prior / shrinkage toward ignorance** — the quantitative form of the framework's skeptical-default stance; regularize toward high uncertainty proportional to provenance weakness.
3. **Adversarial perturbation as a first-class op** — perturb weights / drop sources / flip plausible edges and recompute; survivors are robust. This is t040 (robustness/reproducibility) + the sensitivity-arbitration ethos + DoWhy "refute", made graph-native.

Anchor the intuition as (2)+(3), not unguarded diffusion.

---

## 10. Risks / anti-patterns

- **Reinventing t034** — a second CPDAG/PAG/edge-role vocabulary. (This review's finding #1.) Mitigation: §3 reuse.
- **Silently replacing belief-logodds-v3** — opinions declared canonical. Mitigation: §4 fork + compose-as-derived-view.
- **Provenance-axis collapse** — one `provenance_tier` over four orthogonal axes. Mitigation: §5 split.
- **Loose Pearl crosswalk** — `longitudinal`/`structural` ≠ interventional; silent new `claim_layer`. Mitigation: §3 strict crosswalk.
- **"Future" libraries that already exist** — pgmpy/ChiRho exporters. Mitigation: §7 existing+remaining.
- **False precision / premature formalization**; **layer conflation** (§2); **diffusion amplifying bias** (§9); **GNN-as-causal-model** (§7); **build cost** (opt-in aspect); **gaming new scalars** (evidence-integrity rules extend verbatim).

---

## 11. Recommended first steps (explore-first order)

1. **Resolve §12.1 (reuse/supersede t034)** and §12.2 (substrate). Everything hangs off these.
2. **Decide §2 reification** (world edge ⇄ proposition/payload) on the chosen substrate.
3. **Prototype on a tiny real slice:** encode q14 panels + gene-axis edges as L1 (belief result + provenance axes), reuse the existing independence reduction, and show publication gravity as an independence-discounted, latent-proxy case.
4. **Evaluate §8.1 (latent/measurement model) and §8.2 (argumentation)** against that slice — do they earn their complexity here?
5. **Only then** decide §12.3 (opinions: derived-view vs v4 vs no) and wire the existing pgmpy/ChiRho exporters' remaining pieces (§7).
6. Keep L3–L4 deferred until a real edge warrants a t034 identification payload.

---

## 12. Open decisions (forks for K.H.)

1. **t034 disposition:** reuse verbatim (recommended) vs extend vs supersede the causal/edge-typing substrate.
2. **Storage substrate** for world↔payload reification + multi-edges: RDF-star/named-graphs/PROV-O (stay W3C-native) vs labeled-property-graph vs hybrid.
3. **Uncertainty representation:** keep belief-logodds-v3 scalars only vs add subjective-logic **derived view** (recommended if anything) vs propose opinions as **v4** successor vs credal/DS for special regimes.
4. **Belief backbone:** keep formula-based `aggregate_belief` vs adopt an **argumentation-framework** semantics.
5. **Latent-construct modeling now or later** — bias *correction* (latent proxy model) in scope, or only bias *flagging*? (High leverage for pan-disease.)
5b. **Elicited-belief representation (R6, §3.5):** how far to support user-asserted models — per-edge held-credence only, vs also parameter priors (believed CPDs as distributions) feeding the Pyro/ChiRho prior. Determines whether elicitation is L1-only or can reach L4.
6. **New `claim_layer: counterfactual`?** Default **no** (counterfactual estimands already live in t034 `target_estimand`); adopt only if a proposition-level need is shown — and treat as an enum/schema migration if so.
7. **Delivery shape:** opt-in aspect (recommended) vs core-model change.
8. **Doc home / commit:** ✅ **DECIDED (K.H., 2026-05-31): `meta/doc/plans/`, alongside t034** — the RFC is entangled with the t034 causal-graph work and belongs in the same design corpus.

*No code in this RFC. The pan-disease q15/t071 work proceeds independently on curated panels meanwhile; this model is what eventually retires those editorial labels.*
