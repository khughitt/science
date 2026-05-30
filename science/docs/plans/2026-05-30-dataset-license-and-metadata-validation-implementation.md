# Dataset `license` + metadata validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dataset `license` a first-class, captured, materialized, queryable property and add warn-level vocabulary checks for `license`, `tier`, and `update_cadence`.

**Architecture:** Capture `license` on the base `Entity` (the markdown parse path returns a plain `Entity`, gated to `kind`, like `source_class`), thread it through frontmatter parsing and the datapackage adapter, emit it as `sci:license` in graph materialization, and register that predicate. Validation lives in a new check module that reads **raw frontmatter** (never crashing the loader) and emits warnings only. `tier`/`update_cadence` get validation only.

**Tech Stack:** Python 3.13/3.14, Pydantic v2, rdflib, pytest, `uv`. Two packages: `science_model` (model/schemas/templates under `model/`) and `science_tool` (CLI/graph/validate under `src/`).

**Spec:** `docs/plans/2026-05-30-dataset-license-and-metadata-validation.md`

**Branch:** `feat/dataset-license-metadata-validation` (already created)

**Run tests with:** `uv run --frozen pytest <path> -v` from `~/d/science/science`.

---

## File Structure

| File | Responsibility | New? |
|---|---|---|
| `model/src/science_model/licenses.py` | License vocabulary: `KNOWN_LICENSES`, `LICENSE_SENTINELS`, `suggest()` | new |
| `model/src/science_model/entities.py` | add `license: str = ""` to `Entity` | modify |
| `model/src/science_model/frontmatter.py` | thread `license` into `entity_kwargs` | modify |
| `src/science_tool/graph/storage_adapters/datapackage.py` | add `"license"` to `_ENTITY_FIELDS` | modify |
| `src/science_tool/graph/materialize.py` | emit `sci:license` for datasets in `_add_entity` | modify |
| `src/science_tool/graph/store/constants.py` | register `sci:license` (edge-metadata set + predicate registry) | modify |
| `src/science_tool/validate/checks/dataset_metadata.py` | license/tier/cadence checks | new |
| `src/science_tool/validate/checks/__init__.py` | register `dataset_metadata` module | modify |
| `model/src/science_model/schemas/mixin-dataset-1.0.json` | add `license` property | modify |
| `model/src/science_model/templates/dataset.md` | note sentinels in `license` comment | modify |
| `templates/dataset.md` (workspace root) | same comment update | modify |
| `model/tests/test_licenses.py` | vocabulary unit tests | new |
| `model/tests/test_frontmatter_license.py` | parse-path regression test | new |
| `tests/validate/test_checks_dataset_metadata.py` | pure-core + registration + integration + schema-sync tests | new |
| `tests/test_license_materialize.py` | datapackage-extraction + materialization + predicate-registry tests | new |
| `model/tests/test_mixin_dataset_schema_license.py` | mixin schema has `license` | new |

> **Test layout:** `science_model` tests live under `model/tests/` (the package's own test tree, with its `__init__.py` and `fixtures/`); `science_tool` tests live under `tests/`. Put each new test in the tree matching the package it exercises.

---

## Task 1: License vocabulary module

**Files:**
- Create: `model/src/science_model/licenses.py`
- Test: `model/tests/test_licenses.py`

- [ ] **Step 1: Write the failing test**

Create `model/tests/test_licenses.py`:

```python
from __future__ import annotations

from science_model.licenses import (
    KNOWN_LICENSES,
    LICENSE_SENTINELS,
    is_recognized,
    suggest,
)


def test_known_licenses_include_common_data_licenses() -> None:
    for lic in ("CC-BY-4.0", "CC0-1.0", "ODbL-1.0", "MIT", "Apache-2.0"):
        assert lic in KNOWN_LICENSES


def test_sentinels_are_unknown_proprietary_custom() -> None:
    assert LICENSE_SENTINELS == frozenset({"unknown", "proprietary", "custom"})


def test_is_recognized_accepts_known_and_sentinels_case_sensitively() -> None:
    assert is_recognized("CC-BY-4.0") is True
    assert is_recognized("unknown") is True
    assert is_recognized("cc-by-4.0") is False  # wrong case -> not recognized (but suggestible)
    assert is_recognized("Totally Made Up") is False


def test_suggest_matches_case_and_separator_variants() -> None:
    assert suggest("cc-by-4.0") == "CC-BY-4.0"
    assert suggest("CC_BY_4.0") == "CC-BY-4.0"
    assert suggest("apache 2.0") == "Apache-2.0"


def test_suggest_returns_none_for_gibberish_and_empty() -> None:
    assert suggest("zzzzz") is None
    assert suggest("") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest model/tests/test_licenses.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'science_model.licenses'`

- [ ] **Step 3: Write the implementation**

Create `model/src/science_model/licenses.py`:

```python
"""Curated, SPDX-aligned license vocabulary for dataset entities.

Membership is exact (case-sensitive); `suggest()` is fuzzy and only used to
build "did you mean" hints. Deliberately a single small module so the allow-list
is easy to extend. Per-project extensibility is a future enhancement.
"""

from __future__ import annotations

import difflib

KNOWN_LICENSES: frozenset[str] = frozenset(
    {
        "CC-BY-4.0",
        "CC-BY-SA-4.0",
        "CC-BY-NC-4.0",
        "CC0-1.0",
        "ODbL-1.0",
        "ODC-BY-1.0",
        "PDDL-1.0",
        "MIT",
        "Apache-2.0",
        "BSD-3-Clause",
        "GPL-3.0-only",
        "LGPL-3.0-only",
    }
)

# Honest non-license states. They satisfy presence (clear the missing-license
# warning) without being treated as a real license.
LICENSE_SENTINELS: frozenset[str] = frozenset({"unknown", "proprietary", "custom"})

_CASE_INSENSITIVE = {lic.lower(): lic for lic in KNOWN_LICENSES}


def is_recognized(value: str) -> bool:
    """True iff `value` is exactly a known license id or a sentinel."""
    return value in KNOWN_LICENSES or value in LICENSE_SENTINELS


def suggest(value: str) -> str | None:
    """Closest known license id for a "did you mean" hint, or None.

    Tries a case-insensitive / separator-normalized exact match first, then a
    fuzzy match against the known ids. Never returns a sentinel.
    """
    candidate = value.strip()
    if not candidate:
        return None
    normalized = candidate.lower().replace("_", "-").replace(" ", "-")
    if normalized in _CASE_INSENSITIVE:
        return _CASE_INSENSITIVE[normalized]
    close = difflib.get_close_matches(candidate, list(KNOWN_LICENSES), n=1, cutoff=0.6)
    return close[0] if close else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest model/tests/test_licenses.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add model/src/science_model/licenses.py model/tests/test_licenses.py
git commit -m "feat(model): add curated license vocabulary (KNOWN_LICENSES, sentinels, suggest)"
```

---

## Task 2: Capture `license` on `Entity` + thread through frontmatter

**Files:**
- Modify: `model/src/science_model/entities.py` (add field beside `source_class`, ~line 320)
- Modify: `model/src/science_model/frontmatter.py` (`entity_kwargs` dict, ~line 371)
- Test: `model/tests/test_frontmatter_license.py`

- [ ] **Step 1: Write the failing test**

Create `model/tests/test_frontmatter_license.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_model.frontmatter import parse_entity_file

_DATASET_MD = """\
---
id: "dataset:demo"
type: "dataset"
title: "Demo dataset"
status: "active"
origin: "external"
tier: "use-now"
license: "CC-BY-4.0"
update_cadence: "static"
ontology_terms: []
created: "2026-05-30"
updated: "2026-05-30"
---

# Demo dataset
"""


def test_license_survives_markdown_parse(tmp_path: Path) -> None:
    path = tmp_path / "demo.md"
    path.write_text(_DATASET_MD, encoding="utf-8")

    entity = parse_entity_file(path, project_slug="demo")

    assert entity is not None
    # parse_entity_file returns a plain Entity for datasets; the field must live
    # on Entity (not DatasetEntity) or it would be dropped by extra="ignore".
    assert entity.license == "CC-BY-4.0"


def test_license_defaults_empty_when_absent(tmp_path: Path) -> None:
    path = tmp_path / "nolic.md"
    path.write_text(_DATASET_MD.replace('license: "CC-BY-4.0"\n', ""), encoding="utf-8")

    entity = parse_entity_file(path, project_slug="demo")

    assert entity is not None
    assert entity.license == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest model/tests/test_frontmatter_license.py -v`
Expected: FAIL — `AttributeError: 'Entity' object has no attribute 'license'`

- [ ] **Step 3: Add the field to `Entity`**

In `model/src/science_model/entities.py`, in the `Entity` class, locate the dataset-unification block (the line `source_class: str | None = None`, ~line 320) and add `license` just above it:

```python
    parent_dataset: str = ""
    siblings: list[str] = Field(default_factory=list)
    # Dataset license (SPDX id or sentinel). On Entity (gated to kind) so the
    # parse_entity_file path, which returns a plain Entity for datasets, keeps it.
    license: str = ""
    # Pillar A — epistemic class (orthogonal to origin) + co-owned forward provenance
    source_class: str | None = None       # "observational" | "derived" | "reference"
```

- [ ] **Step 4: Thread it through `entity_kwargs`**

In `model/src/science_model/frontmatter.py`, in the `entity_kwargs = { ... }` dict, locate `"source_class": fm.get("source_class"),` (~line 371) and add directly above it:

```python
        "license": fm.get("license", ""),
        "source_class": fm.get("source_class"),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --frozen pytest model/tests/test_frontmatter_license.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add model/src/science_model/entities.py model/src/science_model/frontmatter.py model/tests/test_frontmatter_license.py
git commit -m "feat(model): capture dataset license on Entity + thread through frontmatter parse"
```

---

## Task 3: Extract `license` in the datapackage adapter

**Files:**
- Modify: `src/science_tool/graph/storage_adapters/datapackage.py` (`_ENTITY_FIELDS`, ~line 33)
- Test: covered by the materialization test in Task 5 (which sources a dataset from a datapackage). This task is the one-line extraction change.

- [ ] **Step 1: Add `license` to the allow-list**

In `src/science_tool/graph/storage_adapters/datapackage.py`, in the `_ENTITY_FIELDS` tuple, add `"license"` immediately after `"source_class",`:

```python
    "source_class",
    "license",
    "derived_kind",
```

- [ ] **Step 2: Verify nothing breaks yet**

Run: `uv run --frozen pytest tests/test_datasets.py -v`
Expected: PASS (no regressions; license simply now flows through)

- [ ] **Step 3: Commit**

```bash
git add src/science_tool/graph/storage_adapters/datapackage.py
git commit -m "feat(graph): extract dataset license from datapackage sources"
```

---

## Task 4: Validation check module (license/tier/cadence) + registration

**Files:**
- Create: `src/science_tool/validate/checks/dataset_metadata.py`
- Modify: `src/science_tool/validate/checks/__init__.py` (add `"dataset_metadata"` to `_load_canonical_checks`)
- Test: `tests/validate/test_checks_dataset_metadata.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/validate/test_checks_dataset_metadata.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from science_tool.validate.checks.dataset_metadata import (
    _ALLOWED_CADENCES,
    evaluate_dataset_metadata,
)
from science_tool.validate.result import Severity


def _rules(datasets: list[dict]) -> list[tuple[Severity, str]]:
    return [(r.severity, r.rule) for r in evaluate_dataset_metadata(datasets)]


def _ds(**kw) -> dict:
    base = {"type": "dataset", "id": "dataset:x", "_path": "doc/datasets/x.md"}
    base.update(kw)
    return base


def test_external_missing_license_warns() -> None:
    assert (Severity.WARN, "dataset.license-missing") in _rules([_ds(origin="external")])


def test_derived_missing_license_is_exempt() -> None:
    rules = _rules([_ds(origin="derived")])
    assert (Severity.WARN, "dataset.license-missing") not in rules


def test_valid_license_passes_silently() -> None:
    assert _rules([_ds(origin="external", license="CC-BY-4.0")]) == []


def test_sentinel_license_clears_missing_without_unrecognized() -> None:
    assert _rules([_ds(origin="external", license="unknown")]) == []


def test_unrecognized_license_warns() -> None:
    assert (Severity.WARN, "dataset.license-unrecognized") in _rules(
        [_ds(origin="external", license="cc-by-4.0")]
    )


def test_unrecognized_tier_warns() -> None:
    assert (Severity.WARN, "dataset.tier-unrecognized") in _rules(
        [_ds(origin="external", license="MIT", tier="use_now")]
    )


def test_versioned_releases_cadence_is_clean() -> None:
    rules = _rules([_ds(origin="external", license="MIT", update_cadence="versioned-releases")])
    assert (Severity.WARN, "dataset.cadence-unrecognized") not in rules


def test_unrecognized_cadence_warns() -> None:
    assert (Severity.WARN, "dataset.cadence-unrecognized") in _rules(
        [_ds(origin="external", license="MIT", update_cadence="hourly")]
    )


def test_absent_tier_and_cadence_not_flagged() -> None:
    rules = _rules([_ds(origin="external", license="MIT")])
    assert (Severity.WARN, "dataset.tier-unrecognized") not in rules
    assert (Severity.WARN, "dataset.cadence-unrecognized") not in rules


def test_non_dataset_rows_ignored() -> None:
    # evaluate_dataset_metadata yields an iterator — must materialize before comparing.
    assert list(evaluate_dataset_metadata([{"type": "paper", "id": "paper:x", "_path": "p.md"}])) == []


def test_non_string_license_is_unrecognized_not_crash() -> None:
    # license: 123 must not raise AttributeError on .strip(); treat as unrecognized.
    assert (Severity.WARN, "dataset.license-unrecognized") in _rules(
        [_ds(origin="external", license=123)]
    )


def test_non_string_tier_is_unrecognized_not_crash() -> None:
    # tier: [] must not raise TypeError on set membership; treat as unrecognized.
    assert (Severity.WARN, "dataset.tier-unrecognized") in _rules(
        [_ds(origin="external", license="MIT", tier=[])]
    )


def test_non_string_cadence_is_unrecognized_not_crash() -> None:
    assert (Severity.WARN, "dataset.cadence-unrecognized") in _rules(
        [_ds(origin="external", license="MIT", update_cadence=[1])]
    )


def test_module_is_registered() -> None:
    # Importing the checks package triggers _load_canonical_checks; the new
    # module must be wired in or it silently never runs.
    from science_tool.validate.checks import CANONICAL_CHECKS

    assert any(entry.fn.__module__.endswith("dataset_metadata") for entry in CANONICAL_CHECKS)


def test_license_missing_surfaces_through_runner(tmp_path: Path) -> None:
    # End-to-end: the finding must appear in a real validate run, not just in
    # the pure core. Proves wiring (registration + raw-frontmatter discovery).
    from science_tool.validate.runner import run

    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    ds_dir = tmp_path / "doc" / "datasets"
    ds_dir.mkdir(parents=True)
    (ds_dir / "x.md").write_text(
        '---\n'
        'id: "dataset:x"\n'
        'type: "dataset"\n'
        'title: "X"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'ontology_terms: []\n'
        '---\n\n# X\n',
        encoding="utf-8",
    )

    result = run(tmp_path, strict=False, verbose=False, enable_python_sidecar=False)

    assert any(r.rule == "dataset.license-missing" for r in result.results)


def test_cadence_vocabulary_equals_schema_enum() -> None:
    # The check's cadence set must equal the authoritative schema enum (minus "")
    # so a value cannot pass the check yet fail schema validation, or vice versa.
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "model/src/science_model/schemas/science-pkg-entity-1.0.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    enum = set(schema["properties"]["update_cadence"]["enum"]) - {""}
    assert _ALLOWED_CADENCES == enum
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/validate/test_checks_dataset_metadata.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.validate.checks.dataset_metadata'`

- [ ] **Step 3: Write the check module**

Create `src/science_tool/validate/checks/dataset_metadata.py`:

```python
"""Dataset metadata vocabulary checks: license, tier, update_cadence.

Reads RAW frontmatter via `dataset_frontmatters` (matching dataset_taxonomy.py) so
a malformed entity can never crash the strict loader. All findings are WARN — never
ERROR — so nothing blocks `validate` by default.

The allowed-cadence set is kept equal to the `update_cadence` enum in
science-pkg-entity-1.0.json (a test enforces the equality); growing the vocabulary
means updating the schema first, then this constant.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from science_model.licenses import LICENSE_SENTINELS, is_recognized, suggest

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_ALLOWED_TIERS = {"use-now", "evaluate-next", "track"}
_ALLOWED_CADENCES = {
    "static",
    "rolling",
    "monthly",
    "quarterly",
    "annual",
    "versioned-releases",
}


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _enum_finding(
    value: object, allowed: set[str], *, path: str | None, ident: str, field: str, rule: str
) -> Result | None:
    """Warn when a present value is non-string or outside `allowed`. Absent
    (None / "" / whitespace-only string) → no finding. Never raises on odd types."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped in allowed:
            return None
        display: object = stripped
    else:
        # Present but not a string (e.g. a list or int): unrecognized, not a crash.
        display = value
    return _result(
        Severity.WARN,
        path,
        f"{ident}: unrecognized {field} {display!r} (expected one of {sorted(allowed)})",
        rule,
    )


def evaluate_dataset_metadata(datasets: Iterable[dict]) -> Iterator[Result]:
    """Pure core: `datasets` are raw frontmatter dicts (each with `_path`).

    Defensive against malformed raw frontmatter: non-string license/tier/cadence
    values become warnings, never exceptions (this runs on un-validated input).
    """
    for fm in datasets:
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        origin = fm.get("origin")

        # --- license ---
        license_raw = fm.get("license")
        if isinstance(license_raw, str):
            license_value: str | None = license_raw.strip()
        elif license_raw is None:
            license_value = ""
        else:
            license_value = None  # present but non-string → unrecognized

        if license_value == "":
            if origin == "external":
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: external dataset declares no license "
                    f"(set an SPDX id, or a sentinel: {sorted(LICENSE_SENTINELS)})",
                    "dataset.license-missing",
                )
        elif license_value is None or not is_recognized(license_value):
            hint = suggest(license_value) if isinstance(license_value, str) else None
            suffix = f" — did you mean {hint!r}?" if hint else ""
            display = license_raw if license_value is None else license_value
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: unrecognized license {display!r}{suffix}",
                "dataset.license-unrecognized",
            )

        # --- tier / update_cadence (present-but-unrecognized only) ---
        tier_finding = _enum_finding(
            fm.get("tier"), _ALLOWED_TIERS,
            path=path, ident=ident, field="tier", rule="dataset.tier-unrecognized",
        )
        if tier_finding is not None:
            yield tier_finding

        cadence_finding = _enum_finding(
            fm.get("update_cadence"), _ALLOWED_CADENCES,
            path=path, ident=ident, field="update_cadence", rule="dataset.cadence-unrecognized",
        )
        if cadence_finding is not None:
            yield cadence_finding


@Check(section="dataset metadata", order=32)
def check_dataset_metadata(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_metadata(dataset_frontmatters(ctx))
```

- [ ] **Step 4: Register the module**

In `src/science_tool/validate/checks/__init__.py`, in the `_load_canonical_checks` tuple, add `"dataset_metadata"` immediately after `"dataset_taxonomy",`:

```python
        "dataset_taxonomy",
        "dataset_metadata",
        "variant_identity",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/validate/test_checks_dataset_metadata.py -v`
Expected: PASS (16 passed)

- [ ] **Step 6: Commit**

```bash
git add src/science_tool/validate/checks/dataset_metadata.py src/science_tool/validate/checks/__init__.py tests/validate/test_checks_dataset_metadata.py
git commit -m "feat(validate): add dataset license/tier/cadence checks (warn-only, schema-aligned)"
```

---

## Task 5: Materialize `sci:license` + register the predicate

**Files:**
- Modify: `src/science_tool/graph/materialize.py` (`_add_entity` dataset block, ~line 240)
- Modify: `src/science_tool/graph/store/constants.py` (`GRAPH_EXPORT_EDGE_METADATA_PREDICATES` ~line 70; `PREDICATE_REGISTRY` ~line 214)
- Test: `tests/test_license_materialize.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_license_materialize.py`:

```python
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from click.testing import CliRunner
from rdflib import URIRef
from rdflib.namespace import RDF

from science_tool.cli import main
from science_tool.graph.materialize import _build_dataset_from_sources
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS
from science_tool.graph.store.constants import (
    GRAPH_EXPORT_EDGE_METADATA_PREDICATES,
)

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)

_DATAPACKAGE = (
    "profiles: [science-pkg-entity-1.0]\n"
    "id: dataset:x\ntype: dataset\ntitle: X\nstatus: active\n"
    "origin: external\ntier: use-now\nlicense: CC-BY-4.0\n"
    # AccessBlock requires both `level` and `verified` (neither has a default).
    "access:\n  level: public\n  availability: available\n  verified: false\n"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def _project(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(_DATAPACKAGE, encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)


def _license_objects(ds) -> set[str]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {str(o) for _, _, o in knowledge.triples((None, SCI_NS.license, None))}


def test_datapackage_license_is_materialized(tmp_path: Path) -> None:
    # Guards BOTH the _ENTITY_FIELDS extraction change and the materialization.
    _project(tmp_path)
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        sources = load_project_sources(tmp_path, include_commons=False)
        ds = _build_dataset_from_sources(sources)
    finally:
        os.chdir(prev)
    assert "CC-BY-4.0" in _license_objects(ds)


def test_license_is_classified_as_edge_metadata() -> None:
    # So graph export treats it as a literal property, not a graph edge.
    assert SCI_NS.license in GRAPH_EXPORT_EDGE_METADATA_PREDICATES


def test_license_predicate_visible_in_graph_predicates() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "predicates", "--format", "json"])
    assert result.exit_code == 0, result.output
    import json

    predicates = {row["predicate"] for row in json.loads(result.output)["rows"]}
    assert "sci:license" in predicates
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --frozen pytest tests/test_license_materialize.py -v`
Expected: FAIL — `test_datapackage_license_is_materialized` (empty set), `test_license_is_classified_as_edge_metadata` (not in set), `test_license_predicate_visible_in_graph_predicates` (not in predicates)

- [ ] **Step 3: Emit `sci:license` in materialization**

In `src/science_tool/graph/materialize.py`, in `_add_entity`, find the dataset block (~line 240):

```python
    if entity.kind == "dataset" and entity.source_class:
        knowledge.add((uri, SCI_NS.sourceClass, Literal(entity.source_class)))
```

Add a `license` emission directly after it:

```python
    if entity.kind == "dataset" and entity.source_class:
        knowledge.add((uri, SCI_NS.sourceClass, Literal(entity.source_class)))
    if entity.kind == "dataset" and entity.license:
        knowledge.add((uri, SCI_NS.license, Literal(entity.license)))
```

- [ ] **Step 4: Register the predicate as edge-metadata**

In `src/science_tool/graph/store/constants.py`, in the `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` frozenset, add `SCI_NS.license` directly after `SCI_NS.sourceClass,` (~line 70):

```python
        SCI_NS.sourceClass,
        SCI_NS.license,
        SCI_NS.usageRole,
```

- [ ] **Step 5: Add the predicate registry entry**

In the same file, in `PREDICATE_REGISTRY`, add an entry directly after the `sci:sourceClass` entry (~line 218, after its closing `},`):

```python
    {
        "predicate": "sci:sourceClass",
        "description": "Dataset epistemic source class (observational | derived | reference)",
        "layer": "graph/knowledge",
    },
    {
        "predicate": "sci:license",
        "description": "Dataset license (SPDX id or sentinel: unknown | proprietary | custom)",
        "layer": "graph/knowledge",
    },
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run --frozen pytest tests/test_license_materialize.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add src/science_tool/graph/materialize.py src/science_tool/graph/store/constants.py tests/test_license_materialize.py
git commit -m "feat(graph): materialize sci:license + register the query predicate"
```

---

## Task 6: Schema + template synchronization

**Files:**
- Modify: `model/src/science_model/schemas/mixin-dataset-1.0.json`
- Modify: `model/src/science_model/templates/dataset.md`
- Modify: `templates/dataset.md` (workspace root, `~/d/science/templates/dataset.md` — same git repo, committed alongside)
- Test: `model/tests/test_mixin_dataset_schema_license.py`

- [ ] **Step 1: Write the failing test**

Create `model/tests/test_mixin_dataset_schema_license.py` (`parents[2]` resolves to the `science/` repo dir from `model/tests/`):

```python
from __future__ import annotations

import json
from pathlib import Path

_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "model/src/science_model/schemas/mixin-dataset-1.0.json"
)


def test_mixin_dataset_schema_declares_license() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert "license" in schema["properties"]
    assert schema["properties"]["license"] == {"type": "string"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --frozen pytest model/tests/test_mixin_dataset_schema_license.py -v`
Expected: FAIL — `KeyError: 'license'` / assertion error

- [ ] **Step 3: Add `license` to the mixin schema**

In `model/src/science_model/schemas/mixin-dataset-1.0.json`, in `properties`, add a `license` line after the `update_cadence` property:

```json
    "update_cadence": {"type": "string"},
    "license": {"type": "string"},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --frozen pytest model/tests/test_mixin_dataset_schema_license.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Update both template comments**

First confirm no generator produces one template from the other:

Run: `grep -rn "model/src/science_model/templates" ~/d/science/science --include='*.py' | grep -iv test`
Expected: no generator/copy step (manual maintenance confirmed). If a generator IS found, regenerate instead of hand-editing and skip the manual edit to the generated copy.

In **both** `model/src/science_model/templates/dataset.md` and `~/d/science/templates/dataset.md`, change line 9 from:

```
license: ""                       # SPDX identifier or "unknown"
```

to:

```
license: ""                       # SPDX id (e.g. CC-BY-4.0) or sentinel: unknown | proprietary | custom
```

- [ ] **Step 6: Verify the two templates remain identical**

Run: `diff ~/d/science/science/model/src/science_model/templates/dataset.md ~/d/science/templates/dataset.md`
Expected: no output (identical)

- [ ] **Step 7: Commit**

```bash
git add model/src/science_model/schemas/mixin-dataset-1.0.json model/src/science_model/templates/dataset.md model/tests/test_mixin_dataset_schema_license.py
git add ../templates/dataset.md
git commit -m "feat(model): declare license in mixin-dataset schema + document sentinels in template"
```

> **Single repo:** `~/d/science` and `~/d/science/science` share one git top-level
> (`git rev-parse --show-toplevel` returns the same path for both), and
> `templates/dataset.md` is tracked in it. So `../templates/dataset.md` is staged
> into the *same* commit on the `feat/dataset-license-metadata-validation` branch —
> no separate repo, no separate commit.

---

## Task 7: Full-suite verification + spec status

**Files:**
- Modify: `docs/plans/2026-05-30-dataset-license-and-metadata-validation.md` (status line)

- [ ] **Step 1: Run the full model + validate + graph test suites**

Run:
```bash
uv run --frozen pytest model/tests/test_licenses.py model/tests/test_frontmatter_license.py model/tests/test_mixin_dataset_schema_license.py tests/validate/test_checks_dataset_metadata.py tests/test_license_materialize.py tests/test_datasets.py tests/test_graph_cli.py -v
```
Expected: all PASS, no regressions.

- [ ] **Step 2: Run the broader suite to catch unexpected regressions**

Run: `uv run --frozen pytest -q`
Expected: green (or only pre-existing unrelated failures — investigate any new failure before proceeding).

- [ ] **Step 3: Smoke-test the real CLI on a dataset fixture**

Create a throwaway external dataset note missing a license under a scratch project (or an existing test project) and run:
```bash
uv run --frozen science validate --verbose 2>&1 | grep -i "dataset.license\|dataset.tier\|dataset.cadence"
```
Expected: a `dataset.license-missing` (or appropriate) warning appears for a license-less external dataset.

- [ ] **Step 4: Mark the spec implemented**

In `docs/plans/2026-05-30-dataset-license-and-metadata-validation.md`, change the status line:

```
- **Status:** design (approved, pre-implementation)
```
to:
```
- **Status:** implemented
```

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-05-30-dataset-license-and-metadata-validation.md
git commit -m "docs(plan): mark dataset-license spec implemented"
```

---

## Self-review notes (spec coverage)

- Spec §1 (license on Entity + thread + extract) → Tasks 2, 3. §1 materialization + predicate → Task 5. §1a (mixin schema + both templates) → Task 6. §2 (vocabulary) → Task 1. §3 (checks + registration + cadence=schema) → Task 4. §4 (health surfacing) → covered by registration (Task 4) + smoke test (Task 7). §5 (all tests: vocabulary, check-core, registration, datapackage-extraction, materialization, predicate-registry, schema-sync, regression) → Tasks 1/2/4/5/6.
- Out-of-scope (`tier`/`update_cadence` materialization, `profiles`, wider field validation) → intentionally not implemented.
