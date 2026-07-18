---
title: Savable archive / mark-superseded plans (save-plan / apply-plan)
status: design
created: '2026-07-18'
---

# Savable archive / mark-superseded plans — Design

**Goal.** Give `science entities archive` and `science entities mark-superseded`
the durable `--save-plan` / `--apply-plan` contract that `entities import`
already has: a *preview* derives a plan that freezes the **complete decision
read set** and the **complete mutation write set** — including exact pre- and
post-states — and `--apply-plan` validates the read/pre-state contract and
writes **only the saved postimages**.

**Why.** A downstream consumer (`natural-systems`, task `t855` / "Plan 1.5")
builds a transaction engine (its "Plan 2") that must replay every curation
mutation byte-exactly so a process killed mid-apply is recoverable. `entities
import` already supports save-plan/apply-plan; `archive` and `mark-superseded`
do not. `archive` reads the clock at apply time (`entities_inventory_cli.py:126`)
and appends a timestamped row to `entities/_archive/archive-index.jsonl`;
`mark-superseded` re-derives its `to_mark` / `to_repair` disposition from a
corpus-wide read set on every call, and its writer stamps `updated` from
`date.today()` (`entities.py:1067`). Neither can be replayed exactly today.

Ships as `science` **0.5.0**; consumed through the delivery gate in §8.

## 1. The authorization model

A saved plan is **untrusted JSON**: any field can be edited after the preview.
Three independent layers authorize an apply, and each answers a question the
others cannot:

1. **Approval envelope — "is this the plan that was reviewed?"** `--apply-plan`
   **requires** an independently supplied `--expected-plan-sha256`: SHA-256 over
   the **exact raw plan-file bytes**, checked **before** JSON parsing (no
   canonicalization, so it matches Plan 2's byte digest with no ambiguity). The
   file is read **exactly once** into a `raw: bytes` buffer; apply refuses unless
   `sha256(raw)` equals the flag, then parses **that same buffer** — never
   reopening the path, so a file swapped between hash and parse cannot slip a
   different plan past the envelope. This is the *only* thing that authenticates **operator
   intent** — which cohort was selected, the frozen timestamp, the reviewed
   report — choices no corpus rederivation can reconstruct (an edited selection
   is just as corpus-valid as the original). `--save-plan` emits this digest
   beside the report; Plan 2 records it at save and supplies it at apply. It is
   not optional: the existing re-derive `--apply` already covers semantic-only
   mutation, so a downgrade path on `--apply-plan` would only hide the guarantee
   in its least visible place.

2. **Corpus gate (A) — "has the corpus drifted?"** *(supersession only.)* A
   digest binds the live corpus to the canonical decision material the plan was
   derived from (§5.2). A mismatch refuses. Archive has no corpus-wide
   derivation, so it has no gate A; its selection re-derivation plus per-path
   pre-state checks (§4.2) are its drift check.

3. **Derivation gate (B) — "do the saved writes match what the sources
   authorize?"** During validation *only*, apply re-derives the expected
   **selected** disposition, the expected postimages, **and the expected
   complete transition surface**, and requires them byte-for-byte equal to the
   frozen plan. Supersession re-derives the disposition from the verified
   decision material and each postimage from the **live source bytes** (bound by
   the write's `pre` fingerprint, §5.3); archive reconstructs rows and the index
   from live sources (§4.2). This closes the circularity a digest leaves open and
   defends against a preview that was wrong at creation.

Execution then writes **only the saved postimages**. Because the saved bytes
equal the re-derived bytes (layer 3), execution faithfully replays what was
reviewed, and a serialization quirk in the writer can never change what lands.

Re-deriving for *authorization* is never re-deriving for *execution*. Two
properties hold the layers together: **pre-state fingerprints gate every write**
(§3.1) and **ownership-scoped rollback** halts rather than clobber a concurrent
change (§3.3).

## 2. Scope boundary — what this does NOT do

`t855` has **no durable journal**, so it cannot perform subprocess-death
*recovery* without duplicating Plan 2.

**In scope (t855):** expose every persistent and transient path an apply may
touch as a declared transition surface (§3.2) so Plan 2 can build write-ahead
intents mechanically; guarantee a killed apply leaves each declared path in a
**recognizable** state (pre / post / modeled intermediate) with **no** undeclared
debris; verbatim replay with three-layer authorization, pre-state gating, and
ownership-scoped rollback.

**Out of scope (Plan 2):** a durable journal and `kill → automatic recovery`; a
true cross-writer lock (§7); the `kill → recovery` acceptance test (wraps the
pinned t855 CLI). Upstream tests kill at every boundary and assert the state is
**classifiable** — not that it auto-recovers.

## 3. Shared primitives

Every persisted model sets `model_config = ConfigDict(extra="forbid")`.

### 3.1 `StateFingerprint`

```python
class StateFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    existed: bool
    type: Literal["file", "dir", "symlink"] | None   # None iff not existed
    content_sha256: str | None
    mode: int | None                                  # st_mode perm bits
    symlink_target: str | None
```

### 3.2 `PathTransition` — the unified declared-surface element

```python
class PathTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["entity-rewrite", "archive-src", "archive-dst",
                  "archive-index", "created-dir"]
    rel_path: str
    pre: StateFingerprint
    post: StateFingerprint
    postimage: str | None = None          # exact bytes, for staged writes; None for rename/mkdir

    # cross-field validators (enforced on load):
    #  - entity-rewrite / archive-index: postimage is not None,
    #      post.existed and post.type == "file",
    #      post.content_sha256 == sha256(postimage.encode("utf-8"))
    #  - archive-src:  post.existed is False (moved away)
    #  - archive-dst / created-dir: pre.existed is False (created)
    #  - created-dir: post.type == "dir", postimage is None
```

The **staging path is NOT a plan field** — it is derived at apply from
`rel_path` plus the batch token (§3.4), never trusted from JSON. `post.mode` is
what the write algorithm (§3.4) must realize; `post.content_sha256` must equal
the hash of `postimage`, so a plan cannot smuggle a `post` that lets the correct
bytes land yet fails verification (which would strand rollback). Gate B
re-derives the entire transition set — every `pre`, `post`, `role`, `rel_path`,
and created directory — and compares, so no executable field is trusted merely
because the plan is self-consistent.

### 3.3 Ownership-scoped rollback

Restore reverts only paths this plan declares. For each persistent path: live
matches the **post** this op wrote → revert to `pre`; live matches `pre` already
→ skip; live matches **neither** → **halt**. Created directories are removed
**bottom-up, only when empty**. A **staging survivor** is deleted only when it
satisfies its declared prefix predicate (§3.4) *and* its persistent target is
still in a state attributable to this op; otherwise **halt** — a staging file
that fails its predicate is interference, not this op's debris. No path outside
the declared surface is written.

### 3.4 Staging, batch token, and mode realization

A kill can land *during* `write()`, before any fsync, leaving a **partial**
staging file — a state no fixed `StateFingerprint` can express. The modeled
intermediate for a staged write is therefore a **prefix predicate**:

```
absent  |  a byte-prefix of `postimage` (0 ≤ n ≤ len)  |  equal to `postimage`
```

The write algorithm, for `entity-rewrite` and `archive-index`:

1. Staging path = `<rel_path>.<batch-token>.tmp`, **sibling** of the target,
   contained, unique, and disjoint from every other staged path.
2. Create it with `O_EXCL` (fails if a survivor from another run exists), write
   `postimage`, `fchmod` to `post.mode`, fsync the file.
3. `os.replace` the staging path onto the target (atomic replacement of an
   existing file, cross-platform), fsync the parent dir.

`os.replace` — not `os.rename` — for staged *replacement*; `os.rename` is
reserved for archive src→**absent**-dst moves (§4.3). The batch token is
supplied by the caller (`--staging-token`, §6) so Plan 2 can predeclare every
staging path `<rel_path>.<token>.tmp` in its write-ahead intents; standalone,
t855 generates one and reports it. `mkdir`'d directories are `chmod`'d to
`post.mode` before verification, since new files and dirs otherwise inherit the
process umask.

### 3.5 Selection contracts

Each plan records how its cohort was chosen, as a discriminated union — what gate
B needs to re-derive the *selected* disposition rather than filtering by the
plan's own (editable) output. The two commands have **different** selection
shapes, so they use **command-specific** unions rather than one shared type:

```python
# archive: --id is authoritative, --status degrades to a guard (archive.py:242)
class ArchiveStatusSweep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["all_by_status"]
    statuses: list[str]              # unique, canonically ordered
class ExplicitArchiveIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["explicit_ids"]
    ids: list[str]                   # authoritative; unique, canonically ordered
    allowed_statuses: list[str]      # the guard each id's live status must satisfy
ArchiveSelection = Annotated[ArchiveStatusSweep | ExplicitArchiveIds,
                             Field(discriminator="kind")]

# mark-superseded has NO status selector (entities_inventory_cli.py:76)
class AllSupersessionMembers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["all"]
class ExplicitSupersessionIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["explicit_ids"]
    ids: list[str]                   # unique, canonically ordered
SupersedeSelection = Annotated[AllSupersessionMembers | ExplicitSupersessionIds,
                               Field(discriminator="kind")]
```

**Model validators** (not the comments above) enforce that every explicit
id/status list is **non-empty, unique, and canonically ordered** — an empty
explicit selection is a state the CLI cannot produce, so the plan model rejects
it on load, and the canonical order makes gate-B equality deterministic.
Selection encodes operator intent, which only the approval envelope (§1 layer 1)
authenticates; gate B uses it to reproduce the *exact* selected disposition.

## 4. Archive capability

### 4.1 Plan schema

```python
class ArchivePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    project_root: str
    op: Literal["archive"]              # unarchive is a separate, later plan kind
    now: str                            # FROZEN ISO-8601 UTC; injected, no apply-time clock
    selection: ArchiveSelection         # §3.5
    moves: list[ArchiveMove]
    index: PathTransition | None = None # role="archive-index", literal postimage bytes; None for an
                                        # EMPTY cohort (no-op plan; legacy `archive` no-ops too)
    transitions: list[PathTransition]   # created-dir entries + per-move archive-src/archive-dst
    preview_report: ArchivePreviewReport  # dry-run review context (§4.4)
    # model_validator enforces the moves↔index invariant: non-empty moves REQUIRE an index; an empty
    # cohort carries neither an index nor any transition. Apply still runs Gate B before the no-op,
    # so an empty saved plan against a corpus that gained an eligible entity is refused as drift.

class ArchiveMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    original_path: str
    archive_path: str                   # = derive_archive_path(original_path); re-derived at apply
    row: ArchiveRow                     # frozen, `now`-stamped (archive.py:25)
```

The index is written as the **literal saved postimage** via a single
`os.replace` (§3.4) — never a per-row append, which can leave a torn final line
after a kill.

### 4.2 Authorization (validation, before mutation)

- **Structural.** Project identity; every path contained + canonical
  (`entity_import._contained`, `entity_import.py:473`); `archive_path ==
  derive_archive_path(original_path)` (`archive.py:65`), re-derived, never
  trusted; a strict `moves ↔ (archive-src, archive-dst) transition` bijection;
  no duplicate `id` / path; staging paths derivable, sibling, disjoint.
- **Gate B (binding).** From the live sources, re-derive the **selected** cohort
  per `selection` (a status sweep re-scans by status; an explicit-id set is
  re-validated against live status, via `_scope_rows_to_allowlist`,
  `archive.py:213`) and reconstruct the **complete** expected `ArchiveRow` for
  each id (with `now` injected), the expected index postimage (live index +
  serialized rows), and the expected `pre`/`post` of every transition. Require
  each byte-for-byte equal to the plan. A plan cannot alter aliases, title,
  history, the selected set, or any fingerprint and recompute its own hashes.

### 4.3 Apply flow

1. §1 envelope (required) → §4.2 structural + gate B. (No gate A — §1 layer 2.)
2. Assert `matches(t.pre, t.rel_path)` for every transition.
3. Snapshot the declared surface (transitions + derived staging paths).
4. Execute: `mkdir` + `chmod` created-dirs; move each src→dst with **`os.rename`**
   (refuse loudly on `EXDEV` — `shutil.move`'s copy-then-unlink fallback breaks
   the atomicity kill-classification needs), fsync both parent dirs; write
   `index.postimage` via the §3.4 staged `os.replace`.
5. Verify `matches(t.post, t.rel_path)` for every transition.
6. On failure → §3.3 rollback.

### 4.4 Preview report vs execution report

Today's dry-run `applied`/`skipped` lists are empty until execution populates
them (`archive.py:266`), so the plan must not persist an execution report it does
not yet have. `ArchivePreviewReport` persists the **dry-run review context** —
the *candidate* id list and the inbound-reference report per candidate — with
dry-run semantics; the frozen *disposition* itself is already the `moves` list.
Apply emits a **separate execution report** (`applied`/`skipped` as actually
performed). The preview report is bound by the approval envelope (§1) and
re-derived at gate B, so a report edited to hide inbound references is refused and
forces renewed review.

## 5. Mark-superseded capability

### 5.1 The problem it solves

`mark_superseded` (`consolidation.py:515`) re-derives the whole disposition every
call via `build_supersedes_graph(load_supersession_inputs(project_root))`. The
read set is corpus-wide: `load_project_sources` (`graph/sources.py:334`) runs
seven storage adapters (markdown over `entities` + `research/packages`, bib,
curie-ref, datapackage, workflow-run, task, code), schema pins, profile
resolution, commons overlays, and the active archive index. Its per-write seal
(`_PreparedWrite`, HMAC keyed by a per-process secret, `entities.py:1000`) is not
serializable.

### 5.2 `SupersessionDecisionMaterial` — the digest must equal the derivation input

A hand-written summary risks being narrower than the real input surface (§5.1).
Introduce a **versioned, serializable** `SupersessionDecisionMaterial` that
`build_supersedes_graph` **itself consumes**, so the digest surface *is* the
derivation surface:

```python
class SupersessionDecisionMaterial(BaseModel):
    model_config = ConfigDict(extra="forbid")
    material_version: int
    entries: list[EntryFrontmatter]    # id, kind, status, superseded_by, relations, path
    resolution: CanonicalResolution    # resolved canonical ids + alias map (sorted)
    mutable_population: list[str]
    archive_population: list[str]       # active archive ids + superseders
    admitted_relations: list[AdmittedEdge]
    defects: list[RelationDefect]      # invalids / unbacked inverses the gate reads
    supported_kinds: list[str]
```

`decision_digest(material) = sha256(canonical_json(material))` — keys sorted,
list order normalized **preserving duplicates**. A match proves the **canonical
decision material** is identical, not that raw file bytes are.

```python
class SupersedePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    project_root: str
    material_version: int
    preview_date: str                  # FALLBACK for a member missing `updated` (§5.4)
    selection: SupersedeSelection      # §3.5
    decision_inputs_sha256: str        # decision_digest at preview time
    to_mark: list[str]
    to_repair: list[str]
    writes: list[PathTransition]       # role="entity-rewrite", one per member
    preview_report: SupersedePreviewReport  # dry-run review context (§5.5)
```

### 5.3 Apply flow

1. §1 envelope (required). Structural: project identity, containment,
   `material_version`/`schema_version` match, no duplicate paths/ids, a strict
   `(to_mark ∪ to_repair) ↔ writes` bijection.
2. **Gate A.** Rebuild `SupersessionDecisionMaterial` from live sources;
   recompute `decision_digest`; refuse on digest or version mismatch.
3. **Gate B — disposition (from decision material).** Re-run
   `build_supersedes_graph` on the verified material, apply `selection` to get the
   **selected** disposition, and require it exactly equal to `to_mark`/`to_repair`.
   Preserve corpus-wide blockers — relation defects and derived `unbacked_inverses`
   still **refuse** (`consolidation.py:615`).
4. **Gate B — postimage (from live source, not decision material).** The decision
   material carries only what graph derivation consumes, *not* each member's body
   or unchanged frontmatter. So for each write, read the **live** source file and
   assert its bytes hash to `w.pre.content_sha256` — this binds the write-source
   identity the material does not carry. Re-render the expected postimage by
   applying the permitted edits to those verified bytes through the shared
   preparation path (§5.4); require it byte-for-byte equal to `w.postimage`;
   re-derive and compare `w.pre`/`w.post`.
5. Snapshot; execute each saved postimage via §3.4; verify `matches(w.post, …)`.
6. On failure → §3.3 rollback.

### 5.4 Injectable-timestamp writer — matching current semantics exactly

Gate B's byte-for-byte compare needs the apply-time re-render to reproduce the
preview's bytes. Exactly **one** thing in today's writer prevents that:
`_prepare_write` **`setdefault`s** `updated` from `date.today()`
(`entities.py:1067`), a fresh clock read each invocation. Everything else is
already deterministic — `_dump_frontmatter` is `yaml.safe_dump(sort_keys=False)`,
and `_parse_markdown_file` (`entities.py:1885`) normalizes the body the *same way
every time*: it `lstrip("\n")`s leading newlines and normalizes line endings via
text-mode reads. That normalization is **not** an instability — it is the byte
output the legacy writer already produces on every edit, so it is fully
compatible with saved-postimage replay.

t855 therefore makes the **minimal** refactor and does **not** switch parsers
(that would be an unrelated, observable behavior change — see the end of this
section):

- extract a **shared preparation function** from `_prepare_write` that **retains
  `_parse_markdown_file`'s existing body normalization** (lstrip + line-ending
  normalization) and all three of its boundary checks — the schema gate
  (`_schema_gate_or_raise`, `entities.py:1072`), prospective-corpus validation
  (`_validate_prospective_write`, `entities.py:1075`), and successor resolution
  (`_resolution_check_or_raise`, `entities.py:1083`);
- make **only** the `updated` default injectable — `date.today()` becomes a
  `preview_date` parameter frozen in the plan; a member that already has the
  `updated` key keeps its value (`setdefault`, unchanged);
- route **preview, legacy `--apply`, and `--apply-plan`** through this one
  preparation path, so all three produce byte-identical output and all three run
  the boundary checks before any mutation.

Gate B compares each saved postimage against **the normalized postimage the
legacy writer would produce** — not against the authored source bytes. The body
does **not** round-trip byte-for-byte: leading newlines are stripped and CRLF is
normalized, exactly as legacy `--apply` already does. Byte comparison is not a
substitute for the boundary — a well-formed postimage can still be an illegal
corpus write. A future move to true body preservation is a separate, deliberate
writer-contract change; the hybrid (preserving only in replay) is **rejected**
because it would create two write semantics.

The test is **presence, not truthiness**: `updated = live[updated] if 'updated'
in live else preview_date`. `setdefault` preserves an existing *falsey* value
(an empty string, say), so `entry.updated or preview_date` would diverge from it
— the render must key on key-presence. Rendering through the actual
`setdefault`-based writer with `preview_date` injected as the default reproduces
this for free, which is what lets gate B re-render byte-identical output and
preserves legacy equivalence with the re-derive `--apply` on an unchanged corpus.

### 5.5 Preview report vs execution report

`SupersedePreviewReport` persists the **dry-run review context** — linear chains,
non-linear components, skipped kinds, blockers, archived/unmanaged targets, and
derived `unbacked_inverses` — with dry-run semantics; the frozen *disposition* is
already `to_mark`/`to_repair`. Today's report populates `applied`/`repaired` only
after execution (`consolidation.py:587`), so those belong to the **separate
execution report** apply emits, not the plan. Today's dry-run report also omits
several review fields; enriching it is part of this tranche. Bound by the envelope
and re-derived at gate B (a report hiding a blocker is refused).

## 6. CLI surface

Mirror `entities import` (`entities_inventory_cli.py:269`):

- `--save-plan PATH` — exclusive-create; `--overwrite-plan` replaces an existing
  plan file, never the corpus. Writes the plan file and emits the report **plus
  the plan's raw-bytes SHA-256** (so Plan 2 / the operator captures the value
  `--apply-plan` will demand); performs **no corpus mutation**.
- `--apply-plan PATH` — consumes a plan and mutates. **Requires**
  `--expected-plan-sha256 SHA` (the approval envelope, §1 — SHA over the raw plan
  bytes, checked before parsing); accepts `--staging-token TOKEN` (§3.4; generated
  + reported if omitted). It **rejects every selector / output option**:
  `--status`, `--id`, `--ids-from`, `--save-plan`, `--overwrite-plan`, and the
  re-derive `--apply` — a replay takes its entire input from the plan and the two
  apply-only flags.
- The existing re-derive `--apply` stays for backward compatibility (the
  non-replayable path); `--save-plan` and `--apply` are mutually exclusive.

## 7. Concurrency precondition

Every check proves equivalence only at the **instant checked**. t855's
precondition is **exclusive project write access during apply**, operator- or
Plan-2-enforced. A lock owned by t855 or Plan 2 serializes only its own
instances; excluding `entity edit`, `unarchive`, consolidation, or manual writes
requires **all** sanctioned Science writers to honor a shared lock. So Plan 2's
lock is honestly **curation-batch serialization**, not a true cross-writer
exclusion; the broader locking contract is out of scope here. `material_version`
lets Plan 2 detect a contract-version skew between a saved plan and the applying
toolkit.

## 8. Delivery & versioning

The `0.4.1 → 0.5.0` bump is **three coordinated edits** (verified present):

- `science/pyproject.toml:3` (package version)
- `.claude-plugin/plugin.json:3` (plugin version)
- `science/tests/test_cli_version.py:27` (the hardcoded `0.4.1` baseline assertion)

`science/tests/test_agent_cli_compatibility.py:193` carries **no** pinned release
value — it checks the command floor stays ≤ the package version — so it runs
**unchanged** and is an acceptance criterion, not an edit.

Then: release-commit convention (message doubles as changelog, per `af67c3df`);
this file is the companion doc. Consumer-side §3.3 delivery gate
(natural-systems): land + push upstream; update the `uv.lock` pin; `uv sync
--frozen`; extend `scripts/__tests__/test_science_cli_surface.py` to assert the
new flags on the **pinned, synced** revision; run consumer integration tests;
`bash validate.sh --verbose` passes.

## 9. Testing

Mirror `tests/test_entity_import.py` / `test_entity_import_cli.py` and
`tests/test_consolidation_mark_superseded.py`:

- **Schema round-trip** — save/load both kinds; `extra="forbid"` rejects unknown
  fields; cross-field validators reject an incoherent `PathTransition`
  (`post.content_sha256 ≠ sha256(postimage)`, wrong role/field combo).
- **Approval envelope** — `--apply-plan` without `--expected-plan-sha256` is a
  usage error; a plan edited in *any* raw byte fails the digest (checked before
  JSON parsing); the un-edited plan passes; `--save-plan` reports the matching
  digest; a plan file **swapped between hash and parse** cannot slip through (the
  single-read regression — hash and parse share one `raw` buffer).
- **Write boundary retained** — a well-formed postimage that is nonetheless an
  illegal corpus write (schema-gate, prospective-corpus, or successor-resolution
  failure) is refused at gate B / the shared prepare function, for both
  `--apply-plan` and legacy `--apply`.
- **Selection authenticity (Critical-1 tests)** — with the envelope, a plan whose
  `selection` or cohort is swapped/extended to another eligible entity is
  refused; a legitimate `explicit_ids` subset applies and equals its
  selection-scoped rederivation (not the full disposition).
- **Transition-surface binding (Critical-2 tests)** — a forged `staging_path`
  cannot be injected (it is derived, not read); a forged `post` fingerprint is
  refused at gate B; a `staging-token` collision with an existing file fails
  `O_EXCL`.
- **Gate-B semantic safety** — an edited `to_mark` / `superseded_by` / `ArchiveRow`
  / index postimage inconsistent with the sources is refused even when internally
  self-consistent; relation defects / unbacked inverses refuse apply.
- **Byte-stable writer** — save-then-apply reproduces the legacy re-derive result
  byte-for-byte; a member lacking the `updated` key gets `preview_date`, not the
  clock. Characterize body **normalization** across all three paths (preview,
  legacy `--apply`, `--apply-plan`): a leading-newline body and a CRLF body are
  normalized identically by each — the writer's normal form, not the authored
  bytes (no body-preservation claim).
- **`updated` presence semantics** — at the render layer (low-level), a
  present-but-empty `updated` is *preserved* (presence, not truthiness).
  Separately: on a schema-backed project an empty `updated` is date-typed
  (`wrapper.py:27`), so the write boundary (§5.4) **rejects** it — the render
  preserving it and the boundary rejecting it are two different layers, tested
  independently.
- **Digest determinism** — stable across runs, order-independent, duplicates
  preserved; a material-bearing frontmatter change flips it; a non-projected
  field does not.
- **Drift rejection** — index changed, src changed, dst appeared, project
  mismatch, `material_version` mismatch, material-bearing change → clean refusal.
- **`os.rename` / `os.replace`** — a simulated cross-device archive move raises
  `EXDEV` loudly; a staged entity/index replacement uses `os.replace` and lands
  atomically; `post.mode` is realized (fchmod/chmod), not umask-dependent.
- **Report binding** — an archive report hiding an inbound reference, or a
  supersede report hiding a blocker, is refused (envelope + gate B).
- **Rollback** — mid-apply failure after the first of two writes fully restores
  the declared surface; a concurrent change to a rollback target, or a staging
  survivor failing its prefix predicate, makes rollback **halt**; created dirs
  removed bottom-up only when empty.
- **Kill-classification** (§2/§3.4) — kill at every boundary (after each move,
  after the index replace, after each entity write, mid-staging with a partial
  `.tmp`); every declared path is in its modeled state and no undeclared debris
  remains. The `kill → auto-recovery` acceptance test is the consumer's.
