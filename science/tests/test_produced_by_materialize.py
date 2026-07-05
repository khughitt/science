import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from rdflib import URIRef
from science_model.entities import CodeFileEntity, EntityType

from science_tool.graph.materialize import _build_dataset_from_sources, _eligible_code_files
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def _code(local_id: str, *, decision_bearing, executable: bool, status: str = "workflow-owned") -> CodeFileEntity:
    return CodeFileEntity(
        id=f"code-file:{local_id}",
        canonical_id=f"code-file:{local_id}",
        kind="code-file",
        type=EntityType.CODE_FILE,
        title=local_id,
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path=f"code/{local_id}",
        status=status,
        decision_bearing=decision_bearing,
        executable=executable,
    )


def test_eligible_code_files_matrix() -> None:
    entities = [
        _code("a.py", decision_bearing=True, executable=False),    # declared true -> eligible
        _code("b.py", decision_bearing=False, executable=True),    # declared false -> excluded
        _code("c.py", decision_bearing=None, executable=True),     # absent + executable -> eligible (fail-closed)
        _code("d.py", decision_bearing=None, executable=False),    # absent + non-executable library -> excluded
        _code("e.py", decision_bearing=True, executable=True, status="exploratory"),  # exempt -> excluded
        _code("f.py", decision_bearing=True, executable=True, status="retired"),      # exempt -> excluded
    ]
    eligible = _eligible_code_files(SimpleNamespace(entities=entities))
    assert eligible == {URIRef(PROJECT_NS["code-file/a.py"]), URIRef(PROJECT_NS["code-file/c.py"])}


def _project(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)
    code = tmp_path / "code"
    code.mkdir()
    (code / "run.py").write_text(
        '# science:code\n# decision_bearing: true\n# status: workflow-owned\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:x\nkind: dataset\ntitle: X\n"
        "status: active\norigin: derived\ntier: use-now\nproduced_by: [code-file:run.py]\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)


def _bears_on_pairs(ds) -> set[tuple[str, str]]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}


def test_decision_bearing_code_bears_on_its_dataset(tmp_path: Path) -> None:
    _project(tmp_path)
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        sources = load_project_sources(tmp_path, include_commons=False)
        ds = _build_dataset_from_sources(sources)
    finally:
        os.chdir(prev)
    code_uri = str(URIRef(PROJECT_NS["code-file/run.py"]))
    dataset_uri = str(URIRef(PROJECT_NS["dataset/x"]))
    assert (code_uri, dataset_uri) in _bears_on_pairs(ds)


def test_produced_by_dangling_ref_does_not_raise(tmp_path: Path) -> None:
    _project(tmp_path)
    # Point produced_by at a code-file that has no block (ghost) -> skip-on-miss.
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.write_text(dp.read_text().replace("code-file:run.py", "code-file:missing.py"), encoding="utf-8")
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        sources = load_project_sources(tmp_path, include_commons=False)
        ds = _build_dataset_from_sources(sources)  # must not raise
    finally:
        os.chdir(prev)
    assert ds is not None
