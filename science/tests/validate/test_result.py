from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from science_tool.validate import Result, Severity


def test_result_is_frozen() -> None:
    result = Result(
        severity=Severity.ERROR,
        path=Path("doc/example.md"),
        line=3,
        message="broken",
        rule="manifest",
        task="task:1",
    )

    with pytest.raises(FrozenInstanceError):
        result.message = "changed"  # type: ignore[misc]


def test_result_equality_uses_all_fields() -> None:
    first = Result(Severity.WARN, Path("doc/a.md"), 1, "message", "rule", None)
    same = Result(Severity.WARN, Path("doc/a.md"), 1, "message", "rule", None)
    different = Result(Severity.INFO, Path("doc/a.md"), 1, "message", "rule", None)

    assert first == same
    assert first != different


def test_result_to_dict_round_trips_through_json() -> None:
    result = Result(
        severity=Severity.INFO,
        path=Path("doc/example.md"),
        line=None,
        message="noted",
        rule=None,
        task="task:2",
    )

    payload = json.loads(json.dumps(result.to_dict()))

    assert payload == {
        "severity": "info",
        "path": "doc/example.md",
        "line": None,
        "message": "noted",
        "rule": None,
        "task": "task:2",
    }
    assert (
        Result(
            severity=Severity.from_str(payload["severity"]),
            path=Path(payload["path"]) if payload["path"] else None,
            line=payload["line"],
            message=payload["message"],
            rule=payload["rule"],
            task=payload["task"],
        )
        == result
    )


def test_severity_from_str_accepts_names_and_values_case_insensitively() -> None:
    assert Severity.from_str("ERROR") is Severity.ERROR
    assert Severity.from_str("warn") is Severity.WARN
    assert Severity.from_str("Info") is Severity.INFO

    with pytest.raises(ValueError, match="unknown severity"):
        Severity.from_str("debug")
