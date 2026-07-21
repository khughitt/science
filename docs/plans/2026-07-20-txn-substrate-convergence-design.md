# Recoverable filesystem effect engine — design

**Date:** 2026-07-21
**Status:** Draft for owner review
**Scope:** durable filesystem transaction engine plus archive/import/supersede adoption
**Package:** `science` (`src/science_tool/`, tests, saved-plan schemas)

> This design supersedes the earlier “transaction substrate convergence” architecture at this path
> before implementation began. The earlier reviews remain useful: their capture, containment,
> no-clobber, durability, restoration, authentication, and test findings are incorporated here. What
> changes is the ownership boundary. Family mutators no longer orchestrate shared primitives with
> callbacks and an in-memory tracker; they compile authenticated intent into one effect protocol
> executed and recovered by one durable engine.

## 1. Decision

Build a **recoverable filesystem effect engine** over Science’s existing file-backed project model.

Archive, import, cohort import, and supersede keep their domain-specific planners and saved plans.
After saved-plan authentication, a thin family adapter compiles the plan into an internal,
validated `TransactionSpec`. A single executor exclusively owns filesystem mutation, write-ahead
journaling, durability, rollback, recovery, and scratch paths.

The filesystem does not provide atomic visibility across multiple paths. The engine therefore does
not claim ACID transactions. Its contract is:

> Every interruption leaves a state that can be classified from durable evidence, safely completed
> or rolled back when attributable, and otherwise halted without overwriting unknown data.

The default recovery policy is conventional write-ahead-log policy, qualified by external drift:

- no durable `COMMITTED` decision → undo every transaction-owned mutation; preserve a safely
  classified no-clobber blocker and finish with a refused outcome;
- durable `COMMITTED` decision → preserve the final state and finish cleanup;
- any unattributable state → halt without mutation and preserve evidence.

## 2. Problem

Science mutators perform coordinated changes across multiple files and directories. A saved plan
freezes what the user authorized, but several independent events can intervene during application:

- Dropbox or another process can modify a path after planning or capture;
- a Python exception can occur after some effects have landed;
- the process can be killed between a mutating syscall and its durability step;
- power loss can retain either side of a publication boundary;
- a later invocation must distinguish the transaction’s work from an unrelated writer’s work.

The shipped code has two execution dialects. Archive and supersede use `PathTransition` and shared
helpers in `plan_common.py`; import has a private snapshot, restore, and written-path restriction.
The earlier convergence design would have unified their primitives but left each family responsible
for ordering effects and marking an in-memory ownership tracker. A later durable-batch layer would
then have introduced a second execution authority: the write-ahead journal.

That split is the architectural defect addressed here. The journal and executor must own execution
from the start. Shared primitives alone are not the transaction boundary.

## 3. Guarantees and non-guarantees

### 3.1 Guarantees

For a valid, authenticated transaction:

1. **Declared persistent surface.** Every persistent path mutation is represented by an effect and
   agrees with the family plan’s declared initial/final transition surface.
2. **Boundary authentication.** Saved external plans are re-derived and checked before compilation.
3. **Coherent rollback material.** A regular file’s retained bytes and fingerprint come from one
   no-follow file descriptor.
4. **Optimistic concurrency without destructive check/use gaps.** Capture verifies the frozen
   precondition. Replacement, deletion, and movement then transfer the actual live directory entry
   atomically into an engine-owned destination before validating it, so a last-instant writer is
   preserved rather than overwritten or unlinked.
5. **No-clobber creation.** File, directory, and move destinations are never silently replaced.
6. **Write-ahead ownership.** Durable effect state makes every interrupted effect conservatively
   classifiable without relying on a process-local callback.
7. **Durability ordering.** Data is durable before publication; moved destinations are fsynced
   before source parents; journal intent is durable before mutation.
8. **Restartable rollback.** Restoration uses staged publication or exchange for files and
   symlinks, quarantines created directories before exact-empty removal, and reconciles attributable
   scratch survivors.
9. **Evidence-preserving halt.** An observed state outside an effect’s declared state machine is not
   overwritten or deleted automatically.
10. **Mechanically enforced choke point.** Family modules cannot directly invoke filesystem
    mutation APIs or private effect primitives.

### 3.2 Non-guarantees

- Noncooperating writers are not locked out. They can cause clean refusal or a recovery halt.
- Multiple persistent paths are not instantaneously visible as one atomic update.
- Fingerprint-equivalent delete-and-recreate activity by an external writer is not distinguishable
  from the declared state; authority is defined by the frozen state contract, not inode provenance.
- A writer holding an open descriptor to an entry after atomic displacement can continue changing
  the quarantined inode. The engine preserves a diverged quarantine object instead of deleting it,
  but cannot make that writer participate in the transaction.
- Arbitrary corruption or deletion of `.science/transactions/` is not automatically repaired.
- Git history publication is not part of this design.

## 4. Architecture boundary

```text
family apply entry point
    ↓
engine coordinator acquires project lock and resolves any active transaction
    ↓
family authenticator → family adapter → validated TransactionSpec
    ↓
engine prepares journal → executes effects → commits or rolls back
```

### 4.1 Family planners and authenticators

Family code owns domain decisions: entity numbering, rendering, reference selection, archive
destinations, cohort structure, and user-facing diagnostics. Saved plans remain family-specific
public wire formats.

On `--apply-plan`, the family authenticator re-derives the plan from persisted decision inputs and
requires the saved and fresh authoritative surfaces to match. Import must have the same Gate-B
surface authentication as archive and supersede, including the rewrite-to-edit bijection.

### 4.2 Family adapters

An adapter deterministically compiles an authenticated family plan into `TransactionSpec`. It does
not mutate the filesystem, create scratch objects, or make recovery decisions. Compiling the same
authenticated plan twice produces byte-identical canonical output.

### 4.3 Coordinator, executor, and recovery engine

The family apply entry point supplies pure authentication/compilation work to the engine coordinator.
The coordinator acquires the project lock first, resolves any active transaction, and only then runs
authentication and compilation against the settled project state. A successful recovery may be
followed by the requested operation, but its saved plan is always re-authenticated after recovery;
a recovery halt prevents compilation and execution.

Only the engine may:

- create or mutate transaction metadata;
- capture rollback contents;
- derive staging paths;
- call effect implementations;
- update execution state;
- roll back or recover an interrupted transaction.

Family code receives a domain-level outcome after the transaction reaches a durable terminal
decision. It never receives mutable ownership state and never supplies commit callbacks.

### 4.4 Public versus internal contracts

`PathTransition` remains the saved-plan declaration of a persistent path’s initial and final state.
It is not the execution language. Effect ordering, intermediate states, scratch paths, journal
generations, and recovery strategies remain internal and are frozen in the journal only when an
application begins.

This keeps engine mechanics out of public plan schemas and prevents observable internal ordering
from becoming an accidental saved-plan compatibility contract.

## 5. Transaction model

### 5.1 `TransactionSpec`

The internal specification contains:

- a schema version;
- family and authenticated-plan digest;
- project-relative declared initial/final transitions;
- an ordered sequence of typed effects with stable effect IDs;
- effect dependencies where sequence alone is insufficient;
- referenced content hashes and exact modes;
- the required filesystem capability set.

The compiled specification is deterministic and contains no runtime transaction ID. Preparation
binds it to a fresh transaction ID in the journal record; scratch paths derive from that ID plus the
stable effect ID. No absolute path is serialized. Resolution happens against the locked project
root.

### 5.2 Effect variants

The closed initial effect set is:

```python
Effect = (
    ReplaceFile
    | CreateFileNoClobber
    | DeletePath
    | MoveNoClobber
    | CreateDirectory
)
```

Each effect names all persistent paths it can mutate, exact before/after fingerprints, any content
payload, and every recognized multi-path intermediate state. A move is one effect over a source and
destination, not two transitions connected through callbacks.

The initial variants do not recursively snapshot directory trees. `CreateDirectory` is
absent-to-empty-directory, `MoveNoClobber` accepts regular files, and `DeletePath` accepts file or
symlink entries. Arbitrary directory-tree movement, replacement, or deletion requires a later effect
variant with an explicit recursive content model.

Restoration is an engine operation, not a forward family effect. It consumes journaled state and
the same atomic publication kernel.

### 5.3 Repeated paths

The model permits a path to appear in multiple ordered effects. Validation requires a continuous
timeline: an earlier occurrence’s post-state equals the next occurrence’s pre-state. The journal
retains the content needed to materialize every state in that timeline.

The initial rollback surface is separate from occurrence-local preconditions. This removes the
earlier single-snapshot ambiguity that forced globally unique `rel_path` values.

### 5.4 Compilation validation

Before any journal or blob write, validation proves:

- effect IDs are unique and ordering is complete;
- each effect’s shapes are legal for its variant;
- payload hashes and modes match the declared postconditions;
- repeated-path timelines are continuous;
- each path’s first and last states match the saved plan’s declared initial/final states;
- the effect surface equals the family transition surface exactly;
- no persistent path is omitted or undeclared;
- ancestor-resolved, leaf-retaining paths stay inside the project root;
- engine scratch names are disjoint from persistent paths;
- required platform capabilities are available, including `renameat2(RENAME_NOREPLACE)` and
  `renameat2(RENAME_EXCHANGE)` plus regular-file hard links on one filesystem.

After this boundary, internal execution code trusts the specification.

## 6. Path resolution and coherent capture

Containment validation resolves the project root and the candidate’s ancestor chain but retains the
leaf pathname. Following the final symlink would turn a transition *of the symlink* into a transition
of its target and could escape the declared surface.

For a regular file:

1. open with `O_RDONLY | O_NOFOLLOW`;
2. obtain type and mode with `fstat`;
3. read bytes from that same descriptor;
4. derive both the content hash and retained rollback bytes from that buffer.

Directories, symlinks, and absence retain `lstat`-based fingerprints and no file content. Capture
refuses if the coherent observed state does not match the effect timeline’s initial precondition.

Capture-time verification is not treated as compare-and-swap authority. For replacement, deletion,
and movement, the effect atomically transfers the actual live entry into an engine-owned staging,
tombstone, or destination path and then validates that transferred object against the frozen
occurrence-local precondition. If it differs, the engine restores it when the declared live path is
still safe or halts while preserving both entries. This closes the destructive check/use gap that an
adjacent fingerprint recheck alone cannot close.

## 7. Project-local durable metadata

```text
.science/transactions/
├── lock
├── active
├── records/
│   └── <transaction-id>/
│       ├── spec.json
│       └── states/
│           ├── 000000.json
│           ├── 000001.json
│           └── ...
└── blobs/
    └── sha256/<digest>
```

### 7.1 Lock

`lock` is a persistent file held with an OS advisory lock. It serializes cooperating Science
processes and is never used as evidence that Dropbox or another arbitrary process is excluded.
Every mutating Science command resolves an existing transaction before planning a new one.

Only one transaction may be active per project. Unsupported locking or publication capabilities
cause an early refusal rather than weaker behavior.

### 7.2 Immutable blobs

Initial file contents and planned postimages are stored by SHA-256. Blob creation is no-clobber,
durable, and idempotent only after byte-for-byte verification. Effects and snapshots reference
hashes; JSON does not duplicate file bodies.

### 7.3 Record and active pointer

`spec.json` is immutable canonical `TransactionSpec`. Execution state is an append-only sequence of
immutable generation files. Each generation contains its number, transaction state, per-effect
state, prior-generation hash, and its own checksum. A new generation is staged completely and
published no-clobber; state is never updated with destructive replacement.

Recovery accepts only the longest contiguous, valid hash chain beginning at generation zero. A
conflicting generation, a gap followed by later generations, or an invalid checksum halts. An
attributable unpublished generation staging file is mutation-free scratch and can be reconciled.

`active` is an atomically published, fsynced pointer to the active record. It is created no-clobber.
The preparation order is:

1. coherently capture and verify the complete initial surface;
2. write or verify all captured and planned blobs;
3. write immutable `spec.json`;
4. write generation zero as `PREPARED`;
5. fsync the record and transaction directories;
6. publish and fsync `active`;
7. begin effects.

A crash before step 6 leaves only mutation-free orphan metadata. A crash after step 6 has a
discoverable recovery record.

Startup scans records as well as `active`. A missing pointer plus exactly one nonterminal record is
treated as interrupted preparation. Multiple nonterminal records, a conflicting pointer, or invalid
metadata halt without project mutation.

### 7.4 Terminal cleanup

After `COMMITTED` is durable, the engine verifies and removes effect-owned displaced preimages and
tombstones, fsyncing their parents. `ROLLED_BACK` is persisted only after every transaction-owned
mutation is undone and all rollback scratch has been removed and fsynced. Its outcome records either
restored initial surface or preserved external drift. The engine removes and fsyncs `active` only
after the applicable cleanup rule completes. A crash during committed cleanup leaves the terminal
record active, so fresh-process recovery finishes cleanup without reconsidering the commit decision.

Detached terminal records and unreferenced blobs may be garbage-collected later under the lock.
Metadata garbage collection is not part of transaction correctness; interruption can only leave
terminal records or immutable blobs.

Transaction metadata is an engine-owned audited surface, distinct from family persistent effects.

## 8. Durable state machine

### 8.1 Transaction states

```text
PREPARED → APPLYING → APPLIED → COMMITTED
    └──────────────→ ROLLING_BACK → ROLLED_BACK

recovery classification ───────→ HALTED
```

`COMMITTED` is the only logical commit decision. It is persisted only after every effect is durable,
the persistent final surface matches, and every retained scratch object matches its exact committed
cleanup contract. The command returns success only after committed scratch cleanup, active-pointer
detachment, and their directory fsyncs complete.

A transaction may enter `ROLLING_BACK` because of a caught application failure or because recovery
finds any noncommitted active transaction. `HALTED` preserves the record, scratch objects, the last
durable commit decision (if any), and diagnostic classification. A halt after `COMMITTED` never
licenses rollback; it preserves the final state and reports incomplete cleanup.

### 8.2 Forward effect states

```text
PENDING → STARTED → DONE
```

The executor must durably persist `STARTED` before invoking the effect. It persists `DONE` only after
the effect’s data and directory-entry durability obligations complete.

These states derive execution ownership:

| Effect state | Meaning |
| --- | --- |
| `PENDING` | `NOT_WRITTEN` |
| `STARTED` | `MAY_HAVE_WRITTEN` |
| `DONE` | `WRITTEN` |

An in-memory view may expose these meanings for diagnostics, but it is not independent mutable
authority.

### 8.3 Reverse effect states

Rollback visits effects in reverse order and durably records:

```text
DONE or attributable STARTED → UNDO_STARTED → UNDONE
```

`UNDO_STARTED` is persisted before restoration or removal begins. A crash during undo is classified
from the same exact path-state contract and restartable restore survivors. An already-initial path is
idempotently accepted; an unattributable path halts.

### 8.4 Recovery classification

For each nonterminal effect, recovery evaluates its complete persistent-and-scratch path tuple:

- exact pre-state → the effect did not land;
- exact post-state → the effect landed;
- a variant-declared intermediate, including an unvalidated displaced entry → apply that variant’s
  settlement rule;
- a no-clobber blocker whose variant-specific persistent-and-scratch tuple proves the effect did not
  land → preserve it and record a refused outcome;
- anything else → halt.

Recovery classifies the whole transaction before performing any mutation. This prevents an early
repair from destroying evidence needed to recognize a later conflict.

No durable `COMMITTED` record means undo transaction-owned effects even when all forward effects
appear complete. This normally restores the initial surface; a proved no-clobber blocker is preserved
as external drift. A durable `COMMITTED` record means preserve the final surface and finish cleanup.

## 9. Effect contracts

### 9.1 `ReplaceFile`

Requires an existing regular-file precondition and exact file postcondition. Persist `STARTED`, then
build a same-directory staging file, write bytes, set the exact mode, and fsync it. Use
`renameat2(RENAME_EXCHANGE)` to atomically swap the staging and live entries. The live path now holds
the complete postimage and the staging path preserves the exact entry that was displaced.

Validate the displaced entry against the expected precondition. On a match, fsync the parent and
mark the effect `DONE`; retain the displaced preimage until the terminal decision. On a mismatch,
exchange it back if the live path still matches our postimage, fsync, and refuse. If the live path
also changed, halt with both entries preserved.

A crash at any point leaves a classifiable tuple of live path plus stable staging path. Rollback
exchanges the retained preimage back when the live postimage is still authoritative. Committed
cleanup removes the displaced entry only if it still matches the validated preimage; divergence is
preserved and reported rather than deleted.

### 9.2 `CreateFileNoClobber`

Requires absence before and an exact regular-file postcondition. Persist `STARTED`, build and fsync
the complete staging file, then publish using `renameat2(RENAME_NOREPLACE)`. Never stream bytes into
the live destination and never fall back to overwriting rename.

If another writer creates the destination first, clean up only the attributable staging object and
raise `PreconditionRefused`. An existing byte-equivalent file is not silently adopted as success for
a family create effect.

For recovery from `STARTED`, a surviving attributable staging object plus any existing destination
proves our no-clobber publish did not land; so does a destination that differs from the postimage.
The engine preserves that blocker, removes only its own staging object, and rolls back earlier
effects with a refused outcome. An exact postimage with no staging survivor is classified as landed,
subject to the fingerprint-equivalent recreation non-guarantee.

Import destination publication itself claims the planned number. The compiler rejects duplicate
destinations within the transaction; a concurrent importer loses at no-clobber publication and the
transaction rolls back. The former live reservation sentinel and partial-destination hard-halt are
not part of the new protocol.

### 9.3 `DeletePath`

Requires an exact present file or symlink precondition and absence after. Persist `STARTED`, then
atomically transfer the live entry with `renameat2(RENAME_NOREPLACE)` to an effect-derived tombstone
in the same parent. The declared path becomes absent while the removed object remains recoverable.

Validate the tombstone against the expected precondition. On mismatch, rename it back no-clobber and
refuse; if the declared path has independently reappeared, halt and preserve both. On match, fsync
the parent and mark `DONE`. Rollback renames the tombstone back no-clobber. Committed cleanup deletes
it only after the durable commit decision and only while it still matches the validated preimage.

Removal of an engine-created directory during rollback remains a separate exact-empty-directory
operation; it is not compiled as a general forward `DeletePath`.

### 9.4 `MoveNoClobber`

One effect owns both source and destination. Its pre-state is `(source=present, destination=absent)`;
its post-state is `(source=absent, destination=source state)`.

Persist `STARTED`, then create and fsync an effect-derived hard-link ownership anchor to the regular
file source. Coherently validate the anchor against the expected source precondition. Use
`renameat2(RENAME_NOREPLACE)` to atomically transfer the actual source entry to the absent
destination, then require the destination and anchor to name the same inode and still match the
expected source fingerprint. The identity relation survives process death and distinguishes the
engine’s moved entry from a byte-equivalent external entry.

When the syscall returns success in-process but the destination is not the anchor’s entry, rename it
back no-clobber and refuse, or halt if the source independently reappeared. On an identity match,
fsync the destination parent before the source parent, then mark `DONE`. Retain the anchor until the
terminal decision.

There is no link/unlink fallback. Cross-filesystem movement or a platform without no-clobber rename
raises `CapabilityUnavailable` before preparation. Recovery of an uncommitted move renames the
anchor-owned destination back to an absent source no-clobber. If the source has reappeared, recovery
removes only an unchanged, anchor-proven destination entry and preserves the source as external
drift; a diverged anchor or destination halts. If the source still names the unchanged anchor and the
destination is foreign, the move did not land; preserve the destination and return a refused outcome.
A tuple in which neither persistent path has the anchor’s identity is unattributable and halts with
the anchor preserved.

### 9.5 `CreateDirectory`

Requires absence before and an exact directory mode after. Persist `STARTED`, create a same-parent
staging directory, set its exact mode, publish with `renameat2(RENAME_NOREPLACE)`, and fsync the
parent. Platforms without the required directory publication primitive refuse early.

Recovery applies the same blocker rule as file creation: a surviving attributable staging directory
plus an existing live directory proves publication did not land, so the live directory is preserved
and the transaction finishes rollback with a refused outcome.

Missing ancestors compile as explicit outer-to-inner effects. Rollback removes them inner-to-outer
by atomically quarantining each directory, validating its exact mode and emptiness, and then using
`rmdir` on the quarantine. A concurrent child makes `rmdir` refuse; the engine restores the
quarantined directory when the live name remains absent or halts while preserving both.

## 10. Restartable materialization

Rollback materializes through stable, effect-derived staging paths:

- present file or symlink preimage over an expected live postimage: stage the exact object; exchange
  it with the live entry; validate and retain the displaced postimage until the rollback decision is
  durable;
- present preimage over an absent live path: publish the staged object no-clobber (normally the
  effect’s retained delete tombstone already provides this object);
- absent file/symlink preimage: atomically quarantine the live entry, validate it against the
  effect’s postcondition, then delete and fsync the quarantine before marking the undo complete;
- absent directory preimage: atomically quarantine the live directory, validate its expected mode
  and emptiness, then use `rmdir` on the quarantine; atomic nonempty refusal preserves any
  concurrently added child.

At entry, restoration classifies a surviving staging or tombstone object:

- complete and attributable → publish it;
- attributable file prefix → remove, recreate, and publish;
- attributable wrong-mode staging directory → finish its mode and publish;
- validated displaced preimage or delete tombstone → restore by no-clobber rename or exchange;
- unvalidated displaced entry → restore it if the live path is still the engine’s exact postimage;
- undo quarantine for an absent preimage → validate, delete, and fsync it before `UNDONE`;
- foreign object or changed live target → halt and preserve evidence.

The authority check precedes every staging-object mutation, including prefix removal. Atomic live
publication means a crash during restoration leaves the target at the effect state or restored state,
never at an in-place partial state.

## 11. Refusal and failure semantics

- **`PreconditionRefused`** — concurrent drift was detected either at capture or by validating an
  atomically displaced entry. The executor returns this refusal only after the current effect and
  every earlier effect have been restored; inability to prove that restoration becomes
  `TransactionHalted`.
- **`CapabilityUnavailable`** — required semantics cannot be supplied. Raised during preparation
  before project mutation.
- **`TransactionHalted`** — the journal, live state, or rollback survivor is unattributable. The
  engine preserves the active record and evidence.
- **`ProtocolError`** — an internal contract was violated. Attempt rollback if mutation may have
  begun; retain the journal if a complete rollback cannot be proved.

Caught process-local failures, including cancellation, `KeyboardInterrupt`, and `SystemExit`, enter
rollback before being re-raised. `SIGKILL`, power loss, and machine failure do not unwind Python and
are exercised only through fresh-process recovery tests.

Recovery and rollback diagnostics identify the transaction, effect, paths, journal state, expected
states, observed states, and the non-mutating operator action required next. There is no silent
fallback or automatic discharge of a halt.

## 12. Family compilation

### 12.1 Supersede

Each frozen entity rewrite compiles to `ReplaceFile`. Supersede is the first production vertical
slice because it exercises the complete transaction lifecycle without allocation or two-path moves.

### 12.2 Archive

Missing archive ancestors compile to `CreateDirectory`; each entity move compiles to one
`MoveNoClobber`; archive index creation or replacement compiles to the corresponding explicit file
effect. Its saved `PathTransition` surface remains the authentication boundary, not execution input.

### 12.3 Import and cohort import

Import saved plans persist a versioned transition surface containing destination creation, source
deletion, created ancestors, and entity rewrites. Apply re-derives the plan from persisted decision
inputs and checks exact surface and rewrite/edit correspondence before compilation.

Destinations compile to `CreateFileNoClobber`, sources to `DeletePath`, ancestors to
`CreateDirectory`, and referrers to `ReplaceFile`. Cohort import compiles one transaction across the
whole cohort; it does not invoke nested per-entity transactions.

The private import snapshot/restore implementation and number-reservation mutation are deleted at
the hard cut.

## 13. Verification strategy

### 13.1 Executable reference model

Each effect defines a pure classifier:

```text
(variant, journal state, observed persistent-and-scratch tuple)
    → recovery decision
```

Table and property tests cover every variant, forward/reverse state, named intermediate,
and unattributable state. Generated valid effect sequences prove:

- path timelines are continuous;
- uncommitted recovery removes every attributable mutation and preserves proved external blockers;
- committed recovery retains the final surface;
- recovery never mutates an unattributable state;
- a second recovery pass is idempotent.

This model is the normative recovery specification.

### 13.2 Real-filesystem effect tests

Run each implementation with faults before and after journal generations, atomic transfer,
displaced-entry validation, settlement, file fsync, parent fsync, and terminal scratch cleanup. Verify
bytes, modes, types, symlink targets, directory entries, and ordering.

Python exception tests exercise caught rollback. Subprocess `SIGKILL` tests exercise true hard halt
and fresh-process recovery. They do not share assertions that depend on Python unwinding.

### 13.3 Compiler conformance

For each family, authenticate a round-tripped plan, compile twice, and require identical canonical
output. Reject missing effects, extra effects, invalid ordering, malformed timelines, payload/mode
mismatches, path escapes, and saved/fresh surface divergence.

### 13.4 End-to-end recovery

Every family covers clean commit, caught rollback, kill during each effect, kill during rollback,
kill during journal update, kill after commit before cleanup, and external drift at destructive
boundaries. Restart happens in a fresh process and must converge or preserve an explained halt.

### 13.5 Actual mutation surface

An always-on in-process interposer records successful mutating operations only after the syscall
succeeds. Every target must be:

- a declared effect path;
- an engine-derived staging path; or
- an exact transaction metadata path.

It wraps `rename`, `replace`, `unlink`, `mkdir`, `rmdir`, `symlink`, `chmod`, `link`, mutating `open`,
and private syscall bindings such as `renameat2`. An optional external trace detects future fresh
`ctypes` or extension bypasses where supported.

An architectural test rejects direct mutation calls and private effect imports from family modules.

## 14. Delivery decomposition

One design governs two implementation plans.

### Plan A — engine core and supersede vertical slice

1. Pure transaction/effect model and validators.
2. Project lock, records, active pointer, blobs, and journal updates.
3. Coherent capture and restartable atomic materialization.
4. Five effects and recovery executor.
5. Model, real-filesystem, and subprocess recovery suites.
6. Supersede adapter and hard cut.

Independently valid capture and restoration fixes replace the shipped implementations early and are
then reused by the engine. No temporary callback/tracker bridge is introduced.

### Plan B — remaining families and hard cut

1. Archive adapter, atomic no-clobber moves, ancestors, and index publication.
2. Import/cohort saved transition schema and Gate-B authentication.
3. Import/cohort adapters with staged destination publication.
4. Cross-family surface and recovery acceptance suite.
5. Delete old family execution loops, private import rollback, callback-bearing orchestration,
   bare rollback, reservation mutation, and obsolete tests.

Each family switches directly to the engine. There is no feature flag, compatibility executor, or
runtime transaction-dialect choice.

## 15. Out of scope and future extension

This design does not add Git temporary-index construction, `commit-tree`, CAS ref publication,
lineage, natural-systems integration, or a general user-facing transaction API.

A later Git design may add a commit participant between filesystem `APPLIED` and transaction
`COMMITTED`. That participant must have its own durable decision and recovery table. It must not
change family adapters or reintroduce a second filesystem executor.

The existing one-off migration journals are not silently interpreted by this engine. Migrating a
command onto the engine is a separate hard-cut design decision.

## 16. Acceptance criteria

The architecture is complete when:

- all four family entry points compile through adapters and mutate only through the executor;
- an active journal is durable before the first project mutation;
- every effect and recovery decision conforms to the executable model;
- caught failure undoes every transaction-owned mutation, preserving external drift as an explicit
  refusal or leaving an explained halt;
- fresh-process recovery rolls back every uncommitted transaction and preserves every committed one;
- import never exposes a partially written destination;
- actual persistent, scratch, and metadata mutations stay within their declared surfaces;
- old execution dialects and temporary bridging APIs are deleted;
- the full Science test suite, lint, and type checks pass.
