def test_project_sources_defaults_commons_overlay_paths_empty() -> None:
    from science_tool.graph.entity_registry import EntityRegistry
    from science_tool.graph.sources import KnowledgeProfiles, ProjectSources

    sources = ProjectSources(
        project_name="demo",
        project_root="/tmp/demo",
        profiles=KnowledgeProfiles(),
        entities=[],
        registry=EntityRegistry.with_core_types(),
    )
    assert sources.commons_overlay_paths == {}


def test_project_sources_accepts_commons_overlay_paths() -> None:
    from science_tool.graph.entity_registry import EntityRegistry
    from science_tool.graph.sources import KnowledgeProfiles, ProjectSources

    sources = ProjectSources(
        project_name="demo",
        project_root="/tmp/demo",
        profiles=KnowledgeProfiles(),
        entities=[],
        registry=EntityRegistry.with_core_types(),
        commons_overlay_paths={"topic:x": "/abs/overlay.md"},
    )
    assert sources.commons_overlay_paths == {"topic:x": "/abs/overlay.md"}
