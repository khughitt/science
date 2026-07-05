from pathlib import Path

import yaml

from science_tool.validate._helpers import dataset_frontmatters, raw_frontmatter


class _Ctx:
    def __init__(self, root: Path) -> None:
        self.project_root = root


def _ctx(root: Path) -> _Ctx:
    return _Ctx(root)


def test_dataset_frontmatters_covers_markdown_and_datapackage(tmp_path: Path) -> None:
    (tmp_path / "entities" / "datasets").mkdir(parents=True)
    (tmp_path / "entities" / "datasets" / "gtex.md").write_text(
        "---\nid: dataset:gtex\nkind: dataset\ntitle: GTEx\n---\nBody.\n", encoding="utf-8"
    )
    (tmp_path / "data" / "refcoll").mkdir(parents=True)
    (tmp_path / "data" / "refcoll" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "refcoll",
                "id": "dataset:refcoll",
                "kind": "dataset",
                "title": "Ref coll",
            }
        ),
        encoding="utf-8",
    )
    ids = {fm["id"] for fm in dataset_frontmatters(_Ctx(tmp_path))}  # type: ignore[arg-type]
    assert ids == {"dataset:gtex", "dataset:refcoll"}


def test_raw_frontmatter_tolerates_malformed_yaml(tmp_path: Path) -> None:
    path = tmp_path / "datapackage.yaml"
    path.write_text("id: [unterminated\n", encoding="utf-8")

    assert raw_frontmatter(path) == {}


def test_entity_frontmatters_discovers_papers_and_datapackage_datasets(tmp_path: Path) -> None:
    from science_tool.validate._helpers import entity_frontmatters

    (tmp_path / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    (tmp_path / "entities" / "papers").mkdir(parents=True)
    (tmp_path / "entities" / "papers" / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "kind: paper\n"
        "title: Adams\n"
        "dataset_usage:\n"
        "  - ref: dataset:gtex-v8\n"
        "    role: analyzed\n"
        "---\n",
        encoding="utf-8",
    )
    dp_dir = tmp_path / "data" / "gtex"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:gtex-v8\n"
        "kind: dataset\n"
        "title: GTEx\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n",
        encoding="utf-8",
    )

    rows = entity_frontmatters(_ctx(tmp_path))  # type: ignore[arg-type]

    by_id = {row["id"]: row for row in rows}
    assert by_id["paper:Adams2025"]["_path"] == "entities/papers/Adams2025.md"
    assert by_id["dataset:gtex-v8"]["_path"] == "data/gtex/datapackage.yaml"


def test_entity_frontmatters_tolerates_entity_datapackage_missing_title(tmp_path: Path) -> None:
    from science_tool.validate._helpers import entity_frontmatters

    dp_dir = tmp_path / "data" / "gtex"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:gtex-v8\n"
        "kind: dataset\n",
        encoding="utf-8",
    )

    rows = entity_frontmatters(_ctx(tmp_path))  # type: ignore[arg-type]

    by_id = {row["id"]: row for row in rows}
    assert by_id["dataset:gtex-v8"]["_path"] == "data/gtex/datapackage.yaml"


def test_entity_frontmatters_skips_datapackage_with_malformed_profiles(tmp_path: Path) -> None:
    from science_tool.validate._helpers import entity_frontmatters

    dp_dir = tmp_path / "data" / "gtex"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: 1\n"
        "id: dataset:gtex-v8\n"
        "kind: dataset\n"
        "title: GTEx\n",
        encoding="utf-8",
    )

    rows = entity_frontmatters(_ctx(tmp_path))  # type: ignore[arg-type]

    assert rows == []


def test_raw_frontmatter_shared_helper_reads_markdown_and_yaml(tmp_path: Path) -> None:
    from science_tool.commons.frontmatter import raw_frontmatter

    md = tmp_path / "entity.md"
    md.write_text("---\nid: paper:Adams2025\nkind: paper\n---\nBody\n", encoding="utf-8")
    yaml_path = tmp_path / "datapackage.yaml"
    yaml_path.write_text("id: dataset:gtex-v8\nkind: dataset\n", encoding="utf-8")

    assert raw_frontmatter(md)["id"] == "paper:Adams2025"
    assert raw_frontmatter(yaml_path)["id"] == "dataset:gtex-v8"
