from pathlib import Path

from science_tool.federation import validate_federation


def _write_yaml(path: Path, body: str) -> None:
    (path / "science.yaml").write_text(body, encoding="utf-8")


def test_consistent_meta_with_two_children(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    b = tmp_path / "b"
    for directory in (meta, a, b):
        directory.mkdir()

    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
  - id: b
    path: {b}
    role: cancer-type
""",
    )
    _write_yaml(
        a,
        f"""
name: a
id: a
role: data-source
parent: {meta}
profile: research
research_question: "..."
""",
    )
    _write_yaml(
        b,
        f"""
name: b
id: b
role: cancer-type
parent: {meta}
profile: research
research_question: "..."
""",
    )

    issues = validate_federation(meta)
    assert issues == []


def test_child_missing_parent_field(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    meta.mkdir()
    a.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
""",
    )
    _write_yaml(
        a,
        """
name: a
id: a
role: data-source
profile: research
research_question: "..."
""",
    )
    issues = validate_federation(meta)
    assert any(issue.kind == "missing_parent" and issue.child_id == "a" for issue in issues)


def test_child_parent_points_elsewhere(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    other = tmp_path / "other"
    a = tmp_path / "a"
    for directory in (meta, other, a):
        directory.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
""",
    )
    _write_yaml(
        a,
        f"""
name: a
id: a
role: data-source
parent: {other}
profile: research
research_question: "..."
""",
    )
    issues = validate_federation(meta)
    assert any(issue.kind == "parent_mismatch" and issue.child_id == "a" for issue in issues)


def test_child_path_does_not_exist(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    meta.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {tmp_path / "missing"}
    role: data-source
""",
    )
    issues = validate_federation(meta)
    assert any(issue.kind == "child_path_missing" and issue.child_id == "a" for issue in issues)


def test_role_disagreement_between_meta_and_child(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    meta.mkdir()
    a.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
""",
    )
    _write_yaml(
        a,
        f"""
name: a
id: a
role: cancer-type
parent: {meta}
profile: research
research_question: "..."
""",
    )
    issues = validate_federation(meta)
    assert any(issue.kind == "role_mismatch" and issue.child_id == "a" for issue in issues)


def test_id_disagreement_between_meta_and_child(tmp_path: Path) -> None:
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    meta.mkdir()
    a.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
""",
    )
    _write_yaml(
        a,
        f"""
name: a
id: bee
role: data-source
parent: {meta}
profile: research
research_question: "..."
""",
    )
    issues = validate_federation(meta)
    assert any(issue.kind == "id_mismatch" and issue.child_id == "a" for issue in issues)
