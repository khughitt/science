from __future__ import annotations

from pathlib import Path

from science_tool.validate.acceptance import (
    EVIDENCE_SCOPED_RULES,
    entry_is_evidence_scoped,
    entry_suppresses,
    filter_accepted_warnings,
)
from science_tool.validate.result import Result, Severity

_SIG = "v1:" + "a" * 64                       # the bare hash token (NOT scoped on its own)
_LABELED = f"evidence-signature: {_SIG}"       # the complete labeled token that IS scoped


def _warn(rule: str, path: str, message: str) -> Result:
    return Result(Severity.WARN, Path(path), None, message, rule, None)


def test_evidence_scoped_rule_is_declared():
    assert "plan.correspondence-drift" in EVIDENCE_SCOPED_RULES


def test_path_only_entry_does_not_suppress_the_scoped_rule():
    entry = {"rule": "plan.correspondence-drift", "path": "entities/plans/0001-x.md", "reason": "checked"}
    assert not entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="entities/plans/0001-x.md", task=None, message=f"... {_LABELED}",
    )


def test_valid_signature_entry_suppresses():
    entry = {
        "rule": "plan.correspondence-drift", "path": "entities/plans/0001-x.md",
        "reason": "input file, not a deliverable", "message_contains": _LABELED,
    }
    assert entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="entities/plans/0001-x.md", task=None, message=f"... {_LABELED}",
    )


def test_bare_signature_without_label_does_not_suppress():
    # A hash without the `evidence-signature:` label is not a scoped signature.
    entry = {
        "rule": "plan.correspondence-drift", "path": "entities/plans/0001-x.md",
        "reason": "tried to accept with a bare hash", "message_contains": _SIG,
    }
    assert not entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="entities/plans/0001-x.md", task=None, message=f"... {_LABELED}",
    )


def test_scoped_entry_without_path_does_not_suppress():
    # Signature present, but no `path`: one signature would blind the rule tree-wide.
    entry = {"rule": "plan.correspondence-drift", "reason": "no path", "message_contains": _LABELED}
    assert not entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="entities/plans/0001-x.md", task=None, message=f"... {_LABELED}",
    )


def test_scoped_entry_with_absolute_path_does_not_suppress():
    entry = {
        "rule": "plan.correspondence-drift", "path": "/abs/entities/plans/0001-x.md",
        "reason": "absolute path", "message_contains": _LABELED,
    }
    assert not entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="/abs/entities/plans/0001-x.md", task=None, message=f"... {_LABELED}",
    )


def test_stale_signature_entry_does_not_suppress():
    entry = {
        "rule": "plan.correspondence-drift", "path": "entities/plans/0001-x.md",
        "reason": "was accepted", "message_contains": "evidence-signature: v1:" + "b" * 64,
    }
    assert not entry_suppresses(
        entry, rule="plan.correspondence-drift", severity="warn",
        path="entities/plans/0001-x.md", task=None, message=f"live {_LABELED}",
    )


def test_entry_is_evidence_scoped_requires_the_exact_token_spelling():
    assert not entry_is_evidence_scoped({"message_contains": "evidence-signature:"})    # label, no hash
    assert not entry_is_evidence_scoped({"message_contains": "v1:short"})               # malformed hash
    assert not entry_is_evidence_scoped({"message_contains": _SIG})                     # hash, no label
    assert not entry_is_evidence_scoped({"message_contains": f"evidence-signature:{_SIG}"})    # no space
    assert not entry_is_evidence_scoped({"message_contains": f"evidence-signature:  {_SIG}"})  # two spaces
    assert not entry_is_evidence_scoped({"message_contains": f"evidence-signature:\n{_SIG}"})  # newline
    assert entry_is_evidence_scoped({"message_contains": f"x {_LABELED} y"})            # exact token


def test_other_rules_are_unaffected_by_evidence_scoping(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        'name: f\nprofile: research\nhealth:\n  accepted_validation:\n'
        '    - rule: "code.metadata-gap"\n      path: "x.py"\n      reason: "ok"\n',
        encoding="utf-8",
    )
    kept = filter_accepted_warnings(tmp_path, [_warn("code.metadata-gap", "x.py", "gap")])
    assert kept == []  # a non-scoped rule still suppresses with a path-only entry


# filter_accepted_warnings is the `validate` surface (cli.py:152 _with_accepted_warnings_filtered
# delegates to it). These exercise the whole filter for the drift rule, not just the predicates.

def _drift_manifest(root: Path, entry_lines: str) -> None:
    (root / "science.yaml").write_text(
        "name: f\nprofile: research\nhealth:\n  accepted_validation:\n" + entry_lines,
        encoding="utf-8",
    )


def _drift_warn() -> Result:
    return _warn("plan.correspondence-drift", "entities/plans/0001-x.md", f"under-claims ... {_LABELED}")


def test_filter_keeps_drift_for_a_path_only_entry(tmp_path: Path):
    _drift_manifest(
        tmp_path,
        '    - rule: "plan.correspondence-drift"\n      path: "entities/plans/0001-x.md"\n'
        '      reason: "path only"\n',
    )
    assert filter_accepted_warnings(tmp_path, [_drift_warn()]) == [_drift_warn()]


def test_filter_suppresses_drift_for_a_valid_signature_entry(tmp_path: Path):
    _drift_manifest(
        tmp_path,
        '    - rule: "plan.correspondence-drift"\n      path: "entities/plans/0001-x.md"\n'
        f'      reason: "input, not a deliverable"\n      message_contains: "{_LABELED}"\n',
    )
    assert filter_accepted_warnings(tmp_path, [_drift_warn()]) == []


def test_filter_keeps_drift_for_a_stale_signature_entry(tmp_path: Path):
    _drift_manifest(
        tmp_path,
        '    - rule: "plan.correspondence-drift"\n      path: "entities/plans/0001-x.md"\n'
        '      reason: "stale"\n      message_contains: "evidence-signature: v1:' + "b" * 64 + '"\n',
    )
    assert filter_accepted_warnings(tmp_path, [_drift_warn()]) == [_drift_warn()]
