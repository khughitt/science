"""Regression oracle for `assess_numeric_claims` (Part A of the numeric-provenance redesign).

Each row in `fixtures/numeric_provenance_oracle.jsonl` is a self-contained
fixture (frontmatter + body) paired with the literal numeric-claim string it
contains and the Part-A outcome the design says that claim must resolve to.
Seven rows are the adversarial controls from
`docs/plans/2026-07-18-numeric-provenance-check-design.md`'s Testing section,
verbatim; the remainder are curated, hand-authored fixtures reproducing the
shapes found in the 2026-07-18 numeric-anchor cross-project audit
(`docs/audits/2026-07-18-numeric-anchor-audit/`), spanning every audit
category (structural NotClaim, marker-scoped Exempt, stipulated-without-marker
Unanchored, frontmatter- and title-anchored Anchored, same-paragraph-anchored
Anchored, distant-cite Unanchored, and truly-orphaned Unanchored).

This is a PINNING test: labels reflect the design's intended outcome and must
never be adjusted to match a buggy engine.
"""

import json
from pathlib import Path

import pytest

from science_tool.numeric_provenance import (
    Anchored, Exempt, NotClaim, NumericProvenanceConfig, Unanchored,
    assess_numeric_claims, build_document_context, build_resolution_index,
)

ORACLE = Path(__file__).parent / "fixtures" / "numeric_provenance_oracle.jsonl"
_OUTCOME = {"NotClaim": NotClaim, "Exempt": Exempt, "Anchored": Anchored, "Unanchored": Unanchored}


def _rows():
    return [json.loads(line) for line in ORACLE.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("row", _rows(), ids=lambda r: r["finding_id"])
def test_oracle_expected_outcome(row, tmp_path):
    # Build a self-contained project reproducing the fixture, with real anchors present.
    (tmp_path / "science.yaml").write_text("name: oracle\n")
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text("## [t064] Anchor task\n\nbody\n")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "qap.json").write_text("{}")
    fm = row.get("frontmatter", "")
    path = tmp_path / f"{row['finding_id']}.md"
    path.write_text(f"---\n{fm}\n---\n{row['fixture_md']}" if fm else row["fixture_md"])
    cfg = NumericProvenanceConfig(
        anchor_patterns=("task:", r"\[@", "cite:"),
        spec_class_kinds=frozenset({"pre-registration", "plan"}),
        provenance_fields=("source_refs", "task_links", "input"),
    )
    assessments = assess_numeric_claims(build_document_context(path), build_resolution_index(tmp_path), cfg)
    match = [a for a in assessments if a.claim.value == row["number"]]
    assert match, f"{row['finding_id']}: number {row['number']!r} not assessed"
    assert isinstance(match[0], _OUTCOME[row["expected_part_a_outcome"]]), (
        f"{row['finding_id']}: {row['expected_reason']}")
