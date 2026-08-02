# Writer Containment Closure — Design

**Status:** design of record. Two sequenced landing slices, one design.

**Goal:** no writer may turn a base-shape-valid entity record into an invalid one, and a
promotion batch that would do so writes nothing at all.

---

## 1. The gap

`certify_persisted` — the **persisted-shape** certification — is called in exactly two
places, both inside `science/src/science_tool/dag/entity_frontmatter.py`: `render_create` and
`render_update`. No other path that rewrites entity frontmatter certifies persisted shape.

That is a narrower claim than "uncertified". `_validate_prospective_write` (`entities.py:1793`,
used at `:920`, `:1085`, `:1326`) certifies a **different property** on other entity writers —
prospective reference resolution and audit rows — and says nothing about whether the result
satisfies base shape. The two are complementary, and neither substitutes for the other.

Two renderers in `science/src/science_tool/entities.py` carry that traffic:

| Renderer | Reached by |
|---|---|
| `render_entity_source_refs` (`:477`) | `append_entity_source_ref` (`:524`), and directly by reconciliation (`:647`) |
| `render_entity_frontmatter_updates` (`:504`) | resynthesis (`:495`), reconciliation (`:668`) |

**Five workflows**, named by their entry points, not five literal call sites:

| # | Entry point | Renderer traffic | Write style |
|---|---|---|---|
| 1 | `apply_candidates` (`promote.py:400`) | both its MINT-accrual route (`:304`) and its LINK route (`:430`) | immediate |
| 2 | `promote_prose_unit` (`prose_promote.py:148`) | LINK, two refs (`:238-239`) | immediate |
| 3 | `apply_prose_promotion_plan` (`prose_promotion_batch.py:77`) | LINK, two refs (`:135-136`) | immediate |
| 4 | `apply_resynthesis_draft` (`proposition_resynthesis_apply.py:665`) | lineage updates (`:495`) | staged |
| 5 | `apply_canonicalization_plan` (`proposition_reconciliation_apply.py:788`) | **both** renderers — source refs (`:647`) and duplicate supersession (`:668`) | staged |

Workflows 4 and 5 are distinct staged workflows in separate modules, not one item: resynthesis
lineage and reconciliation supersession are planned and applied independently.

Neither renderer is kind-scoped. Promotion targets `proposition`, `question` and
`hypothesis` (`build_targets()`, `promote.py:392`); the two prose paths resolve their
destination through `find_entity`, which reaches any kind.

### 1.1 A guard already predicted this work, and is one writer short

`tests/test_hypothesis_consumers.py:263-276`
(`test_the_OTHER_entity_writer_still_cannot_reach_a_hypothesis`) pins the call-site set of
`render_entity_frontmatter_updates` and says in its own comment that the writer "runs NO
schema or resolution check", that this "is not a hole TODAY because both its callers
operate on PROPOSITIONS", and that it "becomes a hole the day a third caller points it at
a hypothesis, or the day the proposition slice runs — and this is the test that will say
so."

The reasoning is sound and the roster is real. It ranges over one writer and not its
sibling: **`append_entity_source_ref` already reaches `hypothesis`** through promotion
LINK, and `hypothesis` is an armed kind. No record is currently broken by it — the write is
an append that preserves base shape — but the boundary the guard asserts does not hold for
the writer it does not name. A guard that lists its scope has a hole by construction; this
design closes the hole by making the *renderers* certify, so containment no longer depends
on a roster staying complete.

The guard's roster and its comment both need updating in slice 1: the premise "runs NO
schema check" stops being true.

---

## 2. The invariant: a writer may not degrade a record

Inside each renderer, validate the pre-image and the post-image with
`EntityValidator.validate_persisted_base_shape`. **Refuse iff the pre-image satisfies base
shape and the post-image would not.**

Exactly one transition is forbidden:

| Pre-image | Post-image | Result |
|---|---|---|
| valid | valid | write |
| valid | **invalid** | **refuse** |
| invalid | invalid | write |
| invalid | valid | write |

Consequences, stated so a later reader does not mistake them for oversights:

- **A record that already fails base shape stays writable.** 183 records across 13 kinds
  fail it today (measured 2026-08-02 over 8209 records in 40 project roots; 41 of them are
  `question`, a live promotion LINK target). Refusing writes to those would couple this
  work to migrating them. This branch performs **no intentional backfill**: it never sets out
  to repair a record, though a write whose own content happens to satisfy base shape is
  allowed through (the `invalid → valid` row above).
- **This is deliberately weaker than `render_update`, not the same rule.** `render_update`
  calls `certify_persisted` unconditionally, so it **rejects an already-invalid record** —
  that is piece 1's "rejection, not backfill" ruling, and it is what makes a workbench update
  refuse the 769 legacy records rather than migrate them. These renderers cannot adopt it:
  they are kind-agnostic and serve live promotion traffic onto records this branch does not
  repair. The shared principle is only that neither writer backfills.
- **The guard is kind-agnostic** — it applies to every built-in or project-local kind routed
  through these renderers, rather than the two kinds piece 1 contained, and it does not need
  to know which kinds are armed. (For scale: `EntityType` has 52 members and
  `_BUILTIN_MARKDOWN_POLICIES` 37, plus whatever kinds a project declares locally. The guard
  ranges over whatever actually arrives, so no roster of kinds appears in it.)
- **Base shape only.** The typed half of `certify_persisted` needs a `WorkbenchEntity` the
  typed writers already hold and these paths do not. Fabricating one from arbitrary
  frontmatter would put the migration's own guesswork inside a certification.

### 2.1 The post-image is validated after rendering and reparsing

Validate the mapping obtained by parsing the **rendered text**, never the in-memory mapping
that was dumped. `certify_persisted` documents the reason at
`dag/entity_frontmatter.py:210-215`: the round trip is what catches a date the YAML dumper
emitted as a bare scalar, which reloads as `datetime.date` where the schema requires a
string. Validating the in-memory mapping would certify something that was never persisted.

That defect class is real but was the minority of piece 3's corpus: of the 792 records it
repaired, **769 had an empty `title`** and **23 differed in no parsed value at all** — those
23 were date-quoting alone.

**Corrected 2026-08-02, by measurement.** An earlier revision of this section claimed the
date case is what an in-memory check "would miss", and §5 proposed it as the round trip's
certification fixture. It is not, and it cannot be: `validate_persisted_base_shape` refuses a
`datetime.date` **identically** whether it reads the in-memory mapping or the reparsed text,
because `type: string` rejects the date object in both. A test built on it passes under the
mutation and certifies nothing.

The rule stands — validate what will be persisted — but its justification is structural, not
this example: the mapping is not the artifact, and any difference introduced between building
the mapping and emitting the text is invisible to a mapping-reading guard. The certification
fixture is therefore an injected corruption at the render seam (a monkeypatched
`_render_markdown`), which a mapping-reading guard demonstrably lets through. For this dumper
and this parser today, no *naturally occurring* input is known to distinguish the two.

### 2.2 How a refusal surfaces

The renderer **raises** `EntityDegradationError` (new, in `entities.py`, subclassing
`EntityCommandError` so existing `except EntityCommandError` handlers in the prose paths keep
their current shape). The message names the record and the validator's own text, so an
operator sees what base shape objected to rather than a paraphrase.

Naming the record requires a path the text-in signature no longer carries, so both renderers
take a **diagnostic-only** keyword:

```python
def render_entity_source_refs(
    current_text: str,
    refs_to_append: Sequence[str],
    *,
    entity_path: Path,
    as_of: date | None = None,
) -> tuple[str, bool]: ...
```

`entity_path` is used **only** to build the error message. The renderer performs no
filesystem I/O — it neither reads nor writes that path — so text-in/text-out and composition
(§4.6) are unaffected. Requiring it rather than defaulting it to `None` keeps every refusal
identifiable; a planner that has text has a path, since it read the text from one.

Raising rather than returning a refusal keeps the guard unskippable — a caller cannot ignore a
return value it never inspects — and matches `certify_persisted`, which raises
`PersistedShapeError`.

**Translation is every planner's job; aggregation is required only where a batch exists.**
Two distinct obligations, and conflating them would over-promise:

- **Translation (all five workflows, slice 1).** No planner may let `EntityDegradationError`
  reach its CLI. Each catches it and raises its own workflow error.
- **Aggregation (every workflow that processes a batch).** Such a planner catches the refusal
  per planned edit, records it, continues planning so one refusal does not hide the next, and
  raises once naming every refused record. This is the division piece 3 used: the repair
  planner collected refusals and the caller raised once with all of them.

The test is whether more than one record can be refused in a single invocation, and by that
test **four of the five workflows aggregate**:

| Workflow | Batch? | Aggregates | Lands in |
|---|---|---|---|
| `apply_candidates` (promotion) | yes — candidate list | yes | slice 2 |
| prose single-unit + batch promotion | yes — row list | yes | slice 2 |
| `plan_canonicalization_apply` | **yes — selected action set** | **yes** | **slice 1** |
| `apply_resynthesis_draft` | no — one draft | no, translation only | — |

Canonicalization is not single-subject: `plan_canonicalization_apply` loops
`for action in actions` over every selected action, and **both** renderer calls sit inside that
loop (`proposition_reconciliation_apply.py:647`, `:668`), one per canonical and one per
duplicate member. A ten-action set can therefore refuse ten times, and aborting on the first
would make an operator re-run the command once per bad record. Because reconciliation already
has a plan phase, its aggregation lands in **slice 1**, with the translation §2.3 assigns it —
the same edit, extended to collect rather than raise on the first refusal, raising one
`ReconciliationApplyError` that names every refused record.

Resynthesis is the genuine single-subject case: one draft, one original proposition, one
`render_entity_frontmatter_updates` call (`_original_edit`). It owes translation only. If a
later slice gives it a multi-draft batch, aggregation follows then.

### 2.3 The workflow-level error contract, and what slice 1 owes

Each workflow must translate a renderer refusal into the error its CLI already handles.
Subclassing `EntityCommandError` covers the two prose workflows, which catch
`(DecompositionError, EntityCommandError, PromotionApplyError)` (`prose_promote.py:244`,
`prose_promotion_batch.py:141`) and re-raise `ProsePromotionError`.
It does **not** cover promotion: `apply_candidates` lets `EntityCommandError` escape, and the
CLI wraps that call in `except PromotionApplyError` alone (`annotation/cli.py:2640-2642`).

That matters because the slices land separately. **Slice 1 makes the renderers raise while
`apply_candidates` still writes as it goes**, so on its own it would introduce a raw traceback
in the promotion CLI for exactly the case the guard exists to report. Slice 1 therefore adds
the translation — `apply_candidates` catches `EntityDegradationError` and raises
`PromotionApplyError` — and slice 2 replaces it with the aggregated report. This is a
deliberate two-step, recorded so the intermediate state is not mistaken for the final one.

The staged workflows are **not** uniformly covered either, and only one of the two is safe
today:

- `apply_resynthesis_draft` already translates — `_original_edit` wraps its renderer call in
  `except EntityCommandError → ResynthesisApplyError`
  (`proposition_resynthesis_apply.py:493-498`), so `EntityDegradationError` is caught by
  inheritance and surfaces correctly with no change.
- `plan_canonicalization_apply` does **not**. Its two renderer calls
  (`proposition_reconciliation_apply.py:647`, `:668`) sit in no `try`, so
  `EntityDegradationError` would escape as itself rather than as
  `ReconciliationApplyError`. Slice 1 adds that translation.

So slice 1 owes translation in two places — `apply_candidates` and
`plan_canonicalization_apply` — not one, and in the canonicalization case that translation is
also where its per-action aggregation (§2.2) lands.

---

## 3. Slice 1 — the guard

### 3.1 Renderers become text-in / text-out

Both renderers currently take a `file_path` and read their own pre-image. Composition (§4.6)
is impossible under that signature, because every edit would re-read the unmodified file.
They become:

```python
def render_entity_source_refs(
    current_text: str,
    refs_to_append: Sequence[str],
    *,
    entity_path: Path,          # diagnostic only (§2.2); no filesystem I/O
    as_of: date | None = None,
) -> tuple[str, bool]: ...

def render_entity_frontmatter_updates(
    current_text: str,
    updates: Mapping[str, object],
    *,
    entity_path: Path,          # diagnostic only (§2.2); no filesystem I/O
    as_of: date | None = None,
) -> tuple[str, bool]: ...
```

The caller reads. `render_entity_frontmatter_updates`'s unchanged branch returns
`current_text` directly instead of re-reading the file, which also removes a redundant read.

Affected: 4 production call sites and ~12 test call sites across `test_entity_writer.py`,
`test_proposition_resynthesis_apply.py` and `test_hypothesis_consumers.py`.

### 3.2 The shared edit vocabulary

`proposition_resynthesis_apply.py:13-21` already imports six private names from
`proposition_reconciliation_apply.py` across a module boundary. That import list defines the
hoist set by evidence rather than by taste.

**Hoist** to a new `science/src/science_tool/annotation/planned_edits.py`:
`PlannedFileEdit`, `_edit`, `_current_text`, `_sha256_text`, `_path_string`,
`_changed_and_noop_paths`.

**Leave in reconciliation:** `ReconciliationApplyError` and `_live_annotation_index` (its own
domain), `CanonicalizationPreflight` (its fields — `expected_source_refs_by_canonical`,
`action_diagnostics_by_id` — are reconciliation's), and
`_changed_and_noop_paths_from_path_changes` (nothing else imports it; it serves
reconciliation's per-action map).

No transaction framework is invented. The hoist moves generic helpers and nothing else.

**`_current_text` must read with `open(newline="")`, not `Path.read_text()`.** `read_text`
applies universal-newline translation, so a CRLF body would be normalized to LF *before
planning* — a change to bytes the edit never intended, and one the round-trip guard would
then certify as correct. The preserving reader at `entities.py:1920-1923` is the precedent.

### 3.3 What slice 1 closes on its own

The two staged workflows (resynthesis, reconciliation) already plan-then-write, so the guard
contains them the moment it lands. Reconciliation is a batch, so slice 1 lands its
aggregation as well as its translation (§2.2); resynthesis needs only translation, which it
already has. `append_entity_source_ref` survives slice 1 unchanged as
the adapter its current callers need — it reads the file, calls the renderer, writes — and is
**deleted in slice 2** once its production callers are gone.

---

## 4. Slice 2 — preflight the three immediate-write workflows

`apply_candidates` and the two prose loops build a complete plan, aggregate every refusal,
then write. This is the pattern reconciliation already implements and that
`resolve_entity_slug`'s docstring (`entities.py`) already states as doctrine: "a caller
creating many entities in a loop calls this for each planned create up front, and a
predictable naming failure aborts the batch instead of stranding it half-written."
Promotion half-adopted it — it pre-screens slugs, then writes as it goes.

### 4.1 Which failures aggregate, and which may abort

Degradation is not the only deterministic preflight failure. Collision detection, slug
naming, template rendering and target resolution all fail deterministically too, and an
operator who fixes one refusal only to hit the next has not been told the truth about the
batch. The boundary:

- **Candidate-local deterministic errors are collected**, and the batch reports them
  together. This covers `EntityDegradationError`, slug-naming failures from
  `resolve_entity_slug`, LINK target-resolution failures, and the never-overwrite guard at
  `promote.py:296-300`. Planning continues past each one so the report is complete.
- **Environment and target-kind precondition failures may abort planning immediately** — a
  missing or malformed packaged template (`Renderer().sections(kind)`, `promote.py:351-352`),
  an unreadable sidecar, an unresolvable project root. These are properties of the
  environment or of a target *kind*, not of a candidate, and no candidate-level fix exists:
  the operator repairs the installation or the kind's template. They still abort **before any
  write**, so the all-or-nothing property holds either way.

  Note this is a precondition, not "every later candidate would fail" — a malformed
  `question` template does not affect the `proposition` candidates in a mixed-kind batch. The
  justification for aborting is that the failure is not attributable to, or fixable at, the
  candidate level; it is not a claim about how many candidates would raise.
- Only the collected candidate-local set is aggregated. A precondition abort reports one
  error, and says which stage it came from.

### 4.2 What all-or-nothing means, precisely

Atomicity **against deterministic preflight failures only.** The write stage can still fail
partway on I/O or concurrent drift. Reconciliation already models the honest answer at
`proposition_reconciliation_apply.py:806-816`, and slice 2 adopts its error shape verbatim:

```
[stage=write, files_written=N, written_paths=(...)] failed to write <path>: <error>
```

**The write stage publishes planned edits and nothing else.** It calls no renderer, no store
method, and no serializer — every post-image, including the sidecar's and every decomposition
index's, was produced during planning (§4.5). Its whole vocabulary is: publish an update,
publish a create, publish a numeric create.

Three failure modes remain, and the wrapper must cover all three:

| Publish | Raises |
|---|---|
| update — pre-publish hash check, then `atomic_write_text` | `PlannedEditDriftError` (§4.3), `OSError` |
| create — exclusive `open("x")` + `os.link` | `EntityWriteError`, `OSError` |
| numeric create — `claim_number_in_dir` | `EntityCommandError` (the drift it exists to detect), `OSError` |

`PlannedEditDriftError` is new, defined in `planned_edits.py` beside `PlannedFileEdit` (§3.2)
since the precondition belongs to the shared edit vocabulary, and it subclasses
`EntityCommandError` for the same reason `EntityDegradationError` does: existing handlers keep
their current shape. Its message names the path and states that the bytes changed after
planning.

So the wrap set is **`(OSError, EntityCommandError, EntityWriteError)`** — which covers
`PlannedEditDriftError` by inheritance; it is listed above so the table stays a complete
inventory of what the write stage can raise. These are *sibling*
`ValueError` subclasses — `EntityCommandError` (`entities.py:47`), `EntityWriteError`
(`dag/entity_frontmatter.py:314`) and `DecompositionError`
(`annotation/prose_decomposition.py:37`) — so catching one catches neither of the others. An
`EntityCommandError`-only wrapper would let the create publish's own refusal escape naked,
which is the one failure preflight was added to make legible.

`DecompositionError` is **not** in the set, and does not need to be: no `record_promotion`
call survives into the write stage (§4.5). If an implementation leaves one there, the wrap
set is wrong — but the correct fix is to plan it, not to widen the tuple.

If a wrapped failure fires after N files have landed, the operator gets the partial-state
diagnostic rather than a bare error. No claim of transactional rollback appears anywhere in
this design.

### 4.3 A planned create is not a planned update

`PlannedFileEdit` models an update: `_edit` calls `_current_text(path)` unconditionally, so it
cannot represent an absent pre-image, and the established apply loop publishes with
`atomic_write_text` — a temp file plus `os.replace`, which overwrites whatever is there.

Planned MINTs cannot use that path without **losing an invariant the code has today**.
`create_entity_file` (`dag/entity_frontmatter.py:359-388`) refuses to clobber twice over: it
checks `dest.exists()`, then stages to a random temp name opened `"x"` and publishes with
`os.link(staged, dest)`, so a file that appears *between* the check and the publish raises
`FileExistsError` → `EntityWriteError("refusing to create <dest>: it already exists")`. Under
a plan-then-apply flow the window between check and publish is no longer microseconds — it
spans the whole planning phase — so the link-based publish stops being belt-and-braces and
becomes the mechanism that makes preflight safe.

The plan therefore carries two operations, and they apply differently:

| Operation | Pre-image | Publish | On drift |
|---|---|---|---|
| update | required, read once from disk | re-read and compare against `before_sha256`, then `atomic_write_text` | **refuses**: `PlannedEditDriftError`, wrapped per §4.2 |
| **create** | **absent** — asserted, not read | exclusive create (`open("x")` + `os.link`), i.e. `create_entity_file`'s primitive; numeric kinds use `claim_number_in_dir`, which is already exclusive | **refuses**: `EntityWriteError` / `EntityCommandError`, wrapped per §4.2 |

**Updates get an optimistic precondition, for the same reason creates do.** `os.replace`
overwrites unconditionally, so an update planned against bytes that have since changed would
silently discard the other writer's work — and preflight is what makes that race worth caring
about, since the window is now the whole planning phase rather than the microseconds between
a read and a write. `PlannedFileEdit` already carries `before_sha256`, and today **nothing
reads it** (`proposition_reconciliation_apply.py:42` is the only occurrence outside its own
construction). Apply re-reads the file immediately before publishing, compares its hash to
`before_sha256`, and refuses the batch if they differ.

This applies to **every** planned update — entity files, the promotion sidecar, and each
decomposition index — not only to entity records. An index or sidecar clobbered by a
concurrent writer loses exactly as much as a record does.

The two guarantees are not equally strong, and the design should not claim they are. A planned
**create** never becomes an overwrite, full stop: the exclusive `open("x")` + `os.link`
publish is atomic against a concurrent creator, so there is no window in which it can clobber.
A planned **update** refuses drift *observed by the immediate pre-publish check* — compare-then-
`os.replace` leaves a narrow TOCTOU window in which a writer could land between the hash read
and the replace, and that write would still be lost. The check shortens the exposure from the
whole planning phase to a few syscalls; it does not eliminate it. In both cases, when drift is
detected the file on disk is left untouched and the batch reports it.

`PlannedFileEdit` gains that distinction rather than a parallel type — `before_sha256` is
absent for a create, and `_edit` grows a sibling constructor for the create case rather than
calling `_current_text` on a path that does not exist.

### 4.4 The promotion planning contract

`PromotionTarget.mint` is a **writing** function today —
`MintFn = Callable[[PromotionCandidate, list[str], Path, date | None], MintOutcome]`
(`promote.py:258-271`), and `MintOutcome` carries only `(entity_id, created)`. All three
immediate workflows call it. Adding a preflight *around* that contract would leave the writes
inside `mint` and produce a design that looks preflighted and is not.

`mint` is therefore replaced by a **pure planning** function. It performs no filesystem
writes, reserves no number, and returns everything apply needs:

```python
@dataclass(frozen=True)
class PlannedMint:
    entity_id: str                          # "<kind>:<local_part>", the id apply must land
    operation: Literal["create", "accrue"]  # what MintOutcome.created encoded
    path: Path
    post_image: str                         # the exact text to publish
    claim_number: int | None                # set for numeric kinds; None for slug-addressed


# (candidate, source_refs, project_root, as_of, assigned_number, current_text) -> PlannedMint
PlanMintFn = Callable[
    ["PromotionCandidate", list[str], Path, "date | None", int | None, str | None],
    PlannedMint,
]
```

The two added inputs are what keep the target pure; without them an implementation must
re-derive them, and each way of doing that reintroduces a defect this design removed:

- **`assigned_number: int | None`** — the number the *outer* planner allocated in memory
  (§4.7), passed in for numeric kinds and `None` for slug-addressed ones. A target that called
  `propose_number` itself would hand every candidate in the batch the same number, since
  `propose_number` is read-only and nothing has been written yet.
- **`current_text: str | None`** — the destination's **composed** post-image so far (§4.6),
  or `None` when the destination does not exist. Accrual is an update, so it must render from
  what previous edits in this batch already planned for that path; re-reading disk would
  discard them, which is exactly the composition defect §4.6 exists to prevent. The outer
  planner owns `planned_text_by_path` and supplies this value — the target never touches the
  filesystem, so it also cannot hide mutable state of its own.

`operation` is typed `Literal["create", "accrue"]` rather than `str`, so a third value is a
type error rather than a silently unhandled apply branch.

- `operation="accrue"` is the MINT-accrual route (`promote.py:304`): the same claim already
  exists, so the plan is a source-ref *update* to that record, not a create. This is where
  `MintOutcome.created is False` goes, and it keeps the accounting (`report.minted` vs
  `report.linked`) computable from the plan rather than from write side effects.
- `claim_number` is the number `propose_number` allocated in memory (§4.7); apply passes it to
  `claim_number_in_dir`, which is what makes drift refuse rather than renumber.
- `post_image` is rendered during planning, so the §2 guard runs at plan time for accruals and
  `render_create`'s own `certify_persisted` runs at plan time for creates.

`PromotionTarget.mint: MintFn` becomes `PromotionTarget.plan_mint: PlanMintFn`. A writing
`mint` no longer exists on the target, so an implementation cannot retain writes inside it —
there is nothing left to hide them in.

### 4.5 Sidecar and decomposition-index writes are planned, not deferred

A "complete plan" that still calls writers during the write stage is not complete.
Reconciliation already gets this right: it serializes the sidecar **during planning**
(`serialize_sidecar` into `final_texts`, `proposition_reconciliation_apply.py:478`) and the
apply stage publishes that exact text.

Slice 2 does the same for both remaining side stores:

- **The promotion sidecar.** `apply_candidates` currently mutates and writes it after the loop
  (`anno_io.write_sidecar`). Planning serializes the post-image with the backlinks already
  applied; apply publishes it as one more planned edit.
- **The prose decomposition index.** `ProseDecompositionStore.record_promotion`
  (`prose_decomposition.py:211`) is called four times across the two prose workflows
  (`prose_promote.py:186,249`, `prose_promotion_batch.py:111,146`), and it is a
  read-modify-write of one JSON file per source slug. **Multiple rows in a batch share one
  index**, so its post-images compose exactly as §4.6 requires for entity files — planning
  composes the index state across all rows and emits one planned write per index.

This also closes a hole in §4.2's wrap set: `record_promotion` raises `DecompositionError`,
which is neither `OSError` nor `EntityCommandError`. Left in the write stage it would escape
the wrapper and lose the partial-write diagnostic; planned, it fails during preflight where it
is aggregated with the other candidate-local errors.

### 4.6 Planned edits compose per path

Each planner maintains `planned_text_by_path: dict[Path, str]`, initialized from disk **once**
per path, then feeds each post-image into the next edit for that path. One `PlannedFileEdit`
is constructed per path **after** composition, so `before_sha256` is the on-disk pre-image and
`after_sha256` is the composed result.

Two reachable cases make this load-bearing, not theoretical:

- A single LINK appends two refs through two sequential renderer calls.
- Two annotations can LINK to the same existing record; prose rows sharing one decomposition
  index are the same case.

Independent edits computed from the same disk pre-image would each contain only their own
change, and the last write would erase the others.

### 4.7 Numeric mints plan without consuming a number

`_mint_numeric` (`promote.py:341`) calls `reserve_entity` → `reserve_number_in_dir`, which
claims the **next** number and commits an empty placeholder `.md` to back it. Under preflight
that is actively wrong: planning would consume numbers and strand placeholders for a batch
that then refuses. `propose_number`'s docstring says so directly — "calling it from a dry run
leaves an empty entity behind and makes the subsequent apply mint a DIFFERENT number."

Slice 2 adopts the pair `entity_import.py` and `migrate_specs.py` already use:

- **Plan:** call `propose_number(project_root, kind)` **once per kind**, then allocate
  `base`, `base+1`, … in memory. `propose_number` is read-only, so repeated calls before any
  write return the same number — calling it per mint would hand every candidate the same id.
- **Apply:** each assigned number goes through `claim_number_in_dir`, which re-reads the
  archive under a sentinel and **refuses** a number claimed since the preview rather than
  silently taking the next free one. `entity_import.py:10` states the rule as doctrine: "The
  preview is READ-ONLY. Id proposal goes through `propose_number`."

---

## 5. Testing

**The guard, per renderer** — the four transitions of §2 are the test matrix: valid→valid
writes, valid→invalid refuses, invalid→invalid writes, invalid→valid writes. The two
`invalid→` rows are what prove the guard forbids one transition rather than enforcing
validity.

**The rendered text** — corruption injected at the render seam (a monkeypatched
`_render_markdown` that empties `title` after the mapping is built), for both renderers. It
passes if the guard validates the rendered text and **fails with `DID NOT RAISE` if the guard
validates the mapping**, which is what makes it the §2.1 certification. The unquoted-date
fixture this section originally named does **not** discriminate — see the correction in §2.1.

**CRLF** — a record with a CRLF body survives planning byte-for-byte. Fails if `_current_text`
uses `read_text()`.

**Aggregation** — a batch containing **two** unsupported records plus one valid edit: both
refusals are named and **nothing is written**. One refusal does not prove aggregation; it is
equally consistent with abort-on-first. A second case mixes *kinds* of candidate-local failure
— one degradation plus one slug-naming failure — so the report is proven to span the whole
candidate-local set of §4.1 rather than degradation alone.

**Canonicalization aggregation (§2.2, slice 1)** — a selected action set in which **two**
actions each carry a degrading duplicate: `plan_canonicalization_apply` raises one
`ReconciliationApplyError` naming both, and writes nothing. This is the test that fails if the
loop keeps raising on the first refusal, and it belongs to slice 1, not slice 2.

**Precondition abort** — a malformed packaged template aborts planning, reports one error
naming its stage, and writes nothing. This is the §4.1 boundary's other half; without it,
"may abort immediately" is untested and an implementer could aggregate everything.

**Translation, per workflow (§2.3)** — each of the five workflows surfaces its own error type
for a degradation refusal, never `EntityDegradationError` itself. `plan_canonicalization_apply`
is the one that fails this today, so it is the one the test would catch regressing.

**Update drift (§4.3)** — a planned update whose target's bytes change between planning and
apply: the batch refuses with `PlannedEditDriftError` and **the target's new content is
unchanged**. Run it for an entity record, the sidecar, and a decomposition index, since all
three are planned updates and only the first is obviously one. The residual TOCTOU window is
not testable and is not claimed as closed.

**Write-stage wrapping** — a `claim_number_in_dir` drift failure raised *after* an earlier
file has been written carries `files_written` and `written_paths`. An `OSError`-only wrapper
passes the plain `atomic_write_text` test and fails this one, which is the point.

**Create drift (§4.3)** — a planned MINT whose destination is created by another writer
*between planning and apply*: the batch refuses, names the path, and **the intervening file is
byte-for-byte unchanged**. Asserting only that an error was raised is not enough — an
`atomic_write_text` publish would overwrite the file and could still raise later in the batch.
The assertion that fails under `os.replace` is the untouched pre-existing content.

**Create planning has no pre-image** — planning a MINT for a destination that does not exist
succeeds. Fails if `_edit` calls `_current_text` on the create path (`FileNotFoundError`).

**Planning writes nothing (§4.4)** — after planning a batch containing MINTs of both a
slug-addressed and a numeric kind, the entity directories are unchanged and **no number was
consumed**: `propose_number` returns the same value before and after planning. This is what
fails if an implementation keeps writes inside `mint`.

**Sidecar and index are planned (§4.5)** — a batch that refuses during planning leaves the
sidecar and every decomposition index byte-for-byte unchanged. And two prose rows sharing one
source slug produce **one** planned index write carrying both promotions, not two writes where
the second drops the first.

**Composition** — two edits to one path: the composed post-image carries both, and the first
is not lost.

**Numeric mints** — a refused batch consumes no number and leaves no placeholder; a number
claimed between plan and apply refuses rather than renumbering.

**Write stage** — the error carries `files_written` and `written_paths`.

Every guard is certified by mutation: break what it guards and watch a named test fail.

---

## 6. Scope-out

Recorded so a later reader does not mistake these for oversights.

- **No repair of the 183 pre-existing invalid records.** That is the "extend the migration to
  13 more kinds" slice, and it is independent.
- **No typed-shape certification** on these paths — base shape only (§2).
- **No transactional rollback** (§4.2).
- **No arming** of `proposition` or `evidence-line`; neither mixin exists yet.
- **`render_update`'s stale-owned-key hole** stays open. Clearing an owned key leaves the
  stale value (`dag/entity_frontmatter.py:298-300`), and the one-line fix also deletes the
  `legacy_*` triple, so it needs its own pass.
- **`entities.py:317-318`'s stale docstring** — it still names the armed set as "hypothesis,
  concept, method and search"; it has been six kinds since the `finding` slice. Out of scope
  here, worth a one-line fix wherever it is next touched.
