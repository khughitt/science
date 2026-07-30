# Agent evidence broker — design

**Status:** proposed (revision 4)
**Sub-project A** of three. B is the multi-assignment dispatch harness; C is
`/science:review-plans`, the LLM plan-adjudication layer this toolkit's drift-screen design
defers to and never built. A is independently landable and useful without either.

Revisions 2 through 4 respond to design review: six production-boundary defects found in revision 1,
six more in revision 2, six more in revision 3. Each is closed below and named at the point it is
closed, because the reasoning that produced the defect is more useful to a reader than the corrected
text alone.

The pattern in what review kept finding is worth stating, because it predicts where the implementation
will go wrong. Every round, the defects clustered in guards that were **narrower than the rule they
were written to enforce** — `any(location)` where the rule was "everything was checked", `line`/`span`
forbidden where the rule was "cite only what you saw" and `pointer` walked through the gap, a run slug
where the rule needed a project identity. A guard that restates its rule on one axis and leaves the
others open reads, on the page, exactly like a guard that works. That is the argument for §7's
discipline: restore the prior behaviour and watch the test fail, on every axis the rule names.

## 1. The problem

`Review` admits `reviewer_kind="agent"` and carries **no evidence field at all**. An agent's
`confirms` is therefore accepted on its own authority: nothing records what the agent was shown,
nothing checks that what it cited was ever in front of it, and nothing distinguishes "this agent
looked and found nothing" from "this agent could not look". Spec 2 — agent-authored findings — is
modelled but unshipped, so the cost of fixing this is at its minimum right now and rises the moment
a producer exists.

The failure is not hypothetical. In a downstream project a fabricated citation survived four months
and produced a Strong finding, because the chain from claim to source was never mechanically closed.
An agent review is the same chain with a faster writer.

This design closes it: evidence an agent sees is **served and recorded** rather than taken, a
citation that does not correspond to what was served is refused, and an agent confirmation that
could not be checked earns no support.

### Threat model

**A bounds confabulation and drift, not filesystem-level forgery.** The reviewer is treated as
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

An actor with write access to `RunBaseline`'s directory defeats A entirely. That is the same
assumption the autonomy envelope already makes, and A does not weaken it.

### What this design does NOT own

- **The judgement schema.** Lifecycle vocabularies, action verbs, remaining-work structures are C's.
  A knows only that a review cites evidence and may declare uncertainty.
- **Blinding.** `drift_sample/blind.py` redacts authored claims from a document under review. That is
  a property of a study, not of a broker. A serves bytes as they are at the commit.
- **Dispatch.** Who spawns reviewers, and how many run concurrently, is B.
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

### 2.1 There is no review-append path today, so A builds one

**Revision 1 named `findings/ingest.py` as the enforcement point. That was wrong.** `ingest_report()`
consumes an `AuditReport`, whose payload is `findings`, `accepted`, `metrics`, `caveats`, `unwired`,
`totals`, `meta` — no reviews. `AuditFindingRecord.with_review()` has exactly one caller in the
repository and it is a test. Placing correspondence enforcement in ingestion would have gated a door
that does not exist.

A therefore defines the boundary it needs: `findings/reviews.py::append_review()`. It is the only
production writer of a `Review`, it takes the store lock the way `ingest_report` does, and it is where
correspondence is computed. §5.4 specifies it.

## 3. The broker

### 3.1 Policy

```python
def authorize(request: EvidenceRequest, policy: SurfacePolicy) -> Denial | None
```

Containment is checked **before** any prefix, because a prefix check alone is walked around with
`..`. Both the as-spelled and the symlink-resolved path are checked, following
`autonomy/baseline.py::reject_baseline_inside_project`.

`Denial` carries two strings. `reason` is categorised and stays parent-side, for the audit. `notice`
is what the requester sees, and it is **policy-supplied**: this toolkit's existing denials are
deliberately informative because a human triages them, while a blinding study needs them uniform and
information-free, since a specific reason confirms the denied thing exists. A cannot decide which is
correct for a caller, so it does not.

**Deny prefixes are a parameter, not a constant.** A guarantees only that a supplied policy is
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

**Every search carries the policy's prefixes as `:(exclude)` pathspecs**, whether or not the caller
supplied a pathspec of its own. Search is the one operation that never names a path, so denying a
directory to `read` while `git grep` returns hits from inside it denies nothing.

### 3.2.1 Canonical invocation — `grep` and `log` must be probed before they ship

A pinned commit fixes the repository's *content*. It does not fix how git *renders* that content, and
for `grep` it does not even fix what the caller's pattern *means*. `grep.patternType` selects basic,
extended, perl, or fixed matching from repository configuration, so the same pattern against the same
commit is a different query depending on a file the actor owns. Colour, path quoting, line-number
emission, and log formatting are all likewise config-derived. Replay comparing two hashes of
differently-rendered output would refuse an honest run.

`autonomy/git.py` states its probe set explicitly — `rev-parse`, `status --porcelain`, `log`,
`show <commit>:<path>`, `diff --raw`, `diff --name-status` — under the stated discipline that "only
what was shown to execute is neutralized". **`grep` is not in that set.** A therefore owes that module
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
- **Open.** `science evidence open` writes the journal with `O_EXCL` through the anchored-descriptor
  primitives in `findings/paths.py`, for the same reason `write_baseline` uses exclusive creation:
  reusing a journal path discards the exposure record of whatever run already owns it.
- **Append.** One line, `O_APPEND`, under a lock file held for the duration of the serve, so
  concurrent reviewers in one run cannot interleave a partial line. Appends never rewrite.
- **Spend.** `requests_used` is **derived by counting `request` events**, not stored as mutable state.
  There is no counter to reset. Truncating the journal to buy rounds destroys the entries that make
  the truncator's own citations correspond, so the move is self-defeating rather than merely detected.
- **Seal.** `finish_run` reads the journal, replays it, and copies it into the run record as
  `EvidenceExposure`. After sealing, the journal is retained; it is the only thing that can re-check
  a run later.

`Session` is also usable in-process, without the CLI, so B can hold sessions in the supervisor where
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
def project_key(project_root: Path) -> str              # <science.yaml name>-<sha256(resolved root)[:12]>
def run_dir(project_root: Path, run_id: str) -> Path    # <root>/<project-key>/<run-slug>/
#   baseline.json, journal.jsonl
```

**The key is project-scoped, and a run id alone is not a project identity.** A run id is
`<date>-<agent>-<short-id>`; two projects running the same agent role on the same day with the same
disambiguator produce the same slug, and a fork inherits its parent's `science.yaml` name outright. A
single global root would let one project's session resolve another's baseline — and between a fork and
its parent, which share a base commit, the replay would even succeed.

`name` alone therefore cannot carry the scope; the digest of the *resolved* project root does, and
`name` stays in the key so a human listing the control plane can read it. Two worktrees of one project
get two control planes, which is correct: they are two trees at two commits.

Known limitation, stated rather than engineered around: moving a project orphans its **unsealed**
sessions, because the key changes. Sealed runs are unaffected — `EvidenceExposure` is copied into the
run record at `finish`, and the journal is needed only to re-check a run later.

`--baseline-out` and a new `--broker` flag on `science autonomy start` are **mutually exclusive**.
`--broker` derives both paths and refuses an explicit one; without it, nothing changes for runs that
do not broker evidence. No silent fallback: a brokered run whose baseline was written somewhere else
is refused rather than searched for.

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
   so a large file would simply fail to emit. The `--output PATH` escape hatch exists for this.
2. It keeps served evidence out of a conversational parent's context, which is the constraint that
   makes B tractable at all.

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
    entries: tuple[ExposureEntry, ...] = ()

# AutonomousRunRecord
    evidence: EvidenceExposure | None = None
```

Grouped into one optional field because it is all-or-nothing: a run either was brokered or was not,
and one group makes "brokered" a single checkable predicate rather than three fields that can
disagree.

`ExposureEntry` deliberately does **not** store which lines a search matched. Those are re-derived at
replay (§5.1); storing them would be storing the actor's account of its own exposure.

**Validators:**

- `requests_used <= budget`.
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
closes when C ships a producer, which is the argument for landing A first. A record written by the new
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
and under `--broker` it is derived from `control_plane.run_dir()` rather than supplied at all.

## 5. Correspondence

```python
def check_correspondence(review, exposure, session, *, repo) -> Correspondence
```

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
consumer that needs it (C) rather than being speculatively added here.

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

Inline entries are not in the tree and cannot be re-served; they are checked against the baseline
manifest instead (§4.3).

Memoised on `(commit, op, target, pathspec)` within an ingestion run; reviews of sibling documents
read many of the same files.

The exposure checked is the one belonging to `review.run_ref`, resolved by `append_review` from that
run's record and baseline. A review checked against some other run's exposure is checked against
nothing.

### 5.3 Outcomes

| Situation | Status / code | Stored? | Counts as support? |
|---|---|---|---|
| No exposure log | `unwired` / `NO_EXPOSURE` | yes | **no** |
| Repo, commit, or baseline unavailable; replay cannot run | `unwired` / `EXPOSURE_UNREACHABLE` | yes | **no** |
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

- **Branches on `reviewer_kind`.** Only an agent submission resolves a run record and baseline and runs
  `check_correspondence`. Human and deterministic submissions get `correspondence=None` and are stored.
  Revision 3 resolved a baseline for every submission, which would have made the boundary unusable for
  the two reviewer kinds §4.2.1 says are unaffected: a human review's `run_ref` need not name an
  autonomous run at all, and demanding a control-plane baseline for one would refuse every human review
  in the toolkit. Broker the kind that needs brokering.
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
unreadable journal yields `RunDisposition.UNWIRED`, which blocks — rather than writing a record that
reads as unbrokered.

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
- **`policy.py`** — containment before prefix; `..` and absolute paths refused; the dual
  as-spelled/resolved check catches a symlink escape.
- **`session.py`** — a denial spends a round; exhaustion refuses without further spend; no unbudgeted
  path to `serve` is exported; `--session` cannot override the baseline's journal path, budget, or
  surface policy; `open` on an existing journal refuses; **seeding N inline inputs leaves
  `requests_used` at zero**; a denied request and a malformed pattern each raise it by one.
- **`control_plane.py`** — `run_dir` is a pure function of `(project root, run id)`; **two projects
  producing the same run slug get different directories**, and a fork of a project does not resolve its
  parent's; `--broker` and `--baseline-out` together are refused, as are `--session` and `--baseline` on
  `finish`; a brokered run whose baseline is elsewhere is refused rather than searched for; a
  control-plane root inside the project is refused.
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
counting as support. The toolkit's first enforced budget, its first review-append boundary, and its first
first run-id-addressable control plane. Instrument identity as a run-record term. A per-judgement
uncertainty channel. `unwired` extended from instruments to agent testimony.

**Costs.** A model migration that must land with its consumers. A probe of `git grep` and `git log`
owed to `autonomy/git.py` before either op ships. A mutually-exclusive flag pair on each of
`science autonomy start` and `finish`. Roughly one git call per journal entry at ingestion, memoised.
A new package to maintain. An agent producer must put prose in `note` rather than in `evidence` for
its reviews to count — a real constraint on C, and the one place this design dictates something about
a schema it does not own.

**Deliberately not addressed.** Whether a supplied deny policy is complete; whether a non-brokered
agent should be permitted at all (it is, at zero support rather than at full support); mechanically
citable search and history misses, which need an `Evidence` variant this design declines to add
speculatively; an authentic journal against a same-uid adversary, which the threat model excludes and
which the in-process session mode sidesteps rather than solves; token and wall-clock caps, which
remain deferred.
