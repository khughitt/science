from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from science_tool.commons.datapackage import (
    DatasetResource,
    DatasetResourceError,
    ResourceSource,
    read_dataset_resources,
)

_GOOD_HASH = "sha256:" + "a" * 64


def _write(path: Path, doc: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def test_no_resources_key_returns_empty(tmp_path: Path) -> None:
    # an entity-profile datapackage with no resources (e.g. gtex/derived fixtures) -> ()
    dp = _write(tmp_path / "datapackage.yaml", {"profiles": ["science-pkg-entity-1.0"], "id": "dataset:x"})
    assert read_dataset_resources(dp) == ()


def test_resource_without_hash_is_kept_with_none_hash(tmp_path: Path) -> None:
    # geneset member resources legitimately lack a hash -> resource still materializes
    dp = _write(tmp_path / "datapackage.yaml", {"resources": [{"name": "sets", "path": "sets.csv"}]})
    resources = read_dataset_resources(dp)
    assert resources == (DatasetResource(path="sets.csv", name="sets"),)
    assert resources[0].hash is None


def test_full_resource_fields_are_parsed(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        {
            "resources": [
                {
                    "name": "counts",
                    "path": "counts.parquet",
                    "hash": _GOOD_HASH,
                    "bytes": 12345678,
                    "format": "parquet",
                    "source": {"type": "url", "ref": "https://example.org/counts.parquet"},
                }
            ]
        },
    )
    assert read_dataset_resources(dp) == (
        DatasetResource(
            path="counts.parquet",
            name="counts",
            hash=_GOOD_HASH,
            bytes=12345678,
            format="parquet",
            source=ResourceSource(type="url", ref="https://example.org/counts.parquet"),
        ),
    )


def test_descriptive_fields_wrong_typed_are_ignored_not_raised(tmp_path: Path) -> None:
    # bytes/format/mediatype carry no integrity weight -> present-but-wrong-typed is ignored
    dp = _write(
        tmp_path / "datapackage.yaml",
        {"resources": [{"path": "ok.csv", "bytes": "big", "format": 7, "mediatype": []}]},
    )
    assert read_dataset_resources(dp) == (DatasetResource(path="ok.csv"),)


def test_malformed_hash_raises(tmp_path: Path) -> None:
    # a DECLARED but malformed hash is a data bug -> loud, not silently dropped to None
    dp = _write(tmp_path / "datapackage.yaml", {"resources": [{"path": "ok.csv", "hash": "not-a-hash"}]})
    with pytest.raises(DatasetResourceError, match="hash"):
        read_dataset_resources(dp)


def test_pathless_entry_raises(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", {"resources": [{"name": "no-path"}]})
    with pytest.raises(DatasetResourceError, match="path"):
        read_dataset_resources(dp)


def test_non_mapping_entry_raises(tmp_path: Path) -> None:
    dp = _write(tmp_path / "datapackage.yaml", {"resources": ["scalar-entry"]})
    with pytest.raises(DatasetResourceError, match="mapping"):
        read_dataset_resources(dp)


def test_malformed_source_raises(tmp_path: Path) -> None:
    dp = _write(
        tmp_path / "datapackage.yaml",
        {"resources": [{"path": "ok.csv", "source": {"type": "bogus", "ref": "x"}}]},
    )
    with pytest.raises(DatasetResourceError, match="source"):
        read_dataset_resources(dp)


def test_absent_or_non_list_resources_returns_empty(tmp_path: Path) -> None:
    # top-level ABSENCE/ambiguity (file gone, or `resources` not a list) is "no
    # distributions", not a malformation -> (); only DECLARED entries are graded.
    missing = tmp_path / "nope.yaml"
    assert read_dataset_resources(missing) == ()
    scalar = _write(tmp_path / "scalar.yaml", {"resources": "not-a-list"})
    assert read_dataset_resources(scalar) == ()
