from pathlib import Path

import yaml

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate._helpers import raw_frontmatter


class _Ctx:
    def __init__(self, root: Path) -> None:
        self.project_root = root


def test_dataset_frontmatters_covers_markdown_and_datapackage(tmp_path: Path) -> None:
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    (tmp_path / "doc" / "datasets" / "gtex.md").write_text(
        "---\nid: dataset:gtex\ntype: dataset\ntitle: GTEx\n---\nBody.\n", encoding="utf-8"
    )
    (tmp_path / "data" / "refcoll").mkdir(parents=True)
    (tmp_path / "data" / "refcoll" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "refcoll",
                "id": "dataset:refcoll",
                "type": "dataset",
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
