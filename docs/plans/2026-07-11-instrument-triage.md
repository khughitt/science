# Instrument triage — the classification behind the boundary guard

**Status:** Complete. Task 2b of the
[InstrumentResult convergence plan](2026-07-11-instrument-result-convergence-plan.md).

The guard's seed was **generated**, not transcribed: 46 violations across 10 modules.
This document rules on each one. It is the work order for Tasks 3–10.

## The line

An earlier draft used the bar *"is there an input whose absence would make an empty
return meaningless?"* That bar is right but hard to apply consistently, because it
invites speculation about hypothetical inputs. Reading the 46 bodies produced a
sharper, mechanical test that gives the same answers:

> **Does the helper do I/O, or resolve a user-supplied identifier?**
>
> - **Yes** → it is an **instrument**. Its empty return is a claim about the world,
>   and that claim can be wrong because the helper never ran.
> - **No** — it is a pure function of already-loaded arguments → it is **not an
>   instrument**. An empty return is a fact about its input, and a status surface
>   would be ceremony without safety (the design's non-goal).

The two sets say different things and the difference is load-bearing:
`_NOT_INSTRUMENTS` **claims the helper cannot be unwired**. It is not a parking lot.

An instrument with **no reachable unwired state** still migrates (`ok`/`empty` only) —
it does I/O, it is rendered as a finding, and it shares the read surface. A spurious
`unwired` is as dishonest as a spurious `empty`; not every instrument needs one.

## `_NOT_INSTRUMENTS` — 8 entries, each a claim that it cannot be unwired

| Helper | Why it cannot be unwired |
|---|---|
| `benchmark_catalog.py::coverage_summary` | `(rows: list[BenchmarkRow]) -> dict`. Pure aggregation over rows the **caller already fetched**. Zero I/O. Always returns all 6 facet keys, and `tasks` is pre-seeded, so it is never even empty. |
| `datasets_catalog.py::consumers_of` | `(fm: dict) -> list[str]`. Reads one key of a caller-supplied dict. The dataset ref is resolved **loudly upstream** (`cli.py:7245` exits 2 on a typo), so `[]` genuinely means "records no consumers". |
| `datasets_catalog.py::format_show` | `(scope, fm, body) -> list[str]`. A **renderer**: its list is display *lines*, not findings. Always ≥6 lines. Wrapping it would be a category error. |
| `graph/attention.py::format_attention_candidate` | Formats **one** candidate to a dict. Pure. Not a collection at all — it is flagged only because `dict` is in `_BARE_COLLECTIONS`, i.e. the detector being coarse, not a finding. |
| `graph/attention.py::weighted_sample_without_replacement` | Pure sampler over a caller-supplied `Sequence`. No I/O. `[]` iff `limit == 0` or the input was empty. |
| `graph/attention.py::reason_aware_sample_candidates` | Same: pure sampler, delegates to the above. |
| `graph/health.py::list_health_checks` | `() -> list[dict]`. **Takes no arguments.** A projection over the module constant `HEALTH_CHECKS` (16 hardcoded definitions). It has no input that could be absent, and its return is never empty. |
| `graph/store/validation.py::query_predicates` | `() -> list[dict]`. Literally `return list(PREDICATE_REGISTRY)`. Same reasoning. |

## `_DEFERRED_INSTRUMENTS` — EMPTY

The plan anticipated `coverage_summary` as a mapping-shaped instrument the row-shaped
type could not express, and built `_DEFERRED_INSTRUMENTS` so that deferral would block
the closeout rather than hide in `_NOT_INSTRUMENTS`.

**Reading the body dissolved the problem.** `coverage_summary` takes `rows` — it does no
I/O and cannot be unwired. It was never an instrument. Its caller (`cli.py:5546`) already
holds the `InstrumentResult` from `list_benchmarks`; the summary is a pure fold over
`.rows`. So the mapping never needs to pass through the type, no consumers change, and
the public `--format json` `payload["summary"]` shape is preserved.

The remaining known shape the type cannot express — the `validate_graph*` family's
`has_failures` channel — is **not in the guard's seed** (the detector was deliberately
narrowed to `tuple[list[T], str | None]`, which excludes `tuple[list[T], bool]`). It stays
deferred at the design level, not as a guard entry.

**The set exists and stays empty. That is the intended outcome, not a formality:** if a
later migration hits a shape the type cannot carry, the entry goes here and Task 11 fails
until it is paid off or the design is explicitly amended.

## The tuple precursor is a REASON channel — it maps cleanly

Three helpers return `tuple[list[T], str | None]`: `benchmark_sources`, `list_benchmarks`,
`list_datasets`. The second element is the **commons-unavailable notice**, set only when
`include_commons=True` and the commons registry read fails, while local rows still come
back. `list_datasets`' own docstring calls it *"graceful degradation"*.

That is exactly `InstrumentResult.reason` **on an `ok`/`empty` result** — the partial-input
caveat the design's four-state ruling anticipated. It is *not* `unwired`. This confirms the
narrowed detector: these three carry a reason string, whereas the `validate_graph*` family
carries an independent `has_failures` **bool**, which `status` cannot express.

## What the reading found that the plan did not predict

Three of these are worse than the silent-empty this design was written to stop. **A silent
empty withholds a finding; these manufacture one.**

1. **`query_gaps` fabricates a false positive** (`summary.py:754`). A center that is not in
   the graph resolves anyway (`_resolve_center_entity` mints a URIRef without ever consulting
   the graph), so `adjacency.get(center_uri)` is empty, `degree == 0`, and the first check in
   the row loop reports `structural_fragility(low_connectivity,degree=0)`. **A typo'd entity
   id does not return `[]` — it returns one confident row asserting the nonexistent entity is
   structurally fragile.**

2. **`query_evidence` manufactures an epistemic claim** (`queries.py:87`). A typo'd target
   scans for evidence pointing at a URI that appears nowhere, finds none, and reports that the
   claim has **no supporting or disputing evidence** — an affirmative statement about the
   literature, produced from a typo.

3. **`validate_inquiry_dataset` returns a vacuous PASS** (`inquiry.py:432`). When the inquiry
   was materialized into the shared `graph/knowledge` layer rather than a dedicated named
   graph, `inquiry_graph` becomes a **brand-new empty `Graph()`**, and every check —
   `boundary_reachability`, `no_cycles`, `unknown_resolution`, `orphaned_interior` — passes
   over zero data. **A structurally broken inquiry validates green because the validator was
   looking at nothing.**

Also worth recording:

- **`collect_invalid_entity_aspects` swallows a `FileNotFoundError`** (`health.py:1231`): if
  `science.yaml` — *the very catalog it validates against* — fails to load, it returns `[]`,
  i.e. "no invalid aspects found". An explicitly swallowed exception, which the repo's
  fail-early convention forbids outright.
- **9 of the 11 health collectors** return a silent `[]` when they could not scan.
  `load_project_sources` does **not** raise on an unscannable project — a missing
  `science.yaml` is defaulted, and `iter_entity_markdown`'s docstring says plainly *"Missing
  root yields nothing."* So a wrong `project_root` produces a clean bill of health.
  `collect_validation_findings` is the one that already does this right: it converts the
  failure into an **error finding** rather than an empty list. That is the pattern the other
  nine should follow through `unwired`.
- **The `science health` aggregator has the same disease at a higher level**
  (`health.py:648`): `_empty_check_results` pre-seeds every key with `[]`, so a check
  **deselected** by `--fast`/`--skip-check` is byte-identical in the report to a check that
  ran and found nothing. That is out of scope here but belongs in the health-render work
  (fb-2026-07-10-021).

## Preconditions to implement (the work order for Tasks 3–10)

`graph_not_found` is **not** among these: `_load_dataset` (`dataset.py:42`) already raises
`ClickException` on a missing graph file. That whole class of speculation is dead.

| Module | Helper | `unwired` code |
|---|---|---|
| `big_picture/knowledge_gaps.py` | `compute_topic_gaps` | `no_topic_entities`, `no_resolvable_topics` |
| `big_picture/validator.py` | `validate_synthesis_file` | `no_project_ids` |
| `big_picture/validator.py` | `validate_rollup_file` | `frontmatter_unreadable` |
| `graph/health.py` | `collect_unresolved_refs`, `collect_unregistered_ref_kinds`, `collect_identity_policy_findings` | `project_sources_empty` |
| `graph/health.py` | `collect_lingering_tags` | `scan_dirs_missing` |
| `graph/health.py` | `collect_legacy_task_type` | `tasks_dir_missing` |
| `graph/health.py` | `collect_agent_context_findings` | `agent_context_files_absent` |
| `graph/health.py` | `collect_invalid_entity_aspects` | `aspect_catalog_missing`, `entities_dir_missing` |
| `graph/health.py` | `check_dataset_anomalies` | `datasets_dir_missing`, `research_packages_dir_missing` |
| `graph/store/queries.py` | `query_evidence` | `target_not_in_graph` |
| `graph/store/queries.py` | `query_neighborhood` | `center_not_in_graph` |
| `graph/store/summary.py` | `query_gaps` | `center_not_in_graph` |
| `graph/store/inquiry.py` | `validate_inquiry_dataset` | `inquiry_graph_empty` |
| `graph/store/inquiry.py` | `list_inquiries_dataset` | `no_inquiry_graphs` |
| `graph/store/validation.py` | `diff_graph_inputs_dataset` | `manifest_unreadable`, `walk_set_empty` (Task 5) |
| `benchmark_catalog.py` | `benchmark_sources`, `list_benchmarks` | `datasets_dir_missing` |
| `datasets_catalog.py` | `list_datasets` | `datasets_dir_missing` |
| `datasets_catalog.py` | `reconcile_dataset_links` | `entities_dir_missing` |

**Instruments with NO unwired state — migrate `ok`/`empty` only, do not invent one:**
`collect_tooling_scaffold_findings` (absence of `pyproject.toml`/`.env` **is** the finding —
it returns *two* findings on an empty dir, so an empty return is unambiguous),
`collect_validation_findings` (already converts the failure into an error finding),
`query_claims` (`about` is a free-text search term, not an id — "no match" is a real answer),
`query_coverage`, `query_dashboard_summary`, `query_question_summary`,
`query_inquiry_summary`, `query_neighborhood_summary`, `query_uncertainty` (corpus scans with
no user-supplied identifier), and `query_project_summary` (always returns exactly one row).

## The three centre-resolution defects share ONE root cause

`_resolve_center_entity` (`identity.py:126`) **takes no graph argument**, so it *cannot*
check existence. It mints a well-formed URIRef from any string: a known CURIE prefix with a
garbage suffix, or a bare word (→ `project:concept/<slug>`). It is called by `query_gaps`,
`query_neighborhood`, `query_evidence`, and — outside this namespace —
`graph/store/cross_impact.py:208`, which has the same defect and is **not** covered by the
guard.

The codebase already knows how to do this correctly: `science entity neighbors`
(`cli.py:783`) calls `find_entity(...)` first and raises `EntityCommandError` on a bad ref.
The graph-query layer simply never adopted it. **Fix the resolver's callers with a graph
membership test** (`(uri, None, None) in graph or (None, None, uri) in graph`) rather than
patching each of the three call sites independently.

## Known gaps in this triage, stated rather than hidden

1. **`curate/inventory.py` produced ZERO violations** despite being in `INSTRUMENT_MODULES`.
   Not because it is safe — because `collect_inventory` returns `CurationInventory`, a
   Pydantic model, and the detector only flags **bare collections**. A model-shaped return
   with no status field evades the guard entirely. This is the annotation-level gap the
   guard's docstring admits, and it is exactly fb-2026-07-10-017 (the payload divergence),
   deliberately out of scope here. **The module is in the namespace so the guard covers its
   shape; the guard does not and cannot currently see this defect.**

2. **`benchmark_opportunities.py` is a consumer outside the namespace.**
   `load_opportunity_datasets` (`:1060`) calls `benchmark_sources` and **re-exports the same
   `tuple[list[T], str | None]` precursor**, threading `commons_notice` through five typed
   payloads. It is not in `INSTRUMENT_MODULES`, so the guard will not flag it — but Task 10
   must update it, and it inherits the same silent-empty defect.

3. **`consumers_of` has an unrelated bug**, recorded so it is not lost:
   `list(fm.get("consumed_by") or [])` on a **string** value (authored without a list) returns
   a list of individual **characters**. No `isinstance(..., list)` guard, unlike the defensive
   `isinstance(access, dict)` checks elsewhere in the same file. Out of scope; not an
   instrument defect.

4. **`query_neighborhood` has a second, weaker precondition:** `dataset.graph()` on an unknown
   named-graph URI **creates an empty graph** rather than raising, so a bogus `graph_layer`
   returns `[]` at library level. The CLI guards it with `click.Choice(GRAPH_LAYERS)`, so it is
   not reachable from the command line today — but the library contract is unguarded.
   Code: `unknown_graph_layer`, if Task 7 chooses to close it.
