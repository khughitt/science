from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.explore_ideas import (
    ApplyValidationError,
    CandidateBlock,
    parse_report,
    resolve_report_path,
)

_REPORT = """\
---
type: meta
id: explore-2026-07-04
---

# Exploration report

Some human prose that is not a candidate.

```yaml
candidate_id: cand-a
proposed_kind: question
title: First
decision: keep
```

```yaml
not_a_candidate: true
note: ignore me
```

```yaml
candidate_id: cand-b
proposed_kind: hypothesis
title: Second
decision: drop
```
"""


def test_parse_report_extracts_only_candidate_blocks() -> None:
    blocks = parse_report(_REPORT)
    assert [b.candidate_id for b in blocks] == ["cand-a", "cand-b"]
    assert isinstance(blocks[0], CandidateBlock)
    assert blocks[0].data["title"] == "First"


def test_parse_report_ignores_non_yaml_and_non_candidate() -> None:
    assert parse_report("no fenced blocks here") == []


def test_parse_report_malformed_yaml_raises_validation_error() -> None:
    text = "```yaml\ncandidate_id: [unterminated\n```\n"
    with pytest.raises(ApplyValidationError, match="invalid yaml"):
        parse_report(text)


def test_resolve_report_path_direct_file(tmp_path: Path) -> None:
    report = tmp_path / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    assert resolve_report_path(tmp_path, str(report)) == report


def test_resolve_report_path_by_id(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    report = d / "explore-2026-07-04.md"
    report.write_text("x", encoding="utf-8")
    assert resolve_report_path(tmp_path, "explore-2026-07-04") == report


def test_resolve_report_path_no_reprepend(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "meta" / "explorations"
    d.mkdir(parents=True)
    (d / "explore-2026-07-04.md").write_text("x", encoding="utf-8")
    with pytest.raises(ApplyValidationError):
        resolve_report_path(tmp_path, "explore-explore-2026-07-04")


def test_resolve_report_path_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(ApplyValidationError):
        resolve_report_path(tmp_path, "nope")
