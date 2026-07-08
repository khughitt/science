<!--
core/decisions.md — load-bearing decisions and reasoning. APPEND-ONLY per
decision; supersede rather than rewrite. Length cap: ~150 lines.
See templates/core-decisions.md for full guidance.
-->

# Decisions

## D-001: Scaffold the meta-project at `meta/` inside the science repo

- **Date:** 2026-04-23
- **Status:** active
- **Decision:** The meta-project lives at `meta/science.yaml` inside the
  existing science repo rather than in a sibling repo or at the repo root.

**Why:**
The repo root already has `data/`, `docs/`, `knowledge/`, `templates/`,
`scripts/`, `tests/` serving the toolkit itself — a root-level Science
scaffold would collide. `resolve_paths()` anchors everything off whatever
directory contains `science.yaml`, so a nested project works with zero tool
changes. Co-locating keeps tool-code references as plain `../` paths and
ties meta-project history to tool history.

**Alternatives considered and rejected:**
- Sibling repo — clean separation, but meta commits drift from tool commits
  and cross-repo `../` references become fragile.
- Root-level scaffold — maximum collision with existing tool dirs.
- Modify science to support out-of-root `science.yaml` — doable but
  only worth it if subdir layout hits a real limit. Start subdir; revisit
  if blocked.

**Implications:**
- Science commands must be run from `meta/` (or with `--project meta`).
- `.env` carries an absolute `SCIENCE_TOOL_PATH` so `validate.sh` works
  regardless of cwd.
- Commits that touch tool code stay scoped to the repo root on feature
  branches; meta-project commits stay scoped to `meta/`.

**Revisit if:**
- Tool operations against a nested `science.yaml` hit a path-resolution bug.
- science gets split into its own repo (meta goes with it or sibling).

---

## D-002: `software` profile with embedded research layer under `doc/`

- **Date:** 2026-04-23
- **Status:** active
- **Decision:** Profile is `software`; research artifacts (hypotheses,
  literature, interpretations, discussions) are kept as first-class entities
  rather than using a `research`-profile layout. (Originally these lived under
  `doc/` and `specs/hypotheses/`; the v2→v3 entity-layout migration relocated
  them to `entities/<kind>/` — see Implications.)

**Why:**
The bulk of work is tool development, which is software. But the tool's
design warrants hypothesis-testing and literature grounding. The
software-profile scaffolder supports a research layer by populating
`doc/background/`, `doc/questions/`, `doc/interpretations/`, and
`specs/hypotheses/` while keeping the implementation root as `src/` rather
than `code/`. This matches the real shape of the work. (These directories were
later unified under `entities/<kind>/` by the v3 migration; see Implications.)

**Alternatives considered and rejected:**
- `research` profile — forces `code/` naming and `data/`, `models/`,
  `results/`, `papers/` directories that don't apply to a project that
  doesn't run its own experiments.
- Two Science projects (one per layer) — double bookkeeping for one body
  of work.

**Implications:**
- `meta/src/` initially held an empty placeholder; as of 2026-04-24 it holds
  shipped packages (see D-004).
- Strategic plan lives in `README.md`.
- As of 2026-06-20 the project migrated to the unified entity layout
  (`layout_version: 3`): papers, questions, hypotheses, interpretations,
  syntheses, topics, and talks now live under `entities/<kind>/NNNN-slug.md`;
  `specs/` is retired. Design/handoff docs remain under `doc/plans/`.
- Aspects enabled: `software-development`, `causal-modeling`,
  `hypothesis-testing`.

**Revisit if:**
- We start running actual experiments or analyses from this project
  (would justify `data/`, `results/`, `models/`).
- The empty `src/` becomes a friction point.

---

## D-003: Operational beliefs are continuous in (0, 1), never 0 or 100%

- **Date:** 2026-04-24
- **Status:** active
- **Decision:** All tool-level beliefs about propositions and hypotheses are
  represented as continuous probabilities strictly bounded away from 0 and 1.
  Decisions that require a binary choice (act or not, publish or not) are
  computed *from* those beliefs at the decision point; they do not collapse
  the underlying representation.

**Why:**
Grounded in applied Bayesian practice
(see `topic:bayesian-methods-continuous-belief`) and consistent with the
replication-crisis literature's demonstration that findings drift, replicate
at below-nominal rates, and accumulate both false and missed signals
(see `topic:analytic-flexibility-and-replication`). A continuous
representation lets the tool update smoothly on new evidence, combine
heterogeneous lines of support, and avoid locking in early mistakes that
hard-gating would enshrine. The principle is load-bearing for H01
(`hypothesis:h01-stochastic-revisiting`), whose entire motivation depends on
down-weighted claims remaining recoverable rather than excluded.

**Alternatives considered and rejected:**
- Hard gating with thresholds — simpler to reason about, but enshrines early
  evidence and cannot recover from noisy warm-ups. Directly disputed by H01.
- Threshold with hysteresis — a middle path, but still discards belief state
  rather than representing it; loses the calibration property.

**Implications:**
- Calibration must be treated as a first-class, audited property, not assumed
  from the framework (see *Calibration* in the Bayesian topic).
- Priors must be specified defensibly — not arbitrary, but also not invisible
  defaults. How priors are set for proposition-level claims is an open
  design question worth tracking separately.
- UX that surfaces probabilistic outputs must communicate them honestly,
  resisting the shortcut of re-binarising for display.
- Any hypothesis or feature that would force collapse of a belief to 0 or 1
  (e.g. permanent retirement of a claim) must make the collapse explicit and
  reversible.

**Revisit if:**
- Calibration proves unachievable at useful precision on any ground-truthable
  subset, suggesting the framework is costing more than it delivers.
- Researcher users consistently misinterpret probabilistic outputs in ways
  the UX cannot correct — at which point a constrained-representation
  interface layer may be warranted even if the internal representation stays
  continuous.

---

## D-004: `meta/` ships Python packages from `src/`

- **Date:** 2026-04-24
- **Status:** active
- **Decision:** `meta/src/` hosts real, shipped Python packages that
  implement the project's research instruments. The first is
  `h01_simulator`, which tests
  `hypothesis:h01-stochastic-revisiting`; others may follow. `meta/`'s
  `pyproject.toml` is a full package manifest with runtime dependencies,
  dev dependencies, and CLI entry points.

**Why:**
The project's hypotheses require computational instruments, not prose alone.
Treating `src/` as a permanent placeholder (D-002 Implications as originally
written) became stale the moment H01's simulator was specified. Shipping
from `src/` is idiomatic for the software profile already chosen in D-002.

**Alternatives considered and rejected:**
- Put simulators at `meta/code/` — conflicts with the software-profile
  validator, which warns on top-level `code/`.
- Ship from a sibling repository — breaks the co-location argument from
  D-001 and forces cross-repo imports for project-internal code.

**Implications:**
- Notebooks live at `meta/notebooks/` (top level), not `meta/code/notebooks/`.
- `meta/AGENTS.md` reflects this as current convention.
- `uv sync` from `meta/` is the expected setup step.

**Revisit if:**
- Shipped packages become substantial enough to warrant their own
  repository (then split out, leaving `meta/` with research artifacts only).
- A researcher-facing distribution channel (PyPI) is wanted — at which
  point the single-manifest-per-package convention may need revisiting.

## D-005: Reuse t034 verbatim as the causal/edge-typing substrate; h00 net-new rides the t022 extension contract

- **Date:** 2026-05-31
- **Status:** active
- **Resolves:** RFC §12.1 (`doc/plans/historical/2026-05-31-epistemic-causal-probabilistic-graph-model-design.md`). Task `t064`.
- **Decision:** **Reuse** t034 — not extend, not supersede — as the sole
  causal/edge-typing substrate (`graph_object_type`, the 10-role
  `epistemic_role` taxonomy, the Petersen-stage payload pipeline,
  identification-by-reference promotion). The `h00` working model adds **no
  second** CPDAG/PAG/edge-role vocabulary. Its net-new pieces (R1 patch, R3
  latent-construct, R6 elicited-belief-with-uncertainty) are **additive** and
  conform to the **t022 evidence-payload core + extension contract** — the same
  contract t034/t035/t037/t038/t040 already conform to — so they land *alongside*
  t034 as typed extensions/entity kinds, never as edits *to* t034.

**Why:**
Prevents the RFC's #1 anti-pattern (reinventing t034) and keeps one causal
vocabulary. The t021/t022 architecture decision already established the
extension contract as the sanctioned way to add typed structure without widening
the mandatory core; R1/R3/R6 are exactly that. Concretely: elicited *structure*
already lives in t034 (`causal-prior-bundle`, `candidate-graph`,
`mechanistic-hypothesis-bundle`), so only elicited *beliefs/parameters with
uncertainty* (R6) are net-new — a payload, not a t034 change; the latent
construct (R3) is a t034 `latent_variable_hypothesis`-role node; the patch (R1)
is a grouping/view over t034 payloads, governed by D-006.

**Revisit if:**
- A genuine causal-representation need appears that t034's taxonomy cannot
  express even via a conforming extension (then extend t034, with its own task).

## D-006: Stay W3C-native (RDF/TriG named graphs + PROV-O + edge-as-node reification); a patch is a named graph

- **Date:** 2026-05-31
- **Status:** active
- **Resolves:** RFC §12.2. Task `t064`.
- **Decision:** Keep the substrate **W3C-native** — the live `knowledge/graph.trig`
  already *is* RDF in TriG with **named graphs**, already declares **PROV-O**, and
  already **reifies edges as first-class IRI nodes** (`bears-on-edge/<hash>` with
  `sci:bearsOnSource`/`Target`). So the three things §12.2 asked us to pick a
  substrate *for* already have homes:
  - **world↔claim reification** → the existing edge-as-node n-ary pattern (**not**
    RDF-star — no new serialization or rdflib/oxigraph tooling dependency);
  - **multi-edges** (associative edge + a causal claim on the same pair) →
    distinct reified-edge nodes over the same subject/object, exactly as t034's
    promotion-by-reference already prescribes (the associative edge is never
    rewritten);
  - **patch (R1) as an addressable unit** → a **named graph** whose IRI *is* the
    patch id, reusing the named-graph mechanism already in the file; ladder level
    + aggregate provenance + uncertainty are triples *about* that graph IRI
    (PROV-O for the agent/AI-vs-human + activity axis, `sci:` for the rest).
  **Reject** a separate labeled-property-graph substrate: it forks from the
  running RDF graph and forfeits SPARQL/SHACL/PROV-O + the federation machinery
  for no capability the edge-as-node + named-graph patterns don't already give.

**Why:**
Zero new substrate — the choice was made implicitly by the running graph. The
only implementation gate is confirming the emitter/loader round-trips
per-patch named-graph contexts (it already emits one named graph today): a
check, not a redesign.

**Carry-forward (not blocking):**
- Whether patch named-graphs **nest** or stay flat under the
  `patch ⊂ project ⊂ collection` federation (h00) is deferred to `t067`
  (federation); D-006 only fixes that a patch *is* a named graph.

## D-007: Model machinery lives in `science_tool.model`; meta holds research; projects hold applications

- **Date:** 2026-06-01
- **Status:** active
- **Resolves:** Where the `h00` working-model *implementation* belongs (raised by K.H. reviewing `meta/src/h00_patch_l1`). Tasks `t065`–`t067`.
- **Decision:** Separate **research** from **machinery** from **application**.
  - **meta** holds the *research* — the RFC, the `h00` hypothesis, the interpretations (the thinking and findings). No reusable implementation.
  - **`science_tool.model`** (new framework subpackage, peer of `graph/`) holds the *reusable machinery* — `patch` (epistemic-neighborhood patch as a TriG named graph + independence-aware fusion), `opinion` (subjective logic), `correction` (PMI/PPMI latent-construct correction), `federation` (the bias-corrected latent common axis). Built on the existing `graph.belief` primitives; pure-Python + rdflib, reusing the canonical `SCI_NS`; synthetic-fixture tests.
  - **Projects** (e.g. pan-disease) hold the *application* — the dataset→evidence mapping, the heavy data processing (matrix PPMI, SVD), fixtures, and the demo.
  - The prototype `meta/src/h00_patch_l1` is **retired**: machinery → `science_tool.model`; application + fixtures → pan-disease `code/scripts/h00_*`.

**Why:**
meta is where we *ask and research* questions about science; realized machinery that is reused across projects should be developed in normal modular software style inside the framework, not as a project-shaped prototype under `meta/src/`. The belief primitives this builds on already live in `science_tool.graph`, so this just extends the same pattern one layer up. The clean dependency boundary (framework = semantics + serialization, no numpy/sklearn; project = data processing) falls out of the split.

**Carry-forward (not blocking):**
- `science_tool.model` graduating does **not** bless the provisional parts as final — the opinion view (default-next, RFC §12.3) and the correction thresholds (pending pan-disease `t070`) carry their status in module docstrings.

## D-008: Adaptive topology is manual-first; `bio/meta` is substrate, not health lens

- **Date:** 2026-07-01
- **Status:** active
- **Resolves:** Durable cleanup of the adaptive-topology planning thread. Tasks
  `t054`, `t056`, and `t058`.
- **Decision:** Adaptive project topology is a manual-first decision-support
  workflow owned by `~/d/science/meta`, not an automatic project-creation or
  archival mechanism. V1 recommendations rank candidate topology changes from
  artifact-derived signals, then require human review for uncertainty,
  novelty, actionability, coherence, false-positive risk, and provenance cost.
  The `~/d/bio/meta` candidate is defined as a biological substrate-model
  project: multiscale systems, state spaces, time and space, reachability, path
  dependence, control regimes, perturbation response, observability, sampling,
  and resolution. `~/d/health/meta` remains the applied health lens:
  homeostasis, disease, intervention, health-state axes, family coordination,
  and decisions about health child projects.

**Why:**
The same cross-project material can look like biological substrate, health
world-model, or commons resource depending on context. Automatic topology
changes would amplify that ambiguity. The durable operating model in
`core/adaptive-project-topology.md` keeps the process inspectable: first record
known topology harms, then run dry-run recommendations, then compare each
candidate against the harms and provenance costs. The `bio/meta` brief in
`core/bio-meta-scaffold-brief.md` provides a crisp candidate boundary without
scaffolding the project prematurely.

**Implications:**
- Do not scaffold `~/d/bio/meta` until `t057` shows that a separate substrate
  project reduces a concrete topology harm.
- Do not move, delete, demote, merge, or archive projects from the topology
  workflow without a reviewed migration note.
- Demotion and merge recommendations must preserve stable IDs, graph nodes,
  decisions, task history, paper-summary provenance, and parent/peer links.

**Revisit if:**
- The `t057` pilot finds that the `bio/meta` boundary duplicates
  `~/d/health/meta` or fails to reduce known routing/duplication costs.
- Dry-run recommendations are mostly obvious from ordinary task review, which
  would weaken the case for a dedicated topology workflow.

---

## D-009: Lenses are first-class content (`lens_views`), separate from provenance

- **Date:** 2026-07-04
- **Status:** active
- **Resolves:** Schema design for `lens_views` as a multi-valued content field, distinct from provenance. Multi-lens feature (lens-views schema, backfill, materialization, graph reification).
- **Decision:** The analytical lens that frames an epistemic entity is modelled
  as a multi-valued content field `lens_views` (one `LensView` per lens: `lens`,
  `rationale`, optional `origin_ref`), not as a string smuggled into an origin
  `ref`. The lens vocabulary is packaged in `science_model.lenses` (stable slugs;
  slug changes are explicit migrations). `OriginRecord` is unchanged and remains
  provenance-only ("MUST NOT affect evidential weight"); `lens_views[].origin_ref`
  links a view to one of the entity's own non-null, unique origin refs. Convergence
  is derived (≥2 lens-views backed by independent origins), materialized as reified
  `sci:hasLensView`/`sci:viewedThroughLens`/`sci:fromOrigin` nodes.

**Why:**
The lens vocabulary and entity framings are first-class scientific metadata,
distinct from *where knowledge came from* (provenance). Preserving complementary
lens framings instead of forcing keep-one-discard-rest is essential to
multi-hypothesis reasoning and exploration. See `~/d/science/meta/doc/plans/2026-07-04-multi-lens-first-class-representation-design.md`
and upstream feedback `fb-2026-07-04-005`.

**Implications:**
- `lens_views` entries are never null or recomputed; they record the *framing*
  under which an entity was produced or analyzed. Backfill and migrations must
  preserve all views.
- `OriginRecord` and its role in evidential weight remain unaffected.
  `lens_views[].origin_ref` is a link, not a modification to origin semantics.
- The lens vocabulary lives in `science_model.lenses` (not in entity frontmatter).
  Slug changes and additions are explicit migrations under Science versioning.
- Convergence (≥2 views from independent origins) is derived and reified in the
  knowledge graph as `sci:hasLensView`/`sci:viewedThroughLens`/`sci:fromOrigin`,
  enabling SPARQL and federation queries.

**Revisit if:**
- Lens vocabulary stability proves fragile (e.g., frequent ad-hoc slug changes
  required), suggesting a mutable registry would be better than explicit
  migrations.
- Convergence reification in the graph adds more noise than signal due to sparse
  view coverage or overlapping lens definitions.

## D-010: `mixin-theme-2.0` owns the canonical `theme_kind` vocabulary

- **Date:** 2026-07-08
- **Status:** active
- **Resolves:** Task `t059`.
- **Decision:** The canonical `theme_kind` enum for Science themes is the
  `theme_kind` property in `science_model/schemas/mixin-theme-2.0.json`, and it
  matches the public `ThemeEntity` model:
  `methodological`, `biological`, `translational`, `evidence-quality`,
  `organizational`, `conceptual`, `empirical`, and `domain`.

**Why:**
Toolkit templates, schema validation, and downstream projects had drifted:
templates documented the older four-value enum while the Python entity model and
active cancer projects already used biological theme kinds. Making the 2.0
mixin the source of truth preserves one validation contract for default themes
and avoids profile-specific schemas silently accepting values that commons
promotion rejects.

**Implications:**
- Project templates point authors at the 2.0 mixin instead of describing a
  separate active-profile override path.
- Commons theme promotion accepts biological and related core theme kinds.
- Older `mixin-theme-1.0` remains historical; no compatibility layer is added.

**Revisit if:**
- A project needs a domain-specific theme taxonomy that cannot fit the core
  enum; add a versioned profile/mixin rather than silently diverging.

## D-011: `entity sections` reports the effective entity-schema contract

- **Date:** 2026-07-08
- **Status:** active
- **Resolves:** Task `t060`.
- **Decision:** `science entity sections <kind>` describes the effective
  entity-schema frontmatter contract for the kind's default profile, then the
  packaged template body-section contract. Frontmatter constraints are computed
  from the composed JSON Schema profile, so `allOf` means intersection rather
  than "last property wins": const narrows enum, enum sets intersect, root
  required fields are unioned, and simultaneous pattern/format constraints are
  preserved.

**Why:**
The command is the discoverability surface users and agents reach for when they
need to author a valid entity. Reporting only template body sections forced
schema-file inspection and trial-and-error validation, especially for theme
fields such as `theme_kind`. The schema layer already owns validation, so the
CLI should expose that same contract instead of maintaining a separate
template-only vocabulary.

**Implications:**
- JSON output keeps one `rows` array and adds `area`, `type`, and structured
  `constraints` so consumers can filter `frontmatter` versus `body`.
- Base-profile fields such as `schema_profile` and `version` appear because
  they are part of the entity-schema contract; source-template ergonomics remain
  a separate authoring concern.
- Future profile extensions must expose their composed constraints through the
  schema introspector rather than duplicating CLI-specific merge logic.

**Revisit if:**
- Source-authored Markdown owners intentionally diverge from shared entity
  schema requirements; then add an explicit source-owner contract rather than
  weakening this schema-discovery surface.
