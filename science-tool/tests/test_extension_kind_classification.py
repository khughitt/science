"""Verify extension kinds with declared epistemic class flow through
materialize_graph end-to-end (regression for t013 #3)."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from science_model.entities import EntityClass
from science_tool.graph.sources import load_project_sources


def _build_extension_project(tmp_path: Path) -> Path:
    """Project with an extension manifest declaring entity_class: epistemic."""
    root = tmp_path / "demo"
    (root / "knowledge" / "sources" / "ext").mkdir(parents=True)
    (root / "science.yaml").write_text(dedent("""
        name: demo
        knowledge_profiles:
          local: ext
    """).lstrip())
    (root / "knowledge" / "sources" / "ext" / "manifest.yaml").write_text(dedent("""
        name: ext
        imports: []
        strictness: typed-extension
        entity_kinds:
          - name: custom-belief
            canonical_prefix: custom-belief
            layer: layer/extension
            description: Test extension kind classified as epistemic.
            entity_class: epistemic
        relation_kinds: []
    """).lstrip())
    return root


def test_project_sources_registry_classifies_extension_kinds(tmp_path: Path) -> None:
    project_root = _build_extension_project(tmp_path)
    sources = load_project_sources(project_root)
    assert sources.registry.kind_class("custom-belief") == EntityClass.EPISTEMIC


def test_invalid_entity_class_in_manifest_raises(tmp_path: Path) -> None:
    project_root = _build_extension_project(tmp_path)
    manifest_path = project_root / "knowledge" / "sources" / "ext" / "manifest.yaml"
    manifest_path.write_text(manifest_path.read_text().replace("epistemic", "epistemyk"))
    with pytest.raises(ValueError, match="Invalid entity_class"):
        load_project_sources(project_root)
