# Supervised run harness — design (autonomous-audit Spec 2b)

**Status:** designed, unbuilt (revision 1)
**Spec 2b** of the autonomous-audit program (§0), scoped to **the loop, not the fleet**.

This slice builds one thing: a supervised autonomous run, end to end, with a deterministic
actor. It ships no concurrency, no assignment records, no LLM actor, and no dispatch policy.
The name "dispatch harness" comes from the program map; what 2b actually answers is *how a
supervised run is shaped*, and 2c inherits that shape when it introduces the first real
reviewer.

Every empirical claim below was measured against a scratch project on `main` at `1c3ce165`.
Where a claim is a reproduction, the observed output is quoted.

## 0. Where this sits

| Slice | Owns | State |
|---|---|---|
| Spec 1 | finding convergence — one emitted `AuditFinding`, fingerprint identity, the `doc/audits/cases/` store, trusted ingestion | **shipped** |
| Spec 2a | the evidence broker — what an agent was shown, recorded and replayable; the addressable control plane | **shipped**, seven plans, 4c merged at `1c11c922` |
| **Spec 2b** | **the supervised run loop — this document** | **designed here** |
| Spec 2c | `/science:review-plans` — the first lens agent | not designed |
| Spec 3 | how many confirmations promote a finding, and by whose authority | not designed |

2b consumes Spec 1's ingestion boundary and the autonomy envelope's S1 contract
(`start_run`, `finish_run`, the path gate, the commit marks). It consumes nothing from 2a:
the deterministic actor never touches the broker, so 2b's runs are **unbrokered**. 2a's
contribution to this program arrives with 2c, which needs `run_dir` to address a reviewer's
session.

## 1. The problem

Nothing calls `start_run`, an actor, and `finish_run` in sequence. The envelope shipped the
contract a run happens inside; Spec 1 shipped the boundary its output crosses; neither
shipped the thing that runs. There is no orchestrator and no command surface for one —
`commands/` holds nothing autonomy-related.

**The mechanism works; the wiring is unexercised.** Running it by hand end to end produces
cases:

```
$ science health --project-root <p> --format json --output <p>/doc/audits/run-report.json
$ science findings ingest <p>/doc/audits/run-report.json --project-root <p> \
    --attest-ingestion-ref … --attest-generated-at … --attest-producer-id … (×16)
16 new case(s), 16 occurrence(s) appended, 0 skipped as already recorded
```

So the frequently-repeated claim that "Spec 1's ingestion path has never processed a report"
is **false about the mechanism**. What is true, and is the gap 2b closes: no test feeds real
`science health` output to ingestion — every case in `test_findings_ingest.py` hand-builds
findings under a synthetic `health_checks` producer — and no supervisor exists to drive the
two commands as one attested run.

### 1.1 Three defects the first end-to-end run exposed

These were found by running the loop, not by reading it. Each is load-bearing for the design.

**`start_run` leaves the tree dirty before the actor exists.** `_capture`
(`autonomy/lifecycle.py:132`) materializes the graph, and `materialize_graph` writes into the
project. Measured immediately after `science autonomy start` on a clean repository:

```
$ git status --porcelain
?? knowledge/
```

A supervisor that then stages the actor's output with `git add -A` sweeps its own write into
the actor's attested range. Under `report-only` the gate denies it, and the first end-to-end
run quarantines for the supervisor's own materialization:

```
quarantined: 0 belief-basis delta(s), 1 path-gate denial(s), 1 commit-mark issue(s)
  denied: knowledge/graph.trig -- tier 'report-only' may write only the run's own report path
```

**The capture commit's author identity is fixed and undocumented.** `verify_marks`
(`autonomy/marks.py:55`) requires the commit author *name* to equal the run's `agent` and the
*email* to equal `AGENT_EMAIL` — `agent@science.local` (`marks.py:20`). Nothing surfaces this
to whoever writes the commit. The same run above also reported:

```
  mark: 005cae177fb9 -- author health-audit <a@a> is not this run's agent
        health-audit <agent@science.local>
```

**Committing the run record on the run's own branch makes every completed run an error.**
`_marked_commits` (`validate/checks/autonomous_runs.py:116`) scans `--all` deliberately — a
quarantined run keeps its branch, so scanning `HEAD` alone would hide exactly the commits the
check exists to find. `load_run_records` reads `runs/` from the *current tree*. Put the record
only on `auto/<slug>`, return to the starting branch, and the two land on opposite sides:

```
ERROR commit bb8f5afb4fa7 carries Science-Run: run:2026-08-02-health-audit-a1b2 but there is
no run record for it -- unwired: autonomous commits with no attestation [autonomous-runs.check]
```

With the record committed on the starting branch instead, the same project validates with the
check silent (`grep -c "autonomous-runs.check"` → `0`).

## 2. Scope

**In scope.**

1. `autonomy/harness.py` — the supervised run loop, as a library function returning a result.
2. `science autonomy run` — the CLI surface over it.
3. `science health --ingestion-ref` / `--generated-at` — so the attestation is dictated
   rather than read back.
4. `graph/health.py::expected_producer_ids` — the shared producer-set derivation.
5. The `start_run` restore postcondition (§4).

**Out of scope, deliberately.** Concurrency and N-way dispatch; assignment records; actor
selection (§3.2); LLM actors; brokered runs; belief-neutral actors (§4.4); served-evidence
retention; token and wall-clock caps.

**Adjacent 2a closure carried on this branch but not part of 2b's design** (§10): the 2a
design's two stale status rows, and the `InlineInput.lines` coverage-ceiling defect.

## 3. Architecture

### 3.1 The supervisor is deterministic code

Every value the supervisor attests — the tier, the run id, the verdict, the ingestion
provenance — is worth something only because its authority lives outside the actor. An
orchestrator that is itself a language-model session reasoning about the work is not outside
the actor; its attestations are self-attestation, which is the failure the envelope was built
to prevent. The harness is therefore ordinary Python invoked by a CLI command, and 2a's
statement that sessions are "held in the supervisor" already presumes this: a chat session
cannot hold a `Session` object.

**The actor owns bytes at one path. The harness owns everything else** — the working tree,
the branch, every commit, the commit identity, and every attested value.

### 3.2 There is one actor, and it is not selectable

`science autonomy run` runs `science health` as a subprocess. There is no `--actor` flag.

With exactly one actor, a selection flag is an interface designed from a single example. 2c
introduces the second actor and the generalization falls out of having two — including the
question this slice cannot answer well, which is how a generic actor learns the report path
and the dictated provenance. Declining to answer it now also keeps the toolkit from acquiring
"spawn an arbitrary command" as a capability in the slice that introduces supervision.

The subprocess boundary is kept even though the actor is our own code: the path gate and the
capture commit need real writes in the real tree, and the subprocess seam is precisely what 2c
replaces. Running health in-process would let harness and actor share state and would exercise
the trusted ingestion path rather than the untrusted one.

### 3.3 The report path is derived

`doc/audits/reports/<run-slug>.json`, from the run id. It cannot collide across runs, needs no
flag, and is the single path `report-only` permits (`autonomy/path_gate.py:123`).

## 4. The loop

Nine steps. The harness aborts on any failure before `finish_run`, leaving every branch and
every file intact for triage and writing no run record — which is `start_run`'s own stated
posture: it writes no record so that "a supervisor that dies mid-run leaves an unattested
branch rather than a half-attested one."

| # | Step | On failure |
|---|---|---|
| 1 | Assert HEAD is a named branch; remember it as the starting branch | abort |
| 2 | `start_run` → baseline (restores the tree itself, §4.1) | raises; abort |
| 3 | `git checkout -b auto/<slug>`, exclusively | abort — an existing branch is a run-id collision |
| 4 | Spawn `science health` as a subprocess | exit ∉ {0, 2} → abort (§4.2) |
| 5 | Assert HEAD is still `baseline.branch`; detached HEAD counts as a mismatch | abort, work left intact |
| 6 | `git add -A`; commit as `<agent> <agent@science.local>` with `Science-Run: <run-id>` | abort |
| 7 | `finish_run(head=HEAD, report_path=…)` | returns `unwired`; continue to 9 |
| 8 | If the disposition is `clean`: load and ingest (§5) | refusal is reported; continue to 9 |
| 9 | Switch to the starting branch, carrying the supervisor's uncommitted output; commit it with the supervisor's identity and **no trailer** | abort naming the dirty tree |

Step 1 exists because step 9 otherwise has no defined destination.

Step 9 runs on **every** disposition. A quarantined run dirties the tree exactly as a clean one
does — `runs/<slug>.md` from `_finalize`, plus `knowledge/graph.trig` from `finish_run`'s
re-materialization — and the next `start_run` refuses a dirty tree. Only step 8 is conditional
on the verdict.

The actor's report stays on the retained `auto/<slug>` branch. The record, the rebuilt graph,
and any cases land on the starting branch, outside `base..head`, where
`check_autonomous_runs` reads them.

### 4.1 `start_run` restores the tree

The residue in §1.1 is a defect in shipped code, not merely an inconvenience for the harness:
`science autonomy start` leaves an untracked `knowledge/graph.trig` behind today. The fix
belongs in `autonomy/lifecycle.py`, and the harness inherits it.

**The postcondition:** when `start_run` returns *or raises*, the working tree is at
`base_commit` — `git status --porcelain` is empty.

**It must hold on the error paths.** `start_run` materializes at `_capture` and can then raise
at least four more times: an unwired basis, an untraversable history, an uncitable tree, a
failed `write_baseline`. Residue after any of those leaves the project dirty and the *next*
`start_run` unable to open. The restore is therefore a tight `try`/`finally` around `_capture`
alone — restore and re-assert `base_commit` immediately, **before** the unwired, history,
citability, and baseline-writing results are processed — so that no later branch can return or
raise past it.

**Restore by predicate, not by roster.** `git checkout -- .` followed by `git clean -fd`
restores *to `base_commit`*. The tempting alternative — restoring `knowledge/graph.trig` by
name, since it is the only file materialization writes today — has a hole by construction: a
second materialized file would survive silently. The predicate form is exactly safe because
`assert_repository_is_at` proved the tree clean *including untracked files* immediately
before, so everything present afterwards is `start_run`'s own residue.

`finish_run` is deliberately **not** given the same postcondition. Its materialization happens
after the range is fixed and reflects the actor's work; step 9 commits it.

### 4.2 The actor's exit code

`science health` writes a complete report and *then* exits 2 when the project's acceptance
configuration is invalid (`graph/health_cli.py`, after `emit` and `sink.flush()`). Exit 2 is
therefore not actor failure. The harness accepts **0 and 2**; any other exit aborts. The
observed exit code is surfaced in the harness result.

### 4.3 Branch identity

`baseline.branch` is `auto/<run-id without the "run:" prefix>`, set by `start_run`, created by
nobody today — a clean run is achievable with no branch at all, because `finish_run` never
checks. The harness closes that: it creates the branch, and after the actor exits it asserts
HEAD still names it. `git rev-parse --abbrev-ref HEAD` returns `HEAD` on a detached HEAD, so
a string comparison already refuses that case; it is asserted deliberately rather than relied
on as an accident.

On mismatch the harness aborts without capture, `finish_run`, ingestion, or a record. Putting
this check inside `finish_run` would be worse: its record *requires* a `branch`, so on mismatch
it could only persist the intended branch as though it had been observed.

### 4.4 What step 9 assumes

Carrying uncommitted output across the branch switch is safe here because 2b's post-verdict
artifacts are untracked (`runs/`, `doc/audits/cases/`) or unchanged — measured.

A **belief-neutral** actor breaks that assumption. It edits entities and rebuilds
`knowledge/graph.trig`, leaving a modified *tracked* file whose base is `auto`'s HEAD while the
starting branch holds `base_commit`'s version. `git checkout` then either refuses or carries a
graph inconsistent with a branch that lacks the run's entity edits. **This is an open ruling
for whichever slice first ships a belief-neutral actor**, named rather than guessed at.

## 5. The attestation

### 5.1 Dictated, not read back

`science health` gains `--ingestion-ref` and `--generated-at`, required together; omitting both
preserves today's behaviour. `execute_health_report` already accepts both — only
`graph/health_cli.py:217-218` invents them, as `health:{uuid4().hex}` and `datetime.now(...)`.

The harness supplies **the run id** as the ingestion ref. Every case's provenance then resolves
to the run that found it, where `health:<random uuid>` resolves to nothing.

It dictates `generated_at` from the supervisor's clock. The precedent is 2a's own ruling that
`Review.at` is attested, not clocked: the value means *the instant the supervisor commissioned
this report*, which is what an attested provenance timestamp should mean. Reading the actor's
timestamp and attesting it back attests nothing.

### 5.2 The producer set

`graph/health.py::expected_producer_ids(checks, skip_checks, fast) -> frozenset[str]` is built
from the same `_select_health_checks` that `execute_health_report` calls, plus
`SCHEMA_INVALID_PRODUCER.producer_id` under the same sources condition
(`health.py:130-155`). There is no second list to drift.

Measured: 15 health checks with 15 unique producer ids, 8 requiring sources; a full run attests
those 15 plus `schema_invalid` — 16, which is what the successful ingestion above supplied.
`schema_invalid` never appears in `--list-checks`, which is why the naive set is wrong and why
a hand-driven operator discovers the right one only by failing once.

Enforcement is the mechanism Spec 1 already ships: ingestion refuses an inexact producer set, so
a wrong prediction fails closed and loudly. 2b adds no new trust mechanism here.

### 5.3 The report is still untrusted

The harness calls `load_report(project_root, report_path)` (`findings/ingest.py:153`) before
`ingest_report`. **Supervisor-chosen arguments do not make the bytes trusted** — the actor still
wrote them. `load_report` enforces path containment, symlink refusal, byte-size and JSON-nesting
ceilings, schema and version validation, and the finding-count limit. The harness then
constructs its own `IngestionProvenance` and ingests the loaded report in-process.

## 6. Toolkit changes

| File | Change |
|---|---|
| `autonomy/harness.py` | new — the loop of §4 |
| `autonomy/cli.py` | new `run` command |
| `autonomy/lifecycle.py` | `start_run` restore postcondition (§4.1) |
| `graph/health.py` | `expected_producer_ids` |
| `graph/health_cli.py` | `--ingestion-ref` / `--generated-at` |
| `budget/registry.py` | classify `autonomy run` (§6.1) |
| `docs/user-guide/cli-and-workflows.md` | the `run` command surface |

### 6.1 Registering the command is enforced, not optional

`test_budget_boundary.py::test_every_leaf_command_is_classified` requires every leaf CLI
command to appear in `BUDGETS`, `DEFERRED`, or `EXEMPTIONS`. Its three siblings —
`autonomy path-gate`, `autonomy start`, `autonomy finish` — are all `DeferredCommand`
entries at `budget/registry.py:281-292`, and `autonomy run` joins them: its output is one
fixed summary per invocation plus whatever `finish_run` reports, so it is bounded by the same
argument. Registering the surface also means the `cli-and-workflows.md` entry, which the same
suite covers.

`autonomy/marks.py`, `autonomy/path_gate.py`, `findings/ingest.py`, and
`validate/checks/autonomous_runs.py` are **consumed unchanged**. If the loop appears to need a
change in any of them, that is a signal the loop is wrong, not that the contract is.

## 7. Errors

Every step before `finish_run` aborts with a message naming the step, and writes no record.
`finish_run` never raises for an expected condition — it returns `unwired`, which blocks — so
steps 7 through 9 always complete. An ingestion refusal at step 8 is reported and does not stop
step 9: the record already exists and the tree must be left clean regardless.

The harness result carries the disposition, the actor's exit code, the ingestion outcome or
refusal, and the two commit shas.

## 8. Testing

The end-to-end test is the deliverable: run the loop against a fixture project; assert the
disposition is `clean`; assert the cases exist; assert `check_autonomous_runs` is silent from
the starting branch.

Mutation rows, in the discipline plan 4c established — apply one mutation alone, require a
*named* test to fail for the stated reason, restore, require it to pass:

| # | Mutation | Expected failure |
|---|---|---|
| 1 | Drop the restore postcondition | a report-only run quarantines on `knowledge/graph.trig` |
| 2 | Restore on return but not on `_capture`'s raise | the next `start_run` refuses a dirty tree |
| 3 | Restore `knowledge/graph.trig` by name | a second materialized path survives the restore |
| 4 | Skip the branch-identity check | off-branch actor work is attested to a branch it never touched |
| 5 | Create the auto branch non-exclusively | a run-id collision reuses another run's branch |
| 6 | Author the capture commit as anyone else | `verify_marks` reports a wrong-agent issue |
| 7 | Omit the capture commit's trailer | `verify_marks` reports no trailer |
| 8 | Commit the record on `auto` and switch away | `no run record for it` from `check_autonomous_runs` |
| 9 | Skip the post-verdict commit | the next `start_run` refuses |
| 10 | Ingest on a non-`clean` disposition | cases created from a denied run |
| 11 | Predict the producer set as a literal list | ingestion refuses (§8.1) |
| 12 | Read `generated_at` off the report | the attested value differs from the commissioned one (§8.2) |
| 13 | Start from a detached HEAD | refused before `start_run` |
| 14 | Accept only exit 0 from the actor | a project with an invalid acceptance configuration aborts |

### 8.1 Row 11 needs more than one fixture

A single full-health run does not kill a literal-list mutation: a list transcribed correctly
today matches the real set today. The row is certified across **full, `--fast`, and scoped
selections, covering both source-requiring and source-free cases** — or by registering a new
check and requiring the prediction to follow it without edit. A row that a correct literal
would also pass certifies nothing.

### 8.2 Row 12 needs a fake actor

Real `health` echoes the dictated timestamp, so "dictate it" and "read it back" are
observationally identical against the real actor. The row uses a stub actor that writes a
`generated_at` different from the commissioned one; only then does reading it back produce a
different attested value.

### 8.3 One convention with no guard

**"No `Science-Run` trailer on the post-verdict commit" is a convention, not a certifiable
invariant.** `verify_marks` reads only `base..head`, and `check_autonomous_runs` accepts any
marked commit whose run id has a record — so adding a trailer there breaks nothing observable.
It is stated as a convention and claims no mutation row.

## 9. Consequences

**Gained.** The first end-to-end autonomous run this toolkit has produced. Spec 1's ingestion
boundary exercised by a real producer rather than a synthetic one. Three defects in shipped
code closed, all three found by running the loop. A run id that resolves from a case's
provenance. `science autonomy start` that no longer dirties the tree it just declared clean.

**Costs.** A supervisor that owns the working tree, the branch, and two commits — a large
responsibility concentrated in one function. A `git clean -fd` inside `start_run`, safe only
because of the cleanliness assertion immediately preceding it. One actor, hard-wired.

**Deliberately not addressed.** Concurrency and fan-out; how a generic actor receives its
report path and provenance; belief-neutral actors across the branch switch (§4.4); whether a
quarantined run's branch is ever cleaned up; retention of anything.

## 10. Adjacent 2a closure

Carried on this branch, scoped as 2a closure rather than 2b:

1. **The 2a design's status rows.** `docs/plans/2026-07-30-agent-evidence-broker-design.md`
   still describes plan 4c as "implemented on `feat/evidence-broker-boundary` … not merged",
   and its §0 row still reads "plans 1–3 merged, 4a/4b designed at revision 17". Both are
   stale as of `1c11c922`. The document declares that table its only status claim.
2. **`InlineInput.lines` counts lines by a different rule than the checker.**
   `autonomy/lifecycle.py:309` sets `lines=len(payload.splitlines())`, which splits on CR, FF,
   LS, PS and NEL as well as LF; `evidence_broker/correspondence.py:49` counts `\n` only. Both
   feed the same `Full(...)` coverage ceiling in `_build_served_map`, so a payload containing a
   bare CR gives an inline input a higher ceiling than the same bytes served through `read` —
   an agent can cite a line the LF convention says does not exist, and the checker calls it
   covered. Brokered runs remain out of 2b's scope; this is a correction to 2a's own
   arithmetic.
