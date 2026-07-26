# Context-budget slice 1b-3 — DEFERRED command audit

> **Status:** audit complete 2026-07-25. Classifies all 198 `DEFERRED` commands from
> slice 1a into their true disposition, per the program design
> ([`2026-07-24-agent-context-budget-program-design.md`](2026-07-24-agent-context-budget-program-design.md),
> §Slice 1b decomposition). Produced by an 11-way parallel per-callback read of every
> command. This doc is the SSOT the 1b-3 wiring sub-slices draw from.

## Method

Each command's Click callback was read to its actual emit call and classified by the
O(1)-vs-O(project) test: **does the number of output lines scale with the number of
records in the project?** A command whose output is a single confirmation / path / count
/ fixed field set is EXEMPT; one that emits a per-item list over a project-scoped
collection is WIRE. WIRE commands are tiered by *exposure*: doc-referenced (an agent
actually runs it in a session) is wired now; growable-but-unreferenced stays DEFERRED
with a sharpened reason (still guard-legal — DEFERRED satisfies the completeness guard).

## Summary

| Bucket | Count | Disposition |
|---|---:|---|
| EXEMPT — fixed-shape, cannot grow | 44 | move `DEFERRED`→`EXEMPTIONS` |
| WIRE — doc-referenced (risk set) | 56 | wire this slice, in grouped batches |
| WIRE — not doc-referenced | 92 | keep `DEFERRED`, sharpen growth reason |
| WRITE-AUDIT-LEAK — O(1) result + whole-corpus warning dump | 6 | summarize-by-default fix (see below) |
| **Total** | **198** | |

## Write-audit-leak (dedicated fix)

These commands advertise an O(1) confirmation but call `_validate_prospective_write(s)`
(`entities.py`) and echo **every pre-existing failing audit row in the corpus** on each
write — a context flood on the most-run write commands. `dataset verify-access` already
summarizes this by default (count + `--show-preexisting`); the rest do not. The fix is to
make them all summarize pre-existing warnings by default (count + escape), after which
they are genuinely EXEMPT. Not budget-wiring: truncating a write's own new warnings would
be wrong; the flood is specifically the *pre-existing* set.

- **`dataset add`** — src/science_tool/datasets/cli.py:349; The advertised 'created <id> -> <path>' confirmation line is O(1), but the warnings loop above it is a side-channel that scales with the WHOLE project's pre-exi
- **`dataset verify-access`** — src/science_tool/datasets/cli.py:447; By DEFAULT this command is effectively O(1) (one access-state line + a summarized warning count) -- only the opt-in --show-preexisting flag reintroduces the gro
- **`entities import`** — src/science_tool/entities_inventory_cli.py:504; No --format option; emit() hardcodes output_format="json". --save-plan writes the plan to a file but the full plan is ALSO always echoed to stdout via emit() re
- **`entity create`** — src/science_tool/entities_cli.py:46; The primary confirmation line ('Created <id> at <path>') IS O(1) -- the growable part is entirely the warnings loop, which is easy to miss by reading only the s
- **`entity edit`** — src/science_tool/entities_cli.py:124; Same shared whole-project-audit-warnings mechanism as entity create/note/entities import -- see entity create's notes. The success line ('Updated <id> at <path>
- **`entity note`** — src/science_tool/entities_cli.py:165; Not doc-referenced, but qualifies HIGH on the whole-project-set criterion alone (same shared warnings mechanism as entity create/edit and entities import -- see

## EXEMPT — reclassify to EXEMPTIONS (44)

| Command | Shape | Reason it cannot grow |
|---|---|---|
| `annotate ack` | — | single-annotation-ID status mutation (open->ack); output is one fixed confirmation line via _crud_invoke, no --format option at all. |
| `annotate dismiss` | — | single-annotation-ID status mutation (open->dismissed) via the shared _crud_invoke helper; output is one fixed confirmation line. |
| `annotate extract` | — | single-paper operation: payload is {written: int, skipped: dict-by-fixed-reason, grounding_dropped: int, source_text_hash_recorded: bool, note}; --check mode returns a single {status: changed/unchanged} field. No per-item annotation loop anywhere. |
| `annotate fix` | — | single-annotation-ID status mutation (open->fixed) via the shared _crud_invoke helper; output is one fixed confirmation line. |
| `annotate promote-prose-decomposition` | — | promotes exactly one --unit (required, singular); payload is {minted: int, linked: int, skipped: dict-by-reason, written: a fixed handful of paths (entity + sidecar)}. Written-path count does not scale with anything but is fixed per single-unit promotion. |
| `annotate pubtator` | — | single-paper (identifier) PubTator seeding; output is one optional note line plus one summary line with entity/relation written counts and a skip-count dict keyed by a small fixed set of skip reasons. |
| `annotate stats` | — | aggregated counts by_status/by_source/by_type; each dict's cardinality is bounded by a small fixed vocabulary (Status enum, the SOURCES registry, and the annotation-type enum), not by the number of annotations or sidecars scanned, even though the underlying scan (query.iter_sidecars(root)) covers the whole project. |
| `benchmark gap-calibration` | — | Payload is O(number of --project label=path flags the user supplies), not O(project record count): each project contributes exactly one calibration_summary object built by gap_calibration_summary(report, top=10), whose sub-lists (top_suggested_facets, top_matched_hint_facets, top_fallback_benchmarks, etc.) are capped at top=10 by construction (benchmark_opportunities.py:2445,2457,2476). Raw per-entity/per-gap rows from the underlying gaps_report() are never emitted -- only counts and top-10 lists. Growing the target project's entity/benchmark count does not add output lines. |
| `commons dataset build` | — | Prints exactly one line: `snakemake exited {exit_code}`. No --format/--json option exists on this command. The underlying `snakemake` subprocess (via subprocess.run with check=False) streams its own stdout/stderr directly to the terminal, not through click.echo, so it is outside this command's emitted payload. |
| `commons member-payload` | — | Resolves exactly one promoted virtual member (member_id) to its payload. Fixed set of top-level fields (member_id, parent_dataset, parent_slug, member_key, payload_kind, payload); text render prints 3 fixed lines. Does not enumerate a list of records that grows with corpus/project size. |
| `commons reference-graph resolve-member` | — | Resolves one (registry_id, member_key) pair to at most one GraphMemberMatch (or an 'unresolved' status record). Fixed set of output fields; text render is 3-4 fixed lines including an optional replaced_by list, which is a small per-member alias set, not a per-project/per-store collection. |
| `commons show` | — | Prints exactly one entity by canonical id (optionally merged with one named project's overlay). Fixed-shape record: frontmatter dict + fixed metadata fields for that single entity; does not enumerate a collection. |
| `dataset reconcile` | — | Diffs at most 3 fixed cached fields (license, update_cadence, ontology_terms) between ONE dataset entity's frontmatter and its ONE runtime datapackage.yaml; output is 0-3 drift lines (or 'in sync'/an error line), independent of project size. |
| `dataset show` | — | datasets_catalog.format_show() (line 703) renders a fixed ~8-10 field block (id/title/status/tier/origin/license/access/url/accessions/related/consumed_by) for the ONE resolved dataset entity, plus its own markdown body text appended as a single unit -- not a per-item list over a collection. |
| `datasets hydrate-worktree` | — | hydrate_worktree_data() iterates over `data_worktree.DEFAULT_DATA_DIRS` (line 7), a hardcoded 3-tuple (data/raw, data/processed, data/external) that is NOT exposed as a CLI option on this command (only --project-root/--source-root/--dry-run/--format are). Output is always exactly 3 rows regardless of project size. |
| `datasets sources` | — | available_adapters() enumerates the fixed, code-defined set of packaged adapter modules (arrayexpress, cbioportal, dryad, figshare, geo, physionet, semantic_scholar, sra, zenodo -- ~9 total); it grows only when the toolkit ships a new adapter, never with project or query size. |
| `discussions create` | — | Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings (emit_entity_warnings); count is bounded by that single entity's fields, not by project size. |
| `discussions show` | — | Renders one entity's fixed field set (id, kind, title, status, path, related refs, source_refs, body). related/source_refs/body length is bounded by that entity's own authored content, not by the number of entities in the project. |
| `doi lookup` | — | lookup_doi_metadata() (src/science_tool/doi.py:10-49) builds a hardcoded, fixed-key dict (doi, title, publisher, source, optionally issued, url -- at most 6 keys, all literal string keys in the function body) from the Crossref response; it does not echo back arbitrary/variable Crossref fields or author lists. Row count is capped by the function's own code, not by the DOI record or by project size -- this is 'N fixed fields for one entity', not a per-project-record list. |
| `entity sections` | — | Rows come from the KIND's fixed template/schema definition (Renderer().sections(kind) + read_effective_frontmatter_fields(default_profile_for_kind(kind))) -- a static, per-kind schema description, not per-entity project data. Row count does not change as entities of that kind are created, edited, or removed. |
| `entity show` | — | emit_entity_show() renders a fixed set of fields (id, kind, title, status, path, related, source_refs, body) for exactly the ONE entity resolved by `ref`; 'related'/'source_refs' are that one entity's own authored lists (small, author-bounded), not a project-wide scan. |
| `evidence-lines create` | — | Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings; bounded by the single created entity, not project size. |
| `evidence-lines show` | — | Renders one entity's fixed field set; bounded by that entity's own content, not project size. |
| `graph build` | — | Output is a handful of fixed confirmation lines (paths written, local-only/no-commons notices) plus a loop of 'Ontology suggestion' lines. That loop (suggest_ontologies, src/science_tool/graph/suggest.py:35) iterates the CODE-SHIPPED ontology registry (load_registry(), a fixed/small catalog), not the project's own entity/edge/task count -- so line count does not scale with project size even though the underlying entity scan does. |
| `graph predicates` | — | query_predicates() (src/science_tool/graph/store/validation.py:32) returns list(PREDICATE_REGISTRY) verbatim -- its own docstring says 'NOT an instrument: a module constant, no input to lack.' It is the fixed, code-shipped vocabulary of supported RDF predicates, entirely independent of any project's size. |
| `graph project-summary` | — | query_project_summary (src/science_tool/graph/store/summary.py:677) returns InstrumentResult.from_rows([...]) with exactly ONE row -- a single project-wide rollup (question_count, inquiry_count, claim_count, priority_score, avg_risk_score, etc., all fixed scalar fields). It internally scans all claims/questions/inquiries to compute those aggregates, but the OUTPUT cardinality is always 1. |
| `graph validate` | — | validate_graph_dataset (src/science_tool/graph/store/validation.py:54) appends a FIXED set of ~6 structural check rows (parseable_trig, provenance_completeness, causal_acyclicity, orphaned_nodes, patch_membership_convenience, empirical_run_resolution) regardless of project size -- each row's 'details' field aggregates a COUNT or first-offender string (e.g. '3 proposition/hypothesis entities missing prov:wasDerivedFrom') rather than emitting one row per violation. |
| `hypotheses create` | — | Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings; bounded by the single created entity, not project size. |
| `hypotheses show` | — | Renders one entity's fixed field set; bounded by that entity's own content, not project size. |
| `interpretations create` | — | Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings; bounded by the single created entity, not project size. |
| `interpretations show` | — | Renders one entity's fixed field set; bounded by that entity's own content, not project size. |
| `paper-fetch` | — | fetch_paper() returns one frozen FetchResult dataclass (status, source, metadata dict, tiers_attempted, pdf_path, text_path, access_hint, errors) describing a single fetch attempt for the one DOI/URL/PMID/PMCID/arXiv id passed in. tiers_attempted/errors are bounded by the hardcoded fetch-strategy ladder in paper_fetch.py (~12 literal tier names: europepmc:*, crossref, unpaywall, arxiv, biorxiv, crossref_text_mining, unpaywall_pdf, europepmc:abstract) -- a fixed algorithm-bounded scaffold, not a per-project-record list. |
| `project artifacts diff` | — | Unified diff between ONE named artifact's canonical and installed bytes; line count is bounded by that single template file's own size, not by any project record count. The registry it draws NAME from currently ships exactly 1 artifact (validate.sh) and is toolkit-defined, not project-scoped. |
| `project artifacts exec` | — | os.execv() replaces the current process with the canonical artifact's own binary; the science CLI itself emits nothing before the exec. Whatever the exec'd process prints is outside this command's control. |
| `project artifacts list` | — | One line per artifact TYPE in the toolkit's static registry.yaml (currently exactly 1: validate.sh). The registry is toolkit-defined and grows only when Science ships new managed-artifact types across releases -- it does not scale with any single project's entity/task/dataset count. |
| `project artifacts update` | — | Fixed confirmation for ONE named artifact update: from-version -> to-version, commit status, backup path. Migration step names, if any, are joined onto a single comma-separated line (', '.join(...)) rather than emitted one-per-line, so output stays O(1) regardless of migration count. |
| `project resolve-refs` | — | Output is one line per --query argument the CALLER supplies (a repeatable option), not per record in the project. An ambiguous single query surfaces a candidate list drawn from that one query's id/title-slug collisions, still gated on caller-chosen query count, not a corpus-wide dump. |
| `propositions create` | — | Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings; bounded by the single created entity, not project size. |
| `propositions show` | — | Renders one entity's fixed field set; bounded by that entity's own content, not project size. |
| `questions create` | — | Echoes exactly one 'Created <id> at <path>' line plus the created entity's own validation warnings; bounded by the single created entity, not project size. |
| `questions show` | — | Renders one entity's fixed field set; bounded by that entity's own content, not project size. |
| `tasks block` | — | single task-state-change confirmation: one line naming the task and echoing back the user-supplied --by refs joined with commas; count of refs is bounded by how many --by options the user typed on this one invocation, not by project size |
| `tasks show` | — | renders ONE task's fixed fields (task.model_dump()) plus that same task's own blocked_by_readiness list -- O(1) in project size: the readiness list is bounded by the single task's own blocker count, never by total tasks/entities in the project |
| `verdict parse` | — | parses exactly ONE named file argument into a single ParseResult document; its internal tokens/claims/interpretations/warnings are bounded by that one file's content, not by project scale (no directory walk) |

## WIRE — doc-referenced, wire this slice (56)

| Command | Shape | --output? | Doc reference |
|---|---|---|---|
| `annotate list` | ROWS | no | agents/paper-annotate.md:25 |
| `annotate promote` | ROWS | no | commands/synthesize-propositions.md:21 |
| `annotate synthesize` | REPORT | no | commands/synthesize-propositions.md:26 |
| `benchmark list` | REPORT | no | commands/catalog-benchmarks.md:38 |
| `big-picture resolve-questions` | ROWS | no | commands/big-picture.md:39 |
| `big-picture validate` | ROWS | no | commands/big-picture.md:246 |
| `book-split` | ROWS | no | commands/review-books.md:38 |
| `commons promote dataset` | REPORT | no | commands/catalog-datasets.md:278 |
| `dag audit` | REPORT | no | commands/dag-audit.md:31 |
| `dag validate` | REPORT | no | commands/dag-audit.md:91 |
| `dataset prioritize` | REPORT | no | commands/catalog-datasets.md:45 |
| `dataset reconcile-links` | ROWS | no | commands/catalog-datasets.md:51 |
| `dataset register-run` | ROWS | no | commands/find-datasets.md:235 |
| `datasets download` | ROWS | no | skills/pipelines/snakemake.md:58 |
| `datasets files` | ROWS | no | commands/find-datasets.md:117 |
| `datasets search` | ROWS | no | commands/find-datasets.md:59 |
| `datasets validate` | ROWS | no | skills/pipelines/snakemake.md:361 |
| `entity rotation` | ROWS | no | commands/curate.md:32 |
| `explore-ideas apply` | REPORT | no | commands/explore-ideas.md:396 |
| `explore-ideas gaps` | REPORT | no | commands/explore-ideas.md:444 |
| `explore-ideas resolve-anchors` | REPORT | no | commands/explore-ideas.md:190 |
| `feedback add` | ROWS | no | commands/search-literature.md:161 |
| `feedback regression-candidates` | ROWS | no | commands/status.md:156 |
| `feedback targets` | ROWS | no | commands/post-mortem.md:58 |
| `graph attention-rank` | ROWS | no | commands/review.md:33 |
| `graph attention-sample` | ROWS | no | commands/status.md:73 |
| `graph audit` | ROWS | no | commands/create-graph.md:29 |
| `graph dashboard-summary` | ROWS | no | commands/big-picture.md:36 |
| `graph diff` | ROWS | no | commands/update-graph.md:34 |
| `graph gaps` | ROWS | no | commands/big-picture.md:55 |
| `graph inquiry-summary` | ROWS | no | commands/big-picture.md:34 |
| `graph neighborhood-summary` | ROWS | no | commands/big-picture.md:38 |
| `graph question-summary` | ROWS | no | commands/big-picture.md:33 |
| `graph rehoming-debt` | ROWS | no | commands/big-picture.md:224 |
| `graph uncertainty` | ROWS | no | commands/big-picture.md:37 |
| `inquiry export-pgmpy` | DOCUMENT | yes | commands/critique-approach.md:94 |
| `inquiry list` | ROWS | no | commands/find-datasets.md:24 |
| `inquiry show` | REPORT | no | commands/critique-approach.md:60 |
| `inquiry validate` | REPORT | no | commands/review-pipeline.md:28 |
| `peers list` | REPORT | no | commands/status.md:25 |
| `project index` | ROWS | no | commands/next-steps.md:32 |
| `project topic-coverage` | REPORT | no | commands/explore-ideas.md:88 |
| `qa-audit` | ROWS | yes | templates/workflow-run.md:7 |
| `refs check` | REPORT | no | skills/literature/citation-discipline.md:41 |
| `research-package build` | ROWS | no | skills/pipelines/snakemake.md:437 |
| `research-package validate` | REPORT | no | skills/research-package/research-package-spec.md:64 |
| `skills lint` | ROWS | no | skills/meta/skill-taxonomy.md:94 |
| `sync projects` | ROWS | no | commands/sync.md:16 |
| `sync rebuild` | REPORT | no | commands/sync.md:71 |
| `sync run` | REPORT | no | commands/sync.md:34 |
| `sync status` | REPORT | no | commands/sync.md:15 |
| `tasks archive` | ROWS | no | commands/status.md:145 |
| `tasks blockers` | ROWS | no | commands/tasks.md:152 |
| `tasks fix-blockers` | ROWS | no | commands/tasks.md:101 |
| `tasks summary` | REPORT | no | commands/review-tasks.md:19 |
| `wander` | REPORT | yes | commands/wander.md:33 |

## WIRE — not doc-referenced, keep DEFERRED with sharpened reason (92)

| Command | Shape | Growable collection |
|---|---|---|
| `annotate apply-proposition-reconciliation` | REPORT | one row per canonicalization action taken (payload['actions']) plus one row per changed/noop file path (payload['changed_paths']/['noop_paths']), all derived from build_reconciliation_report(project_root) which is ALWAYS whole-project (no --proposition/--source scoping option exists on this command, only --input review file(s) and optional --action filter) |
| `annotate apply-proposition-resynthesis` | REPORT | one path per changed_paths/noop_paths entry when applying a single validated resynthesis draft -- bounded to the one draft's replacement propositions and reassigned annotations (one canonicalization group), not the whole project |
| `annotate apply-prose-promotion-plan` | REPORT | one path per written entity/sidecar when applying a batch prose-promotion plan (payload['written']) -- bounded to however many units were selected when the plan file was built (plan-prose-promotions --unit, repeatable), not a project-wide scan |
| `annotate archive-superseded-propositions` | REPORT | one row per superseded-proposition archive candidate across the whole project (payload['candidates'], looped in _render), each with a nested blockers/inbound_live_refs list |
| `annotate audit` | REPORT | one entry per markdown file scanned/modified across the whole project (payload['files'], looped in _emit_audit_table), from _collect_audit_markdown_files(root) which walks the entire tree under --root (default '.') |
| `annotate build-prose-health` | REPORT | one finding per prose-health issue across the whole project's declared prose sources/decomposition units (payload['findings'], built in prose_health.py:143-154 across all sources, incl. _undeclared_grounding_findings) |
| `annotate check-prose-decomposition` | ROWS | one row per decomposition unit (report.rows, looped directly in _render) for the single --source specified -- bounded to one paper/source's decomposition, not the whole project |
| `annotate cross-paper-evidence` | REPORT | when --source is omitted (the project-wide branch): one row per proposition with derived cross-paper literature evidence (payload['propositions'], cross_paper_evidence.py:247/254, looped in _render); when --source is given: one row per evidence unit for that single proposition (bounded) |
| `annotate ground-prose-decomposition` | REPORT | one row per decomposition unit's grounding result (payload['units'], prose_grounding.py:113) for the single --source specified -- bounded to one paper/source, not the whole project |
| `annotate ingest-prose-decomposition` | REPORT | one fingerprint per stale unit in the single ingested artifact (payload['stale'] = report.stale_fingerprints) -- bounded to one source's decomposition artifact, not the whole project |
| `annotate lift-tokens` | REPORT | one entry per markdown file with lifted/removed marker tokens across the whole project (payload['files'], from _collect_lift_markdown_files(root) which walks the entire tree under --root, default '.') |
| `annotate plan-proposition-reconciliation` | REPORT | one row per canonicalization action derived from the reviewed --input judgment file(s) (payload['actions'], looped in _render) against build_reconciliation_report(project_root), which is ALWAYS whole-project (no scoping flag exists) |
| `annotate plan-prose-promotions` | DOCUMENT | one row per --unit ID passed on the command line (multiple, required) -- bounded by the caller's explicit selection, not by a project-wide scan |
| `annotate reconcile-propositions` | REPORT | one row per same-claim candidate and one row per factorization disagreement (payload['same_claim_candidates']/['factorization_disagreements'], looped in _render), plus a 'faults' list -- whole-project scope under --all, which is one of the three mutually-exclusive, user-selectable scopes (--all / --proposition / --source) |
| `annotate record-proposition-reconciliation-decisions` | REPORT | one blocker per decision-recording problem (payload['blockers'], looped in _render), built from build_reconciliation_report(project_root) (unconditional, whole-project, no scoping flag) plus the input action-plan file |
| `annotate resynthesis-draft-context` | DOCUMENT | context-packet entries (propositions/annotations referenced) for the single resynthesis draft passed via --input -- bounded to one prior reconciliation action's replacement group, not the whole project |
| `annotate scaffold-proposition-resynthesis` | REPORT | draft['input_annotations'] (and nested statement/candidate lists) for the single selected reconciliation action (--action, or the plan's default), bounded to one canonicalization group's propositions/annotations, not the whole project |
| `annotate validate-proposition-reconciliation` | REPORT | one entry per incomplete same-claim candidate (payload['review_incomplete'], built by iterating report.same_claim_candidates in validate_review_doc, proposition_reconciliation.py:857-863) plus one entry per validation error (payload['errors']) -- report = build_reconciliation_report(project_root) is unconditional/whole-project (no scoping flag on this command) |
| `annotate validate-proposition-resynthesis` | REPORT | errors/warnings lists plus expected_annotation_targets / expected_source_refs_by_replacement dicts (proposition_resynthesis.py:280-303) for the single --input draft -- bounded to one prior reconciliation action's replacement propositions and reassigned annotations, not the whole project |
| `annotate validate-prose-decomposition-artifact` | ROWS | one row per decomposition unit (report.rows, looped directly in _render) for the single offline artifact_path being validated -- bounded to one document's decomposition, not the whole project |
| `annotate verify` | REPORT | one row per drift issue (broken/degraded/fuzzy/source-missing/parse-error annotation) across the whole project's *.anno.trig sidecars (payload['issues'], looped in _emit_table) -- --root defaults to '.' and walks the entire tree |
| `autonomy path-gate` | REPORT | one denial line per denied path/field over the run's base..head change set (evaluate() -> verdict.denials) |
| `belief profile` | ROWS | one row per belief-bearing entity (proposition/hypothesis/mechanism) in the whole knowledge graph that passes the --kind/--label/--all filters |
| `benchmark gaps` | REPORT | one row per project entity's benchmark coverage gap (payload['benchmark_gaps']), plus an optional per-entity 'evidence_report' section (--evidence-report) -- both scoped over ALL project entities by default (whole project) unless --entity narrows to one |
| `benchmark hint-candidates` | REPORT | one row per candidate term surfaced from gap evidence across ALL project entities (payload['hint_candidates']), plus a 'summary' section |
| `benchmark opportunities` | REPORT | one row per matched benchmark-opportunity pair (payload['matched_opportunities']) across ALL project entities x catalog datasets by default (whole project) unless --entity narrows to one, plus an optional --calibration-report section |
| `benchmark test-triage` | REPORT | payload['buckets'] holds 5 growable lists (run-now, stage-next, metadata-needed, blocked-or-reference, fallback-diagnostic), each one row per benchmark test plan across ALL project entities by default (whole project) unless --entity narrows to one; text rendering slices each bucket to 10 rows but the emitted JSON payload carries the full unsliced lists |
| `benchmark tests` | REPORT | one row per benchmark test plan (payload['benchmark_tests']) across ALL project entities by default (whole project) unless --entity narrows to one, plus a 'summary' section |
| `big-picture cluster-digests` | REPORT | payload['digests'] has one entry per cluster-digest entity in the project, and payload['member_to_digest'] has one entry per archived/consolidated member entity across the WHOLE project; --deep additionally attaches an index-only member summary list per digest |
| `big-picture knowledge-gaps` | ROWS | one row per topic-coverage knowledge gap (compute_topic_gaps) over the whole project's question/topic corpus |
| `commons dataset status` | REPORT | one array entry per declared datapackage.yaml resource path, split into outputs_present/outputs_missing, for the single dataset named by <slug> |
| `commons dataset validate` | REPORT | one row per DatasetPackageFinding (missing files, invalid datapackage/snakefile issues, tracked-payload files found via dataset_dir.rglob('*'), placeholder-resource entries) within the single dataset package named by <slug> |
| `commons find` | ROWS | one record per commons entity of the given entity_type (dataset/paper/topic/theme) matching the optional --tag/--ontology/--year/--slug-glob filters, over the WHOLE commons store (CommonsQuery(root).find, no default limit) |
| `commons index rebuild` | REPORT | one error entry per commons entity that failed to index, scanned across the WHOLE commons store (RegistryBuilder(root, adapter).rebuild() walks filesystem state for all entities) |
| `commons inventory` | DOCUMENT | the inventory_v2 document for the WHOLE commons store (build_commons_inventory(), per docstring 'the whole commons store') |
| `commons list` | ROWS | one row per commons entity indexed in the WHOLE commons store (CommonsQuery(root).list(), no filters, no limit) |
| `commons promote paper` | REPORT | one summary line per plan.decisions entry (one per unique paper slug being promoted, each with nested rename/overlay/completeness-gap lines), across ALL matching papers discovered from the named --from project(s) with no default --limit -- plus up to 5 (+ 'and N more') failed candidates |
| `commons promote theme` | REPORT | one summary line per plan.decisions entry (one per unique theme slug being promoted) across all matching themes discovered from the named --from project(s), same _promote_kind_cmd code path as promote paper |
| `commons promote topic` | REPORT | one summary line per plan.decisions entry (one per unique topic slug being promoted) across all matching topics discovered from the named --from project(s), same _promote_kind_cmd code path as promote paper |
| `commons validate` | REPORT | default mode: one error/warning row per commons entity found invalid, scanned across the WHOLE commons store (CommonsValidator(...).validate(type=entity_type, slug=slug), both filters optional and unset by default); --project mode: one error/warning row per overlay file in the single named project (validate_project_overlays) |
| `dag apply-workbench` | REPORT | one line per changed_paths entry produced by compiling ONE reviewed workbench YAML file (plus fixed summary counts: rows/propositions/evidence_lines) |
| `dag workbench` | DOCUMENT | unified diff lines between the committed workbench YAML and its recompiled canonical form, for ONE --check file |
| `dataset capability-pairs` | ROWS | one row per distinct observed capability shape (dataclasses.asdict(ObservedShape)) across the enumerated corpus. --project-root scans EVERY entity under entities/ (dataset_prioritize._iter_entity_frontmatter); --commons-root scans EVERY commons datasets/*/entity.md. --file is bounded to one file. |
| `dataset consumers` | ROWS | one line per consumer ref in the single resolved dataset's `consumed_by` list (datasets_catalog.consumers_of). |
| `dataset identity resolve` | ROWS | one 'updated/unchanged <id> identity_context resolution=... [stamped]' line plus its resolution messages, per dataset entity matched by REF. `_dataset_paths` (datasets_identity.py:53) treats REF as a glob when it contains wildcard characters, so `dataset identity resolve '*'` iterates and rewrites EVERY entity under entities/datasets/. |
| `dataset list` | ROWS | one table row per dataset entity in the project (datasets_catalog.list_datasets), optionally unioned with every commons dataset record via --commons. |
| `dataset stochasticity` | REPORT | one line per stochastic step in the ONE dataset's inherited provenance/lineage chain (StochasticityReport.stochastic_steps, rendered in datasets_stochasticity_format.render_human/render_json); dataset_id/run_id/seed_policy_kind/deterministic_step_count are fixed fields. |
| `datasets infer-schema` | ROWS | one diff row per changed field (render_diff_rows) plus one review-recommendation row per flagged column (render_report_rows), both bounded to the ONE named resource's field count within the ONE datapackage. |
| `datasets qa` | REPORT | one outcome line per resource in the ONE datapackage (science_qa.runner.PackageRunResult.outcomes), plus a fixed package-summary line. |
| `entities archive` | REPORT | report['candidates'] = one entry per live entity whose status matches the archive-status sweep (default: every superseded/archived entity project-wide, or the --id/--ids-from allowlist), each carrying its own inbound_live_refs list; report['applied']/['skipped'] scale the same way once --apply runs |
| `entities audit-identifiers` | REPORT | two parallel flat lists, 'missing_canonical_ids' and 'invalid_canonical_ids', one entry per markdown file anywhere under the project root (project_root.glob("**/*.md"), excluding templates/) that fails the id check -- a whole-project filesystem sweep, not scoped to entities/ |
| `entities consolidate apply` | REPORT | report['members']/['destinations']/['applied']/['skipped'] = one entry per member entity of the ONE named cluster-digest being consolidated (consolidates_targets() reads the digest's own sci:consolidates relations, not a corpus scan) |
| `entities consolidate scaffold` | REPORT | report['members'] echoes back the comma-separated --members ids the caller typed on the command line (list(member_ids)); it is not derived from a project scan |
| `entities generate-decisions` | DOCUMENT | one full markdown section (## heading + entire body) per DecisionOwner entity under entities/decision/*.md, for the WHOLE project's decision population -- read_decision_owners() globs the whole decision_dir and render_decisions_view() emits every one, unfiltered |
| `entities mark-superseded` | REPORT | report['chains']/['non_linear']/['to_mark']/['to_repair']/['invalid_relations']/['unbacked_inverses']/['archived_targets']/['unmanaged_targets'] are ALL derived from build_supersedes_graph() over the WHOLE project corpus; per mark_superseded()'s own docstring 'Chain derivation and graph validation remain corpus-wide: the allowlist narrows what is WRITTEN and REPORTED, never what is CHECKED' -- so even with --id/--ids-from, several of these lists stay whole-project scale |
| `entities unarchive` | REPORT | report['candidates']/['applied']/['skipped'] = one entry per id in the explicit positional IDS argument list the caller typed; unarchive_entities() only iterates that list, no corpus scan |
| `entity field-inventory` | ROWS | one row per DISTINCT authored frontmatter key observed across every markdown file of the given --kind under entities/ (field_inventory() in field_inventory.py Counter-scans the whole kind population); row count scales with vocabulary diversity (including stray/typo keys), not directly with entity count, so growth is real but much slower than a per-entity list |
| `entity migrate-hypothesis` | ROWS | default invocation (no --preflight-all) is O(1): 'click.echo(f"{verb} {len(paths)} hypotheses")' -- only a count. Under --preflight-all, one 'ok <root> (<n> hypotheses)' line is printed per entry of the operator-authored --manifest JSON roster, and on failure every failing root's exception text is joined into one ClickException message |
| `entity migrate-specs` | REPORT | under --format json, emit() dumps the full report dict verbatim, including report['migrated'] -- one entry per legacy/loose spec doc canonicalized in this pass, a whole-project sweep of every legacy spec under the project (migrate_specs.migrate() canonicalizes ALL of them, not a subset) |
| `entity neighbors` | ROWS | one (subject, predicate, object) row per graph edge within `--hops` of the target entity, already hard-capped by the callback itself at limit=200 rows (query_neighborhood(..., limit=200)) |
| `entity remove` | ROWS | _emit_entity_removal_plan() prints one line per EntityReferenceHit in plan.safe_hits and one per plan.manual_hits; plan_entity_removal() (entities.py:1394) builds these by scanning EVERY file under the project root (_iter_reference_scan_files(project_root)) for text mentions of the target entity's id/slug/path -- a whole-project reference scan, not bounded to the one entity being removed |
| `entity status-inventory` | ROWS | one row per hypothesis entity in the WHOLE project -- inventory(Path.cwd(), adjudication=decisions) enumerates every hypothesis for the lifecycle/verdict-split plan; meta already reports total/deterministic/refused counts alongside the full row list |
| `evidence-lines list` | ROWS | one row per evidence-line entity in the project (list_entities(kind='evidence-line') over the whole project) |
| `explore-ideas backfill-lens-views` | ROWS | one click.echo line per entity that received a backfilled lens_view, drawn from the applied-candidate set of ONE exploration report |
| `feedback report` | REPORT | a markdown report (render_report) grouped by concern -> target -> one bullet per matching feedback entry, across ALL entries in the store matching the (optional) status/project/concern filters -- default status=None means every entry regardless of status |
| `feedback show` | DOCUMENT | the `occurrences` list embedded in the YAML dump of ONE feedback entry (one occurrence per historical filing/merge of that entry; FeedbackEntry.recurrence == len(occurrences)) |
| `feedback triage` | ROWS | one row per (concern,target) triage group (or per near-duplicate cluster in --cluster/json mode) across ALL open feedback entries in the store, each group additionally expanding to one line per member entry in the default text-render path |
| `graph belief-basis` | ROWS | in --compare mode: one 'MOVED <id>: ...' line per pre-existing entity whose belief basis changed, up to the whole graph's entity count (compare_bases over capture_basis rows, src/science_tool/graph/belief_basis.py); --out/capture mode instead prints a single one-line summary ('captured N entities -> path') |
| `graph claims` | ROWS | one row per Proposition whose text matches the free-text --about term (query_claims, src/science_tool/graph/store/queries.py:80), capped at --limit default 200 |
| `graph coverage` | ROWS | one row per Concept/Variable entity across the WHOLE knowledge+causal graph (query_coverage, src/science_tool/graph/store/queries.py:723), unconditional -- no scoping argument, capped at --limit default 200 |
| `graph cross-impact` | REPORT | the payload's 'rows' list -- one row per dependent proposition supporting/disputing one --target_ref (query_cross_impact, src/science_tool/graph/cross_impact.py:51), capped at --limit default 200; payload also carries fixed scalar fields (target, target_text, scope, scope_reason) |
| `graph evidence` | ROWS | one row per support/dispute evidence unit for one --target_ref (a claim, or aggregated across a hypothesis's linked claims) (query_evidence, src/science_tool/graph/store/queries.py:112), capped at --limit default 200 |
| `graph export-json` | DOCUMENT | the entire exported graph payload (all entities/edges via export_graph_payload, plus optional --overlay causal/evidence), dumped whole with no truncation and no --limit option |
| `graph neighborhood` | ROWS | one row per subject/predicate/object triple within --hops of a required --center argument (query_neighborhood, src/science_tool/graph/store/summary.py:22), capped at --limit default 200 |
| `graph propagate-freshness` | ROWS | one row per entity carrying a freshnessState triple in the in-memory-rebuilt graph, across the WHOLE project (propagate_freshness_in_memory, src/science_tool/graph/freshness.py:407); no --limit/--top option at all |
| `graph scan-prose` | ROWS | one row per markdown file with ontology annotations, recursively under the caller-supplied DIRECTORY argument (scan_prose, src/science_tool/prose.py:25); no --limit option |
| `graph viz` | DOCUMENT | a single Graphviz DOT text blob whose length scales with the number of nodes/edges in the selected --layer (default 'graph/knowledge', the WHOLE layer with no --center) or, if --center is given, the --hops neighborhood (build_graph_dot, src/science_tool/graph/store); capped only by --limit default 200 edges |
| `hypotheses list` | ROWS | one row per hypothesis entity in the project (list_entities(kind='hypothesis') over the whole project) |
| `inquiry export-chirho` | DOCUMENT | generated ChiRho/Pyro scaffold script text (one line per node/edge/CPD block) for ONE causal inquiry's compiled subgraph |
| `markers scan` | REPORT | one hit line per annotation-token occurrence found scanning the whole project's markdown tree (plus one summary count line per distinct token) |
| `patch check` | ROWS | one line per stale patch-membership diff (missing/unexpected patch->member pairs) comparing the recorded graph.trig against the re-derived expected graph, across ALL patch definitions and ALL their members in the project |
| `patch explain` | ROWS | one line per warning plus one line per derived membership record, scoped to the single named patch_id passed as an argument |
| `peers check` | ROWS | one row per peer-validation issue across all peers declared in science.yaml's `peers:` list |
| `project verify` | REPORT | verdict_json(result)['against']['source']['differ'/'absent'] and ['payloads']['differ'/'missing'/'extra'] -- one entry per tracked source file or data payload that differs/is missing/is extra between the serialized bundle and a live checkout, via the optional --against flag (science_tool/project_package/verify.py:186 _against_json). Scales with total project source+payload file count. |
| `propositions list` | ROWS | one row per proposition entity in the project (list_entities(kind='proposition') over the whole project) |
| `search` | ROWS | one row per matching entity returned by search_archive() over the whole archive index |
| `skills coverage` | REPORT | CoverageReport.to_dict() (model/src/science_model/skill_coverage/coverage.py:277) -- coverage_occurrences + skill_reference_diagnostics + dataset_reference_diagnostics + candidates + skipped_projects, computed by scan_portfolio() (src/science_tool/skills_coverage/scan.py) across every ENROLLED project in the registered global portfolio, not just one project |
| `skills sources check` | REPORT | three independently-growable lists from check_sources() (skills_lint/cli.py:168): 'sources' (one per declared id in sources.yaml across the --root tree), 'refs' (one per leaf->source citation, filtered to unresolved in text mode but full in JSON), 'leaf_errors' (one per skill file with a malformed sources field) -- all scoped to the full skills corpus under --root (default 'skills') |
| `skills sources list` | REPORT | two dict-of-list sections from build_dependency_views() (skills_lint/cli.py:65): 'by_source' (one entry per declared source id -> list of citing skill leaves) and 'by_leaf' (one entry per skill leaf -> list of source ids it cites), both scoped to the full skills/ tree under --root (default 'skills') |
| `telemetry export` | ROWS | one JSON line per telemetry event ever recorded in the local telemetry directory (export_events_jsonl over ALL read_events, no date/limit filter) |
| `telemetry report` | REPORT | the event_types/commands/error_classes/exit_codes dicts embedded as cells in the single summary row grow with the number of DISTINCT values ever seen in telemetry history; the optional recent_errors table (--errors) is already hard-capped at --limit (max 100) |
| `verdict rollup` | REPORT | scope + n_documents + a `groups` dict; each group entry nests a `documents` list containing one interpretation_id per parsed verdict-interpretation file under --root, i.e. one entry per file across the WHOLE project's verdict-interpretation corpus (walk_interpretations(root)) |

