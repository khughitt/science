from __future__ import annotations

from pathlib import Path

import pydantic
import pytest

from science_model.frontmatter import parse_entity_file

_DATASET_MD = """\
---
id: "dataset:demo"
kind: "dataset"
title: "Demo dataset"
status: "active"
origin: "external"
tier: "use-now"
license: "CC-BY-4.0"
update_cadence: "static"
ontology_terms: []
created: "2026-05-30"
updated: "2026-05-30"
---

# Demo dataset
"""


def test_license_survives_markdown_parse(tmp_path: Path) -> None:
    path = tmp_path / "demo.md"
    path.write_text(_DATASET_MD, encoding="utf-8")

    entity = parse_entity_file(path, project_slug="demo")

    assert entity is not None
    # parse_entity_file returns a plain Entity for datasets; the field must live
    # on Entity (not DatasetEntity) so it would be dropped by extra="ignore".
    assert entity.license == "CC-BY-4.0"


def test_license_defaults_empty_when_absent(tmp_path: Path) -> None:
    path = tmp_path / "nolic.md"
    path.write_text(_DATASET_MD.replace('license: "CC-BY-4.0"\n', ""), encoding="utf-8")

    entity = parse_entity_file(path, project_slug="demo")

    assert entity is not None
    assert entity.license == ""


def test_non_string_license_is_a_typed_load_error(tmp_path: Path) -> None:
    # Two-surface contract: the typed model field `license: str` rejects a
    # non-string value on the load path (consistent with source_class/tier and
    # every other typed string field). load_project_sources catches this
    # per-entity (sources.py ValidationError handler) — it is NOT a whole-run
    # crash, and the raw-frontmatter CHECK still emits dataset.license-unrecognized
    # for the same input (see tests/validate/test_checks_dataset_metadata.py).
    path = tmp_path / "bad.md"
    path.write_text(_DATASET_MD.replace('license: "CC-BY-4.0"', "license: 123"), encoding="utf-8")

    with pytest.raises(pydantic.ValidationError):
        parse_entity_file(path, project_slug="demo")
