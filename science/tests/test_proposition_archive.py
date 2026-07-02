from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation import io as anno_io
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.proposition_archive import (
    PropositionArchiveError,
    archive_superseded_propositions,
    build_superseded_proposition_archive_report,
)
from science_tool.archive import (
    ArchiveRow,
    append_row,
    archive_index_path,
)


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")


def _entity(root: Path, rel: str, frontmatter: str, body: str = "Body.\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return path


def _proposition(
    root: Path,
    slug: str,
    *,
    status: str = "active",
    extra_frontmatter: str = "",
) -> Path:
    return _entity(
        root,
        f"entities/propositions/{slug}.md",
        f"id: proposition:{slug}\n"
        "type: proposition\n"
        f"title: {slug}\n"
        f"status: {status}\n"
        f"{extra_frontmatter}",
        "Claim.\n",
    )


def _paper_sidecar(root: Path, citekey: str, annotations: list[Annotation]) -> None:
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Paper body.\n", encoding="utf-8")
    anno_io.write_sidecar(anno_io.sidecar_for_markdown(md), anno_io.Sidecar(annotations=tuple(annotations)))


def _ann(
    annotation_id: str,
    *,
    promoted_to: str,
    status: Status = Status.OPEN,
    annotation_type: str = "proposition",
) -> Annotation:
    created = datetime(2026, 7, 2, tzinfo=timezone.utc)
    non_open = status is not Status.OPEN
    return Annotation(
        id=annotation_id,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=annotation_id, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value='{"section":"abstract","stance":"asserted"}', format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type=annotation_type,
        source="llm-annot:m:paper-annotate-v1",
        status=status,
        creator="paper-annotate",
        created=created,
        content_hash="0" * 64,
        modified=created if non_open else None,
        modified_by="curator" if non_open else None,
        promoted_to=promoted_to,
    )


def _candidate_by_id(report: dict, ref: str) -> dict:
    return next(candidate for candidate in report["candidates"] if candidate["id"] == ref)


def _blocked_candidate(root: Path, extra_frontmatter: str, *, slug: str = "duplicate") -> dict:
    _seed(root)
    _proposition(root, "canonical")
    _proposition(root, slug, status="superseded", extra_frontmatter=extra_frontmatter)

    report = build_superseded_proposition_archive_report(root)

    candidate = _candidate_by_id(report, f"proposition:{slug}")
    assert candidate["status"] == "blocked"
    return candidate


def test_dry_run_reports_ready_scalar_superseded_proposition(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")

    report = build_superseded_proposition_archive_report(tmp_path)

    assert report["summary"] == {"ready": 1, "blocked": 0, "skipped": 0}
    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "ready"
    assert candidate["lineage_kind"] == "superseded_by"
    assert candidate["successors"] == ["proposition:canonical"]
    assert candidate["archive_path"] == "entities/_archive/propositions/duplicate.md"
    assert candidate["blocking_annotation_refs"] == []


def test_dry_run_reports_ready_multi_successor_superseded_proposition(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "negative")
    _proposition(tmp_path, "positive")
    _proposition(
        tmp_path,
        "broad",
        status="superseded",
        extra_frontmatter=(
            "resynthesized_into:\n"
            "  - proposition:positive\n"
            "  - proposition:negative\n"
        ),
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:broad")
    assert candidate["status"] == "ready"
    assert candidate["lineage_kind"] == "resynthesized_into"
    assert candidate["successors"] == ["proposition:negative", "proposition:positive"]


def test_dry_run_blocks_missing_lineage(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "old", status="superseded")

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:old")
    assert candidate["status"] == "blocked"
    assert "missing lineage" in candidate["blockers"]


def test_dry_run_blocks_both_lineage_fields_declared(tmp_path: Path) -> None:
    candidate = _blocked_candidate(
        tmp_path,
        "superseded_by: proposition:canonical\n"
        "resynthesized_into:\n"
        "  - proposition:canonical\n",
    )

    assert "declares both superseded_by and resynthesized_into" in candidate["blockers"]
    assert candidate["lineage_kind"] is None
    assert candidate["successors"] == []


@pytest.mark.parametrize(
    ("extra_frontmatter", "blocker"),
    [
        ("superseded_by:\n", "malformed superseded_by"),
        ("superseded_by:\n  - proposition:canonical\n", "malformed superseded_by"),
        ("resynthesized_into: proposition:canonical\n", "malformed resynthesized_into"),
        ("resynthesized_into:\n  - proposition:canonical\n  - 123\n", "malformed resynthesized_into"),
    ],
)
def test_dry_run_blocks_malformed_scalar_and_list_lineage(
    tmp_path: Path,
    extra_frontmatter: str,
    blocker: str,
) -> None:
    candidate = _blocked_candidate(tmp_path, extra_frontmatter)

    assert blocker in candidate["blockers"]
    assert candidate["successors"] == []


def test_dry_run_blocks_self_successor(tmp_path: Path) -> None:
    candidate = _blocked_candidate(tmp_path, "superseded_by: proposition:duplicate\n")

    assert "lineage points to itself" in candidate["blockers"]
    assert candidate["successors"] == ["proposition:duplicate"]


def test_dry_run_blocks_duplicate_successor(tmp_path: Path) -> None:
    candidate = _blocked_candidate(
        tmp_path,
        "resynthesized_into:\n"
        "  - proposition:canonical\n"
        "  - proposition:canonical\n",
    )

    assert "duplicate successor proposition:canonical" in candidate["blockers"]
    assert candidate["successors"] == ["proposition:canonical", "proposition:canonical"]


def test_dry_run_blocks_unknown_successor(tmp_path: Path) -> None:
    candidate = _blocked_candidate(tmp_path, "superseded_by: proposition:missing\n")

    assert "unknown successor proposition:missing" in candidate["blockers"]
    assert candidate["successors"] == ["proposition:missing"]


def test_dry_run_blocks_archive_destination_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    archive_path = tmp_path / "entities" / "_archive" / "propositions" / "duplicate.md"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text("Existing archive content.\n", encoding="utf-8")

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "blocked"
    assert "archive destination exists: entities/_archive/propositions/duplicate.md" in candidate["blockers"]


def test_dry_run_blocks_active_archive_id_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:duplicate",
            original_path="entities/_archive/propositions/duplicate.md",
            archived_at="T1",
        ),
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "blocked"
    assert "archive id already active: proposition:duplicate" in candidate["blockers"]


def test_dry_run_blocks_live_id_alias_collision(tmp_path: Path) -> None:
    candidate = _blocked_candidate(
        tmp_path,
        "superseded_by: proposition:canonical\n"
        "aliases:\n"
        "  - proposition:canonical\n",
    )

    assert any("id/alias collision on proposition:canonical" in blocker for blocker in candidate["blockers"])


def test_dry_run_blocks_active_archive_alias_collision(tmp_path: Path) -> None:
    # An active archive row whose *alias* equals the candidate id is not caught by the
    # "archive id already active" check (active_by_id is keyed by canonical id), and
    # load_project_sources does not reject it. Readiness check 9 must still block it.
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:ghost",
            aliases=["proposition:duplicate"],
            original_path="entities/_archive/propositions/ghost.md",
            archived_at="T1",
        ),
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "blocked"
    assert any("id/alias collision" in blocker for blocker in candidate["blockers"])


def test_live_sidecar_backlink_blocks_archive(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    _paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", promoted_to="proposition:duplicate")])

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "blocked"
    assert candidate["blocking_annotation_refs"] == ["annotation:entities/papers/Smith2020.source#a-1"]
    assert "live annotation backlink" in candidate["blockers"][0]


def test_inactive_sidecar_backlink_does_not_block_archive(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    _paper_sidecar(
        tmp_path,
        "Smith2020",
        [_ann("a-1", promoted_to="proposition:duplicate", status=Status.FIXED)],
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "ready"
    assert candidate["blocking_annotation_refs"] == []


def test_report_surfaces_generic_inbound_live_refs_as_context(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")
    _entity(
        tmp_path,
        "entities/propositions/observer.md",
        "id: proposition:observer\n"
        "type: proposition\n"
        "title: Observer\n"
        "status: active\n"
        "related:\n"
        "  - proposition:duplicate\n",
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "ready"
    assert candidate["inbound_live_refs"] == ["proposition:observer"]


def test_apply_raises_task_5_placeholder(tmp_path: Path) -> None:
    _seed(tmp_path)

    with pytest.raises(PropositionArchiveError, match="apply is implemented in Task 5"):
        archive_superseded_propositions(tmp_path, apply=True)
