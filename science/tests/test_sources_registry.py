"""Registry-builder parity and project-local curation-scope threading."""

from science_model.identity import CurationScope
from science_tool.graph.sources import load_project_sources, registry_for_project


def test_registry_for_project_matches_load_project_sources(tmp_project):
    """The lightweight builder yields the same kind-to-scope map as the full loader."""
    full = load_project_sources(tmp_project).registry
    light = registry_for_project(tmp_project)
    kinds = sorted(full.all_kind_classes())
    assert kinds == sorted(light.all_kind_classes())
    for kind in kinds:
        assert full.curation_scope_for_kind(kind) is light.curation_scope_for_kind(kind), kind


def test_local_extension_kind_defaults_correspondence(tmp_project_with_design_kind):
    """An extension kind with no scope declaration defaults to correspondence."""
    registry = registry_for_project(tmp_project_with_design_kind)
    assert registry.curation_scope_for_kind("design") is CurationScope.CORRESPONDENCE


def test_local_manifest_declared_scope_wins(tmp_project_with_scoped_kind):
    """A local manifest's explicit none scope is authoritative."""
    registry = registry_for_project(tmp_project_with_scoped_kind)
    assert registry.curation_scope_for_kind("logbook") is CurationScope.NONE
