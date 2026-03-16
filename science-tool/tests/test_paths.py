from pathlib import Path

from science_tool.paths import resolve_paths


def test_defaults_when_no_yaml(tmp_path: Path) -> None:
    paths = resolve_paths(tmp_path)
    assert paths.doc_dir == tmp_path / "doc"
    assert paths.code_dir == tmp_path / "code"
    assert paths.data_dir == tmp_path / "data"
    assert paths.knowledge_dir == tmp_path / "knowledge"
    assert paths.tasks_dir == tmp_path / "tasks"


def test_defaults_when_yaml_has_no_paths(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\nstatus: active\n")
    paths = resolve_paths(tmp_path)
    assert paths.doc_dir == tmp_path / "doc"


def test_mapped_paths(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\nstatus: active\npaths:\n  doc_dir: docs/\n  code_dir: src/\n")
    paths = resolve_paths(tmp_path)
    assert paths.doc_dir == tmp_path / "docs"
    assert paths.code_dir == tmp_path / "src"
    assert paths.data_dir == tmp_path / "data"


def test_models_dir_nested(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\nstatus: active\npaths:\n  models_dir: src/models/registry/\n")
    paths = resolve_paths(tmp_path)
    assert paths.models_dir == tmp_path / "src/models/registry"
