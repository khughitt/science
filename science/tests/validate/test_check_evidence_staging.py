"""Tests for check_belief_eligible_empirical_has_dataset_usage (Task 2c).

Rule: an empirical evidence-line (evidence_type == empirical_data_evidence) that is
belief-eligible (belief_eligible absent or True) MUST declare non-empty dataset_usage.
Staged lines (belief_eligible: false) are exempt. Non-empirical types are unaffected.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.validate import Severity, ValidateContext


# ---------------------------------------------------------------------------
# Helpers (mirror the pattern in test_checks_evidence_lines.py)
# ---------------------------------------------------------------------------

def _write_manifest(root: Path) -> None:
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                "profile: research",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path) -> ValidateContext:
    _write_manifest(root)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixtures/constants
# ---------------------------------------------------------------------------

_EL_DIR = "entities/evidence-lines"


def _empirical_line(*, belief_eligible: str | None, dataset_usage: str) -> str:
    """Build frontmatter for an empirical evidence-line."""
    lines = [
        "---",
        "stance: supports",
        "target: proposition:p1",
        "source: dataset:d1",
        "evidence_type: empirical_data_evidence",
    ]
    if belief_eligible is not None:
        lines.append(f"belief_eligible: {belief_eligible}")
    lines.append(dataset_usage)
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Tests — ERROR cases
# ---------------------------------------------------------------------------

def test_empirical_belief_eligible_no_dataset_usage_errors(tmp_path: Path) -> None:
    """Empirical + belief_eligible: true + no dataset_usage → ERROR."""
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )

    p = _write(
        tmp_path,
        f"{_EL_DIR}/el01.md",
        _empirical_line(belief_eligible="true", dataset_usage=""),
    )

    results = list(check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "evidence.empirical.requires_dataset_usage"
    assert r.path == p


def test_empirical_belief_eligible_empty_list_dataset_usage_errors(tmp_path: Path) -> None:
    """Empirical + belief_eligible: true + dataset_usage: [] → ERROR."""
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )

    p = _write(
        tmp_path,
        f"{_EL_DIR}/el01.md",
        _empirical_line(belief_eligible="true", dataset_usage="dataset_usage: []"),
    )

    results = list(check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "evidence.empirical.requires_dataset_usage"
    assert r.path == p


def test_empirical_belief_eligible_absent_no_dataset_usage_errors(tmp_path: Path) -> None:
    """Absent belief_eligible defaults to True → ERROR when no dataset_usage."""
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )

    p = _write(
        tmp_path,
        f"{_EL_DIR}/el01.md",
        _empirical_line(belief_eligible=None, dataset_usage=""),
    )

    results = list(check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "evidence.empirical.requires_dataset_usage"
    assert r.path == p


# ---------------------------------------------------------------------------
# Tests — PASS cases (no error)
# ---------------------------------------------------------------------------

def test_empirical_belief_eligible_with_dataset_usage_clean(tmp_path: Path) -> None:
    """Empirical + belief_eligible: true + non-empty dataset_usage → no error."""
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )

    _write(
        tmp_path,
        f"{_EL_DIR}/el01.md",
        _empirical_line(
            belief_eligible="true",
            dataset_usage="dataset_usage:\n  - dataset: dataset:d1\n    role: analyzed",
        ),
    )

    results = list(check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path)))

    assert results == []


def test_empirical_staged_belief_eligible_false_exempt(tmp_path: Path) -> None:
    """belief_eligible: false (staged) → exempt even when dataset_usage absent."""
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )

    _write(
        tmp_path,
        f"{_EL_DIR}/el01.md",
        _empirical_line(belief_eligible="false", dataset_usage=""),
    )

    results = list(check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path)))

    assert results == []


def test_non_empirical_line_unaffected(tmp_path: Path) -> None:
    """Non-empirical evidence_type → rule does not apply."""
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )

    _write(
        tmp_path,
        f"{_EL_DIR}/el01.md",
        "\n".join(
            [
                "---",
                "stance: supports",
                "target: proposition:p1",
                "source: paper:x",
                "evidence_type: literature_evidence",
                "belief_eligible: true",
                "---",
                "",
            ]
        ),
    )

    results = list(check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path)))

    assert results == []


def test_empirical_staged_string_false_exempt(tmp_path: Path) -> None:
    """String 'false' for belief_eligible is treated as False → exempt."""
    from science_tool.validate.checks.evidence_lines import (
        check_belief_eligible_empirical_has_dataset_usage,
    )

    _write(
        tmp_path,
        f"{_EL_DIR}/el01.md",
        _empirical_line(belief_eligible="false", dataset_usage=""),
    )

    results = list(check_belief_eligible_empirical_has_dataset_usage(_ctx(tmp_path)))

    assert results == []
