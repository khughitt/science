# QA Toolkit & Iteration Audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a light, config-driven QA-check runtime (`science-qa`, B1) plus an advisory iteration audit (`science qa-audit`, B3) that surfaces one-shot, QA-ignoring workflows — implementing the existing `pipeline-qa-checkpoints.md` convention rather than rediscovering it.

**Architecture:** A new standalone `science-qa` distribution (deps pandas/pyarrow/pyyaml only) holds the config-runner, an scRNA modality pack, and the disposition reconciler; it emits `qa_report.{md,json}` and scaffolds an analyst-owned `qa_dispositions.yaml`. A new `science qa-audit` subcommand in the existing `science_tool` reads authored `workflow-run` frontmatter (run chain + `manifest_path`) and the QA artifacts those manifests point at, then reports two orthogonal verdicts per workflow. The two packages never import each other.

**Tech Stack:** Python 3.11, click (CLI), pandas + pyarrow (tables), pyyaml (config/manifests/dispositions), pytest (TDD), hatchling + uv (packaging), ruff (lint, line-length 120).

**Spec:** `docs/plans/2026-06-11-qa-toolkit-and-iteration-audit-design.md`. **Branch:** `feat/qa-toolkit-iteration-audit`.

---

## File Structure

**New distribution `science-qa` (rooted at `science/qa/`):**
- `science/qa/pyproject.toml` — distribution metadata, light deps, hatchling build.
- `science/qa/src/science_qa/__init__.py` — package marker + public exports.
- `science/qa/src/science_qa/__main__.py` — `python -m science_qa` entry → CLI.
- `science/qa/src/science_qa/flags.py` — `Flag` dataclass + `build_flag_id`.
- `science/qa/src/science_qa/config.py` — `QAConfig` loader/validator for the `qa:` block.
- `science/qa/src/science_qa/checks.py` — generic structural + distribution checks.
- `science/qa/src/science_qa/report.py` — deterministic `qa_report.{json,md}` writers.
- `science/qa/src/science_qa/dispositions.py` — scaffold/reconcile `qa_dispositions.yaml`.
- `science/qa/src/science_qa/packs/__init__.py` — pack registry (`PACKS`).
- `science/qa/src/science_qa/packs/scrna.py` — scRNA `run(table, params)` pack.
- `science/qa/src/science_qa/runner.py` — orchestrates config → checks → packs → reports → dispositions.
- `science/qa/src/science_qa/cli.py` — `run` command.
- `science/qa/tests/…` — one test module per source module above.

**Audit (in existing `science/src/science_tool/`):**
- `science/src/science_tool/qa_audit/__init__.py`
- `science/src/science_tool/qa_audit/verdicts.py` — pure two-axis verdict functions.
- `science/src/science_tool/qa_audit/runs.py` — load `workflow-run` frontmatter → run records + chains.
- `science/src/science_tool/qa_audit/manifest.py` — read `datapackage.yaml` QA resources + dispositions.
- `science/src/science_tool/qa_audit/audit.py` — assemble per-workflow verdicts + render report.
- `science/src/science_tool/qa_audit/cli.py` — `qa_audit_command` (`science qa-audit`).
- `science/src/science_tool/cli.py` — register the command (one-line `add_command`).
- `science/tests/test_qa_audit_*.py` — verdict, runs, manifest, end-to-end tests.

**Docs/templates:**
- `templates/workflow-run.md`, `docs/conventions/pipeline-qa-checkpoints.md`,
  `docs/process/pipeline-audit-and-refactor.md`,
  `aspects/computational-analysis/computational-analysis.md`.

> **Conventions for every commit:** no `Co-Authored-By` trailer. In docs/code use `~/d/` for absolute paths. Run `ruff` before committing code tasks. All shell commands below assume cwd `science/` (the package root with `pyproject.toml`) unless stated otherwise.

---

## Phase A — `science-qa` distribution (B1)

### Task A1: Scaffold the `science-qa` distribution

**Files:**
- Create: `science/qa/pyproject.toml`
- Create: `science/qa/src/science_qa/__init__.py`
- Create: `science/qa/src/science_qa/__main__.py`
- Create: `science/qa/tests/test_packaging.py`
- Modify: `science/pyproject.toml` (add dev dependency + uv source)

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_packaging.py`:
```python
import subprocess
import sys


def test_module_entry_point_runs():
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "run" in result.stdout


def test_science_qa_does_not_import_science_tool():
    # The runtime must stay light: importing science_qa must not pull science_tool.
    code = "import science_qa, sys; assert 'science_tool' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest qa/tests/test_packaging.py -v`
Expected: FAIL (`No module named science_qa`).

- [ ] **Step 3: Create the distribution files**

`science/qa/pyproject.toml`:
```toml
[project]
name = "science-qa"
version = "0.1.0"
description = "Config-driven pipeline QA-check runtime for science projects"
requires-python = ">=3.11"
dependencies = [
  "click>=8.1",
  "pandas>=2.0",
  "pyarrow>=24.0.0",
  "pyyaml>=6.0",
]

[build-system]
requires = ["hatchling>=1.24"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/science_qa"]

[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]

[tool.ruff]
line-length = 120
```

`science/qa/src/science_qa/__init__.py`:
```python
"""science-qa: a light, config-driven pipeline QA-check runtime.

Implements the qa: schema and structural/distribution severity split from
docs/conventions/pipeline-qa-checkpoints.md. Deliberately depends on nothing
from science_tool so a project's pipeline stays light.
"""

from __future__ import annotations
```

`science/qa/src/science_qa/__main__.py`:
```python
from __future__ import annotations

from science_qa.cli import cli

if __name__ == "__main__":
    cli()
```

- [ ] **Step 4: Add a minimal CLI so `--help` resolves**

Create `science/qa/src/science_qa/cli.py`:
```python
from __future__ import annotations

import click


@click.group()
def cli() -> None:
    """science-qa command-line interface."""


@cli.command("run")
def run_command() -> None:
    """Run QA checks over a built table (implemented in Task A9)."""
    raise click.ClickException("not yet implemented")
```

- [ ] **Step 5: Register the distribution for dev/testing**

In `science/pyproject.toml`, under `[tool.uv.sources]` add (keeps `science-qa` editable-installed in the dev env for tests, WITHOUT making it a runtime dependency of `science_tool`):
```toml
science-qa = { path = "qa", editable = true }
```
And under `[dependency-groups]` `dev = [...]`, add the line:
```toml
    "science-qa",
```
Then sync: `uv sync`

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest qa/tests/test_packaging.py -v`
Expected: PASS (both tests).

- [ ] **Step 7: Commit**

```bash
git add science/qa/pyproject.toml science/qa/src/science_qa science/qa/tests/test_packaging.py science/pyproject.toml science/uv.lock
git commit -m "feat(science-qa): scaffold light QA-check distribution"
```

---

### Task A2: `Flag` dataclass + namespaced `flag_id`

**Files:**
- Create: `science/qa/src/science_qa/flags.py`
- Create: `science/qa/tests/test_flags.py`

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_flags.py`:
```python
from science_qa.flags import Flag, build_flag_id


def test_build_flag_id_two_sided():
    assert build_flag_id("generic", "range", "glucose", "max") == "generic/range/glucose/max"


def test_build_flag_id_no_side():
    assert build_flag_id("generic", "unique_key", "SUBJECT_ID", None) == "generic/unique_key/SUBJECT_ID/-"


def test_build_flag_id_table_level_tuple_subject():
    assert build_flag_id("generic", "exclusive_flags", "on_drug_a+on_drug_b", None) == (
        "generic/exclusive_flags/on_drug_a+on_drug_b/-"
    )


def test_flag_id_property_matches_builder():
    flag = Flag(
        source="scrna", check="threshold", subject="pct_counts_mt", side="max",
        severity="distribution", value="33.0", threshold="20", message="high mito",
    )
    assert flag.flag_id == "scrna/threshold/pct_counts_mt/max"


def test_flag_to_dict_is_json_ready():
    flag = Flag(
        source="generic", check="range", subject="glucose", side="max",
        severity="distribution", value="600", threshold="500", message="above max",
    )
    assert flag.to_dict() == {
        "flag_id": "generic/range/glucose/max",
        "source": "generic", "check": "range", "subject": "glucose", "side": "max",
        "severity": "distribution", "value": "600", "threshold": "500", "message": "above max",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest qa/tests/test_flags.py -v`
Expected: FAIL (`No module named science_qa.flags`).

- [ ] **Step 3: Write minimal implementation**

`science/qa/src/science_qa/flags.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

SEVERITY_STRUCTURAL = "structural"
SEVERITY_DISTRIBUTION = "distribution"


def build_flag_id(source: str, check: str, subject: str, side: str | None) -> str:
    """Namespaced, collision-resistant flag id: {source}/{check}/{subject}/{side}.

    `side` is `min`/`max` for two-sided checks; `None` collapses to `-`.
    """
    return f"{source}/{check}/{subject}/{side or '-'}"


@dataclass(frozen=True)
class Flag:
    source: str            # "generic" or a pack name, e.g. "scrna"
    check: str             # "range", "unique_key", "threshold", ...
    subject: str           # variable name, or a "+"-joined tuple for table-level checks
    side: str | None       # "min" | "max" | None
    severity: str          # SEVERITY_STRUCTURAL | SEVERITY_DISTRIBUTION
    value: str             # observed value, stringified for deterministic output
    threshold: str         # threshold/expectation, stringified
    message: str

    @property
    def flag_id(self) -> str:
        return build_flag_id(self.source, self.check, self.subject, self.side)

    def to_dict(self) -> dict[str, str]:
        return {
            "flag_id": self.flag_id,
            "source": self.source,
            "check": self.check,
            "subject": self.subject,
            "side": self.side or "-",
            "severity": self.severity,
            "value": self.value,
            "threshold": self.threshold,
            "message": self.message,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest qa/tests/test_flags.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/flags.py science/qa/tests/test_flags.py
git commit -m "feat(science-qa): Flag dataclass + namespaced flag_id"
```

---

### Task A3: `QAConfig` loader/validator

**Files:**
- Create: `science/qa/src/science_qa/config.py`
- Create: `science/qa/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_config.py`:
```python
import pytest

from science_qa.config import QAConfig, QAConfigError


def test_loads_full_qa_block(tmp_path):
    cfg = tmp_path / "qa.yaml"
    cfg.write_text(
        "qa:\n"
        "  unique_key: SUBJECT_ID\n"
        "  required_complete: [stratum, psu]\n"
        "  categoricals:\n"
        "    stage: {allowed: [1, 2, 3]}\n"
        "  exclusive_flags: [[on_drug_a, on_drug_b]]\n"
        "  ranges:\n"
        "    glucose: {min: 30, max: 500}\n"
        "  missing_sentinels: [-9]\n"
        "  packs: [scrna]\n"
        "  pack_params:\n"
        "    scrna: {max_mito_pct: 20}\n"
    )
    config = QAConfig.from_file(cfg)
    assert config.unique_key == "SUBJECT_ID"
    assert config.required_complete == ["stratum", "psu"]
    assert config.categoricals == {"stage": {"allowed": [1, 2, 3]}}
    assert config.exclusive_flags == [["on_drug_a", "on_drug_b"]]
    assert config.ranges == {"glucose": {"min": 30, "max": 500}}
    assert config.missing_sentinels == [-9]
    assert config.packs == ["scrna"]
    assert config.pack_params == {"scrna": {"max_mito_pct": 20}}


def test_missing_qa_block_is_error(tmp_path):
    cfg = tmp_path / "qa.yaml"
    cfg.write_text("other: {}\n")
    with pytest.raises(QAConfigError, match="no 'qa:' block"):
        QAConfig.from_file(cfg)


def test_absent_file_is_error(tmp_path):
    with pytest.raises(QAConfigError, match="not found"):
        QAConfig.from_file(tmp_path / "missing.yaml")


def test_empty_qa_block_yields_empty_config(tmp_path):
    cfg = tmp_path / "qa.yaml"
    cfg.write_text("qa: {}\n")
    config = QAConfig.from_file(cfg)
    assert config.unique_key is None
    assert config.required_complete == []
    assert config.packs == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest qa/tests/test_config.py -v`
Expected: FAIL (`No module named science_qa.config`).

- [ ] **Step 3: Write minimal implementation**

`science/qa/src/science_qa/config.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


class QAConfigError(Exception):
    """Raised when the QA config is missing or malformed (fail early, explicit)."""


@dataclass
class QAConfig:
    unique_key: str | None = None
    required_complete: list[str] = field(default_factory=list)
    categoricals: dict[str, dict] = field(default_factory=dict)
    exclusive_flags: list[list[str]] = field(default_factory=list)
    ranges: dict[str, dict] = field(default_factory=dict)
    missing_sentinels: list = field(default_factory=list)
    packs: list[str] = field(default_factory=list)
    pack_params: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "QAConfig":
        if not path.exists():
            raise QAConfigError(f"QA config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or "qa" not in data:
            raise QAConfigError(f"config {path} has no 'qa:' block")
        qa = data["qa"] or {}
        return cls(
            unique_key=qa.get("unique_key"),
            required_complete=list(qa.get("required_complete", []) or []),
            categoricals=dict(qa.get("categoricals", {}) or {}),
            exclusive_flags=[list(pair) for pair in (qa.get("exclusive_flags", []) or [])],
            ranges=dict(qa.get("ranges", {}) or {}),
            missing_sentinels=list(qa.get("missing_sentinels", []) or []),
            packs=list(qa.get("packs", []) or []),
            pack_params=dict(qa.get("pack_params", {}) or {}),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest qa/tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/qa/src/science_qa/config.py science/qa/tests/test_config.py
git commit -m "feat(science-qa): QAConfig loader for the qa: block"
```

---

### Task A4: Generic structural checks

**Files:**
- Create: `science/qa/src/science_qa/checks.py`
- Create: `science/qa/tests/test_checks_structural.py`

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_checks_structural.py`:
```python
import pandas as pd

from science_qa.config import QAConfig
from science_qa.checks import run_structural_checks


def _ids(flags):
    return sorted(f.flag_id for f in flags)


def test_unique_key_violation_is_structural():
    table = pd.DataFrame({"SUBJECT_ID": [1, 1, 2]})
    flags = run_structural_checks(table, QAConfig(unique_key="SUBJECT_ID"))
    assert _ids(flags) == ["generic/unique_key/SUBJECT_ID/-"]
    assert flags[0].severity == "structural"


def test_unique_key_ok_yields_no_flag():
    table = pd.DataFrame({"SUBJECT_ID": [1, 2, 3]})
    assert run_structural_checks(table, QAConfig(unique_key="SUBJECT_ID")) == []


def test_required_complete_missing_value_flags():
    table = pd.DataFrame({"stratum": [1, None, 3]})
    flags = run_structural_checks(table, QAConfig(required_complete=["stratum"]))
    assert _ids(flags) == ["generic/required_complete/stratum/-"]


def test_categorical_allowed_violation_flags():
    table = pd.DataFrame({"stage": [1, 2, 9]})
    cfg = QAConfig(categoricals={"stage": {"allowed": [1, 2, 3]}})
    flags = run_structural_checks(table, cfg)
    assert _ids(flags) == ["generic/allowed/stage/-"]


def test_categorical_allowed_from_registry_subset(tmp_path):
    registry = tmp_path / "contrasts.csv"
    registry.write_text("name\na\nb\n")
    table = pd.DataFrame({"contrast": ["a", "z"]})
    cfg = QAConfig(categoricals={"contrast": {"allowed_from": f"{registry}#name"}})
    flags = run_structural_checks(table, cfg, base_dir=tmp_path)
    assert _ids(flags) == ["generic/allowed/contrast/-"]


def test_exclusive_flags_cooccurrence():
    table = pd.DataFrame({"on_drug_a": [1, 0], "on_drug_b": [1, 0]})
    cfg = QAConfig(exclusive_flags=[["on_drug_a", "on_drug_b"]])
    flags = run_structural_checks(table, cfg)
    assert _ids(flags) == ["generic/exclusive_flags/on_drug_a+on_drug_b/-"]


def test_missing_sentinel_survivor_flags():
    table = pd.DataFrame({"age": [40, -9, 55]})
    flags = run_structural_checks(table, QAConfig(missing_sentinels=[-9]))
    assert _ids(flags) == ["generic/missing_sentinel/age/-"]


def test_config_column_absent_raises():
    import pytest
    from science_qa.checks import QACheckError
    table = pd.DataFrame({"other": [1]})
    with pytest.raises(QACheckError, match="SUBJECT_ID"):
        run_structural_checks(table, QAConfig(unique_key="SUBJECT_ID"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest qa/tests/test_checks_structural.py -v`
Expected: FAIL (`No module named science_qa.checks`).

- [ ] **Step 3: Write minimal implementation**

`science/qa/src/science_qa/checks.py`:
```python
from __future__ import annotations

from pathlib import Path

import pandas as pd

from science_qa.config import QAConfig
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag


class QACheckError(Exception):
    """Raised when a config clause references a column absent from the table."""


def _require_column(table: pd.DataFrame, column: str, *, clause: str) -> None:
    if column not in table.columns:
        raise QACheckError(f"{clause} references column {column!r} absent from table")


def _allowed_values(spec: dict, base_dir: Path) -> set:
    if "allowed" in spec:
        return set(spec["allowed"])
    if "allowed_from" in spec:
        ref = str(spec["allowed_from"])
        file_part, _, column = ref.partition("#")
        path = (base_dir / file_part) if not Path(file_part).is_absolute() else Path(file_part)
        registry = pd.read_csv(path)
        return set(registry[column].dropna().tolist())
    raise QACheckError(f"categorical spec must have 'allowed' or 'allowed_from': {spec!r}")


def run_structural_checks(table: pd.DataFrame, config: QAConfig, *, base_dir: Path | None = None) -> list[Flag]:
    base_dir = base_dir or Path(".")
    flags: list[Flag] = []

    if config.unique_key:
        _require_column(table, config.unique_key, clause="unique_key")
        if table[config.unique_key].duplicated().any():
            dupes = int(table[config.unique_key].duplicated().sum())
            flags.append(Flag("generic", "unique_key", config.unique_key, None,
                              SEVERITY_STRUCTURAL, str(dupes), "0", f"{dupes} duplicate key value(s)"))

    for column in config.required_complete:
        _require_column(table, column, clause="required_complete")
        missing = int(table[column].isna().sum())
        if missing:
            flags.append(Flag("generic", "required_complete", column, None,
                              SEVERITY_STRUCTURAL, str(missing), "0", f"{missing} missing value(s)"))

    for column, spec in config.categoricals.items():
        _require_column(table, column, clause="categoricals")
        allowed = _allowed_values(spec, base_dir)
        illegal = set(table[column].dropna().unique()) - allowed
        if illegal:
            flags.append(Flag("generic", "allowed", column, None,
                              SEVERITY_STRUCTURAL, ",".join(map(str, sorted(map(str, illegal)))),
                              "in allowed set", f"{len(illegal)} value(s) outside allowed set"))

    for pair in config.exclusive_flags:
        for column in pair:
            _require_column(table, column, clause="exclusive_flags")
        cooccur = int((table[pair[0]].astype(bool) & table[pair[1]].astype(bool)).sum())
        if cooccur:
            flags.append(Flag("generic", "exclusive_flags", "+".join(pair), None,
                              SEVERITY_STRUCTURAL, str(cooccur), "0",
                              f"{cooccur} row(s) where {pair[0]} and {pair[1]} co-occur"))

    if config.missing_sentinels:
        sentinels = set(config.missing_sentinels)
        for column in table.columns:
            if not pd.api.types.is_numeric_dtype(table[column]):
                continue
            survivors = int(table[column].isin(sentinels).sum())
            if survivors:
                flags.append(Flag("generic", "missing_sentinel", column, None,
                                  SEVERITY_STRUCTURAL, str(survivors), "0",
                                  f"{survivors} surviving missing-sentinel value(s)"))

    return flags
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest qa/tests/test_checks_structural.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check qa/src/science_qa/checks.py
git add science/qa/src/science_qa/checks.py science/qa/tests/test_checks_structural.py
git commit -m "feat(science-qa): generic structural checks"
```

---

### Task A5: Generic distribution checks + per-variable stats

**Files:**
- Modify: `science/qa/src/science_qa/checks.py`
- Create: `science/qa/tests/test_checks_distribution.py`

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_checks_distribution.py`:
```python
import pandas as pd

from science_qa.config import QAConfig
from science_qa.checks import run_distribution_checks, per_variable_stats


def _ids(flags):
    return sorted(f.flag_id for f in flags)


def test_range_max_exceedance_flags_distribution():
    table = pd.DataFrame({"glucose": [50, 600]})
    cfg = QAConfig(ranges={"glucose": {"min": 30, "max": 500}})
    flags = run_distribution_checks(table, cfg)
    assert "generic/range/glucose/max" in _ids(flags)
    assert all(f.severity == "distribution" for f in flags)


def test_range_min_exceedance_flags_distribution():
    table = pd.DataFrame({"glucose": [10, 50]})
    cfg = QAConfig(ranges={"glucose": {"min": 30, "max": 500}})
    assert _ids(run_distribution_checks(table, cfg)) == ["generic/range/glucose/min"]


def test_range_within_bounds_no_flag():
    table = pd.DataFrame({"glucose": [50, 60]})
    cfg = QAConfig(ranges={"glucose": {"min": 30, "max": 500}})
    assert run_distribution_checks(table, cfg) == []


def test_per_variable_stats_shape():
    table = pd.DataFrame({"glucose": [50, 60, None]})
    stats = per_variable_stats(table)
    row = next(r for r in stats if r["variable"] == "glucose")
    assert row["n"] == 2
    assert row["pct_miss"] == "33.3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest qa/tests/test_checks_distribution.py -v`
Expected: FAIL (`cannot import name 'run_distribution_checks'`).

- [ ] **Step 3: Append implementation to `checks.py`**

Add to `science/qa/src/science_qa/checks.py`:
```python
def run_distribution_checks(table: pd.DataFrame, config: QAConfig) -> list[Flag]:
    flags: list[Flag] = []
    for column, bounds in config.ranges.items():
        _require_column(table, column, clause="ranges")
        series = pd.to_numeric(table[column], errors="coerce").dropna()
        if "min" in bounds:
            below = int((series < bounds["min"]).sum())
            if below:
                flags.append(Flag("generic", "range", column, "min", SEVERITY_DISTRIBUTION,
                                  str(below), str(bounds["min"]), f"{below} value(s) below min"))
        if "max" in bounds:
            above = int((series > bounds["max"]).sum())
            if above:
                flags.append(Flag("generic", "range", column, "max", SEVERITY_DISTRIBUTION,
                                  str(above), str(bounds["max"]), f"{above} value(s) above max"))
    return flags


def per_variable_stats(table: pd.DataFrame) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    total = len(table)
    for column in table.columns:
        series = table[column]
        n = int(series.notna().sum())
        pct_miss = round(100 * (total - n) / total, 1) if total else 0.0
        rows.append({"variable": column, "n": n, "pct_miss": f"{pct_miss}"})
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest qa/tests/test_checks_distribution.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check qa/src/science_qa/checks.py
git add science/qa/src/science_qa/checks.py science/qa/tests/test_checks_distribution.py
git commit -m "feat(science-qa): generic distribution checks + per-variable stats"
```

---

### Task A6: Deterministic report writers

**Files:**
- Create: `science/qa/src/science_qa/report.py`
- Create: `science/qa/tests/test_report.py`

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_report.py`:
```python
import json

from science_qa.flags import Flag
from science_qa.report import write_reports


def _flags():
    return [
        Flag("generic", "unique_key", "SUBJECT_ID", None, "structural", "2", "0", "2 dup"),
        Flag("generic", "range", "glucose", "max", "distribution", "1", "500", "above max"),
    ]


def test_writes_json_and_md(tmp_path):
    write_reports(_flags(), report_dir=tmp_path, rows_checked=3)
    assert (tmp_path / "qa_report.json").exists()
    assert (tmp_path / "qa_report.md").exists()


def test_json_lists_flags_sorted_by_id(tmp_path):
    write_reports(_flags(), report_dir=tmp_path, rows_checked=3)
    payload = json.loads((tmp_path / "qa_report.json").read_text())
    ids = [f["flag_id"] for f in payload["flags"]]
    assert ids == ["generic/range/glucose/max", "generic/unique_key/SUBJECT_ID/-"]
    assert payload["structural_count"] == 1
    assert payload["distribution_count"] == 1


def test_output_is_deterministic(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(); b.mkdir()
    write_reports(_flags(), report_dir=a, rows_checked=3)
    write_reports(list(reversed(_flags())), report_dir=b, rows_checked=3)
    assert (a / "qa_report.json").read_bytes() == (b / "qa_report.json").read_bytes()
    assert (a / "qa_report.md").read_bytes() == (b / "qa_report.md").read_bytes()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest qa/tests/test_report.py -v`
Expected: FAIL (`No module named science_qa.report`).

- [ ] **Step 3: Write minimal implementation**

`science/qa/src/science_qa/report.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag


def _sorted(flags: list[Flag]) -> list[Flag]:
    return sorted(flags, key=lambda f: f.flag_id)


def write_reports(flags: list[Flag], *, report_dir: Path, rows_checked: int) -> None:
    """Write qa_report.json (immutable flag ledger) and qa_report.md.

    Deterministic: output depends only on the flag set (sorted by id) and
    rows_checked — never on wall-clock — so re-run-and-diff stays clean.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    ordered = _sorted(flags)
    structural = [f for f in ordered if f.severity == SEVERITY_STRUCTURAL]
    distribution = [f for f in ordered if f.severity == SEVERITY_DISTRIBUTION]

    payload = {
        "rows_checked": rows_checked,
        "structural_count": len(structural),
        "distribution_count": len(distribution),
        "flags": [f.to_dict() for f in ordered],
    }
    (report_dir / "qa_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    lines = [
        "# QA / sanity-check report",
        "",
        f"- Rows checked: {rows_checked}",
        f"- Structural flags: **{len(structural)}** · Distribution flags: **{len(distribution)}**",
        "",
        "## Flagged issues",
        "### 🔴 Structural (ingest/derive bugs — build-fatal)",
    ]
    lines += [f"- `{f.flag_id}` — {f.message}" for f in structural] or ["- none"]
    lines += ["", "### 🟡 Distribution (domain review — not fatal)"]
    lines += [f"- `{f.flag_id}` — {f.message}" for f in distribution] or ["- none"]
    lines.append("")
    (report_dir / "qa_report.md").write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest qa/tests/test_report.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check qa/src/science_qa/report.py
git add science/qa/src/science_qa/report.py science/qa/tests/test_report.py
git commit -m "feat(science-qa): deterministic qa_report.{json,md} writers"
```

---

### Task A7: Disposition scaffold/reconcile

**Files:**
- Create: `science/qa/src/science_qa/dispositions.py`
- Create: `science/qa/tests/test_dispositions.py`

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_dispositions.py`:
```python
import yaml

from science_qa.dispositions import VALID_DISPOSITIONS, reconcile_dispositions


def _write(path, entries):
    path.write_text(yaml.safe_dump({"dispositions": entries}, sort_keys=True))


def test_scaffolds_open_stub_when_absent(tmp_path):
    stats = reconcile_dispositions(tmp_path, ["generic/range/glucose/max"])
    data = yaml.safe_load((tmp_path / "qa_dispositions.yaml").read_text())
    entry = data["dispositions"][0]
    assert entry["flag_id"] == "generic/range/glucose/max"
    assert entry["disposition"] == "open"
    assert stats.added == 1 and stats.resolved == 0 and stats.unchanged == 0


def test_preserves_filled_entries_and_marks_resolved(tmp_path):
    path = tmp_path / "qa_dispositions.yaml"
    _write(path, [
        {"flag_id": "a/b/c/-", "disposition": "addressed", "note": "fixed", "change": "min_genes=200"},
        {"flag_id": "stale/x/y/-", "disposition": "accepted-real", "note": "ok"},
    ])
    stats = reconcile_dispositions(tmp_path, ["a/b/c/-", "new/d/e/-"])
    data = {e["flag_id"]: e for e in yaml.safe_load(path.read_text())["dispositions"]}
    assert data["a/b/c/-"]["disposition"] == "addressed"     # preserved
    assert data["a/b/c/-"]["change"] == "min_genes=200"      # preserved
    assert data["new/d/e/-"]["disposition"] == "open"        # added
    assert data["stale/x/y/-"]["disposition"] == "resolved"  # vanished
    assert (stats.added, stats.resolved, stats.unchanged) == (1, 1, 1)


def test_never_overwrites_on_repeat(tmp_path):
    reconcile_dispositions(tmp_path, ["a/b/c/-"])
    path = tmp_path / "qa_dispositions.yaml"
    data = yaml.safe_load(path.read_text())
    data["dispositions"][0]["disposition"] = "investigating"
    path.write_text(yaml.safe_dump(data, sort_keys=True))
    reconcile_dispositions(tmp_path, ["a/b/c/-"])
    again = yaml.safe_load(path.read_text())
    assert again["dispositions"][0]["disposition"] == "investigating"


def test_valid_dispositions_set():
    assert VALID_DISPOSITIONS == {"open", "investigating", "addressed", "accepted-real", "wont-fix", "resolved"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest qa/tests/test_dispositions.py -v`
Expected: FAIL (`No module named science_qa.dispositions`).

- [ ] **Step 3: Write minimal implementation**

`science/qa/src/science_qa/dispositions.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DISPOSITIONS_FILENAME = "qa_dispositions.yaml"
VALID_DISPOSITIONS = {"open", "investigating", "addressed", "accepted-real", "wont-fix", "resolved"}


@dataclass
class MergeStats:
    added: int = 0
    resolved: int = 0
    unchanged: int = 0


def reconcile_dispositions(report_dir: Path, distribution_flag_ids: list[str]) -> MergeStats:
    """Create-if-absent / merge-by-flag_id. Never overwrites a filled entry.

    This file is analyst-owned and is NEVER a declared Snakemake rule output —
    callers write it outside any strict-gate rule's output set so a failed build
    cannot delete hand-entered dispositions.
    """
    path = report_dir / DISPOSITIONS_FILENAME
    existing: dict[str, dict] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for entry in loaded.get("dispositions", []) or []:
            existing[entry["flag_id"]] = entry

    current = set(distribution_flag_ids)
    stats = MergeStats()
    merged: dict[str, dict] = {}

    for flag_id in current:
        if flag_id in existing:
            merged[flag_id] = existing[flag_id]
            stats.unchanged += 1
        else:
            merged[flag_id] = {"flag_id": flag_id, "disposition": "open", "note": "", "change": ""}
            stats.added += 1

    for flag_id, entry in existing.items():
        if flag_id not in current:
            entry["disposition"] = "resolved"
            merged[flag_id] = entry
            stats.resolved += 1

    report_dir.mkdir(parents=True, exist_ok=True)
    ordered = [merged[k] for k in sorted(merged)]
    path.write_text(yaml.safe_dump({"dispositions": ordered}, sort_keys=True), encoding="utf-8")
    return stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest qa/tests/test_dispositions.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check qa/src/science_qa/dispositions.py
git add science/qa/src/science_qa/dispositions.py science/qa/tests/test_dispositions.py
git commit -m "feat(science-qa): analyst-owned disposition reconcile (never a rule output)"
```

---

### Task A8: scRNA pack + pack registry

**Files:**
- Create: `science/qa/src/science_qa/packs/__init__.py`
- Create: `science/qa/src/science_qa/packs/scrna.py`
- Create: `science/qa/tests/test_pack_scrna.py`

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_pack_scrna.py`:
```python
import pandas as pd
import pytest

from science_qa.packs import PACKS, resolve_pack, UnknownPackError
from science_qa.packs import scrna


def _ids(flags):
    return sorted(f.flag_id for f in flags)


def test_registry_exposes_scrna():
    assert "scrna" in PACKS
    assert resolve_pack("scrna") is scrna.run


def test_unknown_pack_raises():
    with pytest.raises(UnknownPackError, match="bogus"):
        resolve_pack("bogus")


def test_missing_required_column_is_structural():
    table = pd.DataFrame({"total_counts": [1000]})  # missing pct_counts_mt, n_genes_by_counts
    flags = scrna.run(table, {})
    assert "scrna/required_column/pct_counts_mt/-" in _ids(flags)
    assert all(f.severity == "structural" for f in flags if f.check == "required_column")


def test_high_mito_is_distribution():
    table = pd.DataFrame({
        "total_counts": [1000, 1000],
        "n_genes_by_counts": [500, 500],
        "pct_counts_mt": [5.0, 40.0],
    })
    flags = scrna.run(table, {"max_mito_pct": 20})
    mito = [f for f in flags if f.flag_id == "scrna/threshold/pct_counts_mt/max"]
    assert mito and mito[0].severity == "distribution"


def test_low_gene_count_distribution_uses_default_param():
    table = pd.DataFrame({
        "total_counts": [1000, 1000],
        "n_genes_by_counts": [50, 500],   # 50 < default min_genes 200
        "pct_counts_mt": [5.0, 5.0],
    })
    flags = scrna.run(table, {})
    assert "scrna/threshold/n_genes_by_counts/min" in _ids(flags)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest qa/tests/test_pack_scrna.py -v`
Expected: FAIL (`No module named science_qa.packs`).

- [ ] **Step 3: Write minimal implementation**

`science/qa/src/science_qa/packs/scrna.py`:
```python
from __future__ import annotations

import pandas as pd

from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag

REQUIRED_COLUMNS = ("total_counts", "n_genes_by_counts", "pct_counts_mt")
DEFAULTS = {"max_mito_pct": 20, "min_genes": 200, "max_genes": 8000, "min_counts": 500, "max_doublet": 0.3}


def run(table: pd.DataFrame, params: dict) -> list[Flag]:
    p = {**DEFAULTS, **(params or {})}
    flags: list[Flag] = []

    missing = [c for c in REQUIRED_COLUMNS if c not in table.columns]
    for column in missing:
        flags.append(Flag("scrna", "required_column", column, None, SEVERITY_STRUCTURAL,
                          "absent", "present", f"required scRNA QC column {column!r} missing"))
    if missing:
        return flags  # cannot run distribution checks without the metric columns

    def _count(mask) -> int:
        return int(mask.sum())

    def _gate(column: str, side: str, mask, threshold) -> None:
        n = _count(mask)
        if n:
            flags.append(Flag("scrna", "threshold", column, side, SEVERITY_DISTRIBUTION,
                              str(n), str(threshold), f"{n} cell(s) failing {column} {side} gate"))

    _gate("pct_counts_mt", "max", table["pct_counts_mt"] > p["max_mito_pct"], p["max_mito_pct"])
    _gate("n_genes_by_counts", "min", table["n_genes_by_counts"] < p["min_genes"], p["min_genes"])
    _gate("n_genes_by_counts", "max", table["n_genes_by_counts"] > p["max_genes"], p["max_genes"])
    _gate("total_counts", "min", table["total_counts"] < p["min_counts"], p["min_counts"])
    if "doublet_score" in table.columns:
        _gate("doublet_score", "max", table["doublet_score"] > p["max_doublet"], p["max_doublet"])
    return flags
```

`science/qa/src/science_qa/packs/__init__.py`:
```python
from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from science_qa.flags import Flag
from science_qa.packs import scrna


class UnknownPackError(Exception):
    """Raised when a config names a pack that is not registered (fail early)."""


PackFn = Callable[[pd.DataFrame, dict], list[Flag]]
PACKS: dict[str, PackFn] = {"scrna": scrna.run}


def resolve_pack(name: str) -> PackFn:
    if name not in PACKS:
        raise UnknownPackError(f"unknown pack {name!r}; known packs: {sorted(PACKS)}")
    return PACKS[name]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest qa/tests/test_pack_scrna.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check qa/src/science_qa/packs
git add science/qa/src/science_qa/packs science/qa/tests/test_pack_scrna.py
git commit -m "feat(science-qa): scRNA modality pack + pack registry"
```

---

### Task A9: Runner orchestration + `run` CLI

**Files:**
- Create: `science/qa/src/science_qa/runner.py`
- Modify: `science/qa/src/science_qa/cli.py`
- Create: `science/qa/tests/test_runner.py`
- Create: `science/qa/tests/test_cli_run.py`

- [ ] **Step 1: Write the failing test**

`science/qa/tests/test_runner.py`:
```python
import pandas as pd

from science_qa.runner import run_qa


def _table(tmp_path):
    path = tmp_path / "analysis.parquet"
    pd.DataFrame({
        "SUBJECT_ID": [1, 2, 3],
        "total_counts": [1000, 1000, 1000],
        "n_genes_by_counts": [500, 500, 500],
        "pct_counts_mt": [5.0, 40.0, 6.0],
    }).to_parquet(path)
    return path


def _config(tmp_path):
    path = tmp_path / "qa.yaml"
    path.write_text(
        "qa:\n"
        "  unique_key: SUBJECT_ID\n"
        "  packs: [scrna]\n"
        "  pack_params: {scrna: {max_mito_pct: 20}}\n"
    )
    return path


def test_run_qa_writes_artifacts_and_reconciles(tmp_path):
    out = tmp_path / "out"
    result = run_qa(_config(tmp_path), _table(tmp_path), out)
    assert (out / "qa_report.json").exists()
    assert (out / "qa_report.md").exists()
    assert (out / "qa_dispositions.yaml").exists()
    # one distribution flag (high mito) → one open disposition stub
    assert result.structural_failed is False
    assert any(f.flag_id == "scrna/threshold/pct_counts_mt/max" for f in result.flags)


def test_structural_failure_sets_flag(tmp_path):
    path = tmp_path / "dups.parquet"
    pd.DataFrame({"SUBJECT_ID": [1, 1],
                  "total_counts": [1, 1], "n_genes_by_counts": [1, 1], "pct_counts_mt": [1.0, 1.0]}
                 ).to_parquet(path)
    cfg = tmp_path / "qa.yaml"
    cfg.write_text("qa:\n  unique_key: SUBJECT_ID\n")
    result = run_qa(cfg, path, tmp_path / "out")
    assert result.structural_failed is True
```

`science/qa/tests/test_cli_run.py`:
```python
import subprocess
import sys

import pandas as pd


def _setup(tmp_path):
    pd.DataFrame({"SUBJECT_ID": [1, 1]}).to_parquet(tmp_path / "t.parquet")
    (tmp_path / "qa.yaml").write_text("qa:\n  unique_key: SUBJECT_ID\n")


def test_cli_run_exits_nonzero_on_structural(tmp_path):
    _setup(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--config", str(tmp_path / "qa.yaml"),
         "--table", str(tmp_path / "t.parquet"),
         "--report-dir", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert (tmp_path / "out" / "qa_report.json").exists()  # report written BEFORE exit


def test_cli_run_no_strict_exits_zero(tmp_path):
    _setup(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "science_qa", "run",
         "--config", str(tmp_path / "qa.yaml"),
         "--table", str(tmp_path / "t.parquet"),
         "--report-dir", str(tmp_path / "out"), "--no-strict"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest qa/tests/test_runner.py qa/tests/test_cli_run.py -v`
Expected: FAIL (`No module named science_qa.runner`).

- [ ] **Step 3: Write the runner**

`science/qa/src/science_qa/runner.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from science_qa.checks import run_distribution_checks, run_structural_checks
from science_qa.config import QAConfig
from science_qa.dispositions import reconcile_dispositions
from science_qa.flags import SEVERITY_DISTRIBUTION, SEVERITY_STRUCTURAL, Flag
from science_qa.packs import resolve_pack
from science_qa.report import write_reports


@dataclass
class RunResult:
    flags: list[Flag]
    structural_failed: bool


def _read_table(table_path: Path) -> pd.DataFrame:
    if table_path.suffix == ".parquet":
        return pd.read_parquet(table_path)
    if table_path.suffix in {".csv", ".tsv"}:
        sep = "\t" if table_path.suffix == ".tsv" else ","
        return pd.read_csv(table_path, sep=sep)
    raise ValueError(f"unsupported table format: {table_path.suffix}")


def run_qa(config_path: Path, table_path: Path, report_dir: Path) -> RunResult:
    config = QAConfig.from_file(config_path)
    table = _read_table(table_path)

    flags: list[Flag] = []
    flags += run_structural_checks(table, config, base_dir=config_path.parent)
    flags += run_distribution_checks(table, config)
    for pack_name in config.packs:
        flags += resolve_pack(pack_name)(table, config.pack_params.get(pack_name, {}))

    write_reports(flags, report_dir=report_dir, rows_checked=len(table))
    distribution_ids = [f.flag_id for f in flags if f.severity == SEVERITY_DISTRIBUTION]
    reconcile_dispositions(report_dir, distribution_ids)

    structural_failed = any(f.severity == SEVERITY_STRUCTURAL for f in flags)
    return RunResult(flags=flags, structural_failed=structural_failed)
```

- [ ] **Step 4: Wire the `run` CLI**

Replace the placeholder `run_command` in `science/qa/src/science_qa/cli.py`:
```python
from __future__ import annotations

from pathlib import Path

import click

from science_qa.runner import run_qa


@click.group()
def cli() -> None:
    """science-qa command-line interface."""


@cli.command("run")
@click.option("--config", "config_path", type=click.Path(path_type=Path, exists=False), required=True)
@click.option("--table", "table_path", type=click.Path(path_type=Path, exists=False), required=True)
@click.option("--report-dir", "report_dir", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--no-strict", is_flag=True, default=False,
              help="Suppress the build-fatal exit code (local inspection only; never wire into a default target).")
def run_command(config_path: Path, table_path: Path, report_dir: Path, no_strict: bool) -> None:
    """Run QA checks over a built table; write qa_report.{md,json} + reconcile dispositions."""
    result = run_qa(config_path, table_path, report_dir)
    click.echo(f"{len(result.flags)} flag(s); structural_failed={result.structural_failed}")
    if result.structural_failed and not no_strict:
        raise SystemExit(1)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest qa/tests/test_runner.py qa/tests/test_cli_run.py -v`
Expected: PASS.

- [ ] **Step 6: Full science-qa suite + lint + commit**

```bash
uv run pytest qa/tests -v
uv run ruff check qa/src/science_qa
git add science/qa/src/science_qa/runner.py science/qa/src/science_qa/cli.py science/qa/tests/test_runner.py science/qa/tests/test_cli_run.py
git commit -m "feat(science-qa): runner orchestration + run CLI with exit contract"
```

---

## Phase B — `science qa-audit` (B3)

### Task B1: Pure two-axis verdict functions

**Files:**
- Create: `science/src/science_tool/qa_audit/__init__.py`
- Create: `science/src/science_tool/qa_audit/verdicts.py`
- Create: `science/tests/test_qa_audit_verdicts.py`

- [ ] **Step 1: Write the failing test**

`science/tests/test_qa_audit_verdicts.py`:
```python
from science_tool.qa_audit.verdicts import engagement_verdict, iteration_verdict, FlagDisposition


def fd(disposition, change=""):
    return FlagDisposition(disposition=disposition, change=change)


# --- engagement axis ---
def test_engagement_no_qa_when_no_report():
    assert engagement_verdict(has_report=False, flags=[]) == "NO-QA"


def test_engagement_no_flags():
    assert engagement_verdict(has_report=True, flags=[]) == "NO-FLAGS"


def test_engagement_ignored_all_open():
    assert engagement_verdict(has_report=True, flags=[fd("open"), fd("open")]) == "IGNORED"


def test_engagement_responded_all_resolved_engaged():
    flags = [fd("addressed", "min_genes=200"), fd("accepted-real"), fd("wont-fix")]
    assert engagement_verdict(has_report=True, flags=flags) == "RESPONDED"


def test_engagement_partial_for_investigating():
    assert engagement_verdict(has_report=True, flags=[fd("investigating")]) == "PARTIAL"


def test_engagement_partial_for_mix():
    assert engagement_verdict(has_report=True, flags=[fd("open"), fd("addressed", "x")]) == "PARTIAL"


# --- iteration axis ---
def test_iteration_single_run():
    assert iteration_verdict(chain_depth=1, flags=[fd("addressed", "x")]) == "SINGLE-RUN"


def test_iteration_qa_responsive_requires_rerun_and_change():
    assert iteration_verdict(chain_depth=2, flags=[fd("addressed", "min_genes=200")]) == "QA-RESPONSIVE"


def test_iteration_addressed_without_rerun_is_single_run():
    assert iteration_verdict(chain_depth=1, flags=[fd("addressed", "min_genes=200")]) == "SINGLE-RUN"


def test_iteration_rerun_without_qa_change_is_unrelated():
    assert iteration_verdict(chain_depth=2, flags=[fd("open")]) == "RE-RAN-UNRELATED"


def test_iteration_addressed_without_change_not_responsive():
    assert iteration_verdict(chain_depth=2, flags=[fd("addressed", "")]) == "RE-RAN-UNRELATED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_qa_audit_verdicts.py -v`
Expected: FAIL (`No module named science_tool.qa_audit`).

- [ ] **Step 3: Write minimal implementation**

`science/src/science_tool/qa_audit/__init__.py`:
```python
from __future__ import annotations
```

`science/src/science_tool/qa_audit/verdicts.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

RESOLVED_ENGAGED = {"addressed", "accepted-real", "wont-fix"}
PENDING = {"open", "investigating"}


@dataclass(frozen=True)
class FlagDisposition:
    disposition: str
    change: str = ""


def engagement_verdict(*, has_report: bool, flags: list[FlagDisposition]) -> str:
    """Total function over the flag set's disposition state.

    NO-QA (no report) / NO-FLAGS / RESPONDED (all resolved-engaged) /
    IGNORED (all open) / PARTIAL (anything else, incl. any `investigating`).
    """
    if not has_report:
        return "NO-QA"
    if not flags:
        return "NO-FLAGS"
    if all(f.disposition in RESOLVED_ENGAGED for f in flags):
        return "RESPONDED"
    if all(f.disposition == "open" for f in flags):
        return "IGNORED"
    return "PARTIAL"


def iteration_verdict(*, chain_depth: int, flags: list[FlagDisposition]) -> str:
    """QA-RESPONSIVE requires BOTH a supersedes re-run (chain_depth >= 2) AND a
    flag `addressed` with a non-empty `change`. A change without a re-run stays
    SINGLE-RUN here (and RESPONDED on the engagement axis)."""
    has_qa_change = any(f.disposition == "addressed" and f.change for f in flags)
    if chain_depth >= 2 and has_qa_change:
        return "QA-RESPONSIVE"
    if chain_depth >= 2:
        return "RE-RAN-UNRELATED"
    return "SINGLE-RUN"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_qa_audit_verdicts.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/science_tool/qa_audit
git add science/src/science_tool/qa_audit/__init__.py science/src/science_tool/qa_audit/verdicts.py science/tests/test_qa_audit_verdicts.py
git commit -m "feat(qa-audit): pure two-axis verdict functions"
```

---

### Task B2: Workflow-run loader + chain depth

**Files:**
- Create: `science/src/science_tool/qa_audit/runs.py`
- Create: `science/tests/test_qa_audit_runs.py`

- [ ] **Step 1: Write the failing test**

`science/tests/test_qa_audit_runs.py`:
```python
from pathlib import Path

from science_tool.qa_audit.runs import RunRecord, load_runs, chain_depth


def _run(dirpath: Path, slug, workflow, supersedes=None, manifest_path="results/x/datapackage.yaml"):
    fm = [
        "---",
        f'id: "workflow-run:{slug}"',
        'type: "workflow-run"',
        f'workflow: "{workflow}"',
        f'manifest_path: "{manifest_path}"',
    ]
    if supersedes:
        fm.append(f'supersedes: ["workflow-run:{supersedes}"]')
    fm += ["---", "", "body"]
    (dirpath / f"{slug}.md").write_text("\n".join(fm))


def test_load_runs_parses_frontmatter(tmp_path):
    _run(tmp_path, "r1", "wf-a")
    runs = load_runs(tmp_path)
    assert runs[0].run_id == "workflow-run:r1"
    assert runs[0].workflow == "wf-a"
    assert runs[0].manifest_path == "results/x/datapackage.yaml"
    assert runs[0].error is None


def test_missing_manifest_path_marks_error(tmp_path):
    (tmp_path / "bad.md").write_text('---\nid: "workflow-run:bad"\ntype: "workflow-run"\nworkflow: "wf-a"\n---\n')
    runs = load_runs(tmp_path)
    assert runs[0].error is not None


def test_chain_depth_counts_supersession(tmp_path):
    _run(tmp_path, "r1", "wf-a")
    _run(tmp_path, "r2", "wf-a", supersedes="r1")
    _run(tmp_path, "r3", "wf-a", supersedes="r2")
    runs = load_runs(tmp_path)
    assert chain_depth(runs, "wf-a") == 3


def test_chain_depth_single_run(tmp_path):
    _run(tmp_path, "r1", "wf-a")
    assert chain_depth(load_runs(tmp_path), "wf-a") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_qa_audit_runs.py -v`
Expected: FAIL (`No module named science_tool.qa_audit.runs`).

- [ ] **Step 3: Write minimal implementation**

`science/src/science_tool/qa_audit/runs.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from science_tool.markdown_utils import parse_frontmatter


@dataclass
class RunRecord:
    run_id: str
    workflow: str
    manifest_path: str
    supersedes: list[str] = field(default_factory=list)
    error: str | None = None


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value]


def load_runs(runs_dir: Path) -> list[RunRecord]:
    """Load authored workflow-run entities from doc/workflow-runs/*.md frontmatter.

    A run missing the machine-readable fields the audit depends on
    (manifest_path, workflow) is returned with `error` set rather than skipped.
    """
    records: list[RunRecord] = []
    for path in sorted(runs_dir.glob("*.md")):
        fm, _ = parse_frontmatter(path)
        run_id = str(fm.get("id", path.stem))
        workflow = fm.get("workflow")
        manifest_path = fm.get("manifest_path")
        error = None
        if not workflow:
            error = "missing 'workflow'"
        elif not manifest_path:
            error = "missing 'manifest_path'"
        records.append(RunRecord(
            run_id=run_id,
            workflow=str(workflow or ""),
            manifest_path=str(manifest_path or ""),
            supersedes=_as_list(fm.get("supersedes")),
            error=error,
        ))
    return records


def chain_depth(runs: list[RunRecord], workflow: str) -> int:
    """Number of runs in the workflow's supersession chain (1 == single run)."""
    return sum(1 for r in runs if r.workflow == workflow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_qa_audit_runs.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/science_tool/qa_audit/runs.py
git add science/src/science_tool/qa_audit/runs.py science/tests/test_qa_audit_runs.py
git commit -m "feat(qa-audit): workflow-run frontmatter loader + chain depth"
```

---

### Task B3: Manifest reader (QA resources + dispositions)

**Files:**
- Create: `science/src/science_tool/qa_audit/manifest.py`
- Create: `science/tests/test_qa_audit_manifest.py`

- [ ] **Step 1: Write the failing test**

`science/tests/test_qa_audit_manifest.py`:
```python
import json
from pathlib import Path

import yaml

from science_tool.qa_audit.manifest import load_qa_artifacts


def _manifest(run_dir: Path, resources):
    (run_dir / "datapackage.yaml").write_text(yaml.safe_dump({"name": "run", "resources": resources}))


def _report(path: Path, distribution_ids):
    path.write_text(json.dumps({
        "flags": [{"flag_id": fid, "severity": "distribution"} for fid in distribution_ids]
    }))


def _dispositions(path: Path, entries):
    path.write_text(yaml.safe_dump({"dispositions": entries}))


def test_single_substrate_pairs_report_and_dispositions(tmp_path):
    _report(tmp_path / "qa_report.json", ["scrna/threshold/pct_counts_mt/max"])
    _dispositions(tmp_path / "qa_dispositions.yaml",
                  [{"flag_id": "scrna/threshold/pct_counts_mt/max", "disposition": "addressed", "change": "x"}])
    _manifest(tmp_path, [
        {"name": "qa_report", "path": "qa_report.json"},
        {"name": "qa_dispositions", "path": "qa_dispositions.yaml"},
    ])
    has_report, flags = load_qa_artifacts(tmp_path / "datapackage.yaml")
    assert has_report is True
    assert flags[0].disposition == "addressed" and flags[0].change == "x"


def test_multi_substrate_aggregates(tmp_path):
    _report(tmp_path / "a.json", ["generic/range/glucose/max"])
    _report(tmp_path / "b.json", ["scrna/threshold/pct_counts_mt/max"])
    _dispositions(tmp_path / "a.yaml", [{"flag_id": "generic/range/glucose/max", "disposition": "open"}])
    _dispositions(tmp_path / "b.yaml", [{"flag_id": "scrna/threshold/pct_counts_mt/max", "disposition": "open"}])
    _manifest(tmp_path, [
        {"name": "qa_report:cells", "path": "a.json"},
        {"name": "qa_dispositions:cells", "path": "a.yaml"},
        {"name": "qa_report:bulk", "path": "b.json"},
        {"name": "qa_dispositions:bulk", "path": "b.yaml"},
    ])
    has_report, flags = load_qa_artifacts(tmp_path / "datapackage.yaml")
    assert has_report is True
    assert len(flags) == 2


def test_no_qa_resources_returns_false(tmp_path):
    _manifest(tmp_path, [{"name": "data", "path": "data.parquet"}])
    has_report, flags = load_qa_artifacts(tmp_path / "datapackage.yaml")
    assert has_report is False and flags == []


def test_open_flag_without_disposition_entry_defaults_open(tmp_path):
    _report(tmp_path / "qa_report.json", ["generic/range/glucose/max"])
    _manifest(tmp_path, [{"name": "qa_report", "path": "qa_report.json"}])
    has_report, flags = load_qa_artifacts(tmp_path / "datapackage.yaml")
    assert has_report is True
    assert flags[0].disposition == "open"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_qa_audit_manifest.py -v`
Expected: FAIL (`No module named science_tool.qa_audit.manifest`).

- [ ] **Step 3: Write minimal implementation**

`science/src/science_tool/qa_audit/manifest.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

import yaml

from science_tool.qa_audit.verdicts import FlagDisposition

VALID_DISPOSITIONS = {"open", "investigating", "addressed", "accepted-real", "wont-fix", "resolved"}


class QAManifestError(Exception):
    """Raised on an invalid disposition value (fail early; don't treat as open)."""


def _substrate_suffix(name: str, prefix: str) -> str | None:
    if name == prefix:
        return ""
    if name.startswith(prefix + ":"):
        return name[len(prefix) + 1 :]
    return None


def load_qa_artifacts(manifest_path: Path) -> tuple[bool, list[FlagDisposition]]:
    """Discover QA artifacts via a run's datapackage manifest.

    Selects resources named `qa_report` / `qa_report:<substrate>`, pairs each
    with its `qa_dispositions[:<substrate>]` counterpart, and returns
    (has_report, [FlagDisposition...]) aggregated across substrates. Manifests
    are YAML on disk (datapackage.yaml); JSON is also accepted.
    """
    text = manifest_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load(text) or {}
    base = manifest_path.parent
    resources = manifest.get("resources", []) or []

    reports: dict[str, Path] = {}
    dispositions: dict[str, Path] = {}
    for res in resources:
        name = str(res.get("name", ""))
        sub = _substrate_suffix(name, "qa_report")
        if sub is not None:
            reports[sub] = base / res["path"]
            continue
        sub = _substrate_suffix(name, "qa_dispositions")
        if sub is not None:
            dispositions[sub] = base / res["path"]

    if not reports:
        return (False, [])

    flags: list[FlagDisposition] = []
    for substrate, report_path in sorted(reports.items()):
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        dist_ids = [f["flag_id"] for f in payload.get("flags", []) if f.get("severity") == "distribution"]

        disp_map: dict[str, dict] = {}
        disp_path = dispositions.get(substrate)
        if disp_path and disp_path.exists():
            loaded = yaml.safe_load(disp_path.read_text(encoding="utf-8")) or {}
            for entry in loaded.get("dispositions", []) or []:
                disp_map[entry["flag_id"]] = entry

        for flag_id in dist_ids:
            entry = disp_map.get(flag_id, {})
            disposition = str(entry.get("disposition", "open"))
            if disposition not in VALID_DISPOSITIONS:
                raise QAManifestError(f"invalid disposition {disposition!r} for {flag_id!r}")
            flags.append(FlagDisposition(disposition=disposition, change=str(entry.get("change", "") or "")))

    return (True, flags)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_qa_audit_manifest.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/science_tool/qa_audit/manifest.py
git add science/src/science_tool/qa_audit/manifest.py science/tests/test_qa_audit_manifest.py
git commit -m "feat(qa-audit): manifest QA-resource discovery by stable name"
```

---

### Task B4: Audit orchestration + report rendering

**Files:**
- Create: `science/src/science_tool/qa_audit/audit.py`
- Create: `science/tests/test_qa_audit_audit.py`

- [ ] **Step 1: Write the failing test**

`science/tests/test_qa_audit_audit.py`:
```python
from pathlib import Path

import json
import yaml

from science_tool.qa_audit.audit import audit_workflows, render_markdown


def _run(dirpath: Path, slug, workflow, manifest_path, supersedes=None):
    fm = ["---", f'id: "workflow-run:{slug}"', 'type: "workflow-run"',
          f'workflow: "{workflow}"', f'manifest_path: "{manifest_path}"']
    if supersedes:
        fm.append(f'supersedes: ["workflow-run:{supersedes}"]')
    fm += ["---", "", "body"]
    (dirpath / f"{slug}.md").write_text("\n".join(fm))


def _manifest_with_open_flag(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "qa_report.json").write_text(json.dumps(
        {"flags": [{"flag_id": "scrna/threshold/pct_counts_mt/max", "severity": "distribution"}]}))
    (run_dir / "datapackage.yaml").write_text(yaml.safe_dump(
        {"name": "run", "resources": [{"name": "qa_report", "path": "qa_report.json"}]}))
    return run_dir / "datapackage.yaml"


def test_single_run_ignored_is_headline(tmp_path):
    runs_dir = tmp_path / "doc" / "workflow-runs"
    runs_dir.mkdir(parents=True)
    manifest = _manifest_with_open_flag(tmp_path / "results" / "wf-a")
    _run(runs_dir, "r1", "wf-a", str(manifest))
    rows = audit_workflows(runs_dir=runs_dir, repo_root=tmp_path)
    row = next(r for r in rows if r["workflow"] == "wf-a")
    assert row["iteration"] == "SINGLE-RUN"
    assert row["engagement"] == "IGNORED"


def test_missing_manifest_yields_error_row(tmp_path):
    runs_dir = tmp_path / "doc" / "workflow-runs"
    runs_dir.mkdir(parents=True)
    _run(runs_dir, "r1", "wf-a", str(tmp_path / "nope" / "datapackage.yaml"))
    rows = audit_workflows(runs_dir=runs_dir, repo_root=tmp_path)
    assert rows[0]["engagement"] == "ERROR"


def test_render_markdown_has_header_and_rows(tmp_path):
    rows = [{"workflow": "wf-a", "runs": 1, "chain_depth": 1,
             "open_flags": 1, "dispositioned_flags": 0,
             "iteration": "SINGLE-RUN", "engagement": "IGNORED"}]
    md = render_markdown(rows)
    assert "| Workflow |" in md
    assert "wf-a" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_qa_audit_audit.py -v`
Expected: FAIL (`No module named science_tool.qa_audit.audit`).

- [ ] **Step 3: Write minimal implementation**

`science/src/science_tool/qa_audit/audit.py`:
```python
from __future__ import annotations

from pathlib import Path

from science_tool.qa_audit.manifest import load_qa_artifacts
from science_tool.qa_audit.runs import chain_depth, load_runs
from science_tool.qa_audit.verdicts import RESOLVED_ENGAGED, engagement_verdict, iteration_verdict


def audit_workflows(*, runs_dir: Path, repo_root: Path) -> list[dict]:
    runs = load_runs(runs_dir)
    workflows = sorted({r.workflow for r in runs if r.workflow})
    rows: list[dict] = []

    for workflow in workflows:
        wf_runs = [r for r in runs if r.workflow == workflow]
        depth = chain_depth(runs, workflow)
        # Use the last authored run for QA artifact discovery (single run in the MVP case).
        latest = wf_runs[-1]

        try:
            if latest.error:
                raise FileNotFoundError(latest.error)
            manifest_path = (repo_root / latest.manifest_path)
            if not manifest_path.exists():
                raise FileNotFoundError(f"manifest not found: {manifest_path}")
            has_report, flags = load_qa_artifacts(manifest_path)
        except Exception as exc:  # noqa: BLE001 — per-row ERROR, audit must not crash
            rows.append({
                "workflow": workflow, "runs": len(wf_runs), "chain_depth": depth,
                "open_flags": 0, "dispositioned_flags": 0,
                "iteration": "ERROR", "engagement": "ERROR", "detail": str(exc),
            })
            continue

        open_flags = sum(1 for f in flags if f.disposition == "open")
        dispositioned = sum(1 for f in flags if f.disposition in RESOLVED_ENGAGED)
        rows.append({
            "workflow": workflow, "runs": len(wf_runs), "chain_depth": depth,
            "open_flags": open_flags, "dispositioned_flags": dispositioned,
            "iteration": iteration_verdict(chain_depth=depth, flags=flags),
            "engagement": engagement_verdict(has_report=has_report, flags=flags),
        })
    return rows


def render_markdown(rows: list[dict]) -> str:
    header = (
        "| Workflow | Runs | Chain | Open | Dispositioned | Iteration | Engagement |\n"
        "| --- | --- | --- | --- | --- | --- | --- |"
    )
    body = [
        f"| {r['workflow']} | {r['runs']} | {r['chain_depth']} | {r['open_flags']} | "
        f"{r['dispositioned_flags']} | {r['iteration']} | {r['engagement']} |"
        for r in rows
    ]
    return "\n".join([header, *body]) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_qa_audit_audit.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/science_tool/qa_audit/audit.py
git add science/src/science_tool/qa_audit/audit.py science/tests/test_qa_audit_audit.py
git commit -m "feat(qa-audit): per-workflow two-axis audit + markdown render"
```

---

### Task B5: `science qa-audit` CLI command + registration

**Files:**
- Create: `science/src/science_tool/qa_audit/cli.py`
- Modify: `science/src/science_tool/cli.py` (import + `main.add_command`)
- Create: `science/tests/test_qa_audit_cli.py`

- [ ] **Step 1: Write the failing test**

`science/tests/test_qa_audit_cli.py`:
```python
import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.qa_audit.cli import qa_audit_command


def _setup(tmp_path: Path):
    runs_dir = tmp_path / "doc" / "workflow-runs"
    runs_dir.mkdir(parents=True)
    run_dir = tmp_path / "results" / "wf-a"
    run_dir.mkdir(parents=True)
    (run_dir / "qa_report.json").write_text(json.dumps(
        {"flags": [{"flag_id": "scrna/threshold/pct_counts_mt/max", "severity": "distribution"}]}))
    (run_dir / "datapackage.yaml").write_text(yaml.safe_dump(
        {"name": "run", "resources": [{"name": "qa_report", "path": "qa_report.json"}]}))
    (runs_dir / "r1.md").write_text(
        '---\nid: "workflow-run:r1"\ntype: "workflow-run"\nworkflow: "wf-a"\n'
        f'manifest_path: "{run_dir / "datapackage.yaml"}"\n---\nbody\n')


def test_cli_prints_table_and_exits_zero(tmp_path):
    _setup(tmp_path)
    result = CliRunner().invoke(
        qa_audit_command,
        ["--runs-dir", str(tmp_path / "doc" / "workflow-runs"), "--repo-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert "wf-a" in result.output
    assert "IGNORED" in result.output


def test_cli_json_output(tmp_path):
    _setup(tmp_path)
    result = CliRunner().invoke(
        qa_audit_command,
        ["--runs-dir", str(tmp_path / "doc" / "workflow-runs"), "--repo-root", str(tmp_path), "--json"],
    )
    assert result.exit_code == 0
    rows = json.loads(result.output)
    assert rows[0]["workflow"] == "wf-a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_qa_audit_cli.py -v`
Expected: FAIL (`No module named science_tool.qa_audit.cli`).

- [ ] **Step 3: Write the CLI command**

`science/src/science_tool/qa_audit/cli.py`:
```python
from __future__ import annotations

import json
from pathlib import Path

import click

from science_tool.qa_audit.audit import audit_workflows, render_markdown


@click.command("qa-audit")
@click.option("--runs-dir", type=click.Path(path_type=Path), default=Path("doc/workflow-runs"),
              show_default=True, help="Directory of authored workflow-run entities.")
@click.option("--repo-root", type=click.Path(path_type=Path), default=Path("."), show_default=True,
              help="Repo root used to resolve each run's manifest_path.")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None,
              help="Optional file to write the markdown report to.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON rows instead of a table.")
def qa_audit_command(runs_dir: Path, repo_root: Path, out_path: Path | None, as_json: bool) -> None:
    """Advisory process-quality audit: flag single-run / QA-ignoring workflows.

    Always exits 0 — this never gates a build or `science validate`.
    """
    if not runs_dir.exists():
        raise click.ClickException(f"runs dir not found: {runs_dir}")
    rows = audit_workflows(runs_dir=runs_dir, repo_root=repo_root)
    if as_json:
        click.echo(json.dumps(rows, indent=2, sort_keys=True))
        return
    md = render_markdown(rows)
    click.echo(md, nl=False)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
```

- [ ] **Step 4: Register the command in the main CLI**

In `science/src/science_tool/cli.py`, add an import near the other command imports (find an existing `from science_tool.wander.cli import wander_command` style import; if absent, add it next to where `wander_command` is referenced):
```python
from science_tool.qa_audit.cli import qa_audit_command
```
Then, alongside the existing `main.add_command(...)` block (around line 229 where `main.add_command(wander_command)` lives), add:
```python
main.add_command(qa_audit_command)
```

- [ ] **Step 5: Run tests + verify CLI is wired**

Run: `uv run pytest tests/test_qa_audit_cli.py -v`
Expected: PASS.

Run: `uv run science qa-audit --help`
Expected: help text for `qa-audit` prints (exit 0).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/science_tool/qa_audit/cli.py src/science_tool/cli.py
git add science/src/science_tool/qa_audit/cli.py science/src/science_tool/cli.py science/tests/test_qa_audit_cli.py
git commit -m "feat(qa-audit): science qa-audit CLI command + registration"
```

---

## Phase C — Docs, template & convention updates

### Task C1: workflow-run template — machine-readable fields

**Files:**
- Modify: `templates/workflow-run.md`

- [ ] **Step 1: Add frontmatter fields + fix manifest extension**

In `templates/workflow-run.md`, change the frontmatter block to add `manifest_path` and `supersedes` (so the audit reads them from frontmatter, not prose), and update the body Manifest location extension. New frontmatter:
```yaml
---
id: "workflow-run:<slug>"
type: "workflow-run"
title: "<Run Description>"
status: "complete"
workflow: "<workflow-slug>"          # materializes the executes link the audit walks
manifest_path: "results/<workflow>/<slug>/datapackage.yaml"  # read by `science qa-audit`
supersedes: []                       # ["workflow-run:<prior-slug>"] when re-run with changed params
# Symmetric edges (populated by `science dataset register-run`).
# `produces:` is the inverse of dataset.derivation.workflow_run (state invariant #9).
# `inputs:` enumerates upstream datasets the run consumed; symmetric with each
# upstream dataset's consumed_by listing this workflow-run.
produces: []                       # ["dataset:<slug>", ...]
inputs: []                         # ["dataset:<slug>", ...]
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---
```
And in the body `## Manifest` section, change the location line from `datapackage.json` to `datapackage.yaml`:
```markdown
## Manifest

- **Location:** `results/<workflow>/<slug>/datapackage.yaml`
- **Config snapshot:** `results/<workflow>/<slug>/config.yaml`
```
Leave the prose `**Supersedes:**` line under *Entity Cross-References* (it stays as human narration) but note the canonical machine-readable source is now the frontmatter `supersedes:` field.

- [ ] **Step 2: Validate the template still parses**

Run: `uv run python -c "from pathlib import Path; from science_tool.markdown_utils import parse_frontmatter; fm,_=parse_frontmatter(Path('../templates/workflow-run.md')); assert 'manifest_path' in fm and 'supersedes' in fm; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add templates/workflow-run.md
git commit -m "docs(templates): workflow-run carries manifest_path + supersedes frontmatter"
```

> **Follow-up note (not a code change here):** `science dataset register-run` should populate `manifest_path` to the run's `datapackage.yaml` where it already writes the symmetric `produces`/`inputs` edges. If the maintainer confirms `register-run` is the authoring path, open a separate task to wire that population; this plan's audit already degrades to a per-row ERROR for runs lacking the field, so it is not a blocker.

---

### Task C2: pipeline-qa-checkpoints.md — reference-implementation note

**Files:**
- Modify: `docs/conventions/pipeline-qa-checkpoints.md`

- [ ] **Step 1: Add a "Reference implementation" subsection**

Insert before the `## See also` section:
```markdown
## Reference implementation

The `science-qa` distribution (`science/qa/`, command `python -m science_qa run`) executes this
exact `qa:` schema — `unique_key`, `required_complete`, `categoricals` (`allowed` / `allowed_from`),
`exclusive_flags`, `ranges`, `missing_sentinels` — and applies the structural/distribution severity
split above. Modality packs (e.g. `packs: [scrna]`) add domain checks the declarative config cannot
express. The convention remains the contract; the runner is one implementation of it.

The runner also formalizes the "analyst decides at model time" step for distribution flags: it
emits `qa_report.json` (an immutable flag ledger) and scaffolds an analyst-owned
`qa_dispositions.yaml`. Like the report, the disposition file **must not** be a strict rule's
declared output — it holds hand-entered data a failed-job cleanup would delete. Write it outside the
strict gate's output set and reference it as a manifest resource (`qa_dispositions`).
```

- [ ] **Step 2: Verify markdown links resolve**

Run: `uv run science validate` (from the repo root project that owns these docs, if applicable) — or visually confirm no new links were introduced. Expected: no new broken-link warnings.

- [ ] **Step 3: Commit**

```bash
git add docs/conventions/pipeline-qa-checkpoints.md
git commit -m "docs(conventions): note science-qa as the QA-checkpoint reference implementation"
```

---

### Task C3: pipeline-audit-and-refactor.md — process-iteration discipline

**Files:**
- Modify: `docs/process/pipeline-audit-and-refactor.md`

- [ ] **Step 1: Add process-iteration to "Related QA disciplines"**

In the `## Related QA disciplines` section, add a third bullet after the workflow/DAG-validation entry:
```markdown
- **Process iteration** — validates the *process*, not a table or the rule graph: did the analysis
  iterate (QC / clustering / parameters) in response to QA flags, or run once and record the result
  as truth? Scored during the sweep with `science qa-audit`, which reads each workflow's
  `workflow-run` / `sci:supersedes` chain and its QA dispositions and reports two verdicts —
  an *iteration* axis (QA-RESPONSIVE / RE-RAN-UNRELATED / SINGLE-RUN) and a *QA-engagement* axis
  (NO-QA / NO-FLAGS / RESPONDED / IGNORED / PARTIAL). The headline advisory is the
  SINGLE-RUN × IGNORED workflow. Advisory only — it never fails the build.
```

- [ ] **Step 2: Add a findings/synthesis note**

In the `### findings.md` skeleton's Axis-1 block (where DAG-validation is recorded), add a line:
```markdown
  - process-iteration (`science qa-audit`): <iteration verdict> × <engagement verdict>
```

- [ ] **Step 3: Commit**

```bash
git add docs/process/pipeline-audit-and-refactor.md
git commit -m "docs(process): add process-iteration discipline (science qa-audit)"
```

---

### Task C4: computational-analysis.md — review-pipeline rubric row

**Files:**
- Modify: `aspects/computational-analysis/computational-analysis.md`

- [ ] **Step 1: Add a Process-iteration rubric dimension**

In `## review-pipeline` → `### Additional rubric dimension: QA Coverage`, after the **Severity split** bullet add:
```markdown
- **Process iteration:** Did the analysis iterate in response to QA flags, or run once and record
  the result? Run `science qa-audit`. Score: PASS (QA-RESPONSIVE) / WARN (PARTIAL or
  RE-RAN-UNRELATED) / FAIL (SINGLE-RUN × IGNORED — ran once, flags unexamined).
```

- [ ] **Step 2: Add a plan-pipeline dispositions note**

In `## plan-pipeline` → `### Additional section: QA Checkpoints`, after the paragraph pointing at
`pipeline-qa-checkpoints.md`, add:
```markdown
Plan the QA step to emit `qa_report.{md,json}` and scaffold `qa_dispositions.yaml` (e.g. via
`python -m science_qa run`), and record analyst decisions on distribution flags there — this is what
`science qa-audit` reads to tell genuine QC iteration from a one-shot run.
```

- [ ] **Step 3: Commit**

```bash
git add aspects/computational-analysis/computational-analysis.md
git commit -m "docs(aspect): process-iteration rubric row + dispositions note"
```

---

## Final verification

- [ ] **Step 1: Run the full science-qa suite**

Run: `uv run pytest qa/tests -v`
Expected: all PASS.

- [ ] **Step 2: Run the qa-audit suite**

Run: `uv run pytest tests/test_qa_audit_verdicts.py tests/test_qa_audit_runs.py tests/test_qa_audit_manifest.py tests/test_qa_audit_audit.py tests/test_qa_audit_cli.py -v`
Expected: all PASS.

- [ ] **Step 3: Lint the whole change**

Run: `uv run ruff check qa/src/science_qa src/science_tool/qa_audit`
Expected: no errors.

- [ ] **Step 4: Smoke-test both commands end to end**

Run: `uv run python -m science_qa run --help` and `uv run science qa-audit --help`
Expected: both print help, exit 0.

---

## Spec coverage check (self-review)

- B1 config-runner + qa: schema reuse → Tasks A3–A6, A9.
- scRNA pack + composition interface → Task A8.
- Disposition record, analyst-owned, never a rule output → Task A7 (+ convention note C2).
- Namespaced flag_id → Task A2.
- Determinism (no wall-clock) → Task A6 (`test_output_is_deterministic`).
- Light standalone distribution, one-way dependency → Task A1 (`test_science_qa_does_not_import_science_tool`).
- B3 two-axis verdicts incl. `investigating` home + QA-RESPONSIVE requires rerun → Task B1.
- Canonical sources (graph topology + manifest artifacts) → Tasks B2 (frontmatter) + B3 (manifest).
- Substrate-scoped resource names → Task B3 (`test_multi_substrate_aggregates`).
- Per-row ERROR, always exit 0 → Tasks B4/B5.
- workflow-run authoring fields → Task C1.
- Convention / playbook / aspect extensions → Tasks C2–C4.
- Out of scope (B2 breadth scoring, extra packs, non-table substrates, validate gating) → not implemented, by design.
