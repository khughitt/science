# Task-storage rollout closure — design

**Status:** Complete — implemented and merged to `main` at `6fd80378` (2026-08-01)
**Date:** 2026-07-31

The §12 completion criteria were re-verified against the tree on 2026-08-02: all
15 closure targets are on split storage with 279 active task files across the 13
migration targets; no configured project retains `tasks/active.md`; the 15 local
graphs and 14 composites contain zero absolute `/overlays/` source identifiers
and zero `.worktrees` provenance; and every consumer pin (`9bf9be13` cancer,
`d5bf01e2` health, `885fccd2` multiple-myeloma) is an ancestor of `origin/main`
containing both `36463540` and `2fc330d0`. The §11 follow-up to delete the
missing temporary `obsproj` registry entry was applied on 2026-08-02, leaving 20
registered projects.

## 1. Decision

Finish the task-storage split across every legacy Science project currently
registered in `~/.config/science/config.yaml`.

The rollout has six layers:

1. Correct the shared task parser so an otherwise-valid title may contain `]`.
2. Make project-local overlay provenance independent of checkout location.
3. Close the local graph revision manifest over the source families the graph
   loader actually consumes.
4. Make the migrator refuse substantive aggregate-ledger preambles instead of
   silently dropping them.
5. Migrate each legacy project transactionally, preserve its task set, and
   rebuild its local graph.
6. Once all local graphs are current on local `main`, refresh the affected
   composites without changing federation membership.

This is storage and generated-artifact closure. It is not a federation-topology
migration.

## 2. Context

The task-storage split shipped one open task per file under
`tasks/active/tNNN-slug.md`. The aggregate `tasks/active.md` format is now a
migration-only input: normal task and graph readers fail early and direct the
operator to `science tasks migrate-storage --apply`.

`science/meta` was the worked migration example, but the registered project
fleet was not migrated as part of the toolkit change. That gap now has visible
costs:

- task-aware validation falls back to reduced behavior or reports a storage
  prerequisite;
- graph builds fail when their project still has `tasks/active.md`;
- generated local and federated graphs remain stale;
- operational guides continue to direct agents to the retired aggregate file.

The validation-sidecar retirement exposed this debt in evolution and
health/meta. A registry-wide audit showed that fixing only those two projects
would leave their federations and most registered consumers in the same
pre-split state.

Execution exposed a second shared prerequisite. Graph materialization carries
an overlay's resolved absolute filename from `ProjectSources` into provenance.
A build from a nested worktree therefore serializes `.worktrees/<name>/` into
source URIs and `schema:identifier` values. The first two migrated projects
committed that location-dependent output: six overlay paths in cBioPortal and
54 in pan-disease. Cancer/meta exposed the defect before its commit.

Execution exposed a third shared prerequisite when cBioPortal's corrected
worktree graph was rebuilt from its primary checkout. The two graphs differed
for two independent reasons:

- revision metadata records checkout-specific file mtimes, so otherwise equal
  source trees do not produce byte-identical `graph_revision` triples;
- the primary checkout contained 11 ignored
  `results/**/datapackage.json` files consumed by `WorkflowRunAdapter`, while a
  clean worktree contained none.

The second difference is semantic: the primary graph had 99 workflow-run
quads absent from the clean-worktree graph. Both checkouts nevertheless
reported zero graph-diff rows because the revision manifest did not scan that
source family. Post-acute-infection has the same defect with five manifests.
This is not a reason to bless the primary checkout as authoritative. It is
evidence that graph inputs must be durable and that revision coverage must
match loader coverage before the rollout can continue.

Task 10 review exposed a fourth shared prerequisite. Aggregate parsing starts
at the first `## [tNNN]` header and ignores every earlier line. The migrator's
normalized before/after snapshots therefore certify only parsed task blocks:
they do not prove that the deleted aggregate file contained no other live work.
Cancer/meta would have lost two unchecked reminders, and therapeutics would
have lost a 14-item legacy `t-txNNN` checklist containing six open tasks. A
storage migration must refuse that input until the project explicitly
reconciles it.

## 3. Registry-wide inventory

The 2026-07-31 audit covered all 21 entries in
`~/.config/science/config.yaml`.

| State | Projects | Consequence |
|---|---|---|
| Legacy aggregate store | cancer/meta, evolution, pre-cancer, cBioPortal, ovarian, head-and-neck, prostate, breast, therapeutics, health/meta, pan-disease, cycles, immunity | Must migrate |
| Split store | protein-landscape, natural-systems, multiple-myeloma, seq-feats, science/meta, post-acute-infection | No task migration |
| Commons store | science-commons | No task queue; not a migration target |
| Missing path | `obsproj` under a deleted temporary directory | Registry hygiene debt, not a project migration |

The original parser-visible inventory contains 272 active tasks. The lossless
preamble audit found seven additional live reminders that must become
canonical tasks, yielding 279 active tasks after reconciliation:

| Project | Parsed tasks | Reconciled total | Initial dry-run result | Toolkit action |
|---|---:|---:|---|---|
| cancer/meta | 11 | 12 | 11 writes before guard | Reconcile one live reminder; pin final prerequisite |
| evolution | 31 | 31 | 31 writes | Pin final prerequisite |
| pre-cancer | 6 | 6 | 6 writes | Pin final prerequisite |
| cBioPortal | 74 | 74 | Refused on historical bracketed title | Pin final prerequisite |
| ovarian | 0 | 0 | Valid empty plan | Pin final prerequisite |
| head-and-neck | 0 | 0 | Valid empty plan | Pin final prerequisite |
| prostate | 0 | 0 | Valid empty plan | Pin final prerequisite |
| breast | 0 | 0 | Valid empty plan | Pin final prerequisite |
| therapeutics | 2 | 8 | 2 writes before guard | Archive legacy queue; promote six live items; pin final prerequisite |
| health/meta | 32 | 32 | 32 writes | Pin final prerequisite |
| pan-disease | 58 | 58 | Refused on historical bracketed title | Pin final prerequisite |
| cycles | 53 | 53 | 53 writes | Pin final prerequisite |
| immunity | 5 | 5 | 5 writes | Pin final prerequisite |

No target has a mixed store or a migration journal. All repositories were on
clean local `main` branches during the audit. The unrelated untracked report in
natural-systems remains user state and is outside this rollout.

### 3.1 Environment and revision observations

Seven target projects pin `3b72db6`, a revision that does not contain the
migrator: cancer/meta, pre-cancer, ovarian, head-and-neck, prostate, breast, and
immunity.

cBioPortal and pan-disease contain records that require the parser correction.
Those nine projects pin the new published toolkit revision as part of their
atomic migration commit.

Before the overlay defect was observed, evolution, therapeutics, health/meta,
and cycles already pinned revisions with the migrator and required no lock
movement for task storage alone.

The overlay-provenance correction changes that pin inventory. Eight local
closure targets contain overlays: cancer/meta, evolution, pre-cancer,
cBioPortal, therapeutics, health/meta, pan-disease, and cycles.
Multiple-myeloma also contains overlays and its composite refresh normally
re-materializes its local graph. Those nine projects must consume the corrected
revision before their next local build. For a single auditable prerequisite,
all 13 task-migration targets pin that same corrected revision; the five
zero-overlay upgrades avoid pinning an already-superseded intermediate SHA.

Checked-in locks, not installed environments, are authoritative. cBioPortal and
therapeutics demonstrated why: their existing virtual environments did not
match their lock revisions. Every rollout worktree therefore runs
`uv sync --frozen` before invoking Science.

### 3.2 Project-local source reproducibility

A fleet sweep found two projects with ignored files that contribute domain
quads:

| Project | Ignored graph inputs | Semantic effect |
|---|---:|---|
| cBioPortal | 11 `results/**/datapackage.json` files | 11 workflow-run entities, 99 quads |
| post-acute-infection | 5 `results/**/datapackage.json` files | Five workflow-run entities |

The 16 manifests total 76,324 bytes. All are JSON objects accepted by the
current adapter, contain no credential-shaped fields or values, and use no
volatile host, user, command, or wall-clock metadata. They are provenance
manifests, not result payloads, and are suitable for version control.

One post-acute manifest contains a checkout-local source value:
`results/t116-power-bias-floor-sim/datapackage.json` records an absolute path to
`code/workflows/t116-power-bias-floor/config.yaml`. Normalize that value to the
project-relative path before tracking the file. The adapter does not consume
the `sources` field, so the normalization changes portability without changing
the emitted graph.

Several projects also carry ignored `tasks/.tasks.lock` files, and pan-disease
has ignored Marimo session JSON under a code root. Those files emit no domain
quads. They explain revision-metadata byte differences but not semantic graph
differences. Both are known transient compiler/tool control state and are
removed from the default revision manifest with exact leaf patterns:
`tasks/.tasks.lock` and `**/__marimo__/session/*.json`. No broader code or
notebook exclusion is introduced.

### 3.3 Aggregate-preamble audit

The fleet audit inspected every line before the first canonical active-task
header. cBioPortal and pan-disease began directly with canonical headers before
their completed migrations. Evolution and pre-cancer do the same. The four
empty cancer-type stores contain only one complete HTML comment. Health/meta,
cycles, and immunity contain only their conventional comment; blank lines and
the exact `# Active Tasks` heading are also non-data scaffolding.

Two projects contain substantive preambles:

- cancer/meta has a reminder already satisfied by completed `task:t013` and a
  still-live 2026-06-15 compatibility-symlink scan. The first receives an
  explicit satisfied disposition; the second becomes canonical `task:t053`.
- therapeutics has 14 legacy `t-txNNN` checklist records before canonical
  `task:t001` and `task:t002`. Eight are checked complete and six remain open.
  Preserve all 14 verbatim in `doc/legacy-task-queue.md`, including a mapping
  table. Its done ledger already owns `task:t003` through `task:t005`, so the
  allocator creates `task:t006` through `task:t011` for the six open records in
  source order. Preserve `t-tx003`'s in-progress state as `status: active`; the
  other five begin proposed except `task:t011`, which is blocked by
  `task:t008` and `task:t009`. Historical prose may retain the old labels; each
  new task description and the archive map its legacy label to the canonical
  ID.

This is explicit data reconciliation, not a parser compatibility mode. The
canonical active total increases by seven; no other project count changes.

## 4. Shared toolkit corrections

### 4.1 Root cause

The task parser rejects `]` anywhere in a task title. The storage-split design
justifies that rule by saying a bare closing bracket would break the aggregate
header.

It does not. The header grammar first consumes the complete ID delimiter,
`[tNNN]`, and then captures the remainder of the line as the title. A closing
bracket in that remainder is unambiguous.

The invalid restriction blocks seven historical records:

- six cBioPortal done-ledger titles such as `F10 [Significant] ...`;
- one pan-disease done-ledger title containing `[UNVERIFIED]`.

No active legacy title contains a closing bracket. The migrator refuses because
it scans every done ledger to enforce store-wide ID uniqueness before writing
anything.

### 4.2 Behavior change

Remove `]` from title rejection at the two shared code sites:

- `_parse_task_header`, which covers aggregate-ledger and migration parsing;
- `_validate_task_title`, which covers split frontmatter plus task creation and
  editing.

After `_parse_task_header` normalizes the captured title with `strip()`, route
it through `_validate_task_title` instead of retaining a header-specific
predicate. This also closes the pre-existing spaces-only header hole: today
`## [t014]    ` parses to an empty title. A fleet-wide sweep found no empty
titles, so this adds a fail-early invariant without changing stored data.

Update `_validate_task_title`'s error text as well as its predicate so it no
longer claims that titles may not contain `]`.

Newlines remain invalid. Existing malformed-ID, required-field, unknown-field,
duplicate-ID, destination-collision, and differing-ledger-duplicate refusals
remain unchanged.

Amend `docs/plans/2026-07-26-context-budget-slice3-storage-design.md` where it
claims that `]` breaks the header. Do not add a compatibility parser, feature
flag, or alternate mode.

### 4.3 Required evidence

Tests prove that:

- `F10 [Significant] ...` parses and round-trips unchanged;
- a title containing `[UNVERIFIED]` parses and round-trips unchanged;
- a title beginning with `[UNVERIFIED]` round-trips through split-store YAML
  frontmatter, exercising `yaml.safe_dump`'s quoting of a leading bracket;
- a spaces-only aggregate title is rejected by the shared title validator;
- a migration with those titles in existing done ledgers proceeds;
- multiline titles remain rejected;
- the other fail-closed migration checks remain armed.

The toolkit commit is tested and pushed before any consumer lock points to it.

### 4.4 Stable overlay provenance

Overlay files are project-authored sources. Their graph identity is the stable,
project-relative POSIX path, such as `overlays/papers/Garraway2006.md`, not the
absolute directory from which a build happened to run.

Keep `ProjectSources.commons_overlay_paths` absolute. It is the direct
projection of `borrower.declaration.source_ref.path`, and the Commons canary
pins that `SourceRef.path`-derived value to an absolute filename. Normalize
only at the graph-emission boundary, its sole reader: resolve both
`sources.project_root` and the recorded overlay path, require the latter to be
contained by the former, and serialize `relative_to(project_root).as_posix()`.
An overlay outside the project root is a compiler error rather than a fallback
to machine-specific provenance.

This is the smallest shared fix because every graph-emission path already
passes through `_emit_phase`. Changing `ProjectSources` would redefine its
`SourceRef.path`-derived projection and invalidate the absolute-path canary even
though only persisted graph identity is defective. Mapping a worktree to the
primary checkout's absolute path would still make graph bytes machine- and
location-dependent.

Tests prove that:

- source loading still exposes the absolute overlay path internally;
- graph provenance emits the project-relative overlay path in both its URI and
  `schema:identifier`;
- an overlay path outside the project root fails early;
- identical project content built from a primary checkout and a linked
  worktree produces identical semantic quads after excluding `REVISION_URI`;
- generated graphs contain no absolute `/.../overlays/...` source identifier;
- two peers with the same relative overlay path retain separate source quads in
  their respective project named graphs.

This correction is already published as a second prerequisite revision; the
already published parser revision was not rewritten.

### 4.5 Revision-manifest source closure

`science graph diff` may report “up to date” only if its manifest covers every
project-local source family that can change the materialized graph. The current
directory walk covers entities, tasks, the profile-default code directory,
runs, and structured knowledge sources but omits five loader surfaces:

- `research/packages/**/*.md` canonical markdown;
- `papers/references.bib` bibliography authority;
- entity-profile `data/**/datapackage.yaml` and
  `results/**/datapackage.yaml` files;
- `results/**/datapackage.json` workflow-run manifests;
- `overlays/{datasets,papers,topics,themes}/*.md` Commons overlays.

It also only walks `ProjectPaths.code_dir`. `CodeAdapter` instead scans every
declared `code_roots` entry and honors `code_excludes`. Align the manifest with
that existing discovery contract: walk every code root and exclude the same
configured paths. This is parity for an existing source family, not a sixth
new storage convention.

Extend `build_input_manifest` over those exact source conventions, reusing the
loader's existing discovery predicates where parsing determines eligibility.
Do not hash entire `data/` or `results/` payload trees. Record each existing
source root in the manifest walk-set and each eligible file by project-relative
POSIX path. Add `tasks/.tasks.lock` to the default excludes because the
allocation lock is transient control state and contributes no graph content.
Also exclude only `**/__marimo__/session/*.json`; these are Marimo's ignored
session records, not discoverable code entities.

This closes project-local loader coverage. Commons canonical records remain an
external dependency and are outside the local revision manifest; default
Commons resolution and its existing failure behavior remain unchanged.

The manifest deliberately retains `mtime_ns` because mtime and hybrid diff
modes are local operational instruments. Consequently the `graph_revision`
subject is not a reproducible artifact across checkouts even when file bytes
match. Cross-checkout parity therefore compares named-graph quads after removing
only quads whose subject is `REVISION_URI`. This is the existing semantic
projection used by the compiler phase-split tests. Same-checkout rebuilds may
still use byte identity as the stronger canary.

Tests prove that each omitted source family appears in the manifest, a changed
workflow-run manifest produces a graph-diff row, ignored result payloads remain
outside the manifest, every declared code root and `code_excludes` decision is
respected, both transient leaf classes are excluded, and primary/worktree builds
with the same tracked source bytes have identical semantic quads.

### 4.6 Lossless aggregate-preamble refusal

Keep `_parse_tasks_text` unchanged: done ledgers and direct parser callers may
legitimately carry headings outside task blocks. Tighten only the destructive
storage transition in `tasks_migrate.py`. Before parsing `tasks/active.md`,
inspect the prefix before the first task-like `_ANY_TASK_HEADER_RE` match.
Permit only blank
lines, the exact `# Active Tasks` heading, and complete single-line HTML
comments. Any other line adds a refusal naming `tasks/active.md` and its line
number. The refused plan contains no entries or post-images; dry-run and apply
write no split content or migration journal and leave the aggregate unchanged.
Apply may still create the normal task-allocation lock.

If no canonical header exists, the entire file is the prefix. This keeps the
four audited comment-only empty stores valid while refusing a checklist-only
queue. Do not add a flag, fallback parser, implicit task conversion, or broader
Markdown heuristic.

Tests cover a cancer/meta-style unchecked reminder, a therapeutics-style
legacy checklist item, allowed heading/comment/blank scaffolding, and a
comment-only zero-task store. They also reject text surrounding an otherwise
complete HTML comment and require refused plans to contain zero planned writes.
Existing bracket-title, empty-store, transaction, and second-run refusal tests
remain green.

## 5. Project-local migration contract

Each project migration runs in an isolated worktree created from that project's
exact local `main`.

`$EVIDENCE_DIR` below denotes a project-specific temporary directory outside
the worktree. Evidence files are retained through final review and are never
staged into a consumer repository.

### 5.1 Baseline

Before mutation, capture:

- every active task as a normalized complete `Task` structure;
- every done-ledger task structure and the ledger bytes;
- the migration dry-run and exit status;
- validation JSON, stderr, and exit status;
- the complete, unbudgeted graph diff via
  `science graph diff --format json --output "$EVIDENCE_DIR/local-graph-diff-before.json"`;
- Git status and relevant ignored-state caveats.
- the exact aggregate SHA-256 plus a numbered display of the prefix before the
  first task-like header, so normalized task parity cannot hide non-task text
  without mislabeling the display projection as raw bytes.

The normalized task snapshot is the parity authority. Rendered bytes are not:
the purpose of the migration is to change the active-task representation.

For a project whose pin changes, retain its current-pin validation as
informational evidence, then install the target pin and capture the canonical
pre-migration baseline before applying the storage change. Before/after parity
is evaluated with the same toolkit revision; pin movement and storage movement
are not conflated.

### 5.2 Apply and verify

Run the project-local, lock-synchronized Science command:

```bash
uv run --frozen science tasks migrate-storage --apply
```

After apply:

- the normalized active-task set equals the baseline exactly;
- every done ledger is byte-identical;
- `tasks/active.md` is absent;
- a non-empty source produces exactly one `tasks/active/*.md` file per task;
- no active file contains a terminal task;
- no migration journal remains;
- task listing succeeds from the split or empty store.

For the nine non-empty migrations, a second dry-run refuses because
`tasks/active/` is non-empty and `tasks/active.md` is absent. For ovarian,
head-and-neck, prostate, and breast, apply removes the empty aggregate file and
the resulting valid `EMPTY` state reports only that there is nothing to
migrate. No placeholder file is manufactured to keep an empty directory in
Git.

Any structural task delta, done-ledger byte delta, unplanned refusal, mixed
store, or retained journal stops that project before commit.

Cancer/meta and therapeutics are the only reconciliation exceptions. Their
exact aggregate hashes, numbered preamble displays, and dispositions are
review inputs. Cancer/meta first returns
its uncommitted rollout worktree to the recorded base, preserves the failed
migration evidence, then migrates the original 11 task blocks and adds `t053`
through the split-store CLI. Therapeutics archives all 14 legacy checklist
records verbatim, removes only that archived prefix, migrates `t001` and `t002`,
then adds the six mapped canonical tasks through the CLI. Their after snapshots
must contain 12 and eight active tasks respectively and must pass explicit
legacy-label coverage checks.

### 5.3 Documentation

Update live operational instructions in each touched project where they name
`tasks/active.md`. The current location is `tasks/active/`, with one file per
open task; operators should normally use `science tasks` rather than editing
paths directly.

Historical reports and citations that accurately describe where a task lived
at the time remain unchanged. Already-split standalone documentation debt, such
as natural-systems, is reported separately rather than used to expand this
rollout.

One dated audit is also an active shipped skill reference. Add a dated
superseded note to the canonical
`docs/audits/downstream-project-conventions/synthesis.md`, then regenerate
`skills/generated/science-command-preamble/references/docs/audits/downstream-project-conventions/synthesis.md`.
The note covers its claims that `tasks/active.md` is the universal lifecycle
shape so agents do not read the historical observation as current guidance.

Post-acute-infection is a closure target but not a migration target. Its local
`main` already contains the task-storage split in commit `67361ff`; a later
local commit removed the resolved acceptance prerequisite. Its live guide and
graph still describe the aggregate store. Update its guide and rebuild its
local graph without rerunning the migrator.

## 6. Graph closure

### 6.1 Why graph work is part of the transaction

Task records are graph inputs. Committing a storage migration without updating
`knowledge/graph.trig` leaves the project's tracked generated representation
knowingly stale and keeps downstream composites on the old source provenance.

Local graphs and composites have different dependency boundaries:

- a local graph consumes canonical files in its own project;
- a composite consumes the completed local graphs named by `peers:`.

Separating those phases avoids cyclic ordering between projects that name one
another as peers.

### 6.2 Local phase

The 13 migrated projects, post-acute-infection, and multiple-myeloma run:

```bash
uv run --frozen science graph build --local-only
uv run --frozen science graph validate
uv run --frozen science graph diff --format json \
  --output "$EVIDENCE_DIR/local-graph-diff-after.json"
```

The local graph is committed with the pin, task migration, and live
documentation for that project.

The pre-rollout audit already found non-task graph staleness in several targets,
including 38 rows in cBioPortal, 53 in pan-disease, and 29 in
post-acute-infection. A canonical rebuild incorporates the current source tree
honestly. Generated bytes are not tuned to preserve an obsolete graph.

Task 10 review identified two exact non-task refresh deltas in cancer/meta that
must be recorded rather than hidden: 25 `SkillLoad` quads materialize from the
already-authored `skills_loaded` block in
`entities/plans/0001-t031-transcriptional-output-analysis-plan.md`, which the
baseline graph diff marked stale, and one `skos:related` quad disappears after
Science Commons commit `b98600b` removed that dangling outbound reference from
`theme:0013-cross-disease-foundations`. Before unwinding the interrupted
migration, preserve the complete already-reviewed corrective graph and its
semantic projection. After remigrating the original 11 tasks but before adding
`t053`, the new build must match that projection byte-for-byte after excluding
only `REVISION_URI`. This executable gate proves there is no other semantic
delta without a bespoke normalization script. Adding `t053` is then the only
remaining source change and is reviewed as a bounded final graph addition.

Expected storage deltas include removal of the aggregate source path, addition
of per-task source paths, and corresponding provenance-node changes. Task IDs
and task-domain triples remain equivalent.

Overlay-bearing graphs also replace absolute overlay provenance with stable
project-relative paths. Before any local commit, require zero source identifiers
matching an absolute `/.../overlays/...` path; checking only for `.worktrees/`
would miss the same defect in a primary-checkout build.

cBioPortal and post-acute-infection also make their workflow-run provenance
durable. Replace the broad `results/` ignore with narrow recursive rules that
keep payloads ignored while admitting parent directories and only
`results/**/datapackage.json`; retain each project's tracked
`results/.gitkeep`. Track all
16 manifests in the same consumer transaction that rebuilds the graph. The
post-acute transaction first normalizes the one checkout-local `sources.path`.

Cross-checkout graph comparisons require identical semantic quads, excluding
only the `graph_revision` subject. They do not require byte identity because
revision mtimes are intentionally local. Within one worktree, repeated builds
still require byte identity when no source changed.

The artifact gate is the direct persisted predicate:

```bash
test "$(rg -o 'schema:identifier "/[^"]*/overlays/[^"]*"' \
  knowledge/graph.trig | wc -l)" -eq 0
```

### 6.3 Composite phase

Merge every verified project-local commit into its local `main` before
refreshing composites. Then rebuild composites for:

- cancer/meta;
- multiple-myeloma;
- evolution;
- pre-cancer;
- cBioPortal;
- ovarian;
- head-and-neck;
- prostate;
- breast;
- health/meta;
- pan-disease;
- cycles;
- immunity;
- post-acute-infection.

Therapeutics has no composite. Multiple-myeloma needs a corrected toolkit pin
and local rebuild before its composite refresh; its composite also depends on
the changed cancer/meta local graph.

Once every local graph is current, these composite refreshes are independent:
they read peer local graphs, not peer composites. A normal `graph build` may
re-materialize the local graph while producing the composite; the already
committed local graph must remain byte-identical. A local graph delta at this
stage stops the rollout.

Each composite refresh runs explicit validation and freshness checks against
the composite artifact:

```bash
uv run --frozen science graph validate --path knowledge/composite.trig
uv run --frozen science graph diff --path knowledge/composite.trig --format json \
  --output "$EVIDENCE_DIR/composite-graph-diff-after.json"
```

Composite membership must equal the project's authored `peers:` list before and
after. Default Commons behavior remains in force. A Commons-resolution failure
is reported and blocks the affected build; `--no-commons` is not a silent
fallback.

Relative overlay source URIs are project-local identities, not globally unique
federation identities. Composite assembly places each peer's complete local
graph into that peer's project named graph. Two peers may therefore contain the
same `overlays/<kind>/<name>.md` source URI without losing quads; the named graph
is the required qualifier. Composite consumers inspecting provenance must read
quads or otherwise preserve graph context rather than flattening peer graphs
into one union and treating a source URI as globally unique.

## 7. Validation contract

Validation is compared within each worktree using complete JSON output and
explicit exit statuses. Every non-empty graph-diff capture uses `--output`; the
stdout JSON renderer is capped at 40 rows and is not baseline evidence. The
post-build files are also captured with `--output` and asserted to contain zero
rows.

The storage split can legitimately activate checks that previously lacked a
task resolver. Newly reachable short-form or task-reference findings are
reported as instrument activation, not erased to preserve a false baseline.
Unrelated finding deltas stop the rollout for investigation.

Each project verifies:

- task listing works;
- validation with `--all --strict --format json` and an explicit `--output`
  path produces no traceback; the corresponding baseline also uses
  `--output`;
- no storage-fallback warning remains;
- local and composite graphs validate;
- graph diff is empty in hybrid mode immediately after a worktree build and in
  hash mode from the merged primary checkout;
- federation peer checks complete without task-storage errors.

Primary checkouts may contain ignored data absent from their worktrees. Such
state is preserved and reported; it is never copied into a worktree or deleted
to force parity. If an ignored file is an actual graph input, as with the 16
workflow-run manifests, rollout stops until that provenance is audited and made
durable. Ignored payloads and non-contributing tool state remain untouched.

## 8. Sequencing and commit boundaries

### 8.1 Toolkit prerequisites

The first published toolkit prerequisite contains the parser change,
regression tests, correction to the original storage design, and the
canonical-plus-regenerated audit note.

The second prerequisite bundle added the overlay-provenance normalization and
its regression tests. It is already public at `36463540`.

The third prerequisite closes revision-manifest source coverage, excludes the
transient task lock, adds its regression tests, and carries this amended design
and plan. It is public at `2fc330d0`.

The fourth prerequisite adds only the lossless aggregate-preamble refusal and
its tests, plus this reviewed amendment by ancestry. Run focused migration
tests, Ruff, Pyright, and the full default Science suite before pushing it to
`origin/main`. Final consumer locks use this fourth public SHA; it contains all
earlier corrections by ancestry. cBioPortal and pan-disease receive local-only
follow-up repin commits before Task 10 resumes.

At amendment time, local toolkit `main` is `96ab4a5a`, five commits ahead and
zero behind `origin/main`; those five commits are the reviewed annotation
reasoning-invalidation design/plan series, not part of the preamble-guard
commit. The final revision inherits them when the rollout branch is reconciled
to current local `main`. Reconfirm this relation and the clean merge tree before
publication so the audit trail does not confuse commit scope with revision
ancestry.

These descriptions concern prerequisite commit scope, not the complete revision
history consumers receive. Reconfirm the ahead/behind relation immediately
before the fourth push; consumer locks depend on the resulting revision being
publicly resolvable.

### 8.2 Project-local commits

Each target receives one atomic migration/local-graph commit containing, where
applicable:

- exact toolkit pin and lock update;
- deletion of `tasks/active.md`;
- creation of `tasks/active/*.md`;
- live documentation correction;
- rebuilt `knowledge/graph.trig` and its local manifest/mappings.

Post-acute-infection's corresponding commit contains only its closure changes.
No commit deletes the aggregate store while leaving the project unable to read
the replacement.

cBioPortal and pan-disease already committed their task migrations before the
overlay defect was observed, and cBioPortal already has a local overlay-fix
commit. cBioPortal receives one more source-closure commit containing the final
pin/lock, narrow ignore rules, 11 tracked manifests, and regenerated local
graph. Pan-disease moves directly from its parser pin to the final prerequisite.
Those commits currently pin the third prerequisite; each receives a fourth-pin
follow-up without rewriting its task store or graph semantics. Cancer/meta
remains uncommitted until its lossy interrupted state is unwound and it uses the
fourth SHA.

Post-acute-infection's closure commit contains its final pin/lock, narrow ignore
rules, five tracked manifests, the one path normalization, its live guide fix,
and regenerated local graph.

### 8.3 Composite commits

After all local commits are merged, each project with changed generated bytes
receives one composite-refresh commit. Do not create an empty commit when the
composite is already current.

Consumer repositories are merged into local `main`. Existing consumer remotes
are not pushed without separate authorization. Toolkit prerequisites are
pushed because exact consumer revisions must be publicly resolvable.

## 9. Failure and recovery

The existing transactional migrator remains the only writer:

- dry-run first;
- apply under its task-allocation lock;
- journal post-images before mutation;
- delete `active.md` last;
- use `--resume` only when the journal proves an interrupted apply;
- refuse different post-images rather than overwriting them.

Do not manually finish a partial migration, copy task files between projects,
or delete a journal to bypass recovery. A failure is resolved in that project's
worktree before any commit or local-main merge.

Composite work begins only after all local migrations are complete. A failed
composite refresh cannot corrupt task storage and is retried after its graph or
peer dependency is corrected.

The cBioPortal diagnostic rebuild that exposed the third prerequisite was
preserved, verified, and cleaned before local commit `5a6c6b8` fast-forwarded.
Its primary/worktree semantic projections are identical after excluding the
revision subject. That completed recovery remains evidence and is not rerun by
the fourth-prerequisite repin.

Task 10's interrupted cancer/meta worktree is also rollout-owned and
uncommitted. Preserve its complete evidence and require its exact known status,
then restore only `pyproject.toml`, `uv.lock`, `knowledge/graph.trig`, and
`tasks/active.md` from base and delete only the 11 named generated split files.
Require a clean worktree at `fdeeb705` before applying the reviewed preamble
reconciliation. Do not reset a broader path or reuse the lossy post-image.

## 10. Alternatives rejected

### 10.1 Rewrite the seven historical titles

This would make the current parser accept the corpus, but it changes truthful
historical records to satisfy a restriction unsupported by the grammar. It also
leaves future bracketed titles needlessly invalid.

### 10.2 Migrate cancer and health as separate programs

This adds a checkpoint but leaves half the registered fleet in a known-invalid
storage state longer. The local migrations are already isolated; the graph
phase supplies the needed coordination boundary.

### 10.3 Normalize federation topology during rollout

The global registry has `parent: null` for every entry. Cancer's four newer
cancer-type projects point toward cancer/meta while meta does not list them;
health peer lists are also asymmetric. Those facts merit a separate federation
decision. Changing them here would alter composite membership and make storage
parity impossible to interpret.

### 10.4 Make overlay paths relative in `ProjectSources`

`commons_overlay_paths` itself has one reader, graph materialization, but its
value is projected directly from `SourceRef.path`; the Commons canary pins that
upstream path as absolute. Changing the loader projection would redefine the
source-reference contract to repair a persistence-only defect. Normalize at
graph emission instead.

### 10.5 Serialize the primary checkout's absolute overlay path

The registry already maps worktrees to their primary checkout for project
registration, but reusing that absolute path for provenance only hides the
worktree segment. It still makes graph identity depend on one machine's mount
point and changes semantic source identity after moving a repository.

### 10.6 Treat ignored workflow manifests as local-only state

This preserves existing primary graphs but makes a clean checkout silently
smaller. It also leaves `graph diff` unable to report the omitted inputs. The
manifests are small provenance records; track them while keeping their payloads
ignored.

### 10.7 Require every graph source to be tracked at compile time

This would make released graphs reproducible but would also reject the normal
pre-commit workflow of building a graph from a newly authored entity or task.
Durability is a rollout/release gate. The compiler continues to accept working
tree sources while its revision manifest reports their changes.

### 10.8 Preserve cross-checkout byte parity by deleting revision mtimes

Mtime and hybrid modes are existing local diagnostics. Removing their stored
baseline is unnecessary for this rollout: semantic parity already excludes the
single revision subject, while same-checkout byte identity remains available.

### 10.9 Trust normalized task parity despite unparsed preamble

This is the defect exposed by Task 10: parser parity can be exact while the
aggregate file deletion loses live work. Archiving or reconciling substantive
preamble is a project decision, and the shared migrator must refuse until that
decision is explicit.

## 11. Non-goals and reported follow-ups

This design does not:

- populate global registry parent fields;
- add, remove, or symmetrize project peers;
- delete the missing temporary `obsproj` registry entry;
- invent a graph artifact for science-commons;
- refresh unrelated stale standalone graphs;
- align consumers outside this rollout's local/composite closure set to one
  toolkit revision;
- normalize historical workflow-manifest schemas or broaden
  `WorkflowRunAdapter`'s `related` projection;
- rewrite historical task-path citations.

These remain visible follow-ups rather than hidden prerequisites.

## 12. Completion criteria

The rollout is complete when:

1. No present, non-Commons configured project retains `tasks/active.md`.
2. All 272 originally parsed tasks are structurally identical to their
   baselines, seven reconciled live reminders exist as canonical tasks, and the
   final active total is 279.
3. Non-empty stores have one file per active task; empty stores have no
   placeholder.
4. No target has a mixed store or migration journal.
5. cBioPortal plans 74 writes with no refusal and pan-disease plans 58 writes
   with no refusal under the corrected parser.
6. All 15 closure-target local graphs validate, report zero hybrid staleness in
   their build worktrees, and report zero hash staleness from local `main`.
7. All affected composites preserve declared membership, validate, and leave
   their local graphs byte-identical.
8. Cancer and health peer checks complete without storage errors.
9. Validation emits no traceback or task-storage fallback warning.
10. Registry and peer topology are unchanged.
11. No closure-target graph contains a source identifier that is an absolute
    path containing `/overlays/`, and an overlay-bearing primary/worktree
    rebuild has identical semantic quads after excluding `REVISION_URI`.
12. The revision manifest covers all five formerly omitted project-local
    source families, matches declared code-root discovery, excludes
    `tasks/.tasks.lock` and Marimo session JSON, and detects a changed
    workflow-run manifest.
13. A migration dry-run refuses substantive aggregate preamble before any
    split or journal write; cancer/meta records the satisfied/live
    dispositions, and therapeutics preserves all 14 legacy records while
    mapping its six open labels to canonical tasks.
14. cBioPortal's 11 and post-acute-infection's five workflow-run manifests are
    tracked while non-manifest result payloads remain ignored; no tracked
    manifest contains a checkout-local path.
