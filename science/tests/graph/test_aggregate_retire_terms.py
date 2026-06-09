from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import (
    RetirementReport,
    _read_entries,
    _rewrite_aggregate,
    apply_retirement,
    plan_retirement,
)
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_TERMS_REL = "knowledge/sources/local/terms.yaml"
_ENT_REL = "knowledge/sources/local/entities.yaml"


def _write(root: Path, *, terms: list[dict] | None = None, entities: list[dict] | None = None) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    if terms is not None:
        (src / "terms.yaml").write_text(yaml.safe_dump({"terms": terms}), encoding="utf-8")
    if entities is not None:
        (src / "entities.yaml").write_text(yaml.safe_dump({"entities": entities}), encoding="utf-8")


def _run(root: Path, **flags) -> RetirementReport:
    sources = load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)
    plan = plan_retirement(root, sources, classify_aggregate_rows(sources), **flags)
    return apply_retirement(root, plan, dry_run=False)


def test_read_and_rewrite_use_terms_root_key(tmp_path: Path) -> None:
    _write(tmp_path, terms=[{"id": "concept:a", "title": "A"}, {"id": "concept:b", "title": "B"}])
    assert [e["id"] for e in _read_entries(tmp_path, _TERMS_REL)] == ["concept:a", "concept:b"]
    _rewrite_aggregate(tmp_path, _TERMS_REL, {0})  # drop row 0
    data = yaml.safe_load((tmp_path / _TERMS_REL).read_text(encoding="utf-8"))
    assert "terms" in data and "entities" not in data  # root key preserved
    assert [e["id"] for e in data["terms"]] == ["concept:b"]


def test_terms_coined_concept_promotes_with_description_body(tmp_path: Path) -> None:
    _write(
        tmp_path,
        terms=[
            {
                "id": "concept:prc2-complex",
                "title": "PRC2 complex",
                "description": "Polycomb repressive complex 2 as a local semantic placeholder.",
            }
        ],
    )
    report = _run(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.promoted == ("concept:prc2-complex",)
    owner = tmp_path / "entities/concepts/prc2-complex.md"
    assert owner.exists()
    text = owner.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---")[1])
    assert fm["id"] == "concept:prc2-complex"
    assert fm["type"] == "concept"
    assert fm["title"] == "PRC2 complex"
    assert fm["promoted_from"] == _TERMS_REL
    assert "Polycomb repressive complex 2 as a local semantic placeholder." in text
    # Row dropped, terms root preserved.
    data = yaml.safe_load((tmp_path / _TERMS_REL).read_text(encoding="utf-8"))
    assert data == {"terms": []}


def test_promoted_terms_concept_reloads_with_content_preview(tmp_path: Path) -> None:
    _write(
        tmp_path,
        terms=[
            {
                "id": "concept:prc2-complex",
                "title": "PRC2 complex",
                "description": "Polycomb repressive complex 2 placeholder.",
            }
        ],
    )
    _run(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    reloaded = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    ent = next((e for e in reloaded.entities if e.canonical_id == "concept:prc2-complex"), None)
    assert ent is not None, "promoted concept owner did not reload as an entity"
    # Definition survives: promoted to the owner BODY, so content->content_preview fallback applies.
    assert ent.content_preview
    assert "Polycomb repressive complex 2 placeholder." in ent.content_preview


def test_terms_ambiguous_row_is_left_untouched(tmp_path: Path) -> None:
    # A non-self-sourced concept row classifies AMBIGUOUS (the coined branch requires
    # self_sourced); --promote-coined must not promote or delete it.
    _write(
        tmp_path,
        terms=[
            {"id": "concept:coined", "title": "Coined"},  # self-sourced (no source_path) -> COINED
            {"id": "concept:external", "title": "External", "source_path": "doc/something.md"},  # -> AMBIGUOUS
        ],
    )
    report = _run(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert report.promoted == ("concept:coined",)
    assert "concept:external" not in report.promoted
    assert "concept:external" not in report.deleted
    remaining = yaml.safe_load((tmp_path / _TERMS_REL).read_text(encoding="utf-8"))["terms"]
    assert [r["id"] for r in remaining] == ["concept:external"]


def test_mixed_entities_and_terms_each_file_rewritten_once(tmp_path: Path) -> None:
    _write(
        tmp_path,
        entities=[{"canonical_id": "concept:ent", "kind": "concept", "title": "Ent", "source_path": _ENT_REL}],
        terms=[{"id": "concept:trm", "title": "Trm"}],
    )
    report = _run(tmp_path, promote_coined=True, delete_cruft=False, delete_shadow=False)
    assert set(report.promoted) == {"concept:ent", "concept:trm"}
    assert set(report.files_rewritten) == {_ENT_REL, _TERMS_REL}
    assert yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"] == []
    assert yaml.safe_load((tmp_path / _TERMS_REL).read_text())["terms"] == []


def test_duplicate_id_across_files_routes_by_path_line(tmp_path: Path) -> None:
    # Same canonical_id in both files but DIFFERENT buckets: COINED (self-sourced)
    # in entities.yaml vs CRUFT (migration source) in terms.yaml. Correct routing
    # promotes the entities row (owner created) and deletes the terms cruft row.
    #
    # Old id-keyed triage collapses both metas to ONE triage for "concept:dup":
    # rows are sorted by (bucket, id), so the dict's last write wins = CRUFT, and
    # BOTH metas take the delete action under --delete-cruft -> the coined row is
    # destroyed and the owner file is never written. The owner-exists assertion
    # below fails on the old code and passes on the (path, line)-keyed planner,
    # independent of meta iteration order.
    _write(
        tmp_path,
        entities=[{"canonical_id": "concept:dup", "kind": "concept", "title": "Coined", "source_path": _ENT_REL}],
        terms=[{"id": "concept:dup", "title": "Cruft", "source_path": "migration:audit"}],
    )
    report = _run(tmp_path, promote_coined=True, delete_cruft=True, delete_shadow=False)
    assert (tmp_path / "entities/concepts/dup.md").exists()  # entities (coined) row promoted
    assert "concept:dup" in report.promoted
    assert yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"] == []  # coined row removed
    assert yaml.safe_load((tmp_path / _TERMS_REL).read_text())["terms"] == []  # cruft row deleted
