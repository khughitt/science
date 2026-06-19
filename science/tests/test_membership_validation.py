from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.propositions import check_discusses_membership
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _project(tmp_path: Path, discusses_yaml: str) -> ValidateContext:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    pdir = tmp_path / "entities" / "propositions"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "p1.md").write_text(
        "\n".join(
            [
                "---",
                'id: "proposition:p1"',
                'type: "proposition"',
                'title: "P1"',
                'status: "active"',
                "ontology_terms: []",
                "source_refs: []",
                "related: []",
                f"discusses: {discusses_yaml}",
                "---",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return ValidateContext.from_project_root(tmp_path, strict=True, verbose=False)


def _errors(ctx):
    return [r for r in check_discusses_membership(ctx) if r.severity == Severity.ERROR]


def test_valid_membership_has_no_errors(tmp_path: Path):
    ctx = _project(tmp_path, '[{frame: "hypothesis:h1", role: "rival"}]')
    assert _errors(ctx) == []


def test_bare_string_has_no_errors(tmp_path: Path):
    ctx = _project(tmp_path, '["hypothesis:h1"]')
    assert _errors(ctx) == []


def test_unknown_role_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '[{frame: "hypothesis:h1", role: "rebuttal"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.role" for r in errs)


def test_missing_frame_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '[{role: "core"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.frame" for r in errs)


def test_top_level_scalar_discusses_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '"hypothesis:h1"')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.shape" for r in errs)


def test_top_level_mapping_discusses_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '{frame: "hypothesis:h1", role: "core"}')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.shape" for r in errs)


def test_conflicting_duplicate_frame_is_error(tmp_path: Path):
    ctx = _project(
        tmp_path,
        '[{frame: "hypothesis:h1", role: "core"}, {frame: "hypothesis:h1", role: "rival"}]',
    )
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.duplicate" for r in errs)


def test_string_and_object_same_frame_conflict_is_error(tmp_path: Path):
    ctx = _project(tmp_path, '["hypothesis:h1", {frame: "hypothesis:h1", role: "rival"}]')
    errs = _errors(ctx)
    assert any(r.rule == "proposition.membership.duplicate" for r in errs)
