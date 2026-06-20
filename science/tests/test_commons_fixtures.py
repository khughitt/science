"""Sanity checks: commons test fixtures match the labels on their directories."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from science_model.entity_schema import EntityValidationError, EntityValidator

FIXTURES = Path(__file__).parent / "fixtures" / "commons"
VALID = FIXTURES / "valid"
INVALID = FIXTURES / "invalid"


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} missing frontmatter")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_fixtures_dir_exists() -> None:
    assert VALID.is_dir()
    assert INVALID.is_dir()


@pytest.mark.parametrize(
    "rel_path",
    [
        "datasets/cath-domains/entity.md",
        "datasets/rnaseq-example/entity.md",
        "papers/Adams2025.md",
        "topics/single-cell-foundation-models.md",
        "themes/research-hygiene.md",
    ],
)
def test_valid_fixtures_validate(rel_path: str) -> None:
    validator = EntityValidator()
    validator.validate(_frontmatter(VALID / rel_path))


def test_dataset_missing_datapackage_lacks_sibling() -> None:
    entity = INVALID / "dataset-missing-datapackage" / "datasets" / "no-dp" / "entity.md"
    assert entity.is_file()
    assert not (entity.parent / "datapackage.yaml").exists()
    # Frontmatter itself is schema-valid; the failure is filesystem layout.
    EntityValidator().validate(_frontmatter(entity))


def test_paper_bad_bibkey_fails_schema() -> None:
    fm = _frontmatter(INVALID / "paper-bad-bibkey" / "papers" / "badname.md")
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(fm)


def test_topic_bad_profile_fails_schema() -> None:
    fm = _frontmatter(INVALID / "topic-bad-profile" / "topics" / "x.md")
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(fm)
