# Evidence broker — design (autonomous-audit Spec 2a)

**Status:** partially implemented (revision 23)
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
| Plan 4a | serving hardening — §3.1's NFC tree rule and the shallow refusal, both at `start_run`; §3.2's payload bound and the `run_git` ceiling; the protocol bump | designed at revision 23, not implemented |
| Plan 4b | the checker — the hit parser, §5.1, §5.2, §5.3, and `Correspondence` itself | designed at revision 23, not implemented |
| Plan 4c | the boundary — §4.2's `ReviewAttestation` and stored-`Review` invariants, `ReviewSubmission`, §5.4's `append_review`, §4.2.1 eligibility | designed at revision 23, not implemented |

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

§2.2 also pins the three mechanisms 4a must ship *for* 4b — `is_shallow`, the `run_git` ceiling, the
byte bounds — so they are consumed rather than written twice with two spellings, and states the one
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

Direction 3 is the one that decides the design. It involves no collision, no deny prefix and no
search — one NFD path anywhere in the tree is enough — so no filter on the serving side reaches it.
**The session therefore refuses at open any pinned tree holding a path that is not valid UTF-8 or not
already NFC**, verified by one `git ls-tree -r -z --name-only` pass. All three directions become
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
| **Spec 2a** | **the evidence broker — what an agent was shown, recorded and replayable; the addressable control plane** | **this document — plans 1–3 merged, 4a/4b designed at revision 17** |
| Spec 2b | the dispatch harness — who spawns reviewers, how many run at once (formerly sub-project B) | not designed |
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
    audit/record.py      + Uncertainty, ReviewAttestation, ReviewSubmission; two Review fields
                           (one importing Correspondence from science_model/correspondence.py);
                           confirmation_count() gains a correspondence term

science/src/science_tool/
    autonomy/baseline.py    + EvidenceSession on RunBaseline; journal path containment-checked
    autonomy/control_plane.py  # NEW — the project-and-run-keyed canonical root
    autonomy/git.py         + a probed, canonical invocation for `grep` and `log`
    autonomy/lifecycle.py   start_run opens the session; finish_run seals it
    findings/reviews.py     # NEW — the trusted review-append boundary
    validate/checks/        review.correspondence-unwired, info severity
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
| **May NOT assume** | that any checker exists | that a stored `Review` has `evidence` — it does not until 4c | that any exposure predates 4a |
| **Creates** | — | `evidence_broker/hits.py`, `evidence_broker/correspondence.py`, `science_model/correspondence.py` | `findings/reviews.py`, `validate/checks/review_correspondence.py` |
| **Modifies** | `autonomy/lifecycle.py` (tree scan + shallow check, at `start_run`), `evidence_broker/serve.py`, `autonomy/git.py`, `science_model/evidence_broker.py` (bounds + protocol) | — | `science_model/audit/record.py`, `validate/checks/__init__.py` (register the new check), `findings/cli.py:317` |
| **Must not touch** | `science_model/audit/*` | **any stored-record model** — `audit/record.py` above all | `evidence_broker/serve.py` |
| **Owns in §5.3** | — | the classification column | "Stored?" and "Counts as support?" |

**The guarantee 4a hands forward, stated as one sentence because 4b is entitled to rely on all of
it:** every exposure sealed at `REPLAY_PROTOCOL_VERSION = 2` was served from a **complete** clone of
a tree whose every path is valid UTF-8 and already NFC, under a per-request byte ceiling.

Revision 22 phrased the last clause as "no `history` **entry** originating in a shallow repository",
which was false: revision 18 journaled shallow-history refusals, so such entries existed — refused,
but present and replayed. The guarantee is about the *run*, not about which entries it contains, and
saying it the other way invited a 4b implementer to trust something 4a was not delivering.

That is what licenses 4b to key its served map on the decoded path without re-normalising, and to
perform no tree scan of its own (§5.2). A 4b implementer who adds a normalisation guard "to be safe"
is not adding safety — they are adding a second place for the rule to be stated and a second place
for it to drift.

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

- **`autonomy/git.py::is_shallow(repo) -> bool`** — 4a refuses to open a run, 4b classifies a replay
  environment. Revision 22 declared it shared without naming a module, which is how one mechanism
  becomes two functions.
- The `run_git` output ceiling, including its refuse-not-truncate discipline.
- `MAX_SERVED_BYTES` and `MAX_RUN_SERVED_BYTES`, in `science_model/evidence_broker.py` with the
  other bounds.

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

  **A brokered run refuses to open against a pinned tree containing a path that is not valid UTF-8 or
  not already NFC**, established by one `git ls-tree -r -z --name-only` pass at the pinned commit, in
  `autonomy/lifecycle.py::start_run` — the same place that creates the journal and seals the session,
  and the only one that sees the commit before any request exists (§2.2). UTF-8
  travels with NFC in the same check because a path that does not decode cannot be spelled as a
  `LocationEvidence.path` either, so it can never be cited honestly and refusing it is the same rule
  in the same place. `serve` is unchanged: with the tree guaranteed NFC, git's own pathspec matching
  is byte-exact against the only spelling the model can produce.

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
completeness is what remains. The rule:

- **A brokered run refuses to open against a shallow repository**, decided by
  `autonomy/git.py::is_shallow` (`git rev-parse --is-shallow-repository`), in `start_run` beside the
  §3.1 tree scan. Revision 18 made this a per-request refusal that spent a round and was journaled;
  revision 23 moves it to open, because a journaled refusal is **not deterministic given the pinned
  commit** — it is determined by what the clone happens to hold. Replaying that honest exposure in a
  *complete* clone re-serves real history, the outcome no longer matches, and §5.3 returns
  `EXPOSURE_UNREPRODUCIBLE`: the reciprocal of the case revision 18 set out to fix, created by its
  own fix. Refusing at open removes both directions at once and needs no sealed term to tell them
  apart.
- **At replay, a shallow repository is `unwired` / `EXPOSURE_UNREACHABLE`, never `violated`.** The
  environment could not answer the question; it did not answer it wrongly. Reaching for `violated`
  here would be the could-not-check / checked-and-found-false confusion §5.3 exists to prevent, and
  it would refuse reviews for the property of the machine replaying them.

**This reasoning does NOT extend to a git version or runtime whose output differs, and revision 18
wrote that it did** (corrected at revision 20). Shallowness is checkable: `--is-shallow-repository`
answers it before replay, so the cause is known and `unwired` is a conclusion the checker can reach.
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
| all three | `LC_ALL=C`, `LANG=C` in the child environment |

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
class Uncertainty(_Base):
    field: AuthoredHashComponent
    what: AuthoredProvenance
    why: AuthoredProvenance

class Correspondence(_Base):
    status: Literal["verified", "violated", "unwired"]
    code: str | None = None      # required when unwired
    reason: str | None = None

class ReviewAttestation(_Base):
    """Who is reviewing, asserted by the caller that KNOWS — never by the reviewer.
    The exact counterpart of `IngestionProvenance` at `ingest_report`."""
    reviewer_kind: ReviewerKind
    reviewer_ref: ...
    lens: ...
    model: ...
    run_ref: ...

class ReviewSubmission(_Base):
    """What a producer offers: its FINDINGS, and nothing about its own identity.
    Carries no correspondence field and no identity field — not fields a producer
    may leave blank, fields it cannot express."""
    outcome: ...
    note: ...
    evidence: tuple[Evidence, ...] = ()
    uncertainty: tuple[Uncertainty, ...] = ()

# Review — the STORED shape
    evidence: tuple[Evidence, ...] = ()      # existing discriminated union
    uncertainty: tuple[Uncertainty, ...] = ()
    correspondence: Correspondence | None = None
```

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
def confirmation_count(self) -> int:
    """Distinct confirming reviews that COUNT AS SUPPORT.

    An agent confirmation counts only when EVERYTHING it cited was mechanically
    checkable and was checked against what the agent was shown. `unwired` is not
    a weaker `verified`: a guard that cannot see must not report clean, and free
    support is what it would be. A vacuous `verified` -- a review that cited no
    path at all -- is not evidence of anything either. Prose belongs in `note`,
    which every review already has, and costs nothing there.
    """
    return len({
        r.review_id for r in self.reviews
        if r.outcome == "confirms" and (
            r.reviewer_kind != "agent"
            or (r.correspondence is not None
                and r.correspondence.status == "verified"
                and r.evidence
                and all(e.type == "location" for e in r.evidence))
        )
    })
```

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

Records are LF-delimited, and matched content cannot contain LF because a matched line ends at one.

**Two definitions this section left implicit, which is where off-by-one defects live.** `line_count`
is the number of LF-terminated lines plus one if any bytes follow the final LF; an empty payload is
`line_count = 0`, so every line citation into an empty file fails rather than passing by vacuity. And
`ABSENT` is the strongest claim the table can express — it is what certifies "this file does not
exist at this commit" — which is why §3.1's NFC rule has to hold for it to mean anything at all.

**`Coverage` is a `science_tool`-local sum type, not a sealed model** — `Full(line_count)`,
`Lines(numbers)`, `PathOnly`, `Absent`. It is derived at check time from a replayed exposure and
never stored, so putting it in `science_model` beside the sealed types would advertise a durability
it does not have. `Correspondence`, which *is* returned across the boundary, ships in its **own
dependency-neutral module**, `science_model/correspondence.py`, importing pydantic and nothing else.

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

A span cites every line it covers, so a ten-line span against a one-line grep hit does not correspond.
That is strict on purpose: a reviewer wanting to cite a span should read the file. The line-count check
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

Inline entries are not in the tree and cannot be re-served; they are checked against
**`exposure.inline`** — the sealed copy of the manifest, not the baseline's. The baseline is where the
manifest is *declared* (§4.3) and the exposure is where it is *sealed* (§4.1); replay reads the sealed
copy, and reaches for no control-plane file at all.

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
| Repo or commit unavailable; replay cannot run | `unwired` / `EXPOSURE_UNREACHABLE` | yes | **no** |
| Exposure sealed under a different replay protocol | `unwired` / `REPLAY_PROTOCOL_MISMATCH` | yes | **no** |
| Replay ran; an entry did not reproduce | `violated` / `EXPOSURE_UNREPRODUCIBLE` | **refused** | — |
| Replay ran; a citation was never served, or cites unserved lines | `violated` / `CITATION_UNSERVED` | **refused** | — |
| Replay ran; everything corresponded | `verified` | yes | yes |

**The rows are ordered, and the order is load-bearing.** The three `unwired` conditions are decided
first, before any git call — a protocol mismatch in particular short-circuits, since re-serving under
a protocol whose meaning has changed produces bytes that answer no question. Then **replay integrity
is checked in full, and any entry that fails to reproduce short-circuits to
`EXPOSURE_UNREPRODUCIBLE`; citations are never evaluated.** A served map built from entries that did
not reproduce is not a map of anything, so reporting `CITATION_UNSERVED` off it would name a symptom
as the cause and point an operator at the reviewer instead of at the record. Only against a fully
reproduced exposure are citations checked.

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
    project_root, finding_id, submission: ReviewSubmission,
    *, attestation: ReviewAttestation, actor: str,
) -> Review
```

`actor` is the writer of the record — the same nonblank, NUL-free string `ingest_report` demands —
and is not a reviewer identity. `attestation` is the reviewer identity, and is the *only* source of
one: revisions 1–17 conflated the two into a single unexplained parameter.

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

Plus two backstops:

- The model invariant in §4.2, so a write path that bypasses this function still cannot store `violated`.
- A non-gating `validate` check, `review.correspondence-unwired` at info severity, so unbrokered agent
  reviews are visible in aggregate. The difference between a known weaker standing and a silent one.

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
  `instrument` rejected; `unwired` without a code rejected.
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
  inline target absent from the baseline manifest does not correspond; a policy narrowed between
  serving and replay does not silently re-serve denied hits; the vacuous `verified`.
- **`append_review`** — a human review is stored with no control-plane directory existing at all; the
  same for `deterministic`; an agent review whose run record carries **no exposure** yields
  `unwired`, not a crash. Plus attestation (revision 18): a submission cannot express a
  `reviewer_kind` at all, so the `human`-labelled-agent bypass is unconstructible; an attested agent
  whose `reviewer_ref` or `model` disagrees with the run record is an `IngestError`; the same for a
  `lens` that is not `exposure.instrument.ref`; and two submissions under one run cannot mint two
  `review_id`s, because every field the id hashes is attested rather than supplied.
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
| 4a | Drop the shallow check at open | a brokered run against a shallow clone opens |
| 4a | Journal a shallow-`history` refusal instead of refusing at open | an exposure sealed in a shallow clone and replayed in a complete one is not `EXPOSURE_UNREPRODUCIBLE` |
| 4b | Import `Correspondence` from `evidence_broker.py` | `import science_model.audit.record` raises `ImportError` |
| 4a | Check the payload cap after `communicate()` | an oversized `search` refuses without first buffering the output |
| 4a | Remove the `read` size pre-check | an oversized blob refuses without being read |
| 4a | Bound stdout only | an oversized `stderr` refuses |
| 4a | Exempt the `config --list` preflight | a repository whose `include.path` yields an oversized listing refuses |
| 4a | Exempt the tree scan | an oversized `ls-tree` refuses instead of declaring the tree NFC |
| 4a | Truncate instead of refusing at the ceiling | an over-ceiling config listing does not silently under-blank filter drivers |
| 4a | Journal a `stderr` or preflight overflow as a `Denial` | an entry served before `.git/config` grew still replays, rather than becoming `EXPOSURE_UNREPRODUCIBLE` |
| 4a | Make a tree-scan overflow a `Denial` instead of refusing to open | an oversized tree opens no session |
| 4b | Let `REFUSED` contribute `Full(0)` | a citation to a policy-denied path is refused |
| 4b | Drop `Full` superseding `Lines` | a path both read and searched admits a line outside the hits |
| 4b | `split(b"\0")` without `maxsplit=2` | a binary hit whose matched content holds a NUL parses |
| 4b | Drop the trailing-bytes clause in `line_count` | a citation to the last line of a file with no final newline |
| 4b | Permit `pointer` under `Lines` | a pointer citation on a search-only path is refused |
| 4b | Ignore `replay_protocol` | a v1 exposure yields `unwired`, not a verdict |
| 4b | Make a span cite only its endpoints | a ten-line span against a one-line hit is refused |
| 4b | Evaluate citations before replay integrity | an unreproducible exposure reports `EXPOSURE_UNREPRODUCIBLE`, not `CITATION_UNSERVED` |
| 4b | Drop the shallow check at replay | a `history` exposure replayed in a `--depth 1` clone yields `unwired`, not `violated` |
| 4b | Memoise replay across exposures | two exposures differing only in `surface_policy` do not share a cached payload |
| 4c | Re-add `reviewer_kind` to `ReviewSubmission` and branch on it | constructing a submission carrying `reviewer_kind` raises |
| 4c | Skip the agent cross-check against the run record | an attested agent whose `model` disagrees with its run record is stored |
| 4c | Skip the lens cross-check | an attested `lens` that is not `exposure.instrument.ref` is stored |
| 4c | Apply the lens cross-check unconditionally | an agent review whose run has **no** exposure stores as `unwired`, not `IngestError` |

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
counting as support. The toolkit's first enforced budget, its first review-append boundary, and its
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
