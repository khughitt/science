from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.catalog import CatalogError, CatalogSource, CommonsCatalog, load_commons_catalog


def test_load_commons_catalog_accepts_reserved_source_types(tmp_path: Path) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text(
        "catalog_version: 1\n"
        "sources:\n"
        "  local:\n"
        "    type: path\n"
        "    uri: ~/d/science-commons\n"
        "  bio:\n"
        "    type: git\n"
        "    uri: https://github.com/org/science-bio-commons.git\n"
        "  github-main:\n"
        "    type: github\n"
        "    repo: org/science-bio-commons\n"
        "  dbsnp:\n"
        "    type: zenodo\n"
        "    doi: 10.5281/zenodo.12345\n",
        encoding="utf-8",
    )

    catalog = load_commons_catalog(path)

    assert catalog == CommonsCatalog(
        catalog_version=1,
        sources={
            "local": CatalogSource(type="path", uri="~/d/science-commons", repo=None, doi=None),
            "bio": CatalogSource(type="git", uri="https://github.com/org/science-bio-commons.git", repo=None, doi=None),
            "github-main": CatalogSource(type="github", uri=None, repo="org/science-bio-commons", doi=None),
            "dbsnp": CatalogSource(type="zenodo", uri=None, repo=None, doi="10.5281/zenodo.12345"),
        },
    )


def test_load_commons_catalog_rejects_unknown_source_type(tmp_path: Path) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text(
        "catalog_version: 1\nsources:\n  bad:\n    type: ftp\n    uri: ftp://example.org\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="unsupported source type"):
        load_commons_catalog(path)


def test_load_commons_catalog_rejects_malformed_yaml(tmp_path: Path) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text("sources: [", encoding="utf-8")

    with pytest.raises(CatalogError, match="malformed YAML"):
        load_commons_catalog(path)


def test_load_commons_catalog_rejects_duplicate_top_level_keys(tmp_path: Path) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text(
        "catalog_version: 1\n"
        "sources: {}\n"
        "sources:\n"
        "  local:\n"
        "    type: path\n"
        "    uri: ~/d/science-commons\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="duplicate key"):
        load_commons_catalog(path)


@pytest.mark.parametrize("field", ["type", "uri"])
def test_load_commons_catalog_rejects_duplicate_source_keys(tmp_path: Path, field: str) -> None:
    path = tmp_path / "commons.yaml"
    duplicate_line = "    type: git\n" if field == "type" else "    uri: ~/d/science-commons-copy\n"
    path.write_text(
        "catalog_version: 1\n"
        "sources:\n"
        "  local:\n"
        "    type: path\n"
        "    uri: ~/d/science-commons\n"
        f"{duplicate_line}",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="duplicate key"):
        load_commons_catalog(path)


@pytest.mark.parametrize("catalog_version", ["true", "1.0", '"1"', "2"])
def test_load_commons_catalog_rejects_invalid_catalog_version_values(
    tmp_path: Path, catalog_version: str
) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text(
        f"catalog_version: {catalog_version}\n"
        "sources:\n"
        "  local:\n"
        "    type: path\n"
        "    uri: ~/d/science-commons\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match="catalog_version"):
        load_commons_catalog(path)


@pytest.mark.parametrize(
    ("source_type", "field"),
    [
        ("path", "uri"),
        ("git", "uri"),
        ("github", "repo"),
        ("zenodo", "doi"),
    ],
)
def test_load_commons_catalog_rejects_missing_required_source_fields(
    tmp_path: Path, source_type: str, field: str
) -> None:
    path = tmp_path / "commons.yaml"
    path.write_text(
        "catalog_version: 1\n"
        "sources:\n"
        "  bad:\n"
        f"    type: {source_type}\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogError, match=f"{source_type} source 'bad' requires {field!r}"):
        load_commons_catalog(path)


def test_load_commons_catalog_missing_file_returns_empty_catalog(tmp_path: Path) -> None:
    assert load_commons_catalog(tmp_path / "commons.yaml") == CommonsCatalog(catalog_version=1, sources={})
