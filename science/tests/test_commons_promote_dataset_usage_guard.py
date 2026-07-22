"""Guard: a promoted paper may only reference commons-canonical datasets.

fb-2026-07-19-005. A commons paper's `dataset_usage` refs must resolve to
commons canonicals, because a commons entity can reference only other commons
canonicals. Promoting a paper whose `dataset_usage` points at a project-local /
reference-only dataset (no commons canonical, not co-promotable) mints a
dangling ref that every consumer of the paper then hard-errors on. Refuse at
promote time.
"""
from __future__ import annotations

from pathlib import Path

from science_tool.commons.promote import _uncopromotable_dataset_usage_refs


def _commons_with_datasets(tmp_path: Path, *slugs: str) -> Path:
    commons = tmp_path / "commons"
    for slug in slugs:
        d = commons / "datasets" / slug
        d.mkdir(parents=True)
        (d / "entity.md").write_text("---\nid: dataset:" + slug + "\n---\nbody\n", encoding="utf-8")
    (commons / "papers").mkdir(parents=True, exist_ok=True)
    return commons


def test_ref_to_commons_canonical_is_allowed(tmp_path: Path) -> None:
    commons = _commons_with_datasets(tmp_path, "uk-biobank")
    fields = {"dataset_usage": [{"ref": "dataset:uk-biobank", "role": "analyzed"}]}
    assert _uncopromotable_dataset_usage_refs(fields, commons) == []


def test_ref_to_non_canonical_dataset_is_flagged(tmp_path: Path) -> None:
    commons = _commons_with_datasets(tmp_path)  # empty commons
    fields = {"dataset_usage": [{"ref": "dataset:websle-paediatric-sle", "role": "analyzed"}]}
    assert _uncopromotable_dataset_usage_refs(fields, commons) == ["dataset:websle-paediatric-sle"]


def test_mixed_refs_flags_only_the_uncopromotable(tmp_path: Path) -> None:
    commons = _commons_with_datasets(tmp_path, "uk-biobank")
    fields = {
        "dataset_usage": [
            {"ref": "dataset:uk-biobank", "role": "analyzed"},
            {"ref": "dataset:nih-influenza-vaccination-cohort", "role": "analyzed"},
        ]
    }
    assert _uncopromotable_dataset_usage_refs(fields, commons) == [
        "dataset:nih-influenza-vaccination-cohort"
    ]


def test_no_dataset_usage_is_clean(tmp_path: Path) -> None:
    commons = _commons_with_datasets(tmp_path)
    assert _uncopromotable_dataset_usage_refs({}, commons) == []
    assert _uncopromotable_dataset_usage_refs({"dataset_usage": []}, commons) == []


def test_result_is_deduped_and_sorted(tmp_path: Path) -> None:
    commons = _commons_with_datasets(tmp_path)
    fields = {
        "dataset_usage": [
            {"ref": "dataset:zeta", "role": "analyzed"},
            {"ref": "dataset:alpha", "role": "cited"},
            {"ref": "dataset:zeta", "role": "set_definition_source"},
        ]
    }
    assert _uncopromotable_dataset_usage_refs(fields, commons) == ["dataset:alpha", "dataset:zeta"]
