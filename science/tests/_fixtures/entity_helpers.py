from pathlib import Path

import yaml


def seed_project(root: Path) -> None:
    # Create minimal but valid science.yaml
    (root / "science.yaml").write_text(
        "name: entity-cli-test\n"
        "kind: research\n"
        "created: '2026-07-04'\n"
        "last_modified: '2026-07-04'\n"
        "status: active\n"
        "summary: Test project\n"
        "profile: research\n"
        "layout_version: 3\n"
        "knowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )

    # Create required directories
    for d in ["specs", "doc", "knowledge", "tasks", "code", "papers", "data", "models", "results", "entities"]:
        (root / d).mkdir(parents=True, exist_ok=True)

    # Create minimal CLAUDE.md and AGENTS.md
    (root / "CLAUDE.md").write_text("", encoding="utf-8")
    (root / "AGENTS.md").write_text("", encoding="utf-8")

    # Create minimal research-question.md
    (root / "entities" / "research-question.md").write_text(
        "---\nid: research-question:test\nkind: research-question\n"
        "title: Test Research Question\nstatus: open\n"
        "---\n\nTest question.\n",
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
