from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_model.entity_schema.validator import EntityValidator

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "entity_schema"


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: no frontmatter"
    _, raw, *_ = text.split("---\n", 2)
    return yaml.safe_load(raw)


@pytest.mark.parametrize(
    "relpath",
    [
        "paper_Adams2025.md",
        "topic_single-cell-foundation-models.md",
        "theme_homology-aware-evaluation.md",
        "dataset_cath-domains/entity.md",
    ],
)
def test_fixture_validates(relpath: str) -> None:
    entity = _read_frontmatter(FIXTURE_DIR / relpath)
    EntityValidator().validate(entity)


def test_dataset_fixture_datapackage_parses() -> None:
    text = (FIXTURE_DIR / "dataset_cath-domains" / "datapackage.yaml").read_text(encoding="utf-8")
    dp = yaml.safe_load(text)
    assert dp["name"] == "cath-domains"
    assert len(dp["resources"]) == 1
    assert dp["resources"][0]["hash"].startswith("sha256:")
    assert dp["resources"][0]["bytes"] > 0
