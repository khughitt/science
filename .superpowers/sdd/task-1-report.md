## What you implemented

- Added `science_tool.data_root` as the single owner for project-root discovery and data-root resolution in this task scope.
- Added per-project `data.root` parsing via `ProjectDataConfig` on `ProjectConfig`.
- Added global `data.root` parsing via `DataSettings` on `GlobalConfig`.
- Added focused tests for default, env, project, and global data-root resolution; config parsing; logical-to-physical mapping; and project-root discovery.

## Tests and results

- `cd science && uv run --frozen pytest tests/test_data_root.py -q` -> PASS (`12 passed`)

## TDD Evidence with RED command/output and GREEN command/output

### RED

Command:

```bash
cd science && uv run --frozen pytest tests/test_data_root.py -q
```

Output:

```text
==================================== ERRORS ====================================
___________________ ERROR collecting tests/test_data_root.py ___________________
ImportError while importing test module '/mnt/ssd/Dropbox/science/.worktrees/data-root-config/science/tests/test_data_root.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests/test_data_root.py:9: in <module>
    from science_tool.data_root import (
E   ModuleNotFoundError: No module named 'science_tool.data_root'
=========================== short test summary info ============================
ERROR tests/test_data_root.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
```

### GREEN

Command:

```bash
cd science && uv run --frozen pytest tests/test_data_root.py -q
```

Output:

```text
............                                                             [100%]
```

## Files changed

- `science/src/science_tool/data_root.py`
- `science/src/science_tool/project_config.py`
- `science/src/science_tool/registry/config.py`
- `science/tests/test_data_root.py`

## Self-review findings

- Changes are limited to the files listed in the task brief.
- Resolver precedence matches the task brief: env -> project config -> global config -> `<project>/data`.
- Absolute-path validation is explicit for env and global config roots.
- Project-level `data` config forbids typos while top-level `science.yaml` extras still survive.

## Issues/concerns

- I did not rerun the full package suite, `ruff`, or `pyright` after the user’s status interruption because the follow-up instruction explicitly narrowed completion to the focused test, commit, and report.
