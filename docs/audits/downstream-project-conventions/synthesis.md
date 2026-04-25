# Downstream Project Conventions Audit — Synthesis

**Audit date:** 2026-04-25
**Scope:** Cross-project synthesis across `natural-systems`, `mm30`, `protein-landscape`, `cbioportal`.
**Inputs:** four inventory artifacts (`inventory/<project>.{json,md}`) + four manual project audits (`projects/<project>.md`).
**Method:** convention-threshold rule applied per `docs/plans/2026-04-25-downstream-project-conventions-audit.md` Phase 3 — 3-of-4 with same shape eligible for P1; 2-of-4 eligible for P2 (upgraded with one-line justification only); 1-of-4 → P3 unless it is direct evidence of a known upstream gap.

Findings are tagged `[mav-input]` where managed-artifact-versioning would absorb them, `[hyp-phase]` where they touch the in-flight hypothesis-phase plan, and `[v1-tooling]` where they argue for a Phase-1 inventory/tool change.

---

## 1. Executive Summary

Three patterns dominate the audit:

1. **Every project is multi-axis.** All four use `aspects:` as a workaround because a single `profile:` cannot express the real shape. The two-aspect pair `[computational-analysis, software-development]` appears in three of four projects, mm30 carries four aspects, and natural-systems carries three. Single-string `profile:` is lossy for every mature downstream project we looked at. **(P1)**
2. **Project-local entity kinds are universal.** All four projects extend Science's entity model — explicitly (cbioportal and mm30 register `meta`, `pre-registration`, `synthesis`, `guide`, `modality-guide`, `curation-sweep` etc. via `knowledge/sources/local/manifest.yaml` with `strictness: typed-extension`), or implicitly (protein-landscape's inline `proposition:`/`finding:F[0-9]+`, natural-systems' refactor-pair directories and `concept:`/`vis:` ids). **Pre-registration** is the strongest single recurring kind: 4 of 4 projects need it; none uses Science's canonical type. **(P1)**
3. **Tasks lifecycle is leaking.** Three of four projects accumulate done entries in `tasks/active.md` (natural-systems 49% / 114 of 232, mm30 ~30% / 44 of 152 done+retired+deferred, protein-landscape 44% / 44 of 101). cbioportal is clean — proving the discipline is enforceable, but only with tooling. **(P1, blocks operational hygiene)**

Beyond these, the audit confirms the managed-artifact-versioning plan is on the right track (cbioportal's `validate.sh` is byte-identical to `meta/validate.sh`, the other three carry 80-84 lines of mostly-generic drift), and surfaces a clean shippable provenance pattern (sha256-sealed output sidecars + Frictionless datapackages with `<project>:` extension blocks).

The audit does not surface any P0 findings — no project is blocked from safe downstream use. The P1 list below is the recommended near-term focus; P2 items are ready to move once the P1 work lands.

### Top P1 candidate table

| # | Candidate | Sections | Evidence summary |
| --- | --- | --- | --- |
| 1 | Multi-axis project profile (or formalized aspect-bundle archetype) | §2, §6 | 4/4 projects use `aspects:` as a profile-axis workaround |
| 2 | First-class `pre-registration` type (not `type: plan` with `id: pre-registration:*`) | §6, §8 | 4/4 use it; 3/4 overload `type: plan`; placement varies (`doc/pre-registrations/`, `doc/meta/pre-registration-*`, hypothesis body section) |
| 3 | Sanctioned project-local entity-kind extension (formalize `knowledge/sources/local/manifest.yaml` `typed-extension` pattern) | §6, §10 | 2/4 register explicitly; 4/4 need it (other 2 do it via inline conventions) |
| 4 | `synthesis` rollup convention with `report_kind` discriminator + structured provenance frontmatter | §6, §8 | 2/4 produce structured rollups (mm30 as `type: report`, protein-landscape as `type: synthesis`); canonize the cleaner `type: synthesis` shape; tied to `science:big-picture` |
| 5 | Per-type / multi-axis status enums (separate work-status from reading-state, qualifier blocks, phase) | §6 | 4/4 hit status sprawl (9-25 distinct values); cbioportal's reading-state (`read|abstract-read|summarized|unread`) is the cleanest example of axis collision |
| 6 | Auto-archive of done tasks from `tasks/active.md` to `tasks/done/YYYY-MM.md` | §8, §10 | 3/4 lag (49% / 30% / 44%); cbioportal proves enforceability |
| 7 | `validate.sh` MAV adoption with explicit knobs for genuine local needs | §9 | 1/4 byte-identical (cbioportal); 3/4 carry mostly-generic drift; concrete `mav-input` set is forming |
| 8 | Output-anchored sha256-sealed descriptor sidecars (Frictionless-flavor) + datapackage `<project>:` extension block | §7 | 4/4 either ship the pattern (3/4) or have an active task to adopt it (cbioportal `t128`) |
| 9 | Code/notebook → task back-link convention (sidecar or comment-block, case-by-case) | §6, §8 | 4/4 have weak code-side linkage; reverse direction (entity → code) is fine |
| 10 | Chained-prior next-steps ledger (`prior:` / `prior_analyses:`) | §8 | 4/4 produce date-stamped `next-steps-*.md`; 3/4 chain via prior field; tied to `science:next-steps` |

---

## 2. Project Archetypes

The four projects sit at different points in a multi-axis space — but every project occupies more than one axis.

| Axis | natural-systems | mm30 | protein-landscape | cbioportal |
| --- | --- | --- | --- | --- |
| Research project (hypotheses, questions, interpretations) | yes | yes (5 hypotheses, 90 interpretations) | yes (4 hypotheses, 32 interpretations) | yes (1 inline hypothesis, 8 interpretations) |
| Computational pipeline (Snakemake) | yes (9 analysis families) | yes (multi-stage Snakemake + workflows/external/) | yes (113-file workflow/) | yes (single Snakefile + 122 scripts) |
| Software deliverable (app/viewer) | **yes** (1135-file Vite/React/TS app in `src/`) | partial (`inc/shiny/` untracked, sharing artifacts) | **yes** (166-file viewer/) | no |
| Code-generated cross-language data model | partial (zod schemas in `src/natural/schema/`) | no | **yes** (LinkML → Pydantic+TS+JSON-Schema+TTL+parquet) | no |
| Authored content layer (long-form prose + YAML registries) | **yes** (234 model YAMLs, 281 visual YAMLs, 26 chapter prose files) | partial (`doc/genes/`, `core/decisions.md`) | partial (`papers/references.bib`) | partial (modality guides) |
| Public data publishing (Frictionless datapackages) | **yes** (117 `science-research-package` profile DPs) | yes (3 DPs with `mm30:` extension block) | descriptors-only (19 sha256-sealed sidecars; zero DPs) | no DPs (acknowledged gap, `t128`) |

**Conclusion.** No project is mono-axis. The single-string `profile:` field is lossy for all four. The current `aspects:` array is doing real work — three of four projects carry the same `[computational-analysis, software-development]` pair, mm30 carries `[hypothesis-testing, causal-modeling, computational-analysis, software-development]`, natural-systems carries `[computational-analysis, hypothesis-testing, software-development]` plus a missing `content-authoring` axis. **The recommendation is not to expand `aspects:`. The recommendation is to formalize "archetype" or "axis" as a structured concept** (multi-valued profile, named compound profile, or a small enum of recognized axis labels) and let `aspects:` retire to the lighter-weight role it was meant to have.

Cross-cuts: classification of each project is `research + pipeline + software`, with mm30 closest to pure `research + pipeline`, protein-landscape adding `viewer + codegen`, natural-systems adding `viewer + content-authoring`, cbioportal closest to `research + pipeline` only.

---

## 3. Stable Cross-Project Conventions

Patterns observed at threshold or above. These are the foundation Science can rely on.

### 3.1 Directory shape (4/4)

- `doc/{questions,papers,topics,plans,interpretations,reports,searches,meta}` is the canonical research-record root in every project. Date-prefixed filenames for time-bound entities (interpretations, plans, discussions, next-steps); slug-only for stable entities (questions, papers, topics, datasets).
- `tasks/active.md` + `tasks/done/YYYY-MM.md` monthly archive is the universal lifecycle shape. Format is `## [tNNN] Title` heading + bullet-key/value list. cbioportal proves it can be operated cleanly; the other three demonstrate it slips without tooling (see §8).
- `science.yaml` is the universal manifest; `knowledge/{graph.trig, sources/local/}` is the universal graph layer.

### 3.2 Pre-registration as a recurring entity (4/4) — P1

All four projects pre-register. Three placement variants:

- `doc/pre-registrations/YYYY-MM-DD-tNNN-<slug>.md` (mm30, 16 files; canonical).
- `doc/meta/pre-registration-<scope>-<slug>.md` (natural-systems × 4, protein-landscape × 2, cbioportal × 2).
- Pre-registration **section** inside a hypothesis spec body (mm30 `specs/hypotheses/h*.md`, protein-landscape `specs/hypotheses/h0[1-4]-*.md`).

Three of four projects type these as `type: plan` with `id: pre-registration:<slug>` — the type/id mismatch is the strongest evidence that pre-registration deserves its own canonical type. cbioportal is the only project to use a project-local `type: pre-registration` (registered via `knowledge/sources/local/manifest.yaml`), and it is the cleanest of the four.

**Recommendation:** add `pre-registration` as a Science-canonical type. Body shape is well-converged (locked thresholds + decision rules + `committed:` date + `spec:` back-link to a design doc). Migration cost is low because the file shapes are already aligned; only the `type:` value and validator coverage change.

### 3.3 Synthesis rollups with structured provenance frontmatter (2/4 with type-naming divergence) — P1

**Correction (post-deep-review).** The original draft of this section claimed "3/4 with the same shape." Re-verification against actual file contents shows the truth is more nuanced: two of four projects ship the structured rollup pattern, but they **diverge on `type:` naming**.

- **mm30** uses `type: "report"` + `report_kind: "hypothesis-synthesis | synthesis-rollup | emergent-threads"` + `id: "report:synthesis-<slug>"`. Per-hypothesis files at `doc/reports/synthesis/h{1..6}*.md`, cross-hypothesis rollup at `doc/reports/synthesis.md`, threads file at `_emergent-threads.md`. Frontmatter includes `source_commit`, `provenance_coverage`, and `hypothesis:` (per-hyp). `synthesized_from: [{hypothesis, file, sha}]` appears **only on the cross-hypothesis rollup** — per-hypothesis and threads files do not carry it. `_emergent-threads.md` carries `orphan_ids: [...]`.
- **protein-landscape** uses `type: "synthesis"` on per-hypothesis files (`id: "synthesis:<slug>"`) and a separate `type: "emergent-threads"` on the threads file. Same provenance fields (`source_commit`, `generated_at`, `provenance_coverage`). No `synthesized_from:` field on any file.
- **natural-systems** has 87 `doc/reports/` files, several of which read as syntheses but without the structured rollup frontmatter.
- **cbioportal** has one synthesis file (placement under `doc/papers/` rather than `doc/reports/synthesis/` — cbioportal-internal cleanup, not a recurring pattern).

The two projects ship the same *shape* (provenance-tracked frontmatter + per-hyp rollups + emergent-threads files), but with incompatible `type:` naming. Tied to `science:big-picture`.

**Recommendation:** canonize the cleaner shape — `type: "synthesis"` for all artifacts with `report_kind: "hypothesis-synthesis | synthesis-rollup | emergent-threads"` discriminator; `id` prefix `synthesis:`. `synthesized_from: [{hypothesis, file, sha}]` is required only on `report_kind: synthesis-rollup` (where it carries the cross-hypothesis sha-tracked provenance); per-hypothesis files carry `hypothesis:` instead, threads files carry `orphan_ids:` and counts. **Both downstream projects need migration to the canonical shape**: mm30 from `type: report` + `report_kind:` to `type: synthesis` + `report_kind:` (and `report:synthesis-*` ids → `synthesis:*`); protein-landscape from `type: emergent-threads` to `type: synthesis` + `report_kind: emergent-threads`. Track both as follow-on tasks; the validator does not warn on legacy `type: report` files in synthesis paths so existing files do not turn the validator red on first managed update.

`curation-sweep` is **not** folded into this `report_kind` enum. It is a separate canonical-promotion candidate (see §6.3); deferring it here keeps this plan tight and lets the curation-sweep promotion pick its own shape.

### 3.4 Chained next-steps ledger (4/4) — P1

All four projects produce date-stamped `doc/meta/next-steps-YYYY-MM-DD.md` files. Three chain via a `prior:` (mm30) or `prior_analyses:` (protein-landscape) field; natural-systems uses the same temporal cadence without an explicit chain field; cbioportal's four files don't currently chain.

Tied to `science:next-steps`. **Recommendation:** standardize the chained-prior field name and let `science:next-steps` populate it automatically.

### 3.5 Frictionless-flavor provenance sidecars (4/4 with shape variation) — P1

- natural-systems: 117 `datapackage.json` records under `public/research/<lens>/<id>/` and `research/packages/<lens>/<id>/`, declaring `profile: science-research-package`, with embedded `research: {target_route, provenance{workflow, config, last_run, git_commit, inputs[]}}` block.
- mm30: 3 `datapackage.json` records with a top-level `mm30:` block carrying `stage, type, pipeline_version, provenance[]` and (for external ingestions) `external_source{name, release, url, license}`.
- protein-landscape: 19 `descriptors/<artifact>.parquet.descriptor.json` files — output-anchored, sha256-sealed inputs and outputs, `git_commit`, `tool_version`, `command`, `parameters`, `notes`. No `datapackage.json` at all.
- cbioportal: zero datapackages today, but task `t128` ("Emit retroactive `datapackage.json` manifests for `results/poc-2026-04-17/` and `results/signature-brca-2026-04-22/`") is the project explicitly recognizing the gap.

The pattern is "datapackage with a project-namespaced extension block" + "sha256-sealed output descriptors". Both halves are reusable. **Recommendation:** Science-bless the datapackage `<project>:` extension block (or a generic `science:` block carrying the same fields) and the sha256-sealed descriptor sidecar shape. Pairs cleanly with mm30's `doc/methods/external-data-ingestion-pattern.md` as a reference layout.

### 3.6 Code-generated knowledge graph layer (4/4)

`knowledge/graph.trig` materialized; `knowledge/sources/local/` with `entities.yaml`/`manifest.yaml`/`relations.yaml`/`mappings.yaml` is the recurring shape (mm30 and cbioportal canonical; natural-systems and protein-landscape with variants). protein-landscape extends with `knowledge/ontology/{lenses,pl}.ttl` codegenned from a LinkML schema — project-grown but the *concept* (codegen-from-schema for a project's entity model) is plausibly recurring once at least one peer adopts it.

---

## 4. Legitimate Heterogeneity

Differences Science should explicitly accept rather than flatten.

### 4.1 Code root convention varies with project shape

- `src/` (natural-systems): software-app dominant.
- `scripts/` (mm30): pure pipeline.
- `src/<pkg>/` + `workflow/scripts/` + `code/scripts/` (protein-landscape): library + pipeline + leftover.
- `code/{config,envs,notebooks,scripts,workflows}` (cbioportal): pipeline-dominant with explicit subdirs.

**Recommendation:** do not pick a winner. Have `science.yaml` declare the project's code roots (e.g., `code_roots: [scripts, code/scripts, src]`) and let validators / health checks consult that field.

### 4.2 Pre-registration placement (`doc/pre-registrations/` vs `doc/meta/pre-registration-*` vs hypothesis-body section)

Once `pre-registration` is a canonical type, the placement decision is project-local. Validators should accept all three placements but the type+id should be consistent.

### 4.3 Snakemake layout

- Per-analysis-family with subdirs (natural-systems: 9 families, each with own `Snakefile`+`config.yaml`+`manifests/`+`results/`).
- Master `Snakefile` + `workflows/stages/<stage>.smk` + `workflows/external/<dataset>.smk` (mm30).
- `workflow/{Snakefile, rules/*.smk, scripts/}` (protein-landscape).
- Single `code/workflows/Snakefile` with no rule-file split (cbioportal).

**Recommendation:** treat as legitimate variation. Emit a `pipeline.layout` field if and when a `pipeline` profile axis lands.

### 4.4 Reading-state on papers

cbioportal's `status: read|abstract-read|summarized|unread` overloads the doc-level `status:` axis, but the underlying need is real and only cbioportal is at scale (58 paper files reading-state-tagged). Per-domain projects (mm30, protein-landscape) carry richer paper frontmatter (PMID, DOI) and don't need reading-state at all. **Recommendation:** add an optional `reading_state` field on papers; do not make it global.

### 4.5 `docs/superpowers/` agent-plans subtree

Three of four projects (natural-systems, mm30, protein-landscape) carry a `docs/superpowers/{plans,specs}/` subtree separate from human-curated `doc/`. cbioportal does not. protein-landscape patches `validate.sh` to suppress the duplicate-doc-root warning when `docs/` only contains `docs/superpowers/*`. This is legitimate specialization (agent vs human authoring split) but is currently fighting Science's "single doc root" assumption. **Recommendation:** `meta/validate.sh` should sanction `docs/superpowers/` (or a generalized `docs/<sanctioned-agent-subtree>/`) explicitly. Tag: `[mav-input]`.

---

## 5. Drift And Ambiguity

Patterns that have no clear reason and create operational cost.

### 5.1 Status-enum sprawl (4/4)

| Project | Distinct status values |
| --- | --- |
| natural-systems | 25 (incl. `complete`/`completed`, `partially-answered`/`partially-resolved`/`partially supported`, `agreed`, `current`, `final`, `sketch`, `closed`, `published`) |
| mm30 | 21 (incl. `partially-complete (qualitative)`, `partially-complete (in-house cohort only; ...)`, `pre-conjecture`, `fully-characterized`, `weakened`, `paywalled`, `draft-v1`, `draft-v2`) |
| protein-landscape | 15 (incl. `effectively-answered-at-2M`, `under-investigation`, `disputed`) |
| cbioportal | 9 (incl. paper reading-state collision) |

Recurring sub-issues: (a) inconsistent past-tense (`complete` vs `completed`); (b) parenthetical qualifiers (`partially-complete (...)`) where a structured `qualifier:` field would be cleaner; (c) per-type versus generic (`under-investigation` is hypothesis-shaped, `read` is paper-shaped); (d) mid-state proliferation (`partially-*` × 3 in natural-systems alone). **P1.** See §6.1 for the recommendation.

### 5.2 Type/id mismatch on pre-registrations (3/4)

`type: plan` with `id: pre-registration:<slug>` in natural-systems, mm30, protein-landscape. Resolved by making `pre-registration` canonical.

### 5.3 Report-id-prefix drift (1/4 explicit, but evidence is strong)

natural-systems: 26 of 31 `doc/reports/*.md` files use `id: doc:<date>-<slug>` instead of `id: report:<date>-<slug>`; one file has no frontmatter at all. The other three projects have small enough `doc/reports/` to obscure the pattern. **P2** — but worth a validator id-prefix conformance check (see §10) that would surface this in any project.

### 5.4 Done tasks accumulating in `active.md` (3/4)

natural-systems 49% (114/232), mm30 ~30% (44/152 done+retired+deferred), protein-landscape 44% (44/101). cbioportal 0% — proving discipline is enforceable but not without tooling. **P1.** See §8.

### 5.5 Mixed task-id padding (mm30 only, 1/4)

`[t27]` (legacy) vs `[t043]` (current). Cosmetic but diff-noisy. **P3.**

### 5.6 `mode:` field overloaded across families

protein-landscape: `mode: write` (25 interpretations), `mode: standard` (15 discussions), `mode: conceptual` (1) — same field, different vocabularies per family. mm30 uses `mode: full` on next-steps and `mode: propose|apply` on curation sweeps — cleanly separated by family. cbioportal uses `mode: research`/`standard` on interpretations + `mode: propose` on curation sweeps. **P2** — namespace per-family or define a shared enum.

### 5.7 `docs/` vs `doc/` parallel hierarchy (3/4)

See §4.5. The drift is real (8 frontmatter-less `docs/plans/` files in natural-systems, 14 superpowers-era plans in mm30 still present, 12 agent-authored plans in protein-landscape) but the *cause* is legitimate (agent-vs-human authoring split). Resolution: sanction the agent subtree explicitly, then prune the residue.

---

## 6. Entity Model Recommendations

### 6.1 Status enum strategy — P1

Three orthogonal axes are getting collapsed onto one `status:` field today. Recommendation: split.

- **Per-type work-status enums.** Hypothesis: `{conjecture, proposed, active, partially-supported, supported, refuted, retired}` (mm30's two-axis status + identification is a project-grown specialization on top of this — see §6.2). Question: `{open, partially-answered, answered, retired}` (with `revisit_condition:` optional). Task: `{proposed, in-progress, blocked, done, retired, deferred}`. Paper: `{unread, abstract-read, summarized, archived}` *or* keep paper status off the work-status axis and use `reading_state:` per §4.4.
- **Optional `qualifier:` field** for structured caveats. Replaces `partially-complete (qualitative)` and `partially-complete (in-house cohort only; full-cohort test MMRF-gated)` with `status: partially-complete` + `qualifier: "qualitative"` or `qualifier: {scope: "in-house cohort", blocked_on: "MMRF data access"}`.
- **Hyphenation rule.** Pick one of `partially-supported` or `partially supported`; fix `complete` vs `completed` once and add validator coverage.

Migration cost: medium (touches every entity family across all four projects). Recommend rolling out per-family with validator warnings before errors.

### 6.2 Hypothesis two-axis status + `phase` — P2 `[hyp-phase]`

mm30 ships `status: supported` (replication) + `identification: observational` (causal-id) + `confidence_label` + `confidence_mechanistic_label`. The principle (separating replication-quality from causal-identification-quality) is a legitimate causal-research need likely to recur in protein-landscape and any other DAG-driven project. **Coordinate with the in-flight `2026-04-25-hypothesis-phase.md` plan**, which is adding `phase: candidate|active`. The two are orthogonal: `phase` is "is this a frame we are testing yet?", `identification` is "how rigorous is the causal claim?". Recommendation: ship `phase` first (already in flight), revisit `identification` as a follow-on when a second project adopts it.

### 6.3 Sanctioned project-local entity-kind extension — P1

cbioportal's `knowledge/sources/local/manifest.yaml` with `strictness: typed-extension` is a working solution to "Science doesn't model this kind, but my project needs it." The shape registers the kind name + canonical ID prefix + which layer it lives in. mm30 uses the same surface for `gene-note`, `decision`, `concept`, `latent`, `mechanism`. natural-systems and protein-landscape use *implicit* extensions (inline propositions, `finding:F[0-9]+`, refactor-pair directories) that have no formal registration.

**Recommendation:** Science formally support project-local entity-kind registration with a documented schema. Validators should consult the manifest and treat registered local kinds as first-class. The `typed-extension` strictness model is correct — accept the kind, validate against the project's declared shape, do not require it to be one of Science's canonical types.

Once this lands, several specific kinds become candidates for **promotion to canonical** based on cross-project recurrence:

- `pre-registration` (4/4) — promote now, see §3.2.
- `synthesis` (2/4 with structured rollup frontmatter — mm30 as `type: report`, protein-landscape as `type: synthesis` + separate `type: emergent-threads`; the divergence itself is the canonization motivator) — promote, see §3.3.
- `curation-sweep` (2/4 explicit, mm30 + cbioportal) — P2; cbioportal explicitly cites mm30 as origin. Tied to `science:curate`.
- `guide` / `modality-guide` (2/4 explicit, mm30 + cbioportal) — P2; same origin lineage as curation-sweep.
- `proposition` / `finding` / `claim` — see §6.4.

### 6.4 Proposition / claim / finding — promote or formalize-inline — P1

Two/four projects model atomic claims as first-class entities (mm30's 15 `specs/propositions/p*.md` with `measurement_model{observed_entity, latent_construct, measurement_relation, rationale, known_failure_modes[]}` + `claim_layer` + `identification_strength` + `proxy_directness` + `supports_scope` + `independence_group`). Two/four use inline alternatives — protein-landscape with `h01:P3`, `finding:F53` cited 30+ times across the corpus with no backing files; cbioportal with verdict polarity tokens `[+]/[~]/[?]/[-]` and a backfill audit TSV at `doc/plans/2026-04-19-verdict-token-backfill-audit.tsv`. natural-systems handles claims as workflow inputs in `workflows/claim-extraction/`, not as entity files.

**Recommendation:** Science needs a position on atomic claims. Two design directions:

1. **Lightweight inline convention.** Bless `<hypothesis>:P[0-9]+` and `finding:F[0-9]+` as recognized inline-claim references that resolve to a section in a parent file. Validators check that referenced ids exist somewhere.
2. **First-class `proposition` entity.** Adopt mm30's shape. Each proposition lives in its own file with `measurement_model{}`, `claim_layer`, etc.

Lightweight is faster to ship and matches protein-landscape's current usage. First-class is graph-cleaner and matches mm30's. **Defer to a focused design pass** (see §11.1). Until then, projects can do either; validators should accept both.

### 6.5 Structured fields, not free-text strings — P2

Several fields are crying out for structure across multiple projects:

- `datasets:` (3/4 mix entity-ids and free strings) — pin to `[<entity-id>]` or `[{id, name, accession}]`.
- `source_refs:` (4/4 mix paper ids, `cite:Year` keys, raw DOIs, file paths) — same.
- `ontology_terms:` (3/4 use free-text; only cbioportal uses CURIE-shaped values) — bind to a declared ontology (the project's `science.yaml: ontologies` list); validate URIs.
- `input:` on interpretations (mm30, cbioportal use free-form strings like `"BRCA pair: tcga_mc3 vs msk_impact_2017"`) — structure as `{cohort_pairs: [{matched, unmatched, cancer_type}]}` or similar.
- `access:` block on datasets (protein-landscape's `{level, verified, verification_method, last_reviewed, exception:{mode, decision_date, ...}}`) — adopt as a Science-canonical optional shape.

### 6.6 Typed-related fields — P3

natural-systems' `specs/*-design.md` use a richer related-family split: `related_questions`, `related_specs`, `related_interpretations`, `related_reports`, `related_tasks`. Other projects flatten everything into one `related:`. **Hypothesis** that finer granularity is useful at ≥2 projects; only natural-systems ships it today. Note in deferred questions; don't promote yet.

---

## 7. Data And Result Handling Recommendations

### 7.1 Datapackage `<project>:` extension block — P1

See §3.5 for evidence. Recommendation: define a Frictionless extension profile (`science-research-package` is natural-systems' name; could be `science-package-1.0` upstream) with a generic `science:` (or project-namespaced) block carrying `stage, type, pipeline_version, provenance[{workflow, config, last_run, git_commit, inputs[]}], external_source{name, release, url, license}`. Templates in `templates/` should ship a starter `datapackage.json`.

### 7.2 Output-anchored sha256 descriptor sidecars — P1

protein-landscape's `descriptors/<artifact>.parquet.descriptor.json` carrying `inputs[{path, sha256}]`, `outputs[{path, sha256, row_count}]`, `git_commit`, `command`, `parameters`, `notes` is the right shape for "datapackage-lite, output-anchored, sha256-sealed." cbioportal's `t128` task is the gap-acknowledgment in another project. **Recommendation:** ship as a documented optional pattern, maybe with a `science-tool data descriptor` emitter command. Add `task:<id>` and `question:<id>` fields so descriptors close the code↔entity loop (currently they only carry `git_commit`).

### 7.3 Dataset `access:` structured block — P2

protein-landscape's `doc/datasets/deeploc2.md` carries `access: {level, verified, verification_method, last_reviewed, verified_by, source_url, exception: {mode, decision_date, followup_task, superseded_by_dataset, rationale}}`. cbioportal's `doc/plans/t111-data-gate-record.md` is the same idea expressed as a plan instead of frontmatter, with SHA256 + DOI + assembly + retrieved-date in a markdown table. **Recommendation:** adopt the structured `access:` block as a canonical optional shape on `dataset:` entities. Captures controlled-access lifecycle as metadata.

### 7.4 Symlinked external data + `local_path:` — P2

protein-landscape: `data` is a symlink to `/data/proj/protein-landscape`; tracked datasets carry `local_path: data/raw/<slug>/`. mm30 uses untracked `data/` alongside 1,592 tracked descriptors; the protected MMRF data lives outside the repo via `config/workflow-host.yml`. natural-systems: no symlinks. cbioportal: no data symlinks (only a `science` convenience symlink for tooling). **Recommendation:** Science recognize `local_path:` as a canonical dataset field (it currently has 4 uses across all four projects, all in protein-landscape).

### 7.5 `.gitignore` exception patterns — P2

natural-systems' `src/chapters/generated/{guide-data,...}.json` allow-list (six explicit re-includes after the bulk `src/chapters/generated/*` ignore) and protein-landscape's `!data/processed/entities/.gitkeep` cookie are the same pattern: ignore-then-pin specific outputs. **Recommendation:** document this as the canonical pattern for "we ignore this directory but ship these specific files."

### 7.6 Reproducibility evidence — informational

Three of four projects can reproduce their public data through a documented pipeline (Snakemake + uv-locked deps + per-artifact `git_commit` in descriptors). protein-landscape needs `runpod/` for GPU-only steps. Reproducibility is in a healthy state across the audit set.

---

## 8. Planning And Task Recommendations

### 8.1 Auto-archive done tasks — P1

3/4 projects accumulate done entries in `tasks/active.md` (49% / 30% / 44%). cbioportal is clean; the difference is that cbioportal moves entries on done. **Recommendation:** add `science-tool tasks archive` (and surface in `science-tool health`) that moves `status: done|retired` entries from `tasks/active.md` to `tasks/done/YYYY-MM.md` with the entry's `completed:` date as the bucket.

### 8.2 Code/notebook → task back-link — P1

All four projects have weak code-side linkage to tasks. Forward direction (entity → code) lives in plan/interpretation prose; reverse direction is filename-dependent at best. Three concrete patterns observed:

- **Filename convention** (cbioportal `code/notebooks/q011_length_adjustment_topn_comparison.py`, `t070_*.py`, `t131_*.py`).
- **Commit-message tag** (`fix(t131): ...`, observed in cbioportal and protein-landscape).
- **Descriptor sidecar** (protein-landscape descriptor JSONs carry `git_commit` but not `task:`).

**Recommendation:** case-by-case rather than universal sidecar.

- High-value artifact-producers (descriptor-generating scripts): add `task:<id>` and `question:<id>` to the descriptor JSON.
- Notebooks (3-5 per project, named after tasks): a `# task: tNNN` comment-block convention is sufficient.
- Library code: no metadata required; entity → file linkage is enough.

Ship as a documented convention; do not require it via validator.

### 8.3 Pre-registration ↔ design-spec linkage — P1

mm30's `doc/pre-registrations/*.md` carry a `spec: doc/specs/<...>-design.md` field linking pre-reg to design doc. cbioportal pairs `<date>-tNNN-<slug>-design.md` with `<date>-tNNN-<slug>-implementation-plan.md` filenames but no structured frontmatter link. protein-landscape's `doc/meta/pre-registration-*.md` link via `related:` only. **Recommendation:** once `pre-registration` is canonical (§3.2), add a `spec:` (or `design:`) field as part of its shape.

### 8.4 Inline task `Result:` paragraphs — P2

natural-systems' `tasks/active.md` and `tasks/done/*.md` contain `**Result:**` paragraphs that read like short interpretations. mm30 has the same pattern (e.g., `[t55]` with full multi-paragraph findings). protein-landscape is more disciplined (free-text body but typically pointing at an interpretation). cbioportal's tasks describe what + why; provenance lives in interpretation files. **Recommendation:** discourage inline `Result:` blocks in tasks; they should link to an `interpretation:` entity. Validator could warn when a `done` task has more than N lines of body without a `related:` link to any interpretation.

### 8.5 Task `group:` taxonomy — P2

cbioportal uses 7 stable groups (`audit-fixes`, `audits`, `meta`, `meta-analysis`, `pipeline`, `questions`, `searches`); mm30 uses hypothesis-keyed groups (`h{1,2,4,6}-*`, `causal-identification`, etc.); natural-systems and protein-landscape don't use `group:` consistently. **Recommendation:** make `group:` an optional documented field. Don't standardize the values.

### 8.6 Long-form plans — P3

mm30 carries plan files of 1.5k-3.2k lines (`t172`, `t202`, `hypothesis-pipeline-architecture`); natural-systems carries 191 plans with similar variance; protein-landscape's `docs/superpowers/plans/` files reach 3,421 lines. The pattern is: plans grow into pre-reg + design + acceptance + result narratives. Project-side hygiene issue, not an upstream change.

---

## 9. Validation And Managed Artifact Recommendations

### 9.1 `validate.sh` MAV adoption — P1 `[mav-input]`

The audit is a clean validation of the in-flight `docs/plans/2026-04-25-managed-artifact-versioning.md` plan. Evidence:

| Project | `validate.sh` status vs `meta/validate.sh` | MAV-relevant? |
| --- | --- | --- |
| natural-systems | 80 lines / ~14 content blocks drift (env sourcing, `LOCAL_PROFILE` value, ontologies→curated, error gating) | yes — generic |
| mm30 | 84 lines drift (env early loading, science-tool exit-on-missing, stricter graph-audit error handling) | yes — generic |
| protein-landscape | several substantive logic changes (+ section 17 expensive-pipeline-artifacts; project-specific) | yes (generic parts) + no (section 17 stays local) |
| cbioportal | byte-identical to `meta/validate.sh` | clean reference |

**Concrete `mav-input` fixes for `meta/validate.sh`** (extracted across projects):

- **Parameterize `LOCAL_PROFILE`** — read from `science.yaml.knowledge_profiles.local` rather than hard-coding `"local"`. natural-systems uses `"project_specific"`; this single change closes the largest single piece of drift in that project.
- **Decide on `.env` sourcing** — natural-systems and mm30 add it for `SCIENCE_TOOL_PATH`; protein-landscape removes it. Project-level toggle (or sanction `.env` sourcing canonically and let projects opt out via env-var).
- **JSON-payload extractor** — protein-landscape adds `extract_json_payload()` Python helper because `science-tool` emits non-JSON noise on stdout/stderr. **Better fix:** `science-tool` emits clean JSON. Track as a `science-tool` bug, not a `validate.sh` change.
- **Replace `ontologies` list-shape check with `knowledge_profiles.curated` check** — natural-systems' diff suggests the canonical check has shifted; confirm the right axis.
- **Promote graph-audit unparseable to error** — both natural-systems and mm30 do this locally (mm30 with stricter error-gating around `graph.trig` presence). Probably the right canonical default.
- **Sanction `docs/superpowers/`** in the duplicate-doc-root warning — protein-landscape patches this locally; 3/4 projects have the subtree.
- **Sanction `workflow/` as an execution root** when it contains a `Snakefile` — protein-landscape patches this locally; tied to a `pipeline` profile axis.

### 9.2 Drift not solvable by MAV

These need entity-model or profile-model decisions, not artifact versioning:

- Status enum sprawl (§6.1) — needs per-type schemas.
- Project-local entity kinds (§6.3) — needs sanctioned extension surface.
- Pre-registration `type:` (§3.2) — needs canonical type.
- Multi-axis profile (§2) — needs profile-axis design.
- Reading-state on papers (§4.4) — needs `reading_state` field.
- Code-to-entity linkage (§8.2) — needs convention, not validator.

### 9.3 Validator id-prefix conformance check — P2

natural-systems' 26-of-31 `id: doc:DATE-slug` instead of `id: report:DATE-slug` would have been caught by a per-type id-prefix grammar rule in `validate.sh`. The other projects show smaller-scale drift (mm30 paper case-inconsistency, protein-landscape's bare-q-number vs slug ids). **Recommendation:** add a per-type id-prefix conformance check to `meta/validate.sh` — declarative table mapping `type:` value → required id prefix.

---

## 10. Tooling Recommendations

### 10.1 `science-tool` candidates

- **`science-tool tasks archive`** — moves done/retired tasks from `active.md` to `done/YYYY-MM.md`. Surface in `science-tool health` when the active backlog is dirty. P1.
- **`science-tool data descriptor`** — emits a sha256-sealed parquet/csv descriptor sidecar (the §7.2 shape) for a given output path. P2.
- **`science-tool project profile`** — show / set the multi-axis profile (once §2 lands). P2.
- **`science-tool entity register`** — register a project-local entity kind in `knowledge/sources/local/manifest.yaml` (the §6.3 shape). P2.
- **`science-tool refs lint`** — surface unresolved `concept:` / `finding:` / `task:` references against the local profile. natural-systems already has a hand-rolled version of this in `doc/meta/entity-health/`. P2.

### 10.2 Phase-1 inventory bugs `[v1-tooling]`

The Phase 1.5 fix landed four bug fixes mid-audit (corrected `entity_id_prefix_counts`, content-level validator diff, templates excluded from entity index, gitignored top-level dirs surfaced). Two further v1 improvements would be high-value:

- **Frontmatter coverage % per dir.** protein-landscape has 14/73 plans with YAML frontmatter; the inventory does not currently report coverage rate as a percentage. Useful health signal.
- **Embedded-metadata confidence flag.** Currently flagged in `tooling-notes.md`; protein-landscape's audit confirmed a high false-positive rate (markdown `---` dividers + key-runs inside code blocks). Low/medium/high confidence on the heuristic would let auditors prioritize.

### 10.3 Audit script reuse

The Phase 1.5 inventory script is reusable for periodic project-shape health checks. Consider promoting it from `scripts/audit_downstream_project_inventory.py` to `science-tool project inventory` once a stable v1 shape converges. Defer until at least one re-audit confirms the v1 fields are right.

---

## 11. Deferred Questions

These need a focused design pass before implementation, not just synthesis:

### 11.1 Atomic-claim modeling: inline vs first-class entity

Recommendation in §6.4 is "decide between two design directions." The decision has graph-shape implications (first-class is graph-cleaner; inline is faster) and migration-cost implications (mm30 has 15 propositions in production; protein-landscape has 17 inline findings; natural-systems has none; cbioportal has verdict tokens but no claims). A two-page design doc weighing the options against `science:big-picture` and verdict-rollup needs is the right next step.

### 11.2 Profile-axis design

Once §2 is accepted in principle, the design question is the shape: multi-valued `profile:`, named compound profiles, structured `archetype: {research, pipeline, software}` map, or a small enum of recognized axis labels. Should pair with a `pipeline:` aspect/axis decision so `validate.sh` can sanction `workflow/` and `code/workflows/` execution roots.

### 11.3 Non-markdown entity registries

natural-systems' 234 model YAMLs + 281 visual YAMLs + 8 more YAML registry families are *not* expressible in Science's markdown-frontmatter entity model. mm30's `specs/claim-registry.yaml` is the same shape at smaller scale. Should Science model arbitrary YAML/JSON entity registries alongside markdown frontmatter? Big design pass; defer until a second project shows comparable scale.

### 11.4 Structured-prose entity model

natural-systems' 26 chapter prose files (102k+ lines) carry `<!-- model: id -->` HTML-comment markers + inline classification tables + `**Key:** value` lines. This is *deliberate* prose-as-registry, not drift. The pattern is project-specific today. Worth a future design pass on whether Science wants to model "structured prose" as an entity-bearing surface.

### 11.5 LinkML-driven cross-language data model

protein-landscape's `src/protein_landscape/model/` codegens to Pydantic, TypeScript, JSON Schema, TTL, parquet contracts, with a pre-commit hook keeping artifacts in sync. The *concept* (codegen-from-schema for a project's entity model) is plausibly recurring once at least one peer adopts it. Defer until a second project shows the same shape.

### 11.6 Refactor-pair doc family

natural-systems has 4 refactor-pair directories; protein-landscape has `doc/issues/`; mm30 has `doc/reorg/`; cbioportal has none. The pattern is driven by the global user CLAUDE.md "Refactoring" rule. **Question for the user:** do you want Science to model refactor-as-entity, or is the file-pair convention sufficient at the project level?

### 11.7 Decision-log entity

mm30's `core/decisions.md` (D1–D10+) is surfaced via `knowledge/sources/local/entities.yaml` as `decision:DN`. cbioportal has `doc/discussions/*` with `focus_type` + `focus_ref` fields that play a similar role. natural-systems and protein-landscape don't have an explicit decision log. **Question:** is this a recurring need, or should decisions stay narrative inside discussions / interpretations?

---

## Appendix: Convention threshold application notes

For reviewers checking the priority assignments:

- §3.2 pre-registration (P1): present in 4/4 projects with substantial body-shape convergence; 3/4 carry the type/id mismatch that resolves to the same fix. Strong P1.
- §3.3 synthesis rollups (P1): mm30 + protein-landscape both ship structured rollups but with divergent `type:` naming (mm30 `type: report` + `report_kind:`, protein-landscape `type: synthesis` + separate `type: emergent-threads`). The divergence itself is the strongest evidence that Science needs a canonical shape. Justified P1; canonize the cleaner `type: synthesis` form, accept downstream migration cost as a follow-on.
- §3.4 chained next-steps (P1): 4/4 produce the files; 2/4 chain via explicit field. P1 because the field convention is straightforward and tied to `science:next-steps`.
- §3.5 datapackage extension + descriptors (P1): 3/4 ship the pattern, 1/4 has an active task to adopt it. The "+1 acknowledged gap" upgrades 3/4 to a P1 candidate per the convention threshold's "evidence is unusually strong" clause.
- §6.1 status enum split (P1): 4/4 affected; the recommendation is the only path that reconciles the four observed behaviors.
- §6.3 sanctioned local entity kinds (P1): 2/4 explicit + 2/4 implicit. The 2/4 explicit cases (mm30 + cbioportal, with cbioportal explicitly citing mm30 as origin) prove cross-project transferability; upgrading to P1 with the justification that the implicit 2/4 would benefit from the same surface.
- §8.1 auto-archive (P1): 3/4 lag, 1/4 clean. The clean case is an *existence proof* that the discipline is enforceable with tooling — promotes this from convention to operational requirement.
- §8.2 code → task back-link (P1): 4/4 weak; multiple compatible patterns exist; recommendation is case-by-case, not universal.

P2 candidates are 2/4 cases with reasonable evidence; P3 candidates are 1/4 with hypothesis-strength reasoning. None are P0 — no project is blocked from safe downstream use.
