from pathlib import Path

from science_model.audit import LocationEvidence, Span, TextEvidence

from science_tool.prose_lint import LintIssue
from science_tool.validate.checks import prose_lints
from science_tool.validate.checks.prose_lints import (
    RULE_ADVISORY,
    RULE_CONFIG,
    RULE_HIT,
    check_prose_lints,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.observations import ValidationMetricObservation
from science_tool.validate.result import Result


def _ctx(root: Path, *, strict: bool = False) -> ValidateContext:
    manifest = root / "science.yaml"
    if not manifest.exists():
        manifest.write_text("name: test\n", encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=strict, verbose=False)


def _write_doc(root: Path, text: str) -> None:
    path = root / "doc" / "note.md"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")


def _metrics(observations: list[object]) -> dict[str, object]:
    metric = next(
        item for item in observations if isinstance(item, ValidationMetricObservation)
    )
    return metric.metrics.model_dump(mode="json")


def test_missing_doc_directory_emits_zero_numeric_metrics(tmp_path: Path) -> None:
    observations = list(check_prose_lints(_ctx(tmp_path)))
    assert _metrics(observations) == {
        "verified": 0,
        "unverifiable": 0,
        "mismatch": 0,
        "error": 0,
    }
    assert not [item for item in observations if isinstance(item, Result)]


def test_warn_hit_uses_path_subject_and_normalized_match_identity(
    tmp_path: Path,
) -> None:
    _write_doc(tmp_path, "Smith 2020 argues that the result is robust.\n")
    observations = list(check_prose_lints(_ctx(tmp_path)))
    hits = [item for item in observations if isinstance(item, Result)]
    assert len(hits) == 1
    assert hits[0].rule == RULE_HIT
    assert hits[0].qualifiers == {
        "check": "bare-author-year",
        "match": "smith 2020",
    }


def test_different_normalized_matches_remain_distinct_findings(
    tmp_path: Path,
) -> None:
    _write_doc(
        tmp_path,
        "Smith 2020 argues that the result is robust.\n"
        "Jones 2021 reports a replication.\n",
    )

    observations = list(check_prose_lints(_ctx(tmp_path)))
    hits = [item for item in observations if isinstance(item, Result)]

    assert len(hits) == 2
    assert all(hit.rule == RULE_HIT for hit in hits)
    assert [hit.qualifiers for hit in hits] == [
        {
            "check": "bare-author-year",
            "match": "smith 2020",
        },
        {
            "check": "bare-author-year",
            "match": "jones 2021",
        },
    ]


def test_semantically_identical_matches_group_and_preserve_all_locations(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_doc(tmp_path, "first\nsecond\n")
    path = tmp_path / "doc" / "note.md"
    monkeypatch.setattr(
        prose_lints,
        "scan_root",
        lambda *_args, **_kwargs: {
            "hits": [
                LintIssue(
                    file=path,
                    line=1,
                    col=1,
                    check="bare-author-year",
                    severity="warn",
                    message="first hit",
                    match="  Smith\t2020 ",
                ),
                LintIssue(
                    file=path,
                    line=2,
                    col=1,
                    check="bare-author-year",
                    severity="warn",
                    message="second hit",
                    match="smith 2020",
                ),
            ],
            "counts": {"bare-author-year": 2},
            "coverage": {},
        },
    )

    observations = list(check_prose_lints(_ctx(tmp_path)))
    hits = [item for item in observations if isinstance(item, Result)]

    assert len(hits) == 1
    assert hits[0].qualifiers == {
        "check": "bare-author-year",
        "match": "smith 2020",
    }
    assert hits[0].to_finding(tmp_path).evidence == (
        LocationEvidence(path="doc/note.md", line=1),
        LocationEvidence(path="doc/note.md", line=2),
    )


def test_large_semantic_group_is_summarized_instead_of_truncated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_doc(tmp_path, "body\n")
    path = tmp_path / "doc" / "note.md"
    monkeypatch.setattr(
        prose_lints,
        "scan_root",
        lambda *_args, **_kwargs: {
            "hits": [
                LintIssue(
                    file=path,
                    line=line,
                    col=1,
                    check="bare-author-year",
                    severity="warn",
                    message="repeated hit",
                    match="Smith 2020",
                )
                for line in range(1, 102)
            ],
            "counts": {"bare-author-year": 101},
            "coverage": {},
        },
    )

    observations = list(check_prose_lints(_ctx(tmp_path)))
    hits = [item for item in observations if isinstance(item, Result)]

    assert len(hits) == 1
    assert hits[0].to_finding(tmp_path).evidence == (
        LocationEvidence(
            path="doc/note.md",
            span=Span(start_line=1, end_line=101),
        ),
        TextEvidence(
            label="location summary",
            text=(
                "101 semantically identical prose-lint locations summarized "
                "across lines 1-101 to stay within the 100-entry evidence bound."
            ),
        ),
    )


def test_numeric_coverage_appears_only_in_metrics(tmp_path: Path) -> None:
    _write_doc(tmp_path, "Body text with no numeric bindings.\n")
    observations = list(check_prose_lints(_ctx(tmp_path)))
    assert _metrics(observations) == {
        "verified": 0,
        "unverifiable": 0,
        "mismatch": 0,
        "error": 0,
    }
    assert all(
        not isinstance(item, Result)
        or "numeric-verification.coverage" not in item.rule_id
        for item in observations
    )


def test_policy_info_rules_have_distinct_visibility() -> None:
    assert RULE_ADVISORY.default_visibility == "hidden"
    assert RULE_CONFIG.default_visibility == "visible"
    assert RULE_HIT.default_visibility == "visible"


def test_prose_rules_and_metric_schema_are_registered() -> None:
    from science_tool.validate.checks import CANONICAL_CHECKS

    entry = next(
        item
        for item in CANONICAL_CHECKS
        if item.producer.producer_id == "validate.prose-lints"
    )
    assert entry.producer.producer_id == "validate.prose-lints"
    assert set(entry.producer.rules) == {RULE_HIT, RULE_ADVISORY, RULE_CONFIG}
    assert entry.producer.metrics_schema is not None
