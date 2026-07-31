# Evidence broker plan 3 — the session and its record

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A brokered run opens with one command, serves under a budget it cannot reset through a
journal outside its own tree, and seals into a run record that replays from `(record, repo)` alone.

**Architecture:** One model module gains the sealed vocabulary (`Outcome` moves here from
`serve.py`, plus the exposure, the session, and the supervisor's spec). Two new tool modules —
`evidence_broker/journal.py` (exclusive create, `O_APPEND` under a lock, parse) and
`evidence_broker/session.py` (the budget, the round, `served/<sha256>`) — sit between plan 2's
stateless `serve` and the run lifecycle. `autonomy/lifecycle.py` gains one input at `start` and one
output at `finish`; `evidence/cli.py` gives the actor exactly one command.

**Tech Stack:** Python 3.12+, Pydantic v2 (`science-model`), `click`, `pytest`. No new dependencies.

## Provenance

Implements Spec 2a of the autonomous-audit program:
[`2026-07-30-agent-evidence-broker-design.md`](2026-07-30-agent-evidence-broker-design.md)
**revision 15** — §3.3 (journal), §3.4 (session), §3.4.1 (cross-process contract), §3.5 (CLI and
`served/`), §4.1 (run record), §4.3 (baseline), §6 (seal failure), and the §7 bullets named below.

Plan 1 (`57b09bf0`) and plan 2 (`dab47dc3`) are merged. This is plan 3 of four.

## Scope: what this plan does NOT include, and why

**Plan 4 — correspondence — is everything in §5**, plus `Review` / `ReviewSubmission` /
`Correspondence`, `append_review`, §4.2 eligibility, and the replay itself. This plan seals
`replay_protocol` into the exposure and defines `REPLAY_PROTOCOL_VERSION`; it never replays.

The cut falls here because the seal is a **copy** and the check is §5's — §3.4.1 says so in as many
words, and revision 9 exists because eight revisions had the seal replaying. An implementer who finds
themself re-serving an entry outside `session.py` has crossed into plan 4.

Two consequences worth stating, because both look like omissions:

- **The seal does not verify inline entries against the manifest.** §5.2 checks a journal `inline`
  entry's `sha256` against `exposure.inline` at replay time. Doing it at seal time would make a
  tampered journal produce *no record at all* (§6), which is a failure mode §6's table does not list
  and which is strictly harsher than the design's.
- **The seal does not judge outcomes.** It copies what the journal recorded. §5.2 is where a recorded
  outcome is compared against a recomputed one.

**Which §7 bullets this plan closes in full:** `session.py` (all seven clauses); the `served/` half
of "Served bytes and the write gate"; "Refusals do not become coverage" *as far as the record can
carry it* — the storage side and its guard land here, the `append_review` end-to-end assertion is
plan 4's; "Sealing" (both clauses); the `--broker-spec`/`--baseline-out` and `--session`/`--baseline`
mutual exclusions and the brokered-baseline-elsewhere refusal from the `control_plane.py` bullet; the
"Session handle" bullet; and the `Model` bullet's four exposure clauses (`requests_used > budget`,
entries disagreeing on commit, `commit != base_commit`, exposure without an `instrument`).

**Which §7 bullets this plan deliberately leaves:**

| §7 requirement | Why it cannot land here |
|---|---|
| A relabelled refusal does not replay | The comparison is §5.2's; this plan stores the `outcome` it will compare |
| Correspondence, eligibility, `append_review`, protocol mismatch | Plan 4 entire |
| Integration: open, serve, seal, **append** | The first three land here and are asserted end-to-end; `append` is plan 4's |

## Design deviations recorded here

**None.** Five corrections that would have been deviations were made to the design first, as
**revision 12** (`8fe775b1`), because each was a defect in the design rather than a choice this plan
is making: the missing refusal row in §5.1 and the fail-open it produced, `ExposureEntry.outcome`,
journal creation moving to `start --broker-spec`, an exhausted budget journaling nothing, and a
refusal writing no `served/` file. Read revision 12's header paragraph before Task 1 — it explains
why the refusal row is the whole reason this plan stores an outcome at all.

**Revision 13** came from review of *this plan* and closes two more fail-opens, both design-level:
`InlineInput.target` must be a normalized project-relative path (an absolute one is a manifest entry
`LocationEvidence` can never express, so it would carry `FULL` coverage no citation could reach), and
the served file is written **before** the journal line (an entry appended first claims an exposure a
failed delivery never made — and replay confirms it, because replay re-serves from the commit and
never consults `served/`). Both are in Tasks 3 and 4 below.

That review also found six plan-level defects, all fixed in place: the `served/` containment check
design §3.5 requires and this plan had omitted; a `TypeError` escape in the journal parser that would
have raised out of `finish_run` instead of returning `UNWIRED`; the widened exception boundary and the
`"baseline_path": "None"` receipt on brokered `start`; a vacuous mutation and an overclaiming docstring
on the unbudgeted-path guard; and the `StrEnum` and `git add` slips. The mutation instructions in
Task 1 were themselves an instance of the conjunction defect — they asked for one mutation of a
validator that enforces two rules.

**A second review round found six more, and two of them were in guards the first round had just
rewritten.** The `served/` write used `path.exists()` as proof of content, so a partial write
returned truncated bytes on retry and a planted symlink was written *through* — the same
delivery fail-open reached through the existence check instead of the append (Task 3). `finish
--session` validated the handle but never bound the loaded baseline back to it, so a rule
implemented in full for `evidence serve` was half-implemented for the command that writes the
attestation (Task 6). The session journaled `request.target` rather than the authorized spelling,
which is precisely the defect plan 2 fixed *inside* `serve` — arriving one layer up because
`Served` never handed the spelling back (Task 1 step 9). And the rewritten AST guard accepted a
`_serve` call under *any* lock in the module rather than the one in `Session.request`: narrower
than its rule again, in the guard written to fix being narrower than its rule.

The lesson worth carrying into implementation: **rewriting a guard does not certify the rewrite.**
Each of these passed a careful reading. Only mutation finds them, which is why every guard below
names the specific mutations that must fail it.

**A third round found eight more, and the pattern held a third time.** The atomic-write fix from
round two protected the temporary *leaf* with `O_NOFOLLOW` while still re-resolving the
actor-controlled `served/` **parent** by pathname on every operation — so planting `served ->
<project>` after construction put both files in-tree anyway. That is the repository's own
descriptor-anchoring doctrine, and round two's fix had adopted half of it. The `finish` binding
added in round two was placed in the CLI while the authoritative `read_baseline` stayed inside
`finish_run`, so it constrained a value the attestation never used. And `baseline.py` importing
`control_plane.run_slug` is a **cycle** — `control_plane` already imports `baseline` — which fails
at module initialization, not at call time.

Two of round two's new tests could not have run at all: `monkeypatch.setattr(io.BufferedWriter,
"write", …)` raises `TypeError: cannot set 'write' attribute of immutable type` (verified in this
venv), and the concurrent budget test deadlocks if given the barrier that would make it
deterministic — thread A holds the lock and waits at the barrier for thread B, which is blocked
acquiring that lock. Both are replaced with deterministic forms below.

**A fourth round found five, and the two P1s were the same rule reaching further than round three
took it.** Round three anchored the `served/` *parent* to a descriptor and stopped: `_open_served_dir`
still opened the absolute `run_dir` by pathname with `O_NOFOLLOW`, which protects only that path's
final component — swap the `project-key` directory above it and `mkdir("served", dir_fd=parent)`
writes in-tree regardless. And the journal itself had been left entirely on pathnames: `journal_lock`
anchored only the unrelated lock file, while `append_request` and `read_journal` reopened
`journal.jsonl` by name. Replacing that name with a symlink to an empty project file is the worst
version of the fail-open in this design — counting succeeds, the budget never exhausts because the
count reads zero, a denied request never touches `served/` so no other guard fires, and the run's
exposure record is appended **into the project tree**. A hard link needs no symlink at all, and a FIFO
hangs the reader forever.

The fix is one shape applied everywhere rather than three patches: the run directory is captured once
by a component-by-component `O_NOFOLLOW` walk, and a `JournalHandle` carries that descriptor and the
journal's leaf name together through the lock, the count, the `served/` write and the append. No
function in `journal.py` takes a path any more, which is what makes "nothing re-resolves a pathname"
a property of the signatures instead of a rule to remember. Two new primitives —
`open_dir_anchored`, `open_record_at`, `read_regular_fd` and `write_all` — go into
`findings/paths.py`, where the walk already existed privately, rather than being copied into a
second module.

The round's three P2s are all bookkeeping the earlier rounds got wrong: Task 3's mutation list named
one mutation that cannot compile (`append_request` moved above the point where its arguments exist)
and one that changes nothing (deleting the receipt branch, not the write guard), and prescribed no
mutation at all for the three regressions round three had just added; the working-directory rule was
added as a Global Constraint but applied to only one of six tasks, and its real cost is the *next*
step's `git add science/src/...` resolving under `science/science/`; and Task 4 named a mutation whose
casualty is the opposite test from the one stated.

**A fifth round found seven, and the two P1s were — again — the same rule one step short.** Round
four anchored the *directory* and kept reopening the journal by name inside it. That passes every
check on both opens, because not-a-symlink, is-a-regular-file and one-link are claims about a
name's current occupant and **none of them is a claim about identity**: `unlink` plus an ordinary
new file defeats all three at once. The count would be taken from one inode and the append made to
another, so the round already spent disappears from the record and the budget the count enforces
stops being enforced. `JournalHandle` now carries the journal's own `O_RDWR | O_APPEND` descriptor,
opened once. The second P1 is smaller and older: both `os.write` calls discarded the returned byte
count, and a short write is legal and silent — a truncated line makes the whole journal unparseable,
which is `UNWIRED`.

Three of the five P2s are the same failure of self-checking in different clothes. Task 3's fixture
omitted a required model field, so the suite would have died in setup. Three mutation instructions
were *green against the defects they claimed to certify* — an unconditional `write_bytes` overwrites
the truncated file, an `O_NOFOLLOW` reopen still refuses a final-component symlink, and a FIFO opened
for writing with no reader fails `ENXIO` before `S_ISREG` is ever consulted, so that parametrization
was measuring the kernel. And round four's own `-am` → `-m` change turned "stages things you did not
name" into "drops things you forgot to name": two commit steps then omitted the modified
implementation files entirely. **A fix that trades one failure mode for its mirror image is not
finished until both directions are stated.**

The remaining two are claims that outran their mechanism. `MAX_JOURNAL_BYTES` was a chosen megabyte
with no relationship to what the model admits, so one long target produced a journal that could be
written and never read — the fail-open arriving through arithmetic instead of a syscall; the bound is
now derived from model-declared limits and the write side refuses first. And `create_journal` called
`Path.mkdir(parents=True)` *before* the anchored walk, which is hazard 3 in `findings/paths.py`'s own
header — mutating before validating — so a planted ancestor got directories created in its target
before the refusal.

**The compounding lesson: a fix is a new claim, and inherits none of the certification of what it
replaced.** Five rounds, and each round's *fixes* were where the next round's findings landed. Its
sharpest form is the descriptor rule, which has now been applied four times and been one step short
three times — the file's directory, then the directory's ancestors, then the file's *identity*. The
rule is not "protect the file", nor "protect the file's directory": it is *hold a descriptor and
never name the thing again*.

## Global Constraints

Every task's requirements implicitly include this section.

1. **Every guard is proven by restoring the prior behaviour and confirming its test fails** (§7). A
   test that passes against the defect it was written to catch is a finding, not a test. State in the
   task report *which* mutation you applied and that you watched it fail.
2. **Prefer a predicate over a roster.** A guard that enumerates its scope has a hole where the list
   ends. This was the single recurring defect across plan 2 — seven instances.
3. **No path reaches git without passing `authorize`.** `session.py` calls `serve.serve`, which
   authorizes; it must not build argv or call `run_git` itself.
4. **Nothing this plan writes lands in the project tree.** Journal, baseline and `served/` all live
   under `control_plane.run_dir`, and every one of them is put through
   `reject_baseline_inside_project` against the same `project_root`.
5. **A derived value stored is a derived value recomputed on construction.** `requests_used` is the
   live case; a stored derived value nobody validates is a value that can lie.
6. **Fail early; no silent fallbacks; no compatibility layers.** An absent journal is an error, not
   an empty journal.
7. Line length 120. `(cd science && uv run ruff check && uv run pyright)` and
   `(cd science/model && uv run --frozen pytest)` both clean before every commit.
   **Every `cd` in this plan is relative to the repository root, and your shell's working
   directory persists between commands.** `science/` and `science/model/` are sibling package
   roots, so a bare `cd science/model` after a `cd science` resolves to `science/science/model`
   and fails — and the failure is not confined to the `cd` that causes it: the *next* step's
   `git add science/src/...` then resolves to `science/science/src/...` and the commit silently
   stages nothing. Every command in this plan that changes directory is therefore written as a
   subshell — `(cd science && …)` — including single `Run:` lines. If you find one that is not,
   that is a defect in the plan; wrap it rather than reproducing it.
8. Conventional commits. No AI-attribution trailer or footer.
9. **`git commit -am` stages only tracked files.** Every task here creates new files; `git add`
   them explicitly before committing, and check `git status --porcelain` is clean afterwards. A
   task that "committed" while leaving its module untracked passes its own tests and fails the
   next task's import. Where a step already runs an explicit `git add`, commit with `-m`, not
   `-am`: the `-a` would also sweep in unrelated tracked edits the step never named. **The two
   halves of that rule cut opposite ways** — `-am` stages things you did not name, `-m` drops
   things you forgot to name — so every `git add` must list *every* file the task touched,
   created and modified alike, and every commit step ends with `git status --porcelain` returning
   empty. A task whose implementation file is left unstaged passes its own tests from the working
   tree and fails the next task's.

---

### Task 1: The sealed vocabulary

**Files:**
- Modify: `science/model/src/science_model/evidence_broker.py`
- Modify: `science/model/src/science_model/autonomous_runs.py`
- Modify: `science/src/science_tool/evidence_broker/serve.py:45-50` (delete `Outcome`, import it)
- Test: `science/model/tests/test_evidence_broker_model.py`
- Test: `science/model/tests/test_autonomous_run_record.py`

**Interfaces:**
- Consumes: `SurfacePolicy` (shipped, same module).
- Produces: `Outcome`, `InstrumentIdentity`, `InlineInput`, `ExposureEntry`, `EvidenceExposure`,
  `EvidenceSession`, `EvidenceSessionSpec`, `REPLAY_PROTOCOL_VERSION`, and
  `AutonomousRunRecord.evidence`. Tasks 2–6 all import from here.
- Also modifies plan 2's `Served` to carry the authorized spelling (step 9) — the one change this
  plan makes to shipped serving code, and the reason Task 3 can journal what git actually read.

**Why `Outcome` moves rather than being copied:** `ExposureEntry.outcome` is typed by it and
`science_model` cannot import `science_tool`. A second enum with the same members is the
two-vocabularies failure design §3.3 names explicitly. `MISS_MARKERS` stays in `serve.py` — those are
served *bytes*, which is serving's business.

- [ ] **Step 1: Write the failing tests for the exposure validators**

In `science/model/tests/test_evidence_broker_model.py`:

```python
import pytest
from pydantic import ValidationError

from science_model.evidence_broker import (
    REPLAY_PROTOCOL_VERSION,
    EvidenceExposure,
    ExposureEntry,
    InlineInput,
    InstrumentIdentity,
    Outcome,
    SurfacePolicy,
)

COMMIT = "a" * 40
OTHER = "b" * 40
INSTRUMENT = InstrumentIdentity(ref="rubric.md", sha256="c" * 64, prompt_hash="d" * 64)
POLICY = SurfacePolicy(notice="withheld")


def _entry(**overrides) -> ExposureEntry:
    fields = {
        "op": "read", "target": "a.md", "commit": COMMIT,
        "sha256": "e" * 64, "outcome": Outcome.SERVED,
    }
    return ExposureEntry(**{**fields, **overrides})


def _exposure(**overrides) -> EvidenceExposure:
    fields = {
        "commit": COMMIT, "budget": 10, "requests_used": 0, "instrument": INSTRUMENT,
        "surface_policy": POLICY, "replay_protocol": REPLAY_PROTOCOL_VERSION, "entries": (),
    }
    return EvidenceExposure(**{**fields, **overrides})


def test_requests_used_must_equal_the_non_inline_entry_count() -> None:
    """A spend counter that can disagree with the log it counts is a value that can lie."""
    with pytest.raises(ValidationError, match="requests_used"):
        _exposure(requests_used=1, entries=(_entry(op="inline"),))


def test_a_refusal_counts_toward_the_spend() -> None:
    """Denials spend rounds (design §3.4), so they are entries like any other."""
    exposure = _exposure(requests_used=1, entries=(_entry(outcome=Outcome.REFUSED, sha256=""),))
    assert exposure.requests_used == 1


def test_requests_used_may_not_exceed_the_budget() -> None:
    with pytest.raises(ValidationError, match="budget"):
        _exposure(budget=1, requests_used=2, entries=(_entry(), _entry(target="b.md")))


def test_entries_must_agree_with_the_exposure_commit() -> None:
    """A run that read two trees did not have one evidence surface."""
    with pytest.raises(ValidationError, match="commit"):
        _exposure(requests_used=1, entries=(_entry(commit=OTHER),))


def test_an_inline_entry_carries_served() -> None:
    """`inline` is the supervisor's own seeding; there is no outcome it could have missed."""
    with pytest.raises(ValidationError, match="inline"):
        _exposure(entries=(_entry(op="inline", outcome=Outcome.REFUSED),))


def test_the_instrument_is_required() -> None:
    """Mandatory to open and droppable at seal time would be the RunBudget defect again."""
    with pytest.raises(ValidationError):
        EvidenceExposure(
            commit=COMMIT, budget=1, requests_used=0, surface_policy=POLICY,
            replay_protocol=REPLAY_PROTOCOL_VERSION,
        )


def test_a_budget_of_zero_is_legitimate() -> None:
    """Inline seeding with no requests permitted is a real study design, not a config error."""
    assert _exposure(budget=0, requests_used=0).budget == 0
```

- [ ] **Step 2: Run them and watch every one fail**

Run: `(cd science/model && uv run --frozen pytest tests/test_evidence_broker_model.py -x)`
Expected: `ImportError` on `REPLAY_PROTOCOL_VERSION` / `EvidenceExposure`.

- [ ] **Step 3: Add the vocabulary**

Append to `science/model/src/science_model/evidence_broker.py`:

```python
#: Bumped ONLY when serving or parsing changes -- the defined-miss markers, the canonical argv of
#: design §3.2.1, the hit-line parsing. NOT `toolkit_revision`: a signal that fires on every
#: release is a signal people learn to ignore, and a mismatch REFUSES honest historical work.
REPLAY_PROTOCOL_VERSION = 1

#: THE THREE BOUNDS THAT MAKE THE JOURNAL'S SIZE KNOWABLE IN ADVANCE, and the reason they live
#: here rather than in `journal.py`: the journal's read bound is DERIVED from them
#: (`MAX_JOURNAL_BYTES = (MAX_BUDGET + MAX_INLINE_INPUTS) * MAX_ENTRY_BYTES`). A read bound chosen
#: independently of what the model admits is a run that can write a journal it cannot read back --
#: and since an unreadable journal is design §6's `UNWIRED`, that is a supervisor-side failure
#: produced by an input the model accepted. Bound the inputs, then compute the bound.
#:
#: `MAX_TARGET_BYTES` is `PATH_MAX` on Linux, which is the largest path git could return anyway;
#: a longer `target` is a usage error, not a probe, so refusing it discloses nothing.
MAX_TARGET_BYTES = 4096
MAX_BUDGET = 100
MAX_INLINE_INPUTS = 100


class Outcome(StrEnum):
    """What one request produced. Lives here, not in `serve.py`, because `ExposureEntry` is
    typed by it and `science_model` cannot import `science_tool`."""

    SERVED = "served"
    MISS_ABSENT = "miss-absent"
    MISS_NO_MATCH = "miss-no-match"
    MISS_NO_COMMITS = "miss-no-commits"
    REFUSED = "refused"


class InstrumentIdentity(BaseModel):
    """What defined the judgement procedure. A judgement scored against a silently edited
    rubric is presently undetectable; this is what closes that."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str
    sha256: str
    prompt_hash: str


class InlineInput(BaseModel):
    """One input the opening prompt already supplied.

    `lines` is carried because inline bytes are not in the tree, so a line count cannot be
    re-derived later -- and a line citation into an inline input must be checkable the same
    way as one into a read file.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: str = Field(max_length=MAX_TARGET_BYTES)
    sha256: str
    lines: int = Field(ge=0)


class ExposureEntry(BaseModel):
    """One journal event, sealed.

    Deliberately does NOT store which lines a search matched: those are re-derived at replay,
    and storing them would be storing the actor's account of its own exposure.

    It DOES store `outcome`, and the difference is that `outcome` is CHECKED -- replay
    recomputes it and compares, exactly as it already does for `sha256`. Dropping it was a
    fail-open: a refusal re-serves to an empty payload, so without an outcome a denied path is
    distinguishable from a genuinely empty file only by re-serving, and any consumer
    classifying by op-and-payload files the DENIED path as `FULL` with a line count of zero --
    which design §5.1 reads as "every line was in front of the reviewer".
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    op: Literal["read", "search", "history", "inline"]
    target: str = Field(max_length=MAX_TARGET_BYTES)
    pathspec: str | None = Field(default=None, max_length=MAX_TARGET_BYTES)
    commit: str
    sha256: str
    outcome: Outcome


class EvidenceExposure(BaseModel):
    """The sealed record of what an agent was shown.

    Seals every input replay needs, so re-checking a run takes the record and a repository and
    nothing else. The surface policy is here because deny prefixes are `:(exclude)` pathspecs on
    every search -- part of the query, so part of the replay -- and the manifest is here because
    the baseline it was declared in orphans when a project moves.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    commit: str
    budget: int = Field(ge=0, le=MAX_BUDGET)
    requests_used: int = Field(ge=0)
    instrument: InstrumentIdentity
    surface_policy: SurfacePolicy
    inline: tuple[InlineInput, ...] = Field(default=(), max_length=MAX_INLINE_INPUTS)
    replay_protocol: int
    entries: tuple[ExposureEntry, ...] = ()

    @model_validator(mode="after")
    def _spend_is_derived_then_bounded(self) -> EvidenceExposure:
        """RECOMPUTED, then bounded. The bound is meaningful only once the count is honest.

        Order matters: checking `requests_used <= budget` against a stored number that nobody
        tied to `entries` accepts a record carrying ten request entries and `requests_used=1`.
        """
        counted = len([entry for entry in self.entries if entry.op != "inline"])
        if self.requests_used != counted:
            raise ValueError(
                f"requests_used is {self.requests_used} but {counted} non-inline entries are "
                "recorded; the spend is derived from the log, not asserted beside it"
            )
        if self.requests_used > self.budget:
            raise ValueError(f"requests_used {self.requests_used} exceeds budget {self.budget}")
        return self

    @model_validator(mode="after")
    def _one_evidence_surface(self) -> EvidenceExposure:
        """A run that read two trees did not have one evidence surface."""
        for entry in self.entries:
            if entry.commit != self.commit:
                raise ValueError(
                    f"entry {entry.target!r} is at commit {entry.commit} but the exposure is at "
                    f"{self.commit}"
                )
        return self

    @model_validator(mode="after")
    def _inline_entries_were_served(self) -> EvidenceExposure:
        """`inline` is the supervisor's own seeding, written before any actor exists.

        An `Outcome` member meaning "not applicable" would put a value in the enum that `serve`
        can never return, which is how one vocabulary starts describing two things.
        """
        for entry in self.entries:
            if entry.op == "inline" and entry.outcome is not Outcome.SERVED:
                raise ValueError(
                    f"inline entry {entry.target!r} carries outcome {entry.outcome}; the "
                    "supervisor's own seeding is served by construction"
                )
        return self


class EvidenceSession(BaseModel):
    """The live session, declared in `RunBaseline`. NONE of it is settable on the command line:
    a caller cannot lower a budget it did not set, raise one it did, weaken the deny policy, or
    point the session at a different journal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    journal_path: Path
    commit: str
    budget: int = Field(ge=0, le=MAX_BUDGET)
    surface_policy: SurfacePolicy
    instrument: InstrumentIdentity
    inline: tuple[InlineInput, ...] = Field(default=(), max_length=MAX_INLINE_INPUTS)


class EvidenceSessionSpec(BaseModel):
    """The supervisor's declaration, read from JSON at `start`.

    `inline_paths` are PATHS, not hashes: `start` reads each one and computes its `sha256` and
    line count itself. A supervisor that declared those numbers would be attesting to bytes it
    had not necessarily read.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    budget: int = Field(ge=0, le=MAX_BUDGET)
    surface_policy: SurfacePolicy
    instrument: InstrumentIdentity
    inline_paths: tuple[Path, ...] = Field(default=(), max_length=MAX_INLINE_INPUTS)
```

Add to the module's imports: `from enum import StrEnum`, `from pathlib import Path`,
`from typing import Literal`, and extend the pydantic import to
`from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator`.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `(cd science/model && uv run --frozen pytest tests/test_evidence_broker_model.py)`
Expected: exit 0. (This repo's pytest config suppresses the `N passed` line — the exit code is the
evidence.)

- [ ] **Step 5: Certify each validator by mutation**

There are **three** validators on `EvidenceExposure`, and one of them enforces a conjunction — so
this is four mutations, not three, and not the "one per validator" the count suggests:

| Mutation | Must fail | Must still pass |
|---|---|---|
| `_spend_is_derived_then_bounded`: delete the **count** branch only | `test_requests_used_must_equal_the_non_inline_entry_count` | the budget test |
| `_spend_is_derived_then_bounded`: delete the **bound** branch only | `test_requests_used_may_not_exceed_the_budget` | the count test |
| `_one_evidence_surface` → `return self` | `test_entries_must_agree_with_the_exposure_commit` | others |
| `_inline_entries_were_served` → `return self` | `test_an_inline_entry_carries_served` | others |

**Do not mutate `_spend_is_derived_then_bounded` as a whole.** Removing it fails *both* tests, which
proves neither branch: a guard that certifies a conjunction certifies neither half, and this
validator is the conjunction. The two branches are also ordered on purpose — the bound is meaningless
against a count nobody tied to `entries` — so the count-branch mutation is the one that matters most.

`_exposure_is_bound_to_this_run` lives on `AutonomousRunRecord` and is certified separately in step 7.
Restore everything and record all four mutations and their results in your report.

- [ ] **Step 6: Hang `evidence` on the run record**

In `science/model/src/science_model/autonomous_runs.py`, add to `AutonomousRunRecord`:

```python
    evidence: EvidenceExposure | None = None
```

Grouped into one optional field because it is all-or-nothing: a run either was brokered or was not,
and one group makes "brokered" a single checkable predicate rather than three fields that can
disagree. Then add the cross-field validator:

```python
    @model_validator(mode="after")
    def _exposure_is_bound_to_this_run(self) -> AutonomousRunRecord:
        """`base_commit`, NOT `head_commit`.

        Requiring only internal agreement lets an arbitrary or orphan commit replay perfectly
        while the exposure is bound to no run at all. And `head` includes the actor's own
        writes -- an agent permitted to cite a file it wrote during the run is back to
        self-attestation by a longer route.
        """
        if self.evidence is not None and self.evidence.commit != self.base_commit:
            raise ValueError(
                f"the exposure is at commit {self.evidence.commit} but the run's base commit is "
                f"{self.base_commit}; an exposure bound to another tree is bound to no run"
            )
        return self
```

- [ ] **Step 7: Test the binding, then mutate it**

In `science/model/tests/test_autonomous_run_record.py`, add a test that a record whose
`evidence.commit` differs from `base_commit` is rejected, and one that a record built with
`evidence.commit == head_commit` (and `head != base`) is **also** rejected — the second is what
proves the validator reads `base_commit` rather than merely "some commit on the record". Mutate
`base_commit` → `head_commit` in the validator and confirm the second test fails.

- [ ] **Step 8: Move `Outcome` out of `serve.py`**

Delete the `class Outcome(StrEnum)` block at `serve.py:45-50` and import it instead:

```python
from science_model.evidence_broker import Outcome, SurfacePolicy
```

`MISS_MARKERS` keeps its `dict[Outcome, bytes]` annotation and its position. Every existing reference
is already `Outcome.X`, so no call site moves — but **one more line must go**: `serve.py:21` imports
`StrEnum` solely for the class being deleted, and leaving it is an immediate `ruff` F401. Delete
`from enum import StrEnum` too, and confirm with `grep -n StrEnum serve.py` returning nothing before
you commit.

- [ ] **Step 9: Hand the authorized spelling back through `Served`**

**The defect this closes is the one plan 2 already fixed one layer down.** `authorize` returns both a
verdict *and* the normalized spelling, because "returning only a verdict is what let an earlier draft
authorize one path and read another". `serve` honours that internally — every git call uses
`auth.path` — but `Served` carries only `(outcome, payload, denial)`, so a *caller* has no way to
learn what was actually read. Task 3 journals the entry, and with only the raw request in reach it
would record `a\b` for a read of `a/b`. `LocationEvidence.path` normalizes, so an honest citation to
`a/b` would key differently from the entry and come back `CITATION_UNSERVED`. The same trap, one
layer up, reached by the same route.

Add to `Served`:

```python
    #: The spelling git was actually given: `auth.path` for `read` and `history`, the pattern as
    #: supplied for `search` (a pattern is not a path and is never normalized). On a REFUSAL it
    #: is the raw request -- a denied or malformed request has no authorized spelling, and a path
    #: that fails to normalize has no other form.
    #:
    #: REQUIRED, not defaulted. An optional field with `None` meaning "refused" also means
    #: "somebody forgot to stamp it", and the two are indistinguishable at the call site: a miss
    #: or a history entry that slipped through unstamped would silently fall back to the raw
    #: request in the journal, which is the exact defect this field exists to close. Required
    #: makes the omission a construction error instead of a silent downgrade.
    target: str
    #: `auth.path` for a search's optional pathspec; `None` when the request carried none.
    pathspec: str | None = None
```

Populate it at **every** return in `serve` — not only the served ones. `_serve_read` and
`_serve_history` receive `auth.path` already; `_serve_search` receives the pattern and `auth.path` as
separate arguments; `_miss(...)` must take it too, since a miss is an answer about a specific path;
and the refusal branch passes `request.target`. Because the field is required, the type checker finds
any return that forgot it.

Test all four outcome families, not just a served read — **`MISS_ABSENT`, `MISS_NO_MATCH`,
`MISS_NO_COMMITS` and `REFUSED` each carry a target**, and a read miss on `a\b` reports `a/b`. A
single served-read test would leave the miss and history paths free to regress into the raw
spelling.

Test that a read of `a\b` against a repository containing only `a/b` returns `served.target == "a/b"`,
not `"a\\b"` — plan 2's suite already builds exactly this fixture to prove `auth.path` reaches git, so
extend that test rather than inventing a second repository. Certify by returning `request.target`
instead of `auth.path` and confirming it fails.

- [ ] **Step 10: Confirm plan 2's suite is untouched by the move**

Run: `(cd science && uv run --frozen pytest tests/test_evidence_broker_serve.py
tests/test_evidence_broker_policy.py tests/test_evidence_broker_canonical.py)`
Expected: exit 0. An import move that changes behaviour is not an import move.

- [ ] **Step 11: Lint, type-check, commit**

```bash
(cd science && uv run ruff check && uv run pyright)
(cd science/model && uv run ruff check)
git add science/model/src science/model/tests science/src/science_tool/evidence_broker/serve.py
git commit -m "feat(evidence-broker): seal the exposure vocabulary"
```

---

### Task 2: The journal

**Files:**
- Create: `science/src/science_tool/evidence_broker/journal.py`
- Modify: `science/src/science_tool/findings/paths.py` (two new primitives; see step 0)
- Test: `science/tests/test_evidence_broker_journal.py`, `science/tests/test_findings_paths.py`

**Interfaces:**
- Consumes: `ExposureEntry`, `InlineInput`, `Outcome` (Task 1);
  `reject_baseline_inside_project` (`autonomy/baseline.py`); `open_dir_anchored`,
  `open_lock_at`, `open_record_at`, `create_regular_file_at`, `read_regular_fd`, `write_all`
  (`findings/paths.py`).
- Produces:

```python
class JournalError(RuntimeError): ...


class JournalHandle(NamedTuple):
    """The captured run directory, the OPEN journal, and the journal's leaf name."""

    dir_fd: int
    fd: int
    name: str


def create_journal(path: Path, *, project_root: Path, inline: tuple[InlineInput, ...]) -> None
def append_request(handle: JournalHandle, entry: ExposureEntry) -> None
def read_journal(handle: JournalHandle) -> tuple[ExposureEntry, ...]
def count_requests(entries: tuple[ExposureEntry, ...]) -> int

@contextmanager
def open_journal(path: Path, *, project_root: Path) -> Iterator[JournalHandle]
@contextmanager
def journal_lock(path: Path, *, project_root: Path) -> Iterator[JournalHandle]
```

`read_journal` returns `ExposureEntry` values directly — `inline` events become
`ExposureEntry(op="inline", …, outcome=Outcome.SERVED)`. The journal's `inline` event also carries
`lines`, which `ExposureEntry` has no field for; that number lives in the **manifest**
(`EvidenceSession.inline`), which is where §5.2 reads it from, so it is written to the journal for a
human reader and dropped on parse rather than round-tripped into a field nothing checks.

**Every journal operation is anchored to a descriptor, and no operation takes a pathname.** This is
the module's whole shape, so read the reasoning before the code.

The run directory is **actor-writable** — `served/` lives in it by design (§3.5) — and therefore so
is every name in it, `journal.jsonl` included. A path-taking `append_request` that calls
`path.open("a")` hands the whole pathname back to the kernel at every append. Replace `journal.jsonl`
with a symlink to an empty file inside the project and the consequences compound in the wrong
direction: `read_journal` still parses (an empty file is a journal with no entries), the count comes
back low so the budget never exhausts, a *denied* request never touches `served/` and so trips no
other guard — and the append writes the run's exposure record **into the project tree**, where it is
a `report-only` path-gate denial produced by the broker itself. A FIFO planted under the same name
hangs `read_text` forever; a hard link needs no symlink at all, and `O_NOFOLLOW` is silent about it.

So the journal is reached the way `findings/paths.py` reaches everything: capture the directory once
by walking its components with `O_NOFOLLOW`, then perform **every** operation — the lock, the read,
the append — through that one descriptor. `JournalHandle` exists so the descriptor and the leaf name
travel together; a caller cannot pair one run's directory with another run's filename, and there is
no path-taking entry point left as the hole. `Session` (Task 3) threads the *same* handle from the
lock through the count, the serve, the `served/` write and the append: one capture, one critical
section. Re-walking per operation would be a check/use gap wearing an anchored costume — the lock
and the append could legitimately land in two different directories.

**Why `findings/paths.py` at all**, given design §3.4.1. §3.4.1 rejects that module's
*project-anchored* primitives — `open_dir_inside(project_root, …)`, `resolve_inside(project_root, …)`
— because they guarantee the result is **inside** a project root, which is the negation of what the
journal needs. That objection does not reach the `*_at` family: those take a descriptor, not a
project root, and each guarantees a property (`O_NOFOLLOW`, `S_ISREG`, `st_nlink == 1`, `O_EXCL`,
`O_NONBLOCK`) rather than a location. Cite a mechanism by what it guarantees, not by which module it
sits in. `open_dir_anchored` (step 0) is the same walk `_open_project_root` already performs, with
the project-containment claim factored out.

Containment is still checked, and it is a **different** question, decided in a different way:
`reject_baseline_inside_project(path, project_root)` asks lexically whether this run's record sits
outside the project tree — a supervisor-configuration question. `open_dir_anchored` asks whether we
reached the directory without traversing something an actor planted — a filesystem question. Neither
implies the other, so `open_journal` does both, in that order.

- [ ] **Step 0: Add the two missing anchored primitives**

`findings/paths.py` already has most of what the journal needs. Four things are missing: a walk
that captures an absolute directory **without** claiming it is inside a project (and can create it
one component at a time), a descriptor held open for both reading and appending, a bounded read from
an already-open descriptor, and a write that does not lose bytes to a short write. Add all four
there rather than in `journal.py` — a second private copy of a component-by-component security walk
is exactly the duplication this branch keeps finding defects in.

Add `stat` to the test module's imports alongside `os`; `write_all`'s test needs `monkeypatch`.

First, factor the existing walk. `_open_project_root` currently does two jobs: validate a project
root lexically, then walk it. Split them, so the walk is reusable and there is still only one of it:

```python
def open_dir_anchored(directory: Path, *, create: bool = False) -> int:
    """Open an absolute directory one component at a time, following no link.

    Makes NO claim about where the directory is -- that is the whole point, and why this is
    separate from `_open_project_root`. It guarantees only that the descriptor returned names
    the object reached by resolving each component with `O_NOFOLLOW`, never by handing the
    pathname back to the kernel. Callers outside a project root -- the autonomy control plane's
    run directory -- need that guarantee without the containment one, and design §3.4.1's
    objection to this module is to the containment claim, not to the walk.

    `create=True` makes each missing component ONE AT A TIME, inside the parent already captured,
    and stops AT a link having created nothing beyond it. This is why the flag exists here rather
    than the caller reaching for `Path.mkdir(parents=True)` first: `mkdir(parents=True)` follows
    links and creates directories in the LINK'S TARGET before any check runs, which is hazard 3
    in this module's header -- mutating before validating. A later refusal does not un-create
    them.
    """
    if not directory.is_absolute():
        raise PathSafetyError(f"{directory} must be absolute to be anchored")
    if ".." in directory.parts:
        raise PathSafetyError(f"{directory} contains a `..` segment")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        parent_fd = os.open(os.sep, flags)
    except OSError as exc:
        raise PathSafetyError(f"could not open the filesystem root: {exc}") from exc
    walked = Path(os.sep)
    try:
        for segment in directory.parts[1:]:
            walked = walked / segment
            name = _leaf_name(segment)
            if create:
                try:
                    os.mkdir(name, mode=0o755, dir_fd=parent_fd)
                except FileExistsError:
                    pass  # may be a real directory -- the O_NOFOLLOW reopen below decides
                except OSError as exc:
                    raise PathSafetyError(f"could not create {walked}: {exc}") from exc
            try:
                child_fd = os.open(name, flags, dir_fd=parent_fd)
            except OSError as exc:
                raise PathSafetyError(
                    f"{directory} has a missing, inaccessible, symlink, or non-directory "
                    f"component at {walked}: {exc}"
                ) from exc
            os.close(parent_fd)
            parent_fd = child_fd
    except BaseException:
        os.close(parent_fd)
        raise
    return parent_fd


def _open_project_root(project_root: Path) -> tuple[Path, int]:
    """Capture the absolute lexical root through one descriptor-anchored walk."""
    root = _absolute_project_root(project_root)
    return root, open_dir_anchored(root)
```

`_absolute_project_root` keeps the checks that are about *project roots specifically* — the NUL
scan and the single-POSIX-anchor requirement — and `open_dir_anchored` repeats the `..` and
absoluteness checks because it is now a public entry point that callers reach without going through
`_absolute_project_root` at all. A guard that holds only for one of two callers is not a guard.
`_open_project_root` passes no `create`, so root capture keeps refusing an absent component exactly
as it does today.

Second, an append-only *record* descriptor — one descriptor, held open, that is both read and
appended:

```python
def open_record_at(dir_fd: int, name: str) -> int:
    """Open an EXISTING regular file for reading AND appending, inside an anchored directory.

    READING AND APPENDING THROUGH ONE DESCRIPTOR IS THE POINT, not a convenience. A caller that
    opens the name to read it and opens the name again to append has anchored two operations to
    the DIRECTORY while leaving them unanchored to the FILE: between the two, an actor with write
    access to that directory can `unlink` the name and create an ordinary, single-link, non-symlink
    regular file in its place. Every check below passes on both opens -- and they are checks on two
    different inodes. Whatever the first open established (a count, a size, a parse) is no longer
    true of the object the second one writes to. Hold the descriptor; `O_APPEND` guarantees each
    write lands at the end of THAT inode however many other names come and go.

    Never creates. The journal is created exactly once, at `start`, when no actor yet exists to
    have planted anything (design §3.4.2's temporal trust argument); an open that would *create*
    the file is an operation on a run whose record was never opened, and creating it here would
    silently repair the tampering it is meant to detect.

    Three separate hazards, three separate defenses, because no one of them implies another.
    `O_NOFOLLOW` refuses a symlinked name -- the redirect that would land a run's exposure record
    inside the project tree. `S_ISREG` refuses a FIFO or device, which `O_NOFOLLOW` admits happily
    and which would block or discard every write. `st_nlink == 1` refuses a hard link, which is
    neither a symlink nor an irregular file: an actor who unlinks the journal and hard-links a
    project file into its place defeats both of the others, and the link count is the only thing
    that sees it. `O_NONBLOCK` so the FIFO case is refused rather than waited on.
    """
    name = _leaf_name(name)
    try:
        descriptor = os.open(
            name, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd
        )
    except OSError as exc:
        raise PathSafetyError(f"could not open record {name!r}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise PathSafetyError(f"{name!r} is not a regular file; refusing to use it as a record")
        if info.st_nlink != 1:
            raise PathSafetyError(
                f"{name!r} has {info.st_nlink} links; a hard-linked record lets whoever planted "
                "the link choose where these bytes also land"
            )
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def read_regular_fd(descriptor: int, max_bytes: int) -> str:
    """Read an ALREADY-OPEN regular file whole, from offset zero, without moving its offset.

    `pread`, not `read`: the caller's descriptor is shared with an `O_APPEND` writer, and a
    reader that advanced the offset would be reaching into the writer's state for no reason.
    `read_regular_file_at` delegates here after its own open, so the size bound and the decode
    contract have one implementation rather than two.
    """
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        raise PathSafetyError("descriptor is not a regular file; refusing to read it")
    if info.st_size > max_bytes:
        raise PathSafetyError(f"{info.st_size} bytes exceeds {max_bytes}")
    data = bytearray()
    while len(data) <= max_bytes:
        chunk = os.pread(descriptor, max_bytes + 1 - len(data), len(data))
        if not chunk:
            break
        data.extend(chunk)
    if len(data) > max_bytes:
        raise PathSafetyError(f"record exceeds {max_bytes} bytes")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PathSafetyError(f"record is not valid UTF-8: {exc}") from exc


def write_all(descriptor: int, payload: bytes) -> None:
    """Write every byte, or raise. `os.write` is allowed to write FEWER.

    A short write on a regular file is rare and entirely legal -- a signal arriving mid-write, a
    filesystem boundary, a full device. `os.write` returns the count and raises nothing, so a
    caller that discards the return value has written a TRUNCATED record while believing it wrote
    a whole one. For an append-only journal that is the delivery fail-open in its purest form: a
    half-written line makes the whole journal unparseable, which is design §6's `UNWIRED`, and a
    half-written line that happens to remain valid JSON is worse still.
    """
    view = memoryview(payload)
    while view:
        try:
            written = os.write(descriptor, view)
        except OSError as exc:
            raise PathSafetyError(f"could not write {len(view)} remaining bytes: {exc}") from exc
        if written == 0:
            raise PathSafetyError("write made no progress")
        view = view[written:]
```

`read_regular_file_at` keeps its own open (with `O_NOFOLLOW`/`O_NONBLOCK`/`S_ISREG`) and then
delegates its body to `read_regular_fd`, so there is one bounded-read implementation. That is a
refactor of shipped code — run the module's existing suite and expect it unchanged.

In `science/tests/test_findings_paths.py`, add four tests and run them before writing the code:

```python
def test_open_dir_anchored_refuses_a_symlinked_component(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "leaf").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    with pytest.raises(PathSafetyError, match="component at"):
        open_dir_anchored(tmp_path / "link" / "leaf")


def test_open_dir_anchored_refuses_a_relative_directory(tmp_path: Path) -> None:
    with pytest.raises(PathSafetyError, match="absolute"):
        open_dir_anchored(Path("relative/dir"))


@pytest.mark.parametrize(
    "plant",
    [
        pytest.param(lambda d, t: (d / "j").symlink_to(t), id="symlink"),
        pytest.param(lambda d, t: os.link(t, d / "j"), id="hardlink"),
        pytest.param(lambda d, t: os.mkfifo(d / "j"), id="fifo"),
    ],
)
def test_open_record_at_refuses_a_planted_target(tmp_path: Path, plant) -> None:
    """One test, three plants -- and all three must be present, because each defeats a
    different defense: the symlink defeats nothing but `O_NOFOLLOW`, the hard link defeats
    `O_NOFOLLOW` and `S_ISREG` both, and the FIFO defeats `O_NOFOLLOW` and `st_nlink`.

    THE FIFO NEEDS A READER HELD OPEN, and without one this parametrization certifies nothing.
    Opening a FIFO for writing with no reader fails `ENXIO` at the `os.open` itself, so the test
    goes green whether or not `S_ISREG` is there -- it would be measuring a kernel behaviour
    instead of the check we wrote. (`O_RDWR` avoids `ENXIO` on Linux, but that is
    implementation-defined in POSIX, so do not rely on it either.) Hold a reader so the open
    succeeds and `S_ISREG` is the only thing that can refuse.
    """
    directory, target = tmp_path / "d", tmp_path / "target"
    directory.mkdir()
    target.write_text("", encoding="utf-8")
    plant(directory, target)
    reader = None
    if stat.S_ISFIFO(os.lstat(directory / "j").st_mode):
        reader = os.open(directory / "j", os.O_RDONLY | os.O_NONBLOCK)
    fd = open_dir_anchored(directory)
    try:
        with pytest.raises(PathSafetyError):
            open_record_at(fd, "j")
    finally:
        os.close(fd)
        if reader is not None:
            os.close(reader)
    assert target.read_text(encoding="utf-8") == ""


def test_open_record_at_does_not_create(tmp_path: Path) -> None:
    fd = open_dir_anchored(tmp_path)
    try:
        with pytest.raises(PathSafetyError):
            open_record_at(fd, "absent")
    finally:
        os.close(fd)
    assert not (tmp_path / "absent").exists()


def test_open_dir_anchored_create_stops_at_a_link_having_made_nothing(tmp_path: Path) -> None:
    """Hazard 3 from this module's header: `Path.mkdir(parents=True)` follows links and creates
    inside the TARGET before anything is checked. Creating one component at a time inside the
    already-captured parent cannot: the link is refused where it sits."""
    (tmp_path / "elsewhere").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(PathSafetyError, match="component at"):
        open_dir_anchored(tmp_path / "link" / "a" / "b", create=True)
    assert list((tmp_path / "elsewhere").iterdir()) == []


def test_write_all_completes_a_short_write(tmp_path: Path, monkeypatch) -> None:
    """`os.write` may write fewer bytes than it was given and raise nothing. The stub is scoped
    BY DESCRIPTOR rather than replacing `os.write` wholesale, so pytest's own writes during the
    patched window are untouched -- a global stub here makes the failure mode of this test the
    failure mode of the test runner."""
    target = tmp_path / "f"
    target.write_bytes(b"")
    descriptor = os.open(target, os.O_WRONLY | os.O_APPEND)
    real = os.write

    def one_byte_at_a_time(fd: int, data) -> int:
        return real(fd, bytes(data)[:1]) if fd == descriptor else real(fd, data)

    monkeypatch.setattr(os, "write", one_byte_at_a_time)
    try:
        write_all(descriptor, b"0123456789")
    finally:
        os.close(descriptor)
    assert target.read_bytes() == b"0123456789"
```

Certify these by mutation before moving on: drop `create=True`'s per-component `mkdir` for a
`Path.mkdir(parents=True)` before the walk and confirm the create test fails; replace `write_all`'s
loop with a single `os.write` and confirm the short-write test fails; delete `S_ISREG` from
`open_record_at` and confirm the **`fifo`** parametrization fails (if it does not, the reader is not
being held and the parametrization is vacuous).

Then run the module's existing suite to confirm the `_open_project_root` and `read_regular_file_at`
refactors changed nothing:

Run: `(cd science && uv run --frozen pytest tests/test_findings_paths.py)`
Expected: exit 0, with the four new tests passing and every pre-existing test unchanged.

Commit this separately — it is a change to a shipped module and belongs in its own reviewable diff:

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/findings/paths.py science/tests/test_findings_paths.py
git commit -m "feat(findings): add anchored directory-walk and append primitives"
```

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_evidence_broker_journal.py`:

```python
import json
import os
from pathlib import Path

import pytest

from science_model.evidence_broker import ExposureEntry, InlineInput, Outcome
from science_tool.autonomy.baseline import BaselineError
from science_model.evidence_broker import MAX_BUDGET, MAX_INLINE_INPUTS, MAX_TARGET_BYTES
from science_tool.evidence_broker.journal import (
    MAX_ENTRY_BYTES,
    MAX_JOURNAL_BYTES,
    JournalError,
    append_request,
    count_requests,
    create_journal,
    open_journal,
    read_journal,
)

COMMIT = "a" * 40


def _entry(target: str = "a.md", outcome: Outcome = Outcome.SERVED) -> ExposureEntry:
    return ExposureEntry(
        op="read", target=target, commit=COMMIT, sha256="e" * 64, outcome=outcome
    )


def _append(journal: Path, project: Path, entry: ExposureEntry) -> None:
    """Every append captures the run directory, appends through the descriptor, and releases it.

    The tests use this rather than calling `append_request` with a path because there IS no
    path-taking append -- that is the property, not a convenience the tests happen to skip.
    """
    with open_journal(journal, project_root=project) as handle:
        append_request(handle, entry)


def _read(journal: Path, project: Path) -> tuple[ExposureEntry, ...]:
    with open_journal(journal, project_root=project) as handle:
        return read_journal(handle)


def test_create_then_append_then_read(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=(
        InlineInput(target="prompt.md", sha256="f" * 64, lines=12),
    ))
    _append(journal, project, _entry())
    entries = _read(journal, project)
    assert [entry.op for entry in entries] == ["inline", "read"]
    assert count_requests(entries) == 1


def test_inline_seeding_costs_nothing(tmp_path: Path) -> None:
    """Seeding is not a request; charging for it is charging for evidence never asked for."""
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=tuple(
        InlineInput(target=f"in{n}.md", sha256="f" * 64, lines=1) for n in range(5)
    ))
    assert count_requests(_read(journal, project)) == 0


def test_a_refusal_is_counted(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    _append(journal, project, _entry(outcome=Outcome.REFUSED))
    assert count_requests(_read(journal, project)) == 1


@pytest.mark.parametrize(
    "plant",
    [
        pytest.param(lambda journal, decoy: journal.symlink_to(decoy), id="symlink"),
        pytest.param(lambda journal, decoy: os.link(decoy, journal), id="hardlink"),
        pytest.param(lambda journal, decoy: os.mkfifo(journal), id="fifo"),
    ],
)
def test_a_journal_replaced_after_creation_is_refused_not_followed(tmp_path: Path, plant) -> None:
    """The run directory is actor-writable, so `journal.jsonl` is an actor-controlled NAME.

    Each plant redirects a path-taking append to a file of the actor's choosing, and each
    defeats a different defense -- so all three must be here. The assertion is in two halves and
    both matter: appending RAISES (fail closed, which `finish_run` turns into `UNWIRED`), and the
    decoy is still empty (nothing was written through the redirect). A test that only checked
    the raise would pass against an implementation that wrote first and complained after.

    THE DECOY IS DELIBERATELY OUTSIDE THE PROJECT. Aiming it inside would make
    `reject_baseline_inside_project` refuse the `symlink` case before `O_NOFOLLOW` was ever
    consulted, so that parametrization would certify the containment check rather than the guard
    it is written for -- green for the wrong reason, which is this branch's recurring defect.
    """
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    (tmp_path / "run").mkdir()
    decoy = tmp_path / "decoy.md"
    decoy.write_text("", encoding="utf-8")
    create_journal(journal, project_root=project, inline=())
    journal.unlink()
    plant(journal, decoy)
    with pytest.raises(JournalError):
        _append(journal, project, _entry())
    assert decoy.read_text(encoding="utf-8") == ""


def test_a_symlinked_run_directory_is_refused(tmp_path: Path) -> None:
    """The finding one component further out. Protecting `j.jsonl` protects nothing if `run/`
    itself is re-resolved by pathname: the actor swaps the DIRECTORY, and a leaf-only
    `O_NOFOLLOW` opens a perfectly ordinary regular file that happens to be in the project."""
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    (tmp_path / "real").mkdir()
    (tmp_path / "run").symlink_to(tmp_path / "real")
    with pytest.raises(JournalError, match="run directory"):
        _read(journal, project)


def test_a_journal_larger_than_the_bound_is_an_error(tmp_path: Path) -> None:
    """A bounded read is what keeps a planted enormous file from being loaded whole.
    Refusing is fail-closed: an unreadable journal is design §6's `UNWIRED`.

    `os.truncate` makes a SPARSE file, so this costs no disk and no time; writing
    `MAX_JOURNAL_BYTES` of real bytes would put megabytes through a Dropbox-backed checkout on
    every run of the suite.
    """
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    (tmp_path / "run").mkdir()
    create_journal(journal, project_root=project, inline=())
    os.truncate(journal, MAX_JOURNAL_BYTES + 1)
    with pytest.raises(JournalError):
        _read(journal, project)


def test_an_entry_over_the_line_bound_is_refused_before_it_is_written(tmp_path: Path) -> None:
    """THE OTHER HALF OF THE SAME BOUND, and without it the read bound is a trap rather than a
    guard. A journal that can be WRITTEN past what can be READ means the first over-long entry
    is accepted, and every later request plus the seal then fails on the oversized journal --
    design §6 turns that into no record at all. So the write side refuses first, and the run
    survives."""
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    (tmp_path / "run").mkdir()
    create_journal(journal, project_root=project, inline=())
    with pytest.raises(JournalError, match="bound"):
        _append(journal, project, _entry(target="a" * MAX_TARGET_BYTES))
    assert _read(journal, project) == ()


def test_the_read_bound_admits_a_maximally_sized_journal(tmp_path: Path) -> None:
    """The derivation, asserted rather than trusted: `MAX_BUDGET` entries at `MAX_ENTRY_BYTES`
    must fit under `MAX_JOURNAL_BYTES`. If someone later tunes one constant without the others,
    this is what says so -- an arithmetic relationship nobody checks is an arithmetic
    relationship that drifts."""
    assert (MAX_BUDGET + MAX_INLINE_INPUTS) * MAX_ENTRY_BYTES <= MAX_JOURNAL_BYTES


def test_the_journal_read_and_the_append_address_one_inode(tmp_path: Path) -> None:
    """THE HANDLE PINS THE FILE, NOT ONLY ITS DIRECTORY.

    Between the count and the append, the actor replaces `j.jsonl` with an ordinary, single-link,
    non-symlink regular file. Every check `open_record_at` makes passes on both opens -- they are
    just checks on two different inodes. A handle that reopened by name would count the old file
    and append to the new one, so the round already spent would vanish from the record and the
    budget it enforces would stop being enforced. Holding the descriptor makes the swap
    irrelevant: `O_APPEND` writes to the inode that was opened, whatever now owns the name.
    """
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    (tmp_path / "run").mkdir()
    create_journal(journal, project_root=project, inline=())
    with open_journal(journal, project_root=project) as handle:
        append_request(handle, _entry("first.md"))
        assert count_requests(read_journal(handle)) == 1
        journal.unlink()
        journal.write_text("", encoding="utf-8")     # ordinary, single-link, not a symlink
        append_request(handle, _entry("second.md"))
        assert count_requests(read_journal(handle)) == 2
    assert journal.read_text(encoding="utf-8") == ""  # the decoy never received a thing


def test_a_short_write_does_not_truncate_an_entry(tmp_path: Path, monkeypatch) -> None:
    """`os.write` may write fewer bytes than it is given and raise nothing. A caller that
    discards the count records a TRUNCATED line while believing it recorded a whole one -- and a
    truncated line makes the entire journal unparseable, which is `UNWIRED`. Scoped by
    descriptor so pytest's own writes are untouched."""
    journal, project = tmp_path / "run" / "j.jsonl", tmp_path / "project"
    project.mkdir()
    (tmp_path / "run").mkdir()
    create_journal(journal, project_root=project, inline=())
    real = os.write
    with open_journal(journal, project_root=project) as handle:
        def one_byte_at_a_time(fd: int, data) -> int:
            return real(fd, bytes(data)[:1]) if fd == handle.fd else real(fd, data)

        monkeypatch.setattr(os, "write", one_byte_at_a_time)
        append_request(handle, _entry())
        monkeypatch.undo()
        assert count_requests(read_journal(handle)) == 1


def test_create_makes_nothing_through_a_symlinked_ancestor(tmp_path: Path) -> None:
    """`Path.mkdir(parents=True)` FOLLOWS LINKS and creates in the target before any check runs.
    A refusal afterwards does not remove them, and directories are themselves a write in a tree
    the path gate watches -- so "no bytes were written yet" is not a defence."""
    project, elsewhere = tmp_path / "project", tmp_path / "elsewhere"
    project.mkdir()
    elsewhere.mkdir()
    # NOT aimed at the project: `reject_baseline_inside_project` would refuse that first, and the
    # parametrization would certify the containment check instead of the walk it is written for.
    (tmp_path / "cp").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(JournalError, match="run directory"):
        create_journal(tmp_path / "cp" / "run-x" / "j.jsonl", project_root=project, inline=())
    assert list(elsewhere.iterdir()) == []


def test_creating_over_an_existing_journal_refuses(tmp_path: Path) -> None:
    """Reusing a journal path discards the exposure record of whatever run already owns it."""
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    with pytest.raises(JournalError, match="already"):
        create_journal(journal, project_root=project, inline=())


def test_a_journal_inside_the_project_refuses(tmp_path: Path) -> None:
    """A log inside the tree the actor can write is not a record of what the actor was shown."""
    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(BaselineError, match="inside the project"):
        create_journal(project / "j.jsonl", project_root=project, inline=())


def test_a_truncated_line_is_an_error_not_an_empty_journal(tmp_path: Path) -> None:
    """Fail early. A half-written line is a journal we cannot read, which is design §6's
    `UNWIRED`, not a journal with fewer entries."""
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    _append(journal, project, _entry())
    journal.write_text(journal.read_text()[:-8], encoding="utf-8")
    with pytest.raises(JournalError):
        _read(journal, project)


def test_appends_never_rewrite(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    _append(journal, project, _entry("a.md"))
    first = journal.read_text(encoding="utf-8")
    _append(journal, project, _entry("b.md"))
    assert journal.read_text(encoding="utf-8").startswith(first)


@pytest.mark.parametrize("payload", ["[]", "null", "1", '"a string"'])
def test_valid_json_of_the_wrong_shape_is_a_journal_error(tmp_path: Path, payload: str) -> None:
    """These parse fine, then `event["event"]` raises `TypeError` -- NOT a `ValueError`, so it
    escapes the parse guard, and `finish_run` catches only `JournalError`/`ValidationError`.
    One such line would raise out of `finish_run` instead of returning `UNWIRED, record=None`."""
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    journal.write_text(payload + "\n", encoding="utf-8")
    with pytest.raises(JournalError, match="JSON object"):
        _read(journal, project)


def test_the_journal_is_one_object_per_line(tmp_path: Path) -> None:
    """Append-only means line-oriented; a pretty-printed entry cannot be appended to."""
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    _append(journal, project, _entry())
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "request"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `(cd science && uv run --frozen pytest tests/test_evidence_broker_journal.py -x)`
Expected: `ModuleNotFoundError: science_tool.evidence_broker.journal`.

- [ ] **Step 3: Write the module**

```python
"""The append-only record of what a run was shown.

OUTSIDE THE PROJECT TREE, for the reason `RunBaseline` is: a log inside the tree the actor can
write is not a record of what the actor was shown. Its path is resolved from `RunBaseline`, never
from argv -- a journal a caller can name is a journal a caller can substitute.

WHAT THIS BUYS IS BOUNDED, and the design does not claim otherwise. A same-uid actor can append to
it. A forged entry must name a path that really exists at the pinned commit, so it cannot
manufacture a file, and it leaves the forger's own fingerprints in an artifact the supervisor reads.
It is not a proof of exposure.

SPEND IS DERIVED BY COUNTING, never stored. There is no counter to reset, and truncating the journal
to buy rounds destroys the entries that make the truncator's own citations correspond -- self-
defeating rather than merely detected.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple

from science_model.evidence_broker import (
    MAX_BUDGET,
    MAX_INLINE_INPUTS,
    MAX_TARGET_BYTES,
    ExposureEntry,
    InlineInput,
    Outcome,
)

from science_tool.autonomy.baseline import reject_baseline_inside_project
from science_tool.findings.paths import (
    PathExistsError,
    PathSafetyError,
    create_regular_file_at,
    open_dir_anchored,
    open_lock_at,
    open_record_at,
    read_regular_fd,
    write_all,
)

_LOCK_SUFFIX = ".lock"

MAX_ENTRY_BYTES = 16 * MAX_TARGET_BYTES
"""One encoded line's ceiling, and the factor is arithmetic rather than a guess.

`MAX_TARGET_BYTES` is a pydantic `max_length`, which counts CHARACTERS, not bytes -- so the two
bounded fields (`target`, `pathspec`) can each be 4096 characters, each character can escape to
`\\uXXXX` (six bytes) in the JSON encoding, and 2 x 4096 x 6 = 49152. Sixteen times the character
bound is 65536, which covers that with room for the fixed vocabulary, the 64-character digest and
the 40-character commit. Getting this backwards -- assuming `max_length` bounds bytes -- would put
`MAX_ENTRY_BYTES` below what the model admits, which is the same write-what-you-cannot-read defect
one layer down."""

MAX_JOURNAL_BYTES = (MAX_BUDGET + MAX_INLINE_INPUTS) * MAX_ENTRY_BYTES
"""DERIVED, not chosen. A magic megabyte here would be a bound with no relationship to what the
model permits, and the gap between the two is a live failure mode rather than slack: if the model
admits inputs whose journal exceeds the read bound, a run can WRITE a journal it can never read
back. The first over-long request is accepted and journaled without reaching git; every later
request and the seal itself then fail on the oversized journal, and design §6 turns that into no
record at all. So the read bound is computed from the same constants that gate what can be
written, and `append_request` refuses any single line over `MAX_ENTRY_BYTES` before writing it.

The bound is needed at all because `journal.jsonl` is an actor-controlled NAME in an
actor-writable directory: without it, a planted enormous file is read whole into memory.
Exceeding it raises, which is design §6's `UNWIRED` -- fail closed, not truncate and carry on."""


class JournalHandle(NamedTuple):
    """The captured run directory, the OPEN journal, and the journal's leaf name.

    THREE FIELDS BECAUSE THERE ARE TWO OBJECTS TO PIN, NOT ONE. `dir_fd` anchors the directory,
    which is what `served/` is created inside. `fd` anchors the JOURNAL ITSELF, and it is the
    field a directory descriptor alone cannot substitute for: reopening `name` under `dir_fd` for
    each operation passes every check every time and still addresses a DIFFERENT INODE if the
    actor unlinks the name and drops an ordinary file in its place between them. The count would
    then be taken from one file and the append made to another -- and since the count is what
    enforces the budget, the spend simply disappears. `name` travels with them so a caller cannot
    pair one run's directory with another run's filename.

    Every function below takes the handle; none takes a path. That is what makes "no journal
    operation resolves a pathname" a property of the module's type signatures rather than a rule
    its authors have to remember.
    """

    dir_fd: int
    fd: int
    name: str


class JournalError(RuntimeError):
    """The journal could not be created, appended to, or read."""


def _encode_inline(inline: InlineInput) -> str:
    return json.dumps(
        {"event": "inline", "target": inline.target, "sha256": inline.sha256, "lines": inline.lines},
        sort_keys=True,
    )


def _encode_request(entry: ExposureEntry) -> str:
    return json.dumps(
        {
            "event": "request", "op": entry.op, "target": entry.target,
            "pathspec": entry.pathspec, "commit": entry.commit,
            "sha256": entry.sha256, "outcome": entry.outcome.value,
        },
        sort_keys=True,
    )


@contextmanager
def open_journal(path: Path, *, project_root: Path) -> Iterator[JournalHandle]:
    """Capture the run directory once and hand back the handle for every operation on it.

    TWO CHECKS, ASKING DIFFERENT QUESTIONS, NEITHER IMPLYING THE OTHER.
    `reject_baseline_inside_project` is lexical and asks whether the supervisor pointed this
    run's record inside the project tree -- a configuration mistake, decided on the pathname
    because the pathname is what was configured. `open_dir_anchored` is a filesystem walk and
    asks whether we can reach the directory without traversing something an actor planted --
    decided component by component with `O_NOFOLLOW`, because the pathname cannot answer it.

    AND THEN NOTHING RE-RESOLVES ANY NAME -- not the directory's and not the journal's. Both
    descriptors are opened here, once, and every operation is performed against them. A run
    directory holds `served/` and is therefore actor-writable, so BOTH names are names an actor
    can replace between any two operations, and the two failures are different:

    * re-walking the DIRECTORY per operation would let the lock and the append land in two
      different directories -- anchoring each step while leaving the sequence unanchored;
    * re-opening the JOURNAL per operation passes every check both times and still reads one
      inode and appends to another, because `unlink` plus a fresh ordinary file defeats
      `O_NOFOLLOW`, `S_ISREG` and `st_nlink` simultaneously -- none of them is a claim about
      identity. The count taken before the serve would then be a count of a file the append
      never touches, and the budget it enforces would silently stop being enforced.

    So the journal is opened ONCE, `O_RDWR | O_APPEND`, and both `read_journal` and
    `append_request` use that descriptor.
    """
    reject_baseline_inside_project(path, project_root)
    try:
        directory = open_dir_anchored(path.parent)
    except PathSafetyError as exc:
        raise JournalError(f"could not open the run directory {path.parent}: {exc}") from exc
    try:
        try:
            record = open_record_at(directory, path.name)
        except PathSafetyError as exc:
            raise JournalError(f"could not open journal {path}: {exc}") from exc
        try:
            yield JournalHandle(dir_fd=directory, fd=record, name=path.name)
        finally:
            os.close(record)
    finally:
        os.close(directory)


@contextmanager
def journal_lock(path: Path, *, project_root: Path) -> Iterator[JournalHandle]:
    """Serialize a whole serve, not merely the write, and yield the handle it is serialized on.

    HELD FOR THE DURATION OF THE SERVE (design §3.4.1), which is what makes the budget check
    atomic: two concurrent reviewers in one run that each counted, then each served, would both
    pass a check for the last remaining round.

    Yields the `JournalHandle` rather than `None` so the caller cannot lock one object and then
    write another. A caller that re-derived the journal from its pathname inside this block would
    have exactly the check/use gap the lock is supposed to close.
    """
    with open_journal(path, project_root=project_root) as handle:
        try:
            descriptor = open_lock_at(handle.dir_fd, handle.name + _LOCK_SUFFIX)
        except PathSafetyError as exc:
            raise JournalError(f"could not lock {path}: {exc}") from exc
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield handle
        finally:
            os.close(descriptor)


def create_journal(path: Path, *, project_root: Path, inline: tuple[InlineInput, ...]) -> None:
    """Create the journal exactly once and seed it.

    EXCLUSIVE CREATION, not `write_text`: reusing a journal path discards the exposure record of
    whatever run already owns it.

    Design §3.4.2's trust argument is TEMPORAL -- this runs at `start`, before any actor of this
    run exists -- and it covers the journal file, not the directories above it, which persist
    across runs and which a PREVIOUS run's actor could have redirected.

    SO THE RUN DIRECTORY IS CREATED BY THE ANCHORED WALK, NOT BY `Path.mkdir(parents=True)`.
    `mkdir(parents=True)` FOLLOWS LINKS: a planted symlink at any missing ancestor makes it
    create the remaining directories inside the LINK'S TARGET, and a refusal afterwards does not
    remove them. That is hazard 3 in `findings/paths.py`'s own header -- mutating before
    validating -- and "no bytes were written" is not a defence, because the directories are
    themselves a write, in a tree the path gate watches. `open_dir_anchored(create=True)` makes
    one component at a time inside the parent it has already captured and stops AT a link having
    created nothing beyond it. `create_regular_file_at` then supplies `O_EXCL` (the "opened once"
    rule) and `O_NOFOLLOW` (no redirect on the leaf) in one call, raising `PathExistsError` -- a
    `PathSafetyError` subclass -- for the already-exists case specifically, so that case can be
    reported precisely instead of by string matching.

    This does NOT go through `open_journal`, which opens an existing journal; here there is
    none yet.
    """
    reject_baseline_inside_project(path, project_root)
    try:
        directory = open_dir_anchored(path.parent, create=True)
    except PathSafetyError as exc:
        raise JournalError(f"could not create the run directory {path.parent}: {exc}") from exc
    try:
        try:
            descriptor = create_regular_file_at(directory, path.name)
        except PathExistsError as exc:
            raise JournalError(
                f"{path} already holds a journal; a run's exposure record is opened once"
            ) from exc
        except PathSafetyError as exc:
            raise JournalError(f"could not create journal {path}: {exc}") from exc
        try:
            for entry in inline:
                write_all(descriptor, (_encode_inline(entry) + "\n").encode("utf-8"))
        except PathSafetyError as exc:
            raise JournalError(f"could not seed journal {path}: {exc}") from exc
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)


def append_request(handle: JournalHandle, entry: ExposureEntry) -> None:
    """One line, `O_APPEND`, to the descriptor the count was taken from. Appends never rewrite.

    `write_all`, not `os.write`: a short write leaves a truncated line, which makes the whole
    journal unparseable -- design §6's `UNWIRED` -- while this function's caller believes the
    exposure was recorded.
    """
    line = (_encode_request(entry) + "\n").encode("utf-8")
    if len(line) > MAX_ENTRY_BYTES:
        raise JournalError(
            f"the encoded entry is {len(line)} bytes, over the {MAX_ENTRY_BYTES} bound that "
            f"keeps a full journal under {MAX_JOURNAL_BYTES}"
        )
    try:
        write_all(handle.fd, line)
    except PathSafetyError as exc:
        raise JournalError(f"could not append to journal {handle.name}: {exc}") from exc


def read_journal(handle: JournalHandle) -> tuple[ExposureEntry, ...]:
    """Parse every line or raise. A journal we cannot read is design §6's `UNWIRED`.

Read from `handle.fd` -- the descriptor `open_journal` opened and `append_request` writes to,
    so the count this produces is a count of the inode that will be appended to. The safety
    properties (`O_NOFOLLOW`, `O_NONBLOCK` plus `S_ISREG`, `st_nlink == 1`) were established once
    at open time by `open_record_at`; `read_regular_fd` adds the byte bound, so a journal that
    grew past `MAX_JOURNAL_BYTES` is refused rather than loaded.

    An `inline` event's `lines` is dropped rather than round-tripped: the authoritative line
    count is the sealed manifest's (`EvidenceSession.inline`), which is what §5.2 checks against,
    and a second copy in a field nothing validates is a value that can disagree.
    """
    try:
        text = read_regular_fd(handle.fd, MAX_JOURNAL_BYTES)
    except PathSafetyError as exc:
        raise JournalError(f"could not read journal {handle.name}: {exc}") from exc

    entries: list[ExposureEntry] = []
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JournalError(f"{handle.name} line {number} is not JSON: {exc}") from exc
        if not isinstance(event, dict):
            # `[]`, `null` and `1` are all valid JSON. Indexing them raises `TypeError`, which
            # is NOT a `ValueError` -- it would escape this function uncaught, and `finish_run`
            # catches only `JournalError`/`ValidationError`, so a journal holding one valid
            # non-object line would raise out of `finish_run` instead of returning design §6's
            # `UNWIRED, record=None`. Checked before indexing rather than caught after.
            raise JournalError(f"{handle.name} line {number} is not a JSON object")
        try:
            if event["event"] == "inline":
                entries.append(ExposureEntry(
                    op="inline", target=event["target"], commit="",
                    sha256=event["sha256"], outcome=Outcome.SERVED,
                ))
            elif event["event"] == "request":
                entries.append(ExposureEntry(
                    op=event["op"], target=event["target"], pathspec=event["pathspec"],
                    commit=event["commit"], sha256=event["sha256"],
                    outcome=Outcome(event["outcome"]),
                ))
            else:
                raise JournalError(f"{handle.name} line {number} has unknown event {event['event']!r}")
        except (KeyError, ValueError) as exc:
            raise JournalError(f"{handle.name} line {number} is not a journal event: {exc}") from exc
    return tuple(entries)


def count_requests(entries: tuple[ExposureEntry, ...]) -> int:
    """Count `request` events. `inline` events are the supervisor's own seeding and cost nothing.

    Named `count_requests`, not `requests_used`, because `Session.requests_used()` (Task 3) calls
    it from inside a method of the same name. Two spellings for one concept is worse than one, but
    a module-level function shadowed by the method that calls it is worse than both.
    """
    return len([entry for entry in entries if entry.op != "inline"])
```

**Note on `commit=""` for inline entries.** Inline inputs are not in the tree and have no commit.
The seal (Task 6) rewrites every inline entry's `commit` to the session's, which is what
`EvidenceExposure._one_evidence_surface` requires; the journal itself has no commit to record for
them. Task 6's step covering this is not optional — without it, sealing a run with any inline input
raises on the exposure's own validator.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `(cd science && uv run --frozen pytest tests/test_evidence_broker_journal.py)`
Expected: exit 0.

- [ ] **Step 5: Certify every guard in this module by mutation**

Each row names the *one* line to revert and the test that must fail. Run them one at a time,
restoring between rows — a mutation left in place makes the next row's result meaningless.

| Revert | Must fail | Why this mutation and not another |
|---|---|---|
| `create_regular_file_at(directory, path.name)` → `os.open(path, os.O_WRONLY \| os.O_CREAT \| os.O_TRUNC)` | `test_creating_over_an_existing_journal_refuses` | drops `O_EXCL`; a non-exclusive create silently discards the record of whatever run owns the path |
| wrap `json.loads` in `try: … except json.JSONDecodeError: continue` | `test_a_truncated_line_is_an_error_not_an_empty_journal` | a parser that skips damaged lines converts a tampered journal into a shorter honest one |
| delete the `isinstance(event, dict)` check | every parametrization of `test_valid_json_of_the_wrong_shape_is_a_journal_error`, **with `TypeError`** | the point is the exception *type*: `TypeError` is what escapes `finish_run`'s handler |
| `open_record_at(directory, path.name)` → `Path(...).open("a")` inside `append_request` (reconstructing the path) | all three parametrizations of `test_a_journal_replaced_after_creation_is_refused_not_followed` | if only the `symlink` id fails, the implementation kept `O_NOFOLLOW` and dropped `S_ISREG`/`st_nlink`, and the roster is short again |
| `open_dir_anchored(path.parent)` → `os.open(path.parent, os.O_RDONLY \| os.O_DIRECTORY)` | `test_a_symlinked_run_directory_is_refused` | leaf protection with a pathname-resolved parent is the shape this branch has now hit twice |
| `read_regular_fd(handle.fd, MAX_JOURNAL_BYTES)` → `read_regular_fd(handle.fd, 1 << 40)` | `test_a_journal_larger_than_the_bound_is_an_error` | mutate the **bound**, not the call: swapping the call for `path.read_text()` would fail several tests at once and prove none of them separately |
| delete `append_request`'s `len(line) > MAX_ENTRY_BYTES` check | `test_an_entry_over_the_line_bound_is_refused_before_it_is_written` | the write side of the bound; without it a run can journal what it can never read back |
| make `JournalHandle` carry `dir_fd`/`name` only, reopening with `open_record_at` inside each of `read_journal` and `append_request` | `test_the_journal_read_and_the_append_address_one_inode` | **the round-five P1.** Every safety check still passes on both opens — they are checks on two different inodes, and none of them is a claim about identity |
| `write_all(handle.fd, line)` → `os.write(handle.fd, line)` | `test_a_short_write_does_not_truncate_an_entry` | a short write raises nothing; the caller records a truncated line believing it recorded a whole one |
| `open_dir_anchored(path.parent, create=True)` → `path.parent.mkdir(parents=True, exist_ok=True)` then `open_dir_anchored(path.parent)` | `test_create_makes_nothing_through_a_symlinked_ancestor` | `mkdir(parents=True)` follows links and creates inside the target *before* the refusal — mutating before validating |

Three rows are deliberately *conjunctive checks made separable*: the `open_record_at` row must fail
on all three plants, and the last two rows exist because the previous draft had one revert claiming
two unrelated failures — which proves neither. A single failing parametrization means the guard was
narrowed, not that it held. Record each row's actual result — including any row that surprises you —
in the report.

- [ ] **Step 6: Prove the lock actually serializes**

Add a test that spawns two threads, each taking `journal_lock` and appending 50 entries, and asserts
all 100 lines parse and none is interleaved. Then mutate `journal_lock` to yield without calling
`fcntl.flock` and confirm... **it very likely still passes** — a single `write` of a short line is
usually atomic anyway. That is the finding, not a failure: record it, and instead assert the lock's
real property directly — that a second `journal_lock` on the same path **blocks while the first is
held**, using `fcntl.LOCK_EX | fcntl.LOCK_NB` from a second process and asserting `BlockingIOError`.
Do not ship the thread test as the lock's certification; a guard proven by a test that passes without
it is proven by nothing.

- [ ] **Step 7: Lint, type-check, commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/evidence_broker/journal.py science/tests/test_evidence_broker_journal.py
git commit -m "feat(evidence-broker): add the append-only exposure journal"
```

---

### Task 3: The session

**Files:**
- Create: `science/src/science_tool/evidence_broker/session.py`
- Test: `science/tests/test_evidence_broker_session.py`

**Interfaces:**
- Consumes: `serve.serve`, `serve.Served` (plan 2); `EvidenceRequest` (plan 2's `policy.py`);
  `EvidenceSession`, `ExposureEntry`, `Outcome` (Task 1); `journal.py` (Task 2).
- Produces:

```python
@dataclass(frozen=True)
class Receipt:
    outcome: Outcome
    sha256: str | None       # None for a refusal -- no bytes were served
    path: Path | None        # None for a refusal -- design §3.5 writes no file
    notice: str | None       # the policy's notice, or the budget refusal; None when served

class SessionError(RuntimeError): ...

class Session:
    def __init__(self, repo_root: Path, session: EvidenceSession) -> None
    def request(self, request: EvidenceRequest) -> Receipt
    def requests_used(self) -> int
```

**`served/` is derived from `session.journal_path.parent`, not passed in.** Two parameters for one
location is two sources of truth: a caller could pair run A's journal with run B's `served/`, and
both values would be individually well-formed so no validator could catch it.

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_evidence_broker_session.py`. Build a real temporary git repository (follow
`tests/test_evidence_broker_serve.py`'s existing fixture) and a `run_dir` under `tmp_path`.

Import the module under test as `session_module`
(`from science_tool.evidence_broker import session as session_module`), never as `session` — that
name is a local variable in nearly every test below, and the shadowing would make the AST guard
read `Session.__file__` off whatever object the last assignment left behind.

**The fixture must create the journal**, and this is not incidental: `open_journal` walks the run
directory's components and `open_record_at` refuses to create, so a session whose journal was never
opened raises rather than quietly starting one. That is the intended behaviour — an append to a run
whose record was never opened is exactly what the `start`-time creation rule exists to prevent — but
it means a fixture that only makes the directory produces a suite that fails everywhere for one
reason. Write it out:

```python
@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """OUTSIDE the project, like a real control-plane run directory."""
    directory = tmp_path / "control-plane" / "run-x"
    directory.mkdir(parents=True)
    return directory


@pytest.fixture
def session_model(project: Path, run_dir: Path) -> EvidenceSession:
    """The model alone, with NO journal on disk.

    Kept separate from `session_at` because the two containment tests below must reach
    `Session.__init__` with a `journal_path` that was never opened -- a fixture that created the
    journal first would make them assert about a path the constructor already accepted.
    """
    return EvidenceSession(
        # REQUIRED, and it must be the run slug without the `run:` prefix -- `RunBaseline`'s
        # validator (Task 4) refuses a session that names a different run than the baseline
        # holding it, so a fixture that omits or invents this fails at construction.
        session_id=run_dir.name,
        journal_path=run_dir / "journal.jsonl",
        commit=head_of(project),
        budget=1,
        surface_policy=SurfacePolicy(deny_prefixes=()),
        instrument=INSTRUMENT,
        inline=(),
    )


@pytest.fixture
def session_at(project: Path, session_model: EvidenceSession):
    def build(
        *, budget: int, deny_prefixes: tuple[str, ...] = (), inline_count: int = 0
    ) -> Session:
        inline = tuple(
            InlineInput(target=f"seed{n}.md", sha256="f" * 64, lines=1)
            for n in range(inline_count)
        )
        model = session_model.model_copy(update={
            "budget": budget,
            "surface_policy": SurfacePolicy(deny_prefixes=deny_prefixes),
            "inline": inline,
        })
        create_journal(model.journal_path, project_root=project, inline=inline)
        return Session(project, model)

    return build
```

```python
def test_a_denial_spends_a_round(session_at) -> None:
    """Free denials make probing the deny policy unlimited."""
    session = session_at(budget=3, deny_prefixes=("private",))
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="private/x.md"))
    assert receipt.outcome is Outcome.REFUSED
    assert session.requests_used() == 1


def test_a_malformed_pattern_spends_a_round(session_at) -> None:
    session = session_at(budget=3)
    receipt = session.request(EvidenceRequest(op=EvidenceOp.SEARCH, target="a\0b"))
    assert receipt.outcome is Outcome.REFUSED
    assert session.requests_used() == 1


def test_exhaustion_refuses_and_appends_nothing(session_at) -> None:
    """The load-bearing half. `requests_used` is DERIVED by counting these lines and the
    exposure validates `requests_used <= budget`, so journaling a post-exhaustion request
    makes the run's own seal reject its own record -- design §6, no record at all."""
    session = session_at(budget=1)
    session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert session.requests_used() == 1
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert receipt.outcome is Outcome.REFUSED
    assert session.requests_used() == 1          # NOT 2


def test_a_refusal_writes_no_served_file(session_at, run_dir) -> None:
    """Every refusal serves zero bytes, so content addressing maps all of them onto one
    `served/e3b0c442...` -- a real, empty, readable file indistinguishable from a file that
    was genuinely served empty."""
    session = session_at(budget=3, deny_prefixes=("private",))
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="private/x.md"))
    assert receipt.path is None
    assert receipt.sha256 is None
    assert list((run_dir / "served").glob("*")) == []


def test_a_defined_miss_does_write_its_marker(session_at, run_dir) -> None:
    """A miss is an ANSWER (design §6), and its marker bytes are what was served."""
    session = session_at(budget=3)
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="absent.md"))
    assert receipt.outcome is Outcome.MISS_ABSENT
    assert receipt.path is not None
    assert receipt.path.read_bytes() == MISS_MARKERS[Outcome.MISS_ABSENT]


def test_the_served_name_is_the_digest_of_the_bytes(session_at) -> None:
    """Content addressing is what removes the name from the actor's control."""
    session = session_at(budget=3)
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert receipt.path is not None
    assert receipt.path.name == hashlib.sha256(receipt.path.read_bytes()).hexdigest()


def test_two_requests_serving_identical_bytes_coincide(session_at, run_dir) -> None:
    session = session_at(budget=3)
    first = session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    second = session.request(EvidenceRequest(op=EvidenceOp.READ, target="copy-of-a.md"))
    assert first.path == second.path
    assert session.requests_used() == 2          # coinciding bytes still cost two rounds


def test_seeding_leaves_requests_used_at_zero(session_at) -> None:
    session = session_at(budget=3, inline_count=4)
    assert session.requests_used() == 0


def test_a_journal_inside_the_project_cannot_construct_a_session(project, session_model) -> None:
    """Design §3.5: `served/` is created under the same containment check as the journal.
    An unsafe session must not be CONSTRUCTIBLE -- every file it wrote into the tree would be
    a `report-only` path-gate denial, failing the run for doing what the design prescribes."""
    inside = session_model.model_copy(update={"journal_path": project / "runs" / "j.jsonl"})
    with pytest.raises(BaselineError, match="inside the project"):
        Session(project, inside)


def test_a_symlinked_journal_path_landing_in_the_project_is_refused(project, tmp_path, session_model) -> None:
    """`reject_baseline_inside_project` judges as-spelled AND as-resolved. A path spelled
    outside the tree may still land inside through a link the actor controls."""
    link = tmp_path / "outside"
    link.symlink_to(project / "runs")
    linked = session_model.model_copy(update={"journal_path": link / "j.jsonl"})
    with pytest.raises(BaselineError, match="inside the project"):
        Session(project, linked)


def test_a_truncated_file_at_the_digest_name_is_replaced(session_at, run_dir) -> None:
    """The existence check that isn't. `if not path.exists()` treats the NAME as proof of the
    CONTENT, so a write that died partway -- or anything else at that name -- is handed back
    whole on the next request, while the journal records the full payload's digest. Replay then
    confirms it, because replay re-serves from the commit and never opens `served/`.

    Staged directly rather than by patching `io.BufferedWriter.write`, which raises
    `TypeError: cannot set 'write' attribute of immutable type` -- verified in this venv.
    """
    session = session_at(budget=3)
    digest = hashlib.sha256(EXPECTED_BYTES).hexdigest()
    (run_dir / "served").mkdir(parents=True, exist_ok=True)
    (run_dir / "served" / digest).write_bytes(EXPECTED_BYTES[:3])
    receipt = session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert receipt.path is not None
    assert receipt.path.read_bytes() == EXPECTED_BYTES
    assert hashlib.sha256(receipt.path.read_bytes()).hexdigest() == receipt.path.name


def test_a_planted_leaf_symlink_is_replaced_not_written_through(session_at, project, run_dir) -> None:
    """Writing by pathname FOLLOWS SYMLINKS, and `served/` is actor-writable by design. A planted
    link aimed into the tree turns a serve into an in-tree write -- a path-gate denial produced
    by the broker itself. `replace_at` swaps the name for a regular file instead."""
    session = session_at(budget=3)
    victim = project / "victim.txt"
    victim.write_text("original\n", encoding="utf-8")
    digest = hashlib.sha256(EXPECTED_BYTES).hexdigest()
    (run_dir / "served").mkdir(parents=True, exist_ok=True)
    (run_dir / "served" / digest).symlink_to(victim)
    session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert victim.read_text(encoding="utf-8") == "original\n"
    assert not (run_dir / "served" / digest).is_symlink()


def test_a_planted_DIRECTORY_symlink_is_refused(session_at, project, run_dir) -> None:
    """THE ONE THE LEAF TEST DOES NOT COVER. `O_NOFOLLOW` on the temporary protects the final
    name; it does nothing for a re-resolved PARENT. The actor plants this AFTER construction, so
    the constructor's containment check has already passed -- which is why the write path is
    anchored to a descriptor rather than re-resolving `served/` by pathname each time."""
    session = session_at(budget=3)
    (run_dir / "served").symlink_to(project, target_is_directory=True)
    with pytest.raises(OSError):
        session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert list(project.glob("*.partial")) == []
    assert session.requests_used() == 0        # nothing delivered, so nothing recorded


def test_an_ancestor_swapped_inside_the_critical_section_is_not_followed(
    session_at, project, tmp_path, monkeypatch
) -> None:
    """THE ONE THE `served`-SYMLINK TEST DOES NOT COVER, and the reason `_write_served` takes the
    handle rather than reopening `self._run_dir`.

    Planting a symlink at the FINAL `served` component is still refused by an `O_NOFOLLOW` reopen
    of `self._served_dir` -- so that test cannot tell a pathname-resolved parent from an anchored
    one. Swapping an ANCESTOR can: `os.open(self._served_dir, ...)` re-resolves every component
    above `served`, lands in the project tree, and `O_NOFOLLOW` on the last one says nothing
    about it.

    The swap has to happen INSIDE the critical section, after the handle is captured -- doing it
    beforehand just makes `open_journal` refuse, which proves a different guard. `_serve` is the
    seam: it is called inside the lock and before `_write_served`, which is exactly the window.
    """
    session = session_at(budget=3)
    (project / "run-x").mkdir()
    control_plane = tmp_path / "control-plane"
    inner = session_module._serve

    def swap_then_serve(*args, **kwargs):
        if not control_plane.is_symlink():
            control_plane.rename(tmp_path / "control-plane-moved")
            control_plane.symlink_to(project, target_is_directory=True)
        return inner(*args, **kwargs)

    monkeypatch.setattr(session_module, "_serve", swap_then_serve)
    session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert list((project / "run-x").rglob("*")) == []


def _raising_oserror(*_args: object, **_kwargs: object) -> Path:
    """A `_write_served` that dies between the serve and the append.

    `*args`/`**kwargs` rather than the method's real signature: this stands in for a delivery
    that failed, and it must keep standing in when `_write_served` gains or loses a parameter.
    A stub pinned to today's arity turns a future signature change into a `TypeError` the test
    reports as a passing `pytest.raises(OSError)` failure, which is a test that broke silently.
    """
    raise OSError("disk full")


def test_a_failed_served_write_records_nothing(session_at, monkeypatch) -> None:
    """DELIVER FIRST, RECORD SECOND. An entry appended before delivery succeeds claims an
    exposure that never happened -- and replay confirms it, because replay re-serves from the
    commit and never consults `served/`. Fail closed: no bytes, no line, no round spent."""
    session = session_at(budget=3)
    monkeypatch.setattr(Session, "_write_served", _raising_oserror)
    with pytest.raises(OSError):
        session.request(EvidenceRequest(op=EvidenceOp.READ, target="a.md"))
    assert session.requests_used() == 0


def test_the_served_bytes_leave_the_tree_untouched(session_at, project) -> None:
    """§7's write-gate bullet, composed against the shipped gate rather than asserted:
    a reviewer that serves several files produces a ChangeSet that `evaluate` finds EMPTY."""
    session = session_at(budget=5)
    for target in ("a.md", "b.md", "copy-of-a.md"):
        session.request(EvidenceRequest(op=EvidenceOp.READ, target=target))
    change_set = extract_change_set(project, BASE, head_of(project))
    assert evaluate(change_set, tier=RunTier.REPORT_ONLY, report_path=None).denials == []
    assert change_set.changes == ()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `(cd science && uv run --frozen pytest tests/test_evidence_broker_session.py -x)`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write the module**

```python
"""The budget-enforcing session over `policy`, `serve` and `journal`.

STATE THAT BOUNDS A REQUESTER CANNOT LIVE IN THE REQUESTER. A budget constant beside a stateless
serve function documents a budget without imposing one, which is why this module exists at all.

EVERY REQUEST THAT REACHES `request` SPENDS A ROUND, including denials and invalid patterns: free
denials make probing the deny policy unlimited, and a spent round is also what makes two runs
comparable. The one exception is an EXHAUSTED budget, which appends nothing -- see `request`.

SERVING HAPPENS IN EXACTLY ONE PLACE, inside `request`'s locked critical section, so the count, the
budget check, the serve and the append cannot be separated. This module binds `serve` privately and
calls it once; that is a readability claim and NOT a security boundary -- any caller can import
`serve` directly, and Python offers no way to prevent it. The budget binds the session's own path,
which is the path the CLI and 2b's dispatch actually take.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from science_model.evidence_broker import (
    MAX_TARGET_BYTES,
    EvidenceSession,
    ExposureEntry,
    Outcome,
)

from science_tool.autonomy.baseline import reject_baseline_inside_project
from science_tool.evidence_broker.journal import (
    JournalHandle,
    append_request,
    count_requests,
    journal_lock,
    open_journal,
    read_journal,
)
from science_tool.findings.paths import create_regular_file_at, replace_at, unlink_at

from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
# Bound privately so this module's namespace does not re-export it. That is a readability
# claim, not a security boundary: any caller can import `serve` directly and Python offers no
# way to prevent it. The property that IS enforceable, and is what `budgeted` operationally
# means, is asserted in the suite -- one call site, inside the lock. See Task 3 step 6.
from science_tool.evidence_broker.serve import serve as _serve

_BUDGET_NOTICE = "evidence budget exhausted for this run"


class SessionError(RuntimeError):
    """The session could not answer at all -- distinct from a refusal, which is an answer."""


@dataclass(frozen=True)
class Receipt:
    """What the requester is told. NEVER the bytes themselves (design §3.5)."""

    outcome: Outcome
    sha256: str | None = None
    path: Path | None = None
    notice: str | None = None


class Session:
    """One run's evidence surface. Holds the round counter and the journal."""

    def __init__(self, repo_root: Path, session: EvidenceSession) -> None:
        self._repo_root = repo_root
        self._session = session
        # DERIVED, not a parameter. A separate `run_dir` argument is a second source of truth for
        # one location: nothing would stop a caller pairing run A's journal with run B's
        # `served/`, and no validator could catch it because both values would be individually
        # well-formed. `journal_path` is settable only by the supervisor at `start` (design
        # §3.4.1 -- none of the session's fields is CLI-settable), so deriving from it means the
        # two cannot disagree by construction rather than by check.
        self._run_dir = session.journal_path.parent
        self._served_dir = self._run_dir / "served"
        self._project_root = repo_root
        # CONTAINMENT ON THE CONSTRUCTOR, not at write time. `run_dir` is a parameter, and the
        # in-process interface design §3.4.1 offers 2b hands it in directly -- so without this
        # check a caller could aim `served/` into the project tree, where every written file
        # becomes a `report-only` path-gate denial and the run fails the gate for doing exactly
        # what this design tells it to do. Design §3.5 requires it ("created under the same
        # containment check as the journal"); checking here means an unsafe session cannot be
        # CONSTRUCTED, rather than failing on its first served byte.
        reject_baseline_inside_project(self._served_dir, repo_root)
        reject_baseline_inside_project(session.journal_path, repo_root)

    def requests_used(self) -> int:
        """Derived by counting `request` events. There is no counter to reset."""
        with open_journal(self._session.journal_path, project_root=self._project_root) as handle:
            return count_requests(read_journal(handle))

    def request(self, request: EvidenceRequest) -> Receipt:
        """Answer one request, refuse it, or halt.

        THE LOCK SPANS COUNT-CHECK-SERVE-APPEND, not merely the append. Two concurrent reviewers
        that each counted and then each served would both pass a check for the last round.

        AN EXHAUSTED BUDGET APPENDS NOTHING. `requests_used` is derived by counting these lines
        and `EvidenceExposure` validates `requests_used <= budget`, so a post-exhaustion line
        would make the run's own seal reject its own record -- and under design §6 that means no
        record at all. An actor that simply kept asking would silently convert its run to
        `UNWIRED`, turning ordinary actor misbehaviour into a supervisor-side failure.
        """
        # BOUNDS FIRST, BEFORE THE LOCK AND BEFORE THE SPEND. `ExposureEntry` caps `target` and
        # `pathspec` so a full journal stays under `MAX_JOURNAL_BYTES`; checking that only at
        # entry-construction time would mean the request is served, the round is spent, and THEN
        # a `ValidationError` propagates out of a locked block -- an actor halting its own run
        # with a long string. Refusing here costs nothing and is not an oracle: the answer is a
        # property of the requester's own string, decided before the policy is consulted, so it
        # discloses nothing about the tree or the deny list.
        for field, value in (("target", request.target), ("pathspec", request.pathspec)):
            if value is not None and len(value) > MAX_TARGET_BYTES:
                raise SessionError(
                    f"{field} is {len(value)} characters, over the {MAX_TARGET_BYTES} bound"
                )

        with journal_lock(
            self._session.journal_path, project_root=self._project_root
        ) as handle:
            # ONE CAPTURE FOR THE WHOLE CRITICAL SECTION. `handle` is the run directory the lock
            # was taken in; the count, the `served/` write and the append all go through it. Do
            # not call `self.requests_used()` here -- that opens a SECOND handle, which locks one
            # directory and counts another, and is the check/use gap wearing an anchored costume.
            if count_requests(read_journal(handle)) >= self._session.budget:
                return Receipt(outcome=Outcome.REFUSED, notice=_BUDGET_NOTICE)

            served = _serve(
                self._repo_root, self._session.commit, request, self._session.surface_policy
            )
            digest = hashlib.sha256(served.payload).hexdigest()

            # DELIVER FIRST, RECORD SECOND. The journal is the record of what the requester was
            # SHOWN. Appending before the write succeeds claims an exposure that may not have
            # happened: a failed write leaves the requester with no bytes and no receipt while
            # the seal copies an entry saying `served` -- and replay reproduces it perfectly,
            # because replay re-serves from the commit and never consults `served/`. The
            # reviewer would hold `FULL` coverage over a file it never received. Writing first
            # inverts the failure: bytes on disk with no journal line are bytes nothing counts,
            # the round is not spent, and no coverage is granted. Both orderings can fail; only
            # this one fails closed.
            path: Path | None = None
            if served.outcome is not Outcome.REFUSED:
                path = self._write_served(handle, digest, served.payload)

            append_request(
                handle,
                ExposureEntry(
                    op=request.op.value,
                    # THE AUTHORIZED SPELLING, not the requested one, and taken ONLY from what
                    # `serve` returned. Journaling `request.target` would record `a\b` for a read
                    # of `a/b`, and `LocationEvidence.path` normalizes -- so an honest citation
                    # would key differently and come back unserved. `serve` already resolves the
                    # refusal case to the raw form, so this site never chooses between two
                    # sources; a fallback here would reintroduce the raw spelling for any outcome
                    # that slipped through unstamped.
                    target=served.target,
                    pathspec=served.pathspec,
                    commit=self._session.commit,
                    sha256=digest,
                    outcome=served.outcome,
                ),
            )

            if served.outcome is Outcome.REFUSED:
                # No file: every refusal serves zero bytes, so content addressing would land
                # them all on one `served/e3b0c442...` -- a real, empty, readable file that
                # cannot be told apart from a genuinely empty served file.
                return Receipt(
                    outcome=served.outcome,
                    notice=served.denial.notice if served.denial is not None else None,
                )
            return Receipt(outcome=served.outcome, sha256=digest, path=path)

    def _write_served(self, handle: JournalHandle, digest: str, payload: bytes) -> Path:
        """`served/<sha256>`, written whole or not at all.

        THE ONE PLACE AN ACTOR WRITES IN THE CONTROL PLANE, and it is safe because nothing trusts
        it: replay re-serves every entry from the pinned commit, correspondence reads the manifest
        and the map it rebuilds, and `finish_run` never opens this directory.

        `if not path.exists(): path.write_bytes(...)` is WRONG here in two ways, and both are
        reachable without an attacker. A `write_bytes` that dies partway -- a full disk, a signal
        -- leaves the digest-named path in place holding PARTIAL bytes; the retry sees it exists,
        skips the write, journals the FULL payload's digest, and hands back the truncated file.
        Replay then confirms it, because replay re-serves from the commit and never opens
        `served/`, so the reviewer holds `FULL` coverage over content it never received. That is
        the delivery-ordering fail-open again, arriving through the existence check instead of
        through the append.

        And `write_bytes` FOLLOWS SYMLINKS. `served/` is actor-writable by design, so a planted
        `served/<digest>` symlink aimed into the project tree turns a serve into an in-tree write
        -- a path-gate denial at `report-only`, produced by the broker itself.

        `O_NOFOLLOW` ON THE LEAF IS NOT ENOUGH, and this is the repository's own rule: protecting
        the final name does not protect an operation whose PARENT is re-resolved by pathname.
        Between `Session.__init__`'s containment check and the first serve, the actor can replace
        `served` itself with a symlink to the project tree -- `mkdir(exist_ok=True)` then succeeds
        through it and every subsequent pathname resolution lands in-tree, `O_NOFOLLOW` on the
        temporary leaf notwithstanding. So `served/` is opened ONCE as a descriptor and every
        operation is anchored to it with `dir_fd`, which is exactly what `findings/paths.py`'s
        `*_at` family exists for. Those primitives are fd-anchored rather than project-anchored,
        so design §3.4.1's objection to that module does not reach them -- the same reasoning that
        admits `open_lock_at`.

        AND THE PARENT'S PARENT, WHICH IS WHY THIS TAKES `handle`. `served/` is opened relative to
        the RUN DIRECTORY DESCRIPTOR the lock was taken on, not by reopening `self._run_dir` --
        an absolute pathname whose own components the actor can redirect just as freely. The rule
        does not stop at one component up; it stops at a descriptor, and `handle.dir_fd` is the
        one this session already holds.
        """
        directory = self._open_served_dir(handle.dir_fd)
        try:
            temporary = f".{digest}.{os.getpid()}.partial"
            descriptor = create_regular_file_at(directory, temporary)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(payload)
                replace_at(directory, temporary, digest)
            except BaseException:
                unlink_at(directory, temporary)
                raise
        finally:
            os.close(directory)
        return self._served_dir / digest

    def _open_served_dir(self, run_dir: int) -> int:
        """A descriptor for `served/`, created if absent, never followed through a link.

        `run_dir` is the caller's already-captured descriptor, so this function resolves exactly
        one name and never a pathname. The `mkdir` may be a no-op (a later serve in the same run);
        the `O_NOFOLLOW` reopen is what decides, so a `served` that has since become a symlink
        raises here rather than being written through.
        """
        try:
            os.mkdir("served", dir_fd=run_dir)
        except FileExistsError:
            pass
        return os.open(
            "served", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=run_dir
        )
```

`request.op.value` is what `ExposureEntry.op` takes: `EvidenceOp` is a `StrEnum` whose members are
exactly `"read"`, `"search"`, `"history"`, matching the `Literal`.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `(cd science && uv run --frozen pytest tests/test_evidence_broker_session.py)`
Expected: exit 0.

- [ ] **Step 5: Certify every guard in `request` by mutation**

`request` holds five separate rules in twenty lines, and the obvious mutations do not map onto them
one-to-one — three of the six rows below exist because a more natural-sounding mutation either does
not compile or does not change behaviour. Run one row at a time, restoring between rows.

| Revert | Must fail | Note |
|---|---|---|
| replace the exhaustion branch's `return Receipt(...)` with an `append_request(handle, ExposureEntry(op=request.op.value, target=request.target, pathspec=None, commit=self._session.commit, sha256=hashlib.sha256(b"").hexdigest(), outcome=Outcome.REFUSED))` *before* the return | `test_exhaustion_refuses_and_appends_nothing` | "record the refusal too" is the plausible slip and the actual defect. Do **not** try to move the existing `append_request` call above the check — its `served` and `digest` arguments do not exist yet, so that mutation does not run at all |
| `>=` → `>` in the exhaustion check | some test | if none fails, the suite does not pin the off-by-one — add one asserting a budget of `N` permits exactly `N` requests, then re-run |
| delete the `if served.outcome is not Outcome.REFUSED:` guard, making `path = self._write_served(...)` unconditional | `test_a_refusal_writes_no_served_file` | this is the guard that controls file creation. The *other* `if served.outcome is Outcome.REFUSED:` further down only chooses which `Receipt` to build, so deleting that one leaves the file behaviour untouched and the test green |
| move the `append_request(...)` call *above* the `if served.outcome is not Outcome.REFUSED:` block | `test_a_failed_served_write_records_nothing` | the delivery-ordering rule. Both call sites exist at that point, so this one does run |
| `create_regular_file_at` + `replace_at` → `(self._served_dir / digest).write_bytes(payload)` | `test_a_planted_leaf_symlink_is_replaced_not_written_through` | `write_bytes` follows the link and modifies the victim. It does **not** fail the truncation test — an unconditional `write_bytes` overwrites the short file with the right bytes, so that test stays green and this row certifies only the symlink half |
| the same, but guarded: `if not (self._served_dir / digest).exists(): (self._served_dir / digest).write_bytes(payload)` | `test_a_truncated_file_at_the_digest_name_is_replaced` | the existence-check defect specifically. This is the mutation the truncation test was written against, and the row above is not a substitute for it |
| `self._open_served_dir(handle.dir_fd)` → `os.open(self._served_dir, os.O_RDONLY \| os.O_DIRECTORY \| os.O_NOFOLLOW)` | `test_an_ancestor_swapped_inside_the_critical_section_is_not_followed` | the round-three P1. It does **not** fail `test_a_planted_DIRECTORY_symlink_is_refused` — that test plants the *final* `served` component, which the mutation's own `O_NOFOLLOW` still refuses. Only swapping an **ancestor**, after the handle is captured, separates the two |
| drop `O_NOFOLLOW` from `_open_served_dir`'s reopen | `test_a_planted_DIRECTORY_symlink_is_refused` | what that test actually certifies, now that the row above is aimed at the ancestor case |

Record each row's actual result in the report, including any row that did not fail. Two rows here
exist because the previous draft named mutations that leave their claimed test green — a mutation
that does not fail is not evidence the guard holds, it is evidence the pair was never checked.

- [ ] **Step 6: Guard the unbudgeted path**

**Read this framing before writing the test.** §7 asks that "no unbudgeted path to `serve` is
exported", and the obvious guard for it is worthless twice over. `from …serve import serve` already
binds the name, so `session.serve` is reachable whatever the guard says, and `serve = serve` at module
scope is a no-op that would "prove" the guard while changing nothing. Worse, no structural check can
stop `from science_tool.evidence_broker.serve import serve` in a caller — Python has no such
boundary, and a guard that claims one is a guard narrower than its rule, which is this branch's
recurring defect.

So do not assert an unreachable property. Assert the one that is real and load-bearing: **inside this
module, `serve` is called exactly once, and that call is lexically inside `Session.request`'s
`journal_lock` block.** That is what "budgeted" means operationally — the count, the check, the serve
and the append are one critical section — and it is exactly what a later refactor would break.

Import it as `from science_tool.evidence_broker.serve import serve as _serve` so the module namespace
does not re-export it, then walk the module with `ast`:

```python
def _calls_journal_lock(expression: ast.expr) -> bool:
    """Is this `with` item a `journal_lock(...)` call?

    Matches the CALL, not the name: `with journal_lock as x` binds the function object and locks
    nothing, and a guard that accepted it would pass against code that never took the lock.
    """
    return (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "journal_lock"
    )


def test_serving_happens_only_inside_request_s_locked_critical_section() -> None:
    tree = ast.parse(Path(session_module.__file__).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "_serve"
    ]
    assert len(calls) == 1

    # SCOPED TO `Session.request`, not to "any locked block anywhere". A guard that accepts any
    # `with journal_lock(...)` in the module passes when `_serve` is moved into a NEW method
    # under its OWN lock -- outside the count/check/append critical section, which is the whole
    # property. Locate the method first, then the lock inside it.
    (klass,) = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Session"]
    (method,) = [n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == "request"]
    locked = [
        node for node in ast.walk(method)
        if isinstance(node, ast.With)
        and any(_calls_journal_lock(item.context_expr) for item in node.items)
    ]
    assert any(calls[0] in ast.walk(block) for block in locked)
```

Use `ast`, not a text scan — a text scan's scope is the whole file including the prose above, which
mentions `serve` five times. That is the mistake plan 2 made and fixed.

Certify it with **three** mutations, because the rule is a conjunction of three things: move the
`_serve(...)` call above the `with journal_lock(...)` line; add a second `_serve(...)` call anywhere;
and — the one the unscoped version missed — move the `_serve(...)` call into a new
`Session.peek(...)` method wrapped in its own `with journal_lock(...)`. All three must fail.

- [ ] **Step 6b: Extend the AST assertion to the whole critical section**

The obvious behavioural test — two threads, budget of one — cannot be made deterministic here, and
it is worth understanding why before reaching for it. Without synchronization it is a race that
usually passes for the wrong reason. And a barrier placed where it would matter, immediately before
counting, **deadlocks against the very lock it is testing**: thread A holds `journal_lock` and waits
at the barrier for thread B, which is blocked acquiring that lock and can never arrive. A guard that
either flakes or hangs is not a guard.

The deterministic form of the same property is structural, so extend step 6's assertion rather than
adding a thread test. What must hold is that **every operation shares one lock block** — the anchored
read, the count, the comparison, the serve and the append:

```python
    (block,) = locked                       # exactly one locked block in `request`
    inside = list(ast.walk(block))
    for name in ("read_journal", "count_requests", "_serve", "append_request"):
        assert any(
            isinstance(n, ast.Call)
            and name in (getattr(n.func, "id", None), getattr(n.func, "attr", None))
            for n in inside
        ), f"{name} is outside the locked critical section"
    # The budget comparison too -- a check performed before the lock is a check on a stale count.
    assert any(isinstance(n, ast.Compare) for n in inside)
```

`(block,) = locked` is doing real work: it fails if `request` grows a *second* lock block, which is
how count-then-serve would be split back apart while each half still sat "inside a lock".

Certify with a fourth mutation on top of step 6's three: hoist only the count — replace the
in-block `count_requests(read_journal(handle))` with a `self.requests_used()` call made *above* the
`with` — and confirm this fails. That is the exact refactor that reopens the
count-then-serve window, and it is invisible to a test that only asks whether `_serve` is locked.

If you want the thread test as well, keep it — but record in your report that it is a smoke test and
that the structural assertion is what certifies the property.

- [ ] **Step 7: Lint, type-check, commit**

```bash
(cd science && uv run ruff check && uv run pyright)
git add science/src/science_tool/evidence_broker/session.py science/tests/test_evidence_broker_session.py
git commit -m "feat(evidence-broker): enforce the round budget in a session"
```

---

### Task 4: Opening a brokered run

**Files:**
- Modify: `science/src/science_tool/autonomy/lifecycle.py:120-164` (`start_run`)
- Modify: `science/src/science_tool/autonomy/cli.py:97-176` (`start_command`)
- Modify: `science/src/science_tool/autonomy/baseline.py:30-42` (`RunBaseline.evidence`)
- Test: `science/tests/test_autonomy_lifecycle.py`, `science/tests/test_autonomy_cli.py`

**Interfaces:**
- Consumes: `EvidenceSessionSpec`, `EvidenceSession`, `InlineInput` (Task 1); `create_journal`,
  `open_journal`, `read_journal`, `JournalError` (Task 2); `control_plane.run_dir`, `control_plane.run_slug` (plan 1);
  `normalize_project_path` and `SubjectError` from `science_model.audit.subjects` — both new
  imports in `lifecycle.py`.
- Produces: `start_run(..., baseline_out: Path | None = None, evidence: EvidenceSessionSpec | None
  = None) -> RunBaseline` and `RunBaseline.evidence: EvidenceSession | None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_broker_spec_and_baseline_out_are_mutually_exclusive(project) -> None:
    """No silent fallback: a brokered run whose baseline was written somewhere else is
    refused rather than searched for."""
    with pytest.raises(BaselineError, match="mutually exclusive"):
        start_run(project, ..., baseline_out=tmp / "b.json", evidence=SPEC)


def test_one_of_the_two_is_required(project) -> None:
    with pytest.raises(BaselineError, match="requires"):
        start_run(project, ..., baseline_out=None, evidence=None)


def test_start_computes_the_inline_manifest_itself(project) -> None:
    """A supervisor that declared those numbers would be attesting to bytes it had not read."""
    seed = project / "private" / "rubric.md"          # in-tree, and inside a denied prefix:
    seed.parent.mkdir()                               # design §3.4's motivating case exactly
    seed.write_text("one\ntwo\n", encoding="utf-8")
    baseline = start_run(project, ..., evidence=spec_with(inline_paths=(Path("private/rubric.md"),)))
    assert baseline.evidence is not None
    (manifest,) = baseline.evidence.inline
    assert manifest.lines == 2
    assert manifest.sha256 == hashlib.sha256(seed.read_bytes()).hexdigest()


def test_an_inline_target_is_a_path_a_citation_could_name(project) -> None:
    """THE POINT OF THE NORMALIZATION. An inline target that `LocationEvidence` cannot express
    is a seeded file granted FULL coverage no review can ever reach."""
    baseline = start_run(project, ..., evidence=spec_with(inline_paths=(Path("private/rubric.md"),)))
    (manifest,) = baseline.evidence.inline
    assert LocationEvidence(path=manifest.target).path == manifest.target


def test_an_inline_path_outside_the_project_is_refused(project, tmp_path) -> None:
    """Readable, and provably unciteable. Refused at `start` rather than silently manifested."""
    outside = tmp_path / "prompt.md"
    outside.write_text("x\n", encoding="utf-8")
    with pytest.raises(BaselineError, match="project-relative"):
        start_run(project, ..., evidence=spec_with(inline_paths=(outside,)))


def test_start_creates_the_journal_and_seeds_it(project, tmp_path) -> None:
    """Design revision 12: there is no separate `evidence open`. A file is a legitimate trust
    channel at `start` SPECIFICALLY because there is no actor yet, and creating the journal is
    that same declaration."""
    baseline = start_run(project, ..., evidence=spec_with(inline_paths=(seed,)))
    with open_journal(baseline.evidence.journal_path, project_root=project) as handle:
        entries = read_journal(handle)
    assert [entry.op for entry in entries] == ["inline"]


def test_the_journal_is_created_before_the_baseline(project, monkeypatch) -> None:
    """ORDER IS LOAD-BEARING. A baseline that exists must imply a journal that exists: design
    §6 destroys the whole record for a brokered baseline beside a missing journal, so the
    failure window must be the harmless one (an orphan journal, no run) and not the fatal one
    (a run that can never be sealed)."""
    monkeypatch.setattr(lifecycle, "write_baseline", _raising)
    with pytest.raises(BaselineError):
        start_run(project, ..., evidence=SPEC)
    assert journal_path.exists()          # the orphan, which is the safe direction


def test_a_second_start_on_the_same_run_refuses(project) -> None:
    """Both artifacts are exclusive-create; whichever is checked first, the run is not reopened."""
    start_run(project, ..., short_id="abcd", started=STAMP, evidence=SPEC)
    with pytest.raises((BaselineError, JournalError)):
        start_run(project, ..., short_id="abcd", started=STAMP, evidence=SPEC)


def test_an_unbrokered_start_is_unchanged(project, tmp_path) -> None:
    """Without `--broker-spec`, nothing changes for runs that do not broker evidence."""
    baseline = start_run(project, ..., baseline_out=tmp_path / "b.json")
    assert baseline.evidence is None
```

- [ ] **Step 2: Run them and watch them fail**

Run: `(cd science && uv run --frozen pytest tests/test_autonomy_lifecycle.py -k broker -x)`

- [ ] **Step 3: Add the field to `RunBaseline`**

```python
    evidence: EvidenceSession | None = None

    @model_validator(mode="after")
    def _session_names_this_run(self) -> RunBaseline:
        """`session_id` is `run_slug(run_id)` or the baseline is refused.

        Design §4.3 specifies the field as "the run slug", but a value that is derived once at
        `start` and never checked again is a second identity for one run -- and this baseline is
        read back off disk by a different process, where the two can disagree without anything
        noticing. Validated HERE because `EvidenceSession` alone cannot see `run_id`; this is the
        same shape as `AutonomousRunRecord._exposure_is_bound_to_this_run`.
        """
        if self.evidence is not None and self.evidence.session_id != self.run_id.removeprefix(
            RUN_ID_PREFIX
        ):
            raise ValueError(
                f"the session names {self.evidence.session_id!r} but the run is {self.run_id!r}"
            )
        return self
```

**`RUN_ID_PREFIX`, not `control_plane.run_slug` — that import would not resolve.** `control_plane.py`
already imports `reject_baseline_inside_project` from `baseline.py`, so `baseline.py` importing
`run_slug` back is a cycle that fails at module initialization, not at call time. Nor is a local
import inside the validator the right answer: it would hide a layering inversion behind a deferral.
`RUN_ID_PREFIX` comes from `science_model.autonomous_runs`, which `baseline.py` already imports, and
prefix-stripping is all that is needed here — `run_slug`'s other job is *validating* an actor-supplied
handle, and `run_id` was built by `generate_run_id`, so there is nothing here to validate. The layered
version of the rule: the model boundary owns the spelling, `control_plane` owns the untrusted handle.

Add `RUN_ID_PREFIX` to `baseline.py`'s existing `science_model.autonomous_runs` import, and raise
`ValueError` rather than `BaselineError` — this is a pydantic validator, and pydantic wraps
`ValueError` into `ValidationError`, which `read_baseline` already converts to `BaselineError`.

Named `evidence`, and its policy field named `surface_policy` rather than reusing
`policy_identity` — that field is the autonomy *write-surface* policy, a different thing about a
different boundary, and one field standing for two policies is how they end up enforced as one.

Test both directions, and note carefully which mutation certifies which — they do not cross over,
because the two tests have different subjects.

- **`test_a_baseline_whose_session_names_another_run_is_refused`** constructs `RunBaseline`
  directly, so `start_run` is not in its path at all and no change to `start_run` can affect it.
  It is certified by **deleting the validator**.
- **`test_start_run_builds_an_agreeing_baseline`** is the one `start_run` can break. It is
  certified by having `start_run` set `session_id=run_id` — keeping the `run:` prefix, which is
  the plausible slip — and confirming *this* test fails. The validator then rejects the baseline
  `start_run` just built, so the failure surfaces as a `BaselineError` out of `start_run` rather
  than as an assertion.

Run both mutations. A single mutation here would certify the pair as a conjunction and neither
half on its own, which is the defect shape this branch has hit repeatedly.

- [ ] **Step 4: Rewrite `start_run`'s signature and opening**

```python
def start_run(
    project_root: Path,
    *,
    agent: str,
    model: str,
    tier: RunTier,
    short_id: str,
    started: datetime,
    baseline_out: Path | None = None,
    evidence: EvidenceSessionSpec | None = None,
) -> RunBaseline:
```

and, after `run_id` is generated and before the basis capture:

```python
    if (baseline_out is None) == (evidence is None):
        raise BaselineError(
            "start requires exactly one of a baseline path or a broker spec; they are mutually "
            "exclusive because a brokered run's baseline is DERIVED from the control plane, and "
            "a brokered run whose baseline was written somewhere else is refused rather than "
            "searched for"
        )
```

Then, once the basis is captured and before writing the baseline:

```python
    session: EvidenceSession | None = None
    if evidence is not None:
        directory = run_dir(project_root, run_id)
        baseline_out = directory / "baseline.json"
        session = EvidenceSession(
            session_id=run_slug(run_id),
            journal_path=directory / "journal.jsonl",
            commit=base_commit,
            budget=evidence.budget,
            surface_policy=evidence.surface_policy,
            instrument=evidence.instrument,
            inline=_read_inline_manifest(evidence.inline_paths, project_root=project_root),
        )
        # JOURNAL FIRST. A baseline that exists must imply a journal that exists: design §6
        # writes NO RECORD AT ALL for a brokered baseline beside a missing journal, so the
        # window this ordering leaves open is an orphan journal with no run -- harmless and
        # retryable -- rather than a run that can never be sealed.
        create_journal(session.journal_path, project_root=project_root, inline=session.inline)
```

with the manifest helper:

```python
def _read_inline_manifest(paths: tuple[Path, ...], *, project_root: Path) -> tuple[InlineInput, ...]:
    """`start` reads each path and computes its digest and line count ITSELF.

    `target` IS A NORMALIZED PROJECT-RELATIVE PATH, and the supplied paths must be too (design
    §4.3). Storing the supervisor's absolute path would produce a manifest entry NO CITATION CAN
    NAME: `LocationEvidence.path` runs `normalize_project_path`, which refuses an absolute path
    outright, so the inline input would carry `FULL` coverage under §5.1 that no `Evidence` value
    could ever reach -- a seeded file that is provably unciteable.

    That is not a limitation to work around. §3.4's motivating case is exactly in-tree: "an
    instrument that legitimately lives inside a denied prefix", seeded so it can be accounted
    for despite the policy denying it. A file outside the project can be read but never cited,
    so seeding one accomplishes nothing and is refused here rather than silently manifested.

    The normalized spelling is also what lets §5.1 compare an inline target against a read one
    -- "`FULL` supersedes `LINES`" is a statement about two entries naming ONE path.
    """
    manifest: list[InlineInput] = []
    for path in paths:
        try:
            target = normalize_project_path(str(path))
        except SubjectError as exc:
            raise BaselineError(
                f"inline input {path} is not a project-relative path: {exc}. An inline target "
                "that `LocationEvidence` cannot express is a seeded file no review can cite."
            ) from exc
        try:
            payload = (project_root / target).read_bytes()
        except OSError as exc:
            raise BaselineError(f"could not read inline input {target}: {exc}") from exc
        manifest.append(InlineInput(
            target=target,
            sha256=hashlib.sha256(payload).hexdigest(),
            lines=len(payload.splitlines()),
        ))
    return tuple(manifest)
```

Pass `evidence=session` into the `RunBaseline(...)` construction.

- [ ] **Step 5: Run the tests and watch them pass**

- [ ] **Step 6: Certify the ordering and the exclusion by mutation**

1. Swap `create_journal` to *after* `write_baseline` and confirm
   `test_the_journal_is_created_before_the_baseline` fails.
2. Change the mutual-exclusion condition to `if baseline_out is not None and evidence is not
   None:` and confirm `test_one_of_the_two_is_required` fails — the `==` spelling enforces both
   halves and the naive spelling enforces only one, which is exactly the
   "a guard that certifies a conjunction certifies neither half" shape.

- [ ] **Step 7: Add `--broker-spec` to the CLI**

```python
@click.option(
    "--broker-spec",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="EvidenceSessionSpec JSON. Mutually exclusive with --baseline-out; derives both "
         "control-plane paths. A file is safe HERE because no actor exists until start returns.",
)
```

`--baseline-out` loses `required=True` and gains `default=None`.

**The existing exception boundary does not cover any of the new failures — widen it deliberately.**
`start_command` today catches `(RunRecordError, ToolkitError, RepositoryStateError, BaselineError,
ExtractError)`. Brokered start adds three escapes, none of them in that tuple:

| New failure | Raises | Without the fix |
|---|---|---|
| `--broker-spec` file unreadable | `OSError` | traceback, exit 1 |
| spec JSON invalid or wrong shape | `pydantic.ValidationError` | traceback, exit 1 |
| journal already exists (a second `start` on one run) | `JournalError` | traceback, exit 1 |

Exit 1 is what the documented codes read as *quarantined*, so each of these would misreport a run
that never opened. Read and validate the spec inside the same `try`, and extend the tuple with
`(OSError, ValidationError, JournalError)`.

**`baseline_out` is reassigned inside `start_run`, so the command's own variable is still `None`.**
The existing payload does `"baseline_path": str(baseline_out)`, which for a successful brokered start
would report the string `"None"` — a receipt naming a path that does not exist, for the one flow whose
whole purpose is that the supervisor did not choose the path. Derive both from what was actually
written rather than recomputing the path calculation a second time:

```python
    directory = None if baseline.evidence is None else baseline.evidence.journal_path.parent
    payload = {
        ...,
        "baseline_path": str(baseline_out if directory is None else directory / "baseline.json"),
        "run_dir": None if directory is None else str(directory),
    }
```

`journal_path.parent` **is** `run_dir` — it is the value `start_run` used, read back off the baseline
it wrote, so the receipt cannot drift from the run even if the path calculation later changes. Assert
both fields in the CLI test: a receipt is only useful if it is true.

- [ ] **Step 8: Test the CLI exclusion, then commit**

Assert that passing both flags exits 2 and that passing neither exits 2, through
`CliRunner`. Then:

```bash
(cd science && uv run ruff check && uv run pyright && uv run --frozen pytest tests/test_autonomy_lifecycle.py tests/test_autonomy_cli.py tests/test_autonomy_baseline.py)
git commit -am "feat(autonomy): open a brokered run from a broker spec"
```

---

### Task 5: `science evidence serve`

**Files:**
- Create: `science/src/science_tool/evidence_broker/cli.py`
- Modify: the CLI root that registers command groups (find it with
  `grep -rn "autonomy_group" science/src/science_tool/ | grep add_command`)
- Test: `science/tests/test_evidence_broker_cli.py`

**Interfaces:**
- Consumes: `Session`, `Receipt` (Task 3); `run_dir`, `run_slug`, `ControlPlaneError` (plan 1);
  `read_baseline` (`autonomy/baseline.py`).
- Produces: `science evidence serve --session <run-id> --op <op> --target <str> [--pathspec <str>]`.

**The handle is the attack surface.** It is actor-supplied and becomes a path component, so
`--session ../../other-project/<slug>` is the obvious first attempt. `run_dir` already validates it
as a *generated run id* before any join (plan 1). What this task adds is the second half of §3.4.1's
two-part rule: **after loading, the baseline's own `run_id` must equal the handle.** Validating the
string and never checking what it opened leaves a directory that merely looks like a run id
resolving to another run's baseline.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_traversing_handle_is_refused_before_any_path_join(runner, project) -> None:
    result = runner.invoke(cli, ["evidence", "serve", "--session", "../../elsewhere",
                                 "--op", "read", "--target", "a.md"])
    assert result.exit_code == 2
    assert "run id" in result.output


def test_a_handle_whose_baseline_names_another_run_is_refused_after_loading(runner, project) -> None:
    """A name checked for shape and never for what it refers to."""
    # place a baseline carrying run_id X into the directory addressed by handle Y
    ...
    assert result.exit_code == 2
    assert "does not name" in result.output


def test_an_unbrokered_run_cannot_be_served(runner, project) -> None:
    """`evidence` is all-or-nothing; a baseline with no session has no surface to serve from."""


def test_the_receipt_never_carries_the_bytes(runner, brokered) -> None:
    """`BoundedSink` caps stdout and refuses rather than truncating, and served evidence must
    stay out of a conversational parent's context."""
    result = runner.invoke(cli, ["evidence", "serve", "--session", HANDLE,
                                 "--op", "read", "--target", "a.md", "--format", "json"])
    payload = json.loads(result.output)
    # `notice` is ALWAYS present and `null` when served -- a conditional key makes every
    # consumer branch on presence rather than on value, and the two tests in this file
    # disagreed about the wire format until this was pinned.
    assert set(payload) == {"outcome", "sha256", "path", "notice"}
    assert payload["notice"] is None
    assert FILE_CONTENT not in result.output


def test_a_refusal_prints_the_notice_and_no_path(runner, brokered) -> None:
    payload = json.loads(...)
    assert payload["outcome"] == "refused"
    assert payload["path"] is None
    assert payload["notice"] == POLICY_NOTICE


def test_the_cli_cannot_override_the_budget_or_the_policy(runner) -> None:
    """Asserted against the command's OWN parameter list, not a hand-written roster of flags:
    a flag added later must fail this loudly rather than land on the wrong side."""
    names = {param.name for param in serve_command.params}
    assert names & {"budget", "deny_prefixes", "surface_policy", "journal_path", "commit"} == set()
```

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Write the command**

Resolution order, and each step is load-bearing. `_fail` below is **not** an existing helper — define
it locally in this module as the plan's shorthand for "emit the message in the requested format and
exit 2", matching `autonomy/cli.py`'s existing `emit(...)` + `sys.exit(2)` shape. Task 6 needs the
same behaviour in `autonomy/cli.py` and must **not** import this one: a private helper reached across
CLI modules is how two commands come to share a failure path neither owns. Either duplicate the three
lines there or raise `click.UsageError`, which click renders and exits 2 on its own.

```python
    try:
        directory = run_dir(project_root, handle)          # validates the handle FIRST
    except (ControlPlaneError, BaselineError) as exc:
        _fail(f"could not address run {handle!r}: {exc}")

    try:
        baseline = read_baseline(directory / "baseline.json", project_root=project_root)
    except BaselineError as exc:
        _fail(f"could not read the baseline for {handle!r}: {exc}")

    if run_slug(baseline.run_id) != run_slug(handle):
        # The second half of §3.4.1's rule. `run_slug` on BOTH sides because `RunBaseline.run_id`
        # carries the `run:` prefix and the handle need not.
        _fail(f"the baseline at {directory} does not name run {handle!r}")

    if baseline.evidence is None:
        _fail(f"run {handle!r} was not opened with a broker spec; there is no surface to serve")

    session = Session(project_root, baseline.evidence)
    receipt = session.request(EvidenceRequest(op=EvidenceOp(op), target=target, pathspec=pathspec))
```

The payload is `{"outcome", "sha256", "path", "notice"}` and nothing else — never `payload`, never
the bytes. **All four keys are always present**, with `null` for the ones that do not apply: a
conditionally-omitted key makes every consumer branch on presence rather than on value. Let `ServeError` and `JournalError` propagate: design §6's last row is "anything else from
git raises, halts the run", and a broker that answered around an unreadable journal would be
answering from a record it could not read.

- [ ] **Step 4: Run the tests and watch them pass**

- [ ] **Step 5: Certify the second half of the handle rule**

Delete the `run_slug(baseline.run_id) != run_slug(handle)` check and confirm
`test_a_handle_whose_baseline_names_another_run_is_refused_after_loading` fails. Then delete only
the *first* validation (call `control_plane_root(...) / project_key(...) / handle` directly instead
of `run_dir`) and confirm the traversal test fails. **Both mutations are required**: two defenses
that each look proven because breaking both fails a test, while breaking either alone fails nothing,
is the conjunction defect plan 2 hit twice.

- [ ] **Step 6: Lint, type-check, commit**

```bash
(cd science && uv run ruff check && uv run pyright && uv run --frozen pytest tests/test_evidence_broker_cli.py)
# NAME EVERY FILE THE TASK TOUCHED, created AND modified. `-m` (not `-am`) means nothing is swept
# in unnamed -- which also means anything omitted here is simply left behind. This task creates two
# files and MODIFIES the CLI root that registers the group; without that third path the command
# does not exist on `science` and the next task's tests cannot invoke it.
git add science/src/science_tool/evidence_broker/cli.py science/tests/test_evidence_broker_cli.py \
        science/src/science_tool/cli.py
git commit -m "feat(evidence-broker): serve one request from a session handle"
git status --porcelain      # must be empty
```

---

### Task 6: The seal

**Files:**
- Modify: `science/src/science_tool/autonomy/lifecycle.py:167-262` (`finish_run`), `:310+`
  (`_finalize`)
- Modify: `science/src/science_tool/autonomy/cli.py` (`finish_command`)
- Test: `science/tests/test_autonomy_lifecycle.py`, `science/tests/test_evidence_broker_seal.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `AutonomousRunRecord.evidence` populated on every disposition, and
  `science autonomy finish --session <run-id>`.

**Sealing is a copy; checking is §5's.** The seal does not replay, does not verify inline entries
against the manifest, and does not judge outcomes. Revisions 1–8 had it replaying, and revision 9
removed that because a replaying seal refuses a forged-but-readable journal by writing *no record at
all* — a run vanishing for a reason §6's table does not list.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("disposition", ["clean", "quarantined", "unwired"])
def test_a_missing_journal_writes_no_record_in_every_disposition(project, disposition) -> None:
    """§6's rule is INDIFFERENT to disposition. Asserted three times rather than once: a seal
    placed late satisfies it on the clean path only, and that is exactly the shape a reviewer
    reading the code would call correct."""
    brokered = _open_brokered(project)
    _arrange(project, disposition)
    brokered.evidence.journal_path.unlink()
    outcome = finish_run(project, baseline_path=..., head=..., ...)
    assert outcome.disposition is RunDisposition.UNWIRED
    assert outcome.record is None


def test_the_exposure_is_sealed_on_a_quarantined_run(project) -> None:
    """A run that was brokered was brokered no matter how it ended."""
    outcome = ...
    assert outcome.disposition is RunDisposition.QUARANTINED
    assert outcome.record.evidence is not None
    assert outcome.record.evidence.requests_used == 2


def test_the_seal_copies_the_policy_the_manifest_and_the_protocol(project) -> None:
    """Copying them into the exposure is what makes the run record self-sufficient: a project
    move orphans UNSEALED sessions only."""
    exposure = outcome.record.evidence
    assert exposure.surface_policy == POLICY
    assert exposure.inline == baseline.evidence.inline
    assert exposure.replay_protocol == REPLAY_PROTOCOL_VERSION


def test_inline_entries_are_stamped_with_the_session_commit(project) -> None:
    """The journal has no commit for an inline input. Without this the exposure's own
    `_one_evidence_surface` validator rejects any run that seeded anything."""
    exposure = outcome.record.evidence
    assert {entry.commit for entry in exposure.entries} == {baseline.base_commit}


def test_a_forged_but_readable_journal_still_seals(project) -> None:
    """Sealing is a copy. A forged hash copied into the exposure is caught when the exposure is
    REPLAYED against the pinned commit -- which is plan 4, not here."""
    _append_forged_entry(journal)
    assert finish_run(...).record.evidence is not None


def test_an_unbrokered_run_seals_nothing(project) -> None:
    assert finish_run(...).record.evidence is None


def test_a_sealed_run_survives_the_control_plane_being_deleted(project) -> None:
    """The claim `evidence` exists to make true. Asserted by reading the record back after
    removing the whole control-plane directory."""
    record = finish_run(...).record
    shutil.rmtree(control_plane_root(project))
    (reloaded,) = [r for r in load_run_records(project) if r.id == record.id]
    assert reloaded.evidence == record.evidence
```

- [ ] **Step 2: Run them and watch them fail**

- [ ] **Step 3: Write the seal**

Add to `lifecycle.py`:

```python
def _seal_evidence(session: EvidenceSession, *, project_root: Path) -> EvidenceExposure:
    """Copy the journal into the record. Raises `JournalError` if it cannot be read.

    Inline entries are stamped with the session's commit: the journal has none to record for
    them, and `EvidenceExposure` requires every entry to agree with the exposure's commit.
    """
    with open_journal(session.journal_path, project_root=project_root) as handle:
        entries = read_journal(handle)
    stamped = tuple(
        entry.model_copy(update={"commit": session.commit}) if entry.op == "inline" else entry
        for entry in entries
    )
    return EvidenceExposure(
        commit=session.commit,
        budget=session.budget,
        requests_used=count_requests(stamped),
        instrument=session.instrument,
        surface_policy=session.surface_policy,
        inline=session.inline,
        replay_protocol=REPLAY_PROTOCOL_VERSION,
        entries=stamped,
    )
```

and in `finish_run`, **immediately after `read_baseline` succeeds** and before
`assert_gate_is_external`:

```python
    exposure: EvidenceExposure | None = None
    if baseline.evidence is not None:
        # FIRST, because this is the one failure that returns no record, and it is indifferent
        # to disposition. Placed with the other checks it would compute a full verdict and then
        # discard it -- and would invite an implementation that honours §6 on the clean path
        # only.
        try:
            exposure = _seal_evidence(baseline.evidence, project_root=project_root)
        except (JournalError, ValidationError) as exc:
            return RunOutcome(
                disposition=RunDisposition.UNWIRED,
                record=None,
                reason=(
                    f"the baseline says this run was brokered, but its exposure could not be "
                    f"sealed: {exc}. No record is written: `evidence=None` means NEVER BROKERED, "
                    "so a record here would assert something false about a run that was."
                ),
            )
```

Thread `exposure` into every `_finalize` call by giving `_finalize` an
`evidence: EvidenceExposure | None = None` keyword and passing it to `AutonomousRunRecord(...)`.

`_unwired` is a closure over `finish_run`'s locals, so `exposure` is *in scope* there — but its body
must still add `evidence=exposure` to the `_finalize(...)` call it makes. Being in scope is not being
passed, and this is the "fix applied to the headline and not to the path production takes" pattern in
miniature: the clean path is the one you will test first, and the two `_unwired` returns and the
`QUARANTINED` return are three more call sites that each need the keyword. Grep for `_finalize(` and
confirm every call site has it.

Note the reader for the last test: records load through
`science_tool.graph.autonomous_runs.load_run_records(project_root) -> list[AutonomousRunRecord]`.
There is no single-record reader.

- [ ] **Step 4: Run the tests and watch them pass**

- [ ] **Step 5: Certify the seal's position by mutation**

Move the seal block to just before the final `_finalize` call — the position a reviewer would
call natural — and confirm the *quarantined* and *unwired* parametrizations of
`test_a_missing_journal_writes_no_record_in_every_disposition` fail while the *clean* one still
passes. That asymmetry is the whole reason the test is parametrized; record it in the report.

Then remove the `entry.op == "inline"` stamping and confirm
`test_inline_entries_are_stamped_with_the_session_commit` fails with a `ValidationError` from
`_one_evidence_surface` — the two guards are each other's proof.

- [ ] **Step 6: Add `--session` to `finish`**

Mutually exclusive with `--baseline`, resolving through `run_dir` **from the supervisor's own
environment**. That resolution is what makes §3.4.2's containment argument true rather than
asserted: the actor cannot influence which control plane `finish` reads. Same `(a is None) == (b is
None)` spelling as Task 4, and the same pair of tests (both flags → exit 2; neither → exit 2).

**Apply §3.4.1's rule in BOTH halves here, not just the first.** The rule is two-part — parse the
handle as a generated run id *before* any join, then check the loaded baseline's own `run_id`
*after* — and Task 5 implements both for `evidence serve`. Doing only the first half here would
leave `finish --session Y` finalizing run X from a baseline swapped under Y's directory, which is
precisely the defect the second half exists to close and which Task 5 already refuses. A rule
enforced on one of the two commands that take a handle is enforced on neither, and this is the
"fix applied to the headline and not to the path production takes" pattern: the actor-facing command
is the one you think about, and `finish` is the one that writes the attestation.

**Check it where the baseline is actually read, which is inside `finish_run`.** Verifying in the CLI
and then handing `finish_run` a *path* leaves the classic check/use gap: `finish_run` re-reads that
path and attests whatever it finds the second time, so the check constrains a value the attestation
never used. Give `finish_run` the handle instead and compare immediately after its single read:

```python
def finish_run(
    project_root: Path,
    *,
    baseline_path: Path,
    expect_run: str | None = None,     # the `--session` handle, when one was given
    ...
) -> RunOutcome:
    ...
    try:
        baseline = read_baseline(baseline_path, project_root=project_root)
    except BaselineError as exc:
        return RunOutcome(disposition=RunDisposition.UNWIRED, record=None, reason=str(exc))

    if expect_run is not None and baseline.run_id.removeprefix(RUN_ID_PREFIX) != expect_run.removeprefix(
        RUN_ID_PREFIX
    ):
        # Compared against the model this function will actually attest, not against one the
        # caller read a moment earlier. `UNWIRED` with no record, like every other untrustworthy
        # baseline: identity is precisely what is in doubt.
        return RunOutcome(
            disposition=RunDisposition.UNWIRED, record=None,
            reason=f"the baseline at {baseline_path} names {baseline.run_id!r}, not {expect_run!r}",
        )
```

The CLI's job is then only to resolve `--session` through `run_dir` (which validates the handle
before any join) and pass both the derived path and the handle down.

Give it its own test — `finish --session Y` against a directory holding X's baseline yields
`UNWIRED`, `record=None`, and no record on disk — and its own mutation: delete the comparison and
confirm that test fails. Do not reuse Task 5's test; a guard proven on `serve` is not a guard on
`finish`. Add a second test that the check is inside `finish_run` rather than the CLI, by calling
`finish_run(..., expect_run=...)` directly.

- [ ] **Step 7: End-to-end**

One test that runs the real sequence against a real temporary git repository: `start --broker-spec`
→ two `evidence serve` calls (one served, one denied) → `finish --session` → read the record back and
assert `requests_used == 2`, that the denied entry carries `Outcome.REFUSED`, and that `served/`
holds exactly one file. This is §7's integration bullet minus its `append` clause, which is plan 4's.

- [ ] **Step 8: Full validation and commit**

```bash
# Subshells: these are sibling package roots, and a bare `cd science/model` after `cd science`
# resolves to `science/science/model`. Run each from the repository root.
(cd science && uv run ruff check && uv run pyright)
(cd science/model && uv run --frozen pytest)
(cd science && uv run --frozen pytest)  # ~10 min; the top-level agent runs this, not a subagent
# One created file and three MODIFIED ones. `-m` stages nothing unnamed, so an omitted path is
# silently dropped: this task's whole implementation lives in `lifecycle.py` and `autonomy/cli.py`.
git add science/tests/test_evidence_broker_seal.py science/tests/test_autonomy_lifecycle.py \
        science/src/science_tool/autonomy/lifecycle.py science/src/science_tool/autonomy/cli.py
git commit -m "feat(autonomy): seal a brokered run's exposure into its record"
git status --porcelain      # must be empty
```

---

## Self-review

**Spec coverage.** §3.3 → Task 2. §3.4 → Task 3. §3.4.1: handle → Task 5, open → Task 4, append and
spend → Tasks 2–3, seal → Task 6. §3.4.2's two flag pairs → Tasks 4 and 6. §3.5 → Task 3
(`served/`) and Task 5 (the receipt). §4.1 → Task 1 and Task 6. §4.3 → Tasks 1 and 4. §6's no-record
rule → Task 6.

**Deliberately not covered, and named so they are deferred rather than lost:** §5 entire, §4.2,
§4.2.1, and the `append` clause of §7's integration bullet — all plan 4.

**Type consistency.** `ExposureEntry.op` is a `Literal[...]` of the same four strings `EvidenceOp`
uses plus `"inline"`; `Session.request` passes `request.op.value`. `Outcome` has one definition, in
`science_model.evidence_broker`, from Task 1 step 8 onward. `EvidenceSession.journal_path` is a
`Path` and every consumer treats it as one. `run_slug` is applied to **both** sides of the handle
comparison in Task 5 because `RunBaseline.run_id` carries the `run:` prefix.

**Known sharp edge, stated rather than left to be discovered.** The count is re-read and re-parsed
from the whole journal on every request. That is deliberate — the count must not be cached anywhere
an actor could influence, and there is no counter to reset — but it makes each request O(journal).
At the budgets this design contemplates (tens of requests) that is irrelevant; if a future slice
raises budgets by orders of magnitude, the fix is a cached count *inside the lock's critical
section*, never a stored one.

**And the related trap it creates.** `Session.requests_used()` is the public spelling of that count
and it opens its *own* handle, which is right for a caller outside the lock and wrong inside one:
calling it from `request` would lock one captured directory and count through another. `request`
therefore calls `count_requests(read_journal(handle))` against the handle the lock yielded, and the
AST guard in Task 3 step 6b pins exactly that by requiring `read_journal` inside the lock block. The
two spellings are not redundant — one is the anchored form and one is the convenience form, and the
convenience form has no business in a critical section.
