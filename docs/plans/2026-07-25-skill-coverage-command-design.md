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

> **Population, not just schema.** Types and signatures below are code-verified; the **join edge is
> also population-verified**. `dataset_usage` is **unauthored on plans portfolio-wide** (0 of 351 plan
> entities; the field appears only on evidence-lines/papers/propositions), so the plan→dataset edge is
> `dataset_usage` **∪** `related: dataset:*` (120 refs across 11 projects, §2). `covers:` is sparse
> too — only 11 of 54 catalog terms are covered by any leaf — so `uncovered` occurrences + candidates
> are the command's dominant output by design (§4).

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
  shape is validated. `domain_enrollment(config, "molecular-measurement") ->
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
without the tool loading their sources. To keep the contradictory combination unrepresentable rather
than silently dropped, `__post_init__` **rejects** any non-empty fact tuple when `enrollment !=
EnrollmentStatus.ENROLLED` (a populated `out-of-domain`/`undeclared` instance is a construction-time
error, not evidence the join quietly ignores).

`project_evidence(project: str, sources: ProjectSources) -> ProjectEvidence` (enrolled projects
only) walks `sources.entities` once:

- **datasets:** for each `kind: dataset`, `parse_gen3_capabilities(model_extra["provided_capabilities"])`
  → the set of `data_product` term ids it provides (a dataset with none is *untagged*).
- **plans:** for each `kind: plan`, its **dataset edge = `dataset_usage[].ref` ∪ the `dataset:*`
  members of the typed `related: list[str]` field** (`entities.py:351`). Corpus reality (verified at
  `c06e6073`): `dataset_usage` is **unauthored on plans portfolio-wide** (0 of 351 plan entities),
  while `related: dataset:*` is how a plan actually names the datasets it concerns (120 refs across 11
  projects) — so the union is the only non-empty plan→dataset edge today, and it self-migrates as
  `dataset_usage` adoption grows. **The two edge sources are not equivalent:** `dataset_usage` is
  typed and carries `role`/`overlap`; a `related` ref is **mention-grade** — a bare association with
  no role/overlap, so it may name a dataset the plan critiques or rejects (e.g. mm30 `plan:0116`
  `related`-lists `dataset:gse234261` while its own verdict is `not-ready`). For a gap-detection
  instrument that is acceptable (a mention is enough to ask "was a covering skill loaded?"), but the
  report must not present a `related`-derived pair as a confirmed analysis — see the evidence note in
  §5.
  Both sides resolve through the **same reference-resolution semantics materialization uses**: build
  `ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases,
  archive_alias_tokens=sources.archive_alias_tokens, identity_table=build_identity_table(sources))`;
  obtain `dataset_usage` refs by reusing `usage_records_for_entity(plan, resolve_dataset_ref=<same
  callable `_add_dataset_usage_edges` passes>)`, and resolve each `related` `dataset:*` ref through
  the same callable. Authored refs are **not** canonical — a valid dataset **alias** or manual
  mapping resolves through the resolver, so a raw dict lookup would falsely flag it dangling. A ref
  the resolver cannot resolve is the hard error (not a dict miss). The union is de-duplicated (a
  dataset named by both `dataset_usage` and `related` is one edge). Group `sources.skill_loads` by
  `plan_id` → the canonical skill ids that plan loaded.
- Emit raw join facts (no overlay/catalog knowledge — that is the model's job). A dataset is
  **commons-owned** iff `sources.entity_source_adapters[canonical_id] == "commons-merged"` (the
  **owner's** adapter, `commons_sources.py:49/197`); everything else is project-owned. (Do **not** use
  `commons_overlay_paths` — it is populated only for *borrowers*, `identity_arbitration.py:472`, i.e.
  project-owned ids that commons merely annotates, so it classifies exactly backwards.) See §3:
  - `term_usages: tuple[TermUsage, ...]` — one `(plan_ref, dataset_ref, term, owned: bool)` per
    used-and-tagged pairing (project-owned **and** commons datasets, since either means the plan
    touches the term; `owned` lets the model gate the off-catalog hard error, §3);
  - `untagged_usages: tuple[DatasetUse, ...]` — one `(plan_ref, dataset_ref)` per used-but-untagged
    **project-owned** dataset that does **not** declare `capability_scope` (commons and
    intentionally-scoped datasets are excluded — not the project's mapping debt);
  - `plan_loaded_skills: tuple[PlanSkills, ...]` — `(plan_ref, skill_ids: tuple[str, ...])` for every
    plan that loaded at least one skill;
  - `unresolved_related_refs: tuple[UnresolvedRef, ...]` — `(plan_ref, ref)` for each `related:
    dataset:*` ref the resolver could not resolve (→ `dataset_reference_diagnostics[]`; a dangling
    `dataset_usage.ref` never reaches here — it already hard-errored).

**Dangling refs, by edge source.** A `dataset_usage.ref` that the resolver cannot resolve is a **hard
error** (a typed usage claim pointing nowhere is malformed evidence). An unresolvable `related:
dataset:*` ref is instead **demoted to a reported diagnostic** — `dataset_reference_diagnostics[]`
`{project, plan_ref, ref}` — not a scan abort: `related` is a loose hand-authored list, the same
stale-pointer class as the skipped registry entries. **Commons coupling (stated, not hidden):** these
refs resolve today (0 unresolvable across 11 projects) *only because* `include_commons=True` —
health-meta's three dataset refs resolve solely through the commons store, so an unsynced/missing
commons store would turn them unresolvable. Demoting `related` dangles to a diagnostic keeps that
external-state dependency from aborting the whole scan.

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

- **`unmapped`** — per `(project, dataset)` untagged usage: `{state, project, dataset_ref,
  observation_level, evidence_refs}`. Analysis activity present, dataset not tagged against any term.
  **Honors `capability_scope`:** a dataset that positively declares `capability_scope` asserts its
  empty `provided_capabilities` is *intentional and complete* (`capability_scope.py`; the
  `_scope_gate` in `validate/checks/dataset_capabilities.py` suppresses the missing-capabilities
  finding for exactly these), so a scoped dataset is **not** `unmapped` debt — it is skipped, matching
  the parent's "coverage checks WARN-first, honoring `capability_scope`" invariant.
- **`unmapped-skill-reference`** diagnostic — for every `(plan, skill_id)` in `plan_loaded_skills`
  where `overlay.get(skill_id) is None`: `{project, plan_ref, skill_id}` (canonical post-alias id —
  the id that failed to resolve). Coexists with any coverage state.

**Commons scoping.** `load_project_sources` runs with `include_commons=True` so a plan's `related`/
`dataset_usage` refs into shared commons datasets **resolve** (else they would abort as dangling).
But `unmapped` and the off-catalog hard error apply only to **project-owned** datasets — a dataset is
commons-owned iff `sources.entity_source_adapters[canonical_id] == "commons-merged"` (the owner's
adapter), and those are excluded. (The natural case — a dataset the project never declares, owned
outright by commons — has **no** borrower row and is **absent** from `commons_overlay_paths`, which
is exactly why that map is the wrong test.) A project is not blamed for commons's untagged or
malformed data, and one bad commons dataset cannot abort every enrolled project. A commons dataset a
plan actually uses still contributes its `term` to the plan's coverage (the project genuinely touches
that term). Concretely: health-meta's `dataset:reactome`, `dataset:gene-crosswalk-hgnc`, and
`dataset:ccle-proteomics-nusinow-2020` are commons-owned and carry no capabilities — under the
corrected discriminator they are **not** health-meta `unmapped` debt.

A **project-owned** (`owned=True`) used dataset whose `data_product` is **not** a catalog term is a
**hard error** (aborts the scan): coverage is the first consumer that joins datasets against the
closed catalog vocabulary, so it is the natural integrity gate — consistent with "closed vocabulary,
unknown = hard error". A **commons** (`owned=False`) term not in the catalog is **skipped** (not
classified, not aborted) — commons vocabulary integrity is commons's own pipeline's job, and this is
what keeps one bad commons dataset from aborting every enrolled consumer.

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
  distinct projects exhibiting it. Deterministic and monotone in both repeated use and cross-project
  breadth. With `n_occurrences ≥ 1` and `n_projects ≥ 1` the attainable range is **`[0.5, 1)`** (a
  lone single-project occurrence scores exactly `0.5`).
- `likely_archetype` = **catalog sibling inference**:
  - `parents` = `term.broader` (a catalog term may have several). If empty → `indeterminate`.
  - `siblings` = catalog terms `S != term` with `S.broader ∩ parents != ∅`.
  - `covered_sibling_archetypes` = the archetype of each overlay leaf that covers some sibling.
  - **exactly one** archetype in that set → use it; otherwise (zero, or ≥2 distinct) →
    `indeterminate`.
  - **Expected yield (documented, not a defect):** over the shipped catalog + inventory only ~4 of 54
    terms resolve to a single archetype (50 → `indeterminate`), and only 11 of 54 terms are covered
    by any leaf — so 43 are uncoverable portfolio-wide. The command's dominant signal is therefore
    `uncovered` occurrences + their candidates (which *is* the point — surfacing coverage gaps);
    `likely_archetype` is a conservative best-effort hint that is usually `indeterminate` by design.

No skill prose is generated — candidates are evidence-backed pointers only.

**Deferred ranking signal.** The parent's Prioritization section lists **feedback recurrence
(`concern`+`target`)** as a v1 signal; this sub-plan's score (which you selected as evidence-count +
sibling inference) does **not** consume it. Feedback recurrence is **deferred** — it is a separate
data source (feedback entities), out of scope here — and the parent section is annotated accordingly.

## 5. Report schema (`coverage-report`) — structural discriminated union

Every `evidence_refs[]` is a list of structured `{plan_ref, dataset_ref}` pairs (the occurrence
already carries `project`), so plan↔dataset pairing survives serialization. Distinct frozen
dataclasses per `state` so invalid field combinations are unrepresentable; each has a `to_dict()`
producing exactly its shape:

- `OutOfDomainResult` → `{state: "out-of-domain", project}` — no term, no observation_level.
- `UndeclaredDomainResult` → `{state: "undeclared-domain", project}`.
- `UnmappedOccurrence` → `{state: "unmapped", project, dataset_ref, observation_level,
  evidence_refs[]}` — `dataset_ref` is a first-class field (it *is* the occurrence's grain, not
  something to recover from inside `evidence_refs`).
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

`evidence_refs`/candidate `evidence` are **mention-grade** where a pair originates from a plan's
`related` edge (no `role`/`overlap`; the plan may even reject the dataset, §2) — the report is a
gap-detection instrument, and a pair is not a claim of a confirmed, successful analysis. (v1 does not
tag each pair with its edge source; if that distinction is later needed it is an additive field.)

`CoverageReport{scope, coverage_occurrences[], skill_reference_diagnostics[],
dataset_reference_diagnostics[], candidates[], skipped_projects[]}.to_dict()` → the report object.
`scope = {mode: "portfolio" | "single-project", project?}` records how the report was produced —
under `--project SLUG` (`mode: "single-project"`) every candidate necessarily has `n_projects = 1`
and a deflated `score`, so the mode must be legible in the otherwise byte-identical report shape.
`dataset_reference_diagnostics[]` = `{project, plan_ref, ref}` (unresolvable `related` dataset refs,
§2); `skipped_projects[]` = `{path, reason}` (§6). `serialize_coverage_report(report) -> str` =
`json.dumps(indent=2, sort_keys=True) + "\n"`. **Deterministic ordering** independent of scan order,
on **scalar** keys (never a list of dicts, which is unorderable):

- `coverage_occurrences` sorted by `(state, project, term or "", dataset_ref or "",
  tuple(sorted((e["plan_ref"], e["dataset_ref"]) for e in evidence_refs)))` — the trailing element is
  a tuple of string pairs, which orders; it disambiguates the `(project, dataset)`-grain `unmapped`
  entries that otherwise tie on `(state, project, "")`.
- `skill_reference_diagnostics` sorted by `(project, plan_ref, skill_id)`.
- `dataset_reference_diagnostics` sorted by `(project, plan_ref, ref)`.
- `candidates` sorted by `(-score, proposed_scope)`.
- `skipped_projects` sorted by `path`.

## 6. Command & portfolio scan (`science-tool`)

`science skills coverage [--output PATH] [--project SLUG]`, a new subcommand on the existing
`skills_group` (`skills_lint/cli.py`). `--project SLUG` restricts the scan to the single registered
project whose selected identifier is `SLUG` (unknown slug → hard error); combined with skip-and-
report (below) it lets a user run coverage even when an unrelated registered project is broken.
`scan_portfolio(config_path: Path | None = None, *, only: str | None = None) -> CoverageReport`:

1. `load_global_config(config_path)`. An **absent/empty registry** (no config file, or no `projects`)
   is a **hard error** — coverage over zero projects is a malformed request, not a valid empty
   report (no fail-open).
2. Per registered project: resolve root. A path that is **missing or lacks `science.yaml`** is
   **skipped** and recorded in `skipped_projects[]` (§6 failure semantics); otherwise load
   `ProjectConfig` (`project_config_path(root)`) and read
   `domain_enrollment(config, "molecular-measurement")`:
   - `out-of-domain` / `undeclared` → a `ProjectEvidence` carrying only `project` + `enrollment`;
   - `enrolled` → `load_project_sources(root, include_commons=True)`, `project_evidence(project,
     sources)`.
   Every non-skipped project contributes exactly one `ProjectEvidence` to the list.
3. Build the overlay (`build_skill_overlay(load_skill_inventory(), catalog)`) + catalog
   (`load_catalog()`), call `compute_coverage(projects, overlay, catalog)` — which assembles the
   coverage/diagnostic/candidate sections (non-enrolled single results and
   `dataset_reference_diagnostics[]` included); the scan attaches `skipped_projects[]` and sets
   `scope` (`{mode: "single-project", project: SLUG}` under `--project`, else `{mode: "portfolio"}`).
4. `serialize_coverage_report(report)` → stdout, or `--output PATH` file.

`project` identifier = `RegisteredProject.id or name` (id preferred; name fallback for legacy
null-id entries). The registry deduplicates **paths**, not ids or fallback names, so two entries can
select the same identifier — which would make occurrences indistinguishable and undercount a
candidate's `n_projects`. A **duplicate selected identifier across the portfolio is a hard error**
(`SkillCoverageScanError`), rejected before any coverage computation.

**Failure semantics (fail-early).** The full report is assembled and serialized in memory before any
write, so any scan/serialization error aborts with a **nonzero exit** and **no partial report**. The
`--output` target is left **untouched** on failure — and because a plain `write_text` truncates an
existing file before it can fail on I/O, the write itself is **atomic**: serialize to a
same-directory temp file, then `os.replace` onto the target (the repo's established atomic-output
pattern). A stale prior report is never left half-overwritten. Three outcomes, matching what each
project is actually asked to do (stale registry entries are *expected* — `registry/sync.py:42` skips
non-dir/no-`science.yaml` paths and `prune_missing_projects` exists precisely for this):

- **Skip (missing path):** a registered path that does not exist or has no `science.yaml` is
  **skipped** and recorded in `skipped_projects[]` `{path, reason}` — not silent, not a fallback, and
  not a coverage state. The scan continues and exits 0. (This is why the live `f1-revision3`
  stale-worktree entry no longer aborts the scan.)
- **Abort (present but invalid):** a path that **exists with a `science.yaml`** but is unreadable or
  has invalid config → `SkillCoverageScanError`, abort. Such a project is **never** reclassified as
  `undeclared-domain` (undeclared is a state for a validly-loaded project, not a stand-in for a load
  failure).
- **Enrolled** projects are additionally canonically loaded (`load_project_sources`); a source/entity
  load failure there → abort. **Non-enrolled projects are not source-loaded at all**, so their entity
  integrity is *not* gated by coverage — that is `science validate`'s job. This narrows the parent
  design's blanket "fails canonical loading aborts" to the projects coverage actually loads (and to
  present-but-invalid config), and is the reason an `out-of-domain`/`undeclared` project with
  malformed *entities* is still classified (not aborted): coverage never looks at its entities.

Coverage findings are **not** failures: a clean scan that surfaces `uncovered`/`covered-not-loaded`
occurrences still exits 0. (A future `--strict` exit-nonzero-on-findings flag is out of scope.)

## 7. Docs

Ship the enrollment convention page deferred from sub-plan 1 at
`docs/conventions/skill-coverage.md`: the `skill_coverage:` block, the `molecular-measurement`
domain, `enrolled`/`out-of-domain`/`undeclared` semantics, the enrolled⟹`entity_schema_version: 3`
rule, and the `science skills coverage` command + report schema. Link it from the user guide index.

## Data flow

```text
load_global_config().projects   (absent/empty registry ▶ hard error)
    ├─ missing path / no science.yaml ──▶ skipped_projects[] {path, reason}   (scan continues)
    ├─ non-enrolled ──▶ ProjectEvidence(project, enrollment, <empty facts>)
    └─ enrolled ──load_project_sources(include_commons=True)──▶ ProjectSources(.entities, .skill_loads)
                         └─project_evidence──▶ ProjectEvidence(project, enrollment, term_usages[owned], untagged_usages,
                                                               plan_loaded_skills, unresolved_related_refs)
                              (plan dataset edge = dataset_usage ∪ related:dataset:*, resolver-resolved;
                               owned = entity_source_adapters[id] != "commons-merged")
list[ProjectEvidence] + SkillOverlay + DataProductCatalog
    ──compute_coverage──▶ CoverageReport(scope, coverage_occurrences, skill_reference_diagnostics,
                                          dataset_reference_diagnostics, candidates)
        (non-enrolled ▶ OutOfDomainResult / UndeclaredDomainResult; enrolled ▶ the join + candidates)
    + skipped_projects[] + scope{mode,project?} ──serialize_coverage_report──▶ canonical JSON ──▶ stdout | --output PATH
```

## Testing approach

- **`coverage.py` (pure, model):** each state in isolation — `uncovered`, `covered-not-loaded`,
  covered-and-loaded (emits nothing), `unmapped`, `unmapped-skill-reference`; **exact-term** on a
  parent/child term pair (broader-covering leaf does not cover the child); the score formula on
  known `(n_occurrences, n_projects)` including the `0.5` floor for a lone occurrence; sibling
  inference (single-archetype consensus → that archetype, mixed → `indeterminate`, no-broader →
  `indeterminate`); discriminated-union `to_dict()` shapes; **deterministic ordering under shuffled
  input including several `unmapped` entries in one project** (the list-of-dicts sort-key regression);
  `out-of-domain` / `undeclared` single results; an **owned** off-catalog `data_product` → hard
  error, a **commons** off-catalog term → skipped (not aborted); a `capability_scope` dataset is
  **not** `unmapped`.
- **`evidence.py` (tool):** a synthetic `ProjectSources` (datasets with/without capabilities, plans
  with `dataset_usage` **and** `related: dataset:*` + grouped `skill_loads`) → expected
  `ProjectEvidence` — the **union** edge picks up a `related`-only dataset and de-dups one named by
  both; a **valid dataset alias / manual-alias** resolves (not flagged dangling); a dangling
  `dataset_usage.ref` → hard error, while a dangling **`related`** ref → a
  `dataset_reference_diagnostics` entry (no abort); the **commons discriminator** keys on
  `entity_source_adapters[id] == "commons-merged"` — a commons-**owned** dataset (adapter
  `commons-merged`, absent from `commons_overlay_paths`) is `owned=False` and excluded from
  `untagged_usages`, while a project-owned dataset that commons merely annotates (present in
  `commons_overlay_paths`) stays `owned=True` (the regression guard for the inverted discriminator);
  `ProjectEvidence.__post_init__` rejects facts on a non-enrolled instance.
- **`scan.py` (tool):** a temp `config.yaml` registry pointing at temp project dirs
  (enrolled / out-of-domain / undeclared / present-but-invalid / **missing path**) → expected report;
  a **missing / no-`science.yaml`** entry lands in `skipped_projects[]` and the scan exits 0; a
  **present-but-invalid** config aborts; an **absent/empty registry** → hard error; **duplicate
  selected identifiers** → hard error before computation; **`--project SLUG`** restricts to one
  project (unknown slug → hard error); an **enrolled** project whose sources fail to load aborts; a
  **non-enrolled project with malformed entities** is still classified **without** its sources being
  loaded; a failing project leaves an existing `--output` file byte-for-byte unchanged (atomic-write /
  untouched-on-failure); `--project SLUG` sets `scope.mode == "single-project"` in the report while
  the default sets `"portfolio"`.
- **structured evidence reproducibility (model):** rebuild a candidate's `(n_occurrences,
  n_projects)` purely from its serialized `evidence[]` triples and assert it yields the reported
  `score` — proving the evidence substantiates the score.
- **CLI:** `science skills coverage` via click `CliRunner` — stdout JSON parses; `--output` writes
  the file; a failing portfolio exits nonzero with no file written.

## Out of scope (deferred)

- `observation_level: project-demand` (epistemic q/h reachability fallback).
- **Feedback-recurrence ranking signal** (`concern`+`target`) — a separate data source; the score
  stays evidence-count + sibling inference (parent Prioritization annotated).
- A cross-project migration authoring typed `dataset_usage` on analysis plans (v1 reads the
  `related: dataset:*` edge instead; the union self-migrates as `dataset_usage` adoption grows).
- A `--strict` flag that exits nonzero when findings exist.
- Additional enrollable domains beyond `molecular-measurement`.
- Any persistent overlay/report artifact, graph materialization, or `results/` convention.
- Skill prose generation (candidates remain evidence-backed pointers).
