from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.aggregate_retire import apply_retirement, plan_retirement
from science_tool.graph.aggregate_triage import classify_aggregate_rows
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"
_ENT_REL = "knowledge/sources/local/entities.yaml"


def _write(root: Path, entities: list[dict]) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    src = root / "knowledge" / "sources" / "local"
    src.mkdir(parents=True, exist_ok=True)
    (src / "entities.yaml").write_text(yaml.safe_dump({"entities": entities}), encoding="utf-8")


def _plan_apply(root: Path, **flags):
    sources = load_project_sources(root, include_commons=False, strict_core_schema=False, strict_identity=False)
    plan = plan_retirement(
        root,
        sources,
        classify_aggregate_rows(sources),
        promote_coined=False,
        delete_cruft=False,
        delete_shadow=False,
        **flags,
    )
    return apply_retirement(root, plan, dry_run=False)


def test_external_ref_backed_by_bib_is_dropped(tmp_path: Path) -> None:
    # kind=article -> EXTERNAL_REF bucket; canonical_id canonicalizes article:->paper:.
    _write(tmp_path, [{"canonical_id": "article:Smith2024", "kind": "article", "title": "S"}])
    report = _plan_apply(tmp_path, retire_external_refs=True, bib_keys=frozenset({"Smith2024"}))
    assert "paper:Smith2024" in report.deleted
    assert yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"] == []


def test_external_ref_unbacked_is_rejected_and_retained(tmp_path: Path) -> None:
    _write(tmp_path, [{"canonical_id": "article:Jones2099", "kind": "article", "title": "J"}])
    report = _plan_apply(tmp_path, retire_external_refs=True, bib_keys=frozenset())
    assert ("paper:Jones2099", "missing bibliography authority") in report.rejected
    remaining = yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"]
    assert [r["canonical_id"] for r in remaining] == ["article:Jones2099"]  # untouched


def test_external_ref_untouched_without_flag(tmp_path: Path) -> None:
    _write(tmp_path, [{"canonical_id": "article:Smith2024", "kind": "article", "title": "S"}])
    report = _plan_apply(tmp_path, retire_external_refs=False, bib_keys=frozenset({"Smith2024"}))
    assert "paper:Smith2024" not in report.deleted
    assert len(yaml.safe_load((tmp_path / _ENT_REL).read_text())["entities"]) == 1
