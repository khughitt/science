# Spec 2b — mutation ledger

Design §8. Twenty-nine rows, each certified by the plan-4c discipline: apply **one** mutation
alone, require a **named** test to fail **for the stated reason**, revert, require that same
test to pass before the next row.

**Production baseline:** `51a22c07` (`feat(autonomy): register the supervised run command
surface`) — the tree every mutation was applied to and reverted back to. Only
`science/tests/test_autonomy_harness.py` differs from it in the commit that carries this
ledger; no production file was left changed.

A row whose test fails for a *different* reason than the one stated certifies nothing, so the
observed result below records the actual failure text rather than "fails". Every row was also
re-run after reverting; all 29 reverted runs exited 0.

## Reading the table

`Test node` is the node **as it exists**, which is not always the node the implementation plan
named — Tasks 5, 6 and 9 renamed and reorganized tests after the plan was written. Rows whose
plan-named node did not exist are listed under [Drift](#drift-from-the-plans-row-table).

## Rows 1–9 — the loop

| # | Mutation | Test node | Observed result |
|---|---|---|---|
| 1 | Delete the `try`/`finally` restore in `start_run` | `test_autonomy_start_restore.py::test_start_leaves_no_materialization_residue` | KILLED — `AssertionError: assert '?? knowledge/' == ''`; the materialized graph is left in the tree |
| 2 | Restore after `_capture` returns, not in a `finally` | `test_autonomy_start_restore.py::test_start_removes_its_residue_when_it_raises` | KILLED — `AssertionError: assert '?? knowledge/' == ''`; `_capture` raised, so the trailing restore never ran |
| 3 | Restore `knowledge/graph.trig` by name instead of restoring the tree | `test_autonomy_git_writes.py::test_restore_worktree_discards_modifications_and_untracked_files` | KILLED — `AssertionError: assert '?? new.txt\n?? sub/' == ''`; a named-path restore leaves everything it did not name |
| 4 | Delete the `current_branch != baseline.branch` check | `test_autonomy_harness.py::test_an_actor_that_leaves_the_branch_is_refused` | KILLED — `Failed: DID NOT RAISE HarnessError`; the wandering actor's run completed |
| 5 | `create_branch` uses `checkout -B` instead of `-b` | `test_autonomy_harness.py::test_an_existing_auto_branch_refuses_the_run` | KILLED — `Failed: DID NOT RAISE HarnessError`; `-B` resumed the colliding branch |
| 6 | Author the capture commit as the supervisor | `test_autonomy_harness.py::test_the_capture_commit_carries_the_agent_authorship_and_the_run_trailer` | KILLED — `assert 'science-supervisor <supervisor@science.local>' == 'health-audit <agent@science.local>'` |
| 7 | Drop the `Science-Run` trailer from the capture message | `test_autonomy_harness.py::test_a_supervised_run_completes_and_leaves_the_tree_clean` | KILLED — `assert <RunDisposition.QUARANTINED> is <RunDisposition.CLEAN>`; `verify_marks` refuses the unmarked commit |
| 8 | `_settle` before `switch_branch` | `test_autonomy_harness.py::test_the_autonomous_runs_check_is_silent_from_the_starting_branch` | KILLED — one `Result(severity=ERROR, ...)` observation: `commit f39f275fdc3b carries Science-Run: run... missing-record`; the record commit landed on `auto/<slug>`, so the starting branch's tree cannot see it |
| 9 | Return before `_settle` | `test_autonomy_harness.py::test_a_supervised_run_completes_and_leaves_the_tree_clean` | KILLED — `assert 'auto/2026-08-02-health-audit-a1b2' == 'main'`; the operator is stranded on the run's branch |

## Rows 10–14 — attestation and the actor

| # | Mutation | Test node | Observed result |
|---|---|---|---|
| 10 | Ingest regardless of disposition | `test_autonomy_harness.py::test_a_quarantined_run_ingests_nothing` | KILLED — `assert IngestOutcome(records_written=31, ...) is None` against a `QUARANTINED` outcome |
| 11 | Replace `expected_producer_ids`' derivation with a literal 16-element list | `test_health_attested_provenance.py::test_the_prediction_equals_what_the_report_declares[fast]` | KILLED — extra items in the predicted set (`layered_claim_migration`, `invalid_entity_aspects`, …): the literal is today's *full* set and the `fast` selection declares 7 |
| 12 | Read `generated_at` from the loaded report | `test_autonomy_harness.py::test_the_attested_instant_is_the_commissioned_one` | KILLED — `assert IngestOutcome(...) is None`; a self-sourced attestation agrees with the shifted report instead of refusing it |
| 13 | Accept a `None` starting branch | `test_autonomy_harness.py::test_a_detached_head_is_refused_before_the_run_opens` | KILLED — the expected `HarnessError` never arrives; the run proceeds to `switch_branch(root, None)` and dies with `TypeError: expected str, bytes or os.PathLike object, not NoneType`. Detached HEAD was not refused before the run opened, which is the stated reason; the raised type differs because nothing downstream normalizes it. |
| 14 | Accept only exit 0 from the actor | `test_autonomy_harness.py::test_an_actor_exit_two_still_completes` | KILLED — `HarnessError: the actor exited 2:` on a report that was written completely |

## Rows 15–21 — the revision-2 rows

| # | Mutation | Test node | Observed result |
|---|---|---|---|
| 15 | Wrap `assert_repository_is_at` in the restore | `test_autonomy_start_restore.py::test_a_dirty_input_tree_is_refused_byte_for_byte_unchanged` | KILLED — `assert (True and False)`: the caller's untracked `p2.md` no longer exists; the restore destroyed the work the check exists to refuse |
| 16 | Call `subprocess.run(["git", ...])` directly in `_settle` | `test_autonomy_harness.py::test_no_planted_vector_executes_through_the_supervised_loop` | KILLED (as an error, as predicted) — `CalledProcessError ... exit 128` from the raw commit, with git's stderr reading `warning: Empty last update token.` (the actor's `core.fsmonitor` executed) and `error: gpg failed to sign the data: (no gpg output) / fatal: failed to write commit object` (the actor's `commit.gpgsign` + `gpg.program` executed). Not an unrelated fixture error: the traceback is `harness.py:291 _settle -> harness.py:128 subprocess.run`, i.e. the mutated line. |
| 17 | Drop `--no-gpg-sign` from `commit_tree` | `test_autonomy_git_writes.py::test_no_planted_vector_executes_through_the_write_primitives` | KILLED — `GitError: git ... commit ... failed: error: gpg failed to sign the data: (no gpg output) / fatal: failed to write commit object` |
| 18 | `_settle` commits on the record-less path | `test_autonomy_harness.py::test_a_run_with_no_record_commits_nothing` | KILLED — `assert '4f0456fb…' is None`; a run with `record=None` published a post-verdict commit |
| 19 | `_settle` passes `--allow-empty` and skips the status check | `test_autonomy_harness.py::test_settling_a_clean_tree_creates_no_commit` | KILLED — `assert 'd69dd299…' is None` from the direct `_settle(record_written=True)` call over a clean tree |
| 20 | `ingestion_authority` passes `strict_identity=False` | `test_findings_ingestion_authority.py::test_it_loads_sources_without_relaxing_identity` | KILLED — `AssertionError: the strict default must stand …; {'strict_identity': False}.get(...) is False` |
| 21 | Exit 0 on an ingestion refusal | `test_autonomy_harness.py::test_the_command_exits_four_when_ingestion_refuses` | KILLED — `assert 0 == 4` with `ingestion refused: refused for the test` in the output |

**Rows 18 and 19 are two rows, not one.** Row 18 removes the `record_written` guard; row 19
removes the *status* guard and adds `--allow-empty`. Measured: the record-less test cannot kill
row 19, because on that path control returns at `if not record_written: restore; return None`
before any commit call, so the mutated line never executes. Row 19's condition —
`record_written=True` over a **clean** tree — is one the full loop never produces, since
`finish_run` always leaves the record file on disk. `test_settling_a_clean_tree_creates_no_commit`
calls `_settle` directly for exactly that reason.

**Row 16 needs the whole loop, not the primitives.** Proving the write primitives are hardened
says nothing about whether `_settle` calls them;
`test_no_planted_vector_executes_through_the_write_primitives` (row 17's test) stays green
against a raw `subprocess.run` in `_settle`. That is why row 16 has its own test over the
`supervised_project` fixture, sharing Task 1's `plant_attacks` factory.

## Rows 22–29 — the revision-3 and -4 rows

| # | Mutation | Test node | Observed result |
|---|---|---|---|
| 22 | `_run_actor` uses `["science", "health", ...]` | `test_autonomy_harness.py::test_the_actor_runs_the_supervisors_own_toolkit` | KILLED — `HarnessError: the actor exited 1: impostor toolkit`; the `science` planted ahead of the supervisor's on `PATH` ran |
| 23 | Drop `-P` **and** pass `cwd=project_root` | `test_autonomy_harness.py::test_the_actor_runs_the_supervisors_own_toolkit` | KILLED — `HarnessError: the actor exited 1: shadowed`; the `science_tool` package planted in the project was imported |
| 24 | Swallow a `_settle` failure instead of raising | `test_autonomy_harness.py::test_a_settlement_failure_raises` | KILLED — `Failed: DID NOT RAISE HarnessError` |
| 25 | Take `ended` from the loaded report | `test_autonomy_harness.py::test_the_record_ended_is_the_supervisors_clock` | KILLED — `assert datetime(2099, 1, 1, …) <= datetime(2026, 8, 3, …)`; the record carried the actor's instant |
| 26 | Remove the `_step` wrapper from `current_branch` | `test_autonomy_harness.py::test_a_raw_git_failure_is_normalized` | KILLED — the raw `GitError: cannot read HEAD` escapes instead of a `HarnessError` |
| 27 | Catch only `ValueError` around ingestion | `test_autonomy_harness.py::test_a_failed_ingestion_is_a_refusal_and_not_an_abort` | KILLED — `OSError: report is unreadable` escapes the loop, abandoning the tree before step 9 |
| 28 | Return exit 0 for a quarantined outcome | `test_autonomy_harness.py::test_the_command_maps_each_disposition_to_its_exit_code[quarantined-1]` | KILLED — `assert 0 == 1` |
| 29 | Return exit 0 for an unwired outcome | `test_autonomy_harness.py::test_the_command_maps_each_disposition_to_its_exit_code[unwired-2]` | KILLED — `assert 0 == 2` |

**Row 23 is one mutation with two halves, deliberately.** Re-measured here and consistent with
the earlier measurement recorded in the test's docstring: `-P` alone with `cwd=project_root`
passes, and the neutral `cwd` alone with `-P` dropped passes. `python -m` puts `''` on
`sys.path` and `''` resolves to the *cwd*, so aiming the cwd somewhere harmless and refusing to
trust the cwd are two answers to one question. Splitting it would put two individually
unkillable mutations in this ledger.

Rows 22 and 23 share one test, which is why it now carries **two** plants: a `science_tool`
package inside the project (for 23) and a `science` executable prepended to `PATH` from a
directory *outside* the project (for 22 — an untracked executable beside the entities would
make `start_run` refuse the dirty tree before the actor ever started).

## Drift from the plan's row table

The plan was written before Tasks 5, 6 and 9 ran. Four of its named nodes did not exist:

| Plan's node | Resolution |
|---|---|
| `test_a_recordless_outcome_commits_nothing` (row 18) | Already covered by `test_a_run_with_no_record_commits_nothing`; row repointed, no duplicate added |
| `test_an_unreadable_report_is_a_refusal_not_an_abort` (row 27) | Already covered by `test_a_failed_ingestion_is_a_refusal_and_not_an_abort`; row repointed, no duplicate added |
| `test_settling_a_clean_tree_creates_no_commit` (row 19) | Did not exist — added |
| `test_no_planted_vector_executes_through_the_supervised_loop` (row 16) | Did not exist — added, requesting `plant_attacks` from `tests/conftest.py` |

Six further tests named "(below)" by the plan were also absent and were added:
`test_an_actor_that_leaves_the_branch_is_refused` (4),
`test_a_quarantined_run_ingests_nothing` (10),
`test_the_attested_instant_is_the_commissioned_one` (12),
`test_an_actor_exit_two_still_completes` (14),
`test_a_settlement_failure_raises` (24),
`test_the_record_ended_is_the_supervisors_clock` (25),
`test_a_raw_git_failure_is_normalized` (26).

## Two places where the plan's prescribed test could not have certified its row

Both were found by asking, before certifying, *what input puts control on the mutated line* —
the same question that caught the third instance during Task 5.

**Row 14's fixture.** The plan prescribed `health:\n  accepted_validation: scalar\n`. Measured:
`accepted_validation_entries` returns `[]` when the value is not a **list**, so no
`accepted-validation.invalid-entry` finding is produced and `science health` exits **0**. The
assertion `outcome.actor_exit_code == 2` would then fail on a *correct* implementation. The
fixture is a one-element list holding an unusable entry instead, which does produce the finding
and the exit code. The assertion was not weakened to `in (0, 2)`.

**Row 25's assertion.** The plan's `test_the_record_ended_is_the_supervisors_clock` ran the
untouched fixture and asserted `before <= record.ended <= after`. Against an honest actor the
report's `generated_at` *is* the instant the supervisor dictated, and that instant lies inside
`[before, after]` — so the assertion holds whichever source `ended` came from, and the mutation
survives. The test now shifts the report's `generated_at` to 2099 through the same fixed
`_run_actor` seam row 12 uses (factored into `_shift_the_reported_instant`), which is what makes
"the supervisor's clock" and "the actor's report" distinguishable at all.

## Result

29 rows applied, 29 killed, 0 unkillable. Every reverted re-run passed.
