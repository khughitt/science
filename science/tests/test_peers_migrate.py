from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from science_tool.peers_migrate import MigrationError, migrate_project


def _write_science_yaml(project_root: Path, body: str) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    (project_root / "science.yaml").write_text(dedent(body).lstrip(), encoding="utf-8")


def _read_science_yaml(project_root: Path) -> dict:
    return yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8"))


def test_migrate_parent_to_peer(tmp_path: Path) -> None:
    parent = tmp_path / "meta"
    child = tmp_path / "child"
    _write_science_yaml(
        parent,
        """
        name: meta
        id: meta-project
        role: meta
        profile: research
        research_question: "..."
        """,
    )
    _write_science_yaml(
        child,
        """
        name: child
        id: child-project
        role: data-source
        parent: ../meta
        profile: research
        research_question: "..."
        """,
    )

    summary = migrate_project(child, dry_run=False)

    assert summary.migrated is True
    raw = _read_science_yaml(child)
    assert "parent" not in raw
    assert raw["peers"] == [{"id": "meta-project", "path": "../meta"}]


def test_migrate_children_to_peers(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    _write_science_yaml(
        meta,
        """
        name: meta
        id: meta-project
        role: meta
        profile: research
        research_question: "..."
        children:
          - id: child-a
            path: ../a
            role: data-source
          - id: child-b
            path: ../b
            role: cancer-type
        """,
    )

    summary = migrate_project(meta, dry_run=False)

    assert summary.migrated is True
    raw = _read_science_yaml(meta)
    assert "children" not in raw
    assert raw["peers"] == [
        {"id": "child-a", "path": "../a"},
        {"id": "child-b", "path": "../b"},
    ]


def test_migrate_empty_children_removes_legacy_field(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_science_yaml(
        project,
        """
        id: project
        children: []
        """,
    )

    summary = migrate_project(project, dry_run=False)

    assert summary.migrated is True
    raw = _read_science_yaml(project)
    assert "children" not in raw
    assert raw["peers"] == []


def test_migrate_null_children_fails_without_writing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_science_yaml(
        project,
        """
        id: project
        children: null
        """,
    )
    original_text = (project / "science.yaml").read_text(encoding="utf-8")

    with pytest.raises(MigrationError, match="children must be a list"):
        migrate_project(project, dry_run=False)

    assert (project / "science.yaml").read_text(encoding="utf-8") == original_text


@pytest.mark.parametrize(
    "children_yaml",
    [
        "  - just-a-string\n",
        "  - path: ../a\n",
        "  - id: child-a\n",
    ],
)
def test_migrate_malformed_children_fails_without_writing(tmp_path: Path, children_yaml: str) -> None:
    project = tmp_path / "project"
    _write_science_yaml(project, f"id: project\nchildren:\n{children_yaml}")
    original_text = (project / "science.yaml").read_text(encoding="utf-8")

    with pytest.raises(MigrationError, match="children"):
        migrate_project(project, dry_run=False)

    assert (project / "science.yaml").read_text(encoding="utf-8") == original_text


def test_migrate_existing_conflicting_peer_ids_fail_before_migration(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    _write_science_yaml(
        project,
        """
        id: project
        peers:
          - id: child-a
            path: ../a
          - id: child-a
            path: ../other-a
        children: []
        """,
    )
    original_text = (project / "science.yaml").read_text(encoding="utf-8")

    with pytest.raises(MigrationError, match="duplicate peer id 'child-a'"):
        migrate_project(project, dry_run=False)

    assert (project / "science.yaml").read_text(encoding="utf-8") == original_text


def test_migrate_existing_same_peer_id_and_path_is_allowed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_science_yaml(
        project,
        """
        id: project
        peers:
          - id: child-a
            path: ../a
        children:
          - id: child-a
            path: ../a
            role: data-source
        """,
    )

    first = migrate_project(project, dry_run=False)
    migrated_text = (project / "science.yaml").read_text(encoding="utf-8")
    second = migrate_project(project, dry_run=False)

    assert first.migrated is True
    assert _read_science_yaml(project)["peers"] == [{"id": "child-a", "path": "../a"}]
    assert second.migrated is False
    assert (project / "science.yaml").read_text(encoding="utf-8") == migrated_text


def test_migrate_idempotent(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    _write_science_yaml(
        meta,
        """
        name: meta
        id: meta-project
        children:
          - id: child-a
            path: ../a
            role: data-source
        """,
    )

    first = migrate_project(meta, dry_run=False)
    migrated_text = (meta / "science.yaml").read_text(encoding="utf-8")
    second = migrate_project(meta, dry_run=False)

    assert first.migrated is True
    assert second.migrated is False
    assert (meta / "science.yaml").read_text(encoding="utf-8") == migrated_text


def test_migrate_dry_run_does_not_write(tmp_path: Path) -> None:
    parent = tmp_path / "meta"
    child = tmp_path / "child"
    _write_science_yaml(
        parent,
        """
        id: meta-project
        """,
    )
    _write_science_yaml(
        child,
        """
        id: child-project
        parent: ../meta
        """,
    )
    original_text = (child / "science.yaml").read_text(encoding="utf-8")

    summary = migrate_project(child, dry_run=True)

    assert summary.migrated is True
    assert summary.note == "dry-run: no files written"
    assert (child / "science.yaml").read_text(encoding="utf-8") == original_text


def test_migrate_missing_parent_path_fails(tmp_path: Path) -> None:
    child = tmp_path / "child"
    _write_science_yaml(
        child,
        """
        id: child-project
        parent: ../missing
        """,
    )

    with pytest.raises(
        MigrationError,
        match=r"cannot migrate parent: '../missing'.*no science.yaml.*resolved path",
    ):
        migrate_project(child, dry_run=False)


def test_migrate_malformed_parent_yaml_fails_with_context(tmp_path: Path) -> None:
    parent = tmp_path / "meta"
    child = tmp_path / "child"
    parent.mkdir()
    (parent / "science.yaml").write_text("id: [\n", encoding="utf-8")
    _write_science_yaml(
        child,
        """
        id: child-project
        parent: ../meta
        """,
    )

    with pytest.raises(
        MigrationError,
        match=r"cannot migrate parent: '../meta'.*failed to parse parent YAML",
    ) as exc_info:
        migrate_project(child, dry_run=False)

    assert exc_info.value.__cause__ is not None


@pytest.mark.parametrize("parent_yaml", ["- not-a-mapping\n", "0\n", "", "null\n"])
def test_migrate_parent_yaml_must_be_mapping(tmp_path: Path, parent_yaml: str) -> None:
    parent = tmp_path / "meta"
    child = tmp_path / "child"
    parent.mkdir()
    (parent / "science.yaml").write_text(parent_yaml, encoding="utf-8")
    _write_science_yaml(
        child,
        """
        id: child-project
        parent: ../meta
        """,
    )
    original_text = (child / "science.yaml").read_text(encoding="utf-8")

    with pytest.raises(
        MigrationError,
        match=r"cannot migrate parent: '../meta'.*parent YAML.*mapping",
    ):
        migrate_project(child, dry_run=False)

    assert (child / "science.yaml").read_text(encoding="utf-8") == original_text


def test_migrate_null_parent_returns_unchanged(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_science_yaml(
        project,
        """
        id: project
        parent: null
        """,
    )
    original_text = (project / "science.yaml").read_text(encoding="utf-8")

    summary = migrate_project(project, dry_run=False)

    assert summary.migrated is False
    assert summary.note == "No legacy fields found; nothing to migrate."
    assert (project / "science.yaml").read_text(encoding="utf-8") == original_text


def test_migrate_no_legacy_fields_returns_unchanged(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_science_yaml(
        project,
        """
        id: project
        peers:
          - id: peer-a
            path: ../peer-a
        """,
    )
    original_text = (project / "science.yaml").read_text(encoding="utf-8")

    summary = migrate_project(project, dry_run=False)

    assert summary.migrated is False
    assert summary.note == "No legacy fields found; nothing to migrate."
    assert (project / "science.yaml").read_text(encoding="utf-8") == original_text
