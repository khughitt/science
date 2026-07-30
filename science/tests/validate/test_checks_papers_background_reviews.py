"""Promoted reviews-are-not-evidence guardrail."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate.checks import CANONICAL_CHECKS
from science_tool.validate.checks.papers import (
    _background_review_observations,
    check_papers,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.observations import ValidationNotice
from science_tool.validate.result import Result
from science_tool.validate.runner import VALIDATE_PROFILES, RunResult, run


_PAPERS_CHECK = next(entry for entry in CANONICAL_CHECKS if entry.fn is check_papers)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal Science project. Without science.yaml the context refuses to build."""
    (tmp_path / "science.yaml").write_text("name: fixture\n", encoding="utf-8")
    return tmp_path


def _paper(root: Path, key: str, status: str) -> None:
    papers = root / "entities" / "papers"
    papers.mkdir(parents=True, exist_ok=True)
    (papers / f"{key}.md").write_text(
        f'---\nkind: paper\ntitle: "{key}"\nstatus: {status}\n---\n', encoding="utf-8"
    )


def _entity(root: Path, kind_dir: str, name: str, frontmatter: str) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(f"---\n{frontmatter}---\n\nbody\n", encoding="utf-8")


def _provenance(root: Path, name: str, body: str) -> None:
    d = root / "doc" / "provenance"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.yaml").write_text(body, encoding="utf-8")


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(
        root, strict=False, verbose=False, include_all_checks=False
    )


def _issues(root: Path) -> list[Result]:
    return [o for o in _background_review_observations(_ctx(root)) if isinstance(o, Result)]


def _run_with_only_papers(
    root: Path,
    *,
    profile: str,
    include_all_checks: bool,
) -> RunResult:
    """Run the real validation boundary without trusting leaked suite registry state."""
    original_entries = list(CANONICAL_CHECKS)
    try:
        CANONICAL_CHECKS[:] = [_PAPERS_CHECK]
        return run(
            root,
            strict=False,
            verbose=False,
            profile=profile,
            include_all_checks=include_all_checks,
        )
    finally:
        CANONICAL_CHECKS[:] = original_entries


def test_background_paper_in_evidence_refs_warns(project: Path) -> None:
    _paper(project, "Tasci2022", "background")
    _entity(
        project, "hypotheses", "0001-h",
        "kind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n",
    )

    issues = _issues(project)

    assert len(issues) == 1
    assert issues[0].rule_id == "papers.background-review-evidence-ref"
    assert issues[0].qualifiers["paper_ref"] == "Tasci2022"


def test_unindented_list_items_are_parsed(project: Path) -> None:
    """Every live entity writes top-level `- paper:...`; the sidecar regex required indentation."""
    _paper(project, "Tasci2022", "background")
    _entity(
        project, "themes", "0007-t",
        "kind: theme\nevidence_refs:\n- paper:Tasci2022\n- report:0012-x\n",
    )

    assert len(_issues(project)) == 1


def test_hyphenated_and_dotted_paper_ids(project: Path) -> None:
    _paper(project, "van-der-Berg-2021.v2", "background")
    _entity(
        project, "reports", "0001-r",
        "kind: report\nevidence_refs:\n- paper:van-der-Berg-2021.v2\n",
    )

    issues = _issues(project)

    assert len(issues) == 1
    assert issues[0].qualifiers["paper_ref"] == "van-der-Berg-2021.v2"


def test_recursive_scan_includes_live_nested_entities_but_skips_underscore_subtrees(
    project: Path,
) -> None:
    _paper(project, "Tasci2022", "background")
    _entity(
        project,
        "themes/cohort",
        "0001-live",
        "kind: theme\nevidence_refs:\n- paper:Tasci2022\n",
    )
    _entity(
        project,
        "themes/_wip",
        "0002-hidden",
        "kind: theme\nevidence_refs:\n- paper:Tasci2022\n",
    )

    issues = _issues(project)

    assert [issue.path.relative_to(project).as_posix() for issue in issues if issue.path] == [
        "entities/themes/cohort/0001-live.md"
    ]


def test_active_paper_in_evidence_refs_is_silent(project: Path) -> None:
    _paper(project, "Smith2024", "active")
    _entity(
        project, "hypotheses", "0001-h",
        "kind: hypothesis\nevidence_refs:\n- paper:Smith2024\n",
    )

    assert _issues(project) == []


def test_source_refs_are_not_evidence_refs(project: Path) -> None:
    """The health/meta corpus cites background papers under source_refs."""
    _paper(project, "Tasci2022", "background")
    _entity(
        project, "themes", "0007-t",
        "kind: theme\nsource_refs:\n- paper:Tasci2022\nevidence_refs:\n- report:0012-x\n",
    )

    assert _issues(project) == []


def test_duplicate_citation_dedupes_file_wide(project: Path) -> None:
    """Identity is (rule, path, paper_ref); duplicates would collide at the producer."""
    _paper(project, "Tasci2022", "background")
    _entity(
        project, "hypotheses", "0001-h",
        "kind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n- cite:Tasci2022\n",
    )

    assert len(_issues(project)) == 1


def test_no_background_papers_emits_notice(project: Path) -> None:
    _paper(project, "Smith2024", "active")

    observations = list(_background_review_observations(_ctx(project)))

    assert all(isinstance(o, ValidationNotice) for o in observations)
    assert any("no status:background" in o.message for o in observations)


def test_compliant_provenance_record_is_silent(project: Path) -> None:
    """Both live health/meta Tasci2022 records are already correctly typed."""
    _paper(project, "Tasci2022", "background")
    _provenance(
        project, "tasci",
        "source_ref: paper:Tasci2022\nevidence_tier: background\nreview_typed_source: true\n",
    )

    assert _issues(project) == []


def test_quoted_source_ref_and_real_booleans(project: Path) -> None:
    """YAML quoting and native booleans must not defeat the check."""
    _paper(project, "Tasci2022", "background")
    _provenance(
        project, "tasci",
        'source_ref: "paper:Tasci2022"\nevidence_tier: "background"\nreview_typed_source: yes\n',
    )

    assert _issues(project) == []


def test_provenance_violating_both_conditions_yields_two_findings(project: Path) -> None:
    """Separate rules exist precisely so these two do not collide on identity."""
    _paper(project, "Tasci2022", "background")
    _provenance(
        project, "tasci",
        "source_ref: paper:Tasci2022\nevidence_tier: primary\nreview_typed_source: false\n",
    )

    issues = _issues(project)

    assert len(issues) == 2
    assert {i.rule_id for i in issues} == {
        "papers.background-review-source-typing",
        "papers.background-review-evidence-tier",
    }
    assert {i.qualifiers["paper_ref"] for i in issues} == {"Tasci2022"}


def test_provenance_for_active_paper_is_silent(project: Path) -> None:
    _paper(project, "Smith2024", "active")
    _provenance(project, "smith", "source_ref: paper:Smith2024\nevidence_tier: primary\n")

    assert _issues(project) == []


def test_check_runs_in_every_profile(project: Path) -> None:
    """A guardrail that only runs in the slow path is a guardrail that stops running."""
    _paper(project, "Tasci2022", "background")
    _entity(
        project,
        "hypotheses",
        "0001-h",
        "kind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n",
    )

    for profile in VALIDATE_PROFILES:
        result = _run_with_only_papers(
            project,
            profile=profile,
            include_all_checks=True,
        )
        assert [finding.rule_id for finding in result.results] == [
            "papers.background-review-evidence-ref"
        ], profile


def test_check_is_not_gated_on_include_all(project: Path) -> None:
    _paper(project, "Tasci2022", "background")
    _entity(
        project,
        "hypotheses",
        "0001-h",
        "kind: hypothesis\nevidence_refs:\n- paper:Tasci2022\n",
    )

    result = _run_with_only_papers(
        project,
        profile="full",
        include_all_checks=False,
    )

    assert [finding.rule_id for finding in result.results] == [
        "papers.background-review-evidence-ref"
    ]
