"""Smoke test: package imports, ships data/, registry.yaml is readable."""

from importlib import resources

import science_tool.project_artifacts as pa


def test_package_imports() -> None:
    assert pa is not None


def test_registry_yaml_is_packaged() -> None:
    files = resources.files("science_tool.project_artifacts")
    assert (files / "registry.yaml").is_file()


def test_data_directory_is_packaged() -> None:
    files = resources.files("science_tool.project_artifacts")
    assert (files / "data").is_dir()
