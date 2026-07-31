# Task-storage rollout closure — design

**Status:** Accepted
**Date:** 2026-07-31

## 1. Decision

Finish the task-storage split across every legacy Science project currently
registered in `~/.config/science/config.yaml`.

The rollout has four layers:

1. Correct the shared task parser so an otherwise-valid title may contain `]`.
2. Make project-local overlay provenance independent of checkout location.
3. Migrate each legacy project transactionally, preserve its task set, and
   rebuild its local graph.
4. Once all local graphs are current on local `main`, refresh the affected
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

## 3. Registry-wide inventory

The 2026-07-31 audit covered all 21 entries in
`~/.config/science/config.yaml`.

| State | Projects | Consequence |
|---|---|---|
| Legacy aggregate store | cancer/meta, evolution, pre-cancer, cBioPortal, ovarian, head-and-neck, prostate, breast, therapeutics, health/meta, pan-disease, cycles, immunity | Must migrate |
| Split store | protein-landscape, natural-systems, multiple-myeloma, seq-feats, science/meta, post-acute-infection | No task migration |
| Commons store | science-commons | No task queue; not a migration target |
| Missing path | `obsproj` under a deleted temporary directory | Registry hygiene debt, not a project migration |

The 13 legacy stores contain 272 active tasks:

| Project | Active tasks | Current migration result | Toolkit action |
|---|---:|---|---|
| cancer/meta | 11 | 11 writes | Pin corrective prerequisite |
| evolution | 31 | 31 writes | Pin corrective prerequisite |
| pre-cancer | 6 | 6 writes | Pin corrective prerequisite |
| cBioPortal | 74 | Refused on historical bracketed title | Pin corrective prerequisite |
| ovarian | 0 | Valid empty plan | Pin corrective prerequisite |
| head-and-neck | 0 | Valid empty plan | Pin corrective prerequisite |
| prostate | 0 | Valid empty plan | Pin corrective prerequisite |
| breast | 0 | Valid empty plan | Pin corrective prerequisite |
| therapeutics | 2 | 2 writes | Pin corrective prerequisite; sync stale environment |
| health/meta | 32 | 32 writes | Pin corrective prerequisite |
| pan-disease | 58 | Refused on historical bracketed title | Pin corrective prerequisite |
| cycles | 53 | 53 writes | Pin corrective prerequisite |
| immunity | 5 | 5 writes | Pin corrective prerequisite |

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

## 4. Shared parser correction

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
  worktree produces byte-identical local graph output;
- generated graphs contain no absolute `/.../overlays/...` source identifier;
- two peers with the same relative overlay path retain separate source quads in
  their respective project named graphs.

This correction is published as a second prerequisite revision; the already
published parser revision is not rewritten.

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

Expected storage deltas include removal of the aggregate source path, addition
of per-task source paths, and corresponding provenance-node changes. Task IDs
and task-domain triples remain equivalent.

Overlay-bearing graphs also replace absolute overlay provenance with stable
project-relative paths. Before any local commit, require zero source identifiers
matching an absolute `/.../overlays/...` path; checking only for `.worktrees/`
would miss the same defect in a primary-checkout build. Rebuilds from the
primary checkout and rollout worktree must produce identical local graph bytes
once both name the same content and corrected toolkit revision.

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
- graph diff is empty after the applicable build phase;
- federation peer checks complete without task-storage errors.

Primary checkouts may contain ignored data absent from their worktrees. Such
state is preserved and reported; it is never copied into a worktree or deleted
to force parity.

## 8. Sequencing and commit boundaries

### 8.1 Toolkit prerequisites

The first published toolkit prerequisite contains the parser change,
regression tests, correction to the original storage design, and the
canonical-plus-regenerated audit note.

The second prerequisite bundle adds only the overlay-provenance normalization,
its regression tests, and this rollout amendment. Run focused graph tests,
Ruff, Pyright, and the full default Science suite before pushing it to
`origin/main`. Consumer locks use the second public SHA; it contains the parser
correction by ancestry.

That sentence describes the corrective prerequisite bundle's scope, not the
complete revision history consumers receive. At final amendment review, toolkit `main`
was 28 commits ahead and zero behind `origin/main`, including the entity-index
path scrub, scoped-validation documentation, and the merged evidence-broker
session work. Reconcile the rollout branch with that local `main` before the
release gate; the published corrective SHA inherits those commits rather than
pretending to be parser-plus-overlay only.

At design review, local toolkit `main` was one commit ahead and zero behind
`origin/main`, so the first prerequisite push had a clean ancestry. Reconfirm
the ahead/behind relation immediately before the corrective push; consumer
locks depend on the resulting revision being publicly resolvable.

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
overlay defect was observed. Each receives one follow-up corrective commit
containing the new pin/lock and regenerated local graph; their task stores are
not rewritten. Cancer/meta remains uncommitted until it uses the corrected SHA.

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
point and prevents byte-identical builds after moving a repository.

## 11. Non-goals and reported follow-ups

This design does not:

- populate global registry parent fields;
- add, remove, or symmetrize project peers;
- delete the missing temporary `obsproj` registry entry;
- invent a graph artifact for science-commons;
- refresh unrelated stale standalone graphs;
- align consumers outside this rollout's local/composite closure set to one
  toolkit revision;
- rewrite historical task-path citations.

These remain visible follow-ups rather than hidden prerequisites.

## 12. Completion criteria

The rollout is complete when:

1. No present, non-Commons configured project retains `tasks/active.md`.
2. All 272 migrated active tasks are structurally identical to their baselines.
3. Non-empty stores have one file per active task; empty stores have no
   placeholder.
4. No target has a mixed store or migration journal.
5. cBioPortal plans 74 writes with no refusal and pan-disease plans 58 writes
   with no refusal under the corrected parser.
6. All 15 closure-target local graphs validate and report zero staleness.
7. All affected composites preserve declared membership, validate, and leave
   their local graphs byte-identical.
8. Cancer and health peer checks complete without storage errors.
9. Validation emits no traceback or task-storage fallback warning.
10. Registry and peer topology are unchanged.
11. No closure-target graph contains a source identifier that is an absolute
    path containing `/overlays/`, and an overlay-bearing primary/worktree
    rebuild is byte-identical.
