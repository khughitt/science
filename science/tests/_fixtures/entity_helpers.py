from pathlib import Path

import yaml


def seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: entity-cli-test\nknowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )


def write_markdown_entity(root: Path, rel_path: str, frontmatter: dict[str, object], body: str = "") -> Path:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body,
        encoding="utf-8",
    )
    return path
