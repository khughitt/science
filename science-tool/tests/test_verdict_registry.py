from pathlib import Path

from science_tool.verdict.registry import has_registry, load_registry

FIXTURE_REG = Path(__file__).parent / "fixtures" / "verdict" / "claim-registry.yaml"


def test_load_registry_parses_fixture() -> None:
    registry = load_registry(FIXTURE_REG)
    assert registry.version == 1
    assert registry.project == "fixture"
    assert len(registry.entries) == 5


def test_registry_resolve_canonical_id_returns_self() -> None:
    registry = load_registry(FIXTURE_REG)
    assert registry.resolve("h1#edge5-ifn-arm") == "h1#edge5-ifn-arm"


def test_registry_resolve_synonym_returns_canonical() -> None:
    registry = load_registry(FIXTURE_REG)
    assert registry.resolve("h1-edge6-ifn-arm") == "h1#edge5-ifn-arm"


def test_registry_resolve_unknown_returns_none() -> None:
    registry = load_registry(FIXTURE_REG)
    assert registry.resolve("bogus#id") is None


def test_has_registry_detects_fixture_project() -> None:
    project_root = FIXTURE_REG.parent
    assert has_registry(project_root, alt_filename="claim-registry.yaml") is True


def test_has_registry_false_when_missing(tmp_path: Path) -> None:
    assert has_registry(tmp_path) is False
