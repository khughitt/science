"""Tests for evidence-line structural QA checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate import Severity, ValidateContext


# ---------------------------------------------------------------------------
# Helpers
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
# Rule: evidence.unstanced — sub-case (a): missing stance or target on a line
# ---------------------------------------------------------------------------

def test_unstanced_clean_line_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert results == []


def test_unstanced_missing_stance_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\ntarget: proposition:p1\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.unstanced"
    assert r.path == p
    assert "stance" in r.message


def test_unstanced_missing_target_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.unstanced"
    assert r.path == p
    assert "target" in r.message


def test_unstanced_empty_target_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: ''\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.unstanced"
    assert r.path == p


# ---------------------------------------------------------------------------
# Rule: evidence.unstanced — sub-case (b): uncounted proposition source_ref
# ---------------------------------------------------------------------------

def test_unstanced_counted_source_ref_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write(
        tmp_path,
        "doc/propositions/p1.md",
        "---\nid: proposition:p1\nsource_refs:\n  - paper:x\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert results == []


def test_unstanced_uncounted_source_ref_emits_warn(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    prop = _write(
        tmp_path,
        "doc/propositions/p1.md",
        "---\nid: proposition:p1\nsource_refs:\n  - paper:x\n  - paper:y\n---\n",
    )
    # Only paper:x has a matching evidence-line; paper:y is uncounted.
    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.unstanced"
    assert r.path == prop
    assert "paper:y" in r.message


def test_unstanced_cite_prefix_source_ref_is_skipped(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_lines_unstanced

    _write(
        tmp_path,
        "doc/propositions/p1.md",
        "---\nid: proposition:p1\nsource_refs:\n  - cite:jones2020\n---\n",
    )

    results = list(check_evidence_lines_unstanced(_ctx(tmp_path)))

    # cite: refs are skipped — no warning
    assert results == []


# ---------------------------------------------------------------------------
# Rule: independence.ungrouped-collapse
# ---------------------------------------------------------------------------

def test_ungrouped_collapse_shared_source_without_group_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_ungrouped_collapse

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: shared-source\n---\n",
    )

    results = list(check_independence_ungrouped_collapse(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "independence.ungrouped-collapse"
    assert r.path == p


def test_ungrouped_collapse_circular_without_group_errors(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_ungrouped_collapse

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: circular\n---\n",
    )

    results = list(check_independence_ungrouped_collapse(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.ERROR
    assert r.rule == "independence.ungrouped-collapse"
    assert r.path == p


def test_ungrouped_collapse_shared_source_with_group_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_ungrouped_collapse

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: shared-source\nindependence_group: grp-a\n---\n",
    )

    results = list(check_independence_ungrouped_collapse(_ctx(tmp_path)))

    assert results == []


def test_ungrouped_collapse_independent_is_always_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_ungrouped_collapse

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\n---\n",
    )

    results = list(check_independence_ungrouped_collapse(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Rule: independence.suspect-circular
# ---------------------------------------------------------------------------

def test_suspect_circular_two_independent_sharing_dataset_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\nshared_dataset: gse100\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el02.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:y\nindependence: independent\nshared_dataset: gse100\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "independence.suspect-circular"
    assert "shared_dataset" in r.message
    assert "gse100" in r.message


def test_suspect_circular_two_independent_sharing_group_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\nindependence_group: grp-a\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el02.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:y\nindependence: independent\nindependence_group: grp-a\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert len(results) == 1
    assert results[0].rule == "independence.suspect-circular"


def test_suspect_circular_single_line_emits_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\nshared_dataset: ds:alpha\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert results == []


def test_suspect_circular_genuinely_independent_lines_emit_no_results(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el02.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:y\nindependence: independent\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert results == []


def test_suspect_circular_different_targets_do_not_trigger(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_independence_suspect_circular

    # Same shared_dataset but DIFFERENT targets — should not trigger.
    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nindependence: independent\nshared_dataset: gse100\n---\n",
    )
    _write(
        tmp_path,
        "doc/evidence-lines/el02.md",
        "---\nstance: supports\ntarget: proposition:p2\nsource: paper:y\nindependence: independent\nshared_dataset: gse100\n---\n",
    )

    results = list(check_independence_suspect_circular(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Rule: evidence.strength-implausible
# ---------------------------------------------------------------------------

def test_strength_implausible_strong_background_constraint_warns(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_strength_implausible

    p = _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nstrength: strong\nevidence_role: background_constraint\n---\n",
    )

    results = list(check_evidence_strength_implausible(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity == Severity.WARN
    assert r.rule == "evidence.strength-implausible"
    assert r.path == p


def test_strength_implausible_strong_direct_test_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_strength_implausible

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nstrength: strong\nevidence_role: direct_test\n---\n",
    )

    results = list(check_evidence_strength_implausible(_ctx(tmp_path)))

    assert results == []


def test_strength_implausible_moderate_background_constraint_is_clean(tmp_path: Path) -> None:
    from science_tool.validate.checks.evidence_lines import check_evidence_strength_implausible

    _write(
        tmp_path,
        "doc/evidence-lines/el01.md",
        "---\nstance: supports\ntarget: proposition:p1\nsource: paper:x\nstrength: moderate\nevidence_role: background_constraint\n---\n",
    )

    results = list(check_evidence_strength_implausible(_ctx(tmp_path)))

    assert results == []


# ---------------------------------------------------------------------------
# Rule: evidence.unscored-line
# ---------------------------------------------------------------------------

def test_unscored_line_warns_for_unrecognized_type(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\n"
           "evidence_type: made_up\nevidence_role: direct_test\nstrength: strong\n---\n")
    results = list(check_evidence_unscored_line(_ctx(tmp_path)))
    assert len(results) == 1 and results[0].severity is Severity.WARN


def test_unscored_line_clean_for_fully_specified(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: supports\ntarget: proposition:p1\n"
           "evidence_type: empirical_data\nevidence_role: direct_test\nstrength: strong\n---\n")
    assert list(check_evidence_unscored_line(_ctx(tmp_path))) == []


def test_unscored_line_skips_diagnostic_roles(tmp_path: Path):
    from science_tool.validate.checks.evidence_lines import check_evidence_unscored_line

    # model_criticism is recognized-but-non-massed: outside EVIDENCE_ROLE_RANK, never flagged.
    _write(tmp_path, "doc/evidence-lines/el01.md",
           "---\nstance: disputes\ntarget: proposition:p1\nevidence_role: model_criticism\n---\n")
    assert list(check_evidence_unscored_line(_ctx(tmp_path))) == []
