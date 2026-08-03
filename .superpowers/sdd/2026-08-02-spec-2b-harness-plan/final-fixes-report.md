# Spec 2b final review fixes

## Status

DONE. All five behavioral findings and both documentation findings from the final
whole-branch review are fixed. The relevant mutation ledger is fully certified at
42/42 killed, including the nested-worktree correction found by the full suite.

## Commits

- Initial snapshot (`FIX_BASE`): `46eb7c1835e23e24510768bff25b56d644bb05f4`
- Production, tests, design, and ledger:
  `bdada2d377117669aec0d0b0eb37744b1076a1b4`
- Nested-project worktree correction, regression test, design, and ledger:
  `ef134dd4ac1df89b0afd7f2354108be75f30ea20`

The reviewed working tree was already clean when this fixing wave began, so the
required initial snapshot is an empty checkpoint that preserves the exact reviewed
state.

## Findings closed

### 1. Repository-local `core.worktree` could redirect Git writes

Red test:

```text
uv run --frozen pytest tests/test_autonomy_git_writes.py::test_repo_local_core_worktree_cannot_redirect_write_primitives -q
```

Before the fix, the assertion read `HEAD:named` as `outside named` rather than
`inside named`, proving the repository-local configuration redirected a write to a
sibling worktree.

Fix: `autonomy/git.py::_argv` now supplies
`--work-tree=<nearest-enclosing-worktree-root>` on every gateway invocation, including
the configuration preflight. The root is derived from the nearest unfollowed `.git`
marker rather than repository configuration. Every production Git operation still goes
through this gateway.

Green evidence: the same test passes and exercises create/switch, `stage_paths`,
`commit`, `restore_path`, `stage_all`, and `restore_worktree` while asserting the
sibling is unchanged.

### 2. The actor could follow a committed project symlink

Red test:

```text
uv run --frozen pytest tests/test_autonomy_harness.py::test_actor_output_cannot_follow_a_project_symlink -q
```

Before the fix, the external target contained the derived report file.

Fix: the fixed actor receives a supervisor-owned temporary output path. After an
accepted actor exit, the harness bounded-reads that regular file and copies its bytes
verbatim to the derived report path using the existing descriptor-anchored directory,
exclusive-create, write-all, and unlink primitives in `findings/paths.py`. The fixed
actor, model, and service tier are unchanged, and no generic actor API was added.

Green evidence: the same test passes and the external directory remains empty. The
new `read_regular_file_bytes_at` primitive is separately guarded by
`test_read_regular_file_bytes_at_preserves_non_utf8_bytes`.

### 3. An unforeseen ingestion exception leaked raw after settlement

Red test:

```text
uv run --frozen pytest tests/test_autonomy_harness.py::test_an_unforeseen_ingestion_failure_still_settles_the_tree -q
```

Before the fix, the private `_Unforeseen` exception escaped unchanged.

Fix: an unforeseen ordinary `Exception` becomes a caused `HarnessError` inside the
ingestion `try`; the outer `finally` settles the run before it propagates. Expected
ingestion errors retain the refusal contract.

Green evidence: the same test requires the `HarnessError`, its `_Unforeseen` cause,
the restored starting branch, and a clean tree.

### 4. Named settlement did not verify its clean-tree postcondition

Red test:

```text
uv run --frozen pytest tests/test_autonomy_harness.py::test_settlement_names_an_unaccounted_dirty_path -q
```

Before the fix, the harness returned successfully with `unexpected.txt` left dirty.

Fix: after committing the named settlement set, `_settle` re-reads porcelain status
and raises `HarnessError` containing the complete residue if any path remains.

Green evidence: the same test passes and names `unexpected.txt` in the error.

### 5. `restore_path` treated every `cat-file` failure as path absence

Red test:

```text
uv run --frozen pytest tests/test_autonomy_git_writes.py::test_restore_path_fails_closed_when_cat_file_does_not_prove_absence -q
```

Before the fix, the abnormal object lookup did not raise.

Fix: `restore_path` selects cleanup only when the last non-empty stderr line is one
of Git's exact, fully interpolated absent-path verdicts. Every other nonzero answer
raises `GitError` before a write.

Green evidence: the same test passes.

### 6. Exit-code 3 documentation overstated the failure phase

`docs/user-guide/agent-workflows.md` now says exit 3 means no harness outcome was
returned because orchestration failed, including possible post-verdict settlement
failure. It no longer claims every exit-3 failure occurred before a verdict.

### 7. No-root boundary migration guidance contradicted the CLI

`docs/migration/2026-08-02-gitignore-ingestion-lock.md` now says a project without
declared roots takes no action until enrollment and that `science boundary sync`
refuses such a project.

## Files changed

- `science/src/science_tool/autonomy/git.py`
- `science/src/science_tool/autonomy/harness.py`
- `science/src/science_tool/findings/paths.py`
- `science/tests/test_autonomy_git_writes.py`
- `science/tests/test_autonomy_harness.py`
- `science/tests/test_findings_paths.py`
- `docs/user-guide/agent-workflows.md`
- `docs/migration/2026-08-02-gitignore-ingestion-lock.md`
- `docs/plans/2026-08-02-supervised-run-harness-design.md`
- `docs/plans/2026-08-02-spec-2b-mutation-ledger.md`

## Mutation certification

Each mutant was applied alone, the named guard was run and observed failing for the
intended reason, the original implementation was restored, and the same guard was
observed passing before the next mutant.

| Row | Mutation | Kill evidence |
|---|---|---|
| 34 | Remove `_argv`'s `--work-tree` pin | `test_repo_local_core_worktree_cannot_redirect_write_primitives` read `outside named` from `HEAD:named` instead of `inside named` |
| 35 | Pass the derived project report path directly to the actor | `test_actor_output_cannot_follow_a_project_symlink` found the report in the external symlink target |
| 36 | Re-raise an unforeseen ingestion exception unchanged | `test_an_unforeseen_ingestion_failure_still_settles_the_tree` received raw `_Unforeseen` instead of caused `HarnessError` |
| 37 | Remove `_settle`'s post-commit status check | `test_settlement_names_an_unaccounted_dirty_path` did not raise |
| 38 | Treat every nonzero `cat-file -t` answer as absence | `test_restore_path_fails_closed_when_cat_file_does_not_prove_absence` did not raise |

Row 33 was also re-certified against the final exception contract. Moving settlement
after ingestion caused the unforeseen-ingestion guard to observe the required caused
`HarnessError` while the branch remained `auto/<run-id>` rather than returning to the
starting branch. Restoring the `finally` made the guard pass.

Ledger result: **42/42 killed; no surviving or flaky mutants; no mutant left active.**

## Verification

Focused modules while developing:

```text
uv run --frozen pytest tests/test_autonomy_git_writes.py -q
15 passed

uv run --frozen pytest tests/test_findings_paths.py -q
54 passed

uv run --frozen pytest tests/test_autonomy_harness.py -q
36 passed
```

Full Spec 2b scoped set:

```text
uv run --frozen pytest tests/test_autonomy_harness.py tests/test_autonomy_git_writes.py tests/test_autonomy_start_restore.py tests/test_health_attested_provenance.py tests/test_findings_ingestion_authority.py -q
65 passed
```

Adjacent path, Git, broker, and ingestion guards:

```text
uv run --frozen pytest tests/test_autonomy_git_canonical.py tests/test_evidence_broker_serve.py tests/test_findings_paths.py tests/test_findings_ingest.py -q
193 passed
```

Adjacent lifecycle, record, alarm, documentation, and budget guards:

```text
uv run --frozen pytest tests/test_autonomy_lifecycle.py tests/test_autonomy_record_writer.py tests/test_autonomy_perturbation_alarm.py tests/test_command_docs.py tests/test_budget_boundary.py -q
227 passed
```

Static checks:

```text
uv run --frozen ruff check
All checks passed!

uv run --frozen pyright
0 errors, 0 warnings, 0 informations

git diff --check
passed with no output
```

Total distinct tests in the final required scoped and adjacent runs: **485 passed**.
The approximately 12,000-test full CLI suite was not run because this work did not
meet the repository guide's full-suite triggers; the complete affected and adjacent
contract surfaces were run instead.

## Self-review

- The actor, model, and service tier remain fixed; no `Assignment`, generic actor
  surface, compatibility layer, or `Unified` component was introduced.
- Production Git calls remain centralized through `autonomy/git.py`.
- Actor output installation reuses the existing anchored path vocabulary and copies
  bytes verbatim, including non-UTF-8 content; schema validation remains later at the
  report trust boundary.
- Unforeseen ingestion failures retain their original exception as `__cause__` and
  settle before propagation.
- All five production regressions have direct red/green guards and individually
  certified mutants.
- Documentation uses project-relative examples and contains no AI-attribution trailer.
- `git diff --check`, Ruff, and Pyright are clean.

## Concerns

None.

## Full-suite nested-worktree correction

Fresh full-suite evidence on `51b83f4f` exposed a regression in the first worktree pin:

```text
12840 passed, 7 skipped, 142 deselected, 2 failed
tests/test_boundary_checks.py::test_nested_science_project_in_enclosing_worktree_is_checked
tests/test_data_audit_scope.py::test_nested_project_uses_parent_git_visibility
```

The two nodes were reproduced unchanged. The first omitted
`boundary.tracked-ignored`; the second incorrectly surfaced `build/x.csv`.

### Focused TDD evidence

The gateway regression combines a Science project nested beneath a parent repository,
an enclosing ignore rule and indexed path, and malicious parent
`core.worktree=<sibling>` configuration:

```text
uv run --frozen pytest tests/test_autonomy_git_writes.py::test_nested_project_uses_enclosing_worktree_without_trusting_core_worktree -q
```

RED: the old project-root pin surfaced `build/x.csv` despite the parent ignore rule and
also surfaced the indexed `science.yaml` under `projects/demo/science.yaml`, proving the
nested prefix was lost.

GREEN: `_worktree_root` walks upward from the resolved Science project with `lstat` and
returns the directory containing the nearest `.git` marker. `_argv` pins that directory,
so the same test sees exactly `keep.csv` and `science.yaml`; the configured sibling is
not visible.

The two full-suite nodes then passed together:

```text
uv run --frozen pytest tests/test_boundary_checks.py::test_nested_science_project_in_enclosing_worktree_is_checked tests/test_data_audit_scope.py::test_nested_project_uses_parent_git_visibility -q
2 passed
```

The marker derivation does not import `boundary/gitio.py`, which already imports this Git
gateway. A nearest directory marker or gitfile returns its containing directory; a
corrupt or dangling nearest marker is not skipped; and no marker returns the resolved
project path so Git can render its genuine non-repository verdict.

### Mutation row 39

The sole mutant replaced `_worktree_root(root)` with `root` in the central
`--work-tree` argument. The focused node failed on its literal path list:
`build/x.csv` was the first unexpected path and `projects/demo/science.yaml` was also
present. After restoring the nearest-marker call, the same node passed. No other mutant
was active.

Ledger result after row 39: **42/42 killed; the mutant was restored before commit.**

### Verification after the correction

```text
uv run --frozen pytest tests/test_autonomy_git_writes.py tests/test_autonomy_git_canonical.py -q
36 passed

uv run --frozen pytest tests/test_boundary_checks.py -q
48 passed

uv run --frozen pytest tests/test_data_audit_scope.py -q
8 passed

uv run --frozen ruff check
All checks passed!

uv run --frozen pyright
0 errors, 0 warnings, 0 informations

git diff --check
passed with no output
```

Correction commit: `ef134dd4ac1df89b0afd7f2354108be75f30ea20`.

Concerns: none.
