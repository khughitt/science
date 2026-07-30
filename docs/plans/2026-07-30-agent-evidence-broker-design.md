# Evidence broker — design (autonomous-audit Spec 2a)

**Status:** proposed (revision 8)
**Spec 2a** of the autonomous-audit program (§0). It is independently landable and useful without
the slices that follow it.

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

Four patterns run through what review kept finding, and each predicts where the implementation will go
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
| **Spec 2a** | **the evidence broker — what an agent was shown, recorded and replayable; the addressable control plane** | **this document** |
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
    correspond.py the join, the replay, the coverage-aware outcome
    cli.py        `science evidence open | serve | show`

science/model/src/science_model/
    autonomous_runs.py   + ExposureEntry, InstrumentIdentity, InlineInput, EvidenceExposure
    audit/record.py      + Uncertainty, Correspondence, ReviewSubmission; two Review fields;
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

## 3. The broker

### 3.1 Policy

```python
def authorize(request: EvidenceRequest, policy: SurfacePolicy) -> Denial | None
```

Containment is checked **before** any prefix, because a prefix check alone is walked around with `..`.

**A git path is normalized lexically and the filesystem is never consulted.** Revisions 1–4 borrowed
`reject_baseline_inside_project`'s dual as-spelled/resolved idiom wholesale, which is the wrong tool
here: it follows symlinks in the mutable working tree, while the served surface is
`git show <commit>:<path>` — a blob read that never touches the working tree at all. Replacing a
base-commit file with a working-tree symlink would therefore deny a request that was entirely safe,
and resolving would buy no security in exchange, because there is no filesystem lookup to protect.

`normalize_project_path` is already the right function and is already what `LocationEvidence` uses:
it refuses `..` rather than collapsing it, refuses absolute paths, refuses NUL, and normalizes UTF-8.
Deny prefixes are then matched against the normalized form.

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

Three operations, all resolved at a pinned commit: `read` (`git show <commit>:<path>`), `search`
(`git grep`), `history` (`git log`). Reads go through the commit rather than the filesystem so the
surface is the frozen tree even when the working tree has moved on.

**`verify_commit()` runs once before any request is served, and the ordering is load-bearing.** For a
well-formed but nonexistent commit, git reports `path 'x' exists on disk, but not in '<commit>'` —
the same sentence it emits for a path added after the pinned commit. Miss classification is sound
only once the revision is known good.

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

**`literal` is load-bearing, not decoration.** `normalize_project_path` refuses `..`, absolute paths
and NUL, and permits everything else — including `*`, `?` and `[]`, which are ordinary characters in a
filename and wildmatch syntax in a pathspec. A directory literally named `private/[drafts]` is denied
by `read`, where the prefix is compared as text, and *not* excluded by a bare
`:(exclude)private/[drafts]`, where `[drafts]` is a character class matching one letter. The deny
policy would then hold on one operation and leak on the other, silently, for exactly the paths whose
names happen to contain punctuation. `literal` disables wildmatch; `top` anchors to the repository root
so the exclusion does not drift with the caller's pathspec.

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
`show <commit>:<path>`, `diff --raw`, `diff --name-status` — under the stated discipline that "only
what was shown to execute is neutralized". **`grep` is not in that set.** 2a therefore owes that module
the same treatment it gave the others before adding a subcommand to it:

- **Probe `grep`** for config keys that cause execution, in a scratch repository, under exactly the
  argv the broker will use. `--textconv` is off by default; the probe establishes whether anything
  reaches a driver anyway rather than assuming it does not.
- **Probe `log`** for the keys that were not exercised by the existing `log` call site. `log.showSignature`
  spawns gpg, which the current probe list does not mention.

Whatever executes is neutralised by `-c` in `_HARDENING`; whatever only *shapes output* is pinned in
the argv the broker builds, so that determinism does not depend on a config file at all:

| Op | Pinned |
|---|---|
| `grep` | pattern type passed explicitly, never inherited; `--no-color`; `-n`; `-z` with `core.quotePath=false` for stable path encoding; `--no-recurse-submodules` |
| `log` | explicit `--pretty=format:` with `%H`/`%aI`; `--no-decorate`; `--no-notes`; `--no-abbrev-commit`; `log.showSignature=false` |
| `show <commit>:<path>` | nothing further — a blob read, already covered by `git.py`'s existing analysis |
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

**Argv is not the whole invocation; the environment is part of it.** `run_git` passes no `env` today,
so git inherits the supervisor's locale, and a POSIX class such as `[[:alpha:]]` matches a different
character set under `C` than under a UTF-8 locale. Two honest replays of the same pattern against the
same commit then disagree, and §5.3 refuses on disagreement. Pinning `LC_ALL` and `LANG` is what makes
"deterministic given the commit" true of a regex engine rather than only of a file.

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
 "commit": "...", "sha256": "...", "outcome": "served"}   // served | miss | denied | invalid
```

Revision 2 counted raw lines to derive spend, which cannot express the budget it claimed to enforce:
inline seeds are lines but not requests, so seeding charged the reviewer for evidence it never asked
for, and a denial is a request that produced no served response. `requests_used` counts `request`
events; `inline` events are the supervisor's own seeding and cost nothing.

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
- **Open.** `science evidence open` creates the journal exclusively, for the same reason
  `write_baseline` does: reusing a journal path discards the exposure record of whatever run already
  owns it.

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
- **Seal.** `finish_run` reads the journal, replays it, and copies it into the run record as
  `EvidenceExposure`. After sealing, the record is self-sufficient (§4.1): re-checking needs the record
  and a repository. The journal is retained as the supervisor's own copy of what it served, not as an
  input anything later depends on.

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
def control_plane_root() -> Path                        # $SCIENCE_CONTROL_PLANE, else the XDG state dir
def project_key(project_root: Path) -> str              # sha256(resolved root)[:16] — digest ONLY
def run_dir(project_root: Path, run_id: str) -> Path    # <root>/<project-key>/<run-slug>/
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
necessarily read.

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

`control_plane_root()` is still put through `reject_baseline_inside_project`, so an environment
variable cannot relocate the control plane into the tree the actor writes.

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

## 4. Model changes

### 4.1 Run record

```python
class ExposureEntry(_Frozen):
    op: Literal["read", "search", "history", "inline"]
    target: str
    pathspec: str | None = None
    commit: str
    sha256: str

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

class ReviewSubmission(_Base):
    """What a producer offers. Carries NO correspondence field — not a field a
    producer may leave blank, a field it cannot express."""
    reviewer_kind: ReviewerKind
    reviewer_ref: ...
    lens: ...
    model: ...
    run_ref: ...
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

`Correspondence` mirrors `InstrumentResult`'s invariant — `unwired` requires a machine-readable code
— so both ways this toolkit says "could not run" have one shape.

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

**This is the fix for inline evidence bypassing replay.** Revision 1 had inline entries contributing
trusted correspondence targets on the strength of a hash in the journal — the same journal it argued
was forgeable, which is why every other entry is replayed. Declaring them in the baseline moves them
into the control plane: the supervisor writes the manifest when it composes the prompt, exclusive-create
and outside the tree, and an inline entry corresponds only if its target is in that manifest *and* the
journal's `sha256` matches the manifest's.

`lines` is carried so a line or span citation into an inline input can be checked the same way as one
into a read file. Inline bytes are not in the tree, so a line count cannot be re-derived later.

`surface_policy` is here for the reason given in §3.1: the deny prefixes are `:(exclude)` pathspecs on
every search, so they are part of the query, and a query whose text is not fixed does not replay.
Naming it `surface_policy` rather than reusing `policy_identity` is deliberate — that field is the
autonomy write-surface policy, a different thing about a different boundary, and one field standing
for two policies is how they end up enforced as one.

`journal_path` is containment-checked by `reject_baseline_inside_project`, like the baseline itself,
and under `--broker-spec` it is derived from `control_plane.run_dir()` rather than supplied at all.

## 5. Correspondence

```python
def check_correspondence(review, exposure, *, repo) -> Correspondence
```

The live session is gone from the signature: everything replay needs is sealed into `exposure`.

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

`git grep -n <pattern> <commit>` prefixes every hit with `<commit>:<path>:<line>:`, so the matched
lines are recoverable from the served bytes — which is a second reason replay is not optional, since
the journal stores only a hash of them. Where a path is both read and searched, `FULL` supersedes
`LINES`.

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

Every non-inline entry is re-served at the pinned commit and must reproduce its recorded `sha256`.
When the broker writes the journal it is trustworthy by construction, but a record read back off disk
was written by whatever wrote that file, and a `sha256` field is as forgeable as the rest of the JSON.
Determinism comes from the pin **and** the canonical invocation in §3.2.1.

Inline entries are not in the tree and cannot be re-served; they are checked against
**`exposure.inline`** — the sealed copy of the manifest, not the baseline's. The baseline is where the
manifest is *declared* (§4.3) and the exposure is where it is *sealed* (§4.1); replay reads the sealed
copy, and reaches for no control-plane file at all.

Memoised on `(commit, op, target, pathspec)` within an ingestion run; reviews of sibling documents
read many of the same files.

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

The exposure checked is the one belonging to `review.run_ref`, resolved by `append_review` from that
run's record and baseline. A review checked against some other run's exposure is checked against
nothing.

### 5.3 Outcomes

| Situation | Status / code | Stored? | Counts as support? |
|---|---|---|---|
| No exposure log | `unwired` / `NO_EXPOSURE` | yes | **no** |
| Repo or commit unavailable; replay cannot run | `unwired` / `EXPOSURE_UNREACHABLE` | yes | **no** |
| Exposure sealed under a different replay protocol | `unwired` / `REPLAY_PROTOCOL_MISMATCH` | yes | **no** |
| Replay ran; an entry did not reproduce | `violated` / `EXPOSURE_UNREPRODUCIBLE` | **refused** | — |
| Replay ran; a citation was never served, or cites unserved lines | `violated` / `CITATION_UNSERVED` | **refused** | — |
| Replay ran; everything corresponded | `verified` | yes | yes |

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
def append_review(project_root, finding_id, submission: ReviewSubmission, *, actor) -> Review
```

- **Branches on `reviewer_kind`.** Only an agent submission resolves a run record and runs
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
- **Pathspec translation** — a directory literally named `private/[drafts]` is excluded from search, not
  interpreted as a character class; `private` denies `private/x` and does not deny `privateer/x`; and
  the `read` denial and the `search` exclusion are asserted to **agree** on the same table of inputs,
  because two mechanisms for one policy is how a policy comes to be half enforced.
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
  emptied, since nothing trusted reads it.
- **`session.py`** — a denial spends a round; exhaustion refuses without further spend; no unbudgeted
  path to `serve` is exported; `--session` cannot override the baseline's journal path, budget, or
  surface policy; `open` on an existing journal refuses; **seeding N inline inputs leaves
  `requests_used` at zero**; a denied request and a malformed pattern each raise it by one.
- **`control_plane.py`** — `run_dir` is a pure function of `(project root, run id)`; **two projects
  producing the same run slug get different directories**, and a fork of a project does not resolve its
  parent's; **a `science.yaml` name containing `/` or `..`, or one 4096 characters long, changes no
  path** — asserted directly, since that is the vector the digest-only key exists to close;
  `--broker-spec` and `--baseline-out` together are refused, as are `--session` and `--baseline` on
  `finish`; a brokered run whose baseline is elsewhere is refused rather than searched for; a
  control-plane root inside the project is refused.
- **Sealing** — a sealed run replays from `(record, repo)` alone with the control-plane directory
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
- **`append_review`** — a human submission is stored without a baseline existing at all; the same for
  `deterministic`; an agent submission whose run has no baseline yields `unwired`, not a crash.
- **Derived guard** — no path reaches git without passing `authorize`, asserted by walking the
  dispatch in `serve.py`. Same spirit as `tests/test_instrument_boundary.py`: derived from the code,
  not a list someone maintains.
- **Integration** — end-to-end against a real temporary git repository: open, serve, seal, append.

**Every guard is proven by restoring the prior behaviour and confirming its test fails.** Each defect
closed downstream survived a green suite until it was negative-tested, and four of the six defects in
revision 1 of this document were guards that looked right on the page. A guard nobody has watched fail
is a guard nobody has tested.

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
