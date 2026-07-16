# Curate Inventory Contract Reconciliation — closing fb-2026-07-10-017

## Status

**Decision-ready.** Docs-only reconciliation. Closes fb-2026-07-10-017 (the
last open item on the InstrumentResult-convergence follow-on list) and splits
two concerns the convergence design conflated under that one id.

## The defect, corrected

`fb-2026-07-10-017` (project `post-acute-infection`, `command:curate`,
category `friction`) reports:

> Phase-1 doc promises the inventory helper returns `long_idle`,
> `missing_related`, unresolved refs, alias-resolutions, and stale-task
> evidence in one payload. The installed `science curate inventory` returns
> only `{agents_md, artifact_counts, artifacts, candidate_signals}`.
> Unresolved-ref and stale-task evidence had to be pulled separately from
> `science health` + manual `git log`. Either align the helper's output keys
> with the command doc or update the doc to match the helper.

This is a **doc↔helper contract divergence**, not a return-shape defect.

### The convergence design mis-scoped this item

`docs/plans/2026-07-11-instrument-result-convergence-design.md` carries **two
different characterizations of the same id**:

- **Lines 82–85** (the "four items remain open" list) frame it as a
  *type-shape / guard-blindness* issue: "`collect_inventory` returns a Pydantic
  model with no status field, so the bare-collection detector cannot see it at
  all."
- **Lines 109–115** frame it *accurately* — "`curate inventory` returning a
  payload that silently omits keys its own spec promises" — and explicitly say
  it "belong[s] to other specs and [is] not in this spec's scope."

The second reading matches the feedback. The first bolted a genuinely separate,
still-open observation (the boundary guard cannot inspect a composite
typed-model return — triage "known gap #1") onto the fb-017 id. This spec
un-conflates them: fb-017 is closed by reconciling the doc; the guard-blindness
observation stays open as its own item (see *Adjacent items kept open*).

### What the two surfaces actually contain

`commands/curate.md` lines 64–71 promise the inventory helper returns "compact
facts only", then lists six categories. The helper
(`science/src/science_tool/curate/inventory.py`) returns
`CurationInventory{project_root, artifact_counts, artifacts, candidate_signals,
agents_md}`, where `candidate_signals` is
`CandidateSignals{missing_related, missing_source_refs, no_outbound_links,
recently_modified, long_idle, no_frontmatter_files}`.

| Doc promise (lines 64–71) | Helper field | Verdict |
|---|---|---|
| artifact counts by class | `artifact_counts` | delivered |
| recently modified and long-idle | `recently_modified`, `long_idle` | delivered |
| missing `related` / `source_refs` | `missing_related`, `missing_source_refs` | delivered |
| documents with no outbound links | `no_outbound_links` | delivered |
| unresolved refs and alias-resolutions | — | **absent** |
| candidate stale-task evidence | — | **absent** |
| *(not promised)* | `no_frontmatter_files` | **delivered but unlisted** |

The doc is also internally contradictory: "compact facts only" while promising
unresolved-ref and stale-task evidence — precisely the cross-cutting signals
that other subsystems own.

### Where the two absent signals actually live

- **Unresolved refs** are already a first-class instrument:
  `collect_unresolved_refs -> InstrumentResult[UnresolvedRef]`
  (`graph/health_checks/unresolved_refs.py`), surfaced by `science health`,
  which Phase 1 **already runs** (`commands/curate.md:32`). Duplicating this
  into the inventory helper would be two code paths computing the same facts —
  the exact divergence the toolkit-convergence umbrella exists to kill.
- **Alias-resolutions** exist only as internal machinery
  (`graph/reference_resolution.py`, `_authored_aliases` in `graph/sources.py`);
  there is no user-facing report. The doc already hedged this with "if
  available".
- **Stale-task evidence** is genuinely unowned as a deterministic surface.
  `/science:review-tasks` already performs the *semantic* detection ("Should be
  `done` — implementation evidence found", source-ref / recent-commit checks)
  but is entirely agent-led — no CLI helper backs it. The feedback author fell
  back to manual `git log`.

## Resolution — reconcile the doc to the helper

Docs-only for behaviour: **no change** to `curate/inventory.py` or its tests.
Two files change in lockstep, plus historical banners:

1. `commands/curate.md` — the authored source (lines 64–76).
2. `codex-skills/science-curate/SKILL.md` — the **committed Codex mirror**,
   regenerated from (1), not hand-edited. `codex-skills/science-curate/SKILL.md`
   lines 183–196 carry the identical broken contract, and
   `science/tests/test_codex_skills.py` byte-compares the committed mirror
   against a fresh generation, so editing `commands/curate.md` without
   regenerating **fails that test**. Regenerate via
   `scripts/generate_codex_skills.py`.

### Design principle for the rewrite

The original report saw only the *top-level* JSON keys and could not tell that
`recently_modified`, `long_idle`, `missing_related`, etc. live under
`candidate_signals`. So the replacement does not merely list signal names — it
gives each signal's **exact JSON property path**, which is what actually
resolves the reported confusion.

### The full replacement text (authored here, applied by the plan)

`commands/curate.md` lines 64–76 (and the generated equivalent mirror block —
not byte-identical: the generator rewrites `/science:review-tasks` to
`science-review-tasks`, as the committed mirror already shows at
`SKILL.md:328`) become:

> The inventory helper returns compact corpus facts only. Each signal is a
> property of the JSON payload at the path shown:
>
> - `artifact_counts` — counts by artifact class (top-level object).
> - `candidate_signals.recently_modified` / `candidate_signals.long_idle` —
>   recently modified and long-idle artifact paths.
> - `candidate_signals.missing_related` /
>   `candidate_signals.missing_source_refs` — artifacts missing `related` /
>   `source_refs`.
> - `candidate_signals.no_outbound_links` — artifacts with no outbound links.
> - `candidate_signals.no_frontmatter_files` — Markdown under `entities/` that
>   lacks YAML frontmatter (entity-file drift).
> - `agents_md` — per-project `AGENTS.md` / `CLAUDE.md` / `core/decisions.md`
>   state (see the `agents-md` theme below).
>
> The helper does **not** recompute cross-cutting signals owned by other
> commands this phase already runs:
>
> - **unresolved refs** — read the `unresolved_refs` array from the
>   `science health --format json` output above; the inventory helper does not
>   duplicate them.
> - **alias-resolutions** — no user-facing report currently exists; the
>   reference-resolution machinery is internal only, so treat this as
>   unavailable.
> - **stale-task evidence** — semantic and out of the inventory's scope; defer
>   to `/science:review-tasks` (source-ref / result-manifest / recent-commit
>   judgement). No deterministic stale-task surface exists yet.
>
> `candidate_signals.no_frontmatter_files` lists only Markdown under
> `entities/`; treat each as a missing-metadata candidate unless the file is
> legitimately prose (for example an `entities/**/README.md`). It never
> contains `doc/plans/` or `doc/reports/` paths — the helper scans only the
> canonical entity home.

This corrects three things the old text got wrong: it drops the two
never-delivered promises (unresolved-refs/alias-resolutions, stale-task
evidence), it adds the delivered-but-unlisted `no_frontmatter_files`, and it
replaces the stale lines 73–76 paragraph — which discussed `doc/plans/` /
`doc/reports/` files that the `entities/`-only scan (`inventory.py:77,153`) can
never surface.

## Record-correction (so nothing is silently dropped)

The convergence design carved out its follow-on items with the explicit
principle that none be "silently dropped". Closing fb-017 must therefore split,
not erase, the two concerns it was conflated with. **Three** historical
documents currently mis-state this id and each gets a correction:

1. **`2026-07-11-instrument-result-convergence-design.md`** — banner marking
   fb-2026-07-10-017 CLOSED by this doc-reconciliation, and stating that the
   guard-blindness observation attached to it in lines 82–85 is a *separate*
   item that remains open (it is **not** closed by this spec).
2. **`2026-07-11-instrument-triage.md`** — "known gap #1" (line 172) says guard
   blindness "is exactly fb-2026-07-10-017". That equation is the conflation
   itself. Add a supersession note: fb-017 is the contract divergence (now
   closed); the guard-blindness gap is a *distinct* open item that merely shares
   the module.
3. **`2026-07-11-instrument-result-convergence-plan.md`** — Task 10 Step 2
   (line ~2100) describes fb-017 as "missing `unresolved-ref` / `stale-task` /
   `long_idle` keys". `long_idle` is **delivered**
   (`CandidateSignals.long_idle`); only unresolved-refs and stale-tasks were
   absent. Add a supersession note correcting the key list and pointing to this
   spec.
4. **Adjacent items kept open** (below) get their own recorded homes so they
   survive fb-017's closure.

## Adjacent items kept open (named, not silently dropped)

- **Composite-instrument guard blindness (triage "known gap #1").** The boundary
  guard's bare-collection detector cannot inspect a typed-model return, so
  `collect_inventory` — and any future composite-payload instrument — could
  return a clean-looking empty payload when it never ran, and the guard would
  not catch it. This is real and independent of fb-017. It also has a concrete
  live symptom: the CLI `inventory` command's `--project-root` lacks
  `exists=True` (`curate/cli.py:17`), unlike `consolidation-candidates`
  (`:50`), so a typo'd path yields a valid, empty inventory rather than an
  error. Kept open as its own item; **out of scope here.**
- **Deterministic stale-task-evidence instrument.** A helper examining open
  tasks' `source_refs` / result-manifests / recent commits to emit
  candidate-stale evidence, serving both curate Phase 1 and
  `/science:review-tasks`. New tooling the feedback surfaced but which is not
  required to close fb-017. Recorded as a scoped follow-up for a separate
  brainstorm; **out of scope here.**

## Out of scope

- Any change to `curate/inventory.py`, `CurationInventory`, or `CandidateSignals`.
- Adding a status/`unwired` axis to the inventory payload (that is the
  guard-blindness item above, not fb-017).
- Building the stale-task-evidence instrument.
- Adding `exists=True` to the CLI `--project-root` (belongs to the
  guard-blindness item).

## Validation

Docs-only for behaviour; the one test that runs is the existing Codex
mirror-consistency check. Verification is:

1. The three **obsolete promise sentences** are gone from both
   `commands/curate.md` and `codex-skills/science-curate/SKILL.md` — assert on
   the exact sentences, not bare tokens, because the corrective replacement text
   deliberately mentions "unresolved refs", "stale-task", and
   `doc/plans/`/`doc/reports/` in redirect/clarification context:
   - `unresolved refs and obvious alias-resolutions if available`
   - `candidate stale-task evidence from direct source refs or result manifests`
   - `Legacy \`doc/plans/\` and` (the stale `no_frontmatter_files` legacy-prose
     paragraph)

   Each exact sentence returns no `rg` match in either file.
2. Every inventory-promise property path maps one-to-one to a
   `CandidateSignals` / `CurationInventory` field (manual field-by-field check
   against `curate/inventory.py`): `artifact_counts`, `candidate_signals.{recently_modified,
   long_idle, missing_related, missing_source_refs, no_outbound_links,
   no_frontmatter_files}`, `agents_md`.
3. The Codex mirror is regenerated from source and
   `cd science && uv run --frozen pytest tests/test_codex_skills.py` passes
   (the byte-compare test that would otherwise flag a hand-edited or
   un-regenerated mirror).
4. All three historical correction notes are present (rg the banner text in
   `2026-07-11-instrument-result-convergence-design.md`,
   `2026-07-11-instrument-triage.md`, and
   `2026-07-11-instrument-result-convergence-plan.md`).
5. `git diff --check` is clean.
