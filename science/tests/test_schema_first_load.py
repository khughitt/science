"""D3 on the load path: the SCHEMA goes first, and the PROJECTION preserves what it admitted.

Three points of the five-point D3 contract, and they are one mechanism:

1. Raw frontmatter is validated against its **composed** JSON Schema **first**.
2. The Pydantic projection is constructed **only after** schema validation passes.
3. The projection **preserves schema-valid extension fields**. Never `extra="ignore"` -- *that is the
   original defect.*

Point 3 without point 1 is `extra="allow"` over an unvalidated corpus: every typo preserved forever.
Point 1 without point 3 is worse, and it is subtle -- it is a MIGRATION THAT DELETES. Task 2 rules
`author_stated_evidence` -> `source_stated_evidence` on 13 evolution files, and that target is
declared only in a PROJECT EXTENSION. Validate the file, admit the key, then drop it at
`model_validate`, and the migration has written a field that reaches nothing. The plan's own words,
one level down: *a rename whose target nobody declared is a delete with better manners.*

☠️ All of it is gated on the AUTHORED PIN. An unmigrated project must load exactly as it did before
D5 -- nothing here may infer a project's schema version from the shape of its files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

if "conftest" in sys.modules and not hasattr(sys.modules["conftest"], "build_entity_graph"):
    del sys.modules["conftest"]
from _fixtures.entity_helpers import seed_project, write_markdown_entity

from science_tool.entity_profiles import load_project_schema_if_pinned
from science_tool.graph.sources import load_project_sources

EXTENSION = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://schemas.science/extension-acme-provenance-1.0.json",
    "type": "object",
    "properties": {"source_stated_evidence": {"type": "string"}},
}


def _project(
    tmp_path: Path, *, pinned: bool, extensions: bool = True, generation: int = 2
) -> Path:
    seed_project(tmp_path)

    config = yaml.safe_load((tmp_path / "science.yaml").read_text(encoding="utf-8"))
    if pinned:
        config["entity_schema_version"] = generation
    if extensions:
        config["entity_extensions"] = {"hypothesis": ["acme.provenance/1.0"]}
        schemas = tmp_path / "schemas"
        schemas.mkdir(parents=True, exist_ok=True)
        (schemas / "extension-acme-provenance-1.0.json").write_text(
            json.dumps(EXTENSION), encoding="utf-8"
        )
    (tmp_path / "science.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return tmp_path


def _hypothesis(tmp_path: Path, **extra: object) -> None:
    frontmatter: dict[str, object] = {
        "id": "hypothesis:0001-a",
        "kind": "hypothesis",
        "title": "H",
        "status": "active",
        "created": "2026-07-11",
        "updated": "2026-07-11",
        "related": [],
        "source_refs": [],
    }
    frontmatter.update(extra)
    write_markdown_entity(tmp_path, "entities/hypotheses/0001-a.md", frontmatter, "Body.")


def _load(project_root: Path):
    sources = load_project_sources(project_root)
    return next(e for e in sources.entities if e.id == "hypothesis:0001-a")


def _dataset(tmp_path: Path, *, generation: int, **extra: object) -> None:
    frontmatter: dict[str, object] = {
        "schema_profile": f"science-entity-base/1.0+dataset/{'3.0' if generation == 3 else '2.0'}",
        "id": "dataset:demo",
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
    frontmatter.update(extra)
    write_markdown_entity(tmp_path, "entities/datasets/demo.md", frontmatter, "Body.")


def _load_dataset(project_root: Path):
    sources = load_project_sources(project_root)
    return next(e for e in sources.entities if e.id == "dataset:demo")


def test_a_project_EXTENSION_field_SURVIVES_the_projection(tmp_path: Path) -> None:
    """D3.3, and the reason the migration's renames are sound.

    `source_stated_evidence` is declared by a PROJECT extension, so it can never be a field on the
    shared model -- declaring it there would make one project's field a Science field for all 22.
    Under `extra="ignore"` it validated on disk and evaporated at `model_validate`. It must not.
    """
    project = _project(tmp_path, pinned=True)
    _hypothesis(project, source_stated_evidence="reported in Fig 3")

    entity = _load(project)

    assert entity.model_extra is not None
    assert entity.model_extra["source_stated_evidence"] == "reported in Fig 3"
    # ...and it survives the round trip OUT, which is the property `extra="ignore"` broke:
    # acceptance and preservation are different, and only the second one is worth anything.
    assert entity.model_dump()["source_stated_evidence"] == "reported in Fig 3"


def test_an_UNDECLARED_key_is_REFUSED_on_a_pinned_project(tmp_path: Path) -> None:
    """The half that makes `extra="allow"` safe.

    Without this, preservation is just a slower drop: the typo is kept, nothing reads it, and the
    author is no better off than when it was silently discarded.
    """
    project = _project(tmp_path, pinned=True)
    _hypothesis(project, source_stated_evidenc="typo, one letter out")

    with pytest.raises(ValueError, match="does not satisfy its schema"):
        _load(project)


def test_a_DELETED_key_is_REFUSED_on_a_pinned_project(tmp_path: Path) -> None:
    # `phase` is `false` in the mixin -- not merely undeclared. A migration leftover fails LOUDLY
    # rather than validating quietly, which is the whole reason the deletes are `false` and not just
    # absent (Task 6).
    project = _project(tmp_path, pinned=True)
    _hypothesis(project, phase="active")

    with pytest.raises(ValueError, match="does not satisfy its schema"):
        _load(project)


def test_an_UNPINNED_project_is_NOT_validated(tmp_path: Path) -> None:
    """☠️ The scope of the whole arc, asserted.

    `default_profile_for_kind` is GLOBAL, so the schema exists for every project the moment it ships.
    What must NOT be global is its ENFORCEMENT: 18 roots migrate one at a time, and a project that
    has not declared `entity_schema_version: 2` still carries the verdict in `status` and the 107
    `phase` keys. Enforcing the schema there would break every project that has not migrated yet --
    on a schedule nobody chose.

    This is also why absence may mean only ONE thing. A project that has declared nothing is
    unmigrated, and that is read off the pin, never off the files.
    """
    project = _project(tmp_path, pinned=False)
    _hypothesis(project, phase="active", status="refuted")  # BOTH illegal under schema 2

    entity = _load(project)  # no schema, no refusal

    assert entity.status == "refuted"  # the OLD meaning, untouched


def test_a_GEN_3_project_ARMS_and_composes_the_hypothesis_2_0_mixin(tmp_path: Path) -> None:
    """The generation matrix on the LOAD path: gen 3 arms schema-first validation AND selects the row.

    `entity_schema_version: 3` is a NEW armed generation. It must both switch validation on (like gen
    2 did) and move `hypothesis` onto its 2.0 mixin -- the two are one decision, carried by the single
    declared number. The extension still composes on top, unchanged.
    """
    project = _project(tmp_path, pinned=True, generation=3)

    schema = load_project_schema_if_pinned(project)
    assert schema is not None  # gen 3 ARMS
    mixin = schema.profile_for("hypothesis").mixin
    assert mixin is not None and mixin.render() == "hypothesis/2.0"

    _hypothesis(project, source_stated_evidence="reported in Fig 3")
    entity = _load(project)
    assert entity.model_extra is not None
    assert entity.model_extra["source_stated_evidence"] == "reported in Fig 3"


def test_a_GEN_2_project_STILL_composes_the_hypothesis_1_0_mixin(tmp_path: Path) -> None:
    """Regression: the baseline generation is byte-identical. Gen 2 still composes hypothesis/1.0."""
    project = _project(tmp_path, pinned=True, generation=2)

    schema = load_project_schema_if_pinned(project)
    assert schema is not None
    mixin = schema.profile_for("hypothesis").mixin
    assert mixin is not None and mixin.render() == "hypothesis/1.0"


def test_hypothesis_migrator_targets_generation_2() -> None:
    """The migrator writes gen-1 -> gen-2 hypotheses. Its target is a DESTINATION, not the armed set:
    it stays 2 even as gen 3 is armed."""
    from science_tool import migrate_hypothesis

    assert migrate_hypothesis._TARGET_GENERATION == 2


def test_the_PACKAGE_default_profile_would_reject_the_extension_field(tmp_path: Path) -> None:
    """Why the profile must be the project-COMPOSED one.

    Same file, same pin -- but the project no longer DECLARES the extension. Now
    `source_stated_evidence` is an unknown key and `unevaluatedProperties: false` refuses it. That is
    correct here, and it is exactly the failure a package-default profile would produce for mm30 and
    evolution on every one of their files: an error blaming the corpus for fields their project
    legitimately declares.
    """
    project = _project(tmp_path, pinned=True, extensions=False)
    _hypothesis(project, source_stated_evidence="reported in Fig 3")

    with pytest.raises(ValueError, match="does not satisfy its schema"):
        _load(project)


def test_gen3_dataset_bad_capability_shape_fails(tmp_path: Path) -> None:
    """Task 6: a gen-3 project runs the dataset-only hook, and dataset/3.0 retypes
    `provided_capabilities` to `{data_product, qualifiers}` objects (Task 3). The legacy
    string-keyed shape from mixin-dataset-2.0 must be REFUSED under gen 3 -- dataset stays out of
    `PROJECT_MIXIN_NAMES` (it is a commons kind), so this is a SEPARATE, generation-gated hook, not
    an addition to that frozenset.
    """
    project = _project(tmp_path, pinned=True, extensions=False, generation=3)
    _dataset(project, generation=3, provided_capabilities=[{"assay": "x"}])

    with pytest.raises(ValueError, match="provided_capabilities"):
        _load_dataset(project)


def test_gen3_loose_dataset_with_valid_capability_loads(tmp_path: Path) -> None:
    """The regression the Task-12 dry-run surfaced: project datasets are LOOSE records (id, kind,
    title, `provided_capabilities`, `dataset_class`, `source_class` -- no `origin`/`tier`/`version`/
    `datapackage`/`schema_profile`), and `dataset` stays out of `PROJECT_MIXIN_NAMES` on purpose: the
    load path never validates them as full commons dataset/3.0 documents. The ONLY gen-3 obligation
    is a well-formed capability SHAPE, so a loose dataset with a valid one must load with no error.
    """
    project = _project(tmp_path, pinned=True, extensions=False, generation=3)
    write_markdown_entity(
        project,
        "entities/datasets/demo.md",
        {
            "id": "dataset:demo",
            "kind": "dataset",
            "title": "Demo dataset",
            "provided_capabilities": [
                {"data_product": "data-product:gene-expression", "qualifiers": {}}
            ],
        },
        "Body.",
    )

    entity = _load_dataset(project)  # no error

    assert entity.model_extra is not None
    assert entity.model_extra["provided_capabilities"] == [
        {"data_product": "data-product:gene-expression", "qualifiers": {}}
    ]


def test_gen2_dataset_capability_shape_untouched(tmp_path: Path) -> None:
    """Regression: under gen 2 the dataset hook does not fire at all (`generation != 3`), so the
    legacy `provided_capabilities` shape loads exactly as it did before Task 6.
    """
    project = _project(tmp_path, pinned=True, extensions=False, generation=2)
    _dataset(project, generation=2, provided_capabilities=[{"assay": "x", "modality": "bulk-rna"}])

    entity = _load_dataset(project)  # no error under gen 2

    assert entity.model_extra is not None
    assert entity.model_extra["provided_capabilities"] == [{"assay": "x", "modality": "bulk-rna"}]
