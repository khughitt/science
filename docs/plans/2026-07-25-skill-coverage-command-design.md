# `science skills coverage` Command (skill-coverage sub-plan 4)

> Design doc. Parent: [`2026-07-23-data-product-vocabulary-and-skill-coverage-design.md`](2026-07-23-data-product-vocabulary-and-skill-coverage-design.md).
> Predecessors (all shipped to main): sub-plan 2 (`skills_loaded` truth path, reified
> `sci:skill/<id>`), sub-plan 3 (packaged inventory + role-typed overlay), sub-plan 1
> (enrollment config in `ProjectConfig`).

## Motivation

The prior sub-plans built the substrate but nothing user-facing consumes it. This sub-plan is the
capstone: the `science skills coverage` command that **joins** what analyses touch (data-product
terms, via `dataset_usage` → dataset `provided_capabilities`) against what the corpus **covers**
(leaf `covers:`, via the overlay) and what each plan actually **loaded** (reified `skills_loaded`),
then emits a `coverage-report` and evidence-backed skill candidates. It closes Plan 2.

## Grounding (verified against the live corpus at `c06e6073`)

- **Registry.** `science_tool.registry.config.load_global_config() -> GlobalConfig` enumerates
  `projects: list[RegisteredProject]` from `~/.config/science/config.yaml` (XDG-aware via
  `get_science_config_dir()`). Each `RegisteredProject` exposes `path: str`, `name: str`,
  `id: str | None` (can be `None` for legacy entries), `role`, `parent`. Root =
  `Path(project.path).expanduser()`; the `science.yaml` inside is `project_config_path(root)`.
- **Loader.** `science_tool.graph.sources.load_project_sources(project_root, ...) -> ProjectSources`
  returns `.entities: list[Entity]` **and** `.skill_loads: list[SkillLoadRecord]` (already collected
  inside the loader; generation computed there too). No materialization required.
- **Capabilities.** On a gen-3 `kind: dataset`, `provided_capabilities` is **preserved-raw** in
  `Entity.model_extra` (`extra="allow"`). Parse with
  `science_tool.datasets.capability_shape.parse_gen3_capabilities(value) -> list[Capability]`; each
  `Capability.data_product` retains the `data-product:` prefix and joins directly against
  `catalog.by_id` / `DataProductTerm.id` (same pattern `^data-product:[a-z0-9][a-z0-9-]*$`).
- **Plan fields.** `Entity.dataset_usage: list[DatasetUsage]` is typed (`ref` starts `dataset:`,
  plus `role`, `overlap`). `skills_loaded` is preserved-raw but is already reified into
  `sources.skill_loads` as `SkillLoadRecord(plan_id, canonical_skill_id, reason)`.
- **Join keys.** `SkillLoadRecord.canonical_skill_id` is the **bare kebab id**
  (`transcriptomics-scrna-qa`) → `SkillOverlay.get(id)` with no transformation. Data-product term
  ids **carry** the `data-product:` prefix. **Prefix asymmetry — never cross-normalize the two.**
- **Enrollment ⟹ gen-3.** `ProjectConfig._enrolled_requires_generation_3` already guarantees an
  enrolled project is pinned gen-3, which is exactly when `skill_loads` is populated and capability
  shape is validated. `domain_enrollment_status(config, "molecular-measurement") ->
  EnrollmentStatus | "undeclared"` is the reader. The only enrollable domain in v1 is
  `molecular-measurement`.

## 1. Architecture / package split

- **`science-model` — `science_model/skill_coverage/coverage.py` (new, pure, no I/O).** Owns the
  input evidence types, the overlay/catalog join, coverage-state classification, cross-project
  candidate generation, the discriminated-union output types, and `serialize_coverage_report`
  (canonical JSON). It assembles the **entire** report — including the single out-of-domain /
  undeclared results — from one `list[ProjectEvidence]`, so ordering and shape live in exactly one
  place. Deterministic and unit-testable with no filesystem. Lives beside the overlay, catalog, and
  enrollment vocabulary it consumes.
- **`science-tool` — `science_tool/skills_coverage/` (new package).** The I/O shell: enumerate the
  registry, load each project, **project** entities into `ProjectEvidence`, build the overlay +
  catalog, call the model, serialize, write, and wire the CLI. This is the only place
  `parse_gen3_capabilities`, `dataset_usage`, and `sources.skill_loads` are read.

`science-tool` depends on `science-model`; **never the reverse** (the model defines the input/output
types and pure logic; the tool fills the inputs from `Entity` objects).

## 2. Evidence projection (`science-tool`)

`ProjectEvidence` (a `science-model` input type) carries `project: str`, `enrollment:
EnrollmentStatus | Literal["undeclared"]` (reusing the enrollment vocabulary in the same package),
and — **only when enrolled** — the raw join facts below. Non-enrolled projects are represented as a
`ProjectEvidence` with the status set and empty facts, so the model can emit their single result
without the tool loading their sources.

`project_evidence(project: str, sources: ProjectSources) -> ProjectEvidence` (enrolled projects
only) walks `sources.entities` once:

- **datasets:** for each `kind: dataset`, `parse_gen3_capabilities(model_extra["provided_capabilities"])`
  → the set of `data_product` term ids it provides (a dataset with none is *untagged*).
- **plans:** for each `kind: plan`, obtain its used datasets by the **same reference-resolution
  semantics materialization uses** — build `ReferenceResolver.from_entities(sources.entities,
  manual_aliases=sources.manual_aliases, archive_alias_tokens=sources.archive_alias_tokens,
  identity_table=build_identity_table(sources))` and read resolved dataset refs by reusing
  `usage_records_for_entity(plan, resolve_dataset_ref=<same callable `_add_dataset_usage_edges`
  passes>)`. Authored refs on the entity are **not** canonical — a valid dataset **alias** or manual
  mapping resolves through the resolver, so a raw dict lookup would falsely flag it dangling. A ref
  the resolver cannot resolve is the hard error (matching materialization), not a dict miss. Group
  `sources.skill_loads` by `plan_id` → the canonical skill ids that plan loaded.
- Emit raw join facts (no overlay/catalog knowledge — that is the model's job):
  - `term_usages: tuple[TermUsage, ...]` — one `(plan_ref, dataset_ref, term)` per used-and-tagged
    pairing;
  - `untagged_usages: tuple[DatasetUse, ...]` — one `(plan_ref, dataset_ref)` per used-but-untagged
    dataset;
  - `plan_loaded_skills: tuple[PlanSkills, ...]` — `(plan_ref, skill_ids: tuple[str, ...])` for every
    plan that loaded at least one skill.

A `dataset_usage.ref` that the resolver **cannot resolve** to a dataset entity is a **hard error**
(fail-early — a genuinely dangling usage ref is malformed evidence; a resolvable alias is not).

## 3. Coverage states (`science-model`, exact-term)

`compute_coverage(projects: list[ProjectEvidence], overlay: SkillOverlay, catalog:
DataProductCatalog) -> CoverageReport`. A non-enrolled `ProjectEvidence` yields exactly one
`OutOfDomainResult` or `UndeclaredDomainResult` and no join work; an enrolled one runs the join
below. Coverage is **exact-term, not ancestor-aware** — a leaf covering a broader term does not
auto-cover descendants (the deliberate dual of the matcher's descent rule; tested on parent/child
pairs).

Because the global covering set is a corpus-global property of the overlay (not per-project), a term
is *either* coverable (some leaf covers it) *or* not, portfolio-wide: **`uncovered` and
`covered-not-loaded` never both occur for the same term.** This is why candidates draw only from
`uncovered` terms.

For each project and each `term` it touches (grain: `(project, term)`):

- **global covering set** = overlay leaves whose `covers` includes `term`.
- Partition the plans touching `term` into those that loaded ≥1 covering leaf (**healthy — emits
  nothing**) and those that did not.
- **empty global set** → **`uncovered`** `{project, term, observation_level, evidence_refs}`
  (evidence = every `(plan, dataset)` touching the term).
- **non-empty global set but ≥1 touching plan loaded none of it** → **`covered-not-loaded`**
  `{project, term, observation_level, available_skill_ids, evidence_refs}` (`available_skill_ids` =
  sorted global covering set; evidence = the non-loading plans + their datasets).

Other states:

- **`unmapped`** — per `(project, dataset)` untagged usage: `{project, observation_level,
  evidence_refs}` (no term). Analysis activity present, dataset not tagged against any term.
- **`unmapped-skill-reference`** diagnostic — for every `(plan, skill_id)` in `plan_loaded_skills`
  where `overlay.get(skill_id) is None`: `{project, plan_ref, skill_id}` (canonical post-alias id —
  the id that failed to resolve). Coexists with any coverage state.

A used dataset whose `data_product` is **not** a catalog term is a **hard error** (aborts the scan):
coverage is the first consumer that joins datasets against the closed catalog vocabulary, so it is
the natural integrity gate — consistent with "closed vocabulary, unknown = hard error".

**`observation_level` is `analysis-usage` for every occurrence in v1.** The parent's `project-demand`
fallback (a term demanded via shared question/hypothesis reachability, with no analysis plan
touching it) needs epistemic-graph reachability, which contradicts this lightweight no-graph read
path. It is deferred; the field is kept so the schema is forward-compatible.

## 4. Candidates (`science-model`, cross-project, from `uncovered` only)

One candidate per **distinct uncovered term** across the portfolio:

- `proposed_scope` = the term id.
- `evidence` = the sorted set of **structured triples** `{project, plan_ref, dataset_ref}` across all
  projects with an `uncovered` occurrence for the term. Structured (not flattened refs) so the score
  is reproducible from the report: the triples ARE the `(project, plan, dataset)` units the score
  counts, and carry project ownership so duplicate local plan/dataset ids across projects do not
  collapse.
- `score = round(1 - 1 / (1 + n_occurrences + (n_projects - 1)), 3)` where `n_occurrences` = distinct
  `(project, plan, dataset)` triples touching the term across the portfolio and `n_projects` =
  distinct projects exhibiting it. Deterministic, in `(0, 1)`, monotone in both repeated use and
  cross-project breadth.
- `likely_archetype` = **catalog sibling inference**:
  - `parents` = `term.broader` (a catalog term may have several). If empty → `indeterminate`.
  - `siblings` = catalog terms `S != term` with `S.broader ∩ parents != ∅`.
  - `covered_sibling_archetypes` = the archetype of each overlay leaf that covers some sibling.
  - **exactly one** archetype in that set → use it; otherwise (zero, or ≥2 distinct) →
    `indeterminate`.

No skill prose is generated — candidates are evidence-backed pointers only.

## 5. Report schema (`coverage-report`) — structural discriminated union

Every `evidence_refs[]` is a list of structured `{plan_ref, dataset_ref}` pairs (the occurrence
already carries `project`), so plan↔dataset pairing survives serialization. Distinct frozen
dataclasses per `state` so invalid field combinations are unrepresentable; each has a `to_dict()`
producing exactly its shape:

- `OutOfDomainResult` → `{state: "out-of-domain", project}` — no term, no observation_level.
- `UndeclaredDomainResult` → `{state: "undeclared-domain", project}`.
- `UnmappedOccurrence` → `{state: "unmapped", project, observation_level, evidence_refs[]}`.
- `UncoveredOccurrence` → `{state: "uncovered", project, term, observation_level, evidence_refs[]}`.
- `CoveredNotLoadedOccurrence` → `{state: "covered-not-loaded", project, term, observation_level,
  available_skill_ids[], evidence_refs[]}`.

Plus `SkillReferenceDiagnostic{project, plan_ref, skill_id}` and
`Candidate{proposed_scope, likely_archetype ("indeterminate" when unknown), score, evidence[]}`
(evidence = `{project, plan_ref, dataset_ref}` triples, per §4).

**`skill_id`, not `raw_skill_id`.** The reified `SkillLoadRecord` keeps only the **canonical**
(post-alias) id — the authored id is discarded upstream — so the diagnostic reports the canonical id
that failed to resolve against the overlay, named `skill_id` rather than the parent design's
`raw_skill_id`, and adds `project` so identical `plan_ref`s across projects are unambiguous. This
narrows the parent's `{raw_skill_id, plan_ref}` contract (the authored id is not recoverable from the
reified record without re-parsing raw frontmatter, which this sub-plan deliberately does not do).

`CoverageReport{coverage_occurrences[], skill_reference_diagnostics[], candidates[]}.to_dict()` →
the report object. `serialize_coverage_report(report) -> str` = `json.dumps(indent=2, sort_keys=True)
+ "\n"`. **Deterministic ordering** independent of scan order:

- `coverage_occurrences` sorted by `(state, project, term or "", evidence_refs)`.
- `skill_reference_diagnostics` sorted by `(project, plan_ref, skill_id)`.
- `candidates` sorted by `(-score, proposed_scope)`.

## 6. Command & portfolio scan (`science-tool`)

`science skills coverage [--output PATH]`, a new subcommand on the existing
`skills_group` (`skills_lint/cli.py`). `scan_portfolio(config_path: Path | None = None) ->
CoverageReport`:

1. `load_global_config(config_path).projects`.
2. Per registered project: resolve root, load `ProjectConfig` (`project_config_path(root)`),
   read `domain_enrollment_status(config, "molecular-measurement")`:
   - `out-of-domain` → one `OutOfDomainResult`;
   - `undeclared` → one `UndeclaredDomainResult`;
   - `out-of-domain` / `undeclared` → a `ProjectEvidence` carrying only `project` + `enrollment`;
   - `enrolled` → `load_project_sources(root)`, `project_evidence(project, sources)`.
   Every project (enrolled or not) contributes exactly one `ProjectEvidence` to the list.
3. Build the overlay (`build_skill_overlay(load_skill_inventory(), catalog)`) + catalog
   (`load_catalog()`), call `compute_coverage(projects, overlay, catalog)` — which assembles the
   whole report, non-enrolled results included.
4. `serialize_coverage_report(report)` → stdout, or `--output PATH` file.

`project` identifier = `RegisteredProject.id or name` (id preferred; name fallback for legacy
null-id entries). The registry deduplicates **paths**, not ids or fallback names, so two entries can
select the same identifier — which would make occurrences indistinguishable and undercount a
candidate's `n_projects`. A **duplicate selected identifier across the portfolio is a hard error**
(`SkillCoverageScanError`), rejected before any coverage computation.

**Failure semantics (fail-early).** The full report is assembled in memory and written **once** at
the very end, so any raised error aborts with a **nonzero exit**, **no partial report**, and any
`--output` target **untouched**. Two tiers, matching what each project is actually asked to do:

- **Every** registered project must have a loadable, valid `science.yaml` — the scan reads each
  project's `ProjectConfig` to determine enrollment. Missing/unreadable/invalid config →
  `SkillCoverageScanError`, abort. Such a project is **never** reclassified as `undeclared-domain`
  (undeclared is a state for a validly-loaded project, not a stand-in for a load failure).
- **Enrolled** projects are additionally canonically loaded (`load_project_sources`); a source/entity
  load failure there → abort. **Non-enrolled projects are not source-loaded at all**, so their entity
  integrity is *not* gated by coverage — that is `science validate`'s job. This narrows the parent
  design's blanket "fails canonical loading aborts" to the projects coverage actually loads, and is
  the reason an `out-of-domain`/`undeclared` project with malformed *entities* is still classified
  (not aborted): coverage never looks at its entities.

Coverage findings are **not** failures: a clean scan that surfaces `uncovered`/`covered-not-loaded`
occurrences still exits 0. (A future `--strict` exit-nonzero-on-findings flag is out of scope.)

## 7. Docs

Ship the enrollment convention page deferred from sub-plan 1 at
`docs/conventions/skill-coverage.md`: the `skill_coverage:` block, the `molecular-measurement`
domain, `enrolled`/`out-of-domain`/`undeclared` semantics, the enrolled⟹`entity_schema_version: 3`
rule, and the `science skills coverage` command + report schema. Link it from the user guide index.

## Data flow

```text
load_global_config().projects
    ├─ non-enrolled ──▶ ProjectEvidence(project, enrollment, <empty facts>)
    └─ enrolled ──load_project_sources──▶ ProjectSources(.entities, .skill_loads)
                         └─project_evidence──▶ ProjectEvidence(project, enrollment, term_usages, untagged_usages, plan_loaded_skills)
list[ProjectEvidence] + SkillOverlay + DataProductCatalog
    ──compute_coverage──▶ CoverageReport(coverage_occurrences, skill_reference_diagnostics, candidates)
        (non-enrolled ▶ OutOfDomainResult / UndeclaredDomainResult; enrolled ▶ the join + candidates)
    ──serialize_coverage_report──▶ canonical JSON ──▶ stdout | --output PATH
```

## Testing approach

- **`coverage.py` (pure, model):** each state in isolation — `uncovered`, `covered-not-loaded`,
  covered-and-loaded (emits nothing), `unmapped`, `unmapped-skill-reference`; **exact-term** on a
  parent/child term pair (broader-covering leaf does not cover the child); the score formula on
  known `(n_occurrences, n_projects)`; sibling inference (single-archetype consensus → that
  archetype, mixed → `indeterminate`, no-broader → `indeterminate`); discriminated-union `to_dict()`
  shapes; deterministic ordering under shuffled input; `out-of-domain` / `undeclared` single
  results; the non-catalog `data_product` hard error.
- **`evidence.py` (tool):** a synthetic `ProjectSources` (datasets with/without capabilities, plans
  with `dataset_usage` + grouped `skill_loads`) → expected `ProjectEvidence`; dangling
  `dataset_usage.ref` → hard error.
- **`scan.py` (tool):** a temp `config.yaml` registry pointing at temp project dirs
  (enrolled / out-of-domain / undeclared / load-failure) → expected report; a failing project aborts
  the scan and leaves `--output` untouched.
- **CLI:** `science skills coverage` via click `CliRunner` — stdout JSON parses; `--output` writes
  the file; a failing portfolio exits nonzero with no file written.

## Out of scope (deferred)

- `observation_level: project-demand` (epistemic q/h reachability fallback).
- A `--strict` flag that exits nonzero when findings exist.
- Additional enrollable domains beyond `molecular-measurement`.
- Any persistent overlay/report artifact, graph materialization, or `results/` convention.
- Skill prose generation (candidates remain evidence-backed pointers).
