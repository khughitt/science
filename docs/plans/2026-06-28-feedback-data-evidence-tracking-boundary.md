# Feedback: the `data/` ignore boundary orphans durable evidence records

## Status
Proposed — feedback for triage. Not yet accepted; no implementation started.

## Source
Downstream project `natural-systems` (arXiv formula-prevalence research arm), 2026-06-28. Surfaced while
closing out an experiment whose findings cite on-disk artifacts by sha256 — and discovering those
artifacts were untracked.

## Category
`gap` (durable evidence records have no tracked home / no stated convention), with a `friction` tail
(the workaround is per-author `git add -f`, so adoption is silent and inconsistent).

## Context — the deliberate design this feedback must respect

`science_tool/data_worktree.py` defines `DEFAULT_DATA_DIRS = (data/raw, data/processed, data/external)`
and `hydrate_worktree_data(...)`, which "expose ignored local data directories in a worktree via
symlinks." So those three directories are **intentionally** gitignored: they are large, local-first, and
shared across worktrees by symlink rather than by commit. That is a sound design for **data payloads**
and must not be broken.

The dataset-evidence-flow facet (`docs/plans/2026-06-08-dataset-evidence-flow-design.md`) already models
"evidence" — but at the **epistemic** layer (evidence-lines grounding `DatasetUsage`). This feedback is
about a different, **on-disk** sense of the word: the durable record artifacts a workflow emits.

## Symptom — what actually happened downstream

`data/raw` + `data/processed` are ignored wholesale, so the directory boundary sweeps up two
kinds of file that happen to share the subtree:

1. **Payloads** (correctly ignored, correctly symlink-hydrated): `*.parquet/.feather/.pkl/.pdf`, raw
   `**/tex/**` dumps, downloaded datasets — in `natural-systems`, ~8 GB (a 4.1 GB corpus feather, an
   818 MB assessment dump, a 440 MB index pickle, a 570 MB CSV, …).
2. **Evidence records** (wrongly ignored): freeze/manifest/`datapackage.json`, `RESULTS*.md`, QA
   summaries, blind-adjudication packets (README/RUBRIC/validator/worksheet), human + LLM verdicts and
   labels, dataset metadata sidecars, small (<~150 KB) metric/result tables. These are lightweight,
   durable, and the *primary provenance* for findings.

The consequences observed:
- **Findings cite untracked files.** A committed, pushed `finding` recorded sha256s of a freeze file, a
  precision JSON, and a verdicts JSONL that existed only in one local checkout. Provenance that can't be
  fetched from the repo is provenance in name only.
- **Reproducibility/review blind spot.** RESULTS notes, frozen gates, and human adjudication worksheets
  never appear in diffs or PRs.
- **Silent, inconsistent workaround.** The only escape is `git add -f`. In `natural-systems` exactly one
  early subtree (`…/prevalence/headchar-…`) had been force-added; ~470 equivalent evidence files across
  8 other subprojects had not. A manual 5-agent audit this session force-added them (476 files, ~8.3 MB)
  while leaving the ~8 GB of payloads ignored — but that is a one-off cleanup, not a convention.

The root cause is a **boundary mismatch**: the ignore rule is drawn on the *directory* axis
(`data/processed/` vs not), while the axis that matters is *evidence-record vs data-payload*. Those are
orthogonal — a 0.5 KB `freeze.json` and a 4 GB `raw.feather` sit in the same `data/processed/` subtree —
so no directory rule can separate them.

## Goals
- Give durable, lightweight **evidence records** a **tracked** home, without un-ignoring the
  symlink-hydrated payload directories (`DEFAULT_DATA_DIRS` stays ignored).
- Make "track the record, ignore the payload" the **default**, so it doesn't depend on each author
  remembering `git add -f`.
- Provide a migration/hygiene tool so existing projects can be brought into line (and stay there).

## Non-Goals
- Do **not** un-ignore `data/raw|processed|external` wholesale — that breaks `data_worktree`
  hydration and would invite committing GB-scale payloads.
- No change to the epistemic dataset-evidence-flow model; this is purely about on-disk artifact tracking.
- No remote/large-file storage system (LFS, DVC) proposed here — orthogonal.

## Proposal (framework-aware, prioritized)

**P1 — A tracked evidence path distinct from the symlinked payload dirs.** Establish a convention
(and, ideally, have the workflow/datapackage emit-tooling honor it) that **evidence-class outputs**
land in a path **outside** `DEFAULT_DATA_DIRS` and are tracked by default, while **payloads** stay in
`data/raw|processed|external` and stay ignored+symlinked. Two viable shapes:
  - (a) a sibling tracked tree, e.g. `data/evidence/<...>` or top-level `evidence/<...>`, added to the
    `.gitignore`-not-ignored set and excluded from `DEFAULT_DATA_DIRS`; or
  - (b) keep the current layout but teach the emit-side to split: descriptor-class records
    (`datapackage.json`, freezes, RESULTS, QA, verdicts) to a tracked location, resources to the
    ignored one — the Frictionless split (descriptor tracked, resource local/remote) generalized to all
    of `data/`.
  The choice is a framework-design call; (a) is the smaller change and composes cleanly with
  `data_worktree` (the payload dirs it hydrates are unchanged).

**P2 — A size-guard pre-commit hook** as the safety net: reject staged files over a threshold
(suggest 256 KB) unless whitelisted by the evidence-policy patterns. This is what makes a
track-by-default evidence path *safe* — it can't accidentally swallow a large dump.

**P3 — `science data audit`** — exactly the categorization done by hand this session: report
gitignored-but-durable candidates under the policy below, `--fix` to stage them, respecting
`DEFAULT_DATA_DIRS`. This is the migration tool for existing projects (pairs with
`scripts/migrate_downstream_conventions.py`) and a recurring hygiene check.

## Policy spec (validated downstream — the COMMIT vs KEEP-IGNORED rule)

**Track (evidence record):** freeze/manifest/`datapackage.json`; `RESULTS*.md` and `*-report.{md,json}`;
QA summaries (`**/qa/*.json`); adjudication packets (`{README,RUBRIC}.md`, `validate_*.py`,
`*worksheet*.jsonl`); human + LLM verdicts/labels (`*verdict*`, `*label*`, `*-notes.md`, `*majority*`);
dataset metadata sidecars; interpretation `.md`; curated/digitized primary-source tables; small
(<~150 KB) metric/result tables.

**Keep ignored (payload):** `*.parquet/.feather/.pkl/.pdf/.npy/.npz/.tar*/.zip/.mp4/.mat`; raw
`**/tex/**` and other raw source dumps; downloaded dataset payloads; large regenerable derived dumps
(full rankings, embeddings, sampling pools, envelope drafts) above the size threshold.

**Threshold / carve-out:** ≤ ~150 KB lightweight evidence tracks by default; > ~150 KB tracks only if it
is irreplaceable hand-authored evidence (e.g. human annotation worksheets, a seeded study sample
manifest, a finding's sole label-authority file) — `science data audit` should *flag* these for an
explicit decision rather than auto-include.

## Reconciliation with existing machinery
- **`data_worktree.py`:** unchanged for payloads. If P1(a) adds a tracked `data/evidence/` (or
  `evidence/`), it must NOT be added to `DEFAULT_DATA_DIRS` (tracked files can't be symlink-hydrated).
  The audit tool should read `DEFAULT_DATA_DIRS` as the authoritative "this subtree is payload" signal.
- **Frictionless/datapackage:** P1(b) is just the datapackage contract — descriptor tracked, resource
  local — generalized; `datapackage.json` should always be on the tracked side.
- **Migration:** `scripts/migrate_downstream_conventions.py` is the natural carrier for the `.gitignore`
  template delta + an initial `science data audit --fix` pass across downstream projects.

## Open questions (for triage)
1. P1 shape: a dedicated tracked `evidence/` path (a) vs an emit-side descriptor/resource split (b)?
2. Where should the policy patterns + size threshold live so both the pre-commit hook and
   `science data audit` read one source of truth (a `science.yaml` block? a framework default)?
3. Should `science validate` warn when a `finding`/report cites (by sha256/path) a file that is
   gitignored and not under a recognized payload dir — i.e. provenance pointing at an untracked,
   non-payload file? That would catch this class of issue at validate time, where it is cheapest.

## Appendix — downstream evidence
`natural-systems` commits `8ba917dd` (spike evidence) and `bc685f4f` (repo-wide sweep, 476 files /
~8.3 MB tracked, ~8 GB payloads left ignored) are the concrete before/after. The 5-cluster audit's
per-cluster manifests enumerate the exact COMMIT vs KEEP-IGNORED split that this policy formalizes.
