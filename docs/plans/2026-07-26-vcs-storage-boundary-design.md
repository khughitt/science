# VCS Storage Boundary Design

**Status:** DESIGN — awaiting implementation plan.
**Branch:** `vcs-boundary`.
**Supersedes:** the ignore-then-pin recommendation in
`docs/audits/downstream-project-conventions/synthesis.md` §7.5, and the
`dir/*` + explicit-negation idiom prescribed in `commands/create-project.md`.
**Resolves:** the deferred follow-ups recorded at the end of
`docs/conventions/data-boundary.md`.

## Problem

Science already has a data-boundary *policy*. `docs/conventions/data-boundary.md`
states it well: durable records tracked, bulky or regenerable payloads ignored,
"make the tracked/ignored boundary legible." What it does not have is any
mechanism that reads that policy and enforces it. The convention doc closes by
listing the missing pieces as deferred:

> Deferred follow-ups include a pre-commit size guard that consumes the same
> policy, validate-time warnings for ignored provenance or evidence records,
> project health summaries for boundary violations, scaffold and `.gitignore`
> template updates, and downstream cleanup sweeps.

Every one of those is still deferred. In the gap, downstream projects drift, and
the drift is invisible and permanent.

### The mechanism

Git's ignore rules are not retroactive. A file committed before its ignore rule
stays tracked forever, and git never reports the contradiction. The tracked set
and the ignored set can overlap indefinitely with no diagnostic.

Files in that overlap are worse than either a tracked file or an ignored one,
because tools that honour `.gitignore` — ripgrep, most editor search, and
**ruff** — stop seeing them. They are version-controlled and simultaneously
invisible.

### Measured state (MM30, 2026-07-26)

MM30 carried **1542 tracked files matching an ignore rule**:

| count | cause |
|---|---|
| 1528 | `data/external/*/raw/` payload committed before the rule existed (742 MB Open Targets, 30 MB CCLE proteomics) |
| 10 | audit records under `doc/audits/**/logs/`, caught by a bare `logs/` pattern |
| 4 | tracked source under `scripts/migration/archive/` and `tests/migration/archive/`, caught by a bare `archive` pattern |

None was deliberate. Three consequences worth recording because they generalise:

1. `rg validate_pilot` returned zero Python hits while the file
   `tests/migration/archive/test_validate_pilot.py` was tracked and present.
2. Un-hiding those files revealed **two had never been formatted** — ruff honours
   `.gitignore`, so the project's "1011 files clean" gate had been silently
   understating its own scope for months.
3. The offending bare `archive` pattern was in the user's **global** excludes
   file, not the project's — so the boundary a project declares can be
   overridden by configuration the project cannot see. A project-local negation
   could not have fixed it: git does not descend into an excluded directory.

### Why the existing surfaces did not catch it

Three shipped surfaces look like they should have, and none could:

- **`data_audit.py` never consults `.gitignore`.** Zero mentions. It walks the
  filesystem and classifies by extension, glob, and size. On MM30 it reports
  **51,073 violations**, of which roughly 45,000 are `.venv`, `.snakemake`,
  `node_modules`, and `.opencode` — files git already excludes correctly. An
  audit that noisy is never run, so the boundary is never enforced.
- **`data_root.py`'s guardrail cannot fire for the recommended layout.**
  `_tracked_paths_under_data_root` returns `[]` when the resolved data root is
  out-of-tree. MM30 resolves to `/data/proj/multiple-myeloma` via the global
  `data.root`, so the guardrail is structurally silent — while the actual
  violations sat in the in-repo `data/external/*/raw/`, which is not the data
  root at all. It fires only in the in-repo mode, where tracked files under
  `data/` are usually legitimate. Backwards on both sides.
- **`audit_project_notes` is `data_cli.py`-only.** Not registered in `validate`,
  not surfaced by `health`. Nothing runs it unless a human types it.

### Why the convention itself points the wrong way

This is not only missing enforcement. The recommended convention actively
teaches the pattern that produces the drift.

`commands/create-project.md` prescribes the `dir/*` + explicit-negation idiom
for any directory mixing regenerable artifacts with sources, and documents the
trap it creates ("git does not descend into a fully-excluded directory, so a
later child `models/.gitignore` with `!*.dot` has no effect and a `git add`
appears to succeed while committing nothing"). The cleaner alternative —
"write regenerable dumps to a separate ignored directory ... and keep `models/`
fully tracked" — is present but demoted to a single trailing line.

Conventions-audit §7.5 goes further and recommends *blessing* the pattern:
"document this as the canonical pattern for 'we ignore this directory but ship
these specific files.'"

The result is that each project hand-curates its own boundary as a ledger of
per-case adjudications. MM30's `.gitignore` is ~60 such lines, most citing a
task id, with the phrase "track only the datapackage.json descriptor" appearing
three separate times. Every new dataset requires another judgement call, and
`git add -f` is the documented escape hatch.

### What good looks like

- Raw data, bulk generated files, and PDFs live outside version control.
- Boundaries align with declared paths, not per-file judgement.
- The declaration is the single authority; `.gitignore` is derived from it.
- A tracked file matching an ignore rule is a hard error, everywhere, always.

## Design

### Declaration

Storage class is declared per path in `science.yaml`. **`versioned` is the
implicit default** — only exceptions are declared, so the block stays small and
self-maintaining rather than accumulating thirty lines asserting that
`entities/` is tracked.

```yaml
boundary:
  roots:
    - path: data/raw
      class: payload
    - path: pdfs
      class: payload
    - path: data/external
      class: manifest
      tracked: [datapackage.json, "*.qa_verdict.json"]
```

| class | meaning | generates |
|---|---|---|
| *(undeclared)* | tracked | nothing |
| `payload` | nothing under this path is tracked | anchored whole-directory exclude |
| `manifest` | payload except the declared `tracked:` globs | descend-preserving idiom |

There is deliberately **no `derived` class**. A "regenerable output" root and a
"raw payload" root differ semantically but are mechanically identical — both are
entirely ignored. Two classes with identical behaviour is a distinction without
a difference, and it would immediately reintroduce a judgement call about which
one a given root is.

### The `.gitignore` contract

Two regions. The hand-written region keeps tooling, OS, editor, and secret
noise; that material was never the problem and routing it through config would
be busywork. The managed block owns the project boundary and nothing else.

```gitignore
.venv/
__pycache__/
.env

# BEGIN science-managed boundary — edit science.yaml, not this block
/data/raw/
/pdfs/
/data/external/**
!/data/external/**/
!/data/external/**/datapackage.json
!/data/external/**/*.qa_verdict.json
# END science-managed boundary
```

Two contract properties:

- **Every generated pattern is anchored.** A declaration names a path, and a
  path generates `/path/`. The unanchored-pattern class of bug becomes
  unrepresentable in generated output.
- **`manifest` never emits a whole-directory exclude.** The `dir/**` +
  `!dir/**/` pair is what keeps git descending so the negations actually apply.
  This is exactly the trap `create-project.md` documents; generating it once
  correctly replaces hand-writing it per project.

Generation is **deterministic**: roots sorted, stable emission order. If the
output flaps, the drift check becomes noise and gets disabled — the failure mode
that killed the previous attempt.

### Commands

| command | purpose |
|---|---|
| `science boundary sync` | rewrite the managed block; `--check` exits nonzero on drift; `--verify-equivalence` proves no ignore decision changed |
| `science boundary check` | fast standalone predicate for pre-commit; two git calls, no config load |
| `science boundary init` | adoption aid: propose a declaration from the existing tree |

`boundary init` is the **only remaining caller of `classify()`**. The heuristic
engine is demoted from enforcement, where its false-positive rate makes it
unusable, to bootstrapping, where a human reviews every proposal before it is
written. That is the job it is actually good at, and one we need regardless in
order to absorb existing hand-curated rules.

### Checks

All four are mechanical. No heuristic participates in enforcement.

| check | scope | severity | predicate |
|---|---|---|---|
| `boundary.tracked-ignored` | all projects | ERROR | a tracked file matches an ignore rule |
| `boundary.generated-drift` | declared only | ERROR | managed block ≠ regenerated block |
| `boundary.declaration-conflict` | declared only | ERROR | an unmanaged rule matches a path under a declared root |
| `boundary.unanchored-pattern` | all projects | WARN | bare directory-name pattern with no leading `/`, in the unmanaged region |

Generated patterns are anchored by construction, so `unanchored-pattern` only
ever inspects the hand-written region and any nested `.gitignore`.

`tracked:` globs on a `manifest` root are matched **relative to that root**, at
any depth beneath it. `datapackage.json` therefore covers
`data/external/opentargets/25.03/datapackage.json` without the declaration
naming intermediate directories.

`boundary.tracked-ignored` runs everywhere with no configuration because it
needs none: it uses the project's own declared boundary rather than guessing,
so it has **zero false positives by construction**. It would have caught all
three MM30 drift classes on the day each appeared.

`boundary.declaration-conflict` is what makes the declaration *the* authority
rather than merely *an* authority. Without it, a hand-added rule below the
managed block silently re-opens per-case adjudication.

Precedent exists: `validate/checks/prereg_vehicles.py` already ships a
fail-closed, gitignore-aware gate (`prereg.vehicle-gitignored`). This
generalises that predicate from pre-registration vehicles to the whole tree.

### Implementation details

Each of these comes from an observed failure, not speculation:

- **`git check-ignore -v` reports negation matches**, prefixed `!`. Those files
  are *not* ignored. Filtering them is mandatory: unfiltered, MM30 reports seven
  false positives from `!data/supp/clean/...`.
- **Report the matching rule's source file and line**, which `-v` supplies free.
  This is what turned "three mystery violations" into "it is
  `~/.gitignore_global:14`" in a single command.
- **`--no-index` is required** for the predicate to see tracked files at all,
  and it brings global excludes into scope. The check must *diagnose* a global
  rule and must never rewrite one — that file lives outside the project and may
  be shared across repositories (in the observed case it was a symlink into a
  dotfiles repo).
- **`sync` manages only the root `.gitignore`.** Nested `.gitignore` files stay
  hand-owned; `check-ignore` already accounts for them when the predicate runs.

### Wiring

- New `validate/checks/boundary.py`, registered in `CANONICAL_CHECKS`.
- All four checks are cheap enough for `--profile commit` (worst case two git
  calls plus a config load), so they run in the pre-commit path rather than only
  on full validate.
- `science health` grows a `boundary` section: whether the project declares
  roots, and its violation count. This is what makes ecosystem state visible
  without per-project archaeology.

### Adoption

Enforcement is split by check kind rather than staged by release. The universal
check ships fail-closed immediately because it requires no configuration and
cannot produce a false positive; the declaration-derived checks activate only
once a project declares `boundary:`.

This deliberately avoids the capability-fit rollout shape, where a fail-closed
gate went loud across every project simultaneously and required a multi-task
cleanup campaign (MM30 t832 → t833 → t856, with 154 warnings ultimately left
demand-gated).

### Migration equivalence harness

Replacing hand-curated rules with a generated block risks silently changing what
is ignored. Comparing `.gitignore` *text* cannot detect this. The harness
therefore compares **ignore decisions**:

1. Enumerate every path in the repository; record each `check-ignore` result.
2. Swap in the generated block.
3. Re-record and diff.

An empty diff proves behavioural equivalence. Any intended change appears as an
explicit, reviewable line.

This is exposed as `science boundary sync --verify-equivalence`, not as a
one-off script: any `sync` that replaces existing hand-curated rules should be
able to prove it changed no ignore decision. `boundary init` invokes it before
writing its proposal.

### Retiring the conflicting convention

Required, or the declaration becomes a fourth opinion rather than the authority:

- `commands/create-project.md` — replace the `dir/*` + negation idiom with the
  declaration; scaffold a `boundary:` block; drop the hardcoded `papers/pdfs/`
  (a convention MM30 migrated off on 2026-07-26).
- `docs/conventions/data-boundary.md` — rewrite *Policy* around the declaration;
  resolve the deferred-follow-ups paragraph.
- `docs/audits/downstream-project-conventions/synthesis.md` §7.5 — annotate as
  superseded.
- `data_audit.py` — make the walk gitignore-aware. That single change takes MM30
  from 51,073 violations to roughly 6,000, and the command is redocumented as
  advisory discovery rather than enforcement.

### Testing

- Golden generated output per storage class.
- **Real-git behaviour test** for the `manifest` idiom: assert via
  `git check-ignore` that a nested descriptor is genuinely visible. String
  comparison of generated text would pass even if the negations silently failed,
  which is the entire trap.
- Integration: a temporary repository containing a tracked-and-ignored file
  produces the ERROR; a clean repository passes.
- Regression pinning the `!`-negation false-positive filter.
- Idempotency: `sync` twice yields no diff.
- Global-excludes case: a rule from `core.excludesFile` is diagnosed with its
  source path and is never rewritten.

## Non-goals

- No history rewriting. Untracking removes files from future clones; existing
  history is out of scope.
- **No automatic `git rm --cached`.** The check reports; humans decide.
  Untracking is destructive, and the correct resolution is often "move the file"
  rather than "untrack it."
- No changes to worktree hydration or the commons data root.
- No `derived` storage class.
- Nested `.gitignore` files are evaluated but not managed.
- The global excludes file is diagnosed but never rewritten.

## Relationship to `atoms`

Orthogonal on the primary axis, and deliberately decoupled. `atoms` guarantees
*when a write lands* — crash-safe multi-path mutation, journaling, rollback.
This design governs *where bytes may live and whether they are versioned*: a
classification and enforcement concern fully solvable with git plumbing today.
`atoms` is pre-implementation; coupling would block a cheap fix on a deep one.
Its own README already files data-VCS composition under "orthogonal ... not a
driver now."

One seam is worth designing toward without building now: both want **declared
roots carrying semantics**. `atoms` has `metadata_root` plus a durability
allowlist keyed on mount configuration; this design adds a storage class per
path. If a single "these roots are payload, those are versioned" declaration
emerges, `atoms` becomes a plausible consumer — it would know which roots need
journaled effects and which are disposable. That is a consumer relationship to
leave room for, not a dependency to build.

## Open questions for the implementation plan

- Ordering of `boundary init` against the MM30 declaration: whether MM30 lands
  as a worked example inside this branch or as a downstream follow-up.
- Whether `science health`'s boundary section should report undeclared projects
  as debt, or stay silent until a project opts in.
