# Task 5 Report: Tracked Data-Root Guardrail

## Implementation summary

- Extended `audit_project_notes(project_root)` in [science/src/science_tool/data_audit.py](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/science/src/science_tool/data_audit.py:217) to append a `warning` note with code `tracked-data-root` when the resolved data root is inside the repo and contains git-tracked paths.
- Added `_tracked_paths_under_data_root(...)` in [science/src/science_tool/data_audit.py](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/science/src/science_tool/data_audit.py:251) to derive repo-relative tracked paths beneath the resolved data root using `git_tracked_set(project_root)`.
- Updated [commands/create-project.md](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/commands/create-project.md:242) to document the `dir/*` plus `.gitkeep` pattern for `data/raw`, `data/processed`, and `data/external`, plus the guardrail against putting committed provenance under `data/provenance/` for the default `./data` root.

This change does not alter audit scan traversal, violation classification, or fixer behavior. It only adds an audit note.

## TDD RED/GREEN evidence

### RED

Added failing tests first:

- [science/tests/test_data_audit.py](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/science/tests/test_data_audit.py:210)
- [science/tests/test_command_docs.py](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/science/tests/test_command_docs.py:1390)

Ran:

```bash
cd ~/d/science/.worktrees/data-root-config/science
uv run --frozen pytest tests/test_data_audit.py::test_audit_notes_warn_on_tracked_file_under_data_root tests/test_command_docs.py::test_create_project_docs_keep_data_payload_dirs_gitignored -q
```

Observed failures:

- `test_audit_notes_warn_on_tracked_file_under_data_root`: `assert 0 == 1` because no `tracked-data-root` warning existed.
- `test_create_project_docs_keep_data_payload_dirs_gitignored`: missing `data/raw/*` and related doc guidance in `commands/create-project.md`.

### GREEN

Implemented the minimal note helper and doc updates, then ran:

```bash
cd ~/d/science/.worktrees/data-root-config/science
uv run --frozen pytest tests/test_data_audit.py tests/test_data_audit_cli.py tests/test_command_docs.py::test_create_project_docs_keep_data_payload_dirs_gitignored -q
uv run ruff check
uv run pyright
```

Results:

- `26` focused tests passed.
- `ruff check`: passed.
- `pyright`: `0 errors, 0 warnings, 0 informations`.

## Files changed

- [science/src/science_tool/data_audit.py](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/science/src/science_tool/data_audit.py:217)
- [science/tests/test_data_audit.py](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/science/tests/test_data_audit.py:210)
- [science/tests/test_command_docs.py](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/science/tests/test_command_docs.py:1390)
- [commands/create-project.md](/mnt/ssd/Dropbox/science/.worktrees/data-root-config/commands/create-project.md:242)

## Why `test_command_docs.py` changed

Although `science/tests/test_command_docs.py` was outside the original ownership list, the task brief explicitly required:

- modifying `commands/create-project.md`, and
- adding `science/tests/test_command_docs.py::test_create_project_docs_keep_data_payload_dirs_gitignored`.

I changed that test file only to satisfy the task's command-doc validation requirement and kept the docs change scoped to `commands/create-project.md`.

## Self-review

- The warning is intentionally limited to in-repo data roots. External data roots still only emit `external-data-root`, preserving Task 3 behavior.
- The helper uses repo-relative path comparison against the resolved data root, so custom in-repo roots like `bulk/` will warn correctly if tracked files appear under them.
- Message truncation after five paths matches the task brief and keeps note output bounded.
- No scan or fix path was touched; this is note-only behavior.

## Concerns

- The new warning will include any tracked file under the configured data root, including intentionally committed descriptors if a project chooses to store them there. That is consistent with the guardrail intent in Task 5 and the accompanying docs guidance to keep committed provenance outside the data root.
