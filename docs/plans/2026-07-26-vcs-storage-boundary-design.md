# VCS Storage Boundary Design

**Status:** DESIGN — implementation planned.
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
   file, not the project's — so a project's effective boundary depends on
   configuration outside the project.

On that third point, precedence runs the other way from what a first reading
suggests, and the difference matters for remediation. A project `.gitignore`
**outranks** `core.excludesFile`, so a project-local negation *can* override a
global rule — but only in one of its two forms:

| negation form | `git add .` | ripgrep |
|---|---|---|
| directory-level (`!/s/m/archive/`) | **stages it** | sees it |
| file-level (`!/s/m/archive/a.py`) | **misses it** | sees it |

Only the directory-level form restores directory traversal. A file-level
negation beneath an excluded parent is the "appears to succeed while committing
nothing" trap in its purest form: bulk staging silently skips the file.

`git check-ignore` is deliberately absent from that table. Its verdict is
**index-dependent** — invoked without `--no-index` on an already-tracked path it
reports the path as un-ignored regardless of the rules — so it answers
"do the patterns match?" rather than "will git surface this file?". Those are
different questions, and only the second one matters here. The authoritative
oracle for reachability is:

```
git ls-files --cached --others --exclude-standard
```

Tracked files plus untracked-and-not-ignored files: exactly the set git will
show you. A file absent from it is unreachable, and this oracle agreed with
`git add .` in every case tested, including the ones where `check-ignore`
disagreed. The design uses it for `boundary.unreachable-tracked` below.

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

#### Root composition and validation

Roots do not compose. A `payload` root at `data` emits `/data/`, which stops
git descending and silently disables every negation a `manifest` root at
`data/external` would generate. Verified:

```gitignore
/data/                                        # payload root at data
!/data/external/**/datapackage.json           # manifest root beneath it
# -> datapackage.json STILL IGNORED (.gitignore:1). Descent never happens.
```

**Nested roots are rejected at load time.** A declared root that is an ancestor
or descendant of another declared root is a configuration error, not a
precedence puzzle. Sibling roots (`data/raw` payload + `data/external` manifest)
are the supported shape and compose correctly. Rejecting is chosen over defining
precedence because the failure is silent when it happens and cheap to forbid.

Generation for a `manifest` root always emits the ancestor re-inclusion form
(`/root/**` + `!/root/**/` + negations), never a bare `/root/`, which is what
makes descent survive. The same construction is what a `payload` root must
*avoid* emitting when any negation could exist beneath it — but since nesting is
rejected, a `payload` root can safely emit the terse anchored form.

`path` validation, all fail-closed at load:

- repo-relative POSIX only; reject absolute paths, `.`, `..`, leading or
  trailing `/`, empty strings, and embedded newlines
- reject git pattern metacharacters (`*`, `?`, `[`, `]`, `!`, `\`) in `path` —
  globs belong in `tracked:`, and a glob in `path` cannot be anchored reliably
- reject duplicate `path` values
- `tracked:` is valid **only** on `class: manifest`; supplying it on `payload`
  is an error rather than a silent no-op

`tracked:` grammar. These become git patterns AND must be evaluated by the
checker, so the grammar is the subset both engines provably share: **literals
(including non-ASCII and Unicode whitespace), leading whitespace, and `*`**.
Reject newlines and control characters, absolute paths, a leading `!`
(negation is the generator's job), a leading `#`, a trailing `/` (these match
files, not directories), an **unescaped trailing ASCII space**, empty / `.` /
`..` path segments, `**`, `?`, character classes, backslashes, and duplicates.
Because backslashes are rejected independently, every trailing ASCII space in
a `tracked:` glob is necessarily unescaped. Other Unicode whitespace is a
literal like any other: `trail.json\u00a0` is matched identically by git and
`PurePosixPath`.

Exclusions fall into two groups, and conflating them overstates the case:

**Engine divergences** — the exclusion is forced, because admitting syntax the
checker evaluates differently from git would let the generator emit a *working*
git rule that `unreachable-tracked` silently never verifies:

| Construct | git | `PurePosixPath.match` (the checker) |
|---|---|---|
| `foo/**/bar.json` vs `foo/bar.json` | matches | does not |
| `?.json` vs `é.json` | `?` is one **byte**, so no match | `?` is one **character**, so matches |
| `foo//bar.json`, `foo/./bar.json` | rule does not fire | segments normalised away, matches |
| `a.json ` (unescaped trailing ASCII space) | ASCII space stripped from the pattern | significant |

**One probe restriction** — `[ab].json` is matched *identically* by both
engines. It is excluded because probe generation cannot synthesise a witness
filename for a character class, so `boundary check --probe` could not verify the
emitted rule. Listing it as a divergence, as an earlier draft did, misstated the
reason.

Everything else is admitted: literals (including non-ASCII and U+00A0), `*`,
and **leading** whitespace are byte-for-byte identical in both engines, `*`
matches leading dots in both, and `!/root/**/ lead.json` really does re-include
and stage ` lead.json`. Each row above and each admitted construct is pinned by
a test that runs *both* engines, so a claim of divergence cannot survive being
wrong.

`unmanaged_allow` grammar is **not** the same, because its entries are matched
against `.gitignore` rule *text* by equality rather than compiled as patterns. A
leading `/` (anchored) and a trailing `/` (directory) are both legal and are the
shapes actually written — `/data/raw/`, `.venv/`. What is rejected is text that
cannot be a rule: empty, control characters, a comment, a negation (allowing a
negation is meaningless — it ignores nothing), or an unescaped trailing ASCII
space. Leading whitespace, Unicode whitespace, and an escaped trailing ASCII
space are all significant rule text and are admitted.

Governed ignore files are byte-valued inputs, not UTF-8 documents. They are
read and written with UTF-8 plus `surrogateescape`, and physical rules are split
only at LF boundaries. Python's `splitlines()` is forbidden here: it treats
characters such as U+2028 as line separators, while git treats
`foo<U+2028>bar/` as one pattern. A CR at the end of a physical line is removed
(including at EOF); an embedded CR remains pattern text. Within each physical
line, only git's own normalization is applied: remove unescaped trailing ASCII
spaces, preserving escaped spaces and every other Unicode whitespace character.

An **empty `tracked:` list is an error**. A `manifest` root that tracks nothing
is mechanically a `payload` root, and silently accepting it would leave two
spellings of one meaning — the sort of ambiguity this design exists to remove.
Omitting `tracked:` entirely on a `manifest` root is the same error.

`unmanaged_allow` entries are **source-aware**. Pattern text alone cannot
identify a rule: `build/` may appear in the root `.gitignore` and in
`inc/shiny/.gitignore` with entirely different scopes, and a text-only entry
would silence both. Each entry therefore names the file it excuses a rule in:

```yaml
boundary:
  unmanaged_allow:
    - ".venv/"                                  # shorthand: source is the root
    - {source: "inc/shiny/.gitignore", pattern: "node_modules/"}
```

A bare string is shorthand for `{source: ".gitignore", pattern: <string>}`,
which covers the common case and keeps the shipped defaults terse; every default
entry is root-scoped. Matching is `(source, pattern)` equality — not glob — so
an entry excuses exactly one rule in exactly one file and cannot quietly widen
as either grows. A `source` naming a file that does not exist, or that is not in
the governed universe below, is an **error**, so the allowlist cannot rot
silently into a set of no-ops.

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
| `science boundary sync` | rewrite the managed block; `--check` exits nonzero on drift; `--verify-current-tree` diffs ignore decisions before/after |
| `science boundary check` | fast standalone gate for pre-commit hooks: runs the two universal checks (`tracked-ignored`, `unanchored-pattern`) only; it loads the declaration once for `unmanaged_allow`, falling back to defaults when unusable |
| `science boundary init` | adoption aid: propose a declaration from the existing tree |

`classify()` keeps exactly two callers: `boundary init` and `data audit`. The
heuristic is removed from *enforcement*, where its false-positive rate makes it
unusable, and retained for **proposal** (`boundary init`, where a human reviews
every suggestion before it is written) and **discovery** (`data audit`, which is
advisory and blocks nothing). No boundary check consults it.

### Checks

All six are mechanical. No heuristic participates in enforcement.

| check | scope | severity | predicate |
|---|---|---|---|
| `boundary.tracked-ignored` | all projects | ERROR | a tracked file matches an ignore rule |
| `boundary.generated-drift` | declared only | ERROR | managed block ≠ regenerated block |
| `boundary.declaration-conflict` | declared only | ERROR | an unmanaged rule matches a path under a declared root |
| `boundary.unreachable-tracked` | declared only | ERROR | an extant file matching a `tracked:` glob is absent from the git-visibility oracle |
| `boundary.ignored-undeclared` | declared only | WARN | an unmanaged **exclude** ignores a project path with no declared root and no allowlist entry |
| `boundary.unanchored-pattern` | all projects | WARN | bare directory-name **exclude**, no leading `/`, in the unmanaged region, not allowlisted |

Two universal checks, four declaration-derived; four ERROR, two WARN.

#### Sign awareness

`unmanaged_rules` returns negations as well as excludes, and the three
rule-text checks need them differently. `declaration-conflict` **records** a
negation: a hand-written pin under a declared root is the per-case exception the
declaration abolishes, and nothing ignore-oriented would otherwise find it. The
other two **skip** negations, because their predicates are simply false of one —
a `!` rule ignores nothing, so it cannot swallow tracked source and cannot
ignore undeclared material. The point is not merely cosmetic: `unmanaged_allow`
rejects `!` patterns by construction, so a finding raised against a negation
could never be silenced.

#### "Universal" means every project, not zero configuration

`unanchored-pattern` runs for declared, undeclared and broken-declaration
projects alike — that is what makes it universal. It nonetheless reads the
allowlist, falling back to the built-in default when there is no usable
declaration.

It has to. Six of the rules in the shipped scaffold (`.venv/`, `__pycache__/`,
`.mypy_cache/`, `.ipynb_checkpoints/`, `*.egg-info/`, `.worktrees/`) are bare
directory names, so a freshly created project emitted six warnings on day one
and then reported itself clean. Anchoring them would be the wrong remedy: a
nested `inc/shiny/.venv/` must still be ignored, so depth-independence is the
*intended* behaviour for tool droppings, and the declaration or canonical
default allowlist has already sanctioned them. Warning about a sanctioned rule,
with advice that would break it, is noise that trains people to ignore the
check.

This is not the built-in-judgement problem returning. The exemption is keyed on
the project's own declaration, not on what a pattern *looks like*; the default
allowlist is simply the scaffold's list, coupled in one place. MM30's bare
`archive` — the case that motivated the check — is not in it and still fires.

#### Source universe

The six checks split into two kinds that must read different sources, and
conflating them is what made the allowlist ambiguous in the first place.

**Rule-text checks** — `declaration-conflict`, `ignored-undeclared`,
`unanchored-pattern` — inspect pattern text, and are scoped to **tracked,
in-worktree `.gitignore` files**: the root file's unmanaged region plus any
nested `.gitignore`. This is the project's shareable, version-controlled
declaration surface, and it is exactly the set `unmanaged_allow` may name.

Explicitly **outside** that universe:

- `.git/info/exclude` — per-clone and untracked, so a finding against it could
  not be fixed in the repository or seen by anyone else
- `core.excludesFile` — machine-wide, and editing it affects every repository on
  that machine, which is not a decision a project may make
- a nested `.gitignore` that is itself ignored (one inside a `payload` root, for
  instance) — untracked, therefore not shareable, therefore not governed

**Effect checks** — `tracked-ignored` and `unreachable-tracked` — use git's
**full effective resolution**, including `.git/info/exclude` and
`core.excludesFile`, because they ask what actually happened rather than what
was declared. A machine-local rule that causes a real defect must still surface;
MM30's global bare `archive` is precisely that case.

The principle: **govern what is shareable, diagnose whatever actually bites.**
An effect check may therefore report a rule that no rule-text check governs and
that science will never rewrite — so its message must name the source file and
line, since remediation is the reader's decision and may lie outside the repo.

Generated patterns are anchored by construction, so `unanchored-pattern` only
ever inspects the hand-written region and any nested `.gitignore`.

`tracked:` globs on a `manifest` root are matched **relative to that root**, at
any depth beneath it. `datapackage.json` therefore covers
`data/external/opentargets/25.03/datapackage.json` without the declaration
naming intermediate directories.

`boundary.tracked-ignored` runs everywhere with no configuration because it
needs none: it compares the git index against the effective ignore sources
(project `.gitignore`, nested `.gitignore` files, and `core.excludesFile`)
rather than guessing from filenames, so it has **zero false positives by
construction** — every hit is a genuine self-contradiction in the repository's
own configuration. It would have caught all
three MM30 drift classes on the day each appeared.

`boundary.declaration-conflict` is what makes the declaration *the* authority
rather than merely *an* authority. Without it, a hand-added rule below the
managed block silently re-opens per-case adjudication.

Its predicate is that an unmanaged rule **matches** a path under a declared
root — not that it wins, and regardless of sign. That distinction is
load-bearing twice over, because `check-ignore` reports only the last matching
pattern and two different things can shadow the rule you need to see.

*Managed rules shadow unmanaged ones.* The managed block is spliced **after**
the hand-written region, so a managed rule always wins and a winner-based
implementation could never report a conflict at all. The unmanaged rules are
therefore evaluated **in isolation**: a scratch repository containing only the
governed `.gitignore` files, with managed-block lines blanked rather than
deleted so reported line numbers still match the real file, global excludes
disabled, and no index. Nested-`.gitignore` scoping survives because the files
keep their relative locations.

*Unmanaged rules shadow each other.* Isolation alone still leaves a last-match
winner among the hand-written rules, and a `!` winner reports the path as **not
ignored**. Given `/data/raw/**` followed by `!/data/raw/**`, git names the
negation and the underlying rule is never seen. So isolation is paired with
**peeling**: each round records the rule reported for every path, blanks those
lines, and asks again, until a round reports nothing new. Each round blanks at
least one line, so the loop is bounded by the number of unmanaged rules and
converges in one or two rounds in practice.

A negation is recorded as a match rather than discarded as a false positive.
`!/data/raw/keep.csv` beneath a declared payload root ignores nothing, so no
ignore-oriented search would ever surface it — yet pinning one file out of a
declared root by hand is precisely the per-case exception this design abolishes.
Flagging the text is the point.

Throughout, git's own pattern engine does all the matching; nothing is
reimplemented.

`boundary.ignored-undeclared` closes the complementary hole. `declaration-conflict`
only inspects paths *beneath a declared root*, so without this check a project
could hand-write `/papers/pdfs/` in the unmanaged region and ignore project
material with no declaration at all — the implicit-`versioned` default would be
quietly false. The escape valve is declarative rather than a judgement call:

```yaml
boundary:
  unmanaged_allow: [".venv/", "__pycache__/", ".env", "node_modules/"]
```

`unmanaged_allow` defaults to a canonical tooling/OS/secret set, so a normal
project starts clean. Reaching zero means either declaring the root or naming
the pattern — both explicit, neither a per-file adjudication. It is a WARN
because it is declaration-derived and an adopter should not be blocked by
pre-existing tooling ignores on day one.

**Implicit-`versioned` semantics begin at enrollment.** In a project with no
`boundary:` block, `/papers/pdfs/` in the hand-written region is not a
violation and is not reported — there is no declaration for it to contradict.
This is the honest reading of the opt-in model chosen for adoption, and it is
stated here rather than left as an inference, because the alternative (a
universal warning keyed on a built-in allowance list) would reintroduce exactly
the built-in-judgement problem the declaration removes. Should undeclared
projects later need to be visible as debt, the mechanism is a new
`boundary.declaration-missing` validation warning — which `health` surfaces
automatically through the existing findings path, with no separate section.

`boundary.unreachable-tracked` is the check that makes the `manifest` class
trustworthy, and it replaces an earlier "ask whether the parent directory is
excluded" formulation that was not mechanically definable: `!build/**/README.md`
has no concrete parent to query.

Asking git directly sidesteps the problem entirely. For every extant file
matching a declared `tracked:` glob, membership in
`git ls-files --cached --others --exclude-standard` is the predicate. This works
identically for literal and glob patterns, needs no pattern analysis, and is by
construction the same question `git add .` asks.

It is an ERROR because its failure mode is maximally deceptive — the file exists,
the declaration says it is tracked material, and bulk staging silently skips it.
It is declaration-derived rather than universal because "which files were
*meant* to be reachable" is exactly what the declaration supplies; in an
undeclared project there is no intent to compare against.

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
- All six checks are cheap enough for `--profile commit` (worst case three git
  calls plus a config load), so they run in the pre-commit path rather than only
  on full validate.
- **No separate `health` boundary section.** `graph/health_checks/validate.py`
  already runs the canonical validation runner and surfaces every non-info
  result, so registering the checks in `CANONICAL_CHECKS` makes them appear
  under `validation` automatically. Adding an independent section would re-run
  the same predicates and double-count their findings. If a boundary rollup is
  wanted later, it must be **derived** from the findings that check already
  collects — filtered by `rule` prefix `boundary.` — never a second execution.

### Adoption

Enforcement is split by check kind rather than staged by release. The two
universal checks ship immediately — `tracked-ignored` fail-closed, because it
requires no configuration and cannot produce a false positive, and
`unanchored-pattern` as a warning. The four declaration-derived checks activate
only once a project declares `boundary:`.

This deliberately avoids the capability-fit rollout shape, where a fail-closed
gate went loud across every project simultaneously and required a multi-task
cleanup campaign (MM30 t832 → t833 → t856, with 154 warnings ultimately left
demand-gated).

### Migration verification

Replacing hand-curated rules with a generated block risks silently changing what
is ignored. Comparing `.gitignore` *text* cannot detect this. The harness
therefore compares **ignore decisions**:

1. Enumerate every path in the repository; record each `check-ignore` result.
2. Swap in the generated block.
3. Re-record and diff.

An empty diff means **no path currently on disk changed its ignore decision**.
It does *not* prove the two rule sets are equivalent: they can agree on every
extant path and diverge the moment a new dataset version, a deeper nesting
level, or an unseen filename appears. Naming it "equivalence" would overstate
what it checks.

It is therefore `science boundary sync --verify-current-tree`, and it is
supplemented by **generated probes** covering the shapes that do not exist yet.
`git check-ignore --no-index` evaluates hypothetical paths, so probes need no
files on disk — verified:

```
data/external/NEW/9.9/datapackage.json     visible
data/external/a/b/c/d/datapackage.json     visible
data/external/NEW/big.parquet              IGNORED
```

For each declared root the harness emits probes for: a file directly under the
root, the same file nested three levels deeper, one probe per `tracked:` glob at
both depth 1 and depth 3, a dotfile, and a payload-extension file. Old and new
rule sets must agree on every probe.

Together the two passes cover the extant tree exactly and the future tree
structurally. Neither is a proof of total equivalence, and the spec does not
claim one. The residual risk is a filename shape no probe anticipates.

That residual risk is **not** caught by `boundary.tracked-ignored`, and an
earlier draft wrongly claimed it was. If a future manifest file is mistakenly
ignored, `git add .` never stages it, so it never enters the index, so a
tracked-versus-ignored predicate can never see it — the identical failure mode
the bulk-staging test exists to expose. `boundary.unreachable-tracked` is the
check that covers it, by asking whether extant files matching a `tracked:` glob
are reachable at all rather than whether tracked files are ignored.

**Transactional behaviour.** `--verify-current-tree` is a verification mode, so
it must not leave a candidate block installed merely because it found a change:

- refuses to run when `.gitignore` has uncommitted modifications, so a failure
  can never discard the user's in-flight edits
- installs the candidate block, records decisions, and **always restores the
  original file** before returning, on both the success and failure paths and on
  exception
- exits nonzero with the decision diff when any path changed, leaving the tree
  exactly as it was found

Committing the new block is `sync` without the flag — a separate, deliberate act.

### Retiring the conflicting convention

Required, or the declaration becomes a fourth opinion rather than the authority:

- `commands/create-project.md` — replace the `dir/*` + negation idiom with the
  declaration; scaffold a `boundary:` block; drop the hardcoded `papers/pdfs/`
  (a convention MM30 migrated off on 2026-07-26).
- `docs/conventions/data-boundary.md` — rewrite *Policy* around the declaration;
  resolve the deferred-follow-ups paragraph.
- `docs/audits/downstream-project-conventions/synthesis.md` §7.5 — annotate as
  superseded.
- `data_audit.py` — re-scope the walk. The noise is not "ignored files" as a
  class; it is ignored files that are **also outside every declared root**
  (`.venv`, `node_modules`, `.snakemake`, `.opencode` — roughly 45,000 of MM30's
  51,073). Pruning all ignored paths would be wrong: a `stranded_record` sitting
  inside an ignored payload root is precisely what the audit exists to find.

  New predicate: **skip a path if it is ignored *and* lies outside every
  declared root; always inspect paths inside a declared root.** For a project
  with no declaration this degenerates to auditing tracked files only, which is
  a defensible floor and is documented as such. The command stays advisory
  discovery, blocks nothing, and keeps its `classify()`-driven quadrants.

### Testing

- Golden generated output per storage class.
- **Real-git behaviour test** for the `manifest` idiom: assert via
  `git check-ignore` that a nested descriptor is genuinely visible. String
  comparison of generated text would pass even if the negations silently failed,
  which is the entire trap.
- **Bulk-staging test, not just `check-ignore`.** For every generated `tracked:`
  glob, assert `git add .` actually stages the file. `check-ignore` and
  traversal disagree for file-level negations under an excluded parent, so a
  `check-ignore`-only assertion would pass on a layout that stages nothing.
- Nested-root rejection: `data` payload + `data/external` manifest fails at load
  with a clear message, and the broken `/data/` + negation output is never
  generated.
- Path validation: absolute, `..`, `.`, trailing `/`, embedded newline, glob
  metacharacter, duplicate path, and `tracked:` on a `payload` root each raise.
- `boundary.unreachable-tracked` fires on a file-level negation beneath an
  excluded parent, stays quiet on the directory-level form, and fires on a glob
  case (`!build/**/README.md` under `/build/`) that no parent-directory analysis
  could evaluate.
- Oracle-versus-`check-ignore` regression: a fixture where `check-ignore`
  reports un-ignored while the file is unreachable, asserting the check follows
  the oracle. Includes the index-dependence case — `check-ignore` without
  `--no-index` on an already-tracked path — so nobody "simplifies" the
  implementation back onto `check-ignore`.
- `tracked:` grammar: newline, control character, absolute path, empty / `.` /
  `..` segment, leading `!`, leading `#`, trailing `/`, unescaped trailing ASCII
  space, backslash, `?`, character class, `**`, duplicate, and empty/omitted
  `tracked:` on a `manifest` root each raise. U+00A0 is admitted and runs through
  both engines.
- `unmanaged_allow` grammar admits leading whitespace, Unicode whitespace and an
  escaped trailing ASCII space; it rejects an unescaped trailing ASCII space,
  comments, negations, empty text and control characters.
- Grammar exclusions are *earned*, not asserted. Every divergent construct and
  every admitted construct is driven through **both** engines for real — the
  matcher, and a throwaway git repository carrying the actual generated rule —
  so a divergence claim that is wrong fails the suite instead of surviving as a
  comment. Leading whitespace was found to be non-divergent exactly this way.
- Adoption contract: a freshly scaffolded project, with the scaffold's own
  `.gitignore`, produces **zero** findings. Six of its rules are bare directory
  names, so this is a real regression risk, not a formality.
- Sign awareness: a negation is reported by `declaration-conflict` inside a
  declared root, and by neither `unanchored-pattern` nor `ignored-undeclared`
  outside one.
- Rule sources: a symlinked `.gitignore` contributes nothing (git applies no
  rules from one), a tracked-but-deleted one contributes nothing, and an
  unreadable one raises rather than reading as empty.
- Environment fidelity: `core.ignoreCase` is inherited by the isolated
  evaluation, with both the case-folding and case-sensitive directions pinned.
- Non-UTF-8 tolerance: a byte-valued `.gitignore` pattern and a non-UTF-8
  filename are both handled, since git handles both. `sync` preserves the raw
  rule bytes and verification restores them byte-for-byte.
- Physical-rule parsing is pinned against real git: U+2028 stays inside one
  rule, a terminal CR is removed, an escaped trailing ASCII space and U+00A0
  remain significant, and only an unescaped trailing ASCII space is removed.
- Conflict detection defeats both shadowing mechanisms: a rule hidden by the
  managed block, a rule hidden by a later hand-written negation, and a standalone
  hand-written negation are each reported; a single rule matching many paths is
  attributed to all of them; and a tree with no matching rule terminates.
- Allowlist source-scoping: identical pattern text in the root and in a nested
  `.gitignore` produces two findings; a root-scoped allow entry silences only
  the root one. A `source` outside the governed universe raises.
- Source universe: a rule in `.git/info/exclude` or `core.excludesFile` produces
  no rule-text finding, but a defect it causes is still reported by
  `tracked-ignored` with its source file and line.
- `--verify-current-tree` restores the original `.gitignore` on the failure
  path, on the success path, and on exception; and refuses to run against a
  dirty `.gitignore`.
- `boundary.ignored-undeclared` fires on an unmanaged project ignore, and is
  silenced by both remedies (declaring the root, and `unmanaged_allow`).
- Probe generation: probes are evaluated with `--no-index` against paths that do
  not exist, and a rule-set change that only affects unseen depths is caught.
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
- The global excludes file is diagnosed but never rewritten. Since a project
  `.gitignore` outranks it, the remediation science *can* offer is a
  directory-level negation in the managed block; editing the user's global file
  stays a human decision, because it affects every repository on the machine.

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

## Resolved decisions

Both questions left open in the first draft are now settled.

**MM30's declaration is a downstream follow-up, not part of this branch.** What
lands here is a sanitized MM30-derived fixture serving as the acceptance case
for `init` proposal, generation across all three classes, probe evaluation, and
migration verification. This keeps the upstream change reviewable on its own
terms and avoids coupling a framework release to one project's cleanup — the
same separation the April conventions rollout got right, where downstream shape
migrations were operator work in downstream repositories rather than science
plans.

**Undeclared projects stay silent in v1.** Implicit-`versioned` enforcement is
scoped to projects containing a `boundary:` block, preserving the opt-in
rollout. If absence later needs to be visible as debt, the mechanism is a
`boundary.declaration-missing` validation warning, which `health` surfaces
through the existing findings path — no separate section, consistent with the
wiring decision above.
