"""TDD test for compile_workbench entity-conformance fix (Task 0.3).

compile_workbench must write entity files that pass entity_conformance
checks — specifically the frontmatter-completeness check that requires
id, type, title, status, created, updated in every entity file.

Prior to the fix, _write_entity_file popped `type` and never stamped
`created`/`updated`, causing every entity it wrote to fail the check.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from science_tool.dag.workbench import (
    EvidenceStub,
    WorkbenchFile,
    WorkbenchRow,
    compile_workbench,
)
from science_tool.validate.checks.entity_conformance import _REQUIRED_FRONTMATTER


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: conformance-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"No YAML frontmatter in {path}"
    _, fm_text, _ = text.split("---\n", 2)
    return yaml.safe_load(fm_text) or {}


# ---------------------------------------------------------------------------
# (1) Proposition entity file has all required frontmatter fields
# ---------------------------------------------------------------------------


def test_compiled_proposition_has_required_frontmatter(tmp_path: Path) -> None:
    """Compiled proposition entity passes entity-conformance frontmatter check."""
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:PHF19",
                predicate="affects",
                object="construct:proliferation",
                polarity="positive",
                patch="patch-a",
            )
        ]
    )

    result = compile_workbench(wb, project_root=tmp_path, as_of=date(2026, 6, 13))

    prop = result.propositions[0]
    slug = prop.id.split(":", 1)[1]
    prop_path = tmp_path / "entities" / "propositions" / f"{slug}.md"
    assert prop_path.is_file()

    fm = _read_frontmatter(prop_path)
    missing = [f for f in _REQUIRED_FRONTMATTER if f not in fm]
    assert not missing, f"Missing frontmatter fields in proposition entity: {missing}"

    # Type must be the plain string "proposition".
    assert fm["type"] == "proposition", f"Expected type='proposition', got {fm['type']!r}"
    assert fm["created"] == "2026-06-13"
    assert fm["updated"] == "2026-06-13"


# ---------------------------------------------------------------------------
# (2) Evidence-line entity file has all required frontmatter fields
# ---------------------------------------------------------------------------


def test_compiled_evidence_line_has_required_frontmatter(tmp_path: Path) -> None:
    """Compiled evidence-line entity passes entity-conformance frontmatter check."""
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:PHF19",
                predicate="affects",
                object="construct:proliferation",
                polarity="positive",
                patch="patch-a",
                evidence=[
                    EvidenceStub(
                        stance="supports",
                        source="paper:Smith2025",
                        evidence_type="literature_evidence",
                    )
                ],
            )
        ]
    )

    result = compile_workbench(wb, project_root=tmp_path, as_of=date(2026, 6, 13))

    assert len(result.evidence_lines) == 1
    ev = result.evidence_lines[0]
    ev_slug = ev.id.split(":", 1)[1]
    ev_path = tmp_path / "entities" / "evidence-lines" / f"{ev_slug}.md"
    assert ev_path.is_file()

    fm = _read_frontmatter(ev_path)
    missing = [f for f in _REQUIRED_FRONTMATTER if f not in fm]
    assert not missing, f"Missing frontmatter fields in evidence-line entity: {missing}"

    # Type must be the plain string "evidence-line".
    assert fm["type"] == "evidence-line", f"Expected type='evidence-line', got {fm['type']!r}"
    assert fm["created"] == "2026-06-13"
    assert fm["updated"] == "2026-06-13"


# ---------------------------------------------------------------------------
# (3) created is preserved on upsert; updated advances
# ---------------------------------------------------------------------------


def test_created_preserved_on_upsert_updated_advances(tmp_path: Path) -> None:
    """Second compile reuses the existing entity's `created`; `updated` advances."""
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:MYC",
                predicate="regulates",
                object="gene:CDK4",
                polarity="positive",
                patch="patch-a",
                evidence=[
                    EvidenceStub(
                        stance="supports",
                        source="paper:Jones2024",
                        evidence_type="literature_evidence",
                    )
                ],
            )
        ]
    )

    # First compile.
    result1 = compile_workbench(wb, project_root=tmp_path, as_of=date(2026, 6, 13))
    prop = result1.propositions[0]
    slug = prop.id.split(":", 1)[1]
    prop_path = tmp_path / "entities" / "propositions" / f"{slug}.md"

    fm1 = _read_frontmatter(prop_path)
    assert fm1["created"] == "2026-06-13"
    assert fm1["updated"] == "2026-06-13"

    # Second compile one week later.
    result2 = compile_workbench(wb, project_root=tmp_path, as_of=date(2026, 6, 20))
    prop2 = result2.propositions[0]
    assert prop2.id == prop.id  # same entity

    fm2 = _read_frontmatter(prop_path)
    # `created` must be stable (not overwritten to 2026-06-20).
    assert fm2["created"] == "2026-06-13", (
        f"`created` was overwritten on upsert; expected 2026-06-13, got {fm2['created']!r}"
    )
    # `updated` must have advanced.
    assert fm2["updated"] == "2026-06-20", f"`updated` did not advance; expected 2026-06-20, got {fm2['updated']!r}"

    # Check evidence-line entity too.
    ev = result2.evidence_lines[0]
    ev_slug = ev.id.split(":", 1)[1]
    ev_path = tmp_path / "entities" / "evidence-lines" / f"{ev_slug}.md"
    fm_ev2 = _read_frontmatter(ev_path)
    assert fm_ev2["created"] == "2026-06-13"
    assert fm_ev2["updated"] == "2026-06-20"


# ---------------------------------------------------------------------------
# (4) Default behavior (no as_of) uses date.today()
# ---------------------------------------------------------------------------


def test_default_as_of_stamps_today(tmp_path: Path) -> None:
    """compile_workbench with no as_of uses date.today() for created/updated."""
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:CCND1",
                predicate="affects",
                object="construct:cell-cycle",
                polarity="positive",
                patch="patch-default",
            )
        ]
    )

    result = compile_workbench(wb, project_root=tmp_path)  # no as_of
    prop = result.propositions[0]
    slug = prop.id.split(":", 1)[1]
    prop_path = tmp_path / "entities" / "propositions" / f"{slug}.md"

    fm = _read_frontmatter(prop_path)
    today_str = date.today().isoformat()
    assert fm.get("created") == today_str, f"Expected created={today_str!r}, got {fm.get('created')!r}"
    assert fm.get("updated") == today_str, f"Expected updated={today_str!r}, got {fm.get('updated')!r}"


# ---------------------------------------------------------------------------
# (5) Malformed existing entity file falls back gracefully — does not crash
# ---------------------------------------------------------------------------


def test_malformed_existing_entity_falls_back_gracefully(tmp_path: Path) -> None:
    """A corrupt/unparseable existing entity file does not crash compile_workbench.

    The fallback uses the injected as_of date for both created and updated.
    """
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        rows=[
            WorkbenchRow(
                subject="gene:IRF4",
                predicate="affects",
                object="construct:survival",
                polarity="positive",
                patch="patch-a",
            )
        ]
    )

    # Pre-mint the destination path so we know where to inject the bad file.
    result0 = compile_workbench(wb, project_root=tmp_path, as_of=date(2026, 6, 1))
    prop = result0.propositions[0]
    slug = prop.id.split(":", 1)[1]
    prop_path = tmp_path / "entities" / "propositions" / f"{slug}.md"
    assert prop_path.is_file()

    # Overwrite with malformed YAML frontmatter.
    prop_path.write_text("---\n: : bad yaml\n---\n", encoding="utf-8")

    # Compile again with a new date — must NOT raise.
    as_of = date(2026, 6, 13)
    result = compile_workbench(wb, project_root=tmp_path, as_of=as_of)

    assert len(result.propositions) == 1
    fm = _read_frontmatter(prop_path)
    assert fm.get("created") == as_of.isoformat(), (
        f"Expected created fallback to {as_of.isoformat()!r}, got {fm.get('created')!r}"
    )
    assert fm.get("updated") == as_of.isoformat(), f"Expected updated={as_of.isoformat()!r}, got {fm.get('updated')!r}"
