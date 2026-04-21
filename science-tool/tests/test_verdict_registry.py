from pathlib import Path

import pytest

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


def _write_registry(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "claim-registry.yaml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize("content", ["", "[]\n", "42\n"])
def test_load_registry_rejects_malformed_top_level_shape(tmp_path: Path, content: str) -> None:
    path = _write_registry(tmp_path, content)

    with pytest.raises(ValueError, match="Malformed claim registry.*top-level mapping"):
        load_registry(path)


def test_load_registry_rejects_non_list_claims(tmp_path: Path) -> None:
    path = _write_registry(
        tmp_path,
        """
version: 1
project: fixture
claims: h1#edge5-ifn-arm
""",
    )

    with pytest.raises(ValueError, match="Malformed claim registry.*claims.*list"):
        load_registry(path)


@pytest.mark.parametrize("field", ["id", "predicted_direction"])
def test_load_registry_rejects_missing_required_entry_field(tmp_path: Path, field: str) -> None:
    claim = {
        "id": "h1#edge5-ifn-arm",
        "source": "hypothesis:h1",
        "definition": "IFN arm of the edge-5 PRC2 mechanism.",
        "predicted_direction": "[+]",
    }
    del claim[field]
    claim_yaml = "\n".join(f"    {key}: {value!r}" for key, value in claim.items())
    path = _write_registry(
        tmp_path,
        f"""
version: 1
project: fixture
claims:
  -
{claim_yaml}
""",
    )

    with pytest.raises(ValueError, match=f"Malformed claim registry.*{field}.*required"):
        load_registry(path)


def test_load_registry_rejects_scalar_synonyms(tmp_path: Path) -> None:
    path = _write_registry(
        tmp_path,
        """
version: 1
project: fixture
claims:
  - id: h1#edge5-ifn-arm
    source: hypothesis:h1
    definition: IFN arm of the edge-5 PRC2 mechanism.
    predicted_direction: "[+]"
    synonyms: h1-edge6-ifn-arm
""",
    )

    with pytest.raises(ValueError, match="Malformed claim registry.*synonyms.*list of strings"):
        load_registry(path)


@pytest.mark.parametrize("field", ["synonyms", "members", "cited_in"])
def test_load_registry_rejects_non_string_entry_list_values(tmp_path: Path, field: str) -> None:
    path = _write_registry(
        tmp_path,
        f"""
version: 1
project: fixture
claims:
  - id: h1#edge5-ifn-arm
    source: hypothesis:h1
    definition: IFN arm of the edge-5 PRC2 mechanism.
    predicted_direction: "[+]"
    {field}:
      - valid
      - 12
""",
    )

    with pytest.raises(ValueError, match=f"Malformed claim registry.*{field}.*list of strings"):
        load_registry(path)


def test_load_registry_rejects_duplicate_canonical_id(tmp_path: Path) -> None:
    path = _write_registry(
        tmp_path,
        """
version: 1
project: fixture
claims:
  - id: h1#edge5-ifn-arm
    source: hypothesis:h1
    definition: First definition.
    predicted_direction: "[+]"
  - id: h1#edge5-ifn-arm
    source: hypothesis:h1
    definition: Duplicate definition.
    predicted_direction: "[-]"
""",
    )

    with pytest.raises(ValueError, match="Malformed claim registry.*duplicate canonical ID.*h1#edge5-ifn-arm"):
        load_registry(path)
