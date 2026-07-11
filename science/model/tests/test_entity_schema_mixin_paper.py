from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from science_model.entity_schema import (
    MergePolicy,
    parse_profile,
    read_merge_policy,
    read_overlay_merge_policy,
)
from science_model.entity_schema.validator import EntityValidationError, EntityValidator

_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"
_TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "science_model" / "templates"


@pytest.fixture
def base_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+paper/1.0",
        "id": "paper:Adams2025",
        "kind": "paper",
        "title": "An interesting paper",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-05-13",
        "updated": "2026-05-13",
    }


def test_paper_minimal_validates(base_entity: dict) -> None:
    EntityValidator().validate(base_entity)


def test_paper_with_rich_fields_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "bibkey": "Adams2025",
        "authors": ["Adams, A.", "Baker, B."],
        "year": 2025,
        "journal": "Nature Methods",
        "doi": "10.1038/x.y.z",
        "url": "https://example.org/Adams2025",
        "dataset_usage": [{"ref": "dataset:cath-domains", "role": "analyzed"}],
        "key_findings": ["finding 1", "finding 2"],
        "methods_summary": "They used method X.",
        "limitations": ["small sample"],
        "model_or_tool_availability": "available at https://...",
    }
    EntityValidator().validate(entity)


def test_paper_dataset_usage_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "dataset_usage": [
            {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
            {"ref": "dataset:msigdb-c2", "role": "cited"},
        ]
    }
    EntityValidator().validate(entity)


def test_paper_dataset_usage_bad_role_rejected(base_entity: dict) -> None:
    entity = base_entity | {"dataset_usage": [{"ref": "dataset:x", "role": "consulted"}]}
    with pytest.raises(EntityValidationError, match="dataset_usage"):
        EntityValidator().validate(entity)


def test_paper_id_lowercase_slug_rejected(base_entity: dict) -> None:
    entity = base_entity | {"id": "paper:adams-2025"}  # kebab rejected for papers
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_paper_id_bibkey_accepted(base_entity: dict) -> None:
    entity = base_entity | {"id": "paper:BarrioHernandez2023"}
    EntityValidator().validate(entity)


def test_paper_year_rejects_non_integer(base_entity: dict) -> None:
    entity = base_entity | {"year": "2025"}
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_mixin_paper_2_0_schema_loads():
    raw = (_SCHEMAS / "mixin-paper-2.0.json").read_text(encoding="utf-8")
    schema = json.loads(raw)
    assert schema["$id"].endswith("mixin-paper-2.0.json")
    assert "venue" in schema["properties"]
    assert "journal" not in schema["properties"]
    assert "datasets" not in schema["properties"]


def test_paper_template_fields_are_all_routable():
    """Every field the shipped paper template emits must be declared by the paper
    profile or the overlay schema.

    `science commons promote paper` splits a paper's frontmatter into canonical
    fields (the profile's merge policy) and a project overlay, and the overlay
    schema is closed (`additionalProperties: false`). A template field in neither
    set therefore lands in the overlay and fails validation, making every paper
    written from the template unpromotable.
    """
    template = _TEMPLATES / "paper.md"
    frontmatter = yaml.safe_load(template.read_text(encoding="utf-8").split("---")[1])
    emitted = set(frontmatter) - {"_template"}

    routable = set(read_merge_policy(parse_profile("science-entity-base/1.0+paper/2.0")))
    routable |= set(read_overlay_merge_policy())

    assert emitted <= routable, f"paper template emits unroutable fields: {sorted(emitted - routable)}"


def test_mixin_paper_2_0_declares_paper_kind_canonical():
    """paper_kind (review / survey / synthesis / ...) describes the document itself,
    so it is canonical -- the same in every project that cites the paper -- rather
    than a per-project overlay field."""
    profile = parse_profile("science-entity-base/1.0+paper/2.0")
    assert read_merge_policy(profile)["paper_kind"] is MergePolicy.REPLACE
    assert "paper_kind" not in read_overlay_merge_policy()


def test_mixin_paper_2_0_bibkey_regex_permits_hyphens():
    raw = (_SCHEMAS / "mixin-paper-2.0.json").read_text(encoding="utf-8")
    schema = json.loads(raw)
    pattern = schema["properties"]["bibkey"]["pattern"]
    assert re.match(pattern, "categorical-composition-trio-2023-2025")
    assert re.match(pattern, "Adams2025")
    assert not re.match(pattern, "1leading-digit")


def test_mixin_paper_2_0_canonical_body_sections_annotation():
    raw = (_SCHEMAS / "mixin-paper-2.0.json").read_text(encoding="utf-8")
    schema = json.loads(raw)
    sections = schema["x-canonical-body-sections"]
    assert "Key Findings" in sections
    assert "Methods Summary" in sections
    assert "Limitations" in sections


def test_base_schema_declares_dataset_usage_once() -> None:
    raw = (_SCHEMAS / "science-entity-base-1.0.json").read_text(encoding="utf-8")
    base_schema = json.loads(raw)
    paper_raw = (_SCHEMAS / "mixin-paper-2.0.json").read_text(encoding="utf-8")
    dataset_raw = (_SCHEMAS / "mixin-dataset-1.0.json").read_text(encoding="utf-8")
    paper_schema = json.loads(paper_raw)
    dataset_schema = json.loads(dataset_raw)

    assert "dataset_usage" in base_schema["properties"]
    assert "dataset_usage" not in paper_schema["properties"]
    assert "dataset_usage" not in dataset_schema["properties"]


def test_mixin_paper_2_0_merge_policy_overrides_base_for_created_updated_status():
    profile = parse_profile("science-entity-base/1.0+paper/2.0")
    policy = read_merge_policy(profile)
    assert policy["created"] == MergePolicy.PROJECT_ONLY
    assert policy["updated"] == MergePolicy.PROJECT_ONLY
    assert policy["status"] == MergePolicy.PROJECT_ONLY
    # Base contributes these; mixin does NOT override:
    assert policy["tags"] == MergePolicy.APPEND
    assert policy["ontology_terms"] == MergePolicy.APPEND
    assert policy["dataset_usage"] == MergePolicy.APPEND
    # Paper-specific canonical fields default to REPLACE:
    assert policy["title"] == MergePolicy.REPLACE
    assert policy["authors"] == MergePolicy.REPLACE
    assert policy["year"] == MergePolicy.REPLACE
    assert "datasets" not in policy
