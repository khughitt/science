from __future__ import annotations

from pathlib import Path

from science_tool.correspondence.signature import SIGNATURE_VERSION
from science_tool.validate.checks.accepted_validation import check_accepted_validation
from science_tool.validate.context import ValidateContext
from science_tool.validate.gates import cumulative_rules

_SIG = f"{SIGNATURE_VERSION}:" + "a" * 64


def _ctx(root: Path, manifest_health: str) -> ValidateContext:
    (root / "science.yaml").write_text(f"name: f\nprofile: research\n{manifest_health}", encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_unscoped_entry_for_scoped_rule_warns(tmp_path: Path):
    ctx = _ctx(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "x"\n',
    )
    results = list(check_accepted_validation(ctx))
    assert len(results) == 1
    assert results[0].rule == "accepted-validation.evidence-scope-required"
    assert results[0].severity.value == "warn"
    assert not results[0].path.is_absolute()


def test_scoped_entry_with_valid_signature_is_silent(tmp_path: Path):
    ctx = _ctx(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "x"\n'
        f'      message_contains: "evidence-signature: {_SIG}"\n',
    )
    assert not list(check_accepted_validation(ctx))


def test_signature_present_but_absolute_path_warns(tmp_path: Path):
    # A complete signature is not enough on its own: an absolute path would blind the
    # rule beyond one project-relative plan, so the guard still fires.
    ctx = _ctx(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "/abs/entities/plans/0001-x.md"\n      reason: "x"\n'
        f'      message_contains: "evidence-signature: {_SIG}"\n',
    )
    results = list(check_accepted_validation(ctx))
    assert len(results) == 1
    assert results[0].rule == "accepted-validation.evidence-scope-required"


def test_unrelated_rule_entry_is_silent(tmp_path: Path):
    ctx = _ctx(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "code.metadata-gap"\n'
        '      path: "x.py"\n      reason: "x"\n',
    )
    assert not list(check_accepted_validation(ctx))


def test_rule_is_never_gated(tmp_path: Path):
    assert "accepted-validation.evidence-scope-required" not in cumulative_rules("hygiene")
