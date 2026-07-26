from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_tool.cli import main
from science_tool.explore_ideas import ApplyValidationError, resolve_anchors_report


def _write_report(root: Path, text: str) -> Path:
    path = root / "doc" / "explorations" / "explore-2026-07-06.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _seed_references(root: Path) -> None:
    seed_project(root)
    write_markdown_entity(
        root,
        "entities/papers/smith-2024.md",
        {
            "id": "paper:Smith2024",
            "kind": "paper",
            "title": "Targeted therapy in myeloma",
            "doi": "10.1000/ABC",
            "year": 2024,
            "bibkey": "Smith2024",
        },
        "Paper body.\n",
    )
    (root / "papers" / "references.bib").write_text(
        "@article{Jones2021,\n"
        "  title = {Immune remodeling after therapy},\n"
        "  doi = {10.2000/jones},\n"
        "  author = {Jones, A.},\n"
        "  year = {2021},\n"
        "}\n"
        "@article{Dup2020,\n"
        "  title = {Duplicated title},\n"
        "  year = {2020},\n"
        "}\n",
        encoding="utf-8",
    )
    write_markdown_entity(
        root,
        "entities/papers/dup-2020.md",
        {
            "id": "paper:Dup2020",
            "kind": "paper",
            "title": "Duplicated title",
            "year": 2020,
        },
        "Paper body.\n",
    )


def test_resolve_anchors_report_matches_doi_title_existing_and_unresolved(tmp_path: Path) -> None:
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """# Explore

```yaml
candidate_id: cand-a
decision: keep
proposed_kind: question
title: Candidate
literature_anchors:
  - doi: https://doi.org/10.1000/abc
    title: Targeted therapy in myeloma
  - title: Immune remodeling after therapy
  - ref: cite:Already2020
    title: Already routed
  - doi: 10.9000/missing
    title: Missing paper
```
""",
    )

    result = resolve_anchors_report(tmp_path, "explore-2026-07-06")

    assert [row.status for row in result.anchors] == [
        "resolved",
        "resolved",
        "already-resolved",
        "unresolved",
    ]
    assert result.anchors[0].resolved == "paper:Smith2024"
    assert result.anchors[0].match_kind == "doi"
    assert result.anchors[1].resolved == "cite:Jones2021"
    assert result.anchors[1].match_kind == "title"
    assert result.anchors[2].resolved == "cite:Already2020"
    assert result.anchors[3].query == "10.9000/missing"
    assert result.counts == {
        "resolved": 2,
        "already_resolved": 1,
        "ambiguous": 0,
        "unresolved": 1,
        "mismatch": 0,
        # The two `resolved` plus the one `already-resolved` matched real
        # records; the unresolved one did not, so nothing confirms its identity.
        "verified": 3,
        "unverified": 1,
    }


def test_resolve_anchors_flags_doi_match_whose_title_disagrees(tmp_path: Path) -> None:
    # fb-2026-07-17-009: a syntactically valid DOI pointing at a real but
    # UNRELATED paper (the anchor's stated title names a different work) must
    # NOT resolve silently -- it is the shape that misattributes provenance.
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-zhu
decision: keep
proposed_kind: question
title: Candidate
literature_anchors:
  - doi: 10.1000/abc
    title: A twelve-hour ultradian clock governs metabolic rhythms
    first_author: Zhu
    year: 2017
```
""",
    )

    result = resolve_anchors_report(tmp_path, "explore-2026-07-06")

    row = result.anchors[0]
    assert row.status == "mismatch"
    assert row.resolved == "paper:Smith2024"
    assert row.match_kind == "doi"
    assert row.detail is not None and "title" in row.detail.lower()
    assert result.counts == {
        "resolved": 0,
        "already_resolved": 0,
        "ambiguous": 0,
        "unresolved": 0,
        "mismatch": 1,
        # A mismatch is NOT a verified identity -- the DOI resolved, but to a
        # different work than the anchor names. Counting it as verified would
        # certify exactly the misattribution the mismatch check exists to catch.
        "verified": 0,
        "unverified": 1,
    }


def test_resolve_anchors_doi_match_with_consistent_title_still_resolves(tmp_path: Path) -> None:
    # The cross-check must not fire on a legitimate anchor: same DOI, a title
    # that agrees with the resolved record (minor wording variation tolerated).
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-ok
decision: keep
proposed_kind: question
title: Candidate
literature_anchors:
  - doi: 10.1000/abc
    title: Targeted therapy in myeloma patients
    first_author: Smith
    year: 2024
```
""",
    )

    result = resolve_anchors_report(tmp_path, "explore-2026-07-06")

    row = result.anchors[0]
    assert row.status == "resolved"
    assert row.resolved == "paper:Smith2024"
    assert row.detail is None


def test_resolve_anchors_report_skips_empty_placeholder_anchors(tmp_path: Path) -> None:
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """# Explore

```yaml
candidate_id: cand-a
decision: keep
proposed_kind: question
title: Candidate
literature_anchors:
  - doi: ""
    title: ""
    ref: null
  - doi:
    note: placeholder from first draft
  - first_author: Smith
    year: 2024
  - doi: 10.2000/jones
```
""",
    )

    result = resolve_anchors_report(tmp_path, "explore-2026-07-06")

    assert len(result.anchors) == 1
    assert result.anchors[0].status == "resolved"
    assert result.anchors[0].resolved == "cite:Jones2021"
    assert result.counts == {
        "resolved": 1,
        "already_resolved": 0,
        "ambiguous": 0,
        "unresolved": 0,
        "mismatch": 0,
        "verified": 1,
        "unverified": 0,
    }


def test_resolve_anchors_report_prefers_paper_entity_over_bib_duplicate(tmp_path: Path) -> None:
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
proposed_kind: hypothesis
title: Candidate
literature_anchors:
  - title: Duplicated title
```
""",
    )

    result = resolve_anchors_report(tmp_path, "explore-2026-07-06")

    row = result.anchors[0]
    assert row.status == "resolved"
    assert row.resolved == "paper:Dup2020"
    assert row.match_kind == "title"
    assert row.candidates == ("paper:Dup2020",)


def test_resolve_anchors_report_matches_bib_key(tmp_path: Path) -> None:
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
proposed_kind: hypothesis
title: Candidate
literature_anchors:
  - key: Jones2021
```
""",
    )

    result = resolve_anchors_report(tmp_path, "explore-2026-07-06")

    row = result.anchors[0]
    assert row.status == "resolved"
    assert row.resolved == "cite:Jones2021"
    assert row.match_kind == "key"
    assert row.query == "Jones2021"


def test_resolve_anchors_report_reports_ambiguous_same_priority_title_matches(tmp_path: Path) -> None:
    _seed_references(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/papers/dup-alt-2020.md",
        {
            "id": "paper:DupAlt2020",
            "kind": "paper",
            "title": "Duplicated title",
            "year": 2020,
        },
        "Paper body.\n",
    )
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
proposed_kind: hypothesis
title: Candidate
literature_anchors:
  - title: Duplicated title
```
""",
    )

    result = resolve_anchors_report(tmp_path, "explore-2026-07-06")

    row = result.anchors[0]
    assert row.status == "ambiguous"
    assert row.resolved is None
    assert row.match_kind == "title"
    assert row.candidates == ("paper:Dup2020", "paper:DupAlt2020")


def test_resolve_anchors_report_rejects_malformed_anchor_lists(tmp_path: Path) -> None:
    seed_project(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
literature_anchors:
  not: a list
```
""",
    )

    with pytest.raises(ApplyValidationError, match="literature_anchors must be a list"):
        resolve_anchors_report(tmp_path, "explore-2026-07-06")


def test_resolve_anchors_report_to_dict_shape(tmp_path: Path) -> None:
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
literature_anchors:
  - doi: 10.2000/jones
```
""",
    )

    payload = resolve_anchors_report(tmp_path, "explore-2026-07-06").to_dict()

    counts = payload["counts"]
    assert isinstance(counts, dict)
    assert counts["resolved"] == 1
    assert payload["anchors"] == [
        {
            "candidate_id": "cand-a",
            "anchor_index": 0,
            "status": "resolved",
            "verification": "verified",
            "resolved": "cite:Jones2021",
            "match_kind": "doi",
            "query": "10.2000/jones",
            "candidates": ["cite:Jones2021"],
            "detail": None,
            "anchor": {"doi": "10.2000/jones"},
        }
    ]


def test_cli_resolve_anchors_text_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
literature_anchors:
  - doi: 10.2000/jones
  - title: Missing
```
""",
    )

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["explore-ideas", "resolve-anchors", "--from", "explore-2026-07-06"])

    assert result.exit_code == 0
    assert "1 resolved, 0 already resolved, 0 ambiguous, 1 unresolved" in result.output
    assert "cand-a[0] -> cite:Jones2021 (doi)" in result.output
    assert "cand-a[1] unresolved: Missing" in result.output


def test_cli_resolve_anchors_flags_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
literature_anchors:
  - doi: 10.1000/abc
    title: An unrelated twelve-hour clock study
```
""",
    )

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["explore-ideas", "resolve-anchors", "--from", "explore-2026-07-06"])

    assert result.exit_code == 0
    assert "1 mismatch" in result.output
    assert "cand-a[0] MISMATCH paper:Smith2024 (doi):" in result.output


def test_cli_resolve_anchors_json_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
literature_anchors:
  - doi: 10.2000/jones
```
""",
    )

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        main, ["explore-ideas", "resolve-anchors", "--from", "explore-2026-07-06", "--format", "json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["counts"]["resolved"] == 1
    assert payload["anchors"][0]["resolved"] == "cite:Jones2021"


def test_cli_resolve_anchors_json_output_serializes_anchor_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A `date:` anchor field is parsed by YAML into a datetime.date, which
    # json.dumps cannot serialize unless to_dict coerces it to an ISO string.
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
literature_anchors:
  - doi: 10.2000/jones
    date: 2021-06-15
```
""",
    )

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        main, ["explore-ideas", "resolve-anchors", "--from", "explore-2026-07-06", "--format", "json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["anchors"][0]["anchor"]["date"] == "2021-06-15"


def test_unresolved_anchor_is_reported_unverified(tmp_path: Path) -> None:
    # fb-2026-07-25-006: the resolver checks anchors against the PROJECT corpus
    # only. An anchor that matches nothing there has had its identity confirmed
    # by nothing at all -- the reported run left 47 of 49 in that state, and a
    # bare `ref: null` does not say so. The verdict is stated per anchor.
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
proposed_kind: question
title: Candidate
literature_anchors:
  - doi: 10.9999/not-in-this-project
    title: A plausible-looking title
    first_author: Nobody
    year: 2023
```
""",
    )

    row = resolve_anchors_report(tmp_path, "explore-2026-07-06").anchors[0]

    assert row.status == "unresolved"
    assert row.verification == "unverified"


def test_ambiguous_anchor_is_not_verified(tmp_path: Path) -> None:
    # Several candidate records is not a confirmed identity: the resolver did
    # not pick one, so nothing has been established about which work the anchor
    # names. Two paper entities sharing a title make the ambiguity real -- the
    # bib duplicate in the shared fixture is deduped away by ref preference.
    _seed_references(tmp_path)
    for slug, entity_id in (("twin-a", "paper:TwinA"), ("twin-b", "paper:TwinB")):
        write_markdown_entity(
            tmp_path,
            f"entities/papers/{slug}.md",
            {"id": entity_id, "kind": "paper", "title": "Ambiguous shared title", "year": 2019},
            "Paper body.\n",
        )
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
proposed_kind: question
title: Candidate
literature_anchors:
  - title: Ambiguous shared title
```
""",
    )

    row = resolve_anchors_report(tmp_path, "explore-2026-07-06").anchors[0]

    assert row.status == "ambiguous"
    assert row.resolved is None
    assert row.verification == "unverified"


def test_resolve_anchors_text_output_states_the_identity_split(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The per-status tally buries the number that matters. The text surface
    # states how many anchors were confirmed against a real record.
    _seed_references(tmp_path)
    _write_report(
        tmp_path,
        """```yaml
candidate_id: cand-a
decision: keep
proposed_kind: question
title: Candidate
literature_anchors:
  - doi: 10.2000/jones
  - doi: 10.9999/nowhere
  - doi: 10.9998/also-nowhere
```
""",
    )

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["explore-ideas", "resolve-anchors", "--from", "explore-2026-07-06"])

    assert result.exit_code == 0
    assert "identity: 1 of 3 verified against a real record" in result.output
    assert "2 unverified" in result.output
