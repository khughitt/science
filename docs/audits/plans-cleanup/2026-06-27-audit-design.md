# Plans Cleanup Audit Design

## Status

Accepted.

## Date

2026-06-27

## Context

`docs/plans/` contains hundreds of historical planning, design, implementation,
and specification documents. Many describe work that has since been completed,
superseded, or reshaped by later implementations. Keeping all of them in the
active plans directory makes it harder to find current work and encourages agents
to cite stale status.

The cleanup needs to reduce clutter without losing operational knowledge that
belongs in durable documentation. Because the files are version controlled,
completed or superseded plans can be deleted once their status is verified. Cases
that are incomplete or unclear should be retained for triage rather than forced
into a premature decision.

The same approach should later be adapted to project-level planning/spec
directories such as `meta/doc/plans/`, `doc/plans/`, `doc/specs/`,
`docs/plans/`, and `docs/specs/`. The newer `entities/plans` and
`entities/specs` locations are out of scope for the initial cleanup.

## Decision

Use a first pass that deletes obvious completed or superseded plan threads and
flags uncertain threads for follow-up investigation.

Before cleanup, build a normalized audit manifest under
`docs/audits/plans-cleanup/`. The manifest should group related files into
review threads instead of treating every file independently. A thread may include
paired or closely related files such as `*-design.md`, `*-plan.md`,
`*-implementation.md`, `*-spec.md`, phase variants, and short addenda.

Subagents may review independent batches of threads, but they should not make
irreversible repository changes. They should return structured findings with
evidence. The main agent reconciles those findings, identifies cross-thread
dependencies, performs obvious deletions, and leaves incomplete or unclear cases
in the manifest for later decision.

## Thread Grouping

Group files into threads with a deterministic first pass, then allow explicit
main-agent reconciliation for cases the heuristic cannot safely resolve.

For each file:

1. Parse the leading `YYYY-MM-DD` date as `file_date`.
2. Remove the leading date to produce a raw slug.
3. Normalize terminal role suffixes from the slug, matching the longest suffix
   first. Treat these suffixes as roles, not topic identity: `design`, `plan`,
   `implementation`, `implementation-plan`, `spec`, `findings`, `manifest`,
   `pilot`, and `addendum`.
4. Group files with the same normalized slug into one thread.

Files that do not begin with a `YYYY-MM-DD-` prefix are not silently dropped and
do not abort the inventory. The inventory pass collects every non-conforming
filename, records them under `non_conforming_files` in `thread-index.json`, and
prints them as warnings so a reviewer can rename or exclude them. This matters
most for the later project-level phase, where documentation layouts vary and
stray index or README files are common.

Use the normalized slug as the default `thread_id`. This deliberately biases
toward over-grouping exact slug reuse across dates rather than splitting paired
or continued work across subagent batches. If two genuinely distinct efforts
reuse the same normalized slug months apart, the main agent should split the
thread during reconciliation and record that split in `overrides.json` (see
Overrides). The inventory pass reapplies overrides on every regeneration, so
split thread ids stay first-class in `thread-index.json` and remain eligible for
batching and validation.

Files with different normalized slugs stay in separate threads unless the files
explicitly identify one another as a continuation, replacement, phase, or
supersession. Do not collapse broad same-topic work automatically from loose
slug similarity alone. Instead, record those links in `related_threads` (through
`overrides.json`, which the inventory pass attaches to the named threads) or in
the supersession fields of the review record.

The generated inventory should retain each file's raw slug and stripped role so
reviewers can spot uncommon suffix collisions, such as a topic that genuinely
ends with `manifest`, `spec`, or `plan`.

Each thread has:

- `earliest_file_date`: oldest file date in the grouped thread.
- `latest_file_date`: newest file date in the grouped thread.
- `role_files`: file paths grouped by inferred role.

Batch selection uses `latest_file_date`. A thread that includes June files is a
June-scoped thread even if one of its files started in March or April.

## Overrides

`overrides.json` is a small, hand-authored, version-controlled file that records
the few decisions the deterministic grouping pass cannot make on its own. The
inventory pass reads it and reapplies it on every regeneration, so the generated
`thread-index.json` stays idempotent over human edits instead of clobbering
them.

It supports two override kinds:

- `splits`: map an over-grouped `thread_id` to the child threads it should
  become. Each child names its `thread_id` and the exact files it owns. Every
  file currently in the original thread must be assigned to exactly one child;
  unassigned files, unknown child file paths, or child ids that collide with
  existing threads are a fail-loud error. A split whose original thread has
  already been deleted is a no-op.
- `related_threads`: map a `thread_id` to nearby thread ids that should be
  reconciled together. The inventory pass attaches these to the named thread
  records; the grouping pass never infers them from slug similarity.

Because split children become first-class threads in `thread-index.json`, they
are batched and validated like any other thread, and the audit stays resumable.
A review written against the original thread id before a split stays valid:
`validate` recognizes split origins as allowed thread ids, and the main agent
appends fresh child reviews afterward (latest-wins).

## Manifest Location And Format

Use `docs/audits/plans-cleanup/` for this audit workspace. The first pass should
produce these files:

- `thread-index.json`: generated thread inventory, including grouping metadata,
  non-conforming-file warnings, and related-thread hints applied from
  `overrides.json`.
- `overrides.json`: hand-authored thread splits and related-thread links that
  the inventory pass reapplies on every regeneration (see Overrides).
- `reviews.jsonl`: append-only subagent and main-agent review records. Each line
  is one complete review record keyed by `thread_id`.
- `actions.jsonl`: append-only record of migrations, deletions, and deferred
  decisions performed by the main agent.

The latest review for a `thread_id` is the current review state. Because the
review and action logs are append-only and keyed by stable thread identifiers,
the audit can resume across sessions without re-reviewing completed threads or
re-deleting files.

## Status Taxonomy

Use these statuses in the audit manifest:

- `delete_obvious`: verified completed and no durable-doc migration is needed.
- `superseded_delete`: verified superseded by later functionality or docs.
- `implemented_needs_durable_docs`: verified completed, but the plan contains
  stable user-facing, process, or convention knowledge that should move before
  deletion.
- `keep_historical`: verified complete or superseded, but worth retaining as
  historical architecture context outside active `docs/plans/` discovery.
- `incomplete`: the described work is still meaningfully unfinished.
- `unclear`: evidence is insufficient or conflicting.

## Review Record

Each reviewed thread should capture:

- `thread_id`: normalized slug by default, with an explicit replacement if the
  main agent splits an over-grouped thread.
- `files`: related files in the thread.
- `topic`: short human-readable summary.
- `status`: one status from the taxonomy.
- `superseded_by`: thread identifiers, file paths, or durable docs that replace
  this thread. Required for `superseded_delete`.
- `supersedes`: older thread identifiers or file paths this thread replaces.
- `related_threads`: nearby threads that should be reconciled together but are
  not the same review thread.
- `evidence`: code paths, docs paths, tests, command output summaries, or git
  references used to verify status.
- `remaining_gaps`: concrete missing work for incomplete or unclear threads.
- `durable_doc_candidate`: target durable location if knowledge should be
  migrated.
- `recommended_action`: delete, create migration checkpoint, keep for triage,
  move to historical, or keep active. This must be coherent with `status`; the
  validator rejects mismatched pairs such as `delete_obvious` with `keep active`.
- `review_notes`: short reviewer notes, including confidence and caveats.

## Durable Documentation Targets

Move useful knowledge to existing durable locations:

- User-facing behavior and workflows: `docs/user-guide/`.
- Agent or maintainer process: `docs/process/`.
- Repo, model, and content conventions: `docs/conventions/`.
- Audit outputs and cleanup manifests: `docs/audits/`.

Do not create a new durable documentation hierarchy for this cleanup. The
`docs/audits/plans-cleanup/` workspace is only for audit state and cleanup
evidence.

## First-Pass Scope

Start with older March and April `docs/plans/` threads and obvious superseded
pairs. Avoid recent June work in the initial batch unless it is clearly
superseded or already migrated. This reduces the chance of deleting active plans
while still producing meaningful clutter reduction.

The first-pass date scope is based on `latest_file_date`, not the oldest date in
the thread. If a thread groups March and June files, defer it with the June work
unless the thread is an obvious supersession or already-migrated deletion
candidate.

The first pass should prioritize:

- obvious design/implementation pairs where the current code or durable docs
  clearly prove completion;
- files whose content has already been migrated into `docs/user-guide/`,
  `docs/process/`, or `docs/conventions/`;
- older status logs that only describe completed implementation mechanics.

It should defer:

- threads that describe partially implemented features;
- threads whose plan status conflicts with current code;
- threads that contain concepts not yet represented in durable docs;
- broad architecture documents that may still be useful as historical context.

## Subagent Contract

Each subagent should receive a bounded batch of 8 to 12 review threads and return
structured findings only. Reviewers should verify implementation reality from
the repository rather than trusting stale plan status. Evidence should be
concrete enough for the main agent to audit quickly.

Subagents should not delete files, rewrite durable docs, or modify code. They
may recommend follow-up work, but recommendations should distinguish current
gaps from complementary ideas that are outside the original plan.

## Cleanup Policy

The main agent may delete files only when the audit evidence supports
`delete_obvious` or `superseded_delete`. For `keep_historical`, move the source
files to `docs/plans/historical/` and record the move in `actions.jsonl`; this
keeps the files in versioned documentation while removing them from active
`docs/plans/` discovery. For `implemented_needs_durable_docs`, create a
migration checkpoint first: migrate or summarize the durable knowledge, review
that durable-doc change, and only then delete the stale plan files in a later
cleanup action. For `incomplete` and `unclear`, keep the source files and record
the follow-up in the manifest.

The validator should enforce these cleanup invariants from the latest review for
each thread:

- `deleted` actions require latest status `delete_obvious` or
  `superseded_delete`.
- `moved_to_historical` actions require latest status `keep_historical`.
- `migration_checkpoint_created` actions require latest status
  `implemented_needs_durable_docs`.
- `deferred` actions are valid for non-terminal statuses and for explicit
  reconciliation deferrals, but terminal actions resolve earlier deferrals in
  pending reports.
- Action `files` must be a subset of the files named by the latest review for
  that thread.

Deletion commits should be small enough to review by topic or batch. They should
not include `Co-Authored-By` trailers.

## Later Project-Level Cleanup

After the root `docs/plans/` cleanup is working, adapt the same audit manifest
schema to project-level locations. Start with `meta/doc/plans/`, then scan
project directories for `doc/plans`, `doc/specs`, `docs/plans`, and
`docs/specs`. Skip `entities/plans` and `entities/specs` during this effort.

Project-level cleanup should use the same delete-obvious/flag-uncertain policy,
but batches may need to be grouped by project because project documentation
layouts vary.
