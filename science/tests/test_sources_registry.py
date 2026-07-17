"""Registry-builder parity and profile-aware curation-scope threading."""

from science_model.identity import CurationScope
from science_model.profiles.schema import EntityKind, ProfileManifest
from science_tool.graph.sources import (
    ActiveProfiles,
    build_entity_registry,
    load_project_sources,
    registry_for_project,
)


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


def test_build_registry_threads_explicit_shared_profile_scope() -> None:
    """A shared-profile declaration reaches the registry without a local project load."""
    shared = ProfileManifest(
        name="shared",
        imports=["core"],
        strictness="curated",
        entity_kinds=[
            EntityKind(
                name="shared-claim",
                canonical_prefix="shared-claim",
                layer="layer/shared",
                description="Shared claim record.",
                curation_scope=CurationScope.EPISTEMIC,
            )
        ],
        relation_kinds=[],
    )
    active = ActiveProfiles(
        profile_manifests=[shared],
        local_profile_manifest=None,
        ontology_catalogs=[],
        local_profile="local",
        local_manifest_rel="knowledge/sources/local/manifest.yaml",
    )

    registry, skipped = build_entity_registry(active)

    assert skipped == []
    assert registry.curation_scope_for_kind("shared-claim") is CurationScope.EPISTEMIC
