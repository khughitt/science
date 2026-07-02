from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from rdflib import Dataset
from rdflib.namespace import RDF

from science_tool.annotation import io as anno_io
from science_tool.annotation import proposition_archive
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
    _postflight,
    _rows_for_ready_candidates,
    archive_superseded_propositions,
    build_superseded_proposition_archive_report,
)
from science_tool.archive import (
    ArchiveRow,
    append_row,
    archive_index_path,
    derive_archive_path,
    load_archive_index,
)
from science_tool.graph.store import PROJECT_NS, SCI_NS


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
        f"id: proposition:{slug}\ntype: proposition\ntitle: {slug}\nstatus: {status}\n{extra_frontmatter}",
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


def _knowledge_graph(root: Path):
    from science_tool.graph.materialize import materialize_graph

    out_path = materialize_graph(root, strict=False)
    dataset = Dataset()
    dataset.parse(source=str(out_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/knowledge"])


def _entity_uri(ref: str):
    kind, slug = ref.split(":", 1)
    return PROJECT_NS[f"{kind}/{slug}"]


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
        extra_frontmatter=("resynthesized_into:\n  - proposition:positive\n  - proposition:negative\n"),
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
        "superseded_by: proposition:canonical\nresynthesized_into:\n  - proposition:canonical\n",
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
        "resynthesized_into:\n  - proposition:canonical\n  - proposition:canonical\n",
    )

    assert "duplicate successor proposition:canonical" in candidate["blockers"]
    assert candidate["successors"] == ["proposition:canonical", "proposition:canonical"]


def test_dry_run_blocks_duplicate_successor_through_archived_alias(tmp_path: Path) -> None:
    _seed(tmp_path)
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:archived-canonical",
            aliases=["proposition:archived-alias"],
            original_path="entities/propositions/archived-canonical.md",
            archived_at="T1",
        ),
    )
    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter=(
            "resynthesized_into:\n"
            "  - proposition:archived-canonical\n"
            "  - proposition:archived-alias\n"
        ),
    )

    report = build_superseded_proposition_archive_report(tmp_path)

    candidate = _candidate_by_id(report, "proposition:duplicate")
    assert candidate["status"] == "blocked"
    assert "duplicate successor proposition:archived-canonical" in candidate["blockers"]
    assert candidate["successors"] == ["proposition:archived-canonical", "proposition:archived-canonical"]


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
        "superseded_by: proposition:canonical\naliases:\n  - proposition:canonical\n",
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


def test_apply_moves_ready_proposition_and_writes_scalar_archive_row(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    original = _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert report["applied"] == ["proposition:duplicate"]
    assert not original.exists()
    archived = tmp_path / derive_archive_path("entities/propositions/duplicate.md")
    assert archived.exists()
    row = load_archive_index(tmp_path).active_by_id["proposition:duplicate"]
    assert row.superseded_by == "proposition:canonical"
    assert row.resynthesized_into == []
    assert row.archived_at == "2026-07-02T12:00:00Z"


def test_apply_canonicalizes_scalar_archived_alias_successor(tmp_path: Path) -> None:
    _seed(tmp_path)
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:archived-canonical",
            kind="proposition",
            title="Archived canonical",
            aliases=["proposition:archived-alias"],
            original_path="entities/propositions/archived-canonical.md",
            archived_at="T1",
        ),
    )
    original = _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:archived-alias\n",
    )

    dry_run = build_superseded_proposition_archive_report(tmp_path)
    candidate = _candidate_by_id(dry_run, "proposition:duplicate")
    assert candidate["status"] == "ready"
    assert candidate["lineage_kind"] == "superseded_by"
    assert candidate["successors"] == ["proposition:archived-canonical"]

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert report["applied"] == ["proposition:duplicate"]
    assert not original.exists()
    row = load_archive_index(tmp_path).active_by_id["proposition:duplicate"]
    assert row.superseded_by == "proposition:archived-canonical"
    knowledge = _knowledge_graph(tmp_path)
    assert (
        _entity_uri("proposition:duplicate"),
        SCI_NS.supersededBy,
        _entity_uri("proposition:archived-canonical"),
    ) in knowledge


def test_apply_postflight_receives_expected_archived_at_when_now_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )
    postflight_rows: list[ArchiveRow] = []

    def capture_postflight(project_root: Path, rows: list[ArchiveRow]) -> None:
        assert project_root == tmp_path.resolve()
        postflight_rows.extend(rows)

    monkeypatch.setattr(proposition_archive, "_postflight", capture_postflight)

    archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert [row.archived_at for row in postflight_rows] == ["2026-07-02T12:00:00Z"]


def test_apply_moves_ready_proposition_and_writes_resynthesis_archive_row(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "negative")
    _proposition(tmp_path, "positive")
    original = _proposition(
        tmp_path,
        "broad",
        status="superseded",
        extra_frontmatter=("resynthesized_into:\n  - proposition:positive\n  - proposition:negative\n"),
    )

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert report["applied"] == ["proposition:broad"]
    assert not original.exists()
    row = load_archive_index(tmp_path).active_by_id["proposition:broad"]
    assert row.superseded_by is None
    assert row.resynthesized_into == ["proposition:negative", "proposition:positive"]


def test_apply_canonicalizes_resynthesis_archived_alias_successor(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "live")
    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:archived-canonical",
            kind="proposition",
            title="Archived canonical",
            same_as=["proposition:archived-alias"],
            original_path="entities/propositions/archived-canonical.md",
            archived_at="T1",
        ),
    )
    original = _proposition(
        tmp_path,
        "broad",
        status="superseded",
        extra_frontmatter=(
            "resynthesized_into:\n"
            "  - proposition:live\n"
            "  - proposition:archived-alias\n"
        ),
    )

    dry_run = build_superseded_proposition_archive_report(tmp_path)
    candidate = _candidate_by_id(dry_run, "proposition:broad")
    assert candidate["status"] == "ready"
    assert candidate["lineage_kind"] == "resynthesized_into"
    assert candidate["successors"] == ["proposition:archived-canonical", "proposition:live"]

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert report["applied"] == ["proposition:broad"]
    assert not original.exists()
    row = load_archive_index(tmp_path).active_by_id["proposition:broad"]
    assert row.superseded_by is None
    assert row.resynthesized_into == ["proposition:archived-canonical", "proposition:live"]
    knowledge = _knowledge_graph(tmp_path)
    broad = _entity_uri("proposition:broad")
    assert set(knowledge.objects(broad, SCI_NS.supersededBy)) == {
        _entity_uri("proposition:archived-canonical"),
        _entity_uri("proposition:live"),
    }


def test_apply_moves_ready_candidates_and_leaves_blocked_candidates_live(tmp_path: Path) -> None:
    _seed(tmp_path)
    _entity(
        tmp_path,
        "entities/papers/Smith2020.md",
        "id: paper:Smith2020\ntype: paper\ntitle: Smith 2020\nstatus: active\n",
    )
    _proposition(tmp_path, "canonical")
    ready = _proposition(
        tmp_path,
        "ready",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )
    blocked = _proposition(
        tmp_path,
        "blocked",
        status="superseded",
        extra_frontmatter=(
            "superseded_by: proposition:canonical\n"
            "source_refs:\n"
            "  - paper:Smith2020\n"
            "  - annotation:entities/papers/Smith2020.source#a-1\n"
        ),
    )
    _paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", promoted_to="proposition:blocked")])

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    assert report["applied"] == ["proposition:ready"]
    assert not ready.exists()
    assert blocked.exists()
    assert set(load_archive_index(tmp_path).active_by_id) == {"proposition:ready"}


def test_apply_row_construction_fails_if_ready_candidate_is_no_longer_superseded(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )
    report = build_superseded_proposition_archive_report(tmp_path)
    assert _candidate_by_id(report, "proposition:duplicate")["status"] == "ready"

    _proposition(
        tmp_path,
        "duplicate",
        status="active",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )

    with pytest.raises(PropositionArchiveError, match="no longer superseded"):
        _rows_for_ready_candidates(tmp_path, report)


def test_apply_row_construction_fails_if_ready_candidate_lineage_changes(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "replacement")
    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )
    report = build_superseded_proposition_archive_report(tmp_path)
    assert _candidate_by_id(report, "proposition:duplicate")["status"] == "ready"

    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:replacement\n",
    )

    with pytest.raises(PropositionArchiveError, match="lineage changed before archive apply"):
        _rows_for_ready_candidates(tmp_path, report)


def test_apply_row_construction_fails_if_ready_candidate_gains_active_sidecar_backlink(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )
    report = build_superseded_proposition_archive_report(tmp_path)
    assert _candidate_by_id(report, "proposition:duplicate")["status"] == "ready"

    _paper_sidecar(tmp_path, "Smith2020", [_ann("a-1", promoted_to="proposition:duplicate")])

    with pytest.raises(PropositionArchiveError, match="live annotation backlink"):
        _rows_for_ready_candidates(tmp_path, report)


def test_apply_row_construction_fails_if_ready_candidate_gains_active_archive_id_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )
    report = build_superseded_proposition_archive_report(tmp_path)
    assert _candidate_by_id(report, "proposition:duplicate")["status"] == "ready"

    append_row(
        archive_index_path(tmp_path),
        ArchiveRow(
            op="archive",
            id="proposition:duplicate",
            original_path="entities/_archive/propositions/duplicate.md",
            archived_at="T1",
        ),
    )

    with pytest.raises(PropositionArchiveError, match="archive id already active: proposition:duplicate"):
        _rows_for_ready_candidates(tmp_path, report)


def test_apply_row_construction_fails_if_ready_candidate_gains_id_alias_collision(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )
    report = build_superseded_proposition_archive_report(tmp_path)
    assert _candidate_by_id(report, "proposition:duplicate")["status"] == "ready"

    _proposition(
        tmp_path,
        "collider",
        extra_frontmatter=("aliases:\n  - proposition:duplicate\n"),
    )

    with pytest.raises(PropositionArchiveError, match="id/alias collision on proposition:duplicate"):
        _rows_for_ready_candidates(tmp_path, report)


def test_postflight_fails_if_active_archive_row_lineage_differs_from_planned_row(tmp_path: Path) -> None:
    _seed(tmp_path)
    original_path = "entities/propositions/duplicate.md"
    planned = ArchiveRow(
        op="archive",
        id="proposition:duplicate",
        kind="proposition",
        status="superseded",
        superseded_by="proposition:canonical",
        original_path=original_path,
        archived_at="T1",
    )
    archived = tmp_path / derive_archive_path(original_path)
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_text("Archived proposition.\n", encoding="utf-8")
    append_row(
        archive_index_path(tmp_path),
        planned.model_copy(update={"superseded_by": "proposition:replacement"}),
    )

    with pytest.raises(PropositionArchiveError, match="proposition:duplicate archive index mismatch: superseded_by"):
        _postflight(tmp_path, [planned])


def test_postflight_fails_if_active_archive_row_original_path_differs_from_planned_row(tmp_path: Path) -> None:
    _seed(tmp_path)
    original_path = "entities/propositions/duplicate.md"
    planned = ArchiveRow(
        op="archive",
        id="proposition:duplicate",
        kind="proposition",
        status="superseded",
        superseded_by="proposition:canonical",
        original_path=original_path,
        archived_at="T1",
    )
    archived = tmp_path / derive_archive_path(original_path)
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_text("Archived proposition.\n", encoding="utf-8")
    append_row(
        archive_index_path(tmp_path),
        planned.model_copy(update={"original_path": "entities/propositions/other.md"}),
    )

    with pytest.raises(PropositionArchiveError, match="proposition:duplicate archive index mismatch: original_path"):
        _postflight(tmp_path, [planned])


@pytest.mark.parametrize(
    ("planned_update", "active_update", "field"),
    [
        ({}, {"title": "Changed title"}, "title"),
        ({}, {"reason": "changed:reason"}, "reason"),
        ({"archived_at": None}, {"archived_at": "T1"}, "archived_at"),
    ],
)
def test_postflight_fails_if_active_archive_row_metadata_differs_from_planned_row(
    tmp_path: Path,
    planned_update: dict[str, str | None],
    active_update: dict[str, str | None],
    field: str,
) -> None:
    _seed(tmp_path)
    original_path = "entities/propositions/duplicate.md"
    planned = ArchiveRow(
        op="archive",
        id="proposition:duplicate",
        kind="proposition",
        title="duplicate",
        status="superseded",
        superseded_by="proposition:canonical",
        original_path=original_path,
        archived_at="T0",
        reason="status:superseded",
    ).model_copy(update=planned_update)
    archived = tmp_path / derive_archive_path(original_path)
    archived.parent.mkdir(parents=True, exist_ok=True)
    archived.write_text("Archived proposition.\n", encoding="utf-8")
    append_row(
        archive_index_path(tmp_path),
        planned.model_copy(update=active_update),
    )

    with pytest.raises(PropositionArchiveError, match=f"proposition:duplicate archive index mismatch: {field}"):
        _postflight(tmp_path, [planned])


def test_apply_is_idempotent_after_success(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(
        tmp_path,
        "duplicate",
        status="superseded",
        extra_frontmatter="superseded_by: proposition:canonical\n",
    )
    archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")

    report = archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:01:00Z")

    assert report["summary"] == {"ready": 0, "blocked": 0, "skipped": 0}
    assert report["applied"] == []
    assert report["skipped"] == []


def test_scalar_lineage_graph_triple_survives_archive_movement(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")

    before = _knowledge_graph(tmp_path)
    archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")
    after = _knowledge_graph(tmp_path)

    triple = (
        _entity_uri("proposition:duplicate"),
        SCI_NS.supersededBy,
        _entity_uri("proposition:canonical"),
    )
    assert triple in before
    assert triple in after
    assert (_entity_uri("proposition:duplicate"), RDF.type, SCI_NS.ArchivedEntity) in after


def test_multi_successor_graph_triples_survive_archive_movement(tmp_path: Path) -> None:
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

    before = _knowledge_graph(tmp_path)
    archive_superseded_propositions(tmp_path, apply=True, now="2026-07-02T12:00:00Z")
    after = _knowledge_graph(tmp_path)

    broad = _entity_uri("proposition:broad")
    expected = {_entity_uri("proposition:negative"), _entity_uri("proposition:positive")}
    assert set(before.objects(broad, SCI_NS.supersededBy)) == expected
    assert set(after.objects(broad, SCI_NS.supersededBy)) == expected
    assert (broad, RDF.type, SCI_NS.ArchivedEntity) in after
