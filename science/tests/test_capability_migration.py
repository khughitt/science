"""Transactional capability migrator (gen-2 -> gen-3): journal, pin-last, resume.

The migrator's ONLY job is to rewrite `provided_capabilities`/`required_capabilities`
from the legacy value-keyed shape to `{data_product, qualifiers}` via a crosswalk, then
flip the project's `entity_schema_version` pin from 2 to 3 -- and to do it transactionally,
so a crash mid-write is RESUMED, never re-planned. Every planned post-image is validated
against the composed gen-3 dataset profile before a byte is written; any unmapped or refused
capability shape aborts the whole pass with nothing written.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from science_model.data_products import build_catalog
from science_model.frontmatter import render_frontmatter

from science_tool.datasets import capability_migration
from science_tool.datasets.capability_migration import MigrationRefused, migrate, resume

_BASE_DATASET: dict[str, object] = {
    "schema_profile": "science-entity-base/1.0+dataset/2.0",
    "kind": "dataset",
    "title": "Demo dataset",
    "version": "1.0.0",
    "created": "2026-07-11",
    "updated": "2026-07-11",
    "origin": "external",
    "tier": "use-now",
    "dataset_class": "pointer",
    "access": {"level": "public", "verified": True},
}


def _dataset_fm(name: str, provided: list[dict]) -> dict:
    fm = {"id": f"dataset:{name}", **_BASE_DATASET, "provided_capabilities": provided}
    # keep `id` first, then the base block, then the field under migration.
    return fm


def _project(tmp_path: Path, datasets: list[tuple[str, list[dict]]], *, generation: int = 2) -> Path:
    root = tmp_path / "proj"
    (root / "entities" / "datasets").mkdir(parents=True)
    (root / "science.yaml").write_text(f"name: p\nentity_schema_version: {generation}\n")
    for name, provided in datasets:
        (root / "entities" / "datasets" / f"{name}.md").write_text(
            render_frontmatter(_dataset_fm(name, provided), "body\n")
        )
    return root


def _crosswalk(tmp_path: Path) -> Path:
    p = tmp_path / "cw.yaml"
    p.write_text(
        'schema_version: "1"\nmappings:\n'
        "  - match: {assay: gene-expression, modality: microarray}\n"
        "    data_product: data-product:gene-expression-microarray\n"
        "  - match: {case_definition: who-lc}\n"
        "    out_of_scope: {disposition: drop, rationale: epi facet}\n"
    )
    return p


@pytest.fixture(autouse=True)
def _patch_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = build_catalog(
        {
            "schema_version": "1",
            "terms": [
                {
                    "id": "data-product:gene-expression-microarray",
                    "label": "Gene expression (microarray)",
                    "assay": "gene-expression",
                }
            ],
        }
    )
    monkeypatch.setattr(capability_migration, "load_catalog", lambda: catalog)


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path, [("aa", [{"assay": "gene-expression", "modality": "microarray"}])])
    before = (root / "entities/datasets/aa.md").read_text()

    planned = migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=False)

    assert planned == [root / "entities/datasets/aa.md"]
    assert (root / "entities/datasets/aa.md").read_text() == before
    assert "entity_schema_version: 2" in (root / "science.yaml").read_text()
    assert not (root / ".science/capability-migration.journal").exists()


def test_apply_rewrites_and_pins_last(tmp_path: Path) -> None:
    root = _project(tmp_path, [("aa", [{"assay": "gene-expression", "modality": "microarray"}])])

    migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=True)

    fm, _ = _read(root / "entities/datasets/aa.md")
    assert fm["provided_capabilities"] == [
        {"data_product": "data-product:gene-expression-microarray", "qualifiers": {}}
    ]
    assert "entity_schema_version: 3" in (root / "science.yaml").read_text()
    assert not (root / ".science/capability-migration.journal").exists()


def test_dropped_entry_is_removed(tmp_path: Path) -> None:
    root = _project(
        tmp_path,
        [
            (
                "aa",
                [
                    {"assay": "gene-expression", "modality": "microarray"},
                    {"case_definition": "who-lc"},
                ],
            )
        ],
    )

    migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=True)

    fm, _ = _read(root / "entities/datasets/aa.md")
    assert fm["provided_capabilities"] == [
        {"data_product": "data-product:gene-expression-microarray", "qualifiers": {}}
    ]


def test_unmapped_shape_aborts_writing_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path, [("aa", [{"assay": "made-up"}])])
    before = (root / "entities/datasets/aa.md").read_text()

    with pytest.raises(MigrationRefused):
        migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=True)

    assert (root / "entities/datasets/aa.md").read_text() == before
    assert "entity_schema_version: 2" in (root / "science.yaml").read_text()
    assert not (root / ".science/capability-migration.journal").exists()


def test_entity_without_capabilities_is_skipped(tmp_path: Path) -> None:
    root = _project(tmp_path, [("aa", [{"assay": "gene-expression", "modality": "microarray"}])])
    # a second dataset that authors NO capability field: not planned, untouched.
    plain = dict(_BASE_DATASET)
    plain_fm = {"id": "dataset:bb", **plain}
    (root / "entities/datasets/bb.md").write_text(render_frontmatter(plain_fm, "body\n"))
    before_bb = (root / "entities/datasets/bb.md").read_text()

    planned = migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=False)

    assert planned == [root / "entities/datasets/aa.md"]
    assert (root / "entities/datasets/bb.md").read_text() == before_bb


def test_pre_existing_journal_blocks_replanning(tmp_path: Path) -> None:
    root = _project(tmp_path, [("aa", [{"assay": "gene-expression", "modality": "microarray"}])])
    journal = root / ".science/capability-migration.journal"
    journal.parent.mkdir(parents=True)
    journal.write_text(json.dumps({"entries": []}) + "\n")

    with pytest.raises(MigrationRefused, match="--resume"):
        migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=True)


def test_resume_writes_preimage_and_pins(tmp_path: Path) -> None:
    root = _project(tmp_path, [("aa", [{"assay": "gene-expression", "modality": "microarray"}])])
    path = root / "entities/datasets/aa.md"
    before = path.read_bytes()
    after_text = render_frontmatter(
        _dataset_fm("aa", [{"data_product": "data-product:gene-expression-microarray", "qualifiers": {}}]),
        "body\n",
    )
    journal = root / ".science/capability-migration.journal"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "path": "entities/datasets/aa.md",
                        "before_sha256": hashlib.sha256(before).hexdigest(),
                        "after": after_text,
                    }
                ]
            }
        )
        + "\n"
    )

    resume(root)

    assert path.read_text() == after_text
    assert "entity_schema_version: 3" in (root / "science.yaml").read_text()
    assert not journal.exists()


def test_resume_refuses_when_file_neither_pre_nor_post(tmp_path: Path) -> None:
    root = _project(tmp_path, [("aa", [{"assay": "gene-expression", "modality": "microarray"}])])
    path = root / "entities/datasets/aa.md"
    journal = root / ".science/capability-migration.journal"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "path": "entities/datasets/aa.md",
                        "before_sha256": hashlib.sha256(b"some other content").hexdigest(),
                        "after": "irrelevant",
                    }
                ]
            }
        )
        + "\n"
    )
    before = path.read_text()

    with pytest.raises(MigrationRefused, match="neither"):
        resume(root)

    assert path.read_text() == before
    assert "entity_schema_version: 2" in (root / "science.yaml").read_text()
    assert journal.exists()  # kept for a real recovery


def test_question_with_no_composed_profile_migrates_without_crashing(tmp_path: Path) -> None:
    # `question` carries `required_capabilities` (the q/h side of the capability system) but has
    # no entry in the gen-3 generation matrix, so `profile_for` raises `ProfileParseError` -- the
    # migrator must validate the rewritten capability fields directly instead of full-entity.
    root = tmp_path / "proj"
    (root / "entities" / "questions").mkdir(parents=True)
    (root / "science.yaml").write_text("name: p\nentity_schema_version: 2\n")
    question_fm = {
        "id": "question:0001",
        "kind": "question",
        "required_capabilities": [{"assay": "gene-expression", "modality": "microarray"}],
    }
    (root / "entities/questions/q.md").write_text(render_frontmatter(question_fm, "body\n"))

    migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=True)

    fm, _ = _read(root / "entities/questions/q.md")
    assert fm["required_capabilities"] == [
        {"data_product": "data-product:gene-expression-microarray", "qualifiers": {}}
    ]
    assert "entity_schema_version: 3" in (root / "science.yaml").read_text()


def _read(path: Path) -> tuple[dict, str]:
    from science_model.frontmatter import split_frontmatter

    return split_frontmatter(path.read_text(encoding="utf-8"))
