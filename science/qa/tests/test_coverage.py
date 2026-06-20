from science_qa.coverage import (
    STATUS_BLOCKED,
    STATUS_EMPTY,
    STATUS_NA,
    STATUS_RAN,
    Coverage,
    CoverageEntry,
)


def _cov():
    return Coverage(
        entries=[
            CoverageEntry("a/x", "a", STATUS_RAN, ["c1"], 0),
            CoverageEntry("a/y", "a", STATUS_EMPTY, [], 0),
            CoverageEntry("b/z", "b", STATUS_BLOCKED, [], 1),
            CoverageEntry("b/o", "b", STATUS_NA, [], 0),
        ],
        unconfigured_families=["tabular/categoricals"],
    )


def test_executable_denominator_excludes_not_applicable():
    # ran + empty + blocked = 3 ; not-applicable excluded
    assert _cov().executable_denominator() == 3


def test_narrow_signal_lists_empty_blocked_and_unconfigured():
    signal = _cov().narrow_signal()
    assert "a/y" in signal and "b/z" in signal and "tabular/categoricals" in signal
    assert "a/x" not in signal


def test_to_dict_is_deterministic_and_sorted():
    d = _cov().to_dict()
    assert [e["check_id"] for e in d["entries"]] == ["a/x", "a/y", "b/o", "b/z"]
    assert d["executable_denominator"] == 3
    assert d["ran"] == 1
