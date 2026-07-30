# Agent evidence broker — design

**Status:** proposed
**Sub-project A** of three. B is the multi-assignment dispatch harness; C is
`/science:review-plans`, the LLM plan-adjudication layer this toolkit's drift-screen design
defers to and never built. A is independently landable and useful without either.

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

This design closes it: evidence an agent sees is **served and recorded** rather than taken, and a
citation that does not correspond to what was served is refused.

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
    correspond.py the join, the replay, the three-way outcome
    cli.py        `science evidence open | serve | show`

science/model/src/science_model/
    autonomous_runs.py   + ExposureEntry, InstrumentIdentity, EvidenceExposure
    audit/record.py      + Uncertainty, Correspondence; three Review fields

science/src/science_tool/
    autonomy/lifecycle.py   start_run records the journal path; finish_run seals it
    findings/ingest.py      correspondence enforced beside _assert_attested_provenance
    validate/checks/        review.correspondence-unwired, info severity
```

`serve.py` uses `autonomy/git.py`, the existing hardened runner that neutralises `core.fsmonitor`,
`core.hooksPath`, and configured `filter.*` drivers. Those config keys name programs git executes; a
broker shelling bare `subprocess.run(["git", ...])` into a repository someone else can write inherits
that hole.

The package is named for the generic property — evidence is brokered — not for the study-specific use
(blinding a reviewer to a comparison group).

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

**A malformed search pattern is a third case**: it is the requester's own input, carries no
repository fact, and is refused as retryable rather than treated as instrument failure.

**Every search carries the policy's prefixes as `:(exclude)` pathspecs**, whether or not the caller
supplied a pathspec of its own. Search is the one operation that never names a path, so denying a
directory to `read` while `git grep` returns hits from inside it denies nothing.

### 3.3 Journal

Append-only, one line per served response: `{op, target, pathspec, commit, sha256, outcome}`. It
lives **outside the project tree**, for the reason `RunBaseline` does: a log inside the tree the
actor can write is not a record of what the actor was shown.

It cannot live in the run record, because that record deliberately has no in-flight shape — "a
supervisor that dies mid-run leaves no record, so its branch reads as unattested rather than clean".

### 3.4 Session

The session owns the round counter and the journal. **Every request that reaches it spends a round,
including denials and invalid patterns.** Free denials make probing the deny policy unlimited, and a
spent round is also what makes two runs comparable.

State that bounds a requester cannot live in the requester. A budget constant beside a stateless
serve function documents a budget without imposing one.

The session seeds the journal with inputs the opening prompt already supplied, marked `inline` and
audited by hash rather than against the surface policy. Without seeding, an instrument that
legitimately lives inside a denied prefix can never be accounted for at all.

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
    instrument: InstrumentIdentity | None = None
    entries: tuple[ExposureEntry, ...] = ()

# AutonomousRunRecord
    evidence: EvidenceExposure | None = None
```

Grouped into one optional field because it is all-or-nothing: a run either was brokered or was not,
and one group makes "brokered" a single checkable predicate rather than three fields that can
disagree.

Validators: `requests_used <= budget`; every entry's `commit` equals `EvidenceExposure.commit`, since
a run that read two trees did not have one evidence surface.

**`RunBudget` is untouched.** Its two fields are agent-attested; `requests_used` is parent-derived.
Merging them would blur exactly the distinction that makes `RunBudget` misleading today — it looks
like a cap and is a self-report.

`InstrumentIdentity` closes a gap this toolkit currently has outright: `RunBaseline` binds run, agent,
model, branch, commit and toolkit revision, but not the *instrument*. A judgement scored against a
silently edited rubric is presently undetectable.

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

# Review
    evidence: tuple[Evidence, ...] = ()      # existing discriminated union
    uncertainty: tuple[Uncertainty, ...] = ()
    correspondence: Correspondence | None = None
```

`Correspondence` mirrors `InstrumentResult`'s invariant — `unwired` requires a machine-readable code
— so both ways this toolkit says "could not run" have one shape.

`evidence` is bounded by the existing `MAX_EVIDENCE_ENTRIES`.

**Two invariants, enforced in the model rather than only at a gate:**

1. `_agent_provenance` gains: an agent review **requires** `correspondence`. It may be `unwired`; it
   may not be absent. Absent reads as clean.
2. A stored `Review` may not hold `status="violated"`. Refusal happens at ingestion, and making it a
   model invariant means every other write path inherits it instead of each gate remembering.

`review_id` hashes `(reviewer_kind, reviewer_ref, lens, run_ref, finding_id)`. None of the new fields
enter it, so existing record identities are unchanged.

**Compatibility caveat:** `_Base` is `extra="forbid"`, so old records missing these fields load fine,
but a record written by the new toolkit is rejected by an old one. Runs pin `toolkit_revision`, so
this is contained — but the model change and its consumers must land together.

## 5. Correspondence

```python
def check_correspondence(review, exposure, *, repo) -> Correspondence
```

### 5.1 The served set

`inline`, `read` and `history` entries contribute their `target`. `search` entries contribute the
paths **inside** their served bytes: `git grep -n <pattern> <commit>` prefixes every hit with
`<commit>:<path>:<line>:`, and a search hit is a legitimate way to establish that a file contains a
symbol without reading it.

That set cannot be derived from the journal alone, because the journal stores only a hash of those
bytes. This is why replay is not optional.

Two cases must count as served, or the check punishes correct behaviour: a **search hit**, and a
**defined miss** — a path absent at the commit is frequently the decisive finding, and any rubric
worth using asks for absence to be recorded with the same care as presence.

### 5.2 The replay

Every non-inline entry is re-served at the pinned commit and must reproduce its recorded `sha256`.
When the broker writes the journal it is trustworthy by construction, but a record read back off disk
was written by whatever wrote that file, and a `sha256` field is as forgeable as the rest of the JSON.
Determinism comes free from the pin.

Memoised on `(commit, op, target, pathspec)` within an ingestion run; reviews of sibling documents
read many of the same files.

### 5.3 Outcomes

| Situation | Status / code | Ingestion |
|---|---|---|
| No exposure log | `unwired` / `NO_EXPOSURE` | accept |
| Repo or commit unavailable; replay cannot run | `unwired` / `EXPOSURE_UNREACHABLE` | accept |
| Replay ran; an entry did not reproduce | `violated` / `EXPOSURE_UNREPRODUCIBLE` | **refuse** |
| Replay ran; a citation was never served | `violated` / `CITATION_UNSERVED` | **refuse** |
| Replay ran; everything corresponded | `verified` | accept |

The checker reproduces the distinction it exists to enforce: *could not check* is not *checked and
found false*. A journal that fails to reproduce at a pinned commit is not ambiguous — nothing
legitimate produces that — so it refuses. A journal that cannot be reached genuinely could not be
checked, so it accepts, and says so.

An exposure log with no path-bearing citations is `verified` with a reason: the check ran and found
no violation. A consumer asking whether a review cited anything reads `len(evidence)`. Conflating
that into correspondence would be the empty/unwired confusion one level up.

### 5.4 Enforcement points

- `findings/ingest.py`, beside `_assert_attested_provenance`, which already raises `IngestError` on a
  provenance mismatch. Refusing an unserved citation there is consistent, not novel.
- The model invariant in §4.2, so a write path that bypasses ingestion still cannot store `violated`.
- A non-gating `validate` check, `review.correspondence-unwired` at info severity, so unbrokered
  agent reviews are visible in aggregate. The difference between a known weaker standing and a silent
  one.

## 6. Error handling

| Kind | Behaviour |
|---|---|
| Defined miss | Served as an answer with an explicit marker |
| Policy denial | Refused, policy-supplied notice, spends a round |
| Malformed search pattern | Refused as retryable, spends a round |
| Budget exhausted | Refused, spends nothing further |
| Anything else from git | Raises, halts the run |

**A run record gets `evidence=None` only if a session was never opened.** `start_run` records the
journal path in `RunBaseline`; at `finish_run`, a baseline that says "brokered" plus a missing or
unreadable journal yields `RunDisposition.UNWIRED`, which blocks — rather than writing a record that
reads as unbrokered.

Without this rule, losing a journal silently downgrades every review in that run from `verified` to
`unwired`, and `unwired` accepts. The fail-open returns through the back door.

## 7. Testing

- **`serve.py`** — each operation; an empty file at the commit reads differently from an absent path;
  unrecognised stderr raises rather than answers. Named regression test: **a well-formed but
  nonexistent commit halts rather than answering**, using a genuinely invalid ref — `"0" * 40`
  produces the *miss* message and would let the test pass against broken code.
- **`policy.py`** — containment before prefix; `..` and absolute paths refused; the dual
  as-spelled/resolved check catches a symlink escape.
- **`session.py`** — a denial spends a round; exhaustion refuses without further spend; no unbudgeted
  path to `serve` is exported.
- **Model** — agent review without `correspondence` rejected; `violated` unstorable;
  `requests_used > budget` rejected; entries disagreeing on commit rejected; `unwired` without a code
  rejected.
- **Correspondence** — one test per row of §5.3, plus the search-hit and defined-miss served cases and
  the vacuous `verified`.
- **Derived guard** — no path reaches git without passing `authorize`, asserted by walking the
  dispatch in `serve.py`. Same spirit as `tests/test_instrument_boundary.py`: derived from the code,
  not a list someone maintains.
- **Integration** — end-to-end against a real temporary git repository: open, serve, seal, ingest.

**Every guard is proven by restoring the prior behaviour and confirming its test fails.** Each defect
closed downstream survived a green suite until it was negative-tested. A guard nobody has watched
fail is a guard nobody has tested.

## 8. Consequences

**Gained.** An agent review's citations become checkable against what the agent was shown. The
toolkit's first enforced budget. Instrument identity as a run-record term. A per-judgement
uncertainty channel. `unwired` extended from instruments to agent testimony.

**Costs.** A model migration that must land with its consumers. Roughly one git call per journal entry
at ingestion, memoised. A new package to maintain.

**Deliberately not addressed.** Whether a supplied deny policy is complete; whether a non-brokered
agent should be permitted at all (it is, and its weaker standing is recorded rather than assumed);
token and wall-clock caps, which remain deferred.
