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
**revision 13** — §3.3 (journal), §3.4 (session), §3.4.1 (cross-process contract), §3.5 (CLI and
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
7. Line length 120. `cd science && uv run ruff check && uv run pyright` and
   `cd science/model && uv run --frozen pytest` both clean before every commit.
8. Conventional commits. No AI-attribution trailer or footer.
9. **`git commit -am` stages only tracked files.** Every task here creates new files; `git add`
   them explicitly before committing, and check `git status --porcelain` is clean afterwards. A
   task that "committed" while leaving its module untracked passes its own tests and fails the
   next task's import.

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

Run: `cd science/model && uv run --frozen pytest tests/test_evidence_broker_model.py -x`
Expected: `ImportError` on `REPLAY_PROTOCOL_VERSION` / `EvidenceExposure`.

- [ ] **Step 3: Add the vocabulary**

Append to `science/model/src/science_model/evidence_broker.py`:

```python
#: Bumped ONLY when serving or parsing changes -- the defined-miss markers, the canonical argv of
#: design §3.2.1, the hit-line parsing. NOT `toolkit_revision`: a signal that fires on every
#: release is a signal people learn to ignore, and a mismatch REFUSES honest historical work.
REPLAY_PROTOCOL_VERSION = 1


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

    target: str
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
    target: str
    pathspec: str | None = None
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
    budget: int = Field(ge=0)
    requests_used: int = Field(ge=0)
    instrument: InstrumentIdentity
    surface_policy: SurfacePolicy
    inline: tuple[InlineInput, ...] = ()
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
    budget: int = Field(ge=0)
    surface_policy: SurfacePolicy
    instrument: InstrumentIdentity
    inline: tuple[InlineInput, ...] = ()


class EvidenceSessionSpec(BaseModel):
    """The supervisor's declaration, read from JSON at `start`.

    `inline_paths` are PATHS, not hashes: `start` reads each one and computes its `sha256` and
    line count itself. A supervisor that declared those numbers would be attesting to bytes it
    had not necessarily read.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    budget: int = Field(ge=0)
    surface_policy: SurfacePolicy
    instrument: InstrumentIdentity
    inline_paths: tuple[Path, ...] = ()
```

Add to the module's imports: `from enum import StrEnum`, `from pathlib import Path`,
`from typing import Literal`, and extend the pydantic import to
`from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator`.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd science/model && uv run --frozen pytest tests/test_evidence_broker_model.py`
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

- [ ] **Step 9: Confirm plan 2's suite is untouched by the move**

Run: `cd science && uv run --frozen pytest tests/test_evidence_broker_serve.py
tests/test_evidence_broker_policy.py tests/test_evidence_broker_canonical.py`
Expected: exit 0. An import move that changes behaviour is not an import move.

- [ ] **Step 10: Lint, type-check, commit**

```bash
cd science && uv run ruff check && uv run pyright
cd ../science/model && uv run ruff check
git add science/model/src science/model/tests science/src/science_tool/evidence_broker/serve.py
git commit -m "feat(evidence-broker): seal the exposure vocabulary"
```

---

### Task 2: The journal

**Files:**
- Create: `science/src/science_tool/evidence_broker/journal.py`
- Test: `science/tests/test_evidence_broker_journal.py`

**Interfaces:**
- Consumes: `ExposureEntry`, `InlineInput`, `Outcome` (Task 1);
  `reject_baseline_inside_project` (`autonomy/baseline.py`); `open_lock_at`, `unlink_at`
  (`findings/paths.py`).
- Produces:

```python
class JournalError(RuntimeError): ...

def create_journal(path: Path, *, project_root: Path, inline: tuple[InlineInput, ...]) -> None
def append_request(path: Path, entry: ExposureEntry) -> None
def read_journal(path: Path, *, project_root: Path) -> tuple[ExposureEntry, ...]
def requests_used(entries: tuple[ExposureEntry, ...]) -> int

@contextmanager
def journal_lock(path: Path) -> Iterator[None]
```

`read_journal` returns `ExposureEntry` values directly — `inline` events become
`ExposureEntry(op="inline", …, outcome=Outcome.SERVED)`. The journal's `inline` event also carries
`lines`, which `ExposureEntry` has no field for; that number lives in the **manifest**
(`EvidenceSession.inline`), which is where §5.2 reads it from, so it is written to the journal for a
human reader and dropped on parse rather than round-tripped into a field nothing checks.

**Why `findings/paths.open_lock_at` and not a fresh lock.** Design §3.4.1 rejects
`findings/paths.py`'s *project-anchored* primitives — `open_dir_inside(project_root, …)`,
`resolve_inside(project_root, …)` — because they guarantee the result is **inside** a project root,
which is the negation of what the journal needs. That objection does not reach `open_lock_at(dir_fd,
name)`: it takes a descriptor, not a project root, and what it guarantees is "this lock is a regular
file with exactly one link, opened without following a symlink and without truncating" — precisely
the guarantee wanted here. Cite a mechanism by what it guarantees, not by which module it sits in.

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_evidence_broker_journal.py`:

```python
import json
from pathlib import Path

import pytest

from science_model.evidence_broker import ExposureEntry, InlineInput, Outcome
from science_tool.autonomy.baseline import BaselineError
from science_tool.evidence_broker.journal import (
    JournalError,
    append_request,
    create_journal,
    read_journal,
    requests_used,
)

COMMIT = "a" * 40


def _entry(target: str = "a.md", outcome: Outcome = Outcome.SERVED) -> ExposureEntry:
    return ExposureEntry(
        op="read", target=target, commit=COMMIT, sha256="e" * 64, outcome=outcome
    )


def test_create_then_append_then_read(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=(
        InlineInput(target="prompt.md", sha256="f" * 64, lines=12),
    ))
    append_request(journal, _entry())
    entries = read_journal(journal, project_root=project)
    assert [entry.op for entry in entries] == ["inline", "read"]
    assert requests_used(entries) == 1


def test_inline_seeding_costs_nothing(tmp_path: Path) -> None:
    """Seeding is not a request; charging for it is charging for evidence never asked for."""
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=tuple(
        InlineInput(target=f"in{n}.md", sha256="f" * 64, lines=1) for n in range(5)
    ))
    assert requests_used(read_journal(journal, project_root=project)) == 0


def test_a_refusal_is_counted(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    append_request(journal, _entry(outcome=Outcome.REFUSED))
    assert requests_used(read_journal(journal, project_root=project)) == 1


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
    append_request(journal, _entry())
    journal.write_text(journal.read_text()[:-8], encoding="utf-8")
    with pytest.raises(JournalError):
        read_journal(journal, project_root=project)


def test_appends_never_rewrite(tmp_path: Path) -> None:
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    append_request(journal, _entry("a.md"))
    first = journal.read_text(encoding="utf-8")
    append_request(journal, _entry("b.md"))
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
        read_journal(journal, project_root=project)


def test_the_journal_is_one_object_per_line(tmp_path: Path) -> None:
    """Append-only means line-oriented; a pretty-printed entry cannot be appended to."""
    journal, project = tmp_path / "j.jsonl", tmp_path / "project"
    project.mkdir()
    create_journal(journal, project_root=project, inline=())
    append_request(journal, _entry())
    lines = journal.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["event"] == "request"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd science && uv run --frozen pytest tests/test_evidence_broker_journal.py -x`
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

from science_model.evidence_broker import ExposureEntry, InlineInput, Outcome

from science_tool.autonomy.baseline import reject_baseline_inside_project
from science_tool.findings.paths import PathSafetyError, open_lock_at

_LOCK_SUFFIX = ".lock"


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
def journal_lock(path: Path) -> Iterator[None]:
    """Serialize a whole serve, not merely the write.

    HELD FOR THE DURATION OF THE SERVE (design §3.4.1), which is what makes the budget check
    atomic: two concurrent reviewers in one run that each counted, then each served, would both
    pass a check for the last remaining round.
    """
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            descriptor = open_lock_at(directory, path.name + _LOCK_SUFFIX)
        except PathSafetyError as exc:
            raise JournalError(f"could not lock {path}: {exc}") from exc
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)


def create_journal(path: Path, *, project_root: Path, inline: tuple[InlineInput, ...]) -> None:
    """Create the journal exactly once and seed it.

    Exclusive creation, not `write_text`: reusing a journal path discards the exposure record of
    whatever run already owns it. `open("x")` plus `reject_baseline_inside_project` is the
    `autonomy/baseline.py` pairing -- containment in the direction that is actually wanted --
    and NOT `findings/paths.py`, every primitive of which guarantees the result is INSIDE a
    project root.
    """
    reject_baseline_inside_project(path, project_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            for entry in inline:
                handle.write(_encode_inline(entry) + "\n")
    except FileExistsError as exc:
        raise JournalError(
            f"{path} already holds a journal; a run's exposure record is opened once"
        ) from exc
    except OSError as exc:
        raise JournalError(f"could not create journal {path}: {exc}") from exc


def append_request(path: Path, entry: ExposureEntry) -> None:
    """One line, `O_APPEND`. Appends never rewrite."""
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_encode_request(entry) + "\n")
    except OSError as exc:
        raise JournalError(f"could not append to journal {path}: {exc}") from exc


def read_journal(path: Path, *, project_root: Path) -> tuple[ExposureEntry, ...]:
    """Parse every line or raise. A journal we cannot read is design §6's `UNWIRED`.

    An `inline` event's `lines` is dropped rather than round-tripped: the authoritative line
    count is the sealed manifest's (`EvidenceSession.inline`), which is what §5.2 checks against,
    and a second copy in a field nothing validates is a value that can disagree.
    """
    reject_baseline_inside_project(path, project_root)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise JournalError(f"could not read journal {path}: {exc}") from exc

    entries: list[ExposureEntry] = []
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JournalError(f"{path} line {number} is not JSON: {exc}") from exc
        if not isinstance(event, dict):
            # `[]`, `null` and `1` are all valid JSON. Indexing them raises `TypeError`, which
            # is NOT a `ValueError` -- it would escape this function uncaught, and `finish_run`
            # catches only `JournalError`/`ValidationError`, so a journal holding one valid
            # non-object line would raise out of `finish_run` instead of returning design §6's
            # `UNWIRED, record=None`. Checked before indexing rather than caught after.
            raise JournalError(f"{path} line {number} is not a JSON object")
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
                raise JournalError(f"{path} line {number} has unknown event {event['event']!r}")
        except (KeyError, ValueError) as exc:
            raise JournalError(f"{path} line {number} is not a journal event: {exc}") from exc
    return tuple(entries)


def requests_used(entries: tuple[ExposureEntry, ...]) -> int:
    """Count `request` events. `inline` events are the supervisor's own seeding and cost nothing."""
    return len([entry for entry in entries if entry.op != "inline"])
```

**Note on `commit=""` for inline entries.** Inline inputs are not in the tree and have no commit.
The seal (Task 6) rewrites every inline entry's `commit` to the session's, which is what
`EvidenceExposure._one_evidence_surface` requires; the journal itself has no commit to record for
them. Task 6's step covering this is not optional — without it, sealing a run with any inline input
raises on the exposure's own validator.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd science && uv run --frozen pytest tests/test_evidence_broker_journal.py`
Expected: exit 0.

- [ ] **Step 5: Certify the two guards that matter by mutation**

1. Replace `path.open("x", …)` with `path.open("w", …)` and confirm
   `test_creating_over_an_existing_journal_refuses` fails. A non-exclusive create is the defect
   this guard exists for.
2. Wrap the `json.loads` call in `try: … except json.JSONDecodeError: continue` and confirm
   `test_a_truncated_line_is_an_error_not_an_empty_journal` fails. A parser that skips damaged
   lines converts a tampered journal into a shorter honest one.
3. Delete the `isinstance(event, dict)` check and confirm every parametrization of
   `test_valid_json_of_the_wrong_shape_is_a_journal_error` fails with `TypeError` — the point is
   the *exception type*, not merely that it raises, because `TypeError` is what escapes
   `finish_run`'s handler.

Record all three in the report.

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
cd science && uv run ruff check && uv run pyright
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
    notice: str | None       # the policy's notice, or the budget refusal

class SessionError(RuntimeError): ...

class Session:
    def __init__(self, repo_root: Path, session: EvidenceSession, *, run_dir: Path) -> None
    def request(self, request: EvidenceRequest) -> Receipt
```

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_evidence_broker_session.py`. Build a real temporary git repository (follow
`tests/test_evidence_broker_serve.py`'s existing fixture) and a `run_dir` under `tmp_path`:

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


def test_a_run_dir_inside_the_project_cannot_construct_a_session(project, session_model) -> None:
    """Design §3.5: `served/` is created under the same containment check as the journal.
    An unsafe session must not be CONSTRUCTIBLE -- every file it wrote into the tree would be
    a `report-only` path-gate denial, failing the run for doing what the design prescribes."""
    with pytest.raises(BaselineError, match="inside the project"):
        Session(project, session_model, run_dir=project / "runs")


def test_a_symlinked_run_dir_pointing_into_the_project_is_refused(project, tmp_path, session_model) -> None:
    """`reject_baseline_inside_project` judges as-spelled AND as-resolved. A path spelled
    outside the tree may still land inside through a link the actor controls."""
    link = tmp_path / "outside"
    link.symlink_to(project / "runs")
    with pytest.raises(BaselineError, match="inside the project"):
        Session(project, session_model, run_dir=link)


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

Run: `cd science && uv run --frozen pytest tests/test_evidence_broker_session.py -x`
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
from dataclasses import dataclass
from pathlib import Path

from science_model.evidence_broker import EvidenceSession, ExposureEntry, Outcome

from science_tool.autonomy.baseline import reject_baseline_inside_project
from science_tool.evidence_broker.journal import (
    append_request,
    journal_lock,
    read_journal,
    requests_used,
)
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

    def __init__(self, repo_root: Path, session: EvidenceSession, *, run_dir: Path) -> None:
        self._repo_root = repo_root
        self._session = session
        self._served_dir = run_dir / "served"
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
        return requests_used(read_journal(self._session.journal_path, project_root=self._project_root))

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
        with journal_lock(self._session.journal_path):
            if self.requests_used() >= self._session.budget:
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
                path = self._write_served(digest, served.payload)

            append_request(
                self._session.journal_path,
                ExposureEntry(
                    op=request.op.value,
                    target=request.target,
                    pathspec=request.pathspec,
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

    def _write_served(self, digest: str, payload: bytes) -> Path:
        """`served/<sha256>`. THE ONE PLACE AN ACTOR WRITES IN THE CONTROL PLANE, and it is safe
        because nothing trusts it: replay re-serves every entry from the pinned commit,
        correspondence reads the manifest and the map it rebuilds, and `finish_run` never opens
        this directory. An actor that rewrites its own served files changes what it can read and
        nothing about what it can prove.
        """
        self._served_dir.mkdir(parents=True, exist_ok=True)
        path = self._served_dir / digest
        if not path.exists():
            path.write_bytes(payload)
        return path
```

`request.op.value` is what `ExposureEntry.op` takes: `EvidenceOp` is a `StrEnum` whose members are
exactly `"read"`, `"search"`, `"history"`, matching the `Literal`.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd science && uv run --frozen pytest tests/test_evidence_broker_session.py`
Expected: exit 0.

- [ ] **Step 5: Certify the budget by mutation, in both directions**

1. Move the `append_request` call *above* the exhaustion check and confirm
   `test_exhaustion_refuses_and_appends_nothing` fails.
2. Change `>=` to `>` in the exhaustion check and confirm a test fails. If none does, the suite
   does not pin the off-by-one — add one asserting a budget of `N` permits exactly `N` requests.
3. Delete the `if served.outcome is Outcome.REFUSED` early return so refusals write a file, and
   confirm `test_a_refusal_writes_no_served_file` fails.

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
def test_serving_happens_only_inside_the_locked_critical_section() -> None:
    tree = ast.parse(Path(session.__file__).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "_serve"
    ]
    assert len(calls) == 1
    locked = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.With)
        and any(_calls_journal_lock(item.context_expr) for item in node.items)
    ]
    assert any(calls[0] in ast.walk(block) for block in locked)
```

Use `ast`, not a text scan — a text scan's scope is the whole file including the prose above, which
mentions `serve` five times. That is the mistake plan 2 made and fixed.

Certify it with **two** mutations, because one call site inside one `with` block is a conjunction:
move the `_serve(...)` call above the `with journal_lock(...)` line (confirm it fails), and add a
second `_serve(...)` call anywhere in the module (confirm it fails). Passing only one of these means
the guard pins only one half.

- [ ] **Step 7: Lint, type-check, commit**

```bash
cd science && uv run ruff check && uv run pyright
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
  `JournalError` (Task 2); `control_plane.run_dir`, `control_plane.run_slug` (plan 1);
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
    entries = read_journal(baseline.evidence.journal_path, project_root=project)
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

Run: `cd science && uv run --frozen pytest tests/test_autonomy_lifecycle.py -k broker -x`

- [ ] **Step 3: Add the field to `RunBaseline`**

```python
    evidence: EvidenceSession | None = None
```

Named `evidence`, and its policy field named `surface_policy` rather than reusing
`policy_identity` — that field is the autonomy *write-surface* policy, a different thing about a
different boundary, and one field standing for two policies is how they end up enforced as one.

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
cd science && uv run ruff check && uv run pyright && uv run --frozen pytest tests/test_autonomy_lifecycle.py tests/test_autonomy_cli.py tests/test_autonomy_baseline.py
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
    assert set(payload) == {"outcome", "sha256", "path"}
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

Resolution order, and each step is load-bearing:

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

    session = Session(project_root, baseline.evidence, run_dir=directory)
    receipt = session.request(EvidenceRequest(op=EvidenceOp(op), target=target, pathspec=pathspec))
```

The payload is `{"outcome", "sha256", "path", "notice"}` and nothing else — never `payload`, never
the bytes. Let `ServeError` and `JournalError` propagate: design §6's last row is "anything else from
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
cd science && uv run ruff check && uv run pyright && uv run --frozen pytest tests/test_evidence_broker_cli.py
# `git add` explicitly: this task CREATES two files, and `commit -am` stages only tracked ones.
git add science/src/science_tool/evidence_broker/cli.py science/tests/test_evidence_broker_cli.py
git commit -am "feat(evidence-broker): serve one request from a session handle"
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
    entries = read_journal(session.journal_path, project_root=project_root)
    stamped = tuple(
        entry.model_copy(update={"commit": session.commit}) if entry.op == "inline" else entry
        for entry in entries
    )
    return EvidenceExposure(
        commit=session.commit,
        budget=session.budget,
        requests_used=requests_used(stamped),
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

- [ ] **Step 7: End-to-end**

One test that runs the real sequence against a real temporary git repository: `start --broker-spec`
→ two `evidence serve` calls (one served, one denied) → `finish --session` → read the record back and
assert `requests_used == 2`, that the denied entry carries `Outcome.REFUSED`, and that `served/`
holds exactly one file. This is §7's integration bullet minus its `append` clause, which is plan 4's.

- [ ] **Step 8: Full validation and commit**

```bash
cd science && uv run ruff check && uv run pyright
cd science/model && uv run --frozen pytest
cd ../ && uv run --frozen pytest        # ~10 min; the top-level agent runs this, not a subagent
# `git add` explicitly: this task CREATES a test file, and `commit -am` stages only tracked ones.
git add science/tests/test_evidence_broker_seal.py
git commit -am "feat(autonomy): seal a brokered run's exposure into its record"
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

**Known sharp edge, stated rather than left to be discovered.** `Session.requests_used()` re-reads
and re-parses the whole journal on every call, and `request` calls it inside the lock. That is
deliberate — the count must not be cached anywhere an actor could influence, and there is no counter
to reset — but it makes each request O(journal). At the budgets this design contemplates (tens of
requests) that is irrelevant; if a future slice raises budgets by orders of magnitude, the fix is a
cached count *inside the lock's critical section*, never a stored one.
