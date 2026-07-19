from pathlib import Path

from science_tool.skills_lint.sources import load_sources

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCES = REPO_ROOT / "skills" / "sources.yaml"


def test_repo_sources_registry_is_valid() -> None:
    registry = load_sources(SOURCES)
    assert registry.errors == {}
    assert "baygent-skills" in registry.records
    assert registry.records["baygent-skills"].kind == "skill-repo"
