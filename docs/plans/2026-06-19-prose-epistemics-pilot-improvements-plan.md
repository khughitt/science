# Prose Epistemics Pilot Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the reusable `science` seams exposed by the natural-systems prose epistemics pilot and run one real offline-agent artifact through the pipe.

**Architecture:** Keep P2/P3/P4 as the source of truth. Add a shared P2 validation/reporting module used by both pre-ingest validation and persisted-artifact checks, keep prose-source path normalization in the prose-source/decomposition boundary, add graph revision metadata excludes at graph input-manifest construction, characterize operational annotation refs before changing health behavior, and add batch promotion as a wrapper over single-unit promotion decisions.

**Tech Stack:** Python 3, Click, pytest, rdflib, existing `science_tool.annotation` and `science_tool.graph` modules, downstream `~/d/natural-systems` artifacts for the offline-agent pilot.

---

## Implementation Notes

Run execution in an isolated worktree for `~/d/science`:

```bash
cd ~/d/science
git status --short
git worktree add ../science-prose-pilot-improvements -b prose-pilot-improvements
cd ../science-prose-pilot-improvements
```

If the downstream offline-agent pilot task writes to `~/d/natural-systems`, use a separate natural-systems worktree for that task. Do not mix science framework commits and natural-systems application commits.

## File Structure

- Create: `science/src/science_tool/annotation/prose_validation.py`
  - Shared unit-level validation/reporting for P2 decomposition artifacts.
- Modify: `science/src/science_tool/annotation/cli.py`
  - Add `validate-prose-decomposition-artifact`; route `check-prose-decomposition` through the shared validator.
- Modify: `science/src/science_tool/annotation/prose_decomposition.py`
  - Parse project-relative and `~/d/<project>/...` source paths consistently.
- Modify: `science/src/science_tool/annotation/prose_source_entity.py`
  - Store project-relative `source_path` for in-project prose sources.
- Modify: `science/src/science_tool/graph/io.py`
  - Add `science.yaml`-configured revision manifest excludes.
- Modify: `science/src/science_tool/annotation/prose_promote.py`
  - Expose a reusable single-unit promotion decision for batch planning/apply.
- Create: `science/src/science_tool/annotation/prose_promotion_batch.py`
  - Identity-only batch promotion plan parser/writer/apply functions.
- Test: `science/tests/test_annotate_prose_decomposition_cli.py`
  - Pre-ingest validation CLI and check/validate parity.
- Test: `science/tests/test_prose_source_entity.py`
  - Project-relative source-path storage.
- Create: `science/tests/test_graph_io_revision_manifest.py`
  - Revision manifest exclude behavior.
- Test: `science/tests/test_graph_migrate_identity_audit.py`
  - Operational annotation-ref characterization.
- Create: `science/tests/test_prose_promotion_batch.py`
  - Batch promotion planning/apply behavior.
- Create downstream in `~/d/natural-systems`: `doc/reports/prose-epistemics-agent-artifact-pilot.md`
  - Pilot review report for one real offline-agent artifact.

---

### Task 1: Shared P2 Validation And Pre-Ingest CLI

**Files:**
- Create: `science/src/science_tool/annotation/prose_validation.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Test: `science/tests/test_annotate_prose_decomposition_cli.py`

- [ ] **Step 1: Add failing tests for raw-artifact validation**

Append these tests to `science/tests/test_annotate_prose_decomposition_cli.py`:

```python
def test_validate_prose_decomposition_artifact_reports_units_before_ingest(tmp_path):
    artifact_path = _artifact_file(tmp_path)

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["source_ref"] == "prose-source:example"
    assert payload["artifact_id"] == "decomp-1"
    assert payload["summary"] == {
        "units": 1,
        "resolved": 1,
        "unresolved": 0,
        "ambiguous": 0,
        "stale": 0,
        "hard_failures": 0,
    }
    assert payload["units"][0]["unit_id"] == "u001"
    assert payload["units"][0]["locator_status"] == "resolved"
    assert payload["units"][0]["promoted_to"] is None
    assert payload["units"][0]["stale"] is False
    assert not (tmp_path / "data" / "prose-decompositions" / "example" / "index.json").exists()


def test_validate_prose_decomposition_artifact_hash_mismatch_fails(tmp_path):
    artifact_path = _artifact_file(tmp_path, content_hash="sha256:" + "0" * 64)

    result = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )

    assert result.exit_code != 0
    assert "content hash mismatch" in result.output
    assert not (tmp_path / "entities" / "prose-sources" / "example.md").exists()


def test_validate_and_check_share_per_unit_findings_after_ingest(tmp_path):
    artifact_path = _artifact_file(tmp_path)
    validate = CliRunner().invoke(
        annotate_group,
        [
            "validate-prose-decomposition-artifact",
            str(artifact_path),
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert validate.exit_code == 0, validate.output

    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(artifact_path), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output

    check = CliRunner().invoke(
        annotate_group,
        [
            "check-prose-decomposition",
            "--source",
            "prose-source:example",
            "--root",
            str(tmp_path),
            "--format",
            "json",
        ],
    )
    assert check.exit_code == 0, check.output

    validate_payload = json.loads(validate.output)
    check_payload = json.loads(check.output)
    # Fresh ingest has no stale/promoted state, so raw-artifact validation and
    # latest-artifact check should produce identical per-unit findings.
    assert validate_payload["units"] == check_payload["units"]
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_annotate_prose_decomposition_cli.py::test_validate_prose_decomposition_artifact_reports_units_before_ingest science/tests/test_annotate_prose_decomposition_cli.py::test_validate_prose_decomposition_artifact_hash_mismatch_fails science/tests/test_annotate_prose_decomposition_cli.py::test_validate_and_check_share_per_unit_findings_after_ingest -q
```

Expected: FAIL because `validate-prose-decomposition-artifact` does not exist.

- [ ] **Step 3: Create the shared validation module**

Create `science/src/science_tool/annotation/prose_validation.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.annotation.internal_prose_adapter import InternalProseAdapter
from science_tool.annotation.prose_decomposition import (
    DecompositionArtifact,
    DecompositionError,
    DecompositionUnit,
    ProseDecompositionStore,
    Quote,
    compute_source_hash,
    parse_submitted_decomposition,
)


@dataclass(frozen=True)
class ProseValidationReport:
    source_ref: str
    artifact_id: str
    rows: list[dict[str, object]]

    def to_json(self) -> dict[str, object]:
        counts = {"resolved": 0, "unresolved": 0, "ambiguous": 0, "stale": 0}
        hard_failures = 0
        for row in self.rows:
            status = row.get("locator_status")
            if status in counts:
                counts[status] += 1
            else:
                hard_failures += 1
        return {
            "source_ref": self.source_ref,
            "artifact_id": self.artifact_id,
            "summary": {
                "units": len(self.rows),
                "resolved": counts["resolved"],
                "unresolved": counts["unresolved"],
                "ambiguous": counts["ambiguous"],
                "stale": counts["stale"],
                "hard_failures": hard_failures,
            },
            "units": self.rows,
        }


def validate_submitted_decomposition_artifact(
    artifact_path: Path,
    *,
    project_root: Path,
    allow_changed: bool = False,
) -> tuple[DecompositionArtifact, ProseValidationReport]:
    artifact = parse_submitted_decomposition(artifact_path.read_text(encoding="utf-8"), project_root=project_root)
    current_hash = compute_source_hash(artifact.source.path)
    if current_hash != artifact.source.content_hash and not allow_changed:
        raise DecompositionError(
            "content hash mismatch: "
            f"artifact has {artifact.source.content_hash}; current source is {current_hash}"
        )
    rows = validate_decomposition_units(artifact=artifact, index=None)
    return artifact, ProseValidationReport(
        source_ref=artifact.source_ref,
        artifact_id=artifact.artifact.artifact_id,
        rows=rows,
    )


def validate_latest_decomposition(project_root: Path, source_slug: str) -> tuple[DecompositionArtifact, ProseValidationReport]:
    store = ProseDecompositionStore(project_root)
    index = store.load_index(source_slug)
    artifact = store.load_latest(source_slug)
    rows = validate_decomposition_units(artifact=artifact, index=index)
    return artifact, ProseValidationReport(
        source_ref=artifact.source_ref,
        artifact_id=artifact.artifact.artifact_id,
        rows=rows,
    )


def validate_decomposition_units(
    *,
    artifact: DecompositionArtifact,
    index: dict[str, object] | None,
) -> list[dict[str, object]]:
    adapter = InternalProseAdapter()
    rows: list[dict[str, object]] = []
    units_index = _units_index(index)
    current_fingerprints = {unit.fingerprint for unit in artifact.units}
    for unit in artifact.units:
        index_row = _index_row(units_index, unit.fingerprint)
        quote = quote_for_decomposition_unit(unit)
        resolution = adapter.resolve_unit(artifact.source.path, unit.locator, quote)
        stale = _index_bool(index_row, "stale", default=False, fingerprint=unit.fingerprint)
        rows.append(
            {
                "unit_id": unit.unit_id,
                "disposition": unit.disposition,
                "status": "stale" if stale else unit.disposition,
                "fingerprint": unit.fingerprint,
                "locator_status": resolution.status.value,
                "message": resolution.message,
                "promoted_to": index_row.get("promoted_to"),
                "stale": stale,
            }
        )
    for fingerprint, index_row in units_index.items():
        if fingerprint in current_fingerprints:
            continue
        if not isinstance(index_row, dict):
            raise DecompositionError(f"prose decomposition index row must be an object: {fingerprint}")
        if index_row.get("stale") is True:
            rows.append(_stale_row(fingerprint, index_row))
    return rows


def quote_for_decomposition_unit(unit: DecompositionUnit) -> Quote:
    if unit.disposition == "candidate":
        if unit.candidate is None:
            raise DecompositionError(f"candidate unit {unit.unit_id} is missing candidate payload")
        return Quote(unit.candidate.exact, unit.candidate.prefix, unit.candidate.suffix)
    if unit.disposition == "skip":
        if unit.locator.quote is None:
            raise DecompositionError(f"skip unit {unit.unit_id} is missing locator quote")
        return unit.locator.quote
    raise DecompositionError(f"unknown unit disposition: {unit.disposition}")


def _units_index(index: dict[str, object] | None) -> dict[str, Any]:
    if index is None:
        return {}
    units = index.get("units")
    if not isinstance(units, dict):
        raise DecompositionError("prose decomposition index units must be an object")
    return units


def _index_row(units_index: dict[str, Any], fingerprint: str) -> dict[str, object]:
    if not units_index:
        return {"stale": False, "promoted_to": None}
    row = units_index.get(fingerprint)
    if not isinstance(row, dict):
        raise DecompositionError(f"prose decomposition index row must be an object: {fingerprint}")
    return row


def _index_bool(row: dict[str, object], key: str, *, default: bool, fingerprint: str) -> bool:
    value = row.get(key, default)
    if not isinstance(value, bool):
        raise DecompositionError(f"prose decomposition index {key} must be a bool: {fingerprint}")
    return value


def _stale_row(fingerprint: str, index_row: dict[str, object]) -> dict[str, object]:
    return {
        "unit_id": index_row.get("latest_unit_id", ""),
        "disposition": index_row.get("latest_disposition", ""),
        "status": "stale",
        "fingerprint": fingerprint,
        "locator_status": "stale",
        "message": "unit is stale in latest decomposition",
        "promoted_to": index_row.get("promoted_to"),
        "stale": True,
    }
```

- [ ] **Step 4: Update the CLI to use the shared module**

Modify imports in `science/src/science_tool/annotation/cli.py`:

```python
from science_tool.annotation.prose_validation import (
    validate_latest_decomposition,
    validate_submitted_decomposition_artifact,
)
```

Remove these imports from `science_tool.annotation.prose_decomposition` in `cli.py` because the helper now owns them:

```python
DecompositionArtifact,
DecompositionUnit,
Quote,
```

Replace `check_prose_decomposition_cmd`'s body after `project_root = ...` with:

```python
    try:
        artifact, report = validate_latest_decomposition(project_root, slug)
        rows = report.rows
    except DecompositionError as exc:
        raise click.ClickException(str(exc)) from exc
```

Add the new command above `check-prose-decomposition`:

```python
@annotate_group.command("validate-prose-decomposition-artifact")
@click.argument("artifact_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--allow-changed", is_flag=True, default=False)
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def validate_prose_decomposition_artifact_cmd(
    artifact_path: Path,
    root: Path | None,
    allow_changed: bool,
    fmt: str,
) -> None:
    """Validate an offline internal-prose decomposition artifact before ingest."""
    project_root = (root or Path.cwd()).resolve()
    try:
        artifact, report = validate_submitted_decomposition_artifact(
            artifact_path,
            project_root=project_root,
            allow_changed=allow_changed,
        )
    except DecompositionError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = report.to_json()
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2))
        return

    summary = payload["summary"]
    if not isinstance(summary, dict):
        raise click.ClickException("prose validation summary must be an object")
    click.echo(
        f"validated prose decomposition {artifact.artifact.artifact_id} for {artifact.source_ref}: "
        f"resolved={summary['resolved']} unresolved={summary['unresolved']} "
        f"ambiguous={summary['ambiguous']} hard_failures={summary['hard_failures']}"
    )
    for row in report.rows:
        message = f" - {row['message']}" if row["message"] else ""
        click.echo(
            f"  {row['unit_id']}: {row['status']} "
            f"({row['locator_status']}; {row['fingerprint']}){message}"
        )
```

Delete `_check_prose_decomposition_units`, `_stale_prose_decomposition_check_row`, and `_quote_for_decomposition_unit` from `cli.py`.

- [ ] **Step 5: Run the focused tests**

Run:

```bash
uv run --frozen pytest science/tests/test_annotate_prose_decomposition_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/prose_validation.py science/src/science_tool/annotation/cli.py science/tests/test_annotate_prose_decomposition_cli.py
git commit -m "feat(prose): validate decomposition artifacts before ingest"
```

---

### Task 2: Offline-Agent Artifact Pilot Handoff

**Files:**
- Downstream create: `~/d/natural-systems/data/prose-decomposition-inputs/agent/universality-classes-two-faces.json`
- Downstream create: `~/d/natural-systems/doc/reports/prose-epistemics-agent-artifact-pilot.md`

This task validates the prompt/artifact contract. It does not add live model execution to `science`.

- [ ] **Step 1: Create a downstream worktree**

Run:

```bash
cd ~/d/natural-systems
git status --short
git worktree add ../natural-systems-prose-agent-pilot -b prose-agent-artifact-pilot
cd ../natural-systems-prose-agent-pilot
```

Expected: a clean natural-systems worktree on branch `prose-agent-artifact-pilot`.

- [ ] **Step 2: Produce one offline-agent artifact**

Use the current P2 schema and target source `prose-source:universality-classes-two-faces`.
Write the agent output to:

```text
data/prose-decomposition-inputs/agent/universality-classes-two-faces.json
```

The artifact must use this shape:

```json
{
  "schema_version": 1,
  "source": {
    "kind": "prose-source",
    "slug": "universality-classes-two-faces",
    "path": "entities/discussions/0075-representing-universality-classes-two-faces.md",
    "title": "Representing Universality Classes: Two Faces",
    "content_hash": "sha256:<computed-by-agent-or-operator>"
  },
  "artifact": {
    "id": "agent-universality-classes-two-faces-1",
    "generated_at": "2026-06-19T00:00:00Z",
    "producer": "offline-agent"
  },
  "units": []
}
```

Each candidate unit must use:

```json
{
  "unit_id": "u001",
  "disposition": "candidate",
  "locator": {
    "regime": "markdown-heading-path",
    "value": ["Heading", "Subheading"]
  },
  "payload": {
    "type": "proposition",
    "exact": "Exact source quote.",
    "prefix": "",
    "suffix": "",
    "stance": "asserted"
  }
}
```

Each skip unit must use one of the six canonical skip codes:

```json
{
  "unit_id": "s001",
  "disposition": "skip",
  "reason": {
    "code": "meta_commentary",
    "detail": "Project framing rather than a domain claim."
  },
  "locator": {
    "regime": "markdown-heading-path-with-quote",
    "value": ["Heading"],
    "quote": {
      "exact": "Exact skipped source text.",
      "prefix": "",
      "suffix": ""
    }
  }
}
```

- [ ] **Step 3: Validate the raw agent artifact with the new science CLI**

Run from the natural-systems pilot worktree:

```bash
uv run --frozen science annotate validate-prose-decomposition-artifact data/prose-decomposition-inputs/agent/universality-classes-two-faces.json --root . --format json
```

Expected: PASS with `summary.hard_failures == 0`. If units are `unresolved` or `ambiguous`, edit only the artifact's heading path or quote context and rerun this exact command.

- [ ] **Step 4: Ingest, check, promote a reviewed subset, and rebuild health**

Run:

```bash
uv run --frozen science annotate ingest-prose-decomposition data/prose-decomposition-inputs/agent/universality-classes-two-faces.json --root .
uv run --frozen science annotate check-prose-decomposition --source prose-source:universality-classes-two-faces --root . --format json
npm run kg:build
uv run --frozen science annotate ground-prose-decomposition --source prose-source:universality-classes-two-faces --root . --graph knowledge/graph.trig --floor supported --write
uv run --frozen science annotate build-prose-health --root . --write
npm run health
```

Expected: each command exits 0. It is acceptable for P4 rows to be `unpromoted` or `unbacked`; this pilot tests artifact quality and pipeline compatibility.

- [ ] **Step 5: Write the review report**

Create `doc/reports/prose-epistemics-agent-artifact-pilot.md` with this structure:

```markdown
# Prose Epistemics Agent Artifact Pilot

## Scope

- Source: `prose-source:universality-classes-two-faces`
- Input artifact: `data/prose-decomposition-inputs/agent/universality-classes-two-faces.json`
- Validation command: `science annotate validate-prose-decomposition-artifact ...`

## Counts

| Measure | Count |
|---|---:|
| Candidate units | 0 |
| Skip units | 0 |
| `meta_commentary` skips | 0 |
| `not_a_claim` skips | 0 |
| `duplicate_or_restatement` skips | 0 |
| `citation_or_reference_only` skips | 0 |
| `out_of_scope` skips | 0 |
| `unresolved_or_malformed` skips | 0 |
| Unresolved locators | 0 |
| Ambiguous locators | 0 |
| False-positive candidates | 0 |
| Missed domain claims | 0 |
| Promoted units | 0 |
| Unbacked promoted units | 0 |

## Review Notes

Record concrete unit ids for false-positive candidates, missed domain claims, and wrong skip reasons.

## Outcome

State whether the offline artifact contract is ready for a larger campaign, or which prompt changes are needed before expanding.
```

Replace the zero counts with the actual reviewed counts.

- [ ] **Step 6: Commit the downstream pilot**

Run in the natural-systems pilot worktree:

```bash
git add data/prose-decomposition-inputs/agent/universality-classes-two-faces.json doc/reports/prose-epistemics-agent-artifact-pilot.md data/prose-decompositions data/prose-grounding data/prose-health entities/prose-sources entities/propositions knowledge/graph.trig
git commit -m "test: run prose epistemics agent artifact pilot"
```

Expected: one natural-systems commit. Do not include this commit in the science branch.

---

### Task 3: Project-Relative Prose Source Paths

**Files:**
- Modify: `science/src/science_tool/annotation/prose_decomposition.py`
- Modify: `science/src/science_tool/annotation/prose_source_entity.py`
- Test: `science/tests/test_prose_source_entity.py`
- Test: `science/tests/test_prose_decomposition.py`

- [ ] **Step 1: Update tests for project-relative path storage and parsing**

In `science/tests/test_prose_source_entity.py`, change the expected `source_path` values from `~/d/science/docs/example.md` and `~/d/science/docs/missing.md` to `docs/example.md` and `docs/missing.md`.

Append this test:

```python
def test_resolver_uses_project_relative_path_for_non_science_project_root(tmp_path):
    project_root = tmp_path / "natural-systems"
    source = project_root / "entities" / "discussions" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Example\n", encoding="utf-8")

    resolve_or_create_prose_source(
        project_root=project_root,
        slug="example",
        title="Example",
        source_path=source,
        content_hash="sha256:" + "5" * 64,
        artifact_id="decomp-5",
        today=date(2026, 6, 19),
    )

    entity = project_root / "entities" / "prose-sources" / "example.md"
    frontmatter = yaml.safe_load(entity.read_text(encoding="utf-8").split("---", 2)[1])
    assert frontmatter["source_path"] == "entities/discussions/example.md"
```

In `science/tests/test_prose_decomposition.py`, add:

```python
def test_parse_submitted_decomposition_resolves_project_relative_source_path(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    payload = _artifact(tmp_path)
    payload["source"]["path"] = "docs/example.md"
    payload["source"]["content_hash"] = compute_source_hash(source)

    artifact = parse_submitted_decomposition(json.dumps(payload), project_root=tmp_path)

    assert artifact.source.path == source


def test_parse_submitted_decomposition_resolves_tilde_d_project_alias(tmp_path: Path) -> None:
    project_root = tmp_path / "natural-systems"
    source = project_root / "docs" / "example.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Section\n\nBasalt flows record the cooling history.\n", encoding="utf-8")
    payload = _artifact(project_root)
    payload["source"]["path"] = "~/d/natural-systems/docs/example.md"
    payload["source"]["content_hash"] = compute_source_hash(source)

    artifact = parse_submitted_decomposition(json.dumps(payload), project_root=project_root)

    assert artifact.source.path == source
```

Also add `compute_source_hash` to the import list from `science_tool.annotation.prose_decomposition` at the top of `science/tests/test_prose_decomposition.py`.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_prose_source_entity.py science/tests/test_prose_decomposition.py -q
```

Expected: FAIL because stored paths still use `~/d/science/...`, project-relative parse is not guaranteed, or the `~/d/<project>` alias still only recognizes `~/d/science`.

- [ ] **Step 3: Update source path parsing**

Replace `_resolve_source_path` in `science/src/science_tool/annotation/prose_decomposition.py` with:

```python
def _resolve_source_path(value: str, *, project_root: Path) -> Path:
    root = project_root.resolve(strict=False)
    if value.startswith("~/d/"):
        alias_body = value.removeprefix("~/d/").strip("/")
        parts = Path(alias_body).parts
        if parts and parts[0] == root.name:
            return root.joinpath(*parts[1:])
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate
    return root / candidate
```

- [ ] **Step 4: Update prose-source display path storage**

Replace `_display_path` in `science/src/science_tool/annotation/prose_source_entity.py` with:

```python
def _display_path(project_root: Path, source_path: Path) -> str:
    root = project_root.resolve(strict=False)
    candidate = source_path if source_path.is_absolute() else root / source_path
    resolved = candidate.resolve(strict=False)
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return str(source_path)
```

- [ ] **Step 5: Run the focused tests**

Run:

```bash
uv run --frozen pytest science/tests/test_prose_source_entity.py science/tests/test_prose_decomposition.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/annotation/prose_decomposition.py science/src/science_tool/annotation/prose_source_entity.py science/tests/test_prose_source_entity.py science/tests/test_prose_decomposition.py
git commit -m "fix(prose): store project-relative prose source paths"
```

---

### Task 4: Graph Revision Manifest Excludes

**Files:**
- Modify: `science/src/science_tool/graph/io.py`
- Create: `science/tests/test_graph_io_revision_manifest.py`

- [ ] **Step 1: Write failing tests for configured revision excludes**

Create `science/tests/test_graph_io_revision_manifest.py`:

```python
from pathlib import Path

import pytest

from science_tool.graph.io import build_input_manifest


def _seed_project(root: Path, science_yaml: str) -> None:
    (root / "science.yaml").write_text(science_yaml, encoding="utf-8")
    (root / "doc" / "reports").mkdir(parents=True)
    (root / "doc" / "reports" / "health-report.json").write_text('{"generated": true}\n', encoding="utf-8")
    (root / "doc" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    (root / "knowledge").mkdir()


def test_build_input_manifest_excludes_configured_generated_report(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - doc/reports/health-report.json\n",
    )

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "doc/notes.md" in manifest
    assert "doc/reports/health-report.json" not in manifest


def test_build_input_manifest_keeps_report_without_configured_exclude(tmp_path: Path) -> None:
    _seed_project(tmp_path, "name: fixture\nprofile: research\n")

    manifest = build_input_manifest(tmp_path / "knowledge" / "graph.trig")

    assert "doc/reports/health-report.json" in manifest


def test_build_input_manifest_rejects_absolute_exclude_pattern(tmp_path: Path) -> None:
    _seed_project(
        tmp_path,
        "name: fixture\n"
        "profile: research\n"
        "graph:\n"
        "  revision_manifest_excludes:\n"
        "    - /tmp/outside.json\n",
    )

    with pytest.raises(ValueError, match="revision_manifest_excludes"):
        build_input_manifest(tmp_path / "knowledge" / "graph.trig")
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_graph_io_revision_manifest.py -q
```

Expected: FAIL because `build_input_manifest` does not read `graph.revision_manifest_excludes`.

- [ ] **Step 3: Add YAML and fnmatch imports**

Modify the imports in `science/src/science_tool/graph/io.py`:

```python
import fnmatch
import hashlib
import json
import re
```

Add:

```python
import yaml
```

- [ ] **Step 4: Apply configured excludes inside `build_input_manifest`**

In `build_input_manifest`, after building `files` and before constructing `manifest`, add:

```python
    exclude_patterns = _revision_manifest_excludes(project_root)
```

Then replace:

```python
        rel_path = file_path.relative_to(project_root).as_posix()
        stat = file_path.stat()
        manifest[rel_path] = {
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": _sha256_file(file_path),
        }
```

with:

```python
        rel_path = file_path.relative_to(project_root).as_posix()
        if _matches_revision_manifest_exclude(rel_path, exclude_patterns):
            continue
        stat = file_path.stat()
        manifest[rel_path] = {
            "mtime_ns": int(stat.st_mtime_ns),
            "sha256": _sha256_file(file_path),
        }
```

Add these helpers below `build_input_manifest`:

```python
def _revision_manifest_excludes(project_root: Path) -> tuple[str, ...]:
    config_path = project_root / "science.yaml"
    if not config_path.is_file():
        return ()
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        return ()
    graph = loaded.get("graph") or {}
    if not isinstance(graph, dict):
        return ()
    raw = graph.get("revision_manifest_excludes") or []
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError("science.yaml graph.revision_manifest_excludes must be a list of strings")
    patterns: list[str] = []
    for item in raw:
        pattern = item.strip()
        if not pattern:
            raise ValueError("science.yaml graph.revision_manifest_excludes entries must be non-empty")
        path = Path(pattern)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(
                "science.yaml graph.revision_manifest_excludes entries must be relative project paths"
            )
        patterns.append(path.as_posix())
    return tuple(patterns)


def _matches_revision_manifest_exclude(rel_path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(rel_path, pattern) for pattern in patterns)
```

- [ ] **Step 5: Run the focused tests**

Run:

```bash
uv run --frozen pytest science/tests/test_graph_io_revision_manifest.py -q
```

Expected: PASS.

- [ ] **Step 6: Run graph composite regression**

Run:

```bash
uv run --frozen pytest science/tests/test_graph_composite.py::test_composite_revision_manifest_uses_project_root -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/io.py science/tests/test_graph_io_revision_manifest.py
git commit -m "feat(graph): exclude configured generated files from revision manifest"
```

---

### Task 5: Operational Annotation-Ref Characterization

**Files:**
- Modify: `science/tests/test_graph_migrate_identity_audit.py`

This task is deliberately a characterization gate. It does not broaden annotation-ref exemptions unless a concrete failing warning is pinned during execution.

- [ ] **Step 1: Add characterization tests**

Append to `science/tests/test_graph_migrate_identity_audit.py`:

```python
def test_audit_reference_ignores_annotation_source_refs() -> None:
    referer = _ref_entity("proposition:p1", "proposition", EntityType.PROPOSITION)

    rows = _audit_reference(
        referer,
        "source_refs",
        "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001",
        ReferenceResolver.from_entities([], identity_table=IdentityTable(rows=[])),
        ext_prefixes=frozenset(),
    )

    assert rows == []


def test_audit_reference_does_not_broadly_ignore_annotation_refs_in_other_fields() -> None:
    referer = _ref_entity("proposition:p1", "proposition", EntityType.PROPOSITION)

    rows = _audit_reference(
        referer,
        "evidence_refs",
        "annotation:data/prose-decompositions/example/generations/decomp-1.json#u001",
        ReferenceResolver.from_entities([], identity_table=IdentityTable(rows=[])),
        ext_prefixes=frozenset(),
    )

    assert len(rows) == 1
    assert rows[0]["check"] == "unresolved_reference"
    assert rows[0]["field"] == "evidence_refs"
```

- [ ] **Step 2: Run the characterization tests**

Run:

```bash
uv run --frozen pytest science/tests/test_graph_migrate_identity_audit.py::test_audit_reference_ignores_annotation_source_refs science/tests/test_graph_migrate_identity_audit.py::test_audit_reference_does_not_broadly_ignore_annotation_refs_in_other_fields -q
```

Expected: PASS. If the second test fails because `annotation:` refs are already exempt outside `source_refs`, stop and inspect the current code before changing behavior.

- [ ] **Step 3: Investigate the actual downstream warning**

Run in the natural-systems pilot worktree from Task 2:

```bash
npm run health
```

Expected: capture any warning that mentions `annotation:`, `evidence_refs`, `source_refs`, or unstanced evidence. If no such warning exists, record in the task notes that no health behavior change is needed.

- [ ] **Step 4: Commit the characterization tests**

```bash
git add science/tests/test_graph_migrate_identity_audit.py
git commit -m "test(graph): characterize annotation reference audit behavior"
```

Do not implement an annotation-ref health exemption in this task unless the exact warning string and emitting call site have been pinned in the task notes.

---

### Task 6: Batch Prose Promotion Plan And Apply

**Files:**
- Modify: `science/src/science_tool/annotation/prose_promote.py`
- Create: `science/src/science_tool/annotation/prose_promotion_batch.py`
- Modify: `science/src/science_tool/annotation/cli.py`
- Create: `science/tests/test_prose_promotion_batch.py`
- Test: `science/tests/test_annotate_prose_decomposition_cli.py`

- [ ] **Step 1: Write failing batch promotion tests**

Create `science/tests/test_prose_promotion_batch.py`:

```python
import json
from pathlib import Path

import pytest

from science_tool.annotation.prose_decomposition import ProseDecompositionStore
from science_tool.annotation.prose_promotion_batch import (
    ProseBatchPromotionError,
    apply_prose_promotion_plan,
    build_prose_promotion_plan,
    parse_prose_promotion_plan,
)

from .test_prose_promote import _persist_artifact


def test_build_prose_promotion_plan_is_identity_only(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]

    plan = build_prose_promotion_plan(tmp_path, "prose-source:example", unit_ids=["u001"])
    payload = plan.to_json()

    assert payload["schema_version"] == 1
    assert payload["source_ref"] == "prose-source:example"
    assert payload["decomposition_artifact_id"] == artifact.artifact.artifact_id
    assert payload["units"] == [
        {
            "unit_id": "u001",
            "fingerprint": unit.fingerprint,
            "decision": "mint",
            "target_ref": None,
        }
    ]
    assert "claim" not in payload["units"][0]
    assert "candidate_type" not in payload["units"][0]


def test_apply_prose_promotion_plan_matches_single_unit_apply(tmp_path: Path) -> None:
    artifact = _persist_artifact(tmp_path)
    unit = artifact.units[0]
    plan = build_prose_promotion_plan(tmp_path, "prose-source:example", unit_ids=["u001"])

    report = apply_prose_promotion_plan(tmp_path, plan)

    assert report.minted == 1
    dest = tmp_path / "entities" / "propositions" / "basalt-flows-record-the-cooling-history.md"
    assert dest.exists()
    text = dest.read_text(encoding="utf-8")
    assert "prose-source:example" in text
    assert f"annotation:data/prose-decompositions/example/generations/{artifact.artifact.artifact_id}.json#{unit.unit_id}" in text
    index = ProseDecompositionStore(tmp_path).load_index("example")
    assert index["units"][unit.fingerprint]["promoted_to"] == "proposition:basalt-flows-record-the-cooling-history"


def test_apply_prose_promotion_plan_rejects_stale_artifact_id(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    plan = build_prose_promotion_plan(tmp_path, "prose-source:example", unit_ids=["u001"])
    source = tmp_path / "docs" / "example.md"
    source.write_text(
        "# Section\n\nBasalt flows record the cooling history.\n\nAsh layers date the eruption sequence.\n",
        encoding="utf-8",
    )
    _persist_artifact(
        tmp_path,
        artifact_id="decomp-2",
        unit_id="u002",
        exact="Ash layers date the eruption sequence.",
    )

    with pytest.raises(ProseBatchPromotionError, match="latest decomposition artifact changed"):
        apply_prose_promotion_plan(tmp_path, plan)


def test_apply_prose_promotion_plan_rejects_fingerprint_mismatch(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    plan = build_prose_promotion_plan(tmp_path, "prose-source:example", unit_ids=["u001"])
    payload = plan.to_json()
    payload["units"][0]["fingerprint"] = "sha256:not-the-real-fingerprint"

    with pytest.raises(ProseBatchPromotionError, match="fingerprint mismatch"):
        apply_prose_promotion_plan(tmp_path, parse_prose_promotion_plan(json.dumps(payload)))


def test_apply_prose_promotion_plan_rejects_decision_drift(tmp_path: Path) -> None:
    _persist_artifact(tmp_path)
    plan = build_prose_promotion_plan(tmp_path, "prose-source:example", unit_ids=["u001"])
    dest = tmp_path / "entities" / "propositions" / "existing.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "---\n"
        "id: proposition:existing\n"
        "type: proposition\n"
        "title: Basalt flows record the cooling history.\n"
        "status: active\n"
        "source_refs: []\n"
        "---\n"
        "\n"
        "Existing body.\n",
        encoding="utf-8",
    )

    with pytest.raises(ProseBatchPromotionError, match="promotion decision drift"):
        apply_prose_promotion_plan(tmp_path, plan)


def test_build_prose_promotion_plan_rejects_skip_unit(tmp_path: Path) -> None:
    _persist_artifact(tmp_path, disposition="skip")

    with pytest.raises(ProseBatchPromotionError, match="non-candidate"):
        build_prose_promotion_plan(tmp_path, "prose-source:example", unit_ids=["u001"])
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_prose_promotion_batch.py -q
```

Expected: FAIL because `science_tool.annotation.prose_promotion_batch` does not exist.

- [ ] **Step 3: Expose a single-unit planning function**

In `science/src/science_tool/annotation/prose_promote.py`, add:

```python
from dataclasses import dataclass
```

below existing imports if it is not already imported.

Add below `ProsePromotionError`:

```python
@dataclass(frozen=True)
class ProseUnitPromotionDecision:
    source_ref: str
    source_slug: str
    artifact_id: str
    unit_id: str
    fingerprint: str
    decision: str
    target_ref: str | None
```

Add this function above `promote_prose_unit`:

```python
def plan_prose_unit_promotion(project_root: Path, source_ref: str, unit_id: str) -> ProseUnitPromotionDecision:
    project_root = project_root.resolve()
    source_slug = _source_slug(source_ref)
    store = ProseDecompositionStore(project_root)
    try:
        artifact = store.load_latest(source_slug)
        index = store.load_index(source_slug)
    except DecompositionError as exc:
        raise ProsePromotionError(str(exc)) from exc
    if artifact.source_ref != source_ref:
        raise ProsePromotionError(
            f"latest artifact source_ref {artifact.source_ref!r} does not match requested {source_ref!r}"
        )
    unit = next((candidate_unit for candidate_unit in artifact.units if candidate_unit.unit_id == unit_id), None)
    if unit is None:
        raise ProsePromotionError(f"unit {unit_id!r} is not in latest artifact for {source_ref}; stale or missing")
    if unit.disposition != "candidate":
        raise ProsePromotionError(f"unit {unit_id!r} is non-candidate: {unit.disposition}")
    if unit.candidate is None:
        raise ProsePromotionError(f"candidate unit {unit_id!r} is missing candidate payload")
    ref = artifact_unit_ref(artifact, unit)
    row = _index_row(index, unit.fingerprint)
    if row.get("stale") is True:
        raise ProsePromotionError(f"unit {unit_id!r} is stale in the decomposition index")
    promoted_to = row.get("promoted_to")
    if promoted_to:
        raise ProsePromotionError(f"unit {unit_id!r} is already promoted to {promoted_to}")
    corpora, derived_refs = load_corpora(project_root)

    # Match promote_prose_unit's recovery ordering: if a prior apply already wrote the
    # artifact ref but failed before recording the P2 index, plan that as a link to the
    # recovered entity without forcing locator resolution or decide_all.
    if ref in derived_refs:
        recovered_to = _entity_ref_with_source_ref(project_root, ref, kind=unit.candidate.type)
        if recovered_to is None:
            raise ProsePromotionError(f"artifact unit ref {ref!r} is present in derived refs but no entity was found")
        return ProseUnitPromotionDecision(
            source_ref=source_ref,
            source_slug=source_slug,
            artifact_id=artifact.artifact.artifact_id,
            unit_id=unit.unit_id,
            fingerprint=unit.fingerprint,
            decision="link",
            target_ref=recovered_to,
        )

    quote = Quote(unit.candidate.exact, unit.candidate.prefix, unit.candidate.suffix)
    try:
        resolution = InternalProseAdapter().resolve_unit(artifact.source.path, unit.locator, quote)
    except OSError as exc:
        raise ProsePromotionError(f"source/locator resolution failed for unit {unit_id!r}: {exc}") from exc
    if resolution.status is not LocatorStatus.RESOLVED:
        detail = f": {resolution.message}" if resolution.message else ""
        raise ProsePromotionError(f"locator for unit {unit_id!r} is {resolution.status.value}{detail}")
    targets = build_targets()
    if unit.candidate.type not in targets:
        raise ProsePromotionError(f"unit {unit_id!r} type {unit.candidate.type!r} is not a promotable target")
    promotable = Promotable(
        ref=ref,
        frag=unit.unit_id,
        claim=unit.candidate.exact,
        subject=unit.candidate.subject,
        object=unit.candidate.object,
        kind=unit.candidate.type,
    )
    decision = decide_all([promotable], corpora, targets)[0]
    target_ref = None
    if decision.decision == "MINT":
        target_ref = None
    elif decision.decision == "LINK":
        target_ref = decision.slug
    else:
        raise ProsePromotionError(f"unit {unit_id!r} cannot be batch-promoted: {decision.reason}")
    return ProseUnitPromotionDecision(
        source_ref=source_ref,
        source_slug=artifact.source.slug,
        artifact_id=artifact.artifact.artifact_id,
        unit_id=unit.unit_id,
        fingerprint=unit.fingerprint,
        decision=decision.decision.lower(),
        target_ref=target_ref,
    )
```

Do not refactor `promote_prose_unit` in this task. Its existing recovery short-circuit must stay before locator resolution and `decide_all`.

- [ ] **Step 4: Create the batch module**

Create `science/src/science_tool/annotation/prose_promotion_batch.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from science_tool.annotation.promote import ApplyReport
from science_tool.annotation.prose_decomposition import DecompositionError, ProseDecompositionStore
from science_tool.annotation.prose_promote import (
    ProsePromotionError,
    plan_prose_unit_promotion,
    promote_prose_unit,
)


class ProseBatchPromotionError(ValueError):
    """Raised when a prose promotion batch plan cannot be built or applied."""


@dataclass(frozen=True)
class ProsePromotionPlanUnit:
    unit_id: str
    fingerprint: str
    decision: Literal["mint", "link"]
    target_ref: str | None

    def to_json(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "fingerprint": self.fingerprint,
            "decision": self.decision,
            "target_ref": self.target_ref,
        }


@dataclass(frozen=True)
class ProsePromotionPlan:
    source_ref: str
    decomposition_artifact_id: str
    units: tuple[ProsePromotionPlanUnit, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "source_ref": self.source_ref,
            "decomposition_artifact_id": self.decomposition_artifact_id,
            "units": [unit.to_json() for unit in self.units],
        }


def build_prose_promotion_plan(project_root: Path, source_ref: str, *, unit_ids: list[str] | None = None) -> ProsePromotionPlan:
    source_slug = _source_slug(source_ref)
    store = ProseDecompositionStore(project_root)
    try:
        artifact = store.load_latest(source_slug)
    except DecompositionError as exc:
        raise ProseBatchPromotionError(str(exc)) from exc
    selected = unit_ids if unit_ids is not None else [unit.unit_id for unit in artifact.units if unit.disposition == "candidate"]
    planned: list[ProsePromotionPlanUnit] = []
    for unit_id in selected:
        try:
            decision = plan_prose_unit_promotion(project_root, source_ref, unit_id)
        except ProsePromotionError as exc:
            raise ProseBatchPromotionError(str(exc)) from exc
        if decision.decision not in {"mint", "link"}:
            raise ProseBatchPromotionError(f"unsupported batch decision for {unit_id}: {decision.decision}")
        planned.append(
            ProsePromotionPlanUnit(
                unit_id=decision.unit_id,
                fingerprint=decision.fingerprint,
                decision=decision.decision,
                target_ref=decision.target_ref,
            )
        )
    return ProsePromotionPlan(
        source_ref=source_ref,
        decomposition_artifact_id=artifact.artifact.artifact_id,
        units=tuple(planned),
    )


def parse_prose_promotion_plan(raw: str) -> ProsePromotionPlan:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProseBatchPromotionError(f"promotion plan is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProseBatchPromotionError("promotion plan must be a JSON object")
    if payload.get("schema_version") != 1:
        raise ProseBatchPromotionError("promotion plan schema_version must be 1")
    source_ref = _required_string(payload, "source_ref")
    artifact_id = _required_string(payload, "decomposition_artifact_id")
    raw_units = payload.get("units")
    if not isinstance(raw_units, list):
        raise ProseBatchPromotionError("promotion plan units must be a list")
    units = []
    for index, raw_unit in enumerate(raw_units):
        if not isinstance(raw_unit, dict):
            raise ProseBatchPromotionError(f"promotion plan unit[{index}] must be an object")
        decision = _required_string(raw_unit, "decision")
        if decision not in {"mint", "link"}:
            raise ProseBatchPromotionError(f"promotion plan unit[{index}].decision must be 'mint' or 'link'")
        target_ref = raw_unit.get("target_ref")
        if target_ref is not None and not isinstance(target_ref, str):
            raise ProseBatchPromotionError(f"promotion plan unit[{index}].target_ref must be null or a string")
        units.append(
            ProsePromotionPlanUnit(
                unit_id=_required_string(raw_unit, "unit_id"),
                fingerprint=_required_string(raw_unit, "fingerprint"),
                decision=decision,
                target_ref=target_ref,
            )
        )
    return ProsePromotionPlan(source_ref=source_ref, decomposition_artifact_id=artifact_id, units=tuple(units))


def apply_prose_promotion_plan(project_root: Path, plan: ProsePromotionPlan) -> ApplyReport:
    source_slug = _source_slug(plan.source_ref)
    store = ProseDecompositionStore(project_root)
    try:
        artifact = store.load_latest(source_slug)
    except DecompositionError as exc:
        raise ProseBatchPromotionError(str(exc)) from exc
    if artifact.artifact.artifact_id != plan.decomposition_artifact_id:
        raise ProseBatchPromotionError(
            "latest decomposition artifact changed: "
            f"plan has {plan.decomposition_artifact_id}; latest is {artifact.artifact.artifact_id}"
        )
    latest_by_unit = {unit.unit_id: unit for unit in artifact.units}
    report = ApplyReport()
    for planned in plan.units:
        unit = latest_by_unit.get(planned.unit_id)
        if unit is None:
            raise ProseBatchPromotionError(f"planned unit is missing from latest artifact: {planned.unit_id}")
        if unit.fingerprint != planned.fingerprint:
            raise ProseBatchPromotionError(f"fingerprint mismatch for planned unit {planned.unit_id}")
        if unit.disposition != "candidate":
            raise ProseBatchPromotionError(f"planned unit is non-candidate: {planned.unit_id}")
        try:
            current = plan_prose_unit_promotion(project_root, plan.source_ref, planned.unit_id)
        except ProsePromotionError as exc:
            raise ProseBatchPromotionError(str(exc)) from exc
        if current.decision != planned.decision or current.target_ref != planned.target_ref:
            raise ProseBatchPromotionError(
                f"promotion decision drift for {planned.unit_id}: "
                f"planned {planned.decision}->{planned.target_ref}; "
                f"current {current.decision}->{current.target_ref}"
            )
        try:
            unit_report = promote_prose_unit(
                project_root=project_root,
                source_ref=plan.source_ref,
                unit_id=planned.unit_id,
                apply=True,
            )
        except ProsePromotionError as exc:
            raise ProseBatchPromotionError(str(exc)) from exc
        report.minted += unit_report.minted
        report.linked += unit_report.linked
        report.skipped.update(unit_report.skipped)
        report.written_paths.extend(unit_report.written_paths)
    return report


def _source_slug(source_ref: str) -> str:
    prefix = "prose-source:"
    if not source_ref.startswith(prefix):
        raise ProseBatchPromotionError("source_ref must use prose-source:<slug>")
    slug = source_ref.removeprefix(prefix)
    if not slug:
        raise ProseBatchPromotionError("source slug must not be empty")
    return slug


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ProseBatchPromotionError(f"promotion plan {key} must be a non-empty string")
    return value
```

- [ ] **Step 5: Add batch CLI commands**

In `science/src/science_tool/annotation/cli.py`, add imports:

```python
from science_tool.annotation.prose_promotion_batch import (
    ProseBatchPromotionError,
    apply_prose_promotion_plan,
    build_prose_promotion_plan,
    parse_prose_promotion_plan,
)
```

Add commands after `promote-prose-decomposition`:

```python
@annotate_group.command("plan-prose-promotions")
@click.option("--source", "source_ref", required=True)
@click.option("--unit", "unit_ids", multiple=True)
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--output", "output_path", default=None, type=click.Path(dir_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def plan_prose_promotions_cmd(
    source_ref: str,
    unit_ids: tuple[str, ...],
    root: Path | None,
    output_path: Path | None,
    fmt: str,
) -> None:
    """Plan mint/link decisions for reviewed internal-prose units."""
    project_root = (root or Path.cwd()).resolve()
    try:
        plan = build_prose_promotion_plan(
            project_root,
            source_ref,
            unit_ids=list(unit_ids) if unit_ids else None,
        )
    except (ProseBatchPromotionError, DecompositionError) as exc:
        raise click.ClickException(str(exc)) from exc
    payload = plan.to_json()
    if output_path is not None:
        if not output_path.is_absolute():
            output_path = project_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    click.echo(
        f"planned prose promotions for {source_ref}: "
        f"units={len(plan.units)} artifact={plan.decomposition_artifact_id}"
    )
    for unit in plan.units:
        target = unit.target_ref or "new entity"
        click.echo(f"  {unit.unit_id}: {unit.decision} -> {target} ({unit.fingerprint})")


@annotate_group.command("apply-prose-promotions")
@click.argument("plan_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--root", "root", default=None, type=click.Path(file_okay=False, path_type=Path))
@click.option("--format", "fmt", type=click.Choice(("table", "json")), default="table")
def apply_prose_promotions_cmd(plan_path: Path, root: Path | None, fmt: str) -> None:
    """Apply an identity-only reviewed prose promotion plan."""
    project_root = (root or Path.cwd()).resolve()
    try:
        plan = parse_prose_promotion_plan(plan_path.read_text(encoding="utf-8"))
        report = apply_prose_promotion_plan(project_root, plan)
    except (ProseBatchPromotionError, DecompositionError) as exc:
        raise click.ClickException(str(exc)) from exc
    payload = {
        "minted": report.minted,
        "linked": report.linked,
        "skipped": dict(report.skipped),
        "written": report.written_paths,
    }
    if fmt == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    skipped = ", ".join(f"{reason}={count}" for reason, count in sorted(report.skipped.items())) or "none"
    click.echo(
        f"applied prose promotion plan for {plan.source_ref}: "
        f"minted={report.minted} linked={report.linked} skipped={skipped}"
    )
```

- [ ] **Step 6: Add CLI smoke tests**

Append to `science/tests/test_annotate_prose_decomposition_cli.py`:

```python
def test_plan_and_apply_prose_promotions_cli(tmp_path):
    ingest = CliRunner().invoke(
        annotate_group,
        ["ingest-prose-decomposition", str(_artifact_file(tmp_path)), "--root", str(tmp_path)],
    )
    assert ingest.exit_code == 0, ingest.output
    plan_path = tmp_path / "promotion-plan.json"

    plan = CliRunner().invoke(
        annotate_group,
        [
            "plan-prose-promotions",
            "--source",
            "prose-source:example",
            "--unit",
            "u001",
            "--root",
            str(tmp_path),
            "--output",
            str(plan_path),
            "--format",
            "json",
        ],
    )
    assert plan.exit_code == 0, plan.output
    payload = json.loads(plan.output)
    assert payload["units"][0]["decision"] == "mint"
    assert "claim" not in payload["units"][0]
    assert plan_path.exists()

    applied = CliRunner().invoke(
        annotate_group,
        ["apply-prose-promotions", str(plan_path), "--root", str(tmp_path), "--format", "json"],
    )
    assert applied.exit_code == 0, applied.output
    applied_payload = json.loads(applied.output)
    assert applied_payload["minted"] == 1
```

- [ ] **Step 7: Run batch tests**

Run:

```bash
uv run --frozen pytest science/tests/test_prose_promotion_batch.py science/tests/test_annotate_prose_decomposition_cli.py::test_plan_and_apply_prose_promotions_cli -q
```

Expected: PASS.

- [ ] **Step 8: Run existing promotion regressions**

Run:

```bash
uv run --frozen pytest science/tests/test_prose_promote.py science/tests/test_annotate_prose_decomposition_cli.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/annotation/prose_promote.py science/src/science_tool/annotation/prose_promotion_batch.py science/src/science_tool/annotation/cli.py science/tests/test_prose_promotion_batch.py science/tests/test_annotate_prose_decomposition_cli.py
git commit -m "feat(prose): plan and apply batch promotions"
```

---

### Task 7: Full Verification

**Files:**
- No source edits.

- [ ] **Step 1: Run focused prose and graph tests**

Run:

```bash
uv run --frozen pytest science/tests/test_annotate_prose_decomposition_cli.py science/tests/test_prose_decomposition.py science/tests/test_internal_prose_adapter.py science/tests/test_prose_promote.py science/tests/test_prose_promotion_batch.py science/tests/test_prose_source_entity.py science/tests/test_graph_io_revision_manifest.py science/tests/test_graph_migrate_identity_audit.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint and typing checks**

Run:

```bash
uv run --frozen ruff check science/src/science_tool/annotation/prose_validation.py science/src/science_tool/annotation/prose_promotion_batch.py science/src/science_tool/annotation/prose_decomposition.py science/src/science_tool/annotation/prose_source_entity.py science/src/science_tool/graph/io.py science/tests/test_annotate_prose_decomposition_cli.py science/tests/test_prose_promotion_batch.py science/tests/test_graph_io_revision_manifest.py
uv run --frozen pyright
```

Expected: PASS.

- [ ] **Step 3: Check worktree status**

Run:

```bash
git status --short
```

Expected: clean science worktree after all science commits. The downstream natural-systems worktree may remain on its pilot branch.
