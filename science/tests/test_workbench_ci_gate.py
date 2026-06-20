"""Tests for `dag workbench --check` (Task 5d): CI fixpoint gate on scratch graph.

The `dag workbench --check <file>` command:
- Parses the committed workbench file.
- Compiles it on a SCRATCH temp dir (never writes to the real entities/ dir).
- Serializes the result to canonical YAML.
- Exits ZERO if the committed file equals the canonical form; exits NONZERO with
  a diff if they differ.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.dag.workbench import (
    EvidenceStub,
    WorkbenchFile,
    WorkbenchRow,
    compile_workbench,
    serialize_canonical,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: ci-gate-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )


def _make_canonical_workbench(tmp_path: Path) -> str:
    """Return the canonical serialized text for a small test workbench."""
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:PHF19",
                predicate="affects",
                object="construct:proliferation",
                polarity="positive",
                claim_layer="causal_effect",
                patch="patch-a",
                evidence=[
                    EvidenceStub(
                        stance="supports",
                        source="paper:Smith2025",
                        evidence_type="literature_evidence",
                    )
                ],
            ),
            WorkbenchRow(
                subject="gene:MYC",
                predicate="regulates",
                object="gene:CDK4",
                polarity="positive",
                patch="patch-a",
            ),
        ]
    )
    scratch = tmp_path / "scratch-seed"
    scratch.mkdir()
    _seed_project(scratch)
    result = compile_workbench(wb, project_root=scratch)
    return serialize_canonical(result)


def _snapshot_entities(entities_dir: Path) -> dict[str, bytes]:
    """Return a {relative_path: sha256_digest} snapshot of every file under entities_dir."""
    if not entities_dir.exists():
        return {}
    return {
        str(p.relative_to(entities_dir)): hashlib.sha256(p.read_bytes()).digest()
        for p in sorted(entities_dir.rglob("*"))
        if p.is_file()
    }


# ---------------------------------------------------------------------------
# Test 1: a committed workbench in canonical form → exit zero (passes CI gate)
# ---------------------------------------------------------------------------


def test_check_passes_on_canonical_workbench(tmp_path: Path) -> None:
    """A workbench already in canonical form passes the CI gate (exit 0)."""
    canonical_text = _make_canonical_workbench(tmp_path)

    # Write the canonical text to a "committed" workbench file.
    wb_file = tmp_path / "test.workbench.yaml"
    wb_file.write_text(canonical_text, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["dag", "workbench", "--check", str(wb_file)])
    assert result.exit_code == 0, (
        f"Expected exit 0 for canonical workbench, got {result.exit_code}.\nOutput:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Test 2: a workbench with an un-minted id-less row → exit nonzero + diff shown
# ---------------------------------------------------------------------------


def test_check_fails_on_uncompiled_idless_row(tmp_path: Path) -> None:
    """A workbench with an un-minted (id-less) row fails the gate (nonzero + diff)."""
    # Build a workbench that is NOT in canonical form: id is absent (not minted).
    wb_data = {
        "rows": [
            {
                "subject": "gene:PHF19",
                "predicate": "affects",
                "object": "construct:proliferation",
                "polarity": "positive",
                "patch": "patch-a",
                # no 'id' key — not in canonical form
            }
        ]
    }
    wb_file = tmp_path / "uncompiledold.workbench.yaml"
    wb_file.write_text(yaml.safe_dump(wb_data), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["dag", "workbench", "--check", str(wb_file)])
    assert result.exit_code != 0, (
        f"Expected nonzero exit for un-minted workbench, got {result.exit_code}."
    )
    # The output must contain a diff marker.
    assert "---" in result.output or "+++" in result.output or "@@" in result.output or "differ" in result.output.lower(), (
        f"Expected a diff in the output but got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Test 3: a workbench with an inline evidence stub → exit nonzero + diff shown
# ---------------------------------------------------------------------------


def test_check_fails_on_inline_stub_not_normalized(tmp_path: Path) -> None:
    """A workbench with inline evidence stubs (not refs) fails the gate."""
    # Canonical form requires evidence items to be reference strings, not stubs.
    # Here we have a row with an id but evidence as an inline stub mapping.
    # First get what the minted id would be:
    scratch = tmp_path / "scratch-id"
    scratch.mkdir()
    _seed_project(scratch)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:MYC",
                predicate="regulates",
                object="gene:CDK4",
                polarity="positive",
                patch="patch-a",
            )
        ]
    )
    result = compile_workbench(wb, project_root=scratch)
    minted_id = result.propositions[0].id

    # Write a workbench that has the correct minted id but an inline stub
    # instead of an evidence-line reference.
    wb_data = {
        "rows": [
            {
                "id": minted_id,
                "subject": "gene:MYC",
                "predicate": "regulates",
                "object": "gene:CDK4",
                "polarity": "positive",
                "patch": "patch-a",
                "evidence": [
                    {
                        "stance": "supports",
                        "evidence_type": "literature_evidence",
                        "source": "paper:Jones2024",
                    }
                ],
            }
        ]
    }
    wb_file = tmp_path / "stubby.workbench.yaml"
    wb_file.write_text(yaml.safe_dump(wb_data), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, ["dag", "workbench", "--check", str(wb_file)])
    assert result.exit_code != 0, (
        f"Expected nonzero exit for inline-stub workbench, got {result.exit_code}."
    )
    assert "---" in result.output or "+++" in result.output or "@@" in result.output or "differ" in result.output.lower(), (
        f"Expected a diff in the output but got:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# Test 4: the check writes NOTHING to the real entities/ dir (scratch isolation)
# ---------------------------------------------------------------------------


def test_check_does_not_write_real_entities(tmp_path: Path) -> None:
    """The --check gate must not touch the real project's entities/ dir.

    We set up a real project directory with an entities/ dir, snapshot its
    contents before and after the check, and assert they are byte-for-byte
    identical.
    """
    # Build a real project with an existing entities/ dir.
    real_project = tmp_path / "real_project"
    real_project.mkdir()
    _seed_project(real_project)
    entities_dir = real_project / "entities"
    entities_dir.mkdir()

    # Pre-populate one entity file so we have something concrete to protect.
    prop_dir = entities_dir / "propositions"
    prop_dir.mkdir()
    existing_entity = prop_dir / "sentinel-existing.md"
    existing_entity.write_text("---\nid: proposition:sentinel-existing\nkind: proposition\n---\n\n# sentinel\n")

    # Build a workbench file (NOT canonical — has id-less rows) that lives
    # in the real project.
    wb_data = {
        "rows": [
            {
                "subject": "gene:TP53",
                "predicate": "suppresses",
                "object": "construct:apoptosis-resistance",
                "polarity": "negative",
                "patch": "patch-b",
                # intentionally no id — not canonical
            }
        ]
    }
    wb_file = real_project / "tp53.workbench.yaml"
    wb_file.write_text(yaml.safe_dump(wb_data), encoding="utf-8")

    # Snapshot before.
    snapshot_before = _snapshot_entities(entities_dir)

    runner = CliRunner()
    result = runner.invoke(main, ["dag", "workbench", "--check", str(wb_file)])

    # The check should EXIT NONZERO (the workbench is not canonical).
    assert result.exit_code != 0, (
        f"Expected nonzero exit (uncompiled workbench), got {result.exit_code}.\nOutput:\n{result.output}"
    )

    # The entities/ dir must be byte-for-byte unchanged.
    snapshot_after = _snapshot_entities(entities_dir)
    assert snapshot_before == snapshot_after, (
        f"entities/ dir was mutated by --check.\n"
        f"Before: {sorted(snapshot_before)}\n"
        f"After:  {sorted(snapshot_after)}"
    )

    # Specifically, no new .md files were written alongside our sentinel.
    assert existing_entity.exists(), "Sentinel entity file was deleted!"
    after_files = {str(p.relative_to(entities_dir)) for p in entities_dir.rglob("*.md")}
    assert after_files == {"propositions/sentinel-existing.md"}, (
        f"Unexpected files in entities/ after --check: {after_files}"
    )
