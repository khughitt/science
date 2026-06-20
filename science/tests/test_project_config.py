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
    assert cfg.peers == []


def test_explicit_id_role_peers(tmp_path: Path) -> None:
    yaml_text = """
name: cbioportal
id: cbioportal
role: data-source
profile: research
research_question: "..."
peers:
  - id: meta
    path: ~/d/cancer/meta
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    cfg = load_project_config(tmp_path)
    assert cfg.role == ProjectRole.DATA_SOURCE
    assert cfg.peers[0].id == "meta"
    assert cfg.peers[0].path == "~/d/cancer/meta"


def test_meta_with_peers_manifest(tmp_path: Path) -> None:
    yaml_text = """
name: meta
id: meta
role: meta
profile: research
research_question: "Umbrella: cancer + pre-cancer."
peers:
  - id: cbioportal
    path: ~/d/cancer/data-sources/cbioportal
  - id: multiple-myeloma
    path: ~/d/cancer/cancer-types/multiple-myeloma
"""
    (tmp_path / "science.yaml").write_text(yaml_text)
    cfg = load_project_config(tmp_path)
    assert cfg.role == ProjectRole.META
    assert len(cfg.peers) == 2
    assert cfg.peers[0].id == "cbioportal"
    assert cfg.peers[0].path == "~/d/cancer/data-sources/cbioportal"


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


def test_project_config_accepts_peers(tmp_path: Path) -> None:
    """`peers:` is a list of {id, path}; loaded as PeerEntry objects."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: mm30
    path: ~/d/cancer/mm30
  - id: lit-explore
    path: ../../r/lit-explore
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert len(cfg.peers) == 2
    assert cfg.peers[0].id == "mm30"
    assert cfg.peers[0].path == "~/d/cancer/mm30"
    assert cfg.peers[1].id == "lit-explore"
    assert cfg.peers[1].path == "../../r/lit-explore"


def test_project_config_peers_default_empty(tmp_path: Path) -> None:
    """A config without peers: gets an empty list."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert cfg.peers == []


def test_peer_entry_accepts_unknown_fields_for_forward_compat(tmp_path: Path) -> None:
    """Reserved fields (git, url, etc.) parse without raising; surfaced by validator."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: future-peer
    path: ./somewhere
    git: https://github.com/example/future-peer
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert cfg.peers[0].id == "future-peer"


def test_project_config_rejects_legacy_parent(tmp_path: Path) -> None:
    """parent: is removed; loading a config with it must fail clearly."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
parent: ../meta
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match=r"Use `peers:` instead; the legacy parent/children fields are no longer supported\."):
        load_project_config(project_root)


def test_refs_config_defaults_when_absent(tmp_path):
    """ProjectConfig.refs is None when science.yaml omits the section."""
    from science_tool.project_config import load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n", encoding="utf-8"
    )
    config = load_project_config(tmp_path)
    assert config.refs is None


def test_refs_config_parses_graph_truth_source(tmp_path):
    """`refs.entity_index_source: knowledge_graph` parses to the enum value."""
    from science_tool.project_config import EntityIndexSource, load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n"
        "refs:\n"
        "  entity_index_source: knowledge_graph\n"
        "  scan_roots: [tasks, papers, core]\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.refs is not None
    assert config.refs.entity_index_source == EntityIndexSource.KNOWLEDGE_GRAPH
    assert config.refs.scan_roots == ["tasks", "papers", "core"]


def test_refs_config_default_source_is_frontmatter(tmp_path):
    """`refs:` block with only scan_roots defaults source to frontmatter."""
    from science_tool.project_config import EntityIndexSource, load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n"
        "refs:\n"
        "  scan_roots: [tasks]\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.refs is not None
    assert config.refs.entity_index_source == EntityIndexSource.FRONTMATTER
    assert config.refs.scan_roots == ["tasks"]


def test_refs_config_rejects_unknown_source(tmp_path):
    """`refs.entity_index_source` rejects unknown values via Pydantic validation."""
    from pydantic import ValidationError

    from science_tool.project_config import load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n"
        "refs:\n"
        "  entity_index_source: rdfox\n",
        encoding="utf-8",
    )
    try:
        load_project_config(tmp_path)
    except ValidationError:
        return
    raise AssertionError("Expected ValidationError for unknown source")


def test_project_config_rejects_legacy_children(tmp_path: Path) -> None:
    """children: is removed; loading a config with it must fail clearly."""
    project_root = tmp_path / "meta"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: ../a
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match=r"Use `peers:` instead; the legacy parent/children fields are no longer supported\."):
        load_project_config(project_root)
