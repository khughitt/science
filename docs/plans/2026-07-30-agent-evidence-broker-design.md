# Evidence broker — design (autonomous-audit Spec 2a)

**Status:** partially implemented (revision 38)
**Spec 2a** of the autonomous-audit program (§0). It is independently landable and useful without
the slices that follow it.

**Implementation status.** This design ships as **five** plans, not the three its section grouping
suggests; the boundary was drawn by tracing module dependencies rather than section headings. The
fourth split in two at revision 17, on the seam between producing a `Correspondence` and storing one.

| Plan | Owns | State |
|---|---|---|
| [Plan 1](2026-07-30-evidence-broker-plan-1-control-plane.md) | `autonomy/control_plane.py`, the `grep`/`log` probe, `LC_ALL`/`LANG` pinning in `run_git` | **merged** at `57b09bf0` |
| [Plan 2](2026-07-30-evidence-broker-plan-2-serving.md) | `SurfacePolicy`, `evidence_broker/{policy,serve}.py` — §3.1, §3.2, §3.2.1 | **merged** at `dab47dc3` |
| [Plan 3](2026-07-31-evidence-broker-plan-3-session.md) | the session and its record — §3.3, §3.4, §3.4.1, §3.5, §4.1, §4.3, §6's seal rule | **merged** at `f2fe585e` |
| Plan 4a | serving hardening — §3.1's NFC tree rule at `start_run`; §3.2's `GIT_SHALLOW_FILE` + `GIT_NO_LAZY_FETCH` pins plus the untraversable-history diagnostic at open; the payload bound and the `run_git` ceiling; the protocol bump | **merged** at `d5bf01e2` |
| Plan 4b | the checker — the hit parser, §5.1, §5.2, §5.3, and `Correspondence` itself | **merged** at `cbb7656f` |
| Plan 4a follow-up | §3.1's tree rule restated as `normalize_project_path(p) == p` — see revision 31 | **merged** at `33bbdaf2` |
| Plan 4c | the boundary — §4.2's `ReviewAttestation` and stored-`Review` invariants, `ReviewSubmission`, §5.4's `append_review`, §4.2.1 eligibility | **merged** at `1c11c922` |

Sections carry no per-section status marker: a section describes the design, and a section that is
half-built is still describing the whole thing. The table above is the only status claim, and the
plan documents record what each landed and what each deviated on.

Revisions 2 through 6 respond to design review: six production-boundary defects in revision 1, six in
revision 2, six in revision 3, five in revision 4, six in revision 5. Each is closed below and named at
the point it is closed, because the reasoning that produced the defect is more useful to a reader than
the corrected text alone.

Revision 7 is not another defect round. It places this document inside the program it was already
serving — revisions 1–6 numbered it "sub-project A of three", independently of the autonomous-audit
specs, and two of those three sub-projects were audit-program slices under other names. §0 fixes one
vocabulary and records the boundaries the two schemes left unowned. It also closes the one defect that
only became visible once the two were read together, which is the fourth pattern below.

Revision 8 corrects one mechanism citation found while checking what an implementation plan would
build on: the journal was to be created through `findings/paths.py`, whose every primitive anchors
*inside* a project root, while the journal is deliberately outside one (§3.4.1). A fifth instance of
the fourth pattern — the named component was real, and guaranteed the opposite of what was wanted.

Revision 9 removes replay from the seal (§3.4.1). It is the first defect found by reading three
sections *against each other* rather than any one of them closely: §3.4.1 said `finish_run` replays the
journal, §6 enumerated a missing or unreadable journal as the only way a seal fails, and §5.2 placed
replay at review-append time. Each section was locally coherent, which is why eight revisions of
section-by-section review did not surface it — and it was slicing-relevant, since a replaying seal
would have dragged §5's replay machinery into the session slice. A fifth pattern, below.

Revision 9 carries two further corrections, both from probing git 2.55 while planning the serving
slice rather than from reading. `read` was spelled `git show <commit>:<path>`, which serves a
*directory* as a tree listing at exit 0 — indistinguishable from a file read, so `FULL` coverage would
have been recorded over a listing (§3.2). And §3.2's account of why search pathspecs need `literal` was
invented: the non-literal spelling does not leak denied material, it over-excludes material that was
never denied, which breaks the agreement between `read` and `search` in the opposite direction. Both
are instances of the second pattern below — a claim that outran its mechanism — and the second is its
sharpest form yet, since the recommendation it argued for was correct all along.

Revision 23 closes four defects in §2.2 itself, two of them in the contract's own load-bearing rows.

1. **`Correspondence`'s home did not import.** `evidence_broker.py` imports `audit.subjects`, and
   `audit/__init__.py` eagerly imports `audit.record`, so `import science_model.evidence_broker`
   already loads `audit.record` — probed, not reasoned. Having `audit.record` import `Correspondence`
   back would close a cycle through a partially initialised module. It moves to
   `science_model/correspondence.py`, a leaf importing pydantic and nothing else, which is the only
   placement under which neither package depends on the other.
2. **The forward guarantee was false in the direction 4b would rely on.** Revision 22 promised "no
   `history` entry originating in a shallow repository", but revision 18 journaled shallow-history
   refusals, so such entries existed. Replaying one in a *complete* clone re-serves real history and
   yields `EXPOSURE_UNREPRODUCIBLE` — the reciprocal of the case revision 18 set out to fix, created
   by revision 18's own fix, and left unstated for five revisions. Shallowness now refuses at
   `start_run` beside the tree scan: a journaled refusal was never deterministic given the pinned
   commit, which revision 21's own rule already said disqualifies it from the journal.
3. **`is_shallow` was declared shared without a module** — which is how one mechanism becomes two
   functions. `autonomy/git.py::is_shallow`.
4. **4c's row named a directory.** A new `validate` check is two files: the module and its
   registration in `validate/checks/__init__.py`. Both are named.

**The first and fourth are the same mistake as "must not touch `audit/*`", which revision 23 also
replaces.** A contract stated as a *path* fails exactly as a guard stated as a *roster* does: the ban
on `audit/*` would have forced `Correspondence` into the cycle, because the rule it stood for —
**4b changes no stored-record model** — was never the rule that got written down.

Revision 24 closes three, all inside revision 23's own fixes, and the first is the sharpest defect
this design has had.

1. **The shallow refusal was a check on mutable state, and check-then-use is the shape this design
   has rejected three times.** `.git/shallow` is an ordinary file in the actor-owned `.git`
   directory: an actor writes it *after* the run opens and `git log` answers short at exit 0 —
   **measured, one `echo`, 3 commits become 2** against an unchanged pinned commit. Revision 23
   placed the guarantee at open and left the window wide. The fix is not an earlier check or a
   tighter one: `GIT_SHALLOW_FILE=/dev/null` in `_ENVIRONMENT` makes the file unreadable to git, and
   a genuinely shallow repository then **fails at exit 128 rather than answering short**. The
   open-time check survives as a diagnostic. Same doctrine as `-c` over `.git/config`, one directory
   over.
2. **The forward guarantee said "complete clone", which is not observable.** `is_shallow() == False`
   is a statement about one file; the pin converts truncation into failure. Neither certifies
   completeness. §2.2 now states three clauses, the third of them about *truncation*, not
   *completeness*. Third attempt at that sentence — see the note there.
3. **The import-cycle mutation probed the direction that works.** `import science_model.audit.record`
   initialises `audit` first and then succeeds, and under pytest `sys.modules` may answer without
   executing anything at all. It must spawn a fresh interpreter on
   `import science_model.evidence_broker`.

Revision 29 is pre-flight for plan 4b: §5 read against the merged tree rather than against itself.
Three of its assumptions were **confirmed by probe** and are now stated as such; four points it left
underdetermined are decided; two of §7's own rows are corrected; and design review of this revision
closed five more, listed at the end. None is a defect in the production boundary. All four
undetermined points are places an implementer would have had to invent a rule, and three of them have
a permissive default that an invented rule lands on by accident.

**Confirmed, so 4b may rely on them.** Citation keys and served-map keys land in one namespace, and
4b normalises nothing — but that rests on **two** facts, not one, because a search's target is a
regex and is deliberately never normalised (§3.2). `LocationEvidence.path`, a read or history
`entry.target`, a search's `entry.pathspec` and `InlineInput.target` are all outputs of the same
idempotent `normalize_project_path`; a **search's map keys are not among them** — they are the paths
parsed out of the replayed grep payload, which are git's own tree paths. Take away either fact and
the namespace splits.

**Revision 31 corrects what the second fact has to be.** This sentence said those paths are
"project-relative and NFC by 4a's clause 1" — true, and not enough: NFC does not imply
backslash-free, and `normalize_project_path` rewrites a backslash. The property the served map
actually needs is that **the normalizer returns a tree path unchanged**, which is now what §3.1
guarantees. Revision 29 named this exact class of error in its own finding (3) and then committed a
fresh instance of it one clause later, in the paragraph whose whole subject is which facts the
namespace rests on. The journal's digest is
`sha256(payload)` with no framing, so re-serving alone reproduces it. And revision 23's
import-cycle probe re-runs true on the merged tree.

1. **A replay-time git fault has a disposition, and it is not `unwired` by default.** Exactly two
   conditions are decided before any entry is replayed — the repository does not hold
   `exposure.commit`, and `history_traversal_error` is non-`None` — and those two own
   `EXPOSURE_UNREACHABLE`. Anything else from git propagates, per §6's standing rule for the same
   failure at serving time. The alternative reading, wrapping the whole replay and calling every
   fault `unwired`, is the shape of revision 4's own bug: a project rename silently turned every
   review `unwired`, and this design treated that as a fail-open to close, not as graceful
   degradation. §5.2.
2. **`line_count` is LF-based, and `InlineInput.lines` is not.** MEASURED:
   `b"a\rb\n".splitlines()` is 2 because `bytes.splitlines()` splits on CR as well, and the sealed
   manifest is built that way. `git grep -n` numbers by LF, and §5.1 makes `FULL` supersede `LINES`
   on a path that was both read and searched — so a non-LF `FULL` count is not commensurable with
   the `LINES` numbers beside it. Read coverage uses the LF rule; inline coverage uses the sealed
   count, because 4b has no payload to recount and may not touch the model. The divergence is
   permissive on CR-bearing files and is recorded rather than buried. §5.1.
3. **The coverage merge was stated for one pair out of ten.** "`FULL` supersedes `LINES`" is not a
   total rule. §5.1 now enumerates all ten, including the four self-pairs — nothing bounds a run to
   one request per path — and the single unreachable pair, with why.
4. **An inline entry disagreeing with the sealed manifest is `EXPOSURE_UNREPRODUCIBLE`, not absent
   coverage.** `entries` and `exposure.inline` are seeded from one `session.inline`, so they agree by
   construction; a record where they disagree is a record disagreeing with itself, which is what §5.2
   exists to catch. §7 said "absent from the **baseline** manifest does not correspond" — stale
   wording from before revision 5 moved replay off the baseline, and weaker than the fact. Under the
   weaker reading, editing an inline entry's target is a free way to make a fabricated citation land
   nowhere at no cost.

**And one constraint that reads as tidy-able and is not.** §4.2 spells `Correspondence` as
`Correspondence(_Base)`, but `_Base` lives in `audit/subjects.py`, and importing anything from
`science_model.audit` runs `audit/__init__.py`, which eagerly imports `audit.record` — the module
that will import `Correspondence` back. So `science_model/correspondence.py` inherits nothing from
`audit` and repeats its own two-line model config. Revision 23's mutation row covers importing
`Correspondence` *from* `evidence_broker.py`; this is the other edge of the same cycle.

**Both edges turn out to be 4c rows, not 4b's.** The cycle does not exist until
`audit/record.py` imports `Correspondence`, which is 4c's change — 4b touches no stored-record model.
Run against 4b's tree either mutation imports cleanly and the row passes for the wrong reason, which
is exactly what §7's `Slice` column exists to catch, found one slice later than the last time. 4b
keeps a row it can certify on its own tree: a fresh interpreter executes
`science_model/correspondence.py` with `runpy.run_path`, and that leaf execution must not load
`science_model.audit` at all.

**Design review of revision 29 closed five more, two of them inside revision 29's own fixes** —
the pattern this document has now recorded five rounds running. The fourth is older than all of
them; the fifth was introduced by the implementation plan.

1. **The merge table was incomplete in the same way the thing it replaced was.** Revision 29 replaced
   a one-pair rule with a five-row table and called it total; four pairs were missing, and the
   omission was systematic rather than random — every missing pair was a **self-pair or a pair
   involving one**, because the table was built by asking how two *different* operations combine.
   Nothing bounds a run to one request per path. The costly one is `LINES` + `LINES`: two searches
   expose disjoint line sets of one file, and a rank-based merge discards one of them, refusing a
   citation to a line the reviewer demonstrably saw. It is also the only row where a union is
   correct, which makes "just union everything" look like the safe repair — and unioning `FULL`
   counts takes the maximum, inverting `FULL(min)`. §5.1.
2. **§5.3's order was unexecutable as written.** The table put `EXPOSURE_UNREACHABLE` before
   `REPLAY_PROTOCOL_MISMATCH` while the prose said all three `unwired` conditions are decided
   "before any git call" — but deciding a repository lacks a commit, or will not walk, *is* a git
   call. Only the first two rows are free. §5.3 now numbers the five steps, names
   `serve.verify_commit` so 4b does not grow a second commit probe, and keeps the true part of the
   old claim: a protocol mismatch classifies identically against a healthy repository, an
   unreachable one, and a path that is not a repository.
3. **Revision 29's own "one namespace" claim overshot, on the operation it had just finished calling
   special.** It said every `ExposureEntry.target` is a `normalize_project_path` output; a search's
   target is a regex and is deliberately never normalised (§3.2), and a search's map keys are not
   targets at all — they are hit paths parsed from the payload, project-relative and NFC by 4a's
   clause 1. The namespace rests on two facts, and stating it as one would have licensed a checker to
   normalise a pattern. The same sentence appeared in §5.2 calling the journalled search target an
   "`authorize` output", which it is not. Both corrected.
4. **A §7 row that has been vacuous since revision 1.** "Make a span cite only its endpoints /
   a ten-line span against a one-line hit is refused" — endpoint-checking refuses that too, since
   line 10 is not among `{1}`. The mutation stayed green for twenty-nine revisions, and §5.1's prose
   supplied the same example, so an implementer taking the fixture from either would have certified
   nothing. Separating it needs both endpoints served and the middle not: lines 2–4 against `{2, 4}`.
   Found by self-review of the *plan*, not of this document, which is where a row's fixture first
   has to be written down concretely.
5. **The plan silently invented a durable-model invariant.** It forbade `code` on `verified`, while
   revision 17 required a code on non-verified results but did not state the reciprocal, and the
   `InstrumentResult` invariant this type mirrors explicitly permits a code on `ok`. The tightening
   is retained — a verified correspondence has no failure to classify, so a code beside it is stale
   or contradictory — but §4.2 now states the deliberate divergence instead of letting 4c inherit a
   plan-time assumption as though it had been reviewed here.

Finding (3) is the **second** overshoot in this document to name a mechanism next to the property
instead of the property — §2.2 records the first, three ways over three revisions — and it arrived
in a paragraph whose subject was *which* facts the namespace rests on. Proximity to the caveat is not
protection from the error.

Revision 34 settles plan 4c against the merged tree. Revision 26 designed it against a repository
that contained neither 4a nor 4b, and left the mechanism of the append boundary underdetermined in
six places. Each is closed below at the section that owns it; the entries here are the ones whose
reasoning generalises.

**A parameter that is validated and discarded is a fictional audit property.** Revision 26 gave
`append_review` an `actor`, by symmetry with `ingest_report`. But `ingest_report` *persists* its
actor — in the genesis `Transition` it writes — and `append_review` writes no transition. `Review`
has no actor field and gains none here. The parameter would have been checked for nonblankness and
NUL-freedom and then dropped, which is worse than omitting it: a public argument named `actor`
advertises that the writer is recorded, and nothing in the stored record would carry it. `actor`
is removed. It returns if and when writer provenance gains a durable field to land in.

**A missing run record is refused, not stored as `unwired`.** Revision 34 first proposed a fourth
§5.3 code, `NO_RUN_RECORD`, on the argument that §6 deliberately creates this state — a brokered run
whose journal is gone writes no record — so refusing would discard an honest reviewer's findings for
a supervisor's failure. That is wrong, and the reason is the asymmetry with `EXPOSURE_UNREACHABLE`:
there, an attested run record *exists* and only its repository cannot answer. Here there is no
record, so neither identity cross-check can run and no sealed exposure provenance exists at all.
Storing the review would mint an agent `review_id` whose `run_ref` points at nothing. §6 already
calls the lost-journal branch retryable; the run is re-run, not reviewed around.

**That collapse deleted a test row, and the row must go rather than be rewritten.** While the two
cases had different outcomes, "treat a broken `runs/` as a missing run" was an observable mutation.
Now both refuse with `IngestError` and nothing distinguishes them but message text, so the mutation
survives every assertion worth writing. The distinction is still real in the code and still stated in
§5.4; it is simply no longer certifiable, and it joins §7's list of rows that must not be added. A
ruling that simplifies behaviour can silently invalidate a guard written for the richer behaviour —
the guards must be re-read against the ruling, not just extended.

**A mutation that names a structure rather than a behaviour certifies nothing.** Revision 34's first
draft of §7 carried the row "give the check its own predicate instead of `counts_as_support()`". A
faithful copy of the predicate satisfies that mutation and changes no output, so the row was testing
a refactor it could not observe. The rewritten row names the concrete wrong implementation — *report
only non-verified correspondence* — which the vacuously-`verified` fixture genuinely separates. The
shared predicate is still the right structure; it is just not what an outcome test can prove. This is
the sibling of the vacuous-fixture error revisions 31 and 32 corrected: there the input could not
distinguish the mutant, here the mutant is not distinct from the original.

**And one clause per row.** §4.2.1's eligibility has five independent conditions — outcome, reviewer
kind, correspondence present, status `verified`, and every entry a location. A single fixture that
fails when any of them is dropped certifies whichever one it happens to trip first. §7 now carries a
row per clause, each with a fixture that isolates it, which is the same discipline §7 applies to the
coverage algebra.

**A second review round closed five more, and four are the same defect in different costumes: a
claim of totality resting on a roster.** §5.4 said "every failure to resolve becomes `IngestError`"
while naming only `RunRecordError` — `load_run_records` also emits raw `OSError`, because
`Path.exists()` swallows only the not-found family and `iterdir()` swallows nothing. Its step 7 said
"load the case, `with_review`, write" and left the unknown-`finding_id` and duplicate-`review_id`
channels unspecified, so both would have surfaced as somebody else's exception type. It had no
revalidation step, so a `model_construct`-forged submission reached the checker with the boundary's
own types never having run. And §7 claimed to certify "every guard" while missing eleven rows, among
them both `evidence` bounds and the ordering rule §7's own prose had already described. The pattern
is worth naming because it is not carelessness: each claim was true of everything its author had
enumerated. **A totality claim is only as good as the mechanism that makes enumeration unnecessary** —
which is why §5.4 now names exception *types* it catches rather than situations, and why the
eligibility rows are derived from the predicate's clauses rather than from a reading of it.

The fifth was an explanation that predicted the right outcome from the wrong mechanism — see §4.2 on
`with_review`, which does not do what revision 34 first said it does.

**Revision 36 closes two residues of the round below, both of the same kind as the rest.**

- **Step 0's rows still passed for the wrong reason.** A forged `LocationEvidence` that survives to
  step 4 cites a path the served map cannot cover, so `check_correspondence` returns `violated` and
  step 5 raises `IngestError` anyway — the mutant reaches the same outcome by the longer road. Both
  submission rows now additionally require that **`check_correspondence` is never called**, and the
  attestation row that **`load_run_records` is never called**, since a forged agent attestation with
  `lens=None` is otherwise refused later by the cross-check or by `Review` construction. The rows are
  now about where the refusal happens, which is the only thing step 0 changes.
- **`locked_store`'s passthrough claim overreached by one sentence.** Revision 35 wrote "whatever the
  caller raises passes through untouched" immediately above the measurement showing `case_store`
  converting body-raised `FileNotFoundError` and `PathSafetyError`. The honest claim is about what
  `locked_store` *adds*: no catch spanning its body. What survives that body is a fact about
  `case_store`, and it is not "untouched".

The first is the fourth appearance in this design of a mutation whose outcome is right for a reason
unrelated to the guard, and the pattern is now specific enough to state as a check: **when a mutation
removes an early refusal, ask what the later stages would do with the same input** — if they refuse
too, the row must assert that the later stage never ran.

**Revision 38 closes the final whole-branch review of plan 4c.** Four findings changed the settled
contract or the evidence that guards it.

1. **Boundary models must be exact types, not merely valid instances.** Step 0 rebuilt with
   `type(value)`, preserving caller-owned behavioural subclasses. A measured `ReviewSubmission`
   subtype returned the evidence the run had seen to `check_correspondence`, then returned different
   evidence to the stored `Review`; the stored correspondence vouched for a tuple it had never
   checked. `append_review` now rejects a non-exact `ReviewSubmission` or `ReviewAttestation` before
   reading any property or invoking any method on it, then dumps and strictly validates through the
   named concrete base type. Separate mutations cover both arguments because either call site can
   accidentally reintroduce `type(value)`.
2. **Storage totality ends at the primitive that owns each descriptor.** `open_lock_at` converted
   `os.open` failures but leaked `os.fstat`, and its cleanup `os.close` could replace the validation
   failure. `open_dir_inside` likewise leaked its final close. Those failures now become
   `PathSafetyError` at their owner and therefore `CaseStorageError` and `IngestError` at the two
   enclosing boundaries. If caller work is already failing, release/close failures are attached as
   notes and the caller's exception remains primary; no catch was added around `locked_store`'s
   `yield`.
3. **A predicate test is not an aggregate wiring test.** Every eligibility clause was guarded on
   `Review.counts_as_support()`, but restoring `confirmation_count`'s former outcome-only filter left
   them green. Three record-level negatives — unwired, vacuously verified, and mixed evidence — now
   fail that mutation together.
4. **The implementation plan lagged its collision fix.** The registered validation section is 163
   with display order 16301 because 161 and 162 are already owned; the registration guard is the
   ninth check test. The plan now records those shipped values and the collision rationale.

Six distinct mutations are added: the two exact-type call sites, lock `fstat`, validation-cleanup
close, directory close, and the old aggregate filter. Together with revision 37's 38 rows, plan 4c
now has **44 certifiable rows**.

**Revision 37 removes one vacuous 4c mutation found by the mechanical certification sweep.** The
scan-specific mutant raised `CaseStorageError` rather than `IngestError` when no case matched a
`finding_id`, but the enclosing storage boundary catches `CaseStorageError` and translates it to
`IngestError`. The named test therefore stayed green: direct `IngestError` and internal
`CaseStorageError` have the same public type and no write in both implementations. Only exception
cause, message, or code structure could distinguish them, and none is part of this boundary's
contract. The row moves to §7's "must not be added" list; 4c now has 38 certifiable rows.

**Revision 35 is a third round, and its number exists because revision 34's second round changed the
settled contract while still calling itself 34.** Two commits claiming one revision is a versioning
defect in a document whose whole method is that a numbered contract can be cited. Its three findings
share a root the second round did not reach: **revision 34 kept asserting what neighbouring code
does without running it.**

- The lock fixture was rewritten twice, each time moving closer to the leaf, while the thing making
  it vacuous — that `case_store`'s `try` stays active across its own `yield` — was never checked.
- Step 0 said "the same as `_snapshot_report`" and specified nothing. Measured, the natural spelling
  `T.model_validate(instance)` does not recurse into a forged member at all, and copying
  `_snapshot_report` literally fails on its own JSON-mode dump, which renders `at` as a string that
  strict validation then refuses.
- Step 7 said "load the case", and `CaseStore` has no load-by-id to call.

The corrective is not more care in reading. **Each claim above is about what code does when it runs,
and each was settled in under a minute by running it** — the FIFO reproduction, the
`model_construct` probe, the `CaseStore` method list. A design document that describes a boundary in
terms of its neighbours' behaviour has taken on a testable obligation, and prose review cannot
discharge it. Revision 34 had already established that discipline for `with_review` and then did not
extend it to the three neighbours it leaned on next.

Revision 33 fixes the one place the widened tree rule had not reached: **§2.2's clause 1, which is
where the guarantee is stated rather than merely described.**

Revisions 31 and 32 restated the rule in §3.1, in §5.1's assumption sentence, and in the
three-directions analysis, and left clause 1 reading "valid UTF-8 and already NFC" — two lines above
the sentence that draws the entitlement from it: "Clause 1 is what licenses 4b to key its served map
on the decoded path without re-normalising." That conclusion does not follow from NFC. The guarantee
and the entitlement it grants disagreed, adjacently, for fourteen revisions, and commit `33bbdaf2`
had already shipped the stronger property in code. Clause 1 now reads **decodes as UTF-8 and is
returned unchanged by `normalize_project_path`** — in that order, since the round-trip needs a `str`
before it can run. The same two-part spelling now appears in §3.1's rule and in the three-directions
conclusion, so the seam states one predicate on both sides.

**Why this one outlived three revisions of the same correction.** Revisions 31 and 32 fixed every
sentence that *argued about* the rule and missed the sentence that *is* the rule. §2.2 opens by
declaring itself authoritative for the seam precisely so this cannot happen — and being the
authoritative statement is what made it invisible, because the review attention went to the prose
that reasons and not to the clause it reasons from. **When a rule changes, the numbered contract
changes first and the discussion second.** That is the sixth instance in this document of a fix
carrying a defect of its own shape, and the first where the defect was the *scope* of an otherwise
correct fix rather than its content.

Revision 32 corrects both of revision 31's span mutation fixtures, found while executing the fix wave
it authorised. Revision 31 wrote a section warning that a timeout row is only as strong as the input
that keeps the mutant running, and then supplied two inputs that do not.

1. **The `FULL` row's mutation short-circuits after four iterations.** `Full(3)` against a span of 1
   to `10**18` makes the iterating form return `False` at line **4** — the predicate is false almost
   immediately, so nothing runs long and the row certified nothing. The count must sit just *below*
   the span's end, so every line but the last satisfies it: `Full(10**18 - 1)`.
2. **The `LINES` row's mutation cannot hang at all, so the row is deleted.** A span is contiguous and
   `numbers` holds at most n elements, so among any n+1 consecutive lines at least one is absent and
   the iteration short-circuits within `len(numbers) + 1` steps regardless of the span's declared
   length. The pre-check is a same-verdict optimisation and now sits beside the quadratic
   accumulation in §7's "must not be added" list.

The two share one cause: revision 31 saw two loops over a span and gave them the same treatment
without asking **what bounds each loop**. `FULL` compares against a count, so an authored `end_line`
sets the iteration length directly; `LINES` compares against a set, whose size is fixed by the
payload cap. Only the first is authored-unbounded. This is the fourth time in this document that a
fix has carried a defect of its own shape into the next round — and the first where the *warning
paragraph* and the defective fixture were written in the same revision.

Revision 31 closes the five defects found by plan 4b's final cumulative review of implemented code.
None is a fail-open in 4b — but one is a fail-open in **4a**, which 4b's own assumption sentence had
been quietly repeating for three revisions.

**The one that changes a slice boundary: a backslash in a tree path certifies a false absence.**
`normalize_project_path` maps `\` to `/`. §3.1's tree scan checks UTF-8 and NFC and says nothing
about either character, so a repository holding `a\b.txt` opens a brokered run. A `read` of
`a\b.txt` authorizes as `a/b.txt`, git reports that absent, and the served map records `Absent` for
`a/b.txt` — under which a citation to `a\b.txt`, normalising to the same string, corresponds. **An
agent claims a file does not exist, is wrong, and is certified `verified`.** That is direction 3 of
§3.1's own three-directions analysis, reproduced with no Unicode involved and no deny prefix
required, and §3.1's stated rationale already covers it: a path that cannot be spelled as a
`LocationEvidence.path` can never be cited honestly, "so it is the same rule in the same place."

So §3.1's rule widens, and the repair lands in `autonomy/lifecycle.py` — **4a's cell, not 4b's**. It
ships as a 4a follow-up commit *before* 4b's fix wave rather than folded into it. §2.2's 4b row keeps
saying `Modifies: —` and keeps meaning it; a contract amended once to accommodate the slice that
found a neighbour's bug is a contract that will be amended again. What 4b owns here is the
discovery, not the fix.

**And 4b's assumption sentence was overstated a third time, in the same paragraph as the first two.**
Revision 29 said search-hit paths are "project-relative and NFC by 4a's clause 1", which is true and
insufficient: NFC does not imply backslash-free, and the served map needs the *stronger* property.
Revision 29's own finding (3) named this class of error and then committed a new instance of it one
clause later.

1. **A valid filename containing LF breaks the parser.** MEASURED, git 2.55: `git grep -z` emits the
   path **raw**, so a hit on `a\nb.txt` produces `<commit>:a` LF `b.txt` NUL `1` NUL `content` LF, and
   splitting the payload on LF splits mid-record. It fails loudly — the first fragment carries no NUL
   — so no citation is misclassified. The repair is nevertheless **not** a wider delimiter: splitting
   on `LF + <commit>:` is defeated by a filename containing that literal sequence, and the commit is
   knowable. §5.1 now specifies a **forward scan**, which is unambiguous by construction and needs no
   4a change.
2. **The backslash case above.** §3.1, plus the widened §5.1 assumption.
3. **Inline integrity was one-directional and lost multiplicity.** A dict keyed on
   `(target, sha256)` proves every entry has a manifest item and never the converse, so a manifest
   item with no entry — a record disagreeing with itself in the other direction — passed. It also
   collapsed duplicates. §5.2 now compares **multisets**, and separately refuses a manifest in which
   one `(target, sha256)` key carries two different `lines` values: identical duplicate inputs stay
   reproducible, contradictory line counts are not a coverage question with an answer.
4. **A span can be constructed that never terminates.** `Span.end_line` is `Field(ge=1)` with **no
   upper bound**, so `Span(start_line=1, end_line=10**18)` is constructible and iterating it inside
   `all(...)` hangs. Reachable from authored review content on a write path, and it hangs rather than
   fails, which makes it the most serious of the five. §5.1 now requires the check to be bounded.
5. **Hit accumulation was quadratic.** Uniting a fresh one-element `Lines` per hit rebuilds the set
   each time, so a path with *k* hits costs O(k²) — and `MAX_SERVED_BYTES` admits roughly twenty
   thousand hits in one payload. §5.1 now groups by path before constructing coverage.

**None of these bumps `REPLAY_PROTOCOL_VERSION`, and that needs saying rather than assuming**, since
§5.2 lists "the hit-line parsing" among the things the protocol covers. The bump exists so a changed
*meaning* of serving cannot silently reclassify honest historical work. Every repair here is a strict
widening or a bounded rewrite of the same answer: the parser fix affects only payloads that
previously raised, the span and accumulation fixes compute the identical verdict, the inline fix
tightens a check rather than changing what replay serves, and the tree rule changes which runs may
**open** — not what serving or replay computes. No sealed exposure's verdict moves off `verified`.
The tree rule does mean a repository holding such a filename can no longer open a brokered run; that
is a real behaviour change to 4a, recorded here, not a version bump.

Revision 30 corrects 4b's leaf-import guard. A normal `import science_model.correspondence` always
executes the existing eager `science_model/__init__.py`; its current chain already loads
`science_model.audit` before the leaf executes. The old `sys.modules` predicate therefore measured
package initialisation, not the leaf's dependencies, and could not certify the boundary it named.
4b instead starts a fresh interpreter, executes the leaf file directly with
`runpy.run_path(sys.argv[1])`, and asserts that `science_model.audit` remains absent. Temporarily
importing `_Base` or anything else from `science_model.audit` in that file makes this guard fail.
The real package-cycle rows remain 4c: their `audit.record -> Correspondence` edge does not exist in
4b's tree, and this correction changes no production boundary.

Revision 28 closes the cross-task defect found by Plan 4a's final cumulative review.

**The new run-open failures reached one layer farther than the slice contract recorded.**
`start_run` now calls hardened git for ancestry and tree checks before a session exists. An oversized
configuration preflight or stderr therefore raises `GitError`, but `autonomy start` caught only the
older lifecycle/extraction exceptions. The command documented `0 opened, 2 could not open` and instead
let these normal refusal paths escape as exit 1 — the same quarantined-looking boundary the
`GitOutputTooLarge(GitError)` hierarchy was chosen to avoid. Plan 4a therefore also owns the minimal
`autonomy/cli.py` catch and a test against the **base** `GitError`, so catching only the overflow
subtype cannot pass.

The same review found two closure claims wider than their executable rows. The shallow-history row
named 4b's future replay verdict even though its 4a guard is the earlier fact that no brokered run
opens; the row now asserts that open-time boundary directly. And the combined stderr/preflight row
was only tested on served stderr. It is split: serving must propagate a base `GitError` produced by
the mutable configuration preflight, independently of the stdout/stderr subtype split.

Revision 27 closes one defect, found in pre-flight for plan 4a's Task 2, and it is the fourth time
running that a fix carried a defect of its own shape into the next round.

**The shallow diagnostic was a proxy, and revision 24's pin blinded the proxy.**
`rev-parse --is-shallow-repository` reports whether a shallow *file* could be opened, not whether
history can be walked. MEASURED, git 2.55: `is_repository_shallow()` sets its flag on a **successful
open**, before reading a line, so `/dev/null` opens and a **complete** repository reads `true` under
`GIT_SHALLOW_FILE=/dev/null`. Under the pin the predicate is constant-`true` and would refuse every
brokered run. Revisions 24–26 recorded the measurement ("does not honour the pin") and attached the
opposite conclusion to it — the detector does not keep working, it stops distinguishing.

The natural repair is a detector-specific invocation that omits the pin. It works, and it re-admits
an actor-owned file into a defense — the shape this design has now rejected four times. The repair
taken instead asks the **served property**: `_LOG_ARGV` carries no `-n`, so `history` walks to the
root, and `rev-list --count <commit>` under the pins measures exactly that. MEASURED: a complete
6755-commit repository answers in 42 ms; a complete repository with `.git/shallow` **planted** still
answers, because the plant is ignored; a `--depth 1` clone exits 128. `is_shallow` becomes
`autonomy/git.py::history_traversal_error(repo, commit) -> str | None`, returning git's own
diagnostic.

**Its reach is bounded and stated, because the guarantee sentence three revisions above was widened
by assumption twice.** MEASURED under the pins, `--filter=tree:0` and `--filter=blob:none` clones
both report the full commit count — their commits are all present. The tree case is already refused
at open by the §3.1 tree scan (`ls-tree -r` → `fatal: not a tree object`, measured), for free; the
blob case is not pre-empted at open and fails loudly mid-run at exit 128, which is
`GIT_NO_LAZY_FETCH` working as designed. The diagnostic covers **missing commits**. It is not a
completeness oracle, and §3.2's guarantee never rested on it.

Revision 26 closes two, both in revision 25's own fix and neither in the production boundary.

1. **The lazy-fetch fixture's precondition was built from the pin it mutates.** Asking "is this tree
   absent?" is itself a lazy-fetch trigger: measured, unpinned `cat-file -e <tree>` exits 0 **and
   spawns a fetch**, as does `rev-parse 'HEAD~1^{tree}'` inside the partial clone. Deleting the
   production pin therefore breaks the row's *setup* — and populates the clone while doing it — so
   the mutation never reaches serving. The OID comes from the source repository and the check carries
   its own explicit `GIT_NO_LAZY_FETCH=1`. §7 now states the general question: **which line does the
   mutation break first?**
2. **§3.2.1's canonical-invocation table still listed only `LC_ALL` and `LANG`**, contradicting §3.2.
   Both pins are named there, and named for **all three ops** — a partial clone withholds blobs as
   readily as trees, so `cat-file blob` and `grep` reach a promisor remote by the same mechanism that
   motivated the pin under `history`.

Revision 25 closes one defect, in revision 24's fix, plus a stale status line.

1. **The shallow pin closed one of two ways a repository declines to hold its own history, and the
   other one reaches the network.** A `--filter=tree:0` partial clone does not truncate and does not
   fail — it **lazily fetches** the missing objects from its promisor remote, mid-request, at exit 0.
   Measured against the canonical `_LOG_ARGV`: **two `git fetch` subprocesses spawned**, full answer
   returned, nothing in the output disclosing it. `GIT_NO_LAZY_FETCH=1` joins `GIT_SHALLOW_FILE` in
   `_ENVIRONMENT`; the same probe then fails locally at exit 128 having spawned nothing. Clause 3 of
   the forward guarantee is restated from *ancestors* to *objects the local repository already held*,
   and §7 gains the row plus the two ways its fixture goes vacuously green.

**This one is worse than a determinism defect and the design should say so.** The promisor remote's
URL lives in `.git/config`, the actor-owned file this entire module exists to defend against. Lazy
fetch therefore hands the actor an **egress channel out of the control plane** — it can point the
supervisor at a host of its choosing and make it emit a request — and a served payload whose content
depends on what that host returns. `-c` cannot close it, because the neutralization would have to
name the remote and the remote's name is the actor's to pick: a roster, again, where the environment
variable is the predicate.

**Revision 23's first defect and revision 24's first defect are one lesson, one axis apart.** Both
took a property that is *true at a moment* for a property that is *fixed*: a commit pin fixes
content but not repository completeness (revision 18); an open-time scan fixes what was true at open
but not what is true at request N. `.git/config` was already known to be actor-owned and mutable —
the whole of `autonomy/git.py` exists to say so — and `.git/shallow` sits beside it. **When a defense
reads an actor-owned file, the question is never "when do we check it" but "how do we stop git from
reading it."**

Revision 22 adds **§2.2, the slice contracts** — what each of 4a/4b/4c may assume, may not assume,
creates, modifies, must not touch, and owns in §5.3. It exists because revisions 19, 20 and 21 found
their defects in the *seam* rather than in the design: a slice handed an outcome it could not
structurally reach (twice), a type with two homes, a checker depending on a field a later slice adds.
Boundaries that live only in a header table get re-derived by each reader, and this one had already
been re-derived wrongly three times.

Writing it down immediately found a fourth, of the same kind and this time about a module rather than
a type: **there is no `open_run`.** Revisions 17–21 said the tree scan happens at "session open",
which reads as `evidence_broker/session.py`; that class is constructed *per request* from an
already-sealed model. A brokered run is opened by `autonomy/lifecycle.py::start_run`, the only place
that sees a pinned commit before any request exists. Scanning in `session.py` would have rescanned on
every request and still missed a run that opens and never serves. §3.1 and §2.2 now name the
function.

§2.2 also pins the three mechanisms 4a must ship *for* 4b — `history_traversal_error`, the `run_git`
ceiling, the byte bounds — so they are consumed rather than written twice with two spellings, and states the one
asymmetric edge in the seam: 4b **imports** `serve.py` and **must not modify** it, because replay's
determinism is the canonical invocation itself, and a checker that reimplemented serving would be
comparing its own output to the broker's.

Revision 21 closes four defects in revision 20, two of them in revision 20's own fixes.

1. **The `run_git` ceiling gave one disposition to four different conditions** (§3.2). Revision 20
   wrote "each fails the same way", which journals an overflow of `stderr` or the `config --list`
   preflight — both governed by mutable repository state, not by the pinned commit. An entry served
   before `.git/config` grew would refuse at replay, fail to match, and return
   `EXPOSURE_UNREPRODUCIBLE`: **an honest review refused because the actor edited a file afterwards.**
   That is the defect revision 20 had just removed from `history`, rebuilt one paragraph later in the
   fix for something else. Disposition now follows determinism: served stdout is a journaled
   `Denial`; `stderr` and the preflight fail the invocation; the tree scan refuses to open the
   session.
2. **`check_correspondence` could not produce its own first outcome** (§5). The signature required an
   `EvidenceExposure` while §5.3's first row is `NO_EXPOSURE`. `EvidenceExposure | None` — the same
   defect as revision 20's lens precondition, one slice over, and the second time a slice was handed
   an outcome it structurally could not reach.
3. **`Correspondence` had two homes and the checker module had two names** (§2). §2 placed it in
   `audit/record.py`, revision 20 claimed 4b touches no audit-record model, and §2's tree said
   `correspond.py` against §5's `correspondence.py`. It ships in `evidence_broker.py` beside
   `Outcome`, which moved there for the same reason: it is the broker's verdict vocabulary, and
   `audit/record.py` imports it. 4c must know this before it can store the type.
4. **A roster row certified nothing** (§7). With 4a guaranteeing an NFC tree, keying the served map on
   "raw path bytes" is either identical after decoding or a bytes-vs-str type error, so the row
   measured neither normalization nor coverage. Deleted; 4a's tree tests own normalization. A vacuous
   parametrization inside the roster written to prevent vacuous parametrizations is worth recording
   plainly.

**§5.3's three columns are set in two slices**, now stated: 4b owns the classification, while
"Stored?" and "Counts as support?" are `append_review` and `confirmation_count`, both 4c.

Revision 20 comes from review of revision 19 and closes four defects, three blocking. Three of them
are **failures of the split itself** — not of the design that was split — which is the lesson worth
carrying: dividing a plan creates new claims about what each side may assume, and those claims
inherit none of the review the undivided design received.

1. **The checker depended on a field its own consumer's slice would add** (§5). `check_correspondence`
   took a `review`, but the merged `Review` has no `evidence`; that field arrives with 4c. Fixed by
   taking `Sequence[Evidence]` — which is also the honest signature, since the checker reads nothing
   else off a review — leaving 4b touching no audit-record model at all.
2. **The agent cross-checks were stated as one rule with one precondition** (§4.2). `agent` and
   `model` live on the run record; the instrument lives on the *exposure*, which the `NO_EXPOSURE`
   path is defined by not having. The boundary demanded an instrument in the one case defined by its
   absence. The lens check is now conditional, and costs nothing where it is dropped because an
   unbrokered review is `unwired` and earns no support.
3. **Revision 18 wrote a classification rule the checker cannot implement** (§3.2). Calling
   git-version drift `unwired` requires observing a cause no sealed term records; only shallowness is
   checkable. Every completed replay mismatch is `violated`, and the residual is stated instead.
4. **The payload ceiling covered the requests an actor asks for and not the captures the broker
   performs itself** (§3.2) — `stderr` on every call, the `config --list` preflight that runs before
   every call, and the new full-tree scan.

The fourth is the same shape as revision 18's third and worth naming as a pattern: **a bound placed
on the quantity that prompted the question rather than on the mechanism that holds it.** The journal
was bounded and the payload was not; then the payload was bounded and every other capture was not.
The mechanism here is `run_git`, and the bound belongs there.

Revision 19 splits plan 4 in three rather than two, on a seam revision 18's own findings exposed.
Three of its five defects — the NFC tree rule, the shallow refusal, the payload bound — are not
preparation for correspondence at all. They are **wrong answers the shipped broker gives today**: a
path reported absent that exists under another spelling, a history whose result depends on clone
depth, an allocation with no ceiling. Bundling them into the checker's plan would hold repairs to
merged code behind the design of a component that does not exist yet.

Two further reasons the seam is real rather than tidy. The payload ceiling belongs to `run_git`,
which `extract`, `toolkit_is_clean` and a validate check also use — blast radius outside the broker
entirely, and not something to review inside a plan headlined "correspondence". And bumping
`REPLAY_PROTOCOL_VERSION` in the slice that changes serving lets the checker be written against a
stable protocol instead of bumping the very thing it is learning to parse.

So: **4a serving hardening, 4b the checker, 4c the boundary.** The shallow rule divides along that
line without being forced to — refusal at serving is 4a, `unwired` classification at replay is 4b,
which is where replay lives regardless. **Revision 17's and 18's log entries below use "4a" for the
checker and "4b" for the boundary; from revision 19 those mean 4b and 4c.** The entries are left as
written because a revision log is a record of what was decided when, not a document to be
back-edited.

Revision 18 comes from review of revision 17 and closes five defects, three of which would have
voided plan 4 outright. They are worth reading as a set, because four of the five are one shape: **a
claim about determinism or trust that held for the case the author had in mind and for no other.**

1. **Identity was asserted by the reviewer** (§4.2, §5.4). `reviewer_kind` sat on `ReviewSubmission`
   while §5.4 branched on it, so an agent could label itself `human` and skip §5 entirely — the whole
   spec bypassed by one string — and could vary `reviewer_ref` or `lens` to mint several `review_id`s
   from one run. §0's boundary 2 had already stated the rule ("recompute actor-supplied provenance at
   the boundary rather than accepting it"); §5.4 had simply never applied it to the field that
   decides whether the rest of the design runs. Identity moves to a `ReviewAttestation` and, for
   agents, is cross-checked against the run record and the sealed instrument.
2. **A pinned commit does not make `history` deterministic** (§3.2). It fixes ancestry only if the
   repository *has* the ancestry. Reproduced here: identical commit, identical canonical argv, two
   commits from a full clone and one from a `--depth 1` clone, both at exit 0. Replay in a different
   clone would have called honest evidence `EXPOSURE_UNREPRODUCIBLE` and refused the review.
3. **Served payloads were unbounded** (§3.2). Plan 3 derived a bound for the journal and left the
   payload — the far larger quantity, held in memory by `run_git`, written to `served/`, and read
   again at replay — with none at all.
4. **Replay memoisation keyed on `(commit, op, target, pathspec)`** (§5.2), omitting the sealed
   surface policy that changes both authorization and the exclusion pathspecs. Removed rather than
   re-keyed: nothing here has been measured.
5. **§5.2 and §5.4 contradicted each other about the baseline** (§5.2, §7), and §7's test list
   encoded the wrong one. §5.4 governs.

The fourth pattern below — a named component guaranteeing the opposite of what was wanted — has a
sibling here worth naming on its own: **a guarantee inherited from the wrong axis.** The commit pin
was treated as making every operation reproducible, when it fixes *content* and says nothing about
*repository completeness*; and the journal's bound was treated as bounding the record, when it bounds
one of the two files a run writes.

Revision 17 designs the correspondence slice and, in doing so, closes the NFD residual §3.1 parked
for plan 3 and plan 3 did not take. It is the first revision where a *parked* residual, rather than a
review finding, turned out to be load-bearing for the section that came after it.

Revision 11 recorded the residual as one failure — `search` serving past a deny prefix — because it
read §3.1 against §3.2. Read against §5.1 instead, the same root cause has **three** directions, and
only the first was ever written down:

1. *Leak.* `:(top,literal,exclude)café` in NFC excludes no NFD tree entry, so `search` serves what the
   policy denies.
2. *False refusal.* `LocationEvidence.path` is forced to NFC, so an honest citation into an NFD path
   can never match a served map keyed on the tree's own bytes. §5.3 classifies that as
   `CITATION_UNSERVED`, which **refuses the review**. The checker built to catch fabrication would
   have rejected honest work instead.
3. *False absence.* A `read` of the NFC spelling against an NFD tree entry returns `MISS_ABSENT`,
   which §5.1 defines as "the path is not at the commit, and that was served as the answer" and makes
   citable. An agent could claim a file does not exist, be wrong, and be certified `verified`.

**Revision 31: none of this is really about Unicode.** A tree path holding a **backslash** walks
directions 2 and 3 unchanged — `normalize_project_path` maps `\` to `/`, so `a\b.txt` is uncitable
under its own name, and a `read` of it authorizes as `a/b.txt`, misses, and certifies the absence of
a file that exists. The three directions are consequences of *any* divergence between the tree's
spelling and the normalizer's output; NFD was simply the first one found. §3.1's rule is therefore
stated against the normalizer rather than against an encoding, and this analysis holds verbatim with
"NFD path" read as "path the normalizer would rewrite".

Direction 3 is the one that decides the design. It involves no collision, no deny prefix and no
search — one such path anywhere in the tree is enough — so no filter on the serving side reaches it.
**The session therefore refuses at open any pinned tree holding a path that does not decode as UTF-8,
or that `normalize_project_path` does not return unchanged**, verified by one
`git ls-tree -r -z --name-only` pass. All three directions become
unreachable at once, in the one layer that can still refuse, instead of three guards in three layers.
The serve-time post-filter that revision 17 first proposed came back out: it defended direction 1
only, and it would have read as coverage.

Two properties are worth stating because they are what make one check sufficient. The pinned commit's
tree is immutable, so a session that opened without a violation can never develop one and **replay
inherits the guarantee without re-checking it**. And a colliding pair — `café` and `café` both
present, which is what makes an NFC-keyed served map unsound — is subsumed, since at least one member
of any such pair is non-NFC.

`REPLAY_PROTOCOL_VERSION` goes to 2 even though no serving byte changes. §5.2's rule bumps on a
change to serving or parsing; here the *guarantee* changed, since a v1 exposure may come from an NFD
tree and a v2 one may not. Measured at design time: no control-plane directory exists on this machine
and no stored record anywhere carries an exposure, so the bump invalidates nothing, and a stale v1
control plane reads as `unwired` / `REPLAY_PROTOCOL_MISMATCH` rather than being silently trusted.

Revision 16 comes from a sixth review round and closes three gaps in revision 15's fixes. The
"derived" journal bound counted one `\\uXXXX` escape per Python character, but a non-BMP character
is encoded as a UTF-16 surrogate pair -- twelve JSON bytes, not six -- and inline seeding never
consulted the per-entry bound at all. The model now constrains every variable-width journal field,
the ceiling is checked against actual maximally encoded request and inline events, and *every* line
is bounded before the journal is created or served bytes are delivered. Descriptor anchoring also
protected the write while leaving the receipt behind: if an ancestor is renamed after capture, the
bytes land safely through the descriptor but the original pathname no longer names them. The served
directory's descriptor and receipt pathname must therefore still identify the same directory before
the exposure is appended.

Revision 15 comes from a fifth round and is the *same* rule again, twice more, plus one claim that
outran what the plan delivers. Anchoring the directory is not anchoring the file: a re-opened name
passes every check on both opens because none of those checks is about identity, so a count taken
from one inode and an append made to another silently un-spends a round. And §3.5's bound on the
journal was a chosen constant with no relationship to what the model admits, which is a run able to
*write* a journal it can never *read back* — the fail-open arriving through arithmetic rather than
through a filesystem call. Revision 15 attempted to derive the bound from the model's own limits and
to refuse over-long input before the spend; revision 16 corrects that derivation. Revision 14's claim
that "every operation on `run_dir` is
anchored" was also broader than the truth: `baseline.json` is still pathname-based, and that residual
is now named rather than implied away.

Revision 14 comes from a fourth review round on plan 3 and is the second pattern in its
filesystem form. §3.5 said `served/` "is created under the same containment check as the journal" and
stopped there — a claim about *where* the directory is, standing in for a claim about *how it is
reached*. Because `run_dir` holds an actor-writable `served/`, every name in it is actor-controlled,
so a lexical check followed by a pathname `open()` checks one object and opens another. §3.5 now
states the descriptor-anchoring rule the repository already follows, and states it once, at the place
that owns the run directory, so plan 4 inherits it rather than rediscovering it.

Revision 13 comes from review of plan 3 and closes two more fail-opens, both of the first pattern.
`InlineInput.target` had no specified spelling, and the absolute path an implementer would naturally
store is one `LocationEvidence` can never express — a manifest entry granting `FULL` coverage that no
citation can reach (§4.3). And §3.5 did not order the served-file write against the journal append; an
entry appended first claims an exposure a failed delivery never made, and replay confirms it, because
replay re-serves from the commit and never looks at `served/` (§3.5). Both are cases where the honest
path and the fail-open path look identical in prose and differ by one line of code.

Revisions 10 and 11 come from *building* plan 2 rather than reading it, and both are the second
pattern again. Revision 10 corrects §5.1's grep output format, which said `<commit>:<path>:<line>:`
through nine revisions while §3.2.1's own table pinned `-z` — the two sections were each internally
right and disagreed with each other, and plan 3 is the reader that would have been wrong. It also
records the two actor-owned channels `-c` hardening does not reach, found by the whole-branch review
after all four per-task reviews had passed: an untracked `.gitattributes` with `* binary` blinds every
grep hit at exit 0, and `.git/objects/info/alternates` prepends a warning that turns every defined
miss into a halted run. Revision 11 records the parked NFD residual in §3.1. The lesson these three
share is §7's, arrived at from the other side: none was found by reading the design, and none would
have been found by a suite that did not try to break its own guards.

Revision 12 is what reading §3.3, §3.4, §3.5, §4.1, §5.1 and §6 *against each other* produced before
planning the session slice, and its centre is the first pattern again, in the place it costs most. A
**refused** request had no row in §5.1's coverage table. It must be stored — `requests_used` is
derived by counting request events, so an entry omitted from the seal makes the record disagree with
the log it counts — and it replays to an empty payload. A served-map builder that classifies by
operation and payload rather than by outcome therefore records the *denied* path as `FULL` with a line
count of zero, which under §5.1's own rules admits a path-only citation and permits `pointer`. An agent
could request a withheld file, be refused, cite it, and earn support under §4.2.1. Every individual
sentence was right; the table simply had no row for the case, and the missing row fails open onto the
exact material a blinding study exists to withhold. §4.1 now seals the outcome and §5.2 checks it, on
the same reasoning that already justified sealing `sha256`: a value that is *checked* is not the
actor's account of itself. Three smaller corrections travel with it — journal creation moves to
`start --broker-spec` (§3.4.1), an exhausted budget journals nothing because that is what keeps
`requests_used <= budget` true rather than a courtesy (§3.3), and a refusal writes no `served/` file
(§3.5).

Five patterns run through what review kept finding, and each predicts where the implementation will go
wrong.

**Guards narrower than the rule they enforce.** `any(location)` where the rule was "everything was
checked". `line` and `span` forbidden under weak coverage while `pointer` walked through the gap. A run
slug where the rule needed a project identity. A guard that restates its rule on one axis and leaves the
others open reads, on the page, exactly like a guard that works.

**Claims that outran their mechanism.** "Determinism comes free from the pin" — until repository config
decides what a pattern means. "Sealed runs are unaffected by a project move" — while the checker still
took a live session. Both were true of the intent and false of the design, and prose is where that gap
hides, because a sentence can assert a property no field implements.

**Fixes applied to the headline and not to the path production takes.** Revision 5 sealed every replay
input into the exposure, corrected `check_correspondence`'s signature — and left `append_review`, the
only caller that ships, still resolving a baseline. The schema was right, the checker was right, and a
project rename would still have zeroed every agent review in the run. A property proven on the path
nobody uses is not proven.

**Internally consistent, externally contradictory.** §3.5 had the reviewer write served bytes to a
caller-supplied `--output PATH`. Nothing in this document objected, because nothing in this document
owns the write surface: the shipped autonomy envelope does, and at `report-only` it permits exactly one
in-tree write — the run's own report (`autonomy/path_gate.py`). Every served file would have been a
gate denial. Six review rounds inside one document cannot find that, because the contradiction is not
in the document. It is between the document and the system it runs inside, and it surfaced the moment
the two were placed in one program (§0, §3.5).

**Locally coherent, globally contradictory.** The seal replayed in §3.4.1, did not in §5.2, and could
fail for exactly one non-replay reason in §6. No section was wrong on its own terms; the document was
wrong only as a whole. Review that reads a section closely cannot find this, and neither can a reader
who trusts the section nearest to hand — which, for an implementer, is whichever one the task cites.
The countermeasure is to read every section that touches a mechanism together before building it, and
to state the mechanism once, in the section that owns it, with the others pointing at it.

Hence §7's discipline, and three additions to it: where the document *claims* a property, the suite
establishes that property **under the condition the claim names** — replay with the control-plane
directory deleted, not merely replay — **through the production entry point**, not only against the
function whose signature was corrected, and **against the shipped components it composes with**, not
only against its own.

## 0. Where this sits

This is **Spec 2a** of the autonomous-audit program. The program's slices, with the two former
sub-projects renamed into it:

| Slice | Owns | State |
|---|---|---|
| Spec 1 | finding convergence — one emitted `AuditFinding`, fingerprint identity, the `doc/audits/cases/` store, trusted ingestion | **shipped** |
| **Spec 2a** | **the evidence broker — what an agent was shown, recorded and replayable; the addressable control plane** | **this document — all seven plans merged; 4c at `1c11c922`** |
| Spec 2b | the dispatch harness — who spawns reviewers, how many run at once (formerly sub-project B) | [designed](2026-08-02-supervised-run-harness-design.md) |
| Spec 2c | `/science:review-plans` — the first lens agent (formerly sub-project C) | not designed |
| Spec 3 | how many confirmations promote a finding, and by whose authority | not designed |

**Why 2a goes first, for two reasons that are not the same reason.**

The first is the compatibility window this document already argues from (§4.2): no stored record
anywhere carries `reviewer_kind`, so the invariant "an agent review requires a `correspondence`"
needs no data migration today. The second is independent of correspondence entirely: `run_dir` (§3.4.2)
is what makes a run addressable from its id, and 2b cannot dispatch N assignments and later resolve
them without it. Today `science autonomy start --baseline-out` takes an arbitrary supervisor-chosen
path (`autonomy/cli.py`), so nothing can find a run it did not itself place. 2a ships that addressing
layer as a side effect of needing it; building 2b first would mean inventing a weaker one and
retiring it.

Both windows close on the same event — **2c, the first lens agent** — and a third closes with them:
Spec 1's ingestion path has never processed a report, because no producer of reports exists. That
is the argument for 2b's first actor being **deterministic** (`science health` writing the run's own
report, ingested through the shipped path) before any lens runs. Spec 1's own rationale was that the
first agent should not be the experiment that discovers the finding type is incomplete; the same
sentence holds one layer out, for the harness. 2a places no other constraint on 2b.

**Three boundaries the two numbering schemes left unowned.**

1. **Eligibility is 2a's; the threshold is Spec 3's.** §4.2.1 rewrites `confirmation_count()`, and
   Spec 1's design reserves "review eligibility rules, the confirmation threshold, and promotion
   authority" for Spec 3. The split that makes both true: 2a decides whether an agent confirmation
   *counts as support at all*, which is a question about whether the testimony was checkable. Spec 3
   decides *how much support is enough*, and inherits the count without reopening what feeds it.
2. **The case store gains a second trusted writer.** Spec 1 established `ingest_report` as the
   attested boundary into `doc/audits/cases/`; §2.1 adds `append_review` beside it, because reviews
   are not part of an `AuditReport` and never pass through ingestion. Two writers, one store, one
   discipline: both take the store lock through the anchored-descriptor path, and both recompute
   actor-supplied provenance at the boundary rather than accepting it.
3. **2a ships no dispatch and no agent.** In-process sessions (§3.4.1) exist so 2b can hold them in
   the supervisor; that is an interface 2a offers, not a harness it builds.

## 1. The problem

`Review` admits `reviewer_kind="agent"` and carries **no evidence field at all**. An agent's
`confirms` is therefore accepted on its own authority: nothing records what the agent was shown,
nothing checks that what it cited was ever in front of it, and nothing distinguishes "this agent
looked and found nothing" from "this agent could not look". Agent-authored findings and reviews are
modelled but unshipped — no lens agent exists until 2c — so the cost of fixing this is at its minimum
right now and rises the moment a producer exists.

The failure is not hypothetical. In a downstream project a fabricated citation survived four months
and produced a Strong finding, because the chain from claim to source was never mechanically closed.
An agent review is the same chain with a faster writer.

This design closes it: evidence an agent sees is **served and recorded** rather than taken, a
citation that does not correspond to what was served is refused, and an agent confirmation that
could not be checked earns no support.

### Threat model

**2a bounds confabulation and drift, not filesystem-level forgery.** The reviewer is treated as
capable but unreliable: it will cite from memory, cite a plausible path it never opened, cite a line
number it inferred from a symbol name, and report an absence it did not verify. Every mechanism here
targets that.

It does not defend against an actor running as the same uid that deliberately edits the artifacts.
Such an actor can append a journal entry naming a file that really exists at the pinned commit, and
that entry replays perfectly; it can also hand-edit a stored case. Two consequences follow, and both
are load-bearing below:

1. Everything trustworthy is anchored in `RunBaseline` — outside the project tree, exclusive-create,
   integrity-sealed — and never in argv or in the tree the actor writes.
2. Values the actor could supply are **recomputed at a trusted boundary and overwritten**, never
   accepted. `AuditReport.ingestion_ref` already documents this idiom in this codebase: "Actor-claimed
   … Trusted ingestion writes the independently attested equal value, never this field on its own
   authority."

An actor with write access to `RunBaseline`'s directory defeats 2a entirely. That is the same
assumption the autonomy envelope already makes, and 2a does not weaken it.

### What this design does NOT own

- **The judgement schema.** Lifecycle vocabularies, action verbs, remaining-work structures are 2c's.
  2a knows only that a review cites evidence and may declare uncertainty.
- **Blinding.** `drift_sample/blind.py` redacts authored claims from a document under review. That is
  a property of a study, not of a broker. 2a serves bytes as they are at the commit.
- **Dispatch.** Who spawns reviewers, and how many run concurrently, is 2b's.
- **Pluggable backends.** Git at a pinned commit, and nothing else.

### Prior art carried over

The mechanisms below were proven over five contract revisions in a downstream project
(`natural-systems` `task:t851`), where each was adopted only after the preceding version's failure was
reproduced. They are stated here as requirements, not as history.

## 2. Architecture

```
science/src/science_tool/evidence_broker/     # NEW
    policy.py     containment + caller-supplied deny prefixes -> Denial | None
    serve.py      three git ops at a pinned commit; defined-miss vs raise
    journal.py    append-only per-run log, outside the project tree
    session.py    budget-enforcing session over policy + serve + journal
    hits.py       `git grep -n -z` record parsing; pure bytes -> (path, line)
    correspondence.py  the join, the replay, the coverage-aware outcome
    cli.py        `science evidence serve`   # the only actor-facing command; §3.4.1, §3.5

science/model/src/science_model/
    correspondence.py    # NEW (plan 4b) — Correspondence ONLY; imports pydantic and nothing else
    evidence_broker.py   SurfacePolicy (shipped, plan 2); + Outcome, ExposureEntry,
                         InstrumentIdentity, InlineInput, EvidenceSession, EvidenceExposure
    autonomous_runs.py   + AutonomousRunRecord.evidence
    audit/record.py      + Uncertainty, ReviewAttestation, ReviewSubmission; THREE Review fields
                           — evidence, uncertainty, correspondence (the last importing
                           Correspondence from science_model/correspondence.py);
                           + Review.counts_as_support(), which confirmation_count() now delegates to
    audit/__init__.py    + re-exports Uncertainty, ReviewAttestation, ReviewSubmission beside Review

science/src/science_tool/
    autonomy/baseline.py    + EvidenceSession on RunBaseline; journal path containment-checked
    autonomy/control_plane.py  # NEW — the project-and-run-keyed canonical root
    autonomy/git.py         + a probed, canonical invocation for `grep` and `log`
    autonomy/lifecycle.py   start_run opens the session; finish_run seals it
    findings/reviews.py     # NEW — the trusted review-append boundary
    findings/storage.py     + locked_store, moved out of ingest.py and raising CaseStorageError
    validate/checks/review_confirmations.py  # NEW — review.uncounted-confirmation, info severity
    validate/findings.py    + that rule id in _POLICY_INFO_RULE_IDS, so the finding keeps its
                              rule, qualifiers, fingerprint and suppression
```

`serve.py` uses `autonomy/git.py`, the existing hardened runner that neutralises `core.fsmonitor`,
`core.hooksPath`, and configured `filter.*` drivers. Those config keys name programs git executes; a
broker shelling bare `subprocess.run(["git", ...])` into a repository someone else can write inherits
that hole.

The package is named for the generic property — evidence is brokered — not for the study-specific use
(blinding a reviewer to a comparison group).

`autonomy/control_plane.py` is the one new component here that is **not** broker-private, and it lives
under `autonomy/` rather than inside `evidence_broker/` for that reason. Addressing a run by its id is
what 2b needs to dispatch and later resolve N assignments, brokered or not; 2a happens to be the slice
that discovers the need first (§0). Nothing in it mentions evidence.

### 2.1 There is no review-append path today, so 2a builds one

**Revision 1 named `findings/ingest.py` as the enforcement point. That was wrong.** `ingest_report()`
consumes an `AuditReport`, whose payload is `findings`, `accepted`, `metrics`, `caveats`, `unwired`,
`totals`, `meta` — no reviews. `AuditFindingRecord.with_review()` has exactly one caller in the
repository and it is a test. Placing correspondence enforcement in ingestion would have gated a door
that does not exist.

2a therefore defines the boundary it needs: `findings/reviews.py::append_review()`. It is the only
production writer of a `Review`, it takes the store lock the way `ingest_report` does, and it is where
correspondence is computed. §5.4 specifies it.

### 2.2 Slice contracts for plan 4

**This section is authoritative for the seam.** Where a revision-log entry above describes a slice
boundary — revision 19 on where the shallow rule falls, revisions 17–22 on where `Correspondence`
lives — the log records what was decided then and §2.2 records what holds now. A log entry is not
back-edited; it is superseded.

Plan 4 ships as three slices (header table). Revisions 19–21 each found defects **in the seam rather
than in the design** — a slice handed an outcome it could not reach, a type with two homes, a
dependency on a field a later slice adds — so the boundaries are stated here explicitly rather than
inferred from which section a paragraph sits in. Dependency runs strictly `4a → 4b → 4c`; **no slice
may reach backwards**, and each is independently mergeable.

| | **4a — serving hardening** | **4b — the checker** | **4c — the boundary** |
|---|---|---|---|
| **May assume** | plans 1–3 as merged; nothing about correspondence | 4a's guarantee below; that `LocationEvidence` exists (it is merged) | 4b's `check_correspondence` and `Correspondence` |
| **May NOT assume** | that any checker exists | that a stored `Review` has `evidence` — it does not until 4c | that it may classify an exposure itself — outcome, coverage and protocol are 4b's, and 4c calls `check_correspondence` for all three |
| **Creates** | — | `evidence_broker/hits.py`, `evidence_broker/correspondence.py`, `science_model/correspondence.py` | `findings/reviews.py`, `validate/checks/review_confirmations.py` |
| **Modifies** | `autonomy/lifecycle.py` (tree scan + traversal check, at `start_run`), `autonomy/cli.py` (map hardened-git open failures to the documented exit 2), `evidence_broker/serve.py`, `autonomy/git.py`, `science_model/evidence_broker.py` (bounds + protocol) | — | `science_model/audit/record.py`, `science_model/audit/__init__.py` (re-export the three new types), `findings/storage.py` (gains `locked_store`), `findings/ingest.py` (loses `_locked_store`), `findings/paths.py` (**primitive-owned lock validation and descriptor teardown failures stay inside `PathSafetyError` without replacing an active caller exception**), `validate/checks/__init__.py` (register the new check), `validate/findings.py` (`_POLICY_INFO_RULE_IDS`) |
| **Consumers, unchanged** | — | — | `findings/cli.py:317` — the call site is untouched; what `confirmation_count()` returns changes underneath it |
| **Must not touch** | `science_model/audit/*` | **any stored-record model** — `audit/record.py` above all | `evidence_broker/serve.py`, `evidence_broker/correspondence.py`, `evidence_broker/hits.py`, `science_model/correspondence.py` |
| **Owns in §5.3** | — | the classification column | "Stored?" and "Counts as support?" |

**Revision 34 corrects three things about 4c's cells, all of the same kind: a cell must state what
the slice's diff actually touches.**

- **`findings/cli.py:317` was never an edit.** It is the `confirmation_count()` call in the findings
  display payload, and 4c changes what that method returns, not the line that calls it. Listing a
  consumer under *Modifies* invites an implementer to manufacture a change there to match the
  contract. It moves to its own row.
- **The cell was short by four files.** `audit/__init__.py` re-exports `Review` and must re-export
  its three new peers, or consumers reach past the package's public boundary into `audit.record`.
  `findings/storage.py` and `findings/ingest.py` move `locked_store` (§5.4). `validate/findings.py`
  must list the new rule in `_POLICY_INFO_RULE_IDS`, or `validation_observation` degrades every
  `info` result to a bare `ValidationNotice` — no rule, no qualifiers, no fingerprint, and therefore
  no suppression. A check whose findings cannot be suppressed is a check that will be deleted.
- **The fence grew because 4b is merged.** 4c consumes `check_correspondence` and the
  `Correspondence` type; neither is its to adjust. The reason `serve.py` was fenced off from 4b
  applies unchanged one slice over — a caller that edits its callee to suit itself has erased the
  boundary that made the slices independently reviewable.

**The guarantee 4a hands forward, stated as three clauses because 4b is entitled to rely on each and
on nothing beyond them.** Every exposure sealed at `REPLAY_PROTOCOL_VERSION = 2`:

1. was served from a tree whose every path **decodes as UTF-8 and is returned unchanged by
   `normalize_project_path`** — the two parts in that order, since the second needs a `str` before it
   can run, and NFC is one of several things it subsumes (§3.1);
2. was served under a per-request byte ceiling, with overflow refusing rather than truncating; and
3. was served **entirely from objects the local repository already held**, by a traversal git did not
   silently truncate. A repository that cannot supply an object locally **fails the invocation** —
   it neither answers short nor goes to the network to fill the gap (§3.2).

Clause 3 is deliberately not "was served from a complete clone." Revisions 22 and 23 both claimed
more than the mechanism delivers: `is_shallow() == False` (revision 26's spelling, replaced at
revision 27) is a statement about one file — and under the pin it was not even that — while the
pins convert missing data into failure. Neither certifies that every object is present, and a
damaged repository remains possible. What 4b may rely on is *what is not among the outcomes*: a
truncated answer, and a payload assembled from a remote. A repository broken some other way surfaces
as a non-zero exit and reads `unwired`, which 4b already handles.

**Ask what a guarantee is *about*, not what it is near.** This clause has now been wrong three ways,
each a different overshoot or undershoot: revision 22 said "no `history` entry originating in a
shallow repository" (false — revision 18 journaled such refusals); revision 23 said "complete clone"
(unobservable); revision 24 said "unable to supply an **ancestor**", which named the shallow case and
missed the partial-clone case sitting next to it, where the missing object is a *tree* and git
fetches it rather than failing. Revision 24's own correction of revision 23 was for claiming more
than the mechanism delivered — and it then wrote a clause narrower than the hazard. **Overshooting
and undershooting the same sentence are one error**: describing the mechanism you happen to be
looking at instead of the property the consumer needs.

Clause 1 is what licenses 4b to key its served map on the decoded path without re-normalising — and
it licenses that **only in the round-trip spelling above**. Revisions 19–32 wrote it as "valid UTF-8
and already NFC" while the sentence immediately below drew the no-re-normalisation conclusion from
it, which does not follow: NFC says nothing about a backslash, and `normalize_project_path` rewrites
one. A guarantee and the entitlement it grants sat two lines apart, disagreeing, for fourteen
revisions. The round-trip form is the property the entitlement actually needs, and it is the same
predicate §3.1 enforces at open — one sentence, one mechanism, stated once on each side of the seam.

It is also what licenses 4b to perform no tree scan of its own (§5.2). A 4b implementer who adds a
normalisation guard "to be safe" is not adding safety — they are adding a second place for the rule
to be stated and a second place for it to drift.

**"Session open" is `start_run`, not `Session`.** There is no `open_run`: a brokered run is opened by
`autonomy/lifecycle.py::start_run`, which is where the journal is created and the `EvidenceSession`
is sealed into the baseline, and it is the only place that sees a pinned commit before any request
exists. `evidence_broker/session.py` constructs a `Session` per request from the already-sealed
model and is therefore **not** where a once-per-run tree scan belongs — putting it there would rescan
on every request and still not cover the run that opens and never serves. 4a is expected to leave
`session.py` unchanged.

**4b replays by calling `serve.py`, and modifies nothing there.** Replay's determinism *is* the
canonical invocation (§3.2.1); a checker that reimplemented serving would be comparing its own output
to the broker's, which is not a check of anything. So 4b depends on 4a's module without owning it —
the one place in this seam where "may not modify" and "must import" both apply.

**Three shared mechanisms belong to 4a, so that 4b consumes rather than reinvents them.** Each is
needed on both sides of the seam, and each would otherwise be written twice with two spellings:

- **`autonomy/git.py::history_traversal_error(repo, commit) -> str | None`** — 4a refuses to open a
  run, 4b classifies a replay environment. Revision 22 declared it shared without naming a module,
  which is how one mechanism becomes two functions; revision 27 renamed it when the predicate it
  wrapped turned out to be a proxy the pin blinds.
- **`GIT_SHALLOW_FILE=/dev/null` and `GIT_NO_LAZY_FETCH=1` in `_ENVIRONMENT`** (§3.2). 4b inherits
  them by calling `serve.py`, and inherits them *silently* — which is the point: replay is
  deterministic, and stays off the network, because the environment is pinned, not because 4b
  remembered to check anything.
- The `run_git` output ceiling, including its refuse-not-truncate discipline.
- `MAX_SERVED_BYTES` and `MAX_RUN_SERVED_BYTES`, in `science_model/evidence_broker.py` with the
  other bounds.

**When a slice finds a defect in a neighbour's cell, the fix ships in the neighbour's cell**
(revision 31). 4b's review found that §3.1's tree rule admits a backslash path, which certifies a
false absence — a 4a fail-open, in `autonomy/lifecycle.py`, a file 4b may not modify. The repair is a
**4a follow-up commit landing before 4b's fix wave**, not an amendment widening 4b's `Modifies` cell
to cover it. A contract amended once to accommodate the slice that happened to find a neighbour's bug
is a contract that will be amended again, and the seam's value is that it says the same thing in
month six as in month one. 4b owns the discovery; 4a owns the file. Sequencing, not scope, is what
moves.

**"Must not touch `audit/*`" was a proxy, and revision 23 replaces it with the claim it stood for.**
What must hold is that **4b changes no stored-record model**, so 4c inherits an unmodified `Review`.
Spelling that as a directory ban broke the moment `Correspondence` needed a home that is neither
`evidence_broker.py` (a cycle) nor `audit/record.py` (a banned file) — the ban would have forced the
cycle. A contract stated as a path is the same defect as a guard stated as a roster.

**What 4b imports from `audit/` and does not modify.** `Evidence` and `LocationEvidence` are merged
and unchanged by this plan; 4b reads them. The distinction matters because "must not touch
`science_model/audit/*`" would otherwise read as "must not import", which would make the checker
unable to accept a citation at all.

**Why 4b is mergeable with no production caller.** `check_correspondence` has none until 4c wires it
into `append_review`. That is the cost of the split and it is accepted deliberately: the alternative
is 4b landing alongside a boundary whose model changes it does not need, which is the coupling
revision 20 removed. It is fully testable in isolation — an exposure and a citation list are both
constructible without a `Review`.

## 3. The broker

### 3.1 Policy

```python
def authorize(request: EvidenceRequest, policy: SurfacePolicy) -> Denial | None
```

Containment is checked **before** any prefix, because a prefix check alone is walked around with `..`.

**A git path is normalized lexically and the filesystem is never consulted.** Revisions 1–4 borrowed
`reject_baseline_inside_project`'s dual as-spelled/resolved idiom wholesale, which is the wrong tool
here: it follows symlinks in the mutable working tree, while the served surface is
`git cat-file blob <commit>:<path>` — a blob read that never touches the working tree at all. Replacing a
base-commit file with a working-tree symlink would therefore deny a request that was entirely safe,
and resolving would buy no security in exchange, because there is no filesystem lookup to protect.

`normalize_project_path` is already the right function and is already what `LocationEvidence` uses:
it refuses `..` rather than collapsing it, refuses absolute paths, refuses NUL, and normalizes UTF-8.
Deny prefixes are then matched against the normalized form.

**Unicode normalization is where the two mechanisms can still disagree, and only half of it is
closed.** `normalize_project_path` maps a path to NFC; git stores path bytes verbatim and matches
pathspecs byte-exactly. So a policy and a repository can be spelled differently and both be right:

- *Authoring side, CLOSED.* A deny prefix written in NFD used to be silently stored as NFC, which
  meant the author's spelling never reached git and the policy they wrote was not the policy they
  got. `SurfacePolicy` now **refuses** a prefix whose NFC form differs from what was written, so the
  caller learns the policy cannot express what they meant. Failing early beats a silent weakening.
- *Repository side, CLOSED at revision 17 by refusing the tree rather than filtering the results.*
  Against a tree holding an NFD path (`cafe\xcc\x81/x.txt`), the NFC prefix — now the only spelling
  the model accepts — denies under `read` and **still serves under `search`**, because
  `:(top,literal,exclude)café` in NFC matches no NFD tree entry. Measured on git 2.55.

  Revisions 11–16 parked this as that one leak and nominated `serve` inspecting the tree's own path
  bytes as the fix. Both were wrong. The leak is one of three directions (header, revision 17), and
  the decisive one — a `read` returning `MISS_ABSENT` for a path that exists under another spelling,
  certifying a **false absence claim** — is reachable with no deny prefix and no search at all, so no
  amount of filtering on the serving side closes it.

  **A brokered run refuses to open against a pinned tree containing a path that does not decode as
  UTF-8, or that `normalize_project_path` does not return unchanged**, established by one
  `git ls-tree -r -z --name-only` pass at the pinned commit, in
  `autonomy/lifecycle.py::start_run` — the same place that creates the journal and seals the session,
  and the only one that sees the commit before any request exists (§2.2). UTF-8
  travels with NFC in the same check because a path that does not decode cannot be spelled as a
  `LocationEvidence.path` either, so it can never be cited honestly and refusing it is the same rule
  in the same place. `serve` is unchanged: with the tree guaranteed NFC, git's own pathspec matching
  is byte-exact against the only spelling the model can produce.

  **The third clause is revision 31's, and it is the rule the first two were an instance of.**
  Revisions 17–30 spelled the condition as "UTF-8 and NFC", which is what `normalize_project_path`
  happened to do to the *encoding* — while the same function also maps `\` to `/`, and nothing
  checked that. A tree path holding a backslash therefore survived the scan and reproduced direction
  3 below with no Unicode involved. Stated positively and as a predicate rather than a roster of
  characters: **a tree path is admissible only if `normalize_project_path` returns it unchanged.**
  That is one comparison against the function the citation side already uses, it needs no list of
  forbidden bytes to keep in sync, and it subsumes UTF-8, NFC, backslash, and anything the normalizer
  learns to do later. A path containing LF is admissible under it and is handled where it actually
  bites, in §5.1's parser.

The cost, stated rather than buried: a genuinely NFD-authored repository cannot be brokered until it
renames. That is narrower than it sounds — git on macOS sets `core.precomposeunicode=true` by
default, so macOS-authored *trees* are usually already NFC even where the working filesystem is not,
and revisions 11–16 overstated the exposure by treating filesystem behaviour as tree content.

The dual-spelling check stays where it belongs — on paths that really are filesystem paths and really
are opened: the baseline, the journal, the control-plane root, and the `served/` directory of §3.5.
All four are derived from `RunBaseline` rather than supplied, so the check defends the derivation
against a relocated control plane rather than sanitising an argument. Two kinds of path, two
disciplines, chosen by what the path is used for rather than by resemblance.

`Denial` carries two strings. `reason` is categorised and stays parent-side, for the audit. `notice`
is what the requester sees, and it is **policy-supplied**: this toolkit's existing denials are
deliberately informative because a human triages them, while a blinding study needs them uniform and
information-free, since a specific reason confirms the denied thing exists. 2a cannot decide which is
correct for a caller, so it does not.

**Deny prefixes are a parameter, not a constant.** 2a guarantees only that a supplied policy is
*honoured*. Proving a policy is *complete* — that it covers every artifact a study must withhold —
remains the caller's obligation.

**The policy is supplied once, to the baseline, and never again.** Revision 2 left it caller-supplied
per call, which is two defects at once. Deny prefixes are applied as `:(exclude)` pathspecs on every
search (§3.2), so they shape served bytes: a policy that differs between serving and replay makes an
honest run fail to reproduce. Worse in the other direction, a weaker policy at replay time
re-serves hits that were denied when the reviewer was actually working, and validates citations to
material the study withheld. `EvidenceSession.surface_policy` (§4.3) holds the canonical value; the
CLI has no flag for it.

### 3.2 Serving

Three operations, all resolved at a pinned commit: `read` (`git cat-file blob <commit>:<path>`),
`search` (`git grep`), `history` (`git log`). Reads go through the commit rather than the filesystem so
the surface is the frozen tree even when the working tree has moved on.

**`read` is `cat-file blob`, not `show`, because `show` serves a directory as content.** Revisions 1–8
spelled it `git show <commit>:<path>`. Measured against git 2.55: for a path naming a *directory*, that
command exits 0 and prints a tree listing — `tree <commit>:<path>`, a blank line, then the entry names.
Nothing distinguishes that from a file read, so the served map would record `FULL` coverage with a line
count over a directory listing, and a reviewer could then cite `private:3` in support of a claim about
what a file under `private/` contains, having been shown no file at all. The citation would correspond
mechanically while resting on nothing, which is the exact failure §5.1 exists to prevent.
`cat-file blob` refuses a tree outright — `fatal: git cat-file <commit>:<path>: bad file` — and emits
byte-identical output for a blob. It is a subcommand `autonomy/git.py` has not probed, so §3.2.1's rule
applies to it before it ships.

**`verify_commit()` runs once before any request is served, and the ordering is load-bearing.** For a
well-formed but nonexistent commit, git reports `path 'x' exists on disk, but not in '<commit>'` —
the same sentence it emits for a path added after the pinned commit. Miss classification is sound
only once the revision is known good.

**The read miss has two spellings and the classifier must know both.** `path 'x' does not exist in
'<commit>'` when the path is absent from the working tree as well, and `path 'x' exists on disk, but
not in '<commit>'` when it is present there. Both mean the same thing about the pinned tree, both exit
128, and a classifier that recognises only one turns an ordinary absent path into a halted run for
exactly the paths the actor happens to have created.

**A pinned commit makes `read` and `search` deterministic; it does NOT make `history`
deterministic** (revision 18). `git log` walks ancestry, and ancestry depends on what the repository
*has*, not only on the commit named. Measured on this checkout: one repository, two commits touching
a file; against the identical canonical argv and the identical commit, the full repository returned
**two** commits and a `--depth 1` clone returned **one** — *both at exit 0*. Nothing in the output
says which happened. An exposure sealed against a full clone and replayed in a shallow one would
therefore reproduce different bytes and be classified `EXPOSURE_UNREPRODUCIBLE`, which §5.3
**refuses** — the checker rejecting honest work, the exact failure mode §5.2 invokes to explain why
replay is bound to a protocol version at all.

`--no-replace-objects` is already pinned in `_HARDENING`, so grafts and replace refs are closed;
completeness is what remains.

**A check at open cannot deliver this, and revision 23 asserted that it could.** Shallowness is not a
property of the pinned commit and not a property fixed at open: it lives in `.git/shallow`, an
ordinary file in the actor-owned `.git` directory. Writing it takes no fetch. **Measured, git 2.55**,
one repository, three commits, one pinned commit: `git log` returned **3**; after a single
`echo <sha> > .git/shallow`, the identical argv against the identical commit returned **2** — *both
at exit 0*. This is `.git/config`'s vector with a different filename, and the module docstring in
`autonomy/git.py` already states the doctrine that answers it: the actor owns the file, so the
defense is an input git no longer reads, not a check racing the write.

**Two pins, not one — and the second closes a channel, not just a variance.** `.git/shallow` is one
way a repository declines to hold its own history; a **partial clone** is the other, and it fails in a
worse direction. A `--filter=tree:0` clone does not refuse the traversal: it **goes and gets the
missing objects from the promisor remote**, mid-request, at exit 0. Measured, git 2.55, against the
canonical `_LOG_ARGV`: **two `git fetch` subprocesses spawned**, three commits returned, nothing in
the output saying the network was touched. (The fixture must set `uploadpack.allowFilter=true` on the
serving side — it defaults to false, and without it the filter is silently ignored and the clone
comes back complete, which is the first way this test goes vacuously green.)

That is not merely non-deterministic. It makes a served payload depend on what a **remote** holds and
whether it is reachable, and the promisor remote's URL lives in `.git/config` — actor-owned, the
premise this whole module is built on. A supervisor that lazily fetches is a supervisor the actor can
point at a host of its choosing and cause to emit a request. Neutralizing on the remote *name* via
`-c` would be a roster (the name is the actor's to choose); the environment variable is the
predicate.

- **`GIT_SHALLOW_FILE=/dev/null` and `GIT_NO_LAZY_FETCH=1` join `LC_ALL` and `LANG` in
  `_ENVIRONMENT`.** They stand to `.git/shallow` and to promisor configuration exactly as `-c` stands
  to `.git/config`: they outrank the repository-local state and cannot be un-set from inside the
  worktree. Under `GIT_NO_LAZY_FETCH=1` the same partial-clone probe **fails locally at exit 128**,
  `fatal: unable to read tree`, having spawned nothing. Measured across the cases that matter:

  | repository | default | under the pins |
  |---|---|---|
  | `.git/shallow` planted, objects present | 2 of 3, **exit 0** | 3 of 3, exit 0 |
  | genuine `--depth 1`, objects absent | 1 of 3, **exit 0** | **exit 128**, `fatal: Failed to traverse parents` |
  | `--filter=tree:0`, objects fetchable | 3 of 3, **exit 0, 2 `git fetch` spawned** | **exit 128**, `fatal: unable to read tree` |

  Every row moves the right way. A planted boundary is ignored, and a repository that cannot supply
  an object locally **stops answering and starts failing**, which is this design's standing
  preference: `run_git` returns non-zero, no defined-miss message matches, the run halts `unwired`.
  No new disposition rule is needed — §3.2's table already routes it. Both pins are no-ops in an
  ordinary complete clone, which has no boundary file and nothing to fetch. `GIT_NO_LAZY_FETCH`
  covers `read` and `search` as well as `history`, since a partial clone withholds blobs from
  `cat-file blob` and `grep` by exactly the same mechanism — putting it in `_ENVIRONMENT` rather than
  at one call site is what makes that automatic.

- **A brokered run still refuses to open against a repository that cannot walk the pinned commit's
  ancestry**, decided by `autonomy/git.py::history_traversal_error` (`git rev-list --count <commit>`),
  in `start_run` beside the §3.1 tree scan — but it is a **diagnostic, not the guarantee**. It reports
  such a repository as an operator error at open, carrying git's own sentence, rather than as a
  `Failed to traverse parents` in the middle of a run. The two mechanisms cover disjoint intervals
  and neither depends on the other: at `start_run` no actor exists yet (§3.4.2's temporal argument),
  so an absence present then is genuine; anything appearing later is the actor's and the pin
  neutralizes it.

  **It asks the served property, not a proxy for it, and revision 27 is why.** `_LOG_ARGV` carries no
  `-n`, so `history` walks to the root — walking to the root is what to measure.
  `rev-parse --is-shallow-repository` asks instead whether a shallow *file* could be opened, and
  MEASURED, git 2.55, a **complete** repository reads `true` under `GIT_SHALLOW_FILE=/dev/null`:
  `is_repository_shallow()` sets its flag on a successful open, before reading a line, and
  `/dev/null` opens. Under the pin that predicate is constant-`true`. Giving the proxy its own
  unpinned environment would work and would re-admit an actor-owned file into a defense — an actor
  could refuse its own run's open by writing `.git/shallow`. MEASURED under the pins:

  | repository | `rev-list --count <commit>` |
  |---|---|
  | complete, 6755 commits | full count, exit 0, **42 ms** |
  | complete with `.git/shallow` **planted** | full count — the plant is ignored |
  | genuine `--depth 1` | **exit 128**, `fatal: Failed to traverse parents` |

  **Its reach is bounded, and saying so is the point.** MEASURED under the pins, `--filter=tree:0` and
  `--filter=blob:none` clones both report the full commit count; their *commits* are present. The tree
  case is already refused at open by the §3.1 tree scan (`ls-tree -r` → `fatal: not a tree object`),
  for free. The blob case is not pre-empted at open and fails mid-run at exit 128 — the pin working as
  designed. This diagnostic covers **missing commits**; the guarantee in §2.2 clause 3 rests on the
  pins, not on it.

  Revision 18 made this a per-request refusal that spent a round and was journaled; revision 23 moved
  it to open, because a journaled refusal is **not deterministic given the pinned commit** — it is
  determined by what the clone happens to hold. Replaying that honest exposure in a *complete* clone
  re-serves real history, the outcome no longer matches, and §5.3 returns `EXPOSURE_UNREPRODUCIBLE`:
  the reciprocal of the case revision 18 set out to fix, created by its own fix. That reasoning
  stands; what revision 23 got wrong was believing one open-time check *finished* the job.
- **At replay, a shallow repository is `unwired` / `EXPOSURE_UNREACHABLE`, never `violated`.** The
  environment could not answer the question; it did not answer it wrongly. Reaching for `violated`
  here would be the could-not-check / checked-and-found-false confusion §5.3 exists to prevent, and
  it would refuse reviews for the property of the machine replaying them.

  The pin narrows what this rule has to catch but does not retire it. Under `GIT_SHALLOW_FILE` a
  shallow replay host fails at exit 128, which reaches `unwired` through §5.3's "replay cannot run"
  row anyway — so the two agree, and 4b's explicit `history_traversal_error` check earns its place by
  naming the cause rather than by changing the verdict. That is worth keeping: `EXPOSURE_UNREACHABLE` on a
  history exposure is the one `unwired` an operator can actually fix, and "clone was shallow" is
  repairable advice where "git exited 128" is not.

**This reasoning does NOT extend to a git version or runtime whose output differs, and revision 18
wrote that it did** (corrected at revision 20). Untraversable history is checkable:
`history_traversal_error` answers before replay, so the cause is known and `unwired` is a conclusion
the checker can reach.
A git-version difference is not — the checker sees only that bytes disagree, exactly what a forged
record produces, and there is no sealed runtime term to distinguish them. A rule that classifies by a
cause the classifier cannot observe is unimplementable, and an implementer forced to guess would
reach for the fail-open: treat mismatches as environmental and stop refusing anything.

So **every completed replay mismatch is `violated`** (§5.3), without exception. Sealing a git version
into the exposure to recover the distinction was rejected for the reason §5.2 already gives against
comparing `toolkit_revision`: it would zero the support of every prior run on every git upgrade, and
a signal that fires on every upgrade is one people learn to ignore.

The residual is real and is stated rather than defended away: if git ever changes the output of one
of the three pinned invocations, honest historical exposures become `EXPOSURE_UNREPRODUCIBLE`. What
makes that acceptable is that it is *loud and caught upstream* — `tests/test_evidence_broker_
canonical.py` exercises these invocations against real git, so such a change surfaces as a suite
failure rather than as silently refused reviews, and the response is a deliberate re-probe under
§3.2.1 and a `REPLAY_PROTOCOL_VERSION` bump. That is the mechanism §5.2 designed for precisely this
event; it is a decision someone makes, not a classification the checker invents.

**Served payloads are bounded, and the bound is enforced before the bytes are held** (revision 18).
`run_git` captures a child's entire stdout in memory and the session then writes it to `served/`,
where replay reads it again — so a single large blob or a broad pattern is an unbounded allocation
repeated at least twice, and `MAX_BUDGET` requests amplify it. Plan 3 bounded the *journal* and left
the *payload* unbounded, which is the same omission in a different quantity.

- `MAX_SERVED_BYTES` is per request, and is derived from what a reviewer could actually have
  consumed rather than chosen for roundness: a payload no agent can read is not evidence of exposure,
  and at roughly four bytes per token a mebibyte already exceeds the context of the reviewers this
  program contemplates. `MAX_RUN_SERVED_BYTES = MAX_BUDGET * MAX_SERVED_BYTES` follows, and is the
  disk a single run can occupy.
- **`read` is pre-checked, not truncated:** `cat-file -s <commit>:<path>` yields the blob size before
  any content is read, so an oversized read never allocates.
- **`search` and `history` must be bounded during capture**, since their output size is unknown in
  advance. `run_git` gains an explicit output ceiling; exceeding it terminates the child and refuses.
  A cap that only checks after `communicate()` returns has already spent the memory it exists to
  protect.
- **The ceiling belongs to `run_git`, not to the served operations** (revision 20). Revision 18
  bounded the three requests an actor asks for and left unbounded every capture the broker performs
  on its own behalf — which is the larger surface, and the one an actor reaches without asking:
  - **`stderr`, on every call.** It is captured with `capture_output=True` alongside stdout, it is
    actor-influenced (§3.2.1 records `alternates` emitting a warning on ordinary commands), and
    §3.2's own classifier reads it. An unbounded diagnostic is an unbounded allocation.
  - **The `config --list --name-only -z` preflight**, which `_filter_driver_overrides` runs before
    *every* `run_git` call. Its size is the actor's to choose — `include.path` pulls in arbitrary
    files — so it is unbounded input on the path that executes most often, and it is spent before
    the request it precedes is even authorized.
  - **The §3.1 tree scan.** `ls-tree -r -z --name-only` over a whole tree is proportional to the
    repository, not to any request, and it too runs before a session is allowed to open.

  **They share the ceiling and must NOT share the disposition** (revision 21). Revision 20 said
  "each fails the same way", which put environment-dependent overflow into the journal and thereby
  rebuilt the defect revision 20 had just removed from `history`. What a refusal may be recorded as
  depends on whether the condition is **fixed by the pinned commit**:

  | Overflow | Determined by | Disposition |
  |---|---|---|
  | served stdout (`read`, `search`, `history`) | the pinned commit | a journaled `Denial` — replays identically |
  | `stderr`, on any call | mutable repository and runtime state | **fail the git invocation**; never journaled |
  | the `config --list` preflight | `.git/config`, which the actor may edit at any time | **fail the git invocation**; never journaled |
  | the §3.1 tree scan | the pinned commit, but runs before a run exists | **refuse to open the session** |

  Journaling an environment-dependent refusal is a fail-open with a delay: an entry served before
  `.git/config` grew would refuse at replay, the bytes would not match, and §5.3 would return
  `EXPOSURE_UNREPRODUCIBLE` — **refusing an honest review for a file the actor edited afterwards.**
  Failing the invocation instead reaches §6 as `unwired`, which is what a condition the environment
  controls is supposed to produce.

  In all four rows, exceeding the ceiling **refuses rather than truncates**. A truncated config
  listing silently under-blanks filter drivers, and a truncated tree scan silently declares an
  unscanned tree NFC; both are fail-opens dressed as robustness.
- The refusal is a `Denial` with its own reason, distinct from a policy denial, and it is
  **deterministic given the commit** — the same request refuses identically at replay, which is what
  keeps §5.2 sound. Under §5.1 it contributes no coverage, like every other refusal.

This is a change to what serving *does*, which is what §5.2's rule bumps `REPLAY_PROTOCOL_VERSION`
for; revision 17 bumped it on a weaker argument about guarantees, and revision 18 makes the bump
squarely the rule as written.

**Defined misses are answers.** An absent path, a pattern with no matches, and a path with no commits
are each served with an explicit marker, and each is distinguishable from its degenerate neighbour:
a missing file reads differently from a file that is genuinely empty at the commit — "never shipped"
versus "shipped as a stub". Anything else git reports raises and halts the run.

**The three misses are answers about three different things**, and only one of them is about a path.
A failed `read` establishes that the path is not at the commit. A search with no matches establishes
that a *pattern* did not appear — the path may exist and be full of other content. An empty `log`
establishes that the *query* returned no commits. §5.1 therefore admits only the read miss into the
served map. The other two are journaled, spend rounds, and must replay, but they cite nothing,
because the `Evidence` union has no pattern-bearing variant to cite them with.

**A malformed search pattern is a third case**: it is the requester's own input, carries no
repository fact, and is refused as retryable rather than treated as instrument failure.

**Every search carries the policy's prefixes as `:(top,literal,exclude)` pathspecs**, whether or not
the caller supplied a pathspec of its own. Search is the one operation that never names a path, so
denying a directory to `read` while `git grep` returns hits from inside it denies nothing.

**`literal` is load-bearing, not decoration — but not for the reason revisions 1–8 gave.**
`normalize_project_path` refuses `..`, absolute paths and NUL, and permits everything else — including
`*`, `?` and `[]`, which are ordinary characters in a filename and wildmatch syntax in a pathspec.
Revisions 1–8 asserted that a bare `:(exclude)private/[drafts]` would read `[drafts]` as a character
class, fail to match the literal directory, and *leak* denied material into search results.

**Measured against git 2.55, that is not what happens, in either direction.** Across four constructed
cases — a directory and a file whose names carry `[]`, each with an innocent sibling the glob matches,
including a `[!a]` class that cannot match its own literal spelling — the non-literal spelling **never
under-excluded**: git's pathspec matcher also tries a literal prefix match, so the denied path was
excluded under every spelling tested. What the non-literal spelling did instead was **over-exclude**:
`:(exclude)notes/a[b].md` also removed the innocent sibling `notes/ab.md`, which the policy never
denied and which `read` serves without objection.

So the hazard is the mirror image of the one previously claimed, and it is still disqualifying. The
exclusion set becomes a function of glob syntax rather than of the policy text, and the two operations
disagree: a file `read` will serve is a file `search` cannot see. No false citation results — §5.1
admits a search miss into no coverage at all — but "I searched for `X` across the corpus and found
nothing", which §5.1 names as a legitimate and often decisive finding, becomes false for reasons no
one can see from the policy. `literal` disables wildmatch; `top` anchors to the repository root so the
exclusion does not drift with the caller's pathspec.

The correction is recorded rather than quietly applied because the conclusion survived and the reason
did not, which is the harder case to notice: a paragraph whose recommendation is right and whose
mechanism is invented reads exactly like one that was checked.

The deeper requirement is that the two operations agree. `read` denial and `search` exclusion are
independent implementations of one policy, so §7 tests them **against each other** on the same inputs:
metacharacters, and component boundaries in both directions — `private` must deny `private/x` and must
not deny `privateer/x`, on both paths. A policy enforced by two mechanisms is a policy that can be half
enforced.

### 3.2.1 Canonical invocation — `grep` and `log` must be probed before they ship

A pinned commit fixes the repository's *content*. It does not fix how git *renders* that content, and
for `grep` it does not even fix what the caller's pattern *means*. `grep.patternType` selects basic,
extended, perl, or fixed matching from repository configuration, so the same pattern against the same
commit is a different query depending on a file the actor owns. Colour, path quoting, line-number
emission, and log formatting are all likewise config-derived. Replay comparing two hashes of
differently-rendered output would refuse an honest run.

`autonomy/git.py` states its probe set explicitly — `rev-parse`, `status --porcelain`, `log`,
`show <commit>:<path>`, `diff --raw`, `diff --name-status`, `grep` — under the stated discipline that
"only what was shown to execute is neutralized". `grep` is now in that set: 2a gave that module the
same treatment it gave the others before adding a subcommand to it:

- **`grep` was probed** for config keys that cause execution, in a scratch repository, under exactly
  the argv the broker uses. `--textconv` is off by default; the probe established whether anything
  reaches a driver anyway rather than assuming it does not.
- **`log` was probed** for the keys that were not exercised by the existing `log` call site.
  `log.showSignature` spawns gpg, which the previous probe list did not mention.

Whatever executes is neutralised by `-c` in `_HARDENING`; whatever only *shapes output* is pinned in
the argv the broker builds, so that determinism does not depend on a config file at all:

| Op | Pinned |
|---|---|
| `grep` | pattern type passed explicitly, never inherited; `--no-color`; `--no-column`; `-n`; `-z` (which makes `core.quotePath` inert — pinning the config key as well was measured to be unnecessary, so it is not passed); `-a`; `--no-recurse-submodules` |
| `log` | explicit `--pretty=format:` with `%H`/`%aI`; `--no-decorate`; `--no-notes`; `--no-abbrev-commit`; `--no-follow`; `log.showSignature=false` |

**`-c` hardening does not reach every actor-owned channel, and this table's first nine revisions
assumed it did.** Two channels sit outside `.git/config` entirely and were found only by a
whole-branch review, after all four per-task reviews passed:

- **The attribute stack.** An *untracked* `.gitattributes`, or `$GIT_DIR/info/attributes`, carrying
  `* binary` turns every grep hit into `Binary file <commit>:<path> matches` at exit 0 — a served
  payload with no line numbers and no content, reported as success. There is no config key to pin
  and `--attr-source` replaces only the tracked layer. `-a` neutralizes it, at the cost of raw bytes
  for genuinely binary blobs. `-I` is not an alternative: binary-ness would still be
  attribute-derived, which is to say actor-controlled.
- **`.git/objects/info/alternates`.** An unresolvable path there makes git prepend
  `error: unable to normalize alternate object path: …` to stderr on an otherwise ordinary command.
  Any classifier comparing the *whole* stderr buffer then fails to recognize a defined miss and
  halts the run — so a hostile repository can guarantee the auditor never records an absent path,
  which §5.1 calls frequently the decisive finding. Classify against the last line, not the buffer.

The rule that produced §3.2.1 — *only what was shown to execute is neutralized* — is sound, but its
scope was the set of channels someone thought to probe. `log.follow` was missed the same way: it
changes served history whenever exactly one pathspec is given, which is any policy with no deny
prefixes.
| `cat-file blob <commit>:<path>` | nothing further — a blob read; a new subcommand to `git.py`, so probed under §3.2.1's rule before it ships |
| all three | `LC_ALL=C`, `LANG=C`, `GIT_SHALLOW_FILE=/dev/null`, `GIT_NO_LAZY_FETCH=1` in the child environment |

The last two are pinned for **all three** ops, not for `history` alone. §3.2 argues them from history
because that is where a shallow boundary bites, but a partial clone withholds *blobs* as readily as
trees — so `cat-file blob` and `grep` reach a promisor remote by the identical mechanism. A pin
scoped to the op that motivated it would be this design's recurring defect in environment-variable
form: **the guarantee stated on the axis where it was discovered rather than the axis where it
holds.**

**What was probed, and what actually executes.** Against git 2.55.0 in a scratch
repository, under exactly the argv the broker builds:

| keys | op | verdict |
|---|---|---|
| `grep.patternType=fixed` | `grep` | **INERT** |
| `grep.extendedRegexp=true` | `grep` | **INERT** |
| `grep.lineNumber=false` | `grep` | **INERT** |
| `grep.fullName=true` | `grep` | **INERT** |
| `grep.column=true` | `grep` | **RENDERS** |
| `grep.threads=1` | `grep` | **INERT** |
| `color.grep=always` | `grep` | **RENDERS** |
| `color.ui=always` | `grep` | **RENDERS** |
| `core.quotePath=true` | `grep` | **INERT** |
| `diff.probe.textconv=./spawn.sh` | `grep` | **INERT** |
| `core.pager=./spawn.sh` | `grep` | **INERT** |
| `pager.grep=./spawn.sh` | `grep` | **INERT** |
| `log.date=rfc` | `log` | **INERT** |
| `log.decorate=full` | `log` | **INERT** |
| `log.abbrevCommit=true` | `log` | **INERT** |
| `log.mailmap=true` | `log` | **INERT** |
| `format.pretty=oneline` | `log` | **INERT** |
| `log.showSignature=true` | `log` | **RENDERS** |
| `gpg.program=./spawn.sh` | `log` | **INERT** |
| `log.showSignature=true` + `gpg.program=./spawn.sh` | `log` | **EXECUTES** |
| `core.pager=./spawn.sh` | `log` | **INERT** |

The `log.showSignature=true` row is not the cosmetic kind of `RENDERS` that
`grep.column=true` or `color.ui=always` are. Against the crafted signed commit, git
verifies it with the default `gpg` on `PATH`, and that program's complaint lands in the
same stdout the probe compares:

```
gpg: no valid OpenPGP data found.
gpg: the signature could not be verified.
Please remember that the signature file (.sig or .asc)
should be the first file given on the command line.
```

That is why the row reads `RENDERS` at all — it executes something the probe's marker
cannot name, not something that changes output harmlessly — and it is why the pinning
table above carries `log.showSignature=false` rather than a blanked `gpg.program=`.

Keys that EXECUTE are neutralized by `-c` in `_HARDENING`. Keys that only RENDER are
pinned in argv, or by the environment where argv cannot reach them. Keys recorded
INERT are left alone, per this module's standing rule: blanking them would assert a
defense against behaviour this code has been shown not to have.

**Argv is not the whole invocation; the environment is part of it.** Left unpinned, `run_git` would let
git inherit the supervisor's locale, and a POSIX class such as `[[:alpha:]]` matches a different
character set under `C` than under a UTF-8 locale. Two honest replays of the same pattern against the
same commit would then disagree, and §5.3 refuses on disagreement. Pinning `LC_ALL` and `LANG` is what
makes "deterministic given the commit" true of a regex engine rather than only of a file.

The same pin does a second job the broker specifically needs: **git's diagnostic text is localized, and
§3.2 classifies defined misses by reading it.** Under a translated locale the miss messages would not
match, and the classifier would fall through to "anything else raises" — turning an ordinary absent
path into a halted run. Miss classification is only sound in a pinned locale.

`TZ` is deliberately not pinned: `%aI` carries its own offset, so the rendered log does not depend on
the reader's zone. Pinning it would be defending against behaviour the format has been chosen not to
have, which is the discipline `git.py` already states for config keys.

Config-derived rendering is the reason revision 1's determinism claim ("determinism comes free from
the pin") was too strong. It comes free from the pin *plus* a canonical invocation.

### 3.3 Journal

Append-only, one line per event, and the events are **discriminated** rather than uniform:

```jsonc
{"event": "inline",  "target": "...", "sha256": "...", "lines": 120}
{"event": "request", "op": "read", "target": "...", "pathspec": null,
 "commit": "...", "sha256": "...", "outcome": "served"}
//  outcome is `Outcome`: served | miss-absent | miss-no-match | miss-no-commits | refused
```

**`outcome` is the serving vocabulary, not a coarser one.** Revisions 1–11 wrote it here as
`served | miss | denied | invalid`, which is a fourth spelling of a distinction the shipped
`serve.Outcome` already makes — and it collapses the three defined misses, which §5.1 must tell apart
because only a *read* miss proves a path absent. One concept with two vocabularies is how the two come
to disagree; the journal records what `serve` returned.

Revision 2 counted raw lines to derive spend, which cannot express the budget it claimed to enforce:
inline seeds are lines but not requests, so seeding charged the reviewer for evidence it never asked
for, and a denial is a request that produced no served response. `requests_used` counts `request`
events; `inline` events are the supervisor's own seeding and cost nothing.

**An exhausted budget writes no event at all**, which §6 states as "spends nothing further" and which
reads there like a courtesy to the requester. It is not. `requests_used` is *derived* by counting these
events and §4.1 validates `requests_used <= budget`, so journaling the requests that arrive after
exhaustion would make the run's own seal reject its own record — and under §6 that means no record at
all. An actor that simply kept asking would silently convert its run to `UNWIRED`, which is a
supervisor-side failure triggered by ordinary actor misbehaviour. The refusal is returned, the round
is not spent, and nothing is appended.

It lives **outside the project tree**, for the reason `RunBaseline` does: a log inside the tree the
actor can write is not a record of what the actor was shown.

It cannot live in the run record, because that record deliberately has no in-flight shape — "a
supervisor that dies mid-run leaves no record, so its branch reads as unattested rather than clean".

Its path is **resolved from `RunBaseline`, never from argv**, and is put through
`reject_baseline_inside_project`. A journal a caller can name is a journal a caller can substitute.

Per the threat model: a same-uid actor can still append to it. What that buys is bounded — a forged
entry must name a path that really exists at the pinned commit, so it cannot manufacture a file, and
it leaves the forger's own fingerprints in an artifact the supervisor reads. It is not a proof of
exposure, and this design does not claim it is one.

### 3.4 Session

The session owns the round counter and the journal. **Every request that reaches it spends a round,
including denials and invalid patterns.** Free denials make probing the deny policy unlimited, and a
spent round is also what makes two runs comparable.

State that bounds a requester cannot live in the requester. A budget constant beside a stateless
serve function documents a budget without imposing one.

The session seeds the journal with inputs the opening prompt already supplied, marked `inline` and
audited by hash rather than against the surface policy. Without seeding, an instrument that
legitimately lives inside a denied prefix can never be accounted for at all. §4.3 fixes where those
inline inputs are *declared*, which revision 1 left open.

### 3.4.1 The cross-process contract

A reviewer runs as its own process and reaches the broker through the CLI, so the session is
cross-process and needs a contract rather than an object.

- **Handle.** `--session <run-id>`. It names a baseline, not a file. Journal path, budget, evidence
  commit, surface policy, instrument identity, and the inline manifest are all read from `RunBaseline`.
  **None of them is settable on the command line.** A caller cannot lower a budget it did not set,
  raise one it did, weaken the deny policy, or point the session at a different journal.
- **Handle validation, before it is ever joined to a path.** The handle is actor-supplied and becomes a
  path component in `run_dir`, so `--session ../../other-project/<slug>` is the obvious first attack. It
  is parsed as a *generated run id* — the same constructive check `AutonomousRunRecord._validate_identity`
  performs, rebuilding `<date>-<agent>-<short-id>` and comparing — and rejected before any join. Then,
  after loading, **the baseline's own `run_id` must equal the handle**. Validating the string and never
  checking what it opened would leave a directory that merely looks like a run id resolving to another
  run's baseline, which is the same class of defect as revision 4's unscoped project key: a name checked
  for shape and never for what it refers to.
- **Open.** `science autonomy start --broker-spec` creates the journal exclusively and writes its
  `inline` events, in the same call that writes the baseline, for the same reason `write_baseline`
  does: reusing a journal path discards the exposure record of whatever run already owns it.

  **There is no separate `evidence open` command.** Revisions 1–11 gave journal creation to one, and
  the argument against it is §3.4.2's own, applied consistently: a file is a legitimate trust channel
  at `start` *specifically because there is no actor yet*. Creating the journal and seeding it from the
  manifest are that same declaration, so performing them in a later command surrenders the only
  property that made them trustworthy — and offers an actor holding the handle a command that creates
  supervisor-owned state. It also sharpens §6 rather than weakening it: a brokered baseline beside a
  missing journal is then unambiguously interference, where a two-step open leaves it
  indistinguishable from a supervisor that omitted step two — a distinction §6 cannot afford to blur,
  since it destroys the whole record either way.

  **Not through `findings/paths.py`.** Revisions 1–6 named those primitives, and they are the wrong
  ones: every function there anchors to a project root — `open_dir_inside(project_root, …)`,
  `resolve_inside(project_root, …)` — and guarantees the result is *inside* it. The journal is
  deliberately outside the project tree (§3.3), so the guarantee those primitives exist to provide is
  the negation of the one this path needs. The applicable precedent is `autonomy/baseline.py`:
  exclusive `open("x")` plus `reject_baseline_inside_project`, which is containment in the direction
  that is actually wanted. The same pairing covers the `served/` directory (§3.5). Citing a mechanism
  by resemblance to its purpose rather than by what it guarantees is how the wrong one gets adopted.
- **Append.** One line, `O_APPEND`, under a lock file held for the duration of the serve, so
  concurrent reviewers in one run cannot interleave a partial line. Appends never rewrite.
- **Spend.** `requests_used` is **derived by counting `request` events**, not stored as mutable state.
  There is no counter to reset. Truncating the journal to buy rounds destroys the entries that make
  the truncator's own citations correspond, so the move is self-defeating rather than merely detected.
- **Seal.** `finish_run` reads the journal and copies it into the run record as `EvidenceExposure`.
  After sealing, the record is self-sufficient (§4.1): re-checking needs the record and a repository.
  The journal is retained as the supervisor's own copy of what it served, not as an input anything
  later depends on.

  **The seal does not replay.** Revisions 1–8 said it did, contradicting §6 — which enumerates a
  *missing or unreadable* journal as the only condition under which a seal fails — and contradicting
  §5.2, which places replay at review-append time. A replaying seal would refuse a forged-but-readable
  journal by writing no record at all, so a run would vanish for a reason §6's table does not list; and
  it would strip §5.3's `violated`/`EXPOSURE_UNREPRODUCIBLE` row of nearly all its reach, since after
  sealing every `sha256` replay compares against is one this toolkit wrote itself. The forgeable-journal
  argument of §5.2 is not answered by replaying at seal time: a forged hash copied into the exposure is
  caught when the exposure is replayed against the pinned commit, which is exactly where §5.2 puts it.
  Sealing is a copy; checking is §5's.

`Session` is also usable in-process, without the CLI, so 2b can hold sessions in the supervisor where
its dispatch shape allows. That mode has an authentic journal, since the actor never touches it. The
CLI mode does not, per the threat model — it is an audit aid against confabulation, not proof against
forgery.

### 3.4.2 The control plane must be locatable from a run id

A handle that names a baseline requires that a run id determine where its baseline is. Today it does
not: `science autonomy start --baseline-out` is `required=True` and takes an arbitrary path, chosen
by whatever supervisor invoked it. `--session <run-id>` would have had nothing to resolve against.

`autonomy/control_plane.py` supplies the missing functions:

```python
def control_plane_root(project_root: Path) -> Path       # $SCIENCE_CONTROL_PLANE, else the XDG state dir
def project_key(project_root: Path) -> str               # sha256(resolved root)[:16] — digest ONLY
def run_slug(handle: str) -> str                          # bare <date>-<agent>-<short-id>, either handle spelling
def run_dir(project_root: Path, handle: str) -> Path      # <root>/<project-key>/<run-slug>/
def project_metadata_path(project_root: Path) -> Path     # <root>/<project-key>/project.json
#   project.json  {"name": ..., "root": ...}   ← the human label, as metadata
#   <run-slug>/baseline.json, journal.jsonl, served/   ← served bytes, §3.5
```

**The key is project-scoped, and a run id alone is not a project identity.** A run id is
`<date>-<agent>-<short-id>`; two projects running the same agent role on the same day with the same
disambiguator produce the same slug, and a fork inherits its parent's `science.yaml` name outright. A
single global root would let one project's session resolve another's baseline — and between a fork and
its parent, which share a base commit, the replay would even succeed.

**The digest is the whole directory name; the project's name is metadata inside it.** Revision 4 put
`<name>-<digest>` in the path for legibility. `ProjectConfig.name` is an unconstrained `str` on a model
with `extra="allow"`, so a name containing `/` or `..`, or one long enough to blow a path limit, becomes
a control-plane path that escapes or fails to create — a filesystem-injection vector bought for a
cosmetic gain. The digest already carries the whole identity; legibility costs nothing in a
`project.json` beside the run directories, where a human can read it and a path resolver never does.

Two worktrees of one project get two control planes, which is correct: they are two trees at two
commits.

`--baseline-out` and a new `--broker-spec PATH` option on `science autonomy start` are **mutually
exclusive**. `--broker-spec` derives both control-plane paths and refuses an explicit baseline path;
without it, nothing changes for runs that do not broker evidence. No silent fallback: a brokered run
whose baseline was written somewhere else is refused rather than searched for.

**`--broker-spec` is where the session's mandatory inputs come from**, which revision 4 left with no
source at all: `EvidenceSession` requires a budget, a surface policy, an instrument identity, and an
inline manifest, none of them CLI-settable, behind a flag that carried no value. `autonomy start
--broker` could not have built its baseline.

```python
class EvidenceSessionSpec(_Frozen):     # the supervisor's declaration, read from JSON
    budget: int
    surface_policy: SurfacePolicy
    instrument: InstrumentIdentity
    inline_paths: tuple[Path, ...] = ()
```

`start` reads each `inline_paths` entry and computes its `sha256` and line count itself, producing the
`InlineInput` manifest. A supervisor that declared those numbers would be attesting to bytes it had not
necessarily read. It then creates `journal.jsonl` exclusively and writes one `inline` event per
manifest entry (§3.4.1), so a brokered run is fully opened by the single call that opens it.

**A file is a legitimate trust channel here specifically because there is no actor yet.** `start` is
what opens the run; until it returns, nothing has been dispatched and every input is the supervisor's
own. This is the one place in the design where a path may be supplied, and the reason it is safe is
temporal, not structural — which is why the same channel is not offered to `evidence serve` or to
`finish`, both of which run while an actor exists.

2b, holding sessions in-process, calls `start_run(..., evidence=EvidenceSessionSpec(...))` directly and
never touches JSON.

`science autonomy finish` needs the symmetric input, which revision 3 omitted: it takes
`--baseline PATH` as `required=True` today, so a brokered run had no way to say which run it was
closing. A new `--session <run-id>`, **mutually exclusive with `--baseline`**, resolves the baseline
through `run_dir` from the supervisor's own environment. That resolution is what makes §3.4.2's
containment argument true rather than asserted: the actor cannot influence which control plane
`finish` reads.

`control_plane_root(project_root)` is still put through `reject_baseline_inside_project`, judged
against that same `project_root`, so an environment variable cannot relocate the control plane into
the tree the actor writes.

An actor that sets `SCIENCE_CONTROL_PLANE` when it invokes the CLI redirects its own serving to a
baseline it forged. Consistent with the threat model, and self-limiting: `finish_run` resolves the
control plane from the *supervisor's* environment, finds the real journal without the redirected
run's entries, and every citation made against the forged session comes back `CITATION_UNSERVED`.
Redirection costs the actor its support rather than buying it any.

### 3.5 CLI

`science evidence serve` writes served bytes to a **file** and prints a receipt — path, sha256,
outcome — never the bytes themselves. Two independent reasons converge:

1. `BoundedSink` caps command stdout at 20–30K visible characters and refuses rather than truncating,
   so a large file would simply fail to emit.
2. It keeps served evidence out of a conversational parent's context, which is the constraint that
   makes 2b tractable at all.

**The path is derived from the session, not supplied.** Revisions 1–6 spelled it `--output PATH`, an
actor-chosen destination, and that is wrong twice over.

It contradicts the shipped write gate. `path_gate.evaluate` permits exactly one in-tree write at
`report-only` — the supervisor-supplied report path — and denies everything else by tier, before any
field allowlist is consulted. A reviewer serving ten files into the working tree would collect ten
denials, and the run would fail the gate for doing precisely what this design tells it to do. A
brokered reviewer that cannot run at `report-only` is a brokered reviewer with no tier to run at,
since `belief-neutral` is strictly wider and the whole point is to read, not to write belief.

It also reintroduces the hazard §3.3 already refused for the journal: a destination a caller can name
is a destination a caller can point somewhere else — over the report, over another run's artifacts,
or through a symlink out of the tree.

So served bytes go where the run's other machinery already lives, under `run_dir` (§3.4.2), at a name
derived from the request rather than chosen:

```
<control-plane>/<project-key>/<run-slug>/
    baseline.json      supervisor-only, exclusive-create
    journal.jsonl      actor appends, append-only
    served/<sha256>    actor writes; content-addressed, so a name cannot be chosen
```

Nothing in the project tree is written, so the tier's write surface is untouched and no gate change
is owed. The receipt prints the path; the reviewer reads it back.

**This is the one place an actor writes inside the control plane, and it is safe because nothing
trusts it.** `served/` is not an input to anything: replay re-serves every entry from the pinned
commit (§5.2), correspondence reads `exposure.inline` and the served map it rebuilds, and `finish_run`
never opens the directory. An actor that rewrites its own served files changes what it can read and
nothing about what it can prove — the same self-defeating shape as truncating the journal. The
supervisor-owned artifacts keep their existing disciplines: `baseline.json` is exclusive-create and
never rewritten, the journal is `O_APPEND` under a lock.

Content addressing is what removes the name from the actor's control: `served/<sha256>` of the served
bytes cannot be aimed, and two requests that produce identical bytes coincide harmlessly. The
directory is created under the same containment check as the journal, so a relocated
`SCIENCE_CONTROL_PLANE` cannot land it in the project tree.

**Every operation on the journal and on `served/` is anchored to a descriptor; none re-resolves a
pathname.** This is a consequence of the table above rather than a separate rule, and it is stated
here because it is the easiest thing in this design to implement almost-correctly. Note the scope:
the rule as stated covers the two artifacts the *actor* can reach. `baseline.json` is discussed
separately below. `served/` is actor-writable, and a
directory an actor can write is a directory whose *entries are actor-controlled names* — including
`journal.jsonl` beside it. A containment check on a pathname, followed by an `open()` of that same
pathname, checks one object and opens another: between the two, `served`, `journal.jsonl`, or any
component of `run_dir` itself can become a symlink into the project tree, a hard link to a project
file (which `O_NOFOLLOW` does not see), or a FIFO (which blocks the reader forever). The consequence
is the same fail-open in each case — the run's own broker performs an in-tree write and the tier's
gate denies the run for it, or the exposure record silently reads as empty and the budget never
exhausts.

So the run directory is captured **once**, by walking its components with `O_NOFOLLOW`, and the lock,
the count, the append, and the `served/` write are all performed through that one descriptor. Two
checks are owed and they answer different questions: containment is lexical and asks whether the
supervisor pointed this run's record inside the project tree; the anchored walk is a filesystem
operation and asks whether we reached it without traversing something an actor planted. Neither
implies the other. The repository already has this discipline and its primitives — see
`findings/paths.py`; §3.4.1's objection to that module is to its *project-containment* helpers, not
to its descriptor-anchored ones.

**And the journal's own descriptor, not just its directory's.** A directory descriptor plus a
re-opened name is still two objects: `unlink` followed by an ordinary new file passes every check —
not a symlink, a regular file, one link — on both opens, because none of those is a claim about
*identity*. The count would be taken from one inode and the append made to another, which silently
un-spends a round and disables the budget the count enforces. The journal is opened once,
`O_RDWR | O_APPEND`, and read and appended through that descriptor for the life of the operation.

**Bounds are declared where they can be enforced, and the read bound is derived from them.** The
journal's maximum size is not a chosen constant: it is `(max budget + max inline inputs) × max entry
size`. `target` and `pathspec` have a character bound; digest fields have their exact hexadecimal
width, and the entry commit is either forty hexadecimal characters or the empty inline-journal
sentinel; the inline line count has an integer bound. The maximum entry size accounts for
the actual JSON encoding: one non-BMP Python character becomes a twelve-byte UTF-16 surrogate pair
under `json.dumps`'s default `ensure_ascii=True`, not one six-byte `\\uXXXX` escape. Tests construct
the maximally encoded request and inline events rather than merely restating the constants.

Choosing a read bound independently of what the model admits creates a run that can *write* a
journal it can never *read back* — the first over-long entry is accepted, and every later request and
the seal itself then fail on the oversized journal, which §6 turns into no record at all. Every line,
including supervisor-seeded inline events, is encoded and checked before the journal is created or
served bytes are delivered. Over-long requester input is refused before the lock and before the
spend; it is decided on the requester's own string, before any policy is consulted, so it is not an
oracle.

**What this rule does not yet cover: `baseline.json`.** It is read by `finish_run` and written by
`start_run` through pathnames, and `finish` runs while the actor may still exist. The exposure is
bounded rather than absent — §3.4.2's argument applies, a redirected or forged baseline costs the
actor its support rather than buying any, and `reject_baseline_inside_project` still governs where it
may live — but the honest statement is that the anchoring rule is enforced for the journal and
`served/` and not for the baseline. Recorded here rather than implied away; closing it is a change to
plan 1's shipped `autonomy/baseline.py` and belongs to whichever slice next touches that module.

Plan 4b's replay and correspondence work inherits this: anything that later reads the journal or
`served/` reads it the same way.

**The served file is written before the journal line, not after.** The journal is the record of what
the requester was *shown*, so an entry appended before delivery succeeded claims an exposure that may
not have happened: a failed write leaves the requester with no bytes and no receipt while the seal
copies an entry saying `served`, and replay — which re-serves from the commit and never consults
`served/` — reproduces that entry perfectly. The reviewer would then hold `FULL` coverage over a file
it never received, which is support for a citation it could only have invented. Writing first inverts
the failure: bytes on disk with no journal line are bytes nothing counts, so the round is not spent
and no coverage is granted. Both orderings can fail; only one fails closed.

Descriptor anchoring proves where the bytes were written; it does not by itself prove that the path
printed in the receipt still names them. Before appending the exposure, serving compares the opened
`served/` descriptor with the receipt pathname using inode identity. If an ancestor was renamed after
capture, that comparison fails, no receipt is returned and no journal line is appended. The already
written content-addressed bytes are then an unrecorded orphan, which grants no coverage. This is not
a defence against deliberate same-uid artifact forgery (excluded by the threat model); it prevents
the broker itself from knowingly recording delivery after its own pathname has gone stale.

**A refusal writes no file.** A policy denial, a malformed pattern and an exhausted budget all serve
zero bytes, and content addressing maps all of them onto the digest of the empty string — so every
refusal in every run would coincide on one `served/e3b0c442…`, and the receipt would name a real,
empty, readable file that is indistinguishable from a file that was genuinely served empty. The
receipt for a refusal carries the outcome and the policy's notice, and no path. A defined *miss* does
write one: its marker bytes are the served answer (§6), not an absence of one.

## 4. Model changes

### 4.1 Run record

```python
class ExposureEntry(_Frozen):
    op: Literal["read", "search", "history", "inline"]
    target: str
    pathspec: str | None = None
    commit: str
    sha256: str
    outcome: Outcome      # `inline` entries carry Outcome.SERVED; see below

class InstrumentIdentity(_Frozen):
    ref: str          # what defined the judgement procedure
    sha256: str
    prompt_hash: str

class EvidenceExposure(_Frozen):
    commit: str
    budget: int
    requests_used: int          # includes denials; they spend rounds
    instrument: InstrumentIdentity      # required — see below
    surface_policy: SurfacePolicy       # sealed: part of the query, so part of the replay
    inline: tuple[InlineInput, ...] = ()
    replay_protocol: int                # see §5.2
    entries: tuple[ExposureEntry, ...] = ()

# AutonomousRunRecord
    evidence: EvidenceExposure | None = None
```

Grouped into one optional field because it is all-or-nothing: a run either was brokered or was not,
and one group makes "brokered" a single checkable predicate rather than three fields that can
disagree.

**The exposure seals every input replay needs, so it is self-sufficient.** Revision 4 claimed sealed
runs survive a project move; they did not. `check_correspondence` still took the live `EvidenceSession`,
and the exposure carried neither the surface policy nor the inline manifest — so once the control-plane
key changed, the baseline orphaned, replay lost its policy and its manifest, and every agent review in
that run silently became `unwired`. Under §4.2.1 that means silently losing all its support: exactly
the back-door fail-open §6 exists to prevent, arriving through a directory rename.

Copying the policy, the manifest and the protocol version into the exposure at `finish` makes the run
record the complete record of what was replayable, which is what "sealed" should have meant in the
first place. Re-checking a run then needs the record and a repository, and nothing else. The claim it
buys is now true rather than asserted: **a project move orphans unsealed sessions only.**

`ExposureEntry` deliberately does **not** store which lines a search matched. Those are re-derived at
replay (§5.1); storing them would be storing the actor's account of its own exposure.

**It does store `outcome`, and the difference is that `outcome` is checked.** Revisions 1–11 dropped
it at the seal, on the reasoning above. That reasoning does not reach it: replay recomputes the
outcome and §5.2 compares, exactly as it already does for `sha256`, so the stored value is testimony
under audit rather than testimony taken on faith — and `sha256` was never objected to on those
grounds. What dropping it cost was concrete. A **refusal** must appear in `entries` (the validator
below counts them) and re-serves to an empty payload, so an exposure without `outcome` distinguishes
a denied path from a genuinely empty file only by re-serving it, and any consumer that classifies by
operation and payload maps the denied path to `FULL` with a line count of zero — which §5.1 reads as
"every line was in front of the reviewer", admitting a path-only citation and permitting `pointer`.
That is a fail-open onto exactly the material the surface policy withheld, reachable by requesting a
denied file and citing the refusal. Storing the outcome makes the refusal unmistakable in the record,
and lets a reader see what a run was refused without a repository to replay against.

**`Outcome` moves to `science_model.evidence_broker`.** It ships today in
`science_tool.evidence_broker.serve`, and `science_model` cannot import `science_tool` — so an
`ExposureEntry` field typed by it needs the enum on the model side. Moved, not duplicated: a second
enum with the same members is the two-vocabularies failure one paragraph up, and `SurfacePolicy` is
already in that module for the same reason. `serve.py` imports it from the new home.

`inline` entries carry `Outcome.SERVED`. They are not re-served (§5.2 checks them against
`exposure.inline`), and the alternative — an `Outcome` member meaning "not applicable" — would put a
value in the enum that `serve` can never return, which is how a vocabulary starts describing two
things again.

**Validators:**

- **`requests_used == len([e for e in entries if e.op != "inline"])`, then `requests_used <= budget`.**
  Revision 5 bounded the count by the budget and never tied it to the entries it is derived from, so a
  record carrying ten request entries and `requests_used=1` validated — a spend counter that could
  disagree with the log it counts. `AuditFindingRecord` already states the rule this violates: "Every
  derived value stored here is RECOMPUTED and checked on construction… A stored derived value nobody
  validates is a value that can lie." The budget bound is meaningful only once the count is honest.
- Every entry's `commit` equals `EvidenceExposure.commit` — a run that read two trees did not have one
  evidence surface.
- **`EvidenceExposure.commit == AutonomousRunRecord.base_commit`.** Revision 1 required only internal
  agreement, so an arbitrary or orphan commit replayed perfectly and the exposure was bound to no run
  at all. `base_commit` and not `head_commit`: `head` includes the actor's own writes, and an agent
  permitted to cite a file it wrote during the run is back to self-attestation by a longer route.
  `RunBaseline` already carries `base_commit`, so the session opens from the baseline alone.

**`RunBudget` is untouched.** Its two fields are agent-attested; `requests_used` is parent-derived.
Merging them would blur exactly the distinction that makes `RunBudget` misleading today — it looks
like a cap and is a self-report.

`InstrumentIdentity` closes a gap this toolkit currently has outright: `RunBaseline` binds run, agent,
model, branch, commit and toolkit revision, but not the *instrument*. A judgement scored against a
silently edited rubric is presently undetectable.

**It is required, not optional.** Revision 3 required it on `EvidenceSession` and left it optional on
`EvidenceExposure`, so it was mandatory to open a session and droppable at seal time — which is where
it needs to survive, since the exposure is what anyone later reads. `evidence` is all-or-nothing; a
brokered run missing the identity of the instrument that produced its judgements is not a partially
brokered run, it is a run whose central provenance term went missing between opening and sealing.
Optionality here would have recreated `RunBudget`'s problem: a field that looks binding and is not.

### 4.2 Review

```python
MAX_UNCERTAINTY_ENTRIES = MAX_EVIDENCE_ENTRIES

class Uncertainty(_Base):
    field: AuthoredProvenance
    what: AuthoredProvenance
    why: AuthoredProvenance

class ReviewAttestation(_Base):
    """Who is reviewing and WHEN, asserted by the caller that KNOWS — never by the
    reviewer. The exact counterpart of `IngestionProvenance` at `ingest_report`."""
    reviewer_kind: ReviewerKind
    reviewer_ref: AuthoredHashComponent
    lens: AuthoredHashComponent | None = None
    model: AuthoredProvenance | None = None
    run_ref: AuthoredHashComponent
    at: Instant
    # Same `_agent_provenance` invariant as `Review`: an agent requires lens and model.

class ReviewSubmission(_Base):
    """What a producer offers: its FINDINGS, and nothing about its own identity.
    Carries no correspondence field and no identity field — not fields a producer
    may leave blank, fields it cannot express."""
    outcome: ReviewOutcome
    note: AuthoredProvenance
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=MAX_EVIDENCE_ENTRIES)
    uncertainty: tuple[Uncertainty, ...] = Field(default=(), max_length=MAX_UNCERTAINTY_ENTRIES)

# Review — the STORED shape
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=MAX_EVIDENCE_ENTRIES)
    uncertainty: tuple[Uncertainty, ...] = Field(default=(), max_length=MAX_UNCERTAINTY_ENTRIES)
    correspondence: Correspondence | None = None   # from science_model.correspondence
```

`Correspondence` is not redeclared here: 4b shipped it at `science_model/correspondence.py` as a
plain `BaseModel` with `extra="forbid", frozen=True`, deliberately not `_Base`, so the leaf reaches
`science_model.audit` by no path (§7). 4c's import of it from `audit/record.py` is the edge that
closes the cycle the two subprocess rows guard. It therefore lacks `_Base`'s
`revalidate_instances="always"` — which changes nothing, but **not for the reason revision 34 first
gave.** That draft said `with_review` round-trips the appended review through
`model_dump(mode="python")` and so revalidates it from a dict. It does not: `with_review` dumps the
existing record and then *overwrites* the `reviews` key with `(*self.reviews, review)` — real
`Review` instances, not dicts. What actually forces revalidation is that `Review` inherits
`_Base`'s `revalidate_instances="always"`, so an appended instance is validated rather than trusted.

Measured, because a claim about revalidation is worth more than an argument about it: a
`Correspondence` built past its own validator with `model_construct(status="verified",
code="…")` is **refused** when a `Review` carrying it is constructed. The nested value is checked.
Recorded because the obvious "fix" — giving `Correspondence` the `_Base` config — is exactly the
mutation §7 forbids, and because the wrong reason would have survived review by predicting the right
outcome.

**Revision 34 settles four things revision 26 wrote as `...` or left unstated.**

1. **`at` is attested, not clocked.** `ingest_report` takes `observed_at` from
   `provenance.generated_at` rather than reading a clock, because when a thing happened is part of
   what the trusted caller attests. `ReviewAttestation.at` is the same field at the same boundary, so
   `append_review` needs no clock parameter and has no timestamp of its own to disagree with.
2. **`ReviewAttestation` carries the agent invariant itself.** Without it, an attestation missing
   `lens` reaches the cross-checks, compares `None` against a real instrument ref, and fails three
   steps later when `Review` is constructed — with a message about the stored record rather than
   about the argument that was wrong.
3. **`uncertainty` is bounded.** Revision 26 bounded `evidence` and said nothing about `uncertainty`,
   though both arrive on one submission from one untrusted producer; an unbounded tuple in a stored
   record is a defect however small the intended payload. `MAX_UNCERTAINTY_ENTRIES` is *defined as*
   `MAX_EVIDENCE_ENTRIES` — an honest name at each use, and one number.
4. **`Uncertainty.field` is `AuthoredProvenance`, not `AuthoredHashComponent`.** It enters no digest.
   Revision 34 first kept the hash-component type and explained in prose that the name was
   misleading; a type whose name has to be argued away at every reading is the wrong type. NUL has no
   demonstrated hazard on this field, and if one appears the field can be tightened then.

**The submission/record split is the fix for actor-supplied `verified`.** Revision 1 forbade storing
`violated` and stopped there, which left `verified` settable by any caller — a Pydantic invariant can
constrain a value's shape but can never establish its provenance. Making the submitted type structurally
incapable of carrying a correspondence is stronger than checking that it did not: there is no check to
forget. `AuditReport` versus `AuditFindingRecord` is the same split, for the same reason.

**Revision 18 applies that same argument to identity, which revisions 1–17 left the producer to
assert.** `reviewer_kind` sat on `ReviewSubmission` while §5.4 branched on it, so an agent could
label itself `human` or `deterministic`, skip correspondence entirely, and count as full support —
the whole of §5 bypassed by one string. The submission could also vary `reviewer_ref` or `lens` to
mint several distinct `review_id`s from a single run, turning one reviewer into a quorum, because
`review_id` hashes exactly those fields.

The fix is not to validate the claim but to remove the producer's ability to make it. Identity moves
to `ReviewAttestation`, supplied by the caller that actually knows — the same trust boundary
`IngestionProvenance` already establishes for `ingest_report`, and the thing the previously
unexplained `actor` parameter was gesturing at. §0's boundary 2 already required this of both
writers: "both recompute actor-supplied provenance at the boundary rather than accepting it." §5.4
simply had not applied its own rule to the field that selects whether §5 runs at all.

**And for an agent, the attestation is itself cross-checked against sealed state**, because a
trusted caller can still be wrong:

- `reviewer_ref` must equal the run record's `agent`, and `model` its `model`. Both are sealed
  fields on `AutonomousRunRecord` and neither is derivable from the submission.
- `lens` must equal `exposure.instrument.ref` **when the run record carries an exposure**. The
  instrument is what defined the judgement procedure and is sealed at §4.1; a review claiming a lens
  the run was not opened under is describing a different run.

Mismatch is an `IngestError`, not a weaker correspondence: this is not "could not check", it is a
record disagreeing with the run it names.

**The two cross-checks have different preconditions, and revision 19 stated them as one**
(revision 20). `agent` and `model` are fields of `AutonomousRunRecord` itself, so those comparisons
hold for every agent review. The instrument is a field of the *exposure*, which an unbrokered run
does not have — and §5.3 requires exactly that case to be stored as `unwired` / `NO_EXPOSURE`. As
written, the boundary demanded an instrument in the one situation defined by its absence.

Making the lens check conditional gives up nothing that was being protected. `lens` is attested, so a
producer cannot vary it in the first place; the check defends against a mistaken trusted caller. And
a review with no exposure is `unwired`, which §4.2.1 excludes from `confirmation_count` — so a wrong
lens on an unbrokered review cannot buy support, and cannot mint a countable second `review_id`
either. The check is dropped exactly where its subject does not exist and its absence costs nothing.

`Correspondence` mirrors `InstrumentResult`'s invariant — `unwired` requires a machine-readable code
— so both ways this toolkit says "could not run" have one shape.

**Revision 17 strengthens that to: `code` is required whenever `status != "verified"`.** Revisions
1–16 required it only under `unwired`, which was coherent while `violated` was refused at
`append_review` and never stored. It stops being coherent once §5's checker (plan 4b) ships ahead of
that boundary (plan 4c): `check_correspondence` returns a `violated` result to a caller, and without
this the §5.3 codes `EXPOSURE_UNREPRODUCIBLE` and `CITATION_UNSERVED` would be unrepresentable on the
value that carries them — recoverable only as prose in an error message. `verified` remains the one
status with nothing to explain.

**And that implication runs both ways: `verified` forbids a code.** This is deliberately stricter
than `InstrumentResult`, whose `ok()` constructor accepts one despite supplying the invariant this
type otherwise mirrors. Correspondence codes name the non-verified classifications in §5.3; a code
on `verified` is therefore stale or contradictory state, not information to preserve.

`evidence` is bounded by the existing `MAX_EVIDENCE_ENTRIES`.

**Invariants on the stored `Review`:**

1. `_agent_provenance` gains: an agent review **requires** `correspondence`. It may be `unwired`; it
   may not be absent. Absent reads as clean.
2. A stored `Review` may not hold `status="violated"`. Refusal happens at `append_review`, and making
   it a model invariant means every other write path inherits it instead of each gate remembering.

`review_id` hashes `(reviewer_kind, reviewer_ref, lens, run_ref, finding_id)`. None of the new fields
enter it, so existing record identities are unchanged.

**Compatibility.** Revision 1 claimed old records load fine. That was wrong for the case that matters:
invariant 1 rejects any stored agent review lacking `correspondence`, which is every agent review
written before this change. Verified against the repository — `with_review` has no production caller,
`findings/cli.py` exposes no review command, and no stored case anywhere carries `reviewer_kind` — so
**there are zero such records and no data migration is required.** The window in which that is true
closes when 2c ships a producer, which is the argument for landing 2a first (§0). A record written by the new
toolkit is still rejected by an older one, since `_Base` is `extra="forbid"`; runs pin
`toolkit_revision`, so this is contained, but the model change and its consumers must land together.

### 4.2.1 Eligibility

```python
# on Review
def counts_as_support(self) -> bool:
    """Whether THIS review counts as support, independent of the record holding it.

    An agent confirmation counts only when EVERYTHING it cited was mechanically
    checkable and was checked against what the agent was shown. `unwired` is not
    a weaker `verified`: a guard that cannot see must not report clean, and free
    support is what it would be. A vacuous `verified` -- a review that cited no
    path at all -- is not evidence of anything either. Prose belongs in `note`,
    which every review already has, and costs nothing there.
    """
    if self.outcome != "confirms":
        return False
    if self.reviewer_kind != "agent":
        return True
    return (
        self.correspondence is not None
        and self.correspondence.status == "verified"
        and bool(self.evidence)
        and all(e.type == "location" for e in self.evidence)
    )

# on AuditFindingRecord
def confirmation_count(self) -> int:
    """Distinct confirming reviews that COUNT AS SUPPORT."""
    return len({r.review_id for r in self.reviews if r.counts_as_support()})
```

**Revision 34 lifts the predicate onto `Review` because §5.4's validate check needs the same rule.**
Eligibility is a property of one review, and it was written as a filter clause inside a record-level
aggregate — readable while it had exactly one caller. The check added at §5.4 reports the reviews
this method *excludes*, so a second copy of the condition would be a second thing to update when
§5.3 gains a code or §4.2.1 gains a clause, with a silent disagreement between the count and the
report as the failure mode. One definition, two callers, and the check is spelled
`not r.counts_as_support()` rather than as a list of the codes it knows about — the same
predicate-over-roster rule §7 applies to the coverage algebra.

**Revision 38 guards the delegation at the aggregate as well as at the predicate.** Predicate-level
tests alone did not prove that `AuditFindingRecord.confirmation_count()` still called
`counts_as_support()`: restoring the former outcome-only filter left every one green. Record-level
negatives now cover an unwired confirmation, a vacuous verified confirmation, and a mixed-evidence
confirmation. All three count as zero, and all three fail together under the old aggregate.

Recording a review's weaker standing while still counting it as support is a distinction with no
consequence — revision 1's `unwired`-accepts rule preserved the exact fail-open the design exists to
close, and paid for it with an info notice. An unbrokered agent review is still stored, still
displayed, and still readable; it simply adds nothing to the count.

The alternative — refusing to store a cited-but-unverified agent review — was rejected because the
incentive runs backwards: a producer whose review is refused for citing paths gets it accepted by
deleting its citations.

**`!= "agent"`, not `== "human"`.** `ReviewerKind` is `Literal["human", "agent", "deterministic"]`,
and revision 2's spelling silently dropped every deterministic confirmation to zero support — a
regression introduced by this design, not a gap it inherited. The rule is that brokering is required
of the reviewer kind that can confabulate; the exclusion list is one entry long and is spelled that
way.

**`all`, not `any`.** `evidence` defaults to empty and `TextEvidence` bears no path, so an agent
review citing nothing — or citing only prose — corresponded trivially and, under revision 2, counted
in full. That is the cheapest possible fabrication: "I confirm this" with nothing attached, scoring
the same as a checked citation.

Revision 3's `any(location)` fixed the empty case and left the mixed one, which is worse than it
looks. Correspondence ignores `TextEvidence` entirely, so a review pairing one honest citation to a
README with three fabricated prose exhibits came back `verified` and counted in full — the single real
citation laundering everything beside it. A partially checked review is not a checked review, and
reporting it as one is precisely the failure this design exists to prevent.

So for a *counted* agent confirmation, evidence must be non-empty and **every** entry must be
`LocationEvidence`. Because `verified` means every location citation corresponded, "all entries are
locations" and "everything was checked" are the same statement, and the test needs no stored count.

`TextEvidence` on an agent review is not forbidden — it is simply uncounted, and `note` already exists
for prose at no cost. The incentive points the right way: a producer wanting its review to count moves
its prose to `note`, which is where prose was always supposed to go.

This keeps the vacuous case `verified` at §5.3 rather than reclassifying it. The check genuinely ran
and genuinely found no violation; what it did not do is establish support. Collapsing "no violation"
into "no support" would put the empty/unwired confusion back one level up, which §5.3 exists to
prevent.

Human and deterministic reviews are unaffected: neither is brokered, their `correspondence` is
`None`, and they count as they do today. The blast radius is one non-test consumer, the display column
at `findings/cli.py:317`; `PERMITTED_TRANSITIONS` does not gate on this count.

**This is eligibility, not a threshold** (§0, boundary 1). Spec 1 reserves the confirmation threshold
and promotion authority for Spec 3, and this section takes neither: it decides only whether a
particular agent confirmation is admissible as support, on the ground that testimony nobody could
check is not testimony. Spec 3 sets how many admissible confirmations are enough, and should inherit
this count rather than reopen what feeds it — the alternative is a threshold tuned against a
population that silently includes unverifiable members.

### 4.3 Baseline

```python
class InlineInput(_Frozen):
    target: str
    sha256: str
    lines: int

class SurfacePolicy(_Frozen):
    deny_prefixes: tuple[str, ...] = ()
    notice: str                        # what every denial tells the requester

class EvidenceSession(_Frozen):
    session_id: str                    # the run slug
    journal_path: Path
    commit: str                        # == RunBaseline.base_commit
    budget: int
    surface_policy: SurfacePolicy
    instrument: InstrumentIdentity
    inline: tuple[InlineInput, ...] = ()

# RunBaseline
    evidence: EvidenceSession | None = None
```

The concrete model bounds are part of this contract: `target` and `pathspec` admit at most 4096
Python characters; journal digests are exactly 64 lowercase hexadecimal characters; commits are 40
lowercase hexadecimal characters except for the empty pre-seal inline sentinel; inline line counts
fit a non-negative signed 64-bit integer; budgets and inline manifests each admit at most 100 items.
Those are the inputs to §3.5's encoded-byte ceiling, not merely validation conveniences.

**This is the fix for inline evidence bypassing replay.** Revision 1 had inline entries contributing
trusted correspondence targets on the strength of a hash in the journal — the same journal it argued
was forgeable, which is why every other entry is replayed. Declaring them in the baseline moves them
into the control plane: the supervisor writes the manifest when it composes the prompt, exclusive-create
and outside the tree, and an inline entry corresponds only if its target is in that manifest *and* the
journal's `sha256` matches the manifest's.

`lines` is carried so a line or span citation into an inline input can be checked the same way as one
into a read file. Inline bytes are not in the tree, so a line count cannot be re-derived later.

**`InlineInput.target` is a normalized project-relative path, and `EvidenceSessionSpec.inline_paths`
are too.** Revisions 1–12 left the spelling open, and an implementation that stored the supervisor's
own absolute path would produce a manifest entry **no citation can name**: `LocationEvidence.path`
runs `normalize_project_path`, which refuses an absolute path outright, so an inline input would be
granted `FULL` coverage under §5.1 that no `Evidence` value could ever reach. The motivating case in
§3.4 is already in-tree — "an instrument that legitimately lives inside a denied prefix" — and that
is the whole point of seeding: the file *is* a project path, and inline seeding is how it is accounted
for despite the policy that denies it. A path outside the project can be *read* by `start`, but it
cannot be cited, so seeding one accomplishes nothing and is refused rather than silently manifested.
`start` therefore resolves each `inline_paths` entry against `project_root` to read the bytes, and
stores the normalized project-relative spelling as `target` — the same spelling every other entry
carries, which is what lets §5.1's "`FULL` supersedes `LINES`" compare an inline target against a read
one at all.

`surface_policy` is here for the reason given in §3.1: the deny prefixes are `:(exclude)` pathspecs on
every search, so they are part of the query, and a query whose text is not fixed does not replay.
Naming it `surface_policy` rather than reusing `policy_identity` is deliberate — that field is the
autonomy write-surface policy, a different thing about a different boundary, and one field standing
for two policies is how they end up enforced as one.

`journal_path` is containment-checked by `reject_baseline_inside_project`, like the baseline itself,
and under `--broker-spec` it is derived from `control_plane.run_dir()` rather than supplied at all.

## 5. Correspondence

```python
def check_correspondence(
    evidence: Sequence[Evidence], exposure: EvidenceExposure | None, *, repo: Path
) -> Correspondence
```

**`| None` is what lets 4b own the whole of §5.3** (revision 21). Its first row is
`unwired` / `NO_EXPOSURE`, and a signature requiring an exposure cannot produce the outcome defined by
there not being one — the same defect as revision 20's lens precondition, one slice over. The absent
case is a classification, so it belongs with the classifier; the alternative has `append_review`
constructing `Correspondence` values on one path and delegating on another, which is two producers
of one verdict.

**4b owns §5.3's *classification* column and nothing else.** "Stored?" is `append_review`'s behaviour
and "Counts as support?" is `confirmation_count`'s — both 4c. The table reads as one rule per row
because the three answers move together, but they are set in two different slices, and a 4b
implementer who reads the storage column as a requirement will build a boundary 4c then has to
unbuild.

The live session is gone from the signature: everything replay needs is sealed into `exposure`.

**It takes citations, not a `Review`** (revision 20). Revisions 1–19 passed a `review`, which made
the checker depend on a field the merged `Review` does not have — `evidence` arrives with §4.2's
changes, and those belong to plan 4c. A checker that cannot be written until its consumer's model
lands is a slice boundary that does not hold. Taking `Sequence[Evidence]` removes the dependency
outright rather than resequencing to work around it: plan 4b then touches **no audit-record model at
all**, and §5.4 passes `submission.evidence` at the boundary. It is also the honest signature — the
checker never reads a reviewer's identity, outcome, or note, and a parameter it does not use is a
coupling it should not have.

**Modules (plan 4b).** `evidence_broker/hits.py` parses `git grep -n -z` output into hits and runs no
git of its own — pure bytes in, `(path, line)` out — so the NUL-record contract of §5.1 can be
certified against real `git grep` output without an exposure, a repository or a review in the
picture. That isolation is worth a module because revisions 1–9 stated the format wrongly in prose
and nothing caught it. `evidence_broker/correspondence.py` holds the served map and the check.
`serve.py` is untouched by this slice; §3.1's NFC rule lands in the session's open path.

**`science_model/correspondence.py` inherits nothing, and that is the point.** §4.2 spells the type
as `Correspondence(_Base)`, but `_Base` lives in `audit/subjects.py`, and importing *anything* from
`science_model.audit` runs `audit/__init__.py`, which eagerly imports `audit.record` — the module
that imports `Correspondence` back. So the leaf repeats its own
`ConfigDict(extra="forbid", frozen=True)` rather than sharing one. Factoring that back out is not a
cleanup; it is the cycle, entered from the edge revision 23's mutation row does not cover.

**A naming adjacency, so a reader does not conflate two things.** `validate/findings.py` already
defines `CorrespondenceQualifiers` — a spec-1 findings artifact pairing a task with an evidence
signature, unrelated to this section and never imported alongside it. They share a word and nothing
else; the new module says so in its docstring.

### 5.1 The served set — coverage, not paths

Revision 1 built a set of paths. That certified a whole file from a single grep hit: a match on line 1
would have approved a citation to line 900, and `LocationEvidence` carries exactly the `line` and `span`
fields that makes such a citation expressible. The served set is therefore a map from path to
**coverage**:

| Contributed by | Coverage | Meaning |
|---|---|---|
| `read`, `inline` | `FULL` + line count | every line `1..n` was in front of the reviewer |
| `search` hit | `LINES` + the matched line numbers | only the hit lines were shown |
| `history` | `PATH_ONLY` | the path's commits were shown; its contents were not |
| `read` miss | `ABSENT` | the path is not at the commit, and that was served as the answer |
| `search` miss, `history` miss | *nothing* | see below |
| **any refusal** — policy denial, malformed pattern | ***nothing*** | **the requester was shown nothing; see below** |

**Coverage is keyed on the replayed `Outcome`, never on whether the payload is empty.** Revisions
1–11 had no row for a refusal at all, and the row cannot be omitted as self-evident: a refused entry
*is* in the exposure — it spent a round, so `requests_used` counts it — and it re-serves to zero
bytes at a real path the requester named. A builder that reaches the coverage table by operation and
payload therefore files a denied `read` as `FULL` with a line count of zero, which this table's first
row defines as "every line was in front of the reviewer". A path-only citation to the withheld file
then corresponds, and `pointer` — permitted under `FULL` and nowhere else — comes with it. The
material a surface policy exists to withhold is the last material that may validate a citation, so
the rule is stated positively: `Outcome.REFUSED` contributes no entry to the served map, and an empty
payload is never itself evidence of coverage.

**Only a read miss proves a path is absent.** Revision 2 mapped all three defined misses onto
`ABSENT`, which asserted three different facts as one. A search that matched nothing establishes that
a pattern did not appear, not that any path is missing — the pattern may be wrong and the file may be
full of relevant content. An empty `log` establishes that a query returned no commits. Neither is
citable through the `Evidence` union at all, which has no pattern-bearing variant, so they contribute
nothing to the served map rather than contributing something false. They are still journaled, still
spend a round, and still must replay.

The cost is real and worth naming: "I searched for `X` across the corpus and found nothing" is a
legitimate and often decisive review finding that this design cannot mechanically check. Making it
checkable needs a `SearchEvidence` variant carrying the pattern and pathspec, which belongs with the
consumer that needs it (2c) rather than being speculatively added here.

`git grep -n -z <pattern> <commit>` prefixes every hit with `<commit>:<path>\0<line>\0`, so the
matched lines are recoverable from the served bytes — **NUL-separated, not colon-separated.**
Revisions 1–9 said `<commit>:<path>:<line>:` here while §3.2.1's own table pinned `-z`, which
changes the separator. A parser written to the colon spelling recovers no line numbers at all, so
every search-derived citation would be `CITATION_UNSERVED` and §5.3 would refuse an honest review.
The NUL form is what ships and what **plan 4b** parses — plan 3 was named here through revision 16
and shipped without touching it; a path is unambiguous under it, which is why `-z` is pinned in the
first place — which is a second reason replay is not optional, since the journal stores only a hash
of them. Where a path is both read and searched, `FULL` supersedes `LINES`.

**The pinned argv makes the record format tighter than "NUL-separated", in two ways a plausible
parser gets wrong.** `_GREP_ARGV` pins `-a` and `--no-column`, so every record is exactly
`<commit>:<path>` NUL `<line>` NUL `<matched content>` LF, and there is no `Binary file … matches`
variant to special-case — `-a` means even a binary file yields ordinary numbered hits.

- **Split each record on NUL with `maxsplit=2`; never split the whole payload on NUL.** Because `-a`
  serves binary content as text, matched content can itself contain NUL bytes. `maxsplit=2` makes
  them inert; a whole-payload split silently invents fields from them.
- **Remove the `<commit>:` prefix by exact string removal, not by splitting on `:`.** The commit is
  known to the parser, and a path may legitimately contain a colon.

**Records are parsed by a forward scan, not by splitting the payload on LF.** Matched content cannot
contain LF, because a matched line ends at one — but a **path can**, and git emits it raw.
MEASURED, git 2.55: a hit on a file named `a<LF>b.txt` serves
`<commit>:a` LF `b.txt` NUL `1` NUL `content` LF, so an LF split cuts the record in half. It fails
loudly rather than misparsing, since the leading fragment carries no NUL at all, but a parser that
raises on a legal repository is still wrong.

The repair is not a wider delimiter. Splitting on `LF + <commit>:` looks safe and is not: a filename
may contain that literal sequence, and the pinned commit is knowable to whoever writes the filename.
Parse forward instead, from a known start — the prefix, then the path up to the first NUL, the line
up to the second, and the content up to the next LF, which is the record's end. Every field boundary
is then found by scanning rather than inferred from a split, and no byte in any field can be mistaken
for a delimiter. `maxsplit=2` on a single record is the same discipline stated for one record; this
states it for the payload.

**Accumulate hits per path before constructing coverage.** A payload may carry many hits on one file,
and uniting a fresh one-element `Lines` per hit rebuilds the set on every merge — O(k²) for k hits.
`MAX_SERVED_BYTES` admits on the order of twenty thousand hits, so this is a real cost inside a
bound, not a theoretical one. Group first, construct once.

**Two definitions this section left implicit, which is where off-by-one defects live.** `line_count`
is the number of LF-terminated lines plus one if any bytes follow the final LF; an empty payload is
`line_count = 0`, so every line citation into an empty file fails rather than passing by vacuity. And
`ABSENT` is the strongest claim the table can express — it is what certifies "this file does not
exist at this commit" — which is why §3.1's NFC rule has to hold for it to mean anything at all.

**LF, and only LF — which puts read coverage and inline coverage on different counts.** The obvious
spelling of `line_count` is `len(payload.splitlines())`, and it is wrong: MEASURED,
`b"a\rb\n".splitlines()` is 2, because `bytes.splitlines()` splits on CR as well. `git grep -n`
numbers by LF, and `FULL` supersedes `LINES` on a path that was both read and searched, so a `FULL`
count in any other numbering is not commensurable with the `LINES` numbers sitting beside it in the
same map — a matched line number could exceed the line count of the same file.

`InlineInput.lines` is already computed the wrong way (`lifecycle.py`, at manifest time), and 4b
cannot recompute it: `exposure.inline` seals `target`, `sha256` and `lines`, and no payload. So
inline `FULL` carries the sealed count and read `FULL` carries the LF count, and on a CR-bearing file
the inline one is larger. The error is **permissive** — it admits a citation to a line the LF rule
says is not there — and it is stated here rather than silently inherited. Correcting it means
changing a sealed model, which is 4a's cell and not the checker's (§2.2); it is a follow-up, and the
one place where fixing the divergence and shipping 4b are separable.

**`Coverage` is a `science_tool`-local sum type, not a sealed model** — `Full(line_count)`,
`Lines(numbers)`, `PathOnly`, `Absent`. It is derived at check time from a replayed exposure and
never stored, so putting it in `science_model` beside the sealed types would advertise a durability
it does not have. `Correspondence`, which *is* returned across the boundary, ships in its **own
dependency-neutral module**, `science_model/correspondence.py`, importing pydantic and nothing else.

**One path can pick up two contributions, and "`FULL` supersedes `LINES`" covers one pair of ten.**
Stating only that pair leaves an implementer to invent the rest, and every plausible invention —
last-write-wins, first-write-wins, blanket union — is wrong on at least one row below, usually in the
permissive direction. Merging is therefore a single named function, **total over the four coverages**
and enumerated here rather than left as a rank to infer. Nothing bounds a run to one request per
path: the budget buys requests, not paths, so every self-pair is reachable too.

| Pair | Reachable via | Result |
|---|---|---|
| `FULL` + `FULL` | a path inline-seeded **and** read | `FULL(min)` — the commit is the audited artifact, so a line present only in the working-tree copy is refused |
| `FULL` + `LINES` | a path read and searched | `FULL` |
| `FULL` + `PATH_ONLY` | a path read and asked for history | `FULL` |
| `FULL` + `ABSENT` | a path inline-seeded, absent at the commit | `FULL` — it admits every citation `ABSENT` admits, since a bare path citation corresponds under any coverage |
| `LINES` + `LINES` | **one path searched twice, for different patterns** | `LINES(union)` — each search showed the reviewer its own hit lines, and both were shown |
| `LINES` + `PATH_ONLY` | a path searched and asked for history | `LINES` |
| `PATH_ONLY` + `PATH_ONLY` | history asked twice | `PATH_ONLY` — idempotent |
| `PATH_ONLY` + `ABSENT` | a history entry and a read miss | `ABSENT`; they admit exactly the same citations, and `ABSENT` carries the clearer `reason` |
| `ABSENT` + `ABSENT` | an absent path read twice | `ABSENT` — idempotent |
| `LINES` + `ABSENT` | — | **unreachable**: grep matched the path at commit C, so it exists at C |

**Two rows are doing real work; the rest restate a rank, and mistaking which is which is the whole
risk here.** `FULL(min)` resolves two honest counts of different bytes — a working-tree file and a
committed blob, both of which the reviewer saw — towards the artifact an auditor can re-derive, and
needs no story about which entry arrived first. `LINES(union)` is the one place a *union* is correct
rather than permissive, and it is exactly where a rank-based implementation silently discards
evidence: two searches expose disjoint line sets of one file, and replacing instead of uniting
refuses a citation to a line the reviewer demonstrably saw. A blanket union would then look like the
safe generalisation — and it is not, because unioning `FULL` counts takes the maximum, which is the
`FULL(min)` row inverted.

Revisions 17–22 put it in `evidence_broker.py` beside `Outcome`, which reads well and does not load:
`evidence_broker.py` imports `audit.subjects`, and `science_model/audit/__init__.py` eagerly imports
`audit.record`, so `import science_model.evidence_broker` already pulls in `audit.record` — verified
by probe. Having `audit.record` import `Correspondence` back from `evidence_broker` would close that
into a cycle through a partially initialised module. A leaf module both sides import is not a
compromise between the two homes; it is the only placement under which neither package depends on
the other.

**The cited set.** `line` and `span` are already mutually exclusive on `LocationEvidence`, so a
citation cites `{line}`, or every line from `span.start_line` to `span.end_line` inclusive, with
columns ignored. A `LocationEvidence` bearing no `line`, `span` or `pointer` is a bare path citation
and corresponds under any coverage present in the map, `ABSENT` included — "this file is not here" is
a path-only claim and is exactly the finding §5.1 ends by protecting.

A `LocationEvidence` corresponds iff:

- its path is in the served map, **and**
- under `FULL`, every cited line is `<= line_count`;
- under `LINES`, every cited line is a matched line;
- under `PATH_ONLY` or `ABSENT`, no line or span is cited at all; **and**
- `pointer` is absent under every coverage except `FULL`.

**The span check must be bounded, because a span is not.** `Span.end_line` is `Field(ge=1)` with no
upper bound, so `Span(start_line=1, end_line=10**18)` is constructible and evaluating it by iterating
`range(...)` inside `all(...)` does not return. It is reachable from authored review content on a
write path, and it hangs rather than raising — the one failure mode in this section that no timeout
or error message describes. Under `FULL`, compare `end_line <= line_count` directly: every line in
`[start, end]` is at most `end`, so the O(1) form is not an optimisation but the same predicate.

**`LINES` needs no such repair, and revision 32 corrects revision 31 for thinking it did.** A span is
*contiguous*, and `numbers` holds at most n elements, so among the first n+1 lines of any span at
least one is absent — the iteration short-circuits within `len(numbers) + 1` steps whatever the
span's declared length, and n is bounded by the payload cap. The obvious guard
(`end_line - start_line + 1 > len(numbers)` refuses immediately) is therefore a same-verdict
optimisation, not a termination guarantee. Keep it for the constant factor; do not describe it as
what makes `LINES` safe, and do not write a mutation row for it — see §7.

Only the unbounded comparison against a *count* can run away, because there the predicate is true for
every line until the last one. That asymmetry is the whole finding: `FULL` iterates until the span
exceeds the file, `LINES` iterates until the span leaves the hit set, and only the first of those can
be made arbitrarily long by an authored value.

A span cites every line it covers — **every line, not its endpoints**, and the difference is only
visible on a span whose *interior* is unserved. A span of lines 2–4 against hits `{2, 4}` does not
correspond, because line 3 was never shown; the obvious illustration, a ten-line span against a
one-line hit, is refused by endpoint-checking too and so demonstrates nothing. That is strict on
purpose: a reviewer wanting to cite a span should read the file. The line-count check
under `FULL` is free once the bytes are replayed, and it closes fabricated line numbers into files the
reviewer genuinely opened — a case revision 1 did not consider at all.

**`pointer` is gated by coverage even though its value is never checked.** It is a non-positional
locator — a heading, a symbol name — whose resolution depends on a document format the broker does not
parse. Revision 3 forbade `line` and `span` under the weaker coverages and said nothing about
`pointer`, which left the whole hole open in a different shape: an agent could run `history` on a path,
never see one byte of it, cite `pointer="class FooBar"`, and earn support for a symbol it inferred
from the filename.

The rule that follows from not parsing pointers is that a pointer is only meaningful when the entire
file was in front of the reviewer, since anything less means the pointed-at region may be exactly the
part not served. So `pointer` is permitted under `FULL` and nowhere else — including under `LINES`,
where a pointer may well name something outside the matched lines. `TextEvidence` bears no path and
contributes nothing.

Two cases must count as served, or the check punishes correct behaviour: a **search hit**, and a
**read miss** — a path absent at the commit is frequently the decisive finding, and any rubric worth
using asks for absence to be recorded with the same care as presence.

### 5.2 The replay

Every non-inline entry is re-served at the pinned commit and must reproduce **both its recorded
`sha256` and its recorded `outcome`**. When the broker writes the journal it is trustworthy by
construction, but a record read back off disk was written by whatever wrote that file, and a `sha256`
field is as forgeable as the rest of the JSON. Determinism comes from the pin **and** the canonical
invocation in §3.2.1.

Checking the outcome is not redundant beside the hash. The refusals share one hash — the digest of
the empty payload — so a forged entry that relabels a refusal as a served read of an empty file
reproduces its `sha256` exactly, and only the outcome comparison catches it. This is also where a
policy *widened* between serving and replay is caught: the exposure seals the policy (§4.1), so a
request refused when the reviewer worked must be refused again, and an entry that now serves bytes
where the record says `refused` is `EXPOSURE_UNREPRODUCIBLE`. §5.1's over-exclusion case covers the
narrowing direction; this covers the other one.

**Re-serving reconstructs the request from the entry, and adds no normalisation.** An
`ExposureEntry` becomes `EvidenceRequest(op, target=entry.target, pathspec=entry.pathspec)` handed to
`serve` with `exposure.commit` and `exposure.surface_policy`. `session.py` journals `served.target`
and `served.pathspec`, and what those hold **differs by operation**: for `read` and `history` the
target is `auth.path`, already normalised; for `search` it is the raw pattern, which goes through
`_judge_pattern` and no normaliser at all, while the *pathspec* beside it is the normalised one.
Either way re-serving is stable — `normalize_project_path` is idempotent and `_judge_pattern` is a
pure function of the string — so passing the journalled values back through `authorize` returns them
unchanged. A checker that "helpfully" pre-normalised, or that reached for a raw requester spelling
the journal never stored, would be authorizing one path and comparing another; a checker that
normalised a *search* target would be rewriting a regex.

**A replay-time git fault is `unwired` in exactly two cases, decided before any entry is replayed.**
The repository does not hold `exposure.commit` — asked through the **existing**
`serve.verify_commit`, not a second probe — and `history_traversal_error(repo, exposure.commit)` is
non-`None`. Both are properties of the *environment*, decidable once and cheaply, and both yield
`EXPOSURE_UNREACHABLE`; §5.3 fixes their position in the executable order. Everything after that
point — a `ServeError` on unclassifiable stderr, a `GitError` — **propagates**, which is §6's
standing rule for the same failure at serving time ("anything else from git raises") applied to the
same code on the other side of the seam. So the checker holds exactly one `except ServeError`, around
`verify_commit`, and a second one anywhere is the wrapping this section rejects arriving by
increment.

The alternative is to wrap the whole replay and read every fault as `unwired`. It is attractive
because `check_correspondence` is called from a write path, and because §5.3's own prose says a
journal that cannot be reached could not be checked. It is nevertheless the shape of the bug revision
4 closed: a project rename turned every review in a run silently `unwired`, which under §4.2.1 zeroes
their support, and this design treated that as a fail-open rather than as graceful degradation. A
systematic breakage that reports "could not check" for everything, with an info-severity validate
notice as its only signal, is that failure again with a wider blast radius. The known cost is
concrete and accepted: appending a review against a `--filter=blob:none` clone raises rather than
storing `unwired`, since §2.2 records that the blob case is not pre-empted at open either.

What no fault may ever produce is `violated`. That is the invariant both readings preserve and the
one a third reading — catching exceptions and calling them mismatches — would break.

Inline entries are not in the tree and cannot be re-served; they are checked against
**`exposure.inline`** — the sealed copy of the manifest, not the baseline's. The baseline is where the
manifest is *declared* (§4.3) and the exposure is where it is *sealed* (§4.1); replay reads the sealed
copy, and reaches for no control-plane file at all.

**Compared as multisets, in both directions.** Revision 31: a lookup table keyed on
`(target, sha256)` answers "does every entry have a manifest item" and never the converse, so a
manifest item with no entry — the same record disagreeing with itself, read the other way — passed
unnoticed; and it collapses duplicates, so two entries against one item, or one against two, are
indistinguishable from a clean pairing. The check is therefore multiset equality between
`[(e.target, e.sha256) for e in entries if e.op == "inline"]` and
`[(i.target, i.sha256) for i in exposure.inline]`.

Separately, a manifest in which one `(target, sha256)` key carries two different `lines` values is
refused outright. Identical duplicate inputs are legitimate and remain reproducible — seeding the
same file twice is wasteful, not dishonest. Two different line counts for one content hash are a
contradiction, and coverage derived from whichever item a lookup happened to return would be a
verdict that depends on iteration order.

**A disagreement there is `EXPOSURE_UNREPRODUCIBLE`, not missing coverage.** `entries` and
`exposure.inline` are seeded from one `session.inline` — `create_journal` writes the manifest into
the journal and `finish_run` seals the same tuple — so they agree by construction, and an entry whose
target is absent from the manifest, or whose `sha256` differs from it, is a record disagreeing with
itself. Treating it as merely uncovered would make editing an inline entry's target a free way to
land a fabricated citation nowhere: no coverage, no cost, and the review still reaches the citation
check with everything else intact.

**No cross-exposure memoisation.** Revisions 1–17 memoised on `(commit, op, target, pathspec)` within
an ingestion run, on the reasoning that reviews of sibling documents read many of the same files. That
key is unsound: the surface policy is sealed per exposure (§4.1) and it changes both authorization and
the exclusion pathspecs handed to `grep` and `log`, so one ingestion run spanning two runs with
different deny policies would serve a cached payload from the wrong policy and classify an honest
exposure as `EXPOSURE_UNREPRODUCIBLE`.

Adding the policy to the key would be sound, but nothing here has been measured — replay is bounded by
`MAX_BUDGET` requests per exposure, and a cache introduced ahead of a measurement is a correctness
risk bought with a guess. Memoisation is therefore **within a single exposure only**, where the sealed
policy is by construction one value. If cross-exposure replay is ever shown to be the bottleneck, the
key includes the policy identity, and that is a change made against a number.

**Replay performs no NFC check of its own.** §3.1's rule is enforced at session open against the
pinned commit, and a commit's tree is immutable, so an exposure that exists at all was sealed against
a tree that satisfied it. Re-checking here would be a second guard for a property already
established — and a second place to get it wrong.

**Replay is bound to a `REPLAY_PROTOCOL_VERSION`, not to `toolkit_revision`.** Reproducing a hash
depends on the serving implementation — the defined-miss markers, the canonical argv of §3.2.1, the
hit-line parsing. A later toolkit that changes any of them would recompute different bytes and classify
an honest old exposure as `EXPOSURE_UNREPRODUCIBLE`, which **refuses**. A guard whose failure mode is
"refuse honest historical work after an upgrade" is worse than the gap it closes.

Comparing `toolkit_revision` instead would be safe in direction — mismatch yields `unwired`, which
refuses nothing — but every toolkit bump would zero the support of every prior run, including the
overwhelming majority whose serving behaviour did not change. A signal that fires on every upgrade is a
signal people learn to ignore.

So the protocol carries its own integer, sealed into the exposure and bumped **only** when serving or
parsing changes. A mismatch is `unwired` / `REPLAY_PROTOCOL_MISMATCH`: could-not-check, not
checked-and-found-false, consistent with every other row of §5.3. Ordinary releases invalidate nothing;
a real change to what serving means invalidates exactly the runs it should, loudly, with a code that
says why.

The exposure checked is the one belonging to the attested `run_ref`, resolved by `append_review` from
that **run's record — and from nothing else**. A review checked against some other run's exposure is
checked against nothing.

Revisions 5–17 said "that run's record and baseline" here while §5.4 said "the run record and nothing
else. No baseline, no control-plane lookup, no session." Both could not be true, and the baseline
spelling is the wrong one: §4.1 seals every replay input into the exposure precisely so this boundary
needs no control-plane file, and re-admitting one would reintroduce the project-rename failure §4.1
exists to close. §5.4 governs.

### 5.3 Outcomes

| Situation | Status / code | Stored? | Counts as support? |
|---|---|---|---|
| No exposure log | `unwired` / `NO_EXPOSURE` | yes | **no** |
| Exposure sealed under a different replay protocol | `unwired` / `REPLAY_PROTOCOL_MISMATCH` | yes | **no** |
| Repo or commit unavailable; replay cannot run | `unwired` / `EXPOSURE_UNREACHABLE` | yes | **no** |
| Replay ran; an entry did not reproduce | `violated` / `EXPOSURE_UNREPRODUCIBLE` | **refused** | — |
| Replay ran; a citation was never served, or cites unserved lines | `violated` / `CITATION_UNSERVED` | **refused** | — |
| Replay ran; everything corresponded | `verified` | yes | yes |

**The rows are ordered, and the order is load-bearing — so it is written as executable steps rather
than as a claim about git calls.** Revisions 1–29 said "the three `unwired` conditions are decided
first, before any git call", which cannot be true of all three: deciding that a repository lacks
`exposure.commit`, or that its history will not walk, *is* a git call. Only the first two rows are
free. The order is:

1. `exposure is None` → `NO_EXPOSURE`.
2. `exposure.replay_protocol != REPLAY_PROTOCOL_VERSION` → `REPLAY_PROTOCOL_MISMATCH`. **Before any
   git call**, and that is the part of the old claim worth keeping: re-serving under a protocol whose
   meaning has changed produces bytes that answer no question, so spending git on it is spending it
   on nothing. A mismatched exposure therefore classifies identically against a healthy repository,
   an unreachable one, and a path that is not a repository at all.
3. `serve.verify_commit(repo, exposure.commit)` raises → `EXPOSURE_UNREACHABLE`. **The existing
   helper, not a second commit probe** — it already resolves through hardened `run_git`, and a
   checker that reached for a bare `rev-parse` would be the two-spellings-of-one-mechanism failure
   §2.2 names three times. This is the one narrowly scoped `except ServeError` in the checker;
   §5.2's propagate rule governs every call after it.
4. `history_traversal_error(repo, exposure.commit)` is non-`None` → `EXPOSURE_UNREACHABLE`. Second
   because it is the more expensive walk and because a commit the repository does not hold has no
   ancestry to fail on.
5. Replay integrity, then citations, as below.

Then **replay integrity is checked in full, and any entry that fails to reproduce short-circuits to
`EXPOSURE_UNREPRODUCIBLE`; citations are never evaluated.** A served map built from entries that did
not reproduce is not a map of anything, so reporting `CITATION_UNSERVED` off it would name a symptom
as the cause and point an operator at the reviewer instead of at the record. Only against a fully
reproduced exposure are citations checked.

**The table is exhaustive over verdicts, not over outcomes.** A git fault outside the two
environment checks of §5.2 produces no row at all — it raises, and `check_correspondence` returns
nothing. That is deliberate: adding a seventh row for it would be choosing the wrapping behaviour
§5.2 rejects, one table over.

The checker reproduces the distinction it exists to enforce: *could not check* is not *checked and
found false*. A journal that fails to reproduce at a pinned commit under a canonical invocation is not
ambiguous — nothing legitimate produces that — so the review is refused. A journal that cannot be
reached genuinely could not be checked, so the review is stored, says so, and earns nothing.

A review with no path-bearing citations is `verified` with a reason: the check ran and found no
violation. It earns no support, but that is §4.2.1's rule, not this one — correspondence answers
whether citations held up, and a review that cited nothing has nothing that failed. Conflating the
two would be the empty/unwired confusion one level up.

### 5.4 The append boundary

```python
def append_review(
    project_root: Path, finding_id: str, submission: ReviewSubmission,
    *, attestation: ReviewAttestation,
) -> Review
```

`attestation` is the reviewer identity, and is the *only* source of one: revisions 1–17 conflated
reviewer identity with record authorship into a single unexplained parameter.

**Revision 34 removes `actor`.** Revisions 18–33 kept it, described as "the writer of the record —
the same nonblank, NUL-free string `ingest_report` demands". The symmetry is false.
`ingest_report` *persists* its actor, in the genesis `Transition` it writes; `append_review` writes
no transition, and `Review` has no actor field and gains none. The parameter would have been
validated and discarded — and a discarded parameter is worse than an absent one, because a public
argument named `actor` advertises a record of the writer that the stored record does not contain.
This is `verified`-supplied-by-the-actor in a milder key: a property the type system appears to
carry and does not. It returns only if writer provenance gains a durable field.

**The executable order.** Stated as numbered steps, for the reason §5.3 needed them: a list of
independent rules does not say which fires first, and every one of these can fire on the same input.

0. **Reject non-exact argument types before reading either, then revalidate both**, each as
   `ExpectedBase.model_validate(arg.model_dump(mode="python", warnings="error"), strict=True)`,
   where `ExpectedBase` is concretely `ReviewSubmission` or `ReviewAttestation`, with
   `ValidationError` and any serialization failure becoming `IngestError`. Without this the boundary
   is not total: an instance built with `model_construct`, or mutated past `frozen=True` through
   `__dict__`, reaches step 4 and hands forged `LocationEvidence` straight to the checker. A boundary
   that trusts the shape of its own arguments has moved the trust decision to its callers, which is
   what §4.2's submission/record split exists to prevent.

   Exact means `type(arg) is ExpectedBase`, checked **before** `model_dump` or any property access.
   A Pydantic model subclass is executable caller code, not a passive schema extension: it can
   override `__getattribute__` or `model_dump`. Rebuilding with `type(arg)` preserves that behaviour.
   Measured, a stateful submission subtype returned a served location to the checker and an unserved
   one to `Review`, storing unshown evidence under a verified correspondence; an attestation subtype
   can likewise pass a run identity cross-check under one value and store another. Neither subtype is
   accepted, and the rebuild returns the named base class rather than the caller's class.

   **Two spellings that look like this one and do not work.** Revision 34 said only "the same as
   `_snapshot_report`", which is a defect twice over:

   - **`ReviewSubmission.model_validate(submission)` is not recursive.** Measured: a
     `LocationEvidence` built with `model_construct` around a path holding a `..` segment survives
     it unchanged. `revalidate_instances="always"` governs whether an instance is revalidated *as a
     field of something being built* — passing the outer instance straight to `model_validate` is
     the case it does not cover. Dumping first is what forces every member back through its own
     validators; the same forged value raises through the dump-then-validate path.
   - **`_snapshot_report` cannot be copied literally.** It dumps in JSON mode, which renders
     `ReviewAttestation.at` as a string that `strict=True` then refuses. `mode="python"` keeps the
     `datetime`. `warnings="error"` is what turns a field whose forged value does not match its
     declared type into a failure rather than a silently coerced dump.
1. **Not an agent** → `correspondence = None`, and nothing further runs: no run lookup, no git, no
   control plane.
2. **Agent** → `load_run_records(project_root)`, matching `record.id == attestation.run_ref`.
   No match is an `IngestError` (below).
3. **The cross-checks, before the checker.** `reviewer_ref` against `record.agent`, `model` against
   `record.model`, and — only when `record.evidence is not None` — `lens` against
   `record.evidence.instrument.ref`. Each mismatch is an `IngestError`. They run first because they
   refuse: there is no reason to replay git for a review that will be rejected.
4. `check_correspondence(submission.evidence, record.evidence, repo=project_root)`.
5. `status == "violated"` → `IngestError`.
6. Under `locked_store(project_root)`, **find the case by scanning**:
   `store.read(name) for name in store.names()`, matching `record.finding_id`. `CaseStore` exposes
   `names()`, `read()`, `write()` and `lock()` and has no load-by-id, so there is no call that
   "loads the case"; `load_cases` scans for the same reason. Doing it through the held descriptor
   rather than through the module-level `load_case` keeps the read inside the lock.
   **No match → `IngestError`, no write** — the caller got an argument wrong, and reporting it as a
   storage fault would name the wrong party.
7. **Only now** derive `review_id`, from the matched record's own `finding_id`, then build the
   `Review` stamped `at=attestation.at`, check for a duplicate, and `with_review` + write.
   - **`review_id` already present** → `IngestError`, no write, checked *before* `with_review`.
     `_validate_reviews` already refuses a duplicate, but with `RecordError` from inside the
     constructor — the model's backstop, not this boundary's answer. Re-submitting an identical
     review is the ordinary retry, since the same attestation and run produce the same `review_id`
     by construction, so this path is reached by normal use and deserves a boundary error.

**Deriving `review_id` after the match, not before it, is a correctness requirement rather than
tidiness.** Revision 34 put it at step 6, ahead of the load. `review_id` hashes `finding_id` through
`_components`, which rejects a NUL — so an unknown *and* NUL-bearing `finding_id` would have raised
`RecordError` out of `review_id()` before the scan could return the `IngestError` this boundary
promises, and the brand-new "every failure is an `IngestError`" rule would have been broken by the
step that was added to enforce it. Hashing the matched record's canonical id also means the id is
derived from a value the store vouched for rather than from the argument.

`repo=project_root` is not a convention: `EvidenceSession.__init__` binds `_project_root = repo_root`
and `start_run` passes `project_root`, so an exposure's commit is a commit of this repository by
construction.

**A `run_ref` that resolves to no record is refused, not stored.** Revision 34 first proposed storing
it as `unwired` under a fourth §5.3 code, reasoning that §6 creates this state deliberately — a
brokered run whose journal is gone writes no record at all — so refusing discards an honest
reviewer's findings for a supervisor's failure. The asymmetry with `EXPOSURE_UNREACHABLE` defeats
that: there, an attested run record exists and only its repository cannot answer, so there is
something to be `unwired` *about*. Here there is no record, so neither identity cross-check can run,
no sealed exposure provenance exists, and the stored review's `run_ref` would point at nothing. §6
already calls the lost-journal branch retryable — that run is re-run, not reviewed around.

**Every failure to resolve is the same refusal, and that is deliberate.** `load_run_records` raises
`RunRecordError` on a symlinked `runs/`, a `runs` that is not a directory, and a non-flat child;
those are a broken project rather than a missing run. They and the no-match case all become
`IngestError`. The distinction is real in the code and worth keeping there, but it is not observable
at this boundary, so §7 carries no row for it — see the "must not be added" list.

**`RunRecordError` is not the whole of what that call can raise, and revision 34's first draft said
it was.** `load_run_records` reaches the filesystem through `exists()`, `is_dir()` and `iterdir()`,
none of which converts a `PermissionError` — `Path.exists()` swallows only the not-found family, and
`iterdir()` swallows nothing. An unreadable `runs/` therefore emits a raw `OSError` from a function
whose documented channel is `RunRecordError`. `append_review` translates **`RunRecordError` and
`OSError` alike** into `IngestError`. Stating "every failure becomes `IngestError`" while catching
one of the two exception types is the failure mode this document keeps finding: a claim about
totality resting on a roster of the cases its author happened to think of.

- **Branches on the ATTESTED `reviewer_kind`, never a submitted one.** Only an agent review resolves a run record and runs
  `check_correspondence`. Human and deterministic submissions get `correspondence=None` and are stored.
  Revision 3 resolved a baseline for every submission, which would have made the boundary unusable for
  the two reviewer kinds §4.2.1 says are unaffected: a human review's `run_ref` need not name an
  autonomous run at all, and demanding a control-plane baseline for one would refuse every human review
  in the toolkit. Broker the kind that needs brokering.
- **Resolves the run record and nothing else.** No baseline, no control-plane lookup, no session.
  Revision 5 sealed every replay input into the exposure and then left this boundary — the only path
  production actually takes — still resolving a baseline, so a project rename would have reintroduced
  the exact failure §4.1 claims to have closed, *while the direct checker test stayed green*. A property
  proven only on the path nobody uses is not proven. The regression test in §7 appends a review through
  this function with the control-plane directory deleted.
- Calls `check_correspondence`. The result is **computed here and cannot be supplied**: `ReviewSubmission`
  has no field for it.
- Refuses `violated` with an `IngestError`, consistent with `_assert_attested_provenance` refusing a
  provenance mismatch.
- Takes the store lock through the same anchored-descriptor path as `ingest_report`, and writes via
  `with_review`, which rebuilds through the constructor and re-checks every derived value.

**That path is `_locked_store`, private to `findings/ingest.py`, and revision 34 moves it.** It is
`CaseStore` plus a `flock` on that same descriptor, so `findings/storage.py` is where it belongs;
importing a neighbour's underscore-prefixed contextmanager would make `append_review` raise
`IngestError` out of a function it does not own. Two conditions on the move:

- **Each descriptor primitive owns its conversion, and `locked_store` adds the lock-management
  layer.** `locked_store` converts `flock` and lock-descriptor `close` failures to
  `CaseStorageError`; the contract covers **acquisition, release and close** rather than acquisition
  alone. Revision 38 extends the same ownership rule down one layer: `open_lock_at` converts both
  lock `fstat` and validation-cleanup close failures to `PathSafetyError`, while `open_dir_inside`
  converts its final directory-descriptor close. `case_store` then maps those path failures to
  `CaseStorageError`, and each writer maps that to its own boundary error.

  **It needs no `PathSafetyError` clause, and revisions 34's two attempts at one were both wrong.**
  `case_store` keeps its `try` **active across its own `yield`** (`storage.py:255–261`), so a
  `PathSafetyError` raised by `store.lock()` — inside the caller's `with` body — is thrown back into
  that generator and converted there. Measured, with a FIFO planted at `.ingest.lock` and every
  other conversion removed: the call still raises `CaseStorageError`. The claim that the lock leaf
  "sits outside `case_store`'s try" was false, and both fixtures written to prove it were vacuous.

  **Teardown never replaces an exception already in flight.** If caller work is failing and unlock
  or descriptor close also fails, the teardown failure is attached as a note to the active
  exception. With release, lock close, and directory close all injected to fail, the same sentinel
  from the body remains primary and all three cleanup attempts still run. When there is no active
  failure, the owner raises its documented `PathSafetyError` or `CaseStorageError` normally.

  **Its scope is setup and teardown, and the claim has to be stated as what it adds.**
  `locked_store` introduces **no catch spanning its body**: its conversion wraps the code around the
  `yield`, never the `yield` itself. It does not follow that a body exception reaches the caller
  untouched — `case_store`'s existing clauses still convert a body-raised `FileNotFoundError` or
  `PathSafetyError` on the way out, as measured above. Revision 35 wrote the stronger sentence
  ("whatever the caller raises passes through untouched") one line before acknowledging the fact
  that contradicts it. A contextmanager whose `try` spans its own yield relabels its caller's
  exceptions as its own; that is the fault `case_store` has, and `locked_store` must not copy its
  shape while sharing its module — but not copying it is all `locked_store` can promise.
- **Each writer translates at its own boundary.** `ingest_report` catches `CaseStorageError` and
  raises `IngestError`, exactly as callers observe today; `append_review` does the same for itself.
  Storage raises storage errors; a boundary names its own.

Plus two backstops:

- The model invariant in §4.2, so a write path that bypasses this function still cannot store `violated`.
- A non-gating `validate` check at info severity, so agent confirmations that do not count are visible
  in aggregate. The difference between a known weaker standing and a silent one.

**Revision 34 widens that check and renames it.** Revision 26 specified
`review.correspondence-unwired`, covering unwired reviews. But §4.2.1 excludes agent confirmations
two ways, and the other one is invisible: a review whose correspondence is `verified` while its
evidence is empty or mixed with `TextEvidence` is stored, renders as a confirming review, is excluded
from `confirmation_count`, and is reported by nothing. That is §4.2.1's own "cheapest possible
fabrication" — and a reader seeing three confirming reviews above `confirmations: 2` gets no account
of the difference, which is precisely the silence this backstop exists to break.

The check becomes **`review.uncounted-confirmation`** at `validate/checks/review_confirmations.py`,
reporting every agent review with `outcome == "confirms"` for which `counts_as_support()` is false.
Subject is the case file path; qualifiers are `(review_id, reason)` with `identity_qualifiers =
("review_id",)`, so each review is its own stable, individually suppressible fingerprint. `reason` is
derived, never authored: the correspondence code when there is one, otherwise `no location evidence`
or `evidence mixes non-location entries`.

Two mechanical requirements that are easy to miss:

- **The rule id must be added to `_POLICY_INFO_RULE_IDS` in `validate/findings.py`.** Otherwise
  `validation_observation` degrades every `info` result to a bare `ValidationNotice`, which carries no
  rule, no qualifiers, no fingerprint and no suppression. An advisory finding nobody can suppress is
  an advisory finding somebody eventually deletes.
- **This is the first validate check to read the case store**, via `load_cases(project_root)`.
  `validate` already depends on `findings` — `checks/__init__.py` imports `findings.producers` — so
  the direction is established rather than new, but the store had not been read from here before.
  Read failures propagate: the validation runner already converts them into `validate.check-error`,
  and catching them here would trade a precise report for a vaguer one.

One severity, `info`, for both exclusions. A vacuous `verified` is arguably louder than an `unwired`,
and `severities` can express the split later; 2c's real population is what should decide it, not a
guess made before any producer exists.

## 6. Error handling

| Kind | Behaviour |
|---|---|
| Defined miss | Served as an answer with an explicit marker |
| Policy denial | Refused, policy-supplied notice, spends a round |
| Malformed search pattern | Refused as retryable, spends a round |
| Budget exhausted | Refused, spends nothing further |
| Anything else from git | Raises, halts the run |

**A run record gets `evidence=None` only if a session was never opened.** `start_run` records
`EvidenceSession` in `RunBaseline`; at `finish_run`, a baseline that says "brokered" plus a missing or
unreadable journal yields `RunOutcome(RunDisposition.UNWIRED, record=None)` — **no record at all.**

**So the seal is attempted immediately after the baseline loads, before any other check.** Its
failure is the one that returns no record, and it is indifferent to disposition: a brokered run whose
journal is gone writes nothing whether its verdict would have been clean, quarantined or unwired. A
seal placed with the other checks would compute a full verdict — belief basis, path gate, commit
marks — and then discard it, and, worse, would invite an implementation that writes the record for
the quarantined and unwired paths while honouring this rule only on the clean one. The sealed
exposure then threads through every `_finalize` call, including the `_unwired` ones, because a run
that was brokered was brokered no matter how it ended.

Revision 5 said "yields `UNWIRED`, which blocks — rather than writing a record that reads as
unbrokered", and specified no state in which that is possible. `evidence` is `EvidenceExposure | None`
and `None` is defined as "never brokered", so a failed seal has nothing honest to write: an exposure
does not exist, and `None` asserts something false about a run that *was* brokered.

`RunOutcome.record` is already `AutonomousRunRecord | None`, and `finish_run` already writes no record
when it cannot attest — "an invented record here would be the fabrication this slice exists to
prevent." A failed seal is a third case of that rule, and this is a deliberate narrow exception to
`finish_run`'s "identity is known, so write an attestation saying we could not tell": identity *is*
known here, but the record still cannot express the truth, so writing one would trade a missing
attestation for a false one. The branch reads as unattested, which is the designed failure direction —
and, unlike a written record, it is retryable.

Without this rule, losing a journal silently downgrades every review in that run from `verified` to
`unwired` — which, under §4.2.1, silently drops their support to zero. Either direction of silent
downgrade is a lie about what was checked.

## 7. Testing

- **`serve.py`** — each operation; an empty file at the commit reads differently from an absent path;
  unrecognised stderr raises rather than answers. Named regression test: **a well-formed but
  nonexistent commit halts rather than answering**, using a genuinely invalid ref — `"0" * 40`
  produces the *miss* message and would let the test pass against broken code.
- **Canonical invocation** — a repository configuring `grep.patternType=fixed` and one configuring
  `basic` produce the same served bytes for the same request; `color.ui=always` does not colour the
  output; `log.showSignature=true` does not change the served log. Each written from the probe, so the
  probe's findings are what the tests assert.
- **Locale** — `[[:alpha:]]` against a non-ASCII corpus produces byte-identical results with the parent
  process under `C`, under a UTF-8 locale, and under a translated locale; the defined-miss classifier
  recognises an absent path in all three. Run as a replay across differing parent locales, since that
  is the failure being prevented.
- **Pathspec translation** — under `literal`, a deny prefix `notes/a[b].md` excludes that file and
  leaves the sibling `notes/ab.md` searchable, which is the measured divergence from the bare
  `:(exclude)` spelling (§3.2); `private` denies `private/x` and does not deny `privateer/x`; and
  the `read` denial and the `search` exclusion are asserted to **agree** on the same table of inputs,
  because two mechanisms for one policy is how a policy comes to be half enforced. The over-exclusion
  case is asserted directly and not only through the agreement table, since it is the one that
  motivates `literal` at all.
- **`read` refuses a directory** — a path naming a tree is refused, not served, and the refusal is
  distinguishable from an absent path; asserted against a real tree, since `git show` would have
  answered it with a listing at exit 0 (§3.2).
- **Session handle** — `--session ../../elsewhere` is refused before any path join; a handle that parses
  but whose baseline carries a different `run_id` is refused after loading.
- **`policy.py`** — containment before prefix; `..` and absolute paths refused lexically; **a
  working-tree symlink over a base-commit path does not deny the request**, since the blob read never
  consults the working tree; the dual as-spelled/resolved check still catches a symlink escape on the
  `served/` directory, which is a real filesystem path.
- **Served bytes and the write gate** — composed against the shipped `path_gate`, not asserted: a
  reviewer that serves several files produces a `ChangeSet` that `evaluate(..., tier=REPORT_ONLY)`
  finds **empty**, because nothing landed in the tree. Written as the standing guard against a future
  revision reintroducing an in-tree destination, which no test inside this package would catch. Also:
  the served name is the sha256 of the served bytes, so a request cannot choose it; two requests
  serving identical bytes coincide; and `finish_run` seals a run whose `served/` directory has been
  emptied, since nothing trusted reads it. If an ancestor is renamed after the run-directory
  descriptor is captured, serving fails before the journal append rather than returning a stale
  receipt path; the regression asserts both that the project remains untouched and that no exposure
  was recorded.
- **`session.py`** — a denial spends a round; exhaustion refuses without further spend **and appends
  no journal line**, asserted by sealing a run whose actor kept asking past its budget and confirming
  the record validates rather than that the refusal was returned; no unbudgeted path to `serve` is
  exported; `--session` cannot override the baseline's journal path, budget, or surface policy;
  `start --broker-spec` against an existing journal refuses; **seeding N inline inputs leaves
  `requests_used` at zero**; a denied request and a malformed pattern each raise it by one; a refusal
  writes no file into `served/`, while a defined miss writes its marker. A maximally encoded request
  and inline event fit the derived journal bound, a forged over-bound event is refused before any
  artifact is created or delivered, and an over-long CLI request exits as a usage error without a
  spend.
- **Refusals do not become coverage** — a run that reads a denied path, is refused, and cites that
  path is **not** corresponding, asserted end-to-end through `append_review` rather than against the
  map builder, since the fail-open this closes is reachable only from the production path. Written as
  a negative test that fails if the builder classifies by payload emptiness rather than by `Outcome`
  (§5.1), and paired with one asserting a genuinely **empty file** at the commit *does* give `FULL`
  coverage with a line count of zero — the two cases the empty payload makes identical, which is why
  neither is provable without the other.
- **A relabelled refusal does not replay** — an exposure whose refused entry is edited to
  `outcome: served`, `sha256` untouched, yields `violated` / `EXPOSURE_UNREPRODUCIBLE`. The hash
  reproduces, so this guard is proven only by the outcome comparison, and it fails if that comparison
  is dropped.
- **`control_plane.py`** — `run_dir` is a pure function of `(project root, run id)`; **two projects
  producing the same run slug get different directories**, and a fork of a project does not resolve its
  parent's; **a `science.yaml` name containing `/` or `..`, or one 4096 characters long, changes no
  path** — asserted directly, since that is the vector the digest-only key exists to close;
  `--broker-spec` and `--baseline-out` together are refused, as are `--session` and `--baseline` on
  `finish`; a brokered run whose baseline is elsewhere is refused rather than searched for; a
  control-plane root inside the project is refused.
- **Sealing** — a brokered run whose journal is deleted writes **no record in every disposition**,
  asserted for clean, quarantined and unwired separately rather than once, since §6's rule is
  indifferent to disposition and a seal placed late would satisfy it on one path only; a sealed run
  replays from `(record, repo)` alone with the control-plane directory
  **deleted**, asserted **through `append_review`** and not only against `check_correspondence`: the
  production path is the one the claim is about, and revision 5's version of this guard would have
  passed while production still resolved a baseline. A failed seal returns
  `RunOutcome(UNWIRED, record=None)`, and no record is written for it.
- **Protocol version** — an exposure sealed at protocol `N` read by a toolkit at `N+1` yields
  `unwired`/`REPLAY_PROTOCOL_MISMATCH`, never `violated`; the same exposure at `N` replays clean.
- **Model** — agent review without `correspondence` rejected; `violated` unstorable; `ReviewSubmission`
  rejects a `correspondence` key outright; `requests_used > budget` rejected; entries disagreeing on
  commit rejected; `EvidenceExposure.commit != base_commit` rejected; an exposure without an
  `instrument` rejected; `unwired` without a code rejected. Plus, from revision 34: `evidence` over
  `MAX_EVIDENCE_ENTRIES` and `uncertainty` over `MAX_UNCERTAINTY_ENTRIES` each rejected on **both**
  `ReviewSubmission` and the stored `Review` — four assertions, not two, since a producer reaches
  the first of each pair and a bypassing write path reaches the second; and a
  `ReviewAttestation` whose `reviewer_kind` is `agent` is rejected without a `lens` and without a
  `model`, at the attestation rather than three steps later at the record.
- **Eligibility** — one test per `ReviewerKind`, asserted against the `Literal` rather than a hand-written
  list, so a kind added later fails loudly instead of silently landing on the wrong side: an agent
  `confirms` counts only when `verified` **and** every evidence entry is a location; `human` and
  `deterministic` count regardless; an agent `confirms` with only `TextEvidence` does not count;
  **one honest location citation mixed with prose entries does not count**; the same review with the
  prose moved to `note` does.
- **Correspondence** — one test per row of §5.3, plus: a grep hit on line 1 does **not** validate a
  citation to line 900; a span exceeding the matched lines does not correspond; a line beyond a read
  file's length does not correspond; a `history` entry does not validate a line citation **nor a
  pointer**; a pointer under `LINES` does not correspond; a read miss validates a path-only citation
  and refuses a lined one; **a search miss and an empty history contribute no coverage at all**; an
  inline entry whose target is absent from **`exposure.inline`**, and one whose `sha256` disagrees
  with it, each yield `violated` / `EXPOSURE_UNREPRODUCIBLE` rather than merely contributing no
  coverage; a policy narrowed between serving and replay does not silently re-serve denied hits; the
  vacuous `verified`. Plus, from revision 29: a file whose only line break is a CR reads
  `line_count = 1` from a `read`, not 2; a path both inline-seeded and read takes the **smaller**
  count; a path searched twice for different patterns admits citations to **both** hit sets; a
  mismatched `replay_protocol` classifies the same against a healthy repository and against a
  directory that is not a repository at all; and a repository missing `exposure.commit` yields
  `unwired` while a `ServeError` raised after both environment checks pass **propagates** rather
  than becoming a verdict.
- **`append_review`** — a human review is stored with no control-plane directory existing at all; the
  same for `deterministic`; an agent review whose run record carries **no exposure** yields
  `unwired`, not a crash. Plus attestation (revision 18): a submission cannot express a
  `reviewer_kind` at all, so the `human`-labelled-agent bypass is unconstructible; an attested agent
  whose `reviewer_ref` or `model` disagrees with the run record is an `IngestError`; the same for a
  `lens` that is not `exposure.instrument.ref`; and two submissions under one run cannot mint two
  `review_id`s, because every field the id hashes is attested rather than supplied. Plus, from
  revision 34: a `run_ref` matching no record is an `IngestError` that leaves the case file
  byte-identical; a symlinked `runs/` and an *unreadable* one are the same `IngestError` rather than
  a stored correspondence or a raw `PermissionError`; an unknown `finding_id` and a duplicate
  `review_id` are each an `IngestError` leaving the case untouched; a `model_construct`-forged
  submission is refused at step 0 rather than replayed; and the stored `Review.at` is the attested
  instant, not the moment of the write.

  The cross-checks-before-checker order needs a fixture chosen with care, because the obvious one
  cannot see it: against an unreachable repository the checker *returns* `unwired` rather than
  raising, so both orders end in the same `IngestError` and the ordering is invisible. It is
  observable only where the checker would **raise** — an exposure that verifies and traverses but
  whose replay hits a `ServeError`, which §5.2 propagates rather than converting. Then the correct
  order refuses on identity with an `IngestError` and the inverted one dies of the `ServeError`
  first. Stated here because the natural test asserts the right outcome for a reason unrelated to
  the guard.
- **`review.uncounted-confirmation`** — reports an `unwired` agent confirmation **and** a vacuously
  `verified` one, the second being the case revision 26's `review.correspondence-unwired` could not
  see; reports neither a counted agent confirmation nor a human or deterministic one; and its result
  carries a rule, qualifiers and a fingerprint, which is the assertion that fails if the rule id is
  missing from `_POLICY_INFO_RULE_IDS` and the observation degrades to a bare `ValidationNotice`.
- **Derived guard** — no path reaches git without passing `authorize`, asserted by walking the
  dispatch in `serve.py`. Same spirit as `tests/test_instrument_boundary.py`: derived from the code,
  not a list someone maintains.
- **Integration** — end-to-end against a real temporary git repository: open, serve, seal, append.

**Every guard is proven by restoring the prior behaviour and confirming its test fails.** Each defect
closed downstream survived a green suite until it was negative-tested, and four of the six defects in
revision 1 of this document were guards that looked right on the page. A guard nobody has watched fail
is a guard nobody has tested.

**Plan 4's roster is written as pairs — the mutation beside the test it must turn red — because
across plans 2 and 3 the recurring finding was a mutation that left its test green and therefore
certified nothing.** The `Slice` column is not decoration: a mutation is only meaningful against a
tree where the guard it breaks exists, so a 4b row run during 4a is green for the wrong reason.

| Slice | Mutation | Test that must fail |
|---|---|---|
| 4a | Delete the NFC/UTF-8 tree check at open | a session against an NFD tree opens |
| 4a | Drop `GIT_SHALLOW_FILE` from `_ENVIRONMENT` | `history` served after `.git/shallow` is written mid-run does not match the same request served before it |
| 4a | Drop `GIT_NO_LAZY_FETCH` from `_ENVIRONMENT` | a request against a `--filter=tree:0` clone whose promisor remote **still holds the objects** fails, rather than serving them |
| 4a | Drop the traversal check at open | a brokered run against a genuinely shallow clone opens |
| 4a | Diagnose with `rev-parse --is-shallow-repository` through hardened `run_git` | a **complete** repository reports no traversal error |
| 4a | Diagnose with `rev-parse --is-shallow-repository` under a detector-specific environment omitting `GIT_SHALLOW_FILE` | a complete repository with `.git/shallow` **planted** reports no traversal error |
| 4a | Journal a shallow-`history` refusal instead of refusing at open | a brokered run against a shallow clone opens instead of refusing before session creation |
| 4c | Import `Correspondence` from `evidence_broker.py` | a **subprocess** running `python -c "import science_model.evidence_broker"` exits non-zero |
| 4c | Have `science_model/correspondence.py` import `_Base` from `audit.subjects` | a **subprocess** running `python -c "import science_model.correspondence"` exits non-zero |
| 4b | Have `science_model/correspondence.py` import anything from `science_model.audit` | a **subprocess** executing the leaf with `runpy.run_path` finds `science_model.audit` absent from `sys.modules` |
| 4b | Compute `line_count` with `splitlines()` | a file whose only line break is a CR reads `line_count = 1` |
| 4b | Merge two `Full` contributions by taking the larger, or by last-write-wins | a path inline-seeded at `n+1` lines and read at `n` refuses a citation to line `n+1` |
| 4b | Merge two `Lines` contributions by replacing rather than uniting | one path searched twice for different patterns admits a citation to a line matched **only by the first** search |
| 4a follow-up | Check UTF-8 and NFC instead of `normalize_project_path(p) == p` | a brokered run opens against a tree holding `a\b.txt` |
| 4b | Split the payload on LF, or on `LF + <commit>:` | a search hit on a file named `a<LF>b.txt` parses to that path and line, under **both** spellings |
| 4b | Evaluate a `FULL` span by iterating its lines | a citation spanning lines 1 to `10**18` against **`Full(10**18 - 1)`** is refused **within the test timeout** |
| 4b | Compare inline entries to the manifest with a dict keyed on `(target, sha256)` | a manifest item with **no** corresponding entry yields `EXPOSURE_UNREPRODUCIBLE`; and two entries against one manifest item do too |
| 4b | Accept a manifest with one `(target, sha256)` at two `lines` values | that exposure is refused rather than classified |
| 4b | Check the protocol after resolving the commit | a v1 exposure against a repository that is not a git repository at all yields `REPLAY_PROTOCOL_MISMATCH`, not `EXPOSURE_UNREACHABLE` |
| 4b | Probe the commit with a bare `rev-parse --verify` instead of `serve.verify_commit` | an exposure whose `commit` is the 40-hex OID of a **tree or blob** present in the repository yields `unwired` / `EXPOSURE_UNREACHABLE` |
| 4b | Wrap replay and return `unwired` on any git fault | a `ServeError` raised after both environment checks pass propagates out of `check_correspondence` |
| 4b | Treat an inline entry missing from `exposure.inline` as merely uncovered | a tampered inline `target` yields `EXPOSURE_UNREPRODUCIBLE`, not `CITATION_UNSERVED` |
| 4a | Check the payload cap after `communicate()` | an oversized `search` refuses without first buffering the output |
| 4a | Remove the `read` size pre-check | an oversized blob refuses without being read |
| 4a | Bound stdout only | an oversized `stderr` refuses |
| 4a | Exempt the `config --list` preflight | a repository whose `include.path` yields an oversized listing refuses |
| 4a | Exempt the tree scan | an oversized `ls-tree` refuses instead of declaring the tree NFC |
| 4a | Truncate instead of refusing at the ceiling | an over-ceiling config listing does not silently under-blank filter drivers |
| 4a | Journal a served `stderr` overflow as a `Denial` | search and history propagate the overflow instead of returning `payload-too-large` |
| 4a | Turn a configuration-preflight `GitError` into a `Denial` | a served operation propagates the base invocation failure instead of returning a refusal |
| 4a | Make a tree-scan overflow a `Denial` instead of refusing to open | an oversized tree opens no session |
| 4a | Omit `GitError` from the `autonomy start` boundary | a hardened-git open failure exits 1 instead of the documented exit 2 |
| 4b | Let `REFUSED` contribute `Full(0)` | a citation to a policy-denied path is refused |
| 4b | Drop `Full` superseding `Lines` | a path both read and searched admits a line outside the hits |
| 4b | `split(b"\0")` without `maxsplit=2` | a binary hit whose matched content holds a NUL parses |
| 4b | Drop the trailing-bytes clause in `line_count` | a citation to the last line of a file with no final newline |
| 4b | Permit `pointer` under `Lines` | a pointer citation on a search-only path is refused |
| 4b | Ignore `replay_protocol` | a v1 exposure yields `unwired`, not a verdict |
| 4b | Make a span cite only its endpoints | a span of lines **2–4** against hits `{2, 4}` is refused |
| 4b | Evaluate citations before replay integrity | an unreproducible exposure reports `EXPOSURE_UNREPRODUCIBLE`, not `CITATION_UNSERVED` |
| 4b | Drop the traversal check at replay | a `history` exposure replayed in a `--depth 1` clone yields `unwired`, not `violated` |
| 4b | Memoise replay across exposures | two exposures differing only in `surface_policy` do not share a cached payload |
| 4c | Re-add `reviewer_kind` to `ReviewSubmission` and branch on it | constructing a submission carrying `reviewer_kind` raises |
| 4c | Skip the `reviewer_ref` cross-check | an attested agent whose `reviewer_ref` disagrees with its run record's `agent`, **its `model` agreeing**, is stored |
| 4c | Skip the `model` cross-check | an attested agent whose `model` disagrees with its run record, **its `reviewer_ref` agreeing**, is stored |
| 4c | Skip the lens cross-check | an attested `lens` that is not `exposure.instrument.ref` is stored |
| 4c | Apply the lens cross-check unconditionally | an agent review whose run has **no** exposure stores as `unwired`, not `IngestError` |
| 4c | Store an unresolvable `run_ref` as a correspondence instead of refusing | an agent review naming a run with no record raises `IngestError` **and leaves the case file byte-identical** |
| 4c | Resolve a baseline, or open the control plane, in `append_review` | a review appends with the control-plane directory **deleted** |
| 4c | Stamp `Review.at` from a clock instead of `attestation.at` | a review appended with an attested `at` in the past stores that instant |
| 4c | Drop the stored-`violated` invariant | a `Review` carrying `correspondence.status == "violated"` constructs |
| 4c | Drop agent-requires-`correspondence` | an agent `Review` with `correspondence=None` constructs |
| 4c | Drop `max_length` from `ReviewSubmission.uncertainty` | a submission of `MAX_UNCERTAINTY_ENTRIES + 1` entries raises |
| 4c | Drop `max_length` from `Review.uncertainty` | constructing a stored `Review` with `MAX_UNCERTAINTY_ENTRIES + 1` entries raises |
| 4c | `== "human"` instead of `!= "agent"` in `counts_as_support` | a **deterministic** confirmation counts |
| 4c | Drop the `status == "verified"` clause | an `unwired` agent confirmation **carrying location evidence** does not count |
| 4c | Drop the non-empty `evidence` clause | an agent confirmation, `verified`, citing **nothing**, does not count |
| 4c | `any` instead of `all` over location evidence | an agent confirmation citing one location **and one `TextEvidence`** does not count |
| 4c | Have the check report only non-`verified` correspondence | a **vacuously `verified`** agent confirmation is reported |
| 4c | Omit `review.uncounted-confirmation` from `_POLICY_INFO_RULE_IDS` | the check's result carries a rule, qualifiers and a fingerprint |
| 4c | Drop the `outcome == "confirms"` clause from `counts_as_support` | a **human** review with outcome `refutes` does not count |
| 4c | Drop `max_length` from `ReviewSubmission.evidence` | a submission of `MAX_EVIDENCE_ENTRIES + 1` entries raises |
| 4c | Drop `max_length` from `Review.evidence` | constructing a stored `Review` with `MAX_EVIDENCE_ENTRIES + 1` entries raises |
| 4c | Drop `ReviewAttestation`'s agent-requires-`lens` | an agent attestation with no `lens` raises **at the attestation** |
| 4c | Drop `ReviewAttestation`'s agent-requires-`model` | an agent attestation with no `model`, **its `lens` present**, raises at the attestation |
| 4c | Let `ReviewSubmission` accept a `correspondence` key | constructing a submission carrying `correspondence` raises |
| 4c | Skip step 0 for `submission` | a submission built with `model_construct`, carrying a `LocationEvidence` whose `path` holds a `..` segment, raises `IngestError` **and `check_correspondence` is never called** |
| 4c | Skip step 0 for `attestation` | a `model_construct`-forged **attestation** — an agent with `lens=None` — raises `IngestError` **and `load_run_records` is never called** |
| 4c | Spell step 0 as `T.model_validate(arg)` without the dump | the same forged nested `LocationEvidence` raises **and `check_correspondence` is never called** |
| 4c | Dump in `mode="json"` at step 0 | a **well-formed** submission and attestation append successfully |
| 4c | Run `check_correspondence` before the cross-checks | an attested agent whose `model` disagrees, **against an exposure whose replay raises `ServeError`**, fails with `IngestError` and not `ServeError` |
| 4c | Rely on `_validate_reviews` for the duplicate instead of checking first | re-submitting an identical review raises `IngestError`, **not `RecordError`**, and leaves the case byte-identical |
| 4c | Catch only `RunRecordError` around `load_run_records` | an agent review against an **unreadable** `runs/` raises `IngestError`, not `PermissionError` |
| 4c | Let `OSError` from `flock` **acquisition** escape `locked_store` | with `fcntl.flock` injected to raise `OSError`, a **non-agent** review raises `IngestError` |
| 4c | Let `OSError` from `flock` **release** escape `locked_store`, or replace an active body exception | with release-only injection, a non-agent review that otherwise succeeds raises `IngestError`; with body, release, and close failures together, the body's exact exception remains primary |
| 4c | Let `OSError` from the lock `os.close` escape `locked_store`, or replace an active body exception | with lock-close injection, a non-agent review raises `IngestError`; with body, release, and close failures together, the body's exact exception remains primary |
| 4c | Widen `locked_store`'s `try` to span its own `yield` | an `OSError(EIO)` raised **inside** a `with locked_store(...)` body propagates as that same exception |
| 4c | Derive `review_id` before the case scan | an unknown `finding_id` **containing a NUL** raises `IngestError`, not `RecordError` |
| 4c | Accept a behavioural `ReviewSubmission` subtype by rebuilding through `type(value)` | the subtype is rejected before `model_dump`, field access, run lookup, checker invocation, or storage |
| 4c | Accept a behavioural `ReviewAttestation` subtype by rebuilding through `type(value)` | the subtype is rejected before either argument is read and before run lookup, checker invocation, or storage |
| 4c | Let lock `fstat` `OSError` escape `open_lock_at` | the storage API raises `CaseStorageError` and a non-agent append raises `IngestError` |
| 4c | Let validation-cleanup lock `close` replace the path failure | the original lock-validation failure remains inside `CaseStorageError` / `IngestError`, with cleanup failure secondary |
| 4c | Let the directory-descriptor `close` escape or replace an active body exception | an otherwise-successful append raises `IngestError`; under simultaneous body and teardown failures, the body exception remains primary |
| 4c | Restore `confirmation_count`'s former outcome-only filter | record-level unwired, vacuous verified, and mixed-evidence agent confirmations each count as zero |

**The import-cycle row must run in a subprocess, and the direction is not symmetric.** Written as an
in-process `import science_model.audit.record`, the assertion probes the *safe* direction: it
initialises `audit` first, after which importing `evidence_broker` succeeds — and under pytest it is
worse than useless, because collection has almost certainly imported one of the two already and
`sys.modules` returns a hit without executing anything. The failing direction is a **fresh
interpreter** entering `science_model.evidence_broker`, which reaches `audit/__init__` and loops back
into a partially initialised `audit.record`. Spawn it; do not trust the ambient module cache. This is
the general form: *a cycle test that shares a process with its own test runner tests the runner's
import order.*

**Revisions 29–30 move both cycle rows to 4c, and give 4b the row it can actually certify.** The cycle
does not exist until `audit/record.py` imports `Correspondence`, and that import is 4c's — 4b changes
no stored-record model at all (§2.2). Run against 4b's tree, either mutation imports cleanly and the
row passes for the wrong reason, which is the `Slice` column's whole purpose one slice over from
where it was last needed. What 4b *can* prove is the structural fact it is actually responsible for:
`science_model/correspondence.py` reaches `science_model.audit` by no path. A normal package import
cannot establish that fact because eager `science_model/__init__.py` loads audit first. Instead, a
fresh interpreter executes the leaf directly with `runpy.run_path(sys.argv[1])` and asserts audit is
absent from `sys.modules`. This is still a predicate over what the leaf loads rather than a roster of
imports someone maintains, and the `_Base` mutation breaks it immediately on 4b's own tree, without
waiting for 4c to close the loop.

**The span row needs an unserved *interior*, and revisions 1–29 specified one that cannot fail.** A
ten-line span against a one-line hit is refused by endpoint-checking as readily as by the real rule —
line 10 is not in `{1}` — so the mutation stayed green and the row certified nothing for
twenty-nine revisions. Only a span whose endpoints are both served and whose middle is not
separates them: lines 2–4 against `{2, 4}`. This is the `Full`-supersedes-`Lines` caution in a second
costume — a fixture that satisfies the assertion for a reason unrelated to the guard — and the same
question finds it: which line does the mutation break first? With the ten-line span, none.

**The `verify_commit` row needs a non-commit object, or it certifies nothing.** Against an exposure
whose commit is merely *absent*, a bare `rev-parse --verify` and `verify_commit` agree — both fail,
both give `EXPOSURE_UNREACHABLE` — so the obvious fixture leaves the mutation green. What
`verify_commit` adds is `^{commit}` (and `--end-of-options`): it requires the object to be a
**commit**, where the bare form accepts any object name. `EvidenceExposure.commit` is pattern-bound
to 40 hex, which a tree or blob OID satisfies, so that is a constructible record — and under the
mutation it resolves, replay proceeds against a non-commit, and the checker raises instead of
classifying. Which line does the mutation break first: with an absent commit, none.

**The span row is a timeout row, and a timeout row has one honest form.** The defect it guards is
non-termination, so the mutation does not produce a wrong answer to compare against — it produces no
answer. Assert the refusal under a bounded timeout and choose a span whose length makes iteration
impossible rather than merely slow (`10**18`, not `10**6`, which a fast machine would grind through
and pass). Do not write it as a timing comparison between the two implementations; that is a
benchmark, and it goes flaky on shared runners. The failing observation is "did not return", not
"returned late".

**Its coverage value must not let the mutation short-circuit, which revision 31's did.** The row
first read `Full(3)`, and `all(line <= 3 for line in range(1, 10**18 + 1))` returns `False` at line
**4** — four iterations, well inside any timeout, so the mutation passed and the row certified
nothing. The count has to sit just below the span's end so that every line but the last satisfies the
predicate: `Full(10**18 - 1)` against a span of 1 to `10**18` refuses instantly under the O(1) form
and cannot return under iteration. A timeout row is only as strong as the input that keeps the
mutant running — *which line does the mutation break first?* With `Full(3)`, the fourth.

**The LF row must assert both wrong spellings, because the obvious repair is also wrong.** Splitting
on `LF + <commit>:` passes a naive fixture and fails on a filename containing that sequence — and the
commit is knowable to whoever names the file. The row is discharged only if the same test refuses
both the plain LF split and the prefixed one, which the forward scan satisfies by construction.

**Three rows that must not be added: the quadratic accumulation, the `LINES` span pre-check, and the
widened tree assumption.** Grouping hits by path before constructing coverage computes the *same*
verdict as merging one at a time, so no mutation of it changes an answer — only a timing, and §7 does
not certify timings. The `LINES` pre-check joined that list at revision 32: a contiguous span leaves
a set of n elements within n+1 steps, so removing the guard changes the constant factor and nothing
else. Likewise §5.1's assumption sentence about what the namespace rests on is prose describing a
guarantee enforced in §3.1; the 4a follow-up row above is where that property is certified, and a
second row asserting the prose would test nothing. All three are recorded here so their absence reads
as a decision rather than an oversight.

**Note what separates these from the `FULL` span row, since all four look alike.** An optimisation
whose removal leaves the answer and the termination unchanged gets no row. An optimisation whose
removal leaves the answer unchanged but the termination *unbounded* is not an optimisation, and gets
one. Revision 31 put `FULL` and `LINES` on the same side of that line by pattern-matching on their
shapes instead of asking what bounds each loop.

**A row that must not be added: pre-normalising the replayed request target.** `normalize_project_path`
is idempotent and the journal stores its output, so a checker that normalises again and one that does
not are observationally identical, in both fixtures. There is no test that turns red, so the rule
belongs in §5.2's prose and nowhere here. Revision 27 established the discipline on the
`GIT_SHALLOW_FILE` pair for the same reason: a roster row whose mutation cannot fail certifies
nothing and reads as though it does.

**Three more that must not be added, from 4c's certification rounds.**

- **Treating a broken `runs/` as a missing run.** While a missing record was to be stored as
  `unwired` and a broken directory refused, the two had different outcomes and the mutation was
  observable. §5.4 now refuses both with `IngestError`, and nothing distinguishes them but message
  text. The distinction stays in the code and in §5.4's prose; the row would certify nothing. The
  general form is new to this document: **a ruling that simplifies behaviour can invalidate a guard
  written for the richer behaviour**, so the guards get re-read against every ruling rather than
  merely extended by it.
- **"Give the check its own predicate instead of `counts_as_support()`."** A faithful copy of the
  predicate satisfies that mutation and changes no output. Sharing the predicate is the right
  structure and §4.2.1 argues for it, but structure is not what an outcome test can observe — so the
  row names a concrete wrong implementation, *report only non-`verified` correspondence*, which the
  vacuously-`verified` fixture separates. This is the mirror image of the vacuous fixtures revisions
  31 and 32 corrected: there the input could not distinguish a genuinely different mutant, here the
  mutant was not different from the original.
- **Raise `CaseStorageError` rather than `IngestError` when the case scan finds no matching
  `finding_id`.** The enclosing `except CaseStorageError` translates either implementation to the
  same public `IngestError`, before any write. Only cause, message, or source structure distinguishes
  them; none is a boundary guarantee, so a test for this row would certify an implementation detail.

**Why §4.2.1 gets five rows rather than one.** Its eligibility has five independent conditions —
outcome, reviewer kind, correspondence present, status `verified`, and every entry a location — and a
single fixture that fails when any of them is dropped certifies only whichever one it trips first.
Each row above therefore carries a fixture that satisfies the other four: the `verified`-clause
fixture cites real locations, the non-empty-evidence fixture is `verified`, the `all`/`any` fixture is
`verified` with one genuine citation, and the outcome-clause fixture uses a **human** reviewer so it
cannot pass by way of the agent branch. The same reasoning split the `reviewer_ref` and `model`
cross-checks, where revision 26's single row — "an attested agent whose `model` disagrees" — could
not certify the `reviewer_ref` comparison at all.

**The missing-run row asserts two things, and the second is the load-bearing one.** `IngestError`
alone is satisfied by an implementation that writes the review and *then* raises. The row requires
the case file to be byte-identical afterwards, which is what "refused" has to mean at a boundary that
owns a write. The duplicate-`review_id` row carries the same second assertion for the same reason.

**The lock rows took three attempts, and the first two were vacuous in the same way.** Revision 34
wrote "an unsafe case path", then "an unsafe `.ingest.lock` leaf" — and `case_store` converts
`PathSafetyError` in both cases, because its `try` stays active **across its own `yield`**
(`storage.py:255–261`), so a failure inside the caller's `with` body is thrown back into that
generator and handled there. Measured with a FIFO at `.ingest.lock` and every other conversion
removed: still `CaseStorageError`. Each draft moved the fixture closer to the leaf while the thing
that made it vacuous was never the leaf's location — it was the *extent of somebody else's `try`*,
which neither draft had checked. `locked_store` therefore owns exactly the `flock` and `close`
calls, and the rows reach them by injection, since a real `flock` failure is not producible from a
fixture. All use a **non-agent** review so no run resolution or git precedes the lock and the
failure has one possible source.

**The body-passthrough row must raise an `OSError`, not an `IngestError`.** Revision 34's version
asserted that step 7's duplicate refusal survives a widened `try` — but the widening under test is
of an `OSError`/`PathSafetyError` catch, and `IngestError` is a `ValueError`, so no widening of the
clause in question could ever have caught it. The row asserts that a sentinel `OSError(EIO)` raised
inside the `with` body propagates as itself: an `OSError` that is neither `FileNotFoundError` nor
`PathSafetyError`, so it is not intercepted by `case_store`'s pre-existing clauses on the way out.

**And the ordering row needed a fixture that can see the order at all.** Against an unreachable
repository the checker *returns* `unwired` rather than raising, so cross-checks-first and
checker-first both end in the same `IngestError`. The row therefore specifies an exposure whose
replay raises `ServeError` — which §5.2 propagates rather than converting — so the correct order
refuses on identity and the inverted one dies of the `ServeError` first.

**The lazy-fetch row has three ways to go wrong, and the third is the interesting one.**

1. `uploadpack.allowFilter` defaults to **false**: a `--filter=tree:0` clone from a serving
   repository without it comes back *complete*, so the mutation has nothing to expose and the test
   passes against the defect. Set it on the serving side, and assert the filter actually took before
   serving anything.
2. The promisor remote must still hold the objects and be reachable — point it at a `file://` path
   that exists. With the remote gone, both the pinned and unpinned runs fail, and the pair proves
   nothing. The row tests *whether git goes and gets it*, not whether the request errors.
3. **The precondition in (1) must not be built out of the thing being mutated.** Every obvious way to
   ask "is this tree absent?" is itself a lazy-fetch trigger. Measured, git 2.55, fresh
   `--filter=tree:0` clone: unpinned `git cat-file -e <tree>` **exits 0 and spawns a fetch**, and
   unpinned `git rev-parse 'HEAD~1^{tree}'` inside the clone spawns one too. So a fixture that
   derives the OID in the partial clone, or checks absence through `run_git`, does not merely
   misreport under the mutation — **it fetches the object in and destroys the condition it was
   establishing.** The mutation then fails during setup, and a row that dies in setup certifies
   nothing about serving, which is the whole point of the pair.

   Derive the tree OID from the **source** repository, and run the absence check with a *test-owned,
   explicit* `GIT_NO_LAZY_FETCH=1` rather than through `run_git` or the ambient environment. The
   precondition must hold on a tree where the production pin has been deleted; if it borrows that
   pin, it is not a precondition.

**This is the FIFO/`ENXIO` lesson in a new costume** (§7's standing rule, and the reason the
maximal-mutation probe exists): a parametrization that measures the environment rather than the
guard. There the kernel refused the open before `S_ISREG` was ever consulted; here git satisfies the
precondition by fetching before serving is ever reached. **Ask of every fixture: which line does the
mutation break first?** If the answer is a setup line, the row is not testing what its name says.

**The two `.git/shallow` rows are not redundant, and the first is the one that carries the
guarantee.** Dropping the env pin leaves the open-time check green — the run opens against a clean
repository, exactly as intended — and the defect appears only once an actor writes `.git/shallow`
after opening. A fixture that checks shallowness at open and never mutates it certifies neither row.
Write the mutation as: serve one `history` request, write `.git/shallow`, serve the identical
request, compare.

**The two `--is-shallow-repository` rows are also a pair, and they stand for the two ways revision 27
nearly wrote the diagnostic.** Through hardened `run_git` the proxy is constant-`true` and refuses
every brokered run — caught by the complete-repository row alone. Given its own environment with the
pin omitted it works for genuine shallow clones but also answers `true` to a planted `.git/shallow`,
letting an actor refuse its own run's open — caught by the planted row alone. Note what neither row
is: dropping `GIT_SHALLOW_FILE` does **not** change `history_traversal_error`'s answer in either
fixture (measured — unpinned, a planted graft makes `rev-list --count` stop early at exit 0, so there
is still no error), so no row may claim it does.

**The first 4c row is a different kind of pair and must not be graded like the others.** Identity is
prevented structurally, not checked, so on the fixed tree there is no behaviour to negative-test —
the `human`-labelled-agent bypass cannot be expressed. The test is therefore that *constructing* the
bad submission fails, and the mutation is re-opening the field. A reviewer looking for a
behavioural test here will not find one, and should not read its absence as a gap: it is what §4.2
means by "not a field a producer may leave blank, a field it cannot express."

**The `Full`-supersedes-`Lines` row is the one to distrust**, and its fixture is specified here rather
than left to an implementer: it needs a single exposure in which one path is **both read and
searched**. Against a fixture where every path is read or searched but never both, the mutation stays
green and the row certifies nothing — the precise shape of the vacuous parametrizations found in
plan 2.

## 8. Consequences

**Gained.** An agent review's citations become checkable against what the agent was shown, at line
granularity. An agent confirmation that cited nothing, or whose citations could not be checked, stops
counting as support — and, from revision 34, is *reported* rather than merely subtracted, so the gap
between a review list and a confirmation count always has a written reason. The toolkit's first enforced budget, its first review-append boundary, and its
first addressable control plane. Instrument identity as a run-record term. A per-judgement
uncertainty channel. A run record that is a complete, self-sufficient account of what its agents were
shown. `unwired` extended from instruments to agent testimony.

**Costs.** A model migration that must land with its consumers. A probe of `git grep` and `git log`
owed to `autonomy/git.py` before either op ships. A mutually-exclusive flag pair on each of
`science autonomy start` and `finish`. Roughly one git call per journal entry at ingestion, memoised.
A new package to maintain. An agent producer must put prose in `note` rather than in `evidence` for
its reviews to count — a real constraint on 2c, and the one place this design dictates something about
a schema it does not own. Served evidence accumulates under the control plane rather than in the tree,
so run directories grow with what was read and have no retention rule yet.

**Deliberately not addressed.** Whether a supplied deny policy is complete; whether a non-brokered
agent should be permitted at all (it is, at zero support rather than at full support); mechanically
citable search and history misses, which need an `Evidence` variant this design declines to add
speculatively; an authentic journal against a same-uid adversary, which the threat model excludes and
which the in-process session mode sidesteps rather than solves; token and wall-clock caps, which
remain deferred.
