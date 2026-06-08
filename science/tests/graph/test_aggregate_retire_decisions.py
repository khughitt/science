"""Phase 3c: decision-kind handling in the retirement executor."""

from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import _promote_target, apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.decision_log import DecisionLogIndex, DecisionSection
from science_tool.graph.sources import AggregateRowMeta, load_project_sources


def _project(tmp_path: Path, rows: list[dict], decisions_md: str | None = None) -> Path:
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n",
        encoding="utf-8",
    )
    src = tmp_path / "knowledge" / "sources" / "local"
    src.mkdir(parents=True)
    # `decision` is a builtin filename-policy kind but is NOT a graph-core kind in
    # 3c (it stays a local registry kind so MM30 keeps loading). Graph loading only
    # emits rows for registered kinds, so the fixture must declare `decision` in a
    # local manifest exactly as MM30 does — otherwise the rows are skipped pre-triage.
    (src / "manifest.yaml").write_text(
        "name: t-local\nimports:\n  - core\nstrictness: typed-extension\n"
        "entity_kinds:\n"
        "  - name: decision\n    canonical_prefix: decision\n    layer: layer/local\n"
        "    description: Project-local design decision.\n"
        "relation_kinds: []\n",
        encoding="utf-8",
    )
    (src / "entities.yaml").write_text(yaml.safe_dump({"entities": rows}), encoding="utf-8")
    if decisions_md is not None:
        (tmp_path / "core").mkdir()
        (tmp_path / "core" / "decisions.md").write_text(decisions_md, encoding="utf-8")
    return tmp_path


def _index(*locals_: str) -> DecisionLogIndex:
    return DecisionLogIndex(
        {
            f"decision:{lid}": DecisionSection(
                f"decision:{lid}", lid, f"Title {lid}", "2026-01-01", "active", f"Body {lid}.\n"
            )
            for lid in locals_
        }
    )


def test_migration_audit_decision_with_index_hit_is_promoted_not_deleted(tmp_path: Path):
    # D10: source_path migration:audit -> triage buckets it CRUFT, but it has a
    # real index section. It MUST be promoted, and delete_cruft must NOT delete it.
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D10", "kind": "decision", "title": "D10", "source_path": "migration:audit"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj,
        sources,
        rows,
        promote_coined=False,
        delete_cruft=True,
        delete_shadow=False,
        promote_decisions=True,
        decision_index=_index("D10"),
    )
    report = apply_retirement(proj, plan, dry_run=False, decision_index=_index("D10"))
    assert "decision:D10" in report.promoted
    assert "decision:D10" not in report.deleted
    owner = proj / "entities" / "decision" / "D10.md"
    assert owner.is_file()
    assert "Body D10." in owner.read_text(encoding="utf-8")


def test_delete_cruft_never_deletes_decision_without_promote(tmp_path: Path):
    # delete_cruft alone (promote_decisions off) must still leave decision rows intact.
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D10", "kind": "decision", "title": "D10", "source_path": "migration:audit"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj,
        sources,
        rows,
        promote_coined=False,
        delete_cruft=True,
        delete_shadow=False,
        promote_decisions=False,
        decision_index=DecisionLogIndex({}),
    )
    report = apply_retirement(proj, plan, dry_run=False, decision_index=DecisionLogIndex({}))
    assert "decision:D10" not in report.deleted
    assert "decision:D10" not in report.promoted
    # The entities.yaml row is retained.
    remaining = yaml.safe_load((proj / "knowledge/sources/local/entities.yaml").read_text())["entities"]
    assert any(r["canonical_id"] == "decision:D10" for r in remaining)


def test_index_miss_decision_is_rejected_and_retained(tmp_path: Path):
    proj = _project(
        tmp_path,
        [
            {
                "canonical_id": "decision:D2-treatment-response-category",
                "kind": "decision",
                "title": "D2 Treatment Response Category",
                "source_path": "migration:audit",
            }
        ],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj,
        sources,
        rows,
        promote_coined=False,
        delete_cruft=True,
        delete_shadow=False,
        promote_decisions=True,
        decision_index=_index("D1"),  # no D2-... section
    )
    report = apply_retirement(proj, plan, dry_run=False, decision_index=_index("D1"))
    assert "decision:D2-treatment-response-category" not in report.promoted
    assert "decision:D2-treatment-response-category" not in report.deleted
    assert any(cid == "decision:D2-treatment-response-category" for cid, _ in report.rejected)


def test_core_decisions_sourced_decision_promotes(tmp_path: Path):
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D1", "kind": "decision", "title": "D1. X", "source_path": "core/decisions.md"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj,
        sources,
        rows,
        promote_coined=False,
        delete_cruft=False,
        delete_shadow=False,
        promote_decisions=True,
        decision_index=_index("D1"),
    )
    report = apply_retirement(proj, plan, dry_run=False, decision_index=_index("D1"))
    assert report.promoted == ("decision:D1",)
    assert (proj / "entities" / "decision" / "D1.md").is_file()


def test_promote_decisions_off_leaves_decision_untouched(tmp_path: Path):
    # 3b parity: with no decision flag, decision rows are neither promoted nor deleted.
    proj = _project(
        tmp_path,
        [{"canonical_id": "decision:D1", "kind": "decision", "title": "D1. X", "source_path": "core/decisions.md"}],
    )
    sources = load_project_sources(proj, include_commons=False, strict_core_schema=False, strict_identity=False)
    rows = classify_aggregate_rows(sources)
    plan = plan_retirement(
        proj,
        sources,
        rows,
        promote_coined=False,
        delete_cruft=False,
        delete_shadow=False,
    )  # new params default off
    report = apply_retirement(proj, plan, dry_run=False)  # decision_index defaults to empty
    assert report.promoted == ()
    assert report.deleted == ()


def _meta(canonical_id: str) -> AggregateRowMeta:
    return AggregateRowMeta(
        path="knowledge/sources/local/entities.yaml",
        line=0,
        canonical_id=canonical_id,
        kind="decision",
        source_path="migration:audit",
    )


def test_promote_target_resolves_verbatim_and_blocks_traversal(tmp_path: Path):
    # Directly exercise the path-safety belt: `_is_safe_slug` is lowercase-only, so
    # the helper must special-case verbatim. D10 resolves; `D..x` is blocked by `..`.
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n",
        encoding="utf-8",
    )
    target, reason = _promote_target(_meta("decision:D10"), tmp_path)
    assert target == "entities/decision/D10.md"
    assert reason is None
    bad_target, bad_reason = _promote_target(_meta("decision:D..x"), tmp_path)
    assert bad_target is None
    assert bad_reason is not None and "unsafe" in bad_reason
