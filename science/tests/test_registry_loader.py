"""Registry YAML loader: parses, schema-validates, surfaces errors with paths."""

from pathlib import Path

import pytest

from science_tool.project_artifacts.loader import RegistryLoadError, load_registry


def test_empty_registry_loads(tmp_path: Path) -> None:
    p = tmp_path / "registry.yaml"
    p.write_text("artifacts: []\n", encoding="utf-8")
    reg = load_registry(p)
    assert reg.artifacts == []


def test_invalid_yaml_surfaces_clear_error(tmp_path: Path) -> None:
    p = tmp_path / "registry.yaml"
    p.write_text("artifacts: [: this is not valid yaml :\n", encoding="utf-8")
    with pytest.raises(RegistryLoadError, match="YAML parse error"):
        load_registry(p)


def test_schema_violation_includes_yaml_path(tmp_path: Path) -> None:
    p = tmp_path / "registry.yaml"
    p.write_text(
        "artifacts:\n"
        "  - name: x\n"
        "    source: data/x\n"
        "    install_target: x\n"
        "    description: d\n"
        "    content_type: text\n"
        "    mode: '0755'\n"
        "    consumer: direct_execute\n"
        "    header_protocol: {kind: shebang_comment, comment_prefix: '#'}\n"
        "    extension_protocol: {kind: merged_sidecar, sidecar_path: x.local}\n"
        "    mutation_policy: {}\n"
        "    version: '2026.04.26'\n"
        "    current_hash: " + "a" * 64 + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RegistryLoadError, match="merged_sidecar.*direct_execute"):
        load_registry(p)


def test_package_default_registry_is_loadable() -> None:
    """The packaged registry.yaml must always parse cleanly."""
    from science_tool.project_artifacts import default_registry

    reg = default_registry()
    # may be empty or populated, but it parses
    assert reg is not None
