# Skills Provenance Coverage — Design

Date: 2026-07-18
Status: design approved; spec under review

## Goal

Make the merged skills-provenance system (registry + `sources:` frontmatter +
three-axis freshness) **load-bearing across the whole skills corpus**. Today only
5 of 41 in-scope leaves declare provenance — all from the baygent pull. This
effort brings every canonical skill to an explicit provenance declaration —
either registered external sources or an explicit internal marker — and teaches
the linter to enforce that coverage, WARN first and then ratcheted to ERROR once
the corpus is clean.

This is **attribution-first**: it completes the dependency tree and makes gaps
visible. It does **not** extend the freshness checker. Tool/spec/API sources are
registered as reference-style records whose freshness reports `not_applicable`.

## Scope

- **In scope:** every canonical `skills/**/*.md`, **excluding only
  `skills/INDEX.md`** (the generated index). 41 files: 7 `SKILL.md` routers +
  34 leaves.
- **Out of scope:** the generated `codex-skills/` tree (produced by
  `codex_skills.py`). The linter already defaults to `--root skills`, so
  `codex-skills/` is never walked; this design does not change that.
- **Out of scope:** any change to `GIT_BACKED_KINDS`, the `_run_git` /
  `fetch_remote_head_sha` freshness machinery, or the `science skills check`
  freshness command. Freshness behavior is unchanged.

## Decisions already made (from brainstorming)

1. **Attribution-first**, no freshness-checker changes.
2. **Enforce coverage** in the linter; land as WARN, ratchet to ERROR.
3. **Explicit `provenance: internal` marker** for source-free leaves (not an
   empty `sources: []`).
4. **`SKILL.md` routers are in scope** — they make the same declaration as
   leaves. A router that materially summarizes external methods declares
   `sources:`; a purely navigational router declares `provenance: internal`.
5. **Taxonomy granularity is `spec` + `software`** — no finer split.

## Architecture

### 1. Provenance states — three valid, one invalid

A new classifier operates on a skill's **already-parsed, valid** frontmatter and
produces one of four outcomes:

| Outcome | Condition | Linter result |
|---|---|---|
| **attributed** | `sources:` is a non-empty list of non-empty strings | no coverage finding; id **resolution** stays with `check_source_refs` |
| **internal** | `provenance: internal` present, `sources:` absent | no finding |
| **undeclared** | neither `sources:` nor `provenance:` present | `missing-provenance` (WARN) |
| **invalid** | malformed `sources:` (not a non-empty list of non-empty strings, incl. `sources: []`), `provenance:` value other than `internal`, or **both keys present** | an ERROR finding (see below); **no** `missing-provenance` |

**Separation of concerns — the classifier declares, the source-ref check
resolves.** Whether the ids in a `sources:` list exist in the registry is *not*
this classifier's job. `sources: [does-not-exist]` is an **attributed**
declaration that additionally yields `unknown-source-ref` from the existing
`check_source_refs`. It must **not** also yield `missing-provenance`.

**No cascading on broken frontmatter.** `missing-provenance` means "valid
frontmatter made no declaration," never "classification was impossible." When a
file has missing/unterminated/unparsable frontmatter, or frontmatter that is not
a mapping (the `missing-frontmatter` / `invalid-yaml` cases already emitted by
`check_frontmatter`), the coverage check emits **nothing** for that file — the
frontmatter finding already speaks.

Invalid provenance *declarations* (contradiction, bad marker value, malformed
`sources:`) are reported as ERROR:
- malformed / empty `sources:` continues to surface via the existing
  `invalid-field` on field `sources` (from `check_source_refs` /
  `leaf_source_refs`); the plan verifies `sources: []` reaches that path.
- `provenance:` with a non-`internal` value, and the both-keys contradiction,
  surface as a new `invalid-provenance` ERROR finding.

In every invalid case the coverage check suppresses `missing-provenance` — an
invalid declaration is not an *absent* one.

### 2. Severity model in the linter

The linter has **no severity model today**: `SkillIssue` carries no severity and
`lint_cmd` does `if issues: raise Exit(1)` — every finding fails the run
(`cli.py`). This effort introduces severity:

- `SkillIssue` gains `severity: Severity` where `Severity = Literal["error",
  "warn"]`, **defaulting to `"error"`** so every existing finding stays ERROR
  with no behavior change.
- Per-rule severity is a **named module constant**. `missing-provenance` is
  emitted at `MISSING_PROVENANCE_SEVERITY`, initialized to `"warn"`. All other
  kinds are ERROR.
- **Text output** appends the severity to each line; **JSON output**
  (`to_json`) gains a `"severity"` key.
- **Exit code** becomes severity-aware: `lint_cmd` exits nonzero iff **any**
  finding has `severity == "error"`. A run whose only findings are WARN
  **exits zero**. (Existing ERROR-only behavior is preserved because all prior
  kinds default to ERROR.)

Chosen over the two alternatives:
- an **audit-only command** — rejected: it would leave provenance *outside* the
  linter, so coverage would never gate.
- a **baseline allowlist** of currently-undeclared files — rejected as
  unnecessary for a 41-file canonical corpus we are sweeping to zero in the
  same effort.

### 3. The ratchet

The final task flips the single named constant
`MISSING_PROVENANCE_SEVERITY` from `"warn"` to `"error"`. This is safe **only
after** the corpus sweep brings `missing-provenance` to zero, so the ratchet is
the last task, gated on a clean repository run. Its test proves the exit-code
flip (undeclared fixture: WARN + exit 0 before, ERROR + exit nonzero after).

### 4. Source-kind taxonomy — two new reference-style kinds

Add to `REFERENCE_KINDS` (freshness `not_applicable`, `last_checked` only, **no**
`upstream_ref`):

- **`spec`** — a standard, specification, or ontology. Examples: the Frictionless
  Data Package spec, the EDAM ontology.
- **`software`** — an attribution/reference to a **tool, library, API, or
  service**, cited generally rather than at a pinned revision. Examples:
  snakemake, marimo, runpod, the `frictionless` CLI, the OpenAlex API, the
  PubMed E-utilities.

**`software` is not an escape hatch from the pinned-revision contract.** The
existing `package-docs` kind (in `GIT_BACKED_KINDS`) remains the kind for
*material adapted from a specific repository revision*, and it keeps its
Git-backed freshness (`upstream_ref` SHA vs remote HEAD). Choose `package-docs`
when a leaf's guidance was lifted from a pinned revision of a repo; choose
`software` when a leaf merely *references* a tool without pinning it. Method
papers stay `paper`; the choice between citing a tool (`software`) and its
method paper (`paper`) is made per source during the sweep, and a leaf may cite
both.

`spec`/`software` records require the same base fields as any record
(`title`, `authors`, `url` https, `kind`, `last_checked`). To make the
`software`-vs-`package-docs` boundary structural rather than advisory,
`validate_record` gains one guard: **`upstream_ref` is rejected on
non-git-backed kinds** (a pinned revision belongs to `package-docs` /
`skill-repo`). This closes the escape-hatch gap — you cannot pin a revision on
a `software` record. A `spec`/`software` record therefore carries no
`upstream_ref` and reports freshness `not_applicable`.

### 5. What `provenance: internal` claims

> `provenance: internal` means the document's substantive guidance is a
> Science-native convention and was **not materially derived from an external
> source**. Merely being maintained in this repository does not make externally
> informed guidance internal.

This is the guard against the sweep degenerating into "mark every router
internal." A `SKILL.md` or leaf that materially summarizes external methods,
tools, or specs uses `sources:` even if most routers ultimately are internal.
The sweep classifies each file on the substance of its guidance, not its
location.

## The sweep — coverage triage in waves

Every in-scope file gets a declaration. Classification is per-file judgment
requiring citation research for the externally-derived leaves (e.g. scRNA-QA →
scanpy/Seurat conventions + a QC method paper; mutational-signatures → COSMIC /
SigProfiler + Alexandrov et al.; frictionless → Data Package spec + the tool).
The plan structures this as **waves by family**, each an independently testable
task that ends with those files declared and the registry extended:

- **Wave A — statistics internal/leaf backfill:** the 9 statistics leaves
  without `sources:` (`bias-vs-variance-decomposition`, `compositional-data`,
  `estimator-certification`, `population-genetics-likelihood`,
  `power-floor-acknowledgement`, `prereg-amendment-vs-fresh`,
  `prereg-defensive-instrumentation`, `replicate-count-justification`,
  `time-series-and-longitudinal-models`) plus `statistics/SKILL.md`. Mix of
  external (textbook/method) and internal (Science-native prereg conventions).
- **Wave B — data QA leaves:** `data/` QA leaves and the nested `expression/`
  and `genomics/` subtrees (tool + method-paper attribution).
- **Wave C — data specs & sources:** `data/frictionless.md` (spec + tool),
  `data/sources/openalex.md`, `data/sources/pubmed.md` (API `software`),
  `data/SKILL.md`, and subtree routers.
- **Wave D — pipelines:** `snakemake` (tool + Mölder et al. paper), `marimo`,
  `runpod`, `pipelines/SKILL.md`.
- **Wave E — research & writing:** `research/` leaves and routers,
  `writing/SKILL.md` (mostly `provenance: internal`; `annotation-curation-qa`
  and any externally-derived summaries use `sources:`).

Per-leaf citation research within a wave is well-suited to parallel subagents
during execution; the controller curates the registry additions.

Each wave's registry additions are appended to `skills/sources.yaml` and must
pass the existing `invalid-source-record` / `unknown-source-ref` checks. Waves
are ordered so the linter stays green (WARN-level `missing-provenance` allowed)
throughout; the ratchet task runs only after Wave E.

## File-change summary

- `science/src/science_tool/skills_lint/lint.py` — add `Severity`, `severity`
  field on `SkillIssue` (default `"error"`) + `to_json` key; add
  `missing-provenance` and `invalid-provenance` to `IssueKind`; add
  `MISSING_PROVENANCE_SEVERITY` constant; add the provenance classifier +
  `check_provenance` (composed into `check_skills`, sharing the parsed
  frontmatter, suppressed on broken frontmatter).
- `science/src/science_tool/skills_lint/sources.py` — add `spec`, `software`
  to `REFERENCE_KINDS`; add the `upstream_ref`-on-non-git-backed-kind guard to
  `validate_record`.
- `science/src/science_tool/skills_lint/cli.py` — severity in text +
  JSON rendering; severity-aware exit code.
- `skills/sources.yaml` — new `spec` / `software` / `paper` records surfaced by
  the sweep.
- `skills/**/*.md` (41 files) — `sources:` or `provenance: internal` on each.
- `science/tests/skills_lint/` — new tests (below).

## Testing

Assertions are kept **separate**, each with its own fixture, so no single test
conflates severity, coverage, and exit code:

- **Classifier unit tests** — the four outcomes from valid frontmatter:
  attributed (non-empty `sources:`), internal (`provenance: internal`),
  undeclared (neither → `missing-provenance`), invalid (both keys; bad
  `provenance` value; `sources: []` / malformed). Assert the undeclared fixture
  yields severity **WARN**, and that invalid fixtures yield an ERROR finding and
  **not** `missing-provenance`.
- **No-cascade unit test** — a file with missing/unparsable frontmatter yields
  the frontmatter finding and **no** `missing-provenance`.
- **Non-double-report unit test** — `sources: [unregistered-id]` yields
  `unknown-source-ref` only, **not** `missing-provenance`.
- **CLI severity test** — a WARN-only lint run **exits zero** and its text +
  JSON output **report severity**.
- **CLI error-exit test** — a run containing any ERROR finding exits nonzero
  (severity-aware exit preserved for existing kinds).
- **Repository coverage test** — the real `skills/` corpus produces **zero**
  `missing-provenance` findings (the sweep is complete). This asserts *coverage*,
  not severity — severity is proven by the fixture tests above, since a clean
  corpus has no findings to grade.
- **Ratchet test** — with `MISSING_PROVENANCE_SEVERITY` promoted to `"error"`,
  the undeclared fixture yields **ERROR** and the run **exits nonzero**.
- **Registry / source tests** — `spec` and `software` records validate; a
  `spec`/`software` record without `upstream_ref` reports freshness
  `not_applicable`; a `spec`/`software` record **with** `upstream_ref` is
  **rejected** by `validate_record`; the freshness axis is unchanged for
  git-backed kinds.

## Non-goals

- No release/tag-based or repo-HEAD staleness for tool/spec sources.
- No new CLI subcommand; provenance coverage lives in `skills lint`.
- No baseline/allowlist mechanism.
- No change to `codex-skills/` generation.
