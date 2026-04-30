from pathlib import Path

import pytest
from pydantic import ValidationError

from science_tool.project_config import (
    ProjectRole,
    load_project_config,
)


def test_loads_minimal_existing_yaml(tmp_path: Path) -> None:
    """An existing science.yaml without new fields must still load."""
    project_root = tmp_path / "cbioportal"
    project_root.mkdir()
    yaml_text = """
name: cbioportal
created: "2025-02-21"
profile: research
research_question: "What is the structure of somatic mutations across cancers?"
"""
    (project_root / "science.yaml").write_text(yaml_text)

    cfg = load_project_config(project_root)
    assert cfg.name == "cbioportal"
    assert cfg.id == "cbioportal"
    assert cfg.role == "standalone"
    assert cfg.parent is None
    assert cfg.children == []


def test_explicit_id_role_parent(tmp_path: Path) -> None:
    yaml_text = """
name: cbioportal
id: cbioportal
role: data-source
parent: ~/d/cancer/meta
profile: research
research_question: "..."
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    cfg = load_project_config(tmp_path)
    assert cfg.role == ProjectRole.DATA_SOURCE
    assert cfg.parent == "~/d/cancer/meta"


def test_meta_with_children_manifest(tmp_path: Path) -> None:
    yaml_text = """
name: meta
id: meta
role: meta
profile: research
research_question: "Umbrella: cancer + pre-cancer."
children:
  - id: cbioportal
    path: ~/d/cancer/data-sources/cbioportal
    role: data-source
  - id: multiple-myeloma
    path: ~/d/cancer/cancer-types/multiple-myeloma
    role: cancer-type
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    cfg = load_project_config(tmp_path)
    assert cfg.role == ProjectRole.META
    assert len(cfg.children) == 2
    assert cfg.children[0].id == "cbioportal"
    assert cfg.children[0].role == ProjectRole.DATA_SOURCE


def test_role_string_extensible(tmp_path: Path) -> None:
    """Unknown roles are accepted but normalized as raw strings (vocabulary is extensible)."""
    yaml_text = """
name: foo
id: foo
role: model-system
profile: research
research_question: "..."
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    cfg = load_project_config(tmp_path)
    assert cfg.role == "model-system"


def test_children_only_on_meta(tmp_path: Path) -> None:
    """Non-meta projects must not declare children."""
    yaml_text = """
name: foo
id: foo
role: data-source
profile: research
research_question: "..."
children:
  - id: bar
    path: ~/d/bar
    role: data-source
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    with pytest.raises(ValidationError, match="children.*only.*meta"):
        load_project_config(tmp_path)


def test_id_uniqueness_in_children(tmp_path: Path) -> None:
    yaml_text = """
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: cbioportal
    path: ~/d/x
    role: data-source
  - id: cbioportal
    path: ~/d/y
    role: data-source
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    with pytest.raises(ValidationError, match="duplicate.*id"):
        load_project_config(tmp_path)
